# Vérification V8 — sorties brutes

Toutes les sorties ci-dessous ont été produites sur cette instance, sur le
commit livré. Aucune n'est reconstituée.

---

## 1. Suite backend — PostgreSQL

```
$ DJANGO_SETTINGS_MODULE=feba_project.settings.test_postgres python -m pytest -q
673 passed, 443 warnings, 60 subtests passed in 71.41s
```

## 2. Suite backend — SQLite

```
$ DJANGO_SETTINGS_MODULE=feba_project.settings.test_sqlite python -m pytest -q
672 passed, 1 skipped, 442 warnings, 60 subtests passed in 46.84s

SKIPPED [1] tests/test_parent_student.py:325: Test de concurrence
multi-threads : SQLite en mémoire verrouille la table entière
(« database table is locked ») — nécessite un vrai serveur de base de
données. Exécuté sur PostgreSQL.
```

## 3. Tests frontend

```
$ npx vitest run
 Test Files  14 passed (14)
      Tests  109 passed (109)
```

## 4. ESLint

```
$ npx eslint src --ext .js,.jsx
✖ 83 problems (0 errors, 83 warnings)
```

83 avertissements, tous préexistants (variables inutilisées, `setState`
dans un effet sur des pages du site vitrine). **0 erreur.**

## 5. Build de production

```
$ npm run build
dist/assets/index-CvQLxgjj.js   398.59 kB │ gzip: 130.85 kB
✓ built in 12.46s
```

## 6. Isolation des académies

```
$ python manage.py seed_check
  ✓ Aucune classe sans année scolaire
  ✓ Aucune académie en ligne dans l'emploi du temps présentiel
  ✓ Aucune école présentielle dans les séances en ligne
  ✓ Aucun créneau FEBA reliant deux académies
  ✓ Aucune séance FEBA FHA reliant deux académies

Académies : FEBA=47 compte(s) · FEBA_FHA=6 compte(s)
Élèves    : FEBA=30 · FEBA_FHA=3
Emplois du temps : FEBA=50 créneau(x) · FEBA_FHA=3 séance(s) en ligne

✓ 20 contrôles passés — isolation intacte.
```

---

## 7. P0 — Devises

### Audit sur la base réelle

```
$ python manage.py audit_payment_currencies
Audit des devises — 276 paiement(s)

Conforme : 276

Totaux par académie et par devise :
  FEBA         8 550 000 FCFA
  FEBA_FHA     $601.50

Aucune anomalie de devise.
```

Les deux totaux sont **séparés**. Aucun taux de conversion n'existe dans le
projet, et aucune ligne ne les additionne.

### Migration des données existantes

270 paiements migrés. `amount_minor` total : `8 550 000` — identique à la
somme des décimaux, XOF n'ayant pas de subdivision. Aucune valeur modifiée.

### La devise transmise par le client est ignorée

```
$ POST /api/payments/
  {"amount":"80.00","currency":"XOF","amount_minor":999999, …}

→ 201  envoyé currency=XOF amount_minor=999999
       reçu   USD $80.00
```

### Chaque académie dans sa devise, via l'API

```
-- Paiements FEBA FHA --
   USD $125.50 | Naomi Adjovi
   USD $75.00  | Naomi Adjovi
   USD $125.50 | Kofi Mensah

-- Paiements FEBA --
   XOF 35 000 FCFA | Nadège Ahouansou
   XOF 35 000 FCFA | Josiane Dansou
   XOF 35 000 FCFA | Amina Tokpanou

-- Tableau de bord --
  FHA  USD | recettes année : $681.50
  FEBA XOF | recettes année : 0 FCFA
```

Le `0 FCFA` de FEBA vient du KPI qui filtre sur l'année **civile**, alors
que les paiements de démonstration sont datés du début de l'année
**scolaire**. Comportement antérieur à cette itération, sans effet sur les
devises.

---

## 8. P1 — Paiement par carte

### La configuration guidée refuse les combinaisons dangereuses

```
$ payments_setup --secret-key sk_test_… --publishable-key pk_live_…
  ✗ La clé secrète et la clé publique ne sont pas dans le même mode
    (test / production) : les paiements créés dans l'un ne seraient jamais
    confirmés dans l'autre.
CommandError: Configuration refusée. Aucune clé n'a été écrite : une
configuration à moitié juste est pire qu'absente.

$ payments_setup --secret-key pk_test_… --publishable-key sk_test_…
  ✗ STRIPE_SECRET_KEY n'a pas le format attendu (^sk_(test|live)_[A-Za-z0-9]+$).
  ✗ STRIPE_PUBLISHABLE_KEY n'a pas le format attendu (^pk_(test|live)_[A-Za-z0-9]+$).
  ✗ Les clés secrète et publique semblent inversées. Exposer une clé
    secrète au navigateur donnerait à quiconque le contrôle du compte
    marchand.
CommandError: Configuration refusée.
```

