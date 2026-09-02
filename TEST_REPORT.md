# Rapport de tests — livraison FEBA

Environnement : Python 3.11.15 · Django 5.0.4 · PostgreSQL 16.13 ·
Node 22.22 · Chromium (Playwright) · Nginx 1.24.

Tout ce qui figure ici a été **exécuté**. Ce qui ne l'a pas été est listé
en section 7 et dans [`KNOWN_LIMITATIONS.md`](KNOWN_LIMITATIONS.md).

---

## 1. Archive source

| | |
|---|---|
| Origine | `https://drive.google.com/file/d/1_XB0DUpHUOFcqO-gGCzZfLzRgLRUp2zS/view` |
| Fichier | `feba.zip` |
| Taille | 34 457 093 octets — identique aux métadonnées Drive |
| Type (`file`) | `Zip archive data, at least v1.0 to extract` |
| **SHA-256** | `e06cdab5bad530087cf1a1c2c6917faff957d84b7ff48bca9e992dbb04d53c74` |
| `unzip -t` | **PASS** — 1 076 entrées, « No errors detected » |
| Racine | `feba_v6_version_finale_corrigee/` |

Le premier téléchargement a renvoyé une page HTML d'avertissement antivirus
(2 424 octets) : Drive interpose cet écran au-delà d'un certain volume. Les
octets réels ont été obtenus via `drive.usercontent.google.com` avec le
jeton de confirmation. **`file` et `sha256sum` ont été exécutés sur le
fichier obtenu, pas supposés.**

---

## 2. Suites backend

Exécutées sur les **deux** bases, conformément à la consigne.

### PostgreSQL 16.13 — la référence

```
DJANGO_SETTINGS_MODULE=feba_project.settings.test_postgres pytest tests -q
```

| | Avant | Après |
|---|---|---|
| Réussis | 1 111 | **1 164** |
| Échecs | **2** | **0** |
| Ignorés | 0 | 0 |
| Sous-tests | 530 | 571 |

### SQLite en mémoire

```
DJANGO_SETTINGS_MODULE=feba_project.settings.test_sqlite pytest tests -q
```

| | Avant | Après |
|---|---|---|
| Réussis | 1 151 | **1 163** |
| Échecs | **2** | **0** |
| Ignorés | 1 | 1 |

Les **2 échecs constatés dès l'archive source** portaient sur
`KNOWN_LIMITATIONS.md`, dont le contenu attendu avait disparu lors d'un
cycle antérieur (voir §4.4). Ils ne sont pas contournés : le document a été
rétabli.

> **Pourquoi les deux bases.** SQLite n'applique pas les longueurs de
> colonnes. Un premier jet d'un test de cette livraison passait une période
> de bulletin de 12 caractères dans une colonne `varchar(7)` : ignoré par
> SQLite, refusé par PostgreSQL (`StringDataRightTruncation`). Sans
> exécution PostgreSQL, l'erreur serait partie en production.

### Tests ajoutés

| Fichier | Tests | Objet |
|---|---|---|
| `test_institutional_phone.py` | 20 | P1 — numéro sur les documents réellement produits |
| `test_jitsi_production_domain.py` | 21 | P13 — domaine, jetons, rapport de santé, configuration livrée |
| `test_production_settings.py` | 10 | P15 — réglages de `globalfeba.com` |

**Chacun a été vérifié contre le code d'origine** (§4).

---

## 3. Frontend

```
npm test        → 21 fichiers, 185 tests, 185 réussis
npm run lint    → 0 erreur, 81 avertissements (préexistants)
npm run build   → PASS (13,7 s)
```

L'archive source comptait 82 avertissements ; un seul a été corrigé, dans
un fichier déjà modifié pour le flyer (`useEffect` importé sans usage).
Aucun avertissement n'a été introduit.

Test ajouté : `src/site/fhaFlyerDownload.test.jsx` — 6 tests.

---

## 4. Preuve que les correctifs corrigent quelque chose

