# FEBA — Itération V8

Quatre priorités : la devise, le paiement par carte, le diplôme, le
certificat. Trois sont terminées et vérifiées. La quatrième — les documents
officiels — est construite et éprouvée, mais **ne peut pas être achevée**
faute des deux images de fond, qui n'ont pas été transmises comme fichiers.
Ce point est traité en premier, parce qu'il change ce qui est livrable.

---

## Point bloquant : les deux PNG sont absents

`Diplôme FEBA(2).png` et `Certificat FEBA(2).png` ont été **affichés dans
la conversation**, mais aucun des deux n'est arrivé sous forme de fichier.
Le répertoire des pièces jointes de la session ne contient que l'archive
V7, deux PDF et cinq vidéos. Une recherche sur tout le disque ne trouve
rien qui corresponde.

Ce qui en découle, sans détour :

- le calibrage au millimètre **n'a pas été fait** ;
- la comparaison pixel à pixel des documents réels **n'a pas été faite** ;
- aucun diplôme ni certificat ne peut être **émis** par cette version.

Ce qui a été fait à la place : tout le reste. Le moteur documentaire est
complet, verrouillé sur l'empreinte des fonds, testé sur un fond
synthétique de mêmes dimensions, et il **refuse d'émettre** tant que les
fonds réels ne sont pas installés et calibrés. Ce refus n'est pas un
contournement, c'est la garantie : il rend impossible la remise d'un
diplôme dont personne n'a vérifié qu'il est juste.

Détail complet : `DIPLOMA_CERTIFICATE_FIDELITY_REPORT.md`.

**Pour débloquer** : déposer les deux fichiers, puis

```bash
python manage.py install_document_template --template diploma_feba --file "…/Diplôme FEBA(2).png"
python manage.py document_calibrate --template diploma_feba
python manage.py document_compare  --template diploma_feba
```

La commande d'installation vérifie dimensions **et** SHA-256 avant de
copier quoi que ce soit.

---

## P0 — FEBA FHA facture en dollars

### Ce qui n'allait pas

Onze écrans écrivaient `FCFA` en dur, et `Payment` ne stockait aucune
devise. Un encaissement FHA de 125,50 $ s'affichait « 125,50 FCFA ».

Le reçu PDF était pire : `f"{payment.amount:,.0f} FCFA"` en sortait
**« 126 FCFA »**, chiffres et lettres. Le montant en toutes lettres fait
foi en cas de litige — ce n'était pas un défaut d'affichage, c'était un
faux document.

### Ce qui a été fait

`School.currency_code` est la seule autorité. Symbole, nom, décimales et
locale en **dérivent** : une colonne séparée pourrait afficher « FCFA » sur
une académie dont le code vaut `USD`.

Les montants sont des entiers en unité mineure (`amount_minor`,
BigInteger). Aucun `float` n'intervient sur une somme d'argent. Deux
devises ne s'additionnent jamais — `Money.__add__` lève une erreur, et les
totaux consolidés sont ventilés : `$1,500.00 · 500 000 FCFA`.

Vérification en direct :

```
POST /api/payments/  {"amount":"80.00","currency":"XOF","amount_minor":999999}
→ 201  {"currency":"USD","amount_display":"$80.00"}
```

Migration exécutée sur la base réelle : 270 paiements, `amount_minor` total
`8 550 000` — identique à la somme des décimaux. Aucune valeur modifiée.

Commandes `audit_payment_currencies` et `repair_payment_currencies`
classent chaque paiement en conforme / affichage / **ambigu** / orphelin.
La réparation **refuse de s'exécuter** s'il reste un cas ambigu : convertir
silencieusement un historique reviendrait à réécrire une comptabilité sur
une hypothèse.

Audit sur la base réelle : 276 paiements, 0 anomalie,
`FEBA 8 550 000 FCFA` / `FEBA_FHA $601.50`.

Détail : `MULTI_CURRENCY_REPORT.md`.

---

## P1 — Paiement par carte

### Trois règles

**Le serveur décide du montant.** Un modèle `FeeSchedule` publie les tarifs
par académie, année, niveau et nature de frais. Le parent choisit une
**ligne**, jamais une somme. Un `amount` transmis n'est lu que d'un membre
de l'administration, et seulement hors grille.

Vérifié en navigateur : le panneau ne propose **aucun champ de montant**, et
la requête émise n'en transporte aucun.

**La redirection n'est pas une preuve.** Aucun appel ne permet de déclarer
un succès depuis le navigateur. Seul le webhook, signé et vérifié sur le
corps brut, crée l'encaissement. La page de retour dit « en cours de
vérification », pas « payé ».

