# Archive finale

Date : 04/11/2026.

| Élément | Valeur |
|---|---|
| Commit validé | `1c12e5b` (« Dossier de clôture de la phase 3 (#78) »), sur `main`, avec toute la CI au vert |
| Archive | `FEBA_1c12e5b.zip`, produite par `git archive --format=zip --prefix=FEBA/ 1c12e5b` |
| SHA-256 | `9ddca95f4fff39a18a9c31409947c305a451269e5e31b256174e949274cc90b7` |
| Fichiers | 1 468 |

Ce rapport a été ajouté **après** l'archive : il n'y figure donc pas. L'archive correspond exactement au commit `1c12e5b`.

## Correspondance avec le commit

- **Reproductible** : une seconde production donne le même SHA-256.
- **Contenu** : `diff -rq` entre l'archive extraite et `git archive --format=tar 1c12e5b` ne trouve aucune différence. Les règles `export-ignore` de `.gitattributes` excluent les anciens scripts E2E, les captures et les anciens rapports.

## Contrôle du contenu

| Contrôle | Résultat |
|---|---|
| `.env`, `.env.prod`, clés `*.pem` et `*.key`, `__pycache__`, `node_modules`, `dist`, `*.sqlite3`, `.DS_Store` | aucun |
| gitleaks v8.28.0, sans historique, valeurs masquées | 6 signalements, tous classés en phase 2 comme valeurs de test ou faux positifs : exemple d'en-tête WebSocket (`JITSI_PRODUCTION_ACTIONS.md`), valeurs de test (`test_production_preflight.py` ×2, `test_v11_jitsi_moderators_and_jwt.py`), empreinte publique du client plugNmeet v2.5.3 (`meet_plugnmeet.sh`), secret factice du contrôle de configuration (`compose_config_check.sh`) |
| Anciens mots de passe de démonstration | 2 fichiers, **volontairement** : `check_demo_passwords.py`, qui détecte les comptes qui les acceptent encore, et `test_securite_fenetre_alertes.py`, qui teste cette détection. Ces valeurs sont publiques depuis l'origine du dépôt et ne sont plus acceptées par les comptes de démonstration. Les retirer est une décision humaine |

## Reconstruction depuis la copie vierge

L'archive est extraite dans un dossier neuf, sans le dépôt git.

| Étape | Résultat |
|---|---|
| Image backend (`backend/Dockerfile.prod`) | construite ; utilisateur `uid=10001(feba)` ; celery 5.3.6, kombu 5.6.2, redis 5.0.3, Django 5.2.18 |
| Image frontend (`frontend/Dockerfile.prod`) | construite |
| Image nginx (`nginx/image`) | construite |
| `manage.py check` | aucun problème |
| `migrate` sur une base PostgreSQL vide, puis `migrate --plan` | « No planned migration operations » |
| `makemigrations --check` | « No changes detected » |
| Tests PostgreSQL : `test_password_reset`, `test_technical_incidents`, `test_surveillance_sauvegarde`, `test_reference_fha_concurrence`, `test_securite_attaques` | 87 tests, OK |

La suite complète (backend PostgreSQL et SQLite, frontend, E2E 210 contrôles, images, sécurité) tourne en CI sur ce même commit.

## Limites

- Pas de reconstruction sur une machine physique distincte : Docker local, dossier neuf.
- L'archive n'inclut pas les fichiers `.env` de production, qui ne sont jamais versionnés. Leur sauvegarde relève de Restic, sur le serveur.