Un test qui passe ne prouve rien s'il passait déjà. Chaque correctif a été
**retiré temporairement** pour vérifier que les tests échouent.

### 4.1 P1 — numéro institutionnel

Correctif retiré (`phone=academy.phone` rétabli, nettoyage de l'adresse
supprimé) :

```
9 failed, 13 passed
  ↳ test_recu_de_paiement_feba              ÉCHEC
  ↳ test_recu_de_paiement_feba_fha          ÉCHEC
  ↳ test_bulletin_feba / _feba_fha          ÉCHEC
  ↳ test_fiche_de_preinscription_feba       ÉCHEC
  ↳ test_le_numero_en_base_ne_decide_plus…  ÉCHEC (FEBA et FEBA FHA)
```

Correctif rétabli : **20 passed**.

### 4.2 P4 — instance publique dans les modèles de configuration

`JITSI_DOMAIN=meet.jit.si` remis dans `.env.prod.example` :

```
2 failed
  ↳ test_aucun_exemple_ne_propose_une_instance_publique      ÉCHEC
  ↳ test_le_modele_de_production_vise_l_instance_du_groupe   ÉCHEC
```

### 4.3 P15 — `CSRF_TRUSTED_ORIGINS`

Bloc retiré de `settings/prod.py` : **5 échecs**.

### 4.4 Les 2 échecs de l'archive source

Reproduits, diagnostiqués (contenu attendu absent de
`KNOWN_LIMITATIONS.md`), corrigés en rétablissant le document — pas en
affaiblissant l'assertion.

Au passage, un défaut de fond a été traité : le test cherchait le fichier à
la racine du dépôt, or seul `./backend` est monté dans le conteneur
(`./backend:/app`). Un cycle antérieur avait contourné le problème en
**dupliquant** `KNOWN_LIMITATIONS.md` dans `backend/` — deux copies d'un
document dont l'intérêt est d'être unique, et qui avaient déjà divergé. Le
test remonte désormais l'arborescence, et `docker-compose.yml` monte le
fichier de la racine dans le conteneur.

---

## 5. Documents réellement produits

Générés dans une base PostgreSQL dont les deux académies portaient
**délibérément** l'ancien numéro dans `School.phone` **et** recopié dans
`School.address` — l'état exact de la base de production.

| Document | En-tête produit |
|---|---|
| Reçu FEBA | `Akpakpa, Cotonou, Bénin \| Tél: 0160011717` |
| Reçu FEBA FHA | `Programme 100 % en ligne — … \| Tél: 0160011717` |
| Bulletin FEBA | `Akpakpa, Cotonou, Bénin \| Tél: 0160011717` |
| Bulletin FEBA FHA | `Programme 100 % en ligne — … \| Tél: 0160011717` |
| Fiche de préinscription FEBA | `… \| Tél: 0160011717` |
| Certificats et diplômes (×4) | aucun numéro — vérifié |

Les PDF ont été rendus en image et **inspectés visuellement**, pas
seulement analysés textuellement. Le bulletin ne portait auparavant
**aucun** numéro : il recomposait son en-tête à partir de la seule adresse.

`0196697363` est absent de tous, y compris sous ses écritures espacée,
pointée, tiretée et préfixée de l'indicatif.

---

## 6. Parcours en navigateur réel

Chromium, contre le **build de production** servi par Nginx avec la
configuration de production, backend Django et PostgreSQL.

### Parcours 1 — flyer FEBA FHA : **PASS**

| Contrôle | Résultat |
|---|---|
| Le lien ne renvoie plus vers `/feba-fha` | `href=/images/feba-fha/feba-fha-flyer.pdf` |
| Attribut `download` | `FEBA-French-Heritage-Academy-flyer.pdf` |
| N'ouvre pas d'onglet (saisie préservée) | `target` absent |
| Un vrai clic déclenche un téléchargement | oui |
| Le fichier reçu est un PDF | `%PDF-` |
| **Identique au flyer officiel, octet pour octet** | SHA-256 `c1024474…` |
| L'utilisateur reste sur le formulaire | URL inchangée |
| Erreurs JavaScript | aucune |
| Téléchargement sur mobile (390 px) | PASS |

