# FEBA — Rapport de tests : audit du 28 octobre 2026

## Campagne de référence

Commit `1e464ff`, exporté par `git archive` dans un répertoire isolé. Image `backend/Dockerfile.dev` : Python 3.12.16, LibreOffice 25.2, Django 5.2.18.

| Suite | Résultat | Durée |
|---|---|---|
| PostgreSQL 16 (+ Mailpit, `FEBA_REQUIRE_LIBREOFFICE=1`) | 1959 passed, 0 failed, 4 skipped, 717 subtests | 13 min 20 s |
| SQLite | 1948 passed, 0 failed, 15 skipped, 717 subtests | 10 min 36 s |
| `check` + `makemigrations --check --dry-run` | aucun problème, aucune migration manquante | — |

### Tests ignorés et raison

| Test | PostgreSQL | SQLite | Raison |
|---|---|---|---|
| `test_plugnmeet_integration` (3) | ignoré | ignoré | aucun serveur plugNmeet de test (`PLUGNMEET_TEST_URL`) — **NOT RUN** |
| `test_diploma_ready_after_install` (1) | ignoré | ignoré | contrôle du suivi git : sans objet sur une archive extraite (vérifié sur le dépôt) |
| Concurrence réelle (7) | **exécutés** | ignorés | SQLite ne permet pas l'écriture concurrente |
| Mailpit (3) | **exécutés** | ignorés | service SMTP de test présent seulement sur la campagne PostgreSQL |

## Frontend (code final)

| Contrôle | Résultat |
|---|---|
| Vitest | 413 passed (55 fichiers) |
| ESLint | 0 erreur, 74 avertissements préexistants |
| `vite build` | réussi |
| `npm audit --omit=dev --audit-level=high` | aucune vulnérabilité haute ou critique |

## Contrôles ciblés

| Contrôle | Résultat |
|---|---|
| `tests/test_bulletin_one_page.py` (12 tests, 9 sous-tests) | réussi |
| `test_delai_de_conversion_depasse` + `GlobalDeadlineTests`, rejoués 5 fois dans l'image | 5/5 |
| Contre-épreuve du délai global (ancien `conversion.py`) | 2 échecs → défaut détecté |
| Contre-épreuve frontend (fichiers d'origine) | 15 échecs → défauts détectés |
| Migration `main` → branche sur copie peuplée | effectifs, empreintes et sommes identiques |
| Ancien code sur schéma migré | écritures élève, note, paiement, matière, école réussies |
| `pip-audit` (base + prod) après correction | aucune vulnérabilité connue |
| Images Docker de production (backend, frontend) | construites ; backend : Python 3.12.16, LibreOffice, Django 5.2.18 |

## Navigateur réel (Chrome ; pile locale PostgreSQL, Django, Vite)

| Scénario | Résultat |
|---|---|
| `parcours-bulletin-une-page.mjs` : aperçu depuis l'écran et 6 PDF officiels | 7 PDF, 1 page chacun |
| `parcours-langues-identite.mjs` (création + administrateur testete) | vert |
| `academies.mjs`, `espaces-anglais.mjs`, `parcours-preinscription-feba.mjs`, `site-public-anglais.mjs` | verts |

La première exécution après un changement de dépendances échoue à la connexion : Vite ré-optimise les dépendances et recharge la page (« lockfile has changed »), alors que la requête de connexion réussit (200). L'exécution suivante passe. Il s'agit d'un démarrage à froid de l'environnement de développement, pas d'un défaut de l'application.

## Non exécuté

- La production (lecture comme écriture) : **BLOQUÉ**, accès refusé.
- plugNmeet réel : **NOT RUN**.