**Tout est idempotent.** Clé d'idempotence par tentative, unicité des
événements **en base** (deux instances du serveur peuvent recevoir le même
événement au même instant), réutilisation d'une tentative ouverte au double
clic, remboursement plafonné par contrainte de base.

Les événements hors séquence sont traités : un `succeeded` reçu après un
`failed` l'emporte ; l'inverse n'efface pas une recette.

### Ce qui n'est jamais stocké

Numéro de carte, expiration, cryptogramme, jeton brut. Le modèle n'a aucun
champ pour les recevoir, et un test le vérifie en énumérant les champs
déclarés.

### État réel

**Le code est complet ; aucun compte marchand n'est branché.** Aucune clé
valide n'a été fournie, et le projet n'en invente pas. Observé en direct :

```
POST /api/payments/card/checkout/
→ 502  Invalid API Key provided: sk_test_***********************LIDE

Journal : FEBA_FHA  $125.50  failed  | Invalid API Key provided…
```

C'est le comportement attendu, et la preuve qu'aucune interface factice ne
simule un encaissement.

Détail : `CARD_PAYMENT_INTEGRATION_REPORT.md`,
`STRIPE_CONFIGURATION_GUIDE.md`.

---

## P2 / P3 — Diplôme et certificat

Voir le point bloquant ci-dessus. Ce qui est en place :

- fond **verrouillé** sur dimensions + SHA-256 ; un ré-export aux mêmes
  dimensions est refusé ;
- A4 paysage 297 × 210 mm, rapport d'aspect du fond **préservé** (le mode
  `contain` évite un étirement de 0,09 % qui déplacerait tout de 0,1 mm) ;
- gabarits JSON en millimètres, quatre champs variables chacun, rien
  d'autre ;
- un nom trop long réduit la police puis **fait échouer** le rendu — jamais
  de troncature ;
- signature et cachet apposés **seulement** si un fichier officiel existe ;
  « YOUR SEAL » reste visible à défaut ;
- planche de calibrage millimétrée, harnais de comparaison pixel à pixel
  produisant un score et une image de différence ;
- historique complet : six états, immuabilité de l'émis, remplacement sans
  disparition, numérotation séquentielle verrouillée en base, empreintes
  SHA-256 du PDF et du gabarit ;
- stockage **hors du répertoire public**, accès par vue authentifiée avec
  vérification sur l'élève, `Cache-Control: private, no-store` ;
- l'aperçu est produit par **le même moteur** que le document.

Détail : `DIPLOMA_CERTIFICATE_FIDELITY_REPORT.md`.

---

## Corrections de passage

| Défaut | Où | Portée |
|---|---|---|
| Reçu FHA libellé « 126 FCFA » | `payments/pdf_generator.py` | P0 |
| Reçu FHA au nom de Cotonou (`School.objects.first()`) | idem | P0 |
| Notifications « {amount} FCFA » | `payments/views.py` | P0 |
| KPI de recettes en `float` sans devise | `dashboard/views.py` | P0 |
| Total parent additionnant des devises (`parseFloat`) | `parent/Payments.jsx` | P0 |
| Parent FHA sans profil ni enfants liés | `seed_demo_data.py` | P1 |
| Seed non rejouable (`MultipleObjectsReturned`) | idem | robustesse |
| Connexion E2E validant l'ancienne session | `e2e/…mjs` | tests |

---

## Vérifications exécutées

| Suite | Résultat |
|---|---|
| pytest PostgreSQL | **673 passés** |
| pytest SQLite | **672 passés, 1 ignoré** |
| Vitest | **109 passés** |
| ESLint | **0 erreur** (83 avertissements préexistants) |
| Build de production | réussi |
| `seed_check` | **20 contrôles passés** |
| `audit_payment_currencies` | 276 paiements, 0 anomalie |
| `document_templates_check` | 2 gabarits, émission bloquée — état exact annoncé |
| E2E navigateur | voir `e2e/rapport-v8.txt` |

Tests ajoutés cette itération : 54 (paiement carte) + 40 (documents) + 3
(devise au tableau de bord) = **97**.

---

## Ce qui n'est pas livré

1. **Calibrage et comparaison des documents réels** — bloqués par l'absence
   des deux PNG. Tout ce qui les rend possibles est livré et testé.
2. **Encaissement réel par carte** — bloqué par l'absence de compte
   marchand. Le code est complet ; la vérification des identifiants échoue
   honnêtement contre l'API réelle de Stripe.
3. **Aucune signature de directeur** n'est fournie : la zone reste vide.

Aucun de ces trois points n'est présenté comme terminé, et aucun n'a été
contourné par une approximation.