### La vérification interroge réellement le prestataire

```
$ python manage.py payments_check
  ✓ Paiement par carte activé
  ✓ STRIPE_SECRET_KEY renseignée
  ✓ STRIPE_PUBLISHABLE_KEY renseignée
  ✓ STRIPE_WEBHOOK_SECRET renseignée
  ✓ Mode « test » cohérent avec la clé
  · URL publique : http://localhost:5173

  [appel réel] GET https://api.stripe.com/v1/account → 401
  error_message='Invalid API Key provided: sk_test_***********************LIDE'

  ✗ Identifiants acceptés par le prestataire
    Clé refusée par le prestataire (révoquée ou erronée).
```

**C'est le résultat attendu : aucun compte marchand n'est branché.** Le
projet n'invente pas de clé.

### Le montant du navigateur est ignoré, et l'échec est réel

```
$ POST /api/payments/card/checkout/
  {"student":54,"payment_type":"mensualite",
   "amount":"1.00","amount_minor":1,"currency":"XOF"}

→ 502  Invalid API Key provided: sk_test_***********************LIDE
```

La tentative est tracée, pas perdue :

```
$ GET /api/payments/card/transactions/
  FEBA_FHA    $125.50  failed  | Invalid API Key provided: sk_test_…LIDE
```

Le montant retenu est **$125.50** — celui de la grille tarifaire — et non
le `1.00` transmis.

### Tarifs publiés, vus par le parent

```
$ GET /api/payments/card/fees/?student=54
  académie FEBA_FHA | devise USD
    inscription $75.00  | Frais d'inscription (démonstration)
    mensualite  $125.50 | Mensualité (démonstration)
```

### Webhook non signé

```
$ POST /api/payments/webhook/stripe/  (sans en-tête de signature)
→ 400
```

Sans `STRIPE_WEBHOOK_SECRET` configuré, la même requête donne **503** :
aucun événement ne peut être authentifié, ils sont donc tous refusés.

### Anti-IDOR

```
$ POST /api/payments/card/checkout/   (parent FEBA, élève FEBA FHA)
→ 404
```

404 et non 403 : confirmer l'existence d'un élève qu'on n'a pas le droit de
voir est déjà une fuite.

---

## 9. P2 / P3 — Documents officiels

### État réel des gabarits

```
$ python manage.py document_templates_check

Gabarits de documents officiels

  ✗ Certificat FEBA (certificate_feba v1)
      Fond        : Certificat FEBA(2).png (1491×1055 px)
      Installé    : NON
      Calibré     : NON (tolérance 0.2 mm)
      Champs      : 4
      Émission impossible :
        - Le fond « Certificat FEBA(2).png » n'est pas installé
          (backend/document_templates/originals). Voir originals/README.md.
        - Le gabarit n'est pas calibré : les positions n'ont jamais été
          confrontées à l'image réelle. Un nom décalé de trois millimètres
          reste un diplôme aux yeux de celui qui le reçoit.

  ✗ Diplôme FEBA (diploma_feba v1)
      Fond        : Diplôme FEBA(2).png (1492×1054 px)
      Installé    : NON
      Calibré     : NON (tolérance 0.2 mm)
      Champs      : 4
      Émission impossible : [idem]

  2 gabarit(s) sur 2 ne peuvent pas émettre de document.
  Un aperçu filigrané « NON CALIBRÉ » reste disponible pour travailler la
  mise en page.
```

### Les deux PNG sont absents du système de fichiers

```
$ ls /root/.claude/uploads/<session>/
3ab55626-feba_v3.zip
419758e4-FEBA_French_Heritage_Academy_Guidance.pdf
423eaf65-WhatsApp_Video_20260731_at_20.06.45.mp4
4a8c657b-WhatsApp_Video_20260731_at_20.06.41.mp4
82101b52-feba_multi_academies_v7.zip
b79e5cf0-Enregistrement_de_l_e_cran_20260731_a__19.22.42.mov
e5b45f9a-Enregistrement_de_l_e_cran_20260731_a__19.22.00.mov
f2750377-FEBA_Recap_Site_Web_Pour_Chris.pdf
f63b8651-WhatsApp_Video_20260731_at_20.06.44.mp4

$ find / -iname "*ipl*me*.png" -o -iname "*ertificat*.png"
/usr/share/icons/Adwaita/16x16/mimetypes/application-certificate.png
```