Le lien se trouve à l'**étape 12/12** du formulaire : le parcours a été
joué en reprenant un brouillon, comme un parent qui revient finir son
inscription — le cas où perdre la saisie fait le plus de dégâts.

### Parcours 2 — reçu de paiement : **PASS**

Connexion administrateur → liste des paiements → génération du reçu →
téléchargement authentifié → analyse du PDF : `0160011717` présent,
`0196697363` absent.

### Parcours 3 & 4 — salles virtuelles FEBA FHA : **PASS**

| Contrôle | Résultat |
|---|---|
| Salles FHA listées | 3 |
| Référence à `meet.jit.si` ou `8x8.vc` | **aucune** |
| « Rejoindre » sans instance configurée | **HTTP 503** — jamais une URL publique |
| Rapport de santé pendant la panne | répond, état `unavailable` |
| Écran « Salles virtuelles » | bandeau de diagnostic affiché, aucune instance publique |

### Parcours 5 — cloisonnement inter-académies : **PASS**

| Contrôle | Résultat |
|---|---|
| Élèves visibles | FEBA 30 · FHA 3 |
| Élève visible des deux | **aucun** |
| **IDOR** : admin FEBA demandant un élève FHA par son id | **HTTP 404** |
| Salle partagée entre académies | **aucune** |

---

## 7. Infrastructure

| Contrôle | Commande | Résultat |
|---|---|---|
| Nginx SPA | `nginx -t` | PASS |
| Nginx production | `nginx -t` | PASS |
| Compose (4 fichiers) | analyse YAML | PASS |
| Cohérence Jitsi | `make jitsi-config-check` | PASS (4 notes) |
| Détection de mauvaise configuration | 6 erreurs injectées | **6 détectées**, sortie 1 |
| Migrations sur base vierge | `manage.py migrate` | PASS (dont `schools.0015`) |
| Données de démonstration | `seed_demo_data` | PASS, deux académies cohérentes |

### Flyer servi par Nginx

| Cas | Attendu | Obtenu |
|---|---|---|
| Fichier présent | `200 · application/pdf · attachment` | ✅ |
| Intégrité | identique au dépôt | ✅ SHA-256 |
| **Fichier retiré** | `404` | ✅ (et non un `200` HTML) |
| Route du SPA | `200 · text/html` | ✅ |

Le dernier cas est un défaut **constaté sur le site en ligne** :
`https://globalfeba.com/images/feba-fha/definitely-not-here.pdf` répond
aujourd'hui `200` avec la page de l'application.

### Visioconférence de production

```
$ make jitsi-health JITSI_TARGET=meet.globalfeba.com
État : DÉGRADÉ
  OK    configuration        Domaine « meet.globalfeba.com », identifiants JWT présents.
  OK    domaine_non_public   n'est pas une instance publique interdite.
  OK    signature_jeton      Un jeton de test a été signé.
 ÉCHEC  dns                  « meet.globalfeba.com » ne résout pas […]
```

**Diagnostic exact et attendu** : l'enregistrement DNS n'existe pas encore
(`getent hosts meet.globalfeba.com` → aucun résultat, alors que
`globalfeba.com` → `62.238.38.111`). Voir
[`MANUAL_PRODUCTION_ACTIONS.md`](MANUAL_PRODUCTION_ACTIONS.md).

---

## 8. Ce qui n'a pas été exécuté

- **Docker Compose** — aucun démon disponible. Les fichiers ont été
  validés syntaxiquement ; la pile n'a jamais démarré en conteneurs.
- **Un appel Jitsi réel** — l'infrastructure n'existe pas encore.
- **Un envoi d'e-mail réel** — backend en mémoire pendant les tests.
- **Les 13 tests e2e existants** — ils supposent la pile Docker.

Détail et conséquences dans [`KNOWN_LIMITATIONS.md`](KNOWN_LIMITATIONS.md).
