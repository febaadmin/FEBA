# INSTALLATION — FEBA multi-académies

Ce document décrit l'installation vérifiée dans le cadre de la présente
livraison. `INSTALLATION_GUIDE.md`, présent dans l'archive d'origine, reste la
référence détaillée du projet.

## Prérequis

Docker et Docker Compose. En installation manuelle : Python 3.11, Node 22,
PostgreSQL 15 et Redis.

## Installation Docker (recommandée)

```bash
cp .env.example .env          # puis renseigner les variables
make install
make seed
make seed-check
```

Le frontend est servi sur `http://localhost:5173`, l'API sur
`http://localhost:8000/api`, Mailpit sur `http://localhost:8025`.

Commandes de contrôle disponibles : `make documents-ready`,
`make branding-check`, `make jitsi-health`, `make celery-health`,
`make install-check`.

**VALIDATION DOCKER LOCALE REQUISE** : ces cibles n'ont pas pu être exécutées
dans l'environnement de préparation de cette livraison (pas de démon Docker).
Elles sont reprises telles quelles depuis le `Makefile` de l'archive source,
qui n'a pas été modifié.

## Installation manuelle — VÉRIFIÉ PAR EXÉCUTION

C'est le mode réellement utilisé pour valider cette livraison.

### Backend

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements/dev.txt      # dev.txt inclut base.txt

export DJANGO_SETTINGS_MODULE=feba_project.settings.test_sqlite
python manage.py check
python manage.py makemigrations --check --dry-run
python -m pytest -q
```

Résultats obtenus : `check` sans problème ; aucune migration manquante ;
**1 112 tests passants, 1 ignoré**.

`requirements/dev.txt` est nécessaire pour la suite complète : `PyMuPDF`
(inspection des PDF générés) et `numpy` (calibrage documentaire) sont requis
par dix modules de tests.

Le module `settings.test_sqlite` permet de tout exécuter sans PostgreSQL,
Redis ni WeasyPrint. Le seul test ignoré est un test de concurrence
multi-threads qui exige un vrai serveur de base de données.

### Frontend

```bash
cd frontend
npm ci
npm run lint     # 0 erreur, 82 avertissements préexistants
npm test         # 179 tests passants
npm run build    # build Vite réussi
```

## Nettoyage des données antérieures

Voir `PREVIOUS_USAGE_CLEANUP.md`. Toujours commencer par `--dry-run`, et
prendre un instantané Restic avant toute exécution réelle.