Aucune des deux images de document. **Le calibrage au millimètre et la
comparaison pixel à pixel des documents réels n'ont donc pas été
exécutés.**

### La comparaison pixel à pixel est éprouvée sur un fond de mêmes dimensions

Test `RenderFidelityTests::test_le_fond_est_reproduit_pixel_a_pixel` :
fond synthétique 1492 × 1054 en dégradé (une image unie ne prouverait rien,
un étirement ne s'y verrait pas), rendu PDF rastérisé à la résolution du
fond, comparaison point par point. Écart mesuré **inférieur à 1 %**, bruit
de rééchantillonnage compris.

Test `test_le_rapport_d_aspect_du_fond_est_preserve` : le rapport rendu
égale le rapport source à 4 décimales, et le décentrage résiduel reste sous
0,2 mm.

Test `test_la_page_est_un_a4_paysage` : 841,89 × 595,28 pt, soit
297 × 210 mm exactement.

---

## 10. Parcours navigateur

Scénario `e2e/devises-et-documents.mjs`, Chromium réel, application servie
depuis le **build de production**. Un navigateur neuf par profil : vider
`localStorage` ne suffit pas — encore authentifiée, l'application redirige
vers l'espace en cours et le scénario se poursuivrait avec le compte
précédent, si bien qu'une vérification d'isolation entre académies
passerait pour de mauvaises raisons.

```
=== P0 — Devise imposée par l'académie ===
  OK  FEBA FHA affiche des dollars
  OK  aucun « FCFA » sur l'écran FEBA FHA
  OK  tableau de bord FEBA FHA sans « FCFA »
  OK  FEBA affiche des francs CFA
  OK  aucun montant en dollars sur l'écran FEBA

=== P1 — Paiement par carte ===
  OK  le panneau de paiement par carte est présent
  OK  aucun champ de saisie de montant n'est proposé au parent
  OK  les tarifs publiés par l'académie sont affichés
  OK  les tarifs FHA ne sont pas libellés en FCFA
  OK  le clic déclenche bien une demande de paiement
  OK  la requête ne transporte AUCUN montant — {"student":31,"payment_type":"inscription"} {"student":31,"payment_type":"inscription"}

=== P2 / P3 — Diplômes et certificats ===
  OK  le gabarit du diplôme est listé
  OK  le gabarit du certificat est listé
  OK  l'état réel des gabarits est annoncé, sans le masquer

=== Réseau et console ===
  OK  aucune erreur serveur
  INFO  2 réponse(s) 502 sur le paiement carte : le prestataire refuse la clé de démonstration. C'est le comportement attendu sans compte marchand — et la preuve qu'aucune interface factice ne simule un encaissement.
  OK  aucune erreur de console inattendue

Requêtes API observées : 54
Captures : /home/user/FEBA/e2e/captures

Toutes les vérifications V8 sont passées.
```

Captures : `captures/v8-01` à `v8-06`.

Le point le plus parlant est la ligne du milieu : le corps de la requête
de paiement est `{"student":31,"payment_type":"inscription"}`. **Aucun
montant.** Le serveur lit son propre tarif.

---

## 11. Retest du ZIP livré, extrait dans un dossier neuf

L'archive `feba_multi_academies_v8.zip` a été extraite dans un répertoire
vierge, hors du dépôt, puis testée telle quelle.

### Ce que l'archive ne contient pas

```
node_modules   : 0
venv           : 0
.env           : 0
db.sqlite3     : 0
private_media  : 0      (documents officiels : données personnelles)
dist-livraison : 0
*.pyc          : 0
```

`.env.example` est bien présent, avec ses cinq clés de paiement — toutes
vides. `backend/document_templates/originals/` ne contient que son
`README.md` : les fonds officiels ne sont pas versionnés.

### Suites exécutées sur l'extrait

```
$ pytest (PostgreSQL)   → 676 passed
$ pytest (SQLite)       → 675 passed, 1 skipped
$ npx vitest run        → 109 passed
$ npx eslint src        → 0 error, 83 warnings
$ npm run build         → ✓ built in 13.91s
$ manage.py document_templates_check
                        → 2 gabarits, émission bloquée, état annoncé
```

Les compteurs dépassent de trois ceux de la section 1 : les derniers tests
de devise sur le tableau de bord ont été ajoutés après cette première
exécution. C'est l'extrait qui fait foi — il correspond au commit livré.

### Le bundle Git est réellement clonable

```
$ git clone feba_multi_academies_v8.bundle clonetest
$ git -C clonetest log --oneline -1
9ed7ed8 Rapports V8, scénario navigateur et livraison
```
