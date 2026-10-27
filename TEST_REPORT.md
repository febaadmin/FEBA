# FEBA — Rapport de tests : programme linguistique et identités des académies

27 octobre 2026. Les commandes sont exécutées par les scripts de vérification locaux. Les résultats depuis l'**extraction neuve** de l'archive sont consignés dans `DELIVERY_VERIFICATION_LANGUES_IDENTITE.txt`, à côté de l'archive.

## Campagnes sur le dépôt (commit `062da38`, arbre propre)

Backend exécuté **dans l'image Docker avec LibreOffice** (`backend/Dockerfile.dev`), avec Mailpit local et sans serveur plugNmeet réel.

| Suite | Résultat |
|---|---|
| PostgreSQL 16 | **1943 passed**, 3 skipped (intégration plugNmeet réelle : `PLUGNMEET_TEST_URL` non défini), 708 subtests |
| SQLite | **1933 passed**, 14 skipped (concurrence réservée à PostgreSQL, Mailpit, plugNmeet), 708 subtests |
| `makemigrations --check` | No changes detected |

Après `062da38`, les tests du programme ont été renforcés (section « Autres matières », rapport des programmes), avec 21 tests au vert. L'onglet des notes a aussi été corrigé. Ces changements sont rejoués dans la campagne depuis l'extraction neuve.

Frontend, sur le code final :

| Suite | Résultat |
|---|---|
| Vitest | **410 passed** (53 fichiers) |
| ESLint | 0 erreur (73 avertissements préexistants) |
| `vite build` | réussi |

## Nouveaux tests

| Fichier | Ce qu'il prouve |
|---|---|
| `backend/tests/test_curriculum_language_mode.py` (21 tests) | création via l'API pour les 3 modes (champ obligatoire, valeur inconnue refusée) ; contexte d'entité ; langues des matières par mode ; parcours par mode et politique monolingue ; copie d'année ; notes unitaires et en masse refusées hors programme ou hors classe ; créneau refusé ; **bulletins PDF relus** : français /10 sans section anglaise ni 60/40, anglais /20 sans section française, bilingue 60/40 avec matière commune comptée une fois ; moyennes pondérées et note manquante ignorée ; diagnostic, refus, confirmation sans suppression ; retour à vide refusé ; diagnostic réservé au super administrateur ; classement de la migration (règle et données) ; académie non configurée inchangée ; `init_academies` ; rapport en lecture seule |
| `backend/tests/test_academy_identity_features.py` | capacités calculées pour FEBA, FEBA FHA et deux académies « testete » ; non falsifiables ; rattachement par réglage ; rapports mensuels refusés (403) sans nom d'académie ; admissions vides |
| `frontend/src/layouts/menuIdentity.test.jsx` | en-tête de 5 espaces au nom de testete (long, accentué, tronqué) ; menus par rôle et par académie ; « Toutes les Académies » |
| `frontend/src/pages/admin/Schedule.tabs.test.jsx` | onglets dynamiques pour une académie, et pour 2, 7, 19 académies |
| `frontend/src/components/AcademyBadge.test.jsx` | badge, teinte stable, `FeatureGate` |
| `frontend/src/pages/superadmin/Academies.test.jsx` (+4) | programme obligatoire, diagnostic, confirmation |
| `frontend/src/utils/classLanguage.test.js` (+4) | matières communes, parcours et catégories proposés |
| `e2e/parcours-langues-identite.mjs` | navigateur réel, deux phases (super administrateur, administrateur de testete) |

Tests modifiés, **sans affaiblissement** :
- `test_academy_types_creation.py` : le jeu de données porte désormais le programme, et un cas « programme obligatoire » est ajouté.
- `test_fha_forms.py` : le message attendu nomme le module « Admissions en ligne », et l'absence de « FEBA » est vérifiée.
- `Website.prereg.test.jsx` : le contexte simulé porte la capacité, et un cas « académie sans préinscriptions » est ajouté.
- `VirtualRoomEnded.test.jsx` : le lien s'appelle « Retour à l'accueil ».
- `e2e/academies.mjs` : voir `FINAL_REPORT.md` § C.

## Navigateur réel (Chrome, pile locale : PostgreSQL, Django, Vite)

| Scénario | Résultat |
|---|---|
| `parcours-langues-identite.mjs`, phase création (super administrateur) | PASS |
| `parcours-langues-identite.mjs`, phase administrateur de testete (connexion, rechargement, reconnexion) | PASS |
| `academies.mjs` | PASS (30 → 3 → 33 → 30 élèves ; bascules de 0,7 à 1,2 s) |
| `espaces-anglais.mjs`, `parcours-preinscription-feba.mjs`, `site-public-anglais.mjs` | PASS |

## Non exécuté

- Intégration plugNmeet réelle : **NOT RUN**.
- Hetzner, SMTP Hostinger, Twilio : **BLOCKED**.
