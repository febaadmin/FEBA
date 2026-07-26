# TEST_REPORT.md — Missions V4 → V8 (26/07/2026)

## Résultats V8

| # | Suite | Commande | Tests | Réussis | Échecs | Ignorés |
|---|---|---|---|---|---|---|
| 1 | Backend **SQLite** | `DJANGO_SETTINGS_MODULE=…test_sqlite pytest --no-migrations -q` | 394 | **393** | 0 | **1** |
| 2 | Backend **PostgreSQL 16** | `DJANGO_SETTINGS_MODULE=…test_postgres pytest -q` | 394 | **394** | 0 | **0** |
| 3 | Frontend | `npx vitest run` | 70 (9 fichiers) | **70** | 0 | 0 |
| 4 | ESLint | `npx eslint src` | — | **0 erreur** (63 avertissements hérités) | 0 | — |
| 5 | Build production | `npx vite build` | — | **✓ built** | 0 | — |

### Le test ignoré (SQLite uniquement)

`tests/test_parent_student.py:325` — test de **concurrence multi-thread**.
SQLite en mémoire verrouille la table entière (« database table is locked ») ;
il exige un vrai serveur de base. **Il s'exécute et réussit sur PostgreSQL**
(d'où 394/394 sans aucun ignoré en ligne 2). Aucun test n'est donc réellement
laissé de côté.

### PostgreSQL : ce que SQLite ne pouvait pas prouver

La suite PostgreSQL applique la **chaîne de migrations complète** (impossible
sur la SQLite embarquée : une migration historique utilise une syntaxe refusée
— limitation **pré-existante**, vérifiable sur un test antérieur à la V8, d'où
`--no-migrations`). Elle valide donc aussi : les 3 migrations V8, les
contraintes d'unicité réelles, les transactions et la concurrence.

### Suites ajoutées en V8

| Fichier | Tests | Objet |
|---|---|---|
| `tests/test_profile_creation.py` | 16 | création Enseignant (régression matricule), atomicité, doublons, permissions, isolation établissement, Élève, Parent |
| `tests/test_technical_incidents.py` | 20 | 500 réelle → incident + notification, dédoublonnage, sanitisation, permissions, cycle de traitement, date de résolution |
| `tests/test_grade_weighting_and_scale.py` | 19 | poids unique (12+5 = 8,50), cas limites, barèmes /10 et /20, appréciations |
| `tests/test_pdf_stamps.py` | 22 | deux cachets distincts, mentions supprimées, positions, non-chevauchement, textes non tronqués |
| `tests/test_data_migrations.py` | 5 | logique des migrations de données (avant/après, idempotence) |

### Vérifications navigateur (réelles, non automatisées)

Création d'un profil Enseignant **depuis le formulaire**, sur une base
présentant un **trou de séquence** (`count()+1` = `ENS-2026-0006`, déjà pris) :
profil créé avec **`ENS-2026-0007`**, 2 classes et 2 matières conservées,
modification sans 500. Incidents : page, compteurs, filtres, cloche, changement
de statut, admin **403**, anonyme **401**. Notes : 8,50 en base, via l'API et
dans le résumé. Parent : tableau de bord chargé, moyennes présentes. Site
public : 5 slides, 6 albums / 42 médias dont la vidéo, formulaire contact 201.
Documents : reçus (court, partiel, soldé, duplicata, multiligne) et bulletins
(court, chargé, primaire, collège) **rendus en images et inspectés**.


## Résultats V7

```bash
cd backend && DJANGO_SETTINGS_MODULE=feba_project.settings.test_sqlite \
  .venv-test/bin/python -m pytest --no-migrations -q     # 311 passed, 1 skipped
cd frontend && npx vitest run                            # 70 passed
npx eslint src                                           # 0 erreur
npx vite build                                           # ✓ built
```

Ajouts V7 :

| Suite | Fichier | Tests | Couvre |
|---|---|---|---|
| Backend | `tests/test_grade_precision.py` | 5 | saisir 10 → 10.00 (DB+API) ; 14 valeurs 0..20 ; bulk ; modification |
| Backend | `tests/test_document_branding.py` | 6 | nom avec « & », GROUPE ÉDUCATIF présent, GROUPE SCOLAIRE absent, cachet embarqué, 1 page |
| Frontend | `src/utils/gradeInput.test.js` | 8 | 10 reste 10 ; décimales ; virgule ; bornes ; signe |

Vérif navigateur : formulaire notes (champ texte décimal, 10 immuable) ;
bulletin & reçu réels (noms + cachet) ; galerie vidéo (contrôles, readyState 4) ;
Admissions (corps entiers) ; façade (panneau visible). PDF réels extraits +
rendus PNG (aucune fabrication).

## Résultats V4 + V5 + V6



## Résultats V6.2 (conformité visuelle exacte aux captures annotées)

```bash
cd backend && DJANGO_SETTINGS_MODULE=feba_project.settings.test_sqlite \
  .venv-test/bin/python -m pytest --no-migrations -q     # 300 passed, 1 skipped
cd frontend && npx vitest run                            # 62 passed (8 fichiers)
npx eslint src                                           # 0 erreur
npx vite build                                           # ✓ built
```

- **Nouveau fichier** `src/site/visual-conformity.test.jsx` (6 cas) : vérifie le
  **slug exact** attendu à chaque emplacement corrigé — pas seulement qu'une
  image existe, mais que c'est **la bonne** :
  - carrousel slide 1 = `campus-logo` ;
  - « Notre campus » (fallback) = `[campus-logo, campus-facade-logo,
    campus-devise, campus-cour]`, **sans** `campus-facade` ni `campus-fresque` ;
  - mosaïque d'accueil = `campus-facade-logo` (et **pas** `campus-fresque`) ;
  - À propos « La direction » = `apropos-direction-2` (et **pas**
    `apropos-direction`) + cartes distinctes ;
  - Académique = `bilingue-accompagnement` avec focal `50% 66%`.
- `mediaMeta.test.js` : invariant slug ↔ fichier maintenu après ajout de
  `campus-facade-logo`, `campus-devise`, restauration d'`apropos-direction-2`.
- Vérif navigateur (captures 375 + 1440 + DOM) : les 4 corrections conformes ;
  cadrage Académique correct sur desktop **et** mobile (overlay responsive).

## Résultats V6.1 (corrections visuelles finales sur captures annotées)

```bash
cd backend && DJANGO_SETTINGS_MODULE=feba_project.settings.test_sqlite \
  .venv-test/bin/python -m pytest --no-migrations -q     # 300 passed, 1 skipped
cd frontend && npx vitest run                            # 56 passed (7 fichiers)
npx eslint src                                           # 0 erreur
npx vite build                                           # ✓ built
```

- `mediaMeta.test.js` valide l'invariant bidirectionnel slug ↔ fichiers après
  ajout de 4 médias et **suppression** de 3 (apropos-direction,
  apropos-direction-2, galerie-mosaique-3) : chaque slug a ses fichiers
  800+1600 **et** chaque fichier a une entrée de focal.
- `seed_website` idempotent + élagage : « Notre campus » −2, « Petite enfance »
  +1 (crèche), « Moments FEBA » −1 (mosaïque bannie).
- Vérif navigateur déterministe (DOM) : slide 1 = `campus-logo` ; mosaïque =
  `campus-fresque` ; focals vignettes = 50/66, 50/68, 66/46, 66/46, 52/64 ;
  overlays hero `hero-left`+`hero-gold` présents ; `apropos-direction*` /
  `galerie-mosaique-3` absents du DOM.

## Résultats V6 (carrousel/galerie, dédoublonnage, recadrages, menu, saisie groupée)

```bash
cd backend && DJANGO_SETTINGS_MODULE=feba_project.settings.test_sqlite \
  .venv-test/bin/python -m pytest --no-migrations -q
# → 300 passed, 1 skipped (concurrence PostgreSQL, documentée), 46 subtests passed

cd frontend && npx vitest run          # → 56 passed (7 fichiers)
npx eslint src                         # → 0 erreur (62 avertissements, base projet)
npx vite build                         # → ✓ built (~8 s)
```

Détail des ajouts V6 :

| Suite | Fichier | Tests | Couvre |
|---|---|---|---|
| Backend | `tests/test_bulk_grades.py` | 16 | atomicité, rollback, erreurs indexées, permissions (enseignant/admin/superadmin/parent/anonyme), IDOR, doublons, coefficient |
| Frontend | `src/components/grades/BulkGradeModal.test.jsx` | 6 | charge utile groupée, succès, mapping erreurs par ligne, validations cliente |
| Frontend | `src/site/carousel-gallery.test.jsx` | 9 | 0/1/N slides, repli galerie vide/erreur/pleine, déduplication `siteDefaults` |

**Régressions détectées par la passe complète et corrigées :**

1. `tests/test_website.py::FocalPointTests::test_gallery_items_expose_focal` —
   assertion sur l'ancien point focal de `academique-participation` (`82% 28%`)
   alignée sur la valeur V6 seedée voulue (`26% 64%`, enseignante en bas-gauche
   hors mur crème). *Correction : test.*
2. `src/i18n/translations.js` — 4 clés dupliquées (`no-dupe-keys`) introduites
   avec les libellés de saisie groupée, retirées (valeurs EN identiques, aucun
   changement de comportement). *eslint : 4 erreurs → 0.*

E2E navigateur (session enseignant réelle + site public 375/1280/1920) :
voir `BULK_GRADES_REPORT.md` §4.3 et `VISUAL_FIXES_REPORT.md`.

## Résultats V5 (corrections visuelles)

```bash
cd backend && DJANGO_SETTINGS_MODULE=feba_project.settings.test_sqlite \
  .venv-test/bin/python -m pytest --no-migrations -q
# → 284 passed, 1 skipped (concurrence PostgreSQL), 46 subtests passed

cd frontend && npx vitest run   # → 41 passed (5 fichiers)
npx eslint src --ext .js,.jsx --quiet   # → 0 erreur
npx vite build                  # → ✓ built (~10 s, chunks identiques V4)
```

Nouveaux tests V5 : `frontend/src/site/mediaMeta.test.js` (6 — chaque
fichier packagé a un point focal, chaque entrée du registre correspond à un
fichier réel, positions valides, overlays 100 % couleurs de marque) ;
`backend/tests/test_website.py::FocalPointTests` (4 — focal exposé par
l'API avec les valeurs seedées, bornes 0–100 validées, PATCH admin
répercuté sur l'API publique).

Vérifications navigateur V5 réellement effectuées :
- captures pleine page AVANT/APRÈS des 10 pages publiques × 3 largeurs
  (livraison_v5/captures/avant|apres, 60 fichiers) ;
- accueil aux 9 largeurs imposées 320/375/390/430/768/1024/1280/1440/1920
  (captures/breakpoints) ;
- 0 débordement horizontal à 320 px sur les 12 pages (scrollWidth mesuré) ;
- 36 images accueil, 0 cassée après lazy-load ; console sans erreur ;
- slides 4 et 5 vérifiées interactivement en mobile (texte lisible, sujets
  entiers, plus de flèche sous le titre) ;
- non-régression ERP : login admin → dashboard 200, notes 200 ; login
  parent → moyennes + appréciation « PEUT MIEUX FAIRE » (12,67) intactes.


# Rappel V4

Tous les résultats ci-dessous proviennent de commandes réellement exécutées
sur cette machine (macOS, Python 3.14.5 via `backend/.venv-test`, Node/Vite).

## 1. Tests backend (pytest, SQLite en mémoire)

```bash
cd backend
DJANGO_SETTINGS_MODULE=feba_project.settings.test_sqlite \
  .venv-test/bin/python -m pytest --no-migrations -q
```

| Étape | Résultat |
|---|---|
| **Baseline avant mission** | 219 passed, 1 skipped |
| Après P1+P3 | 238 passed, 1 skipped (2 anciens tests mis à jour : ils attendaient l'ancienne échelle « Bien » — la règle métier a changé) |
| Après P2 | 261 passed, 1 skipped |
| **Final (P4 inclus)** | **280 passed, 1 skipped, 46 subtests passed** |

Le skip unique est documenté : test de concurrence multi-threads
impossible sur SQLite en mémoire (verrou de table globale), exécuté sur la
stack PostgreSQL (`settings.test_postgres`) — Docker indisponible sur cette
machine au moment de la mission (voir KNOWN_LIMITATIONS).

Nouveaux fichiers de tests :
- `tests/test_note_types_appreciations.py` — 19 tests + 40 subtests
  (bornes du barème, normalisation, invalides, migration bulletins, P1 API).
- `tests/test_password_reset.py` — 23 tests (matrice de permissions
  complète, effets, journal, parcours must_change_password).
- `tests/test_website.py` — 19 tests (contenu public, formulaires +
  honeypot, non-exposition des soumissions, permissions admin, seed).

`manage.py check` : « System check identified no issues (0 silenced). »

## 2. Tests frontend (vitest, jsdom)

```bash
cd frontend && npx vitest run
```

| Étape | Résultat |
|---|---|
| Baseline avant mission | 22 passed (3 fichiers) |
| **Final** | **35 passed (4 fichiers)** |

Nouveau : `src/site/site.test.jsx` — 13 tests : layout + menu complet +
lien Connexion → /login, menu mobile accessible (aria-expanded), accueil
sans crash (carrousel administrable, sections), chiffres masqués si non
renseignés / affichés si saisis, actualités (état vide sans fausses
données, erreur API propre, liste réelle), formulaire contact (validations
frontend, succès, erreurs backend), formulaire préinscription (champs
obligatoires, envoi), 404 publique.

`npx eslint src --quiet` : 0 erreur (1 clé i18n dupliquée détectée et
corrigée pendant l'audit).

## 3. Compilation de production

```bash
cd frontend && npx vite build
```

✓ built in ~8 s — bundle initial 295 Ko (95,8 Ko gzip) + chunks lazy par
page (site vitrine : 1–19 Ko). Avant la mission : chunk unique de
1 534 Ko (407 Ko gzip). Build servi et vérifié via
`BACKEND_ORIGIN=http://localhost:8000 npx vite preview` (page d'accueil
publique fonctionnelle sur http://localhost:4173, données API chargées).

## 4. Vérifications navigateur réellement effectuées (E2E)

Environnement : backend Django `dev_sqlite` (schéma `migrate --run-syncdb`,
`seed_demo_data` + `seed_website`), frontend Vite, navigateur intégré.

| # | Parcours | Constat |
|---|---|---|
| 1 | Ouverture de `/` | Site vitrine public affiché (hero carrousel 5 slides administrables, sections complètes, pas de section chiffres car stats non renseignées) |
| 2 | Navigation site (desktop) | Accueil, À propos, Galerie (mosaïque + albums), Contact OK ; aucun débordement horizontal |
| 3 | Accès connexion depuis le menu | Bouton « Connexion » → `/login` (page bilingue existante) |
| 4 | Connexion Administrateur | admin@feba.bj → tableau de bord admin (données chargées) |
| 5 | Réinitialisation mdp d'un enseignant | Modal complet (identité, rôle, avertissement, règles, confirmation explicite) → toast de succès |
| 6 | Tentative interdite | La liste admin ne contient aucun superadmin ; appel API direct admin→superadmin (id=1) → **HTTP 403** ; mot de passe cible intact |
| 7 | Note « Interrogation / Devoir de classe » | Créée via le modal UI (élève Koffi Codjo, Français, T1, 17,5) — API : `note_type="interrogation"`, libellé neuf, **appréciation TRÈS SATISFAISANT** |
| 8 | Note « Examen / Évaluation » | Modification de la même note via PATCH en session réelle → 200, libellé « Examen / Évaluation » |
| 9 | Anciennes notes | Tableau des notes : les notes seedées `interrogation`/`examen` affichent les nouveaux libellés (compatibilité des données) |
| 10 | Appréciations en base | Bulletins stockés : 13,80/13,59/13,18 → ACCEPTABLE (migration + seed corrects) |
| 11 | Connexion enseignant avec mdp temporaire | Redirection automatique vers « Nouveau mot de passe requis » ; impossible d'accéder aux espaces avant changement |
| 12 | Changement forcé | Nouveau mot de passe accepté → arrivée sur le tableau de bord enseignant |
| 13 | Connexion Parent | `/parent/home` sans page blanche ; cartes enfants avec moyenne générale + **appréciation PEUT MIEUX FAIRE (12,67)**, Moy T1/T2, Français, Anglais |
| 14 | Moyennes parent (page Notes) | 4 cartes par enfant : Générale 12,67 · Française 13,84 · Anglaise 11,07 · **Bilingue 12,73** — aucun tiret indu |
| 15 | Notification | Clic cloche → panneau (la note 17,50 créée en test y figure) ; clic → page Notes correcte, session conservée, pas de redirection annonces |
| 16 | Formulaires publics (réseau réel, anonyme) | contact → **201** ; préinscription → **201** ; honeypot rempli → **400** ; soumissions visibles dans l'écran admin « Site vitrine » (statut Nouveau) |
| 17 | Mobile (375×812) | Accueil, menu hamburger accessible (tous liens + Mon espace + Inscrire mon enfant), page Contact — aucune coupure ni débordement |
| 18 | Console navigateur | Aucune erreur sur l'ensemble des parcours |

## 5. Commandes d'environnement propre exécutées

```bash
# Base de démo recréée de zéro pendant la mission :
cd backend
rm -f db_dev.sqlite3
DJANGO_SETTINGS_MODULE=feba_project.settings.dev_sqlite .venv-test/bin/python manage.py migrate --run-syncdb
DJANGO_SETTINGS_MODULE=feba_project.settings.dev_sqlite .venv-test/bin/python manage.py seed_demo_data
DJANGO_SETTINGS_MODULE=feba_project.settings.dev_sqlite .venv-test/bin/python manage.py seed_website
DJANGO_SETTINGS_MODULE=feba_project.settings.dev_sqlite .venv-test/bin/python manage.py runserver 8000
# Frontend :
cd frontend && BACKEND_ORIGIN=http://localhost:8000 npm run dev
```

Comptes de démonstration (seed) :
superadmin@feba.bj / SuperAdmin@2024 · admin@feba.bj / Admin@2024 ·
prof.math@feba.bj (mot de passe modifié pendant l'E2E : MonNouveauProf#26) ·
parent1@feba.bj / Parent@2024 · eleve1@feba.bj / Student@2024.
