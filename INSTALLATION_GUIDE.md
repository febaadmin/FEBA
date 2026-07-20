# INSTALL_V6.md — Guide d'installation (V6, 20/07/2026)

## 1. Prérequis

- Docker 24+ et Docker Compose 2+ (voie recommandée), ou Python 3.12+ / Node 20+
  pour un lancement hors Docker.
- Git.

## 2. Installation avec Docker (recommandé)

```bash
unzip feba_v1_v6_complet.zip && cd feba_v1
cp .env.example .env          # puis renseigner les secrets (voir §5)
make dev                      # PostgreSQL → Redis → backend (migrate auto) → Celery → frontend
make seed                     # données de démonstration
```

Accès :

| Service | URL |
|---|---|
| Site vitrine + application | http://localhost:5173 |
| API | http://localhost:8000/api/ |
| Admin Django | http://localhost:8000/django-admin/ |

Suivre le démarrage : `make logs`.

## 3. Contenu du site vitrine (carrousel + galerie)

Le contenu public est seedé par une commande dédiée :

```bash
docker compose exec backend python manage.py seed_website
```

Elle installe/actualise : paramètres du site, **5 slides de carrousel**,
**6 albums de galerie** (Vie de classe, Activités et épanouissement, Notre
campus, Petite enfance, FEBA Online, Moments FEBA), la vidéo de présentation,
et les **points focaux** de chaque média.

> **V6 — élagage anti-doublon** : la commande supprime désormais les médias
> d'album qui ne font plus partie de la liste voulue
> (`exclude(image_path__in=…).delete()`). Un re-seed ne laisse donc plus de
> doublon ni d'orphelin. Elle est **idempotente** : on peut la relancer.

Même si la base est vide, le front **ne reste jamais vide** : `HeroCarousel` et
la galerie basculent sur les médias packagés (`src/site/siteDefaults.js`).

## 4. Lancement hors Docker (développement)

```bash
# Backend (SQLite de développement)
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
DJANGO_SETTINGS_MODULE=feba_project.settings.dev_sqlite python manage.py migrate
DJANGO_SETTINGS_MODULE=feba_project.settings.dev_sqlite python manage.py seed_website
DJANGO_SETTINGS_MODULE=feba_project.settings.dev_sqlite python manage.py runserver 8000

# Frontend (autre terminal)
cd frontend && npm ci
BACKEND_ORIGIN=http://localhost:8000 npm run dev
```

> ⚠️ `dev_sqlite` **désactive les migrations** (`_DisableMigrations`). Après un
> changement de schéma, recréer la base : supprimer le fichier SQLite puis
> `migrate --run-syncdb` et re-seeder.

## 5. Variables d'environnement

Partir de `.env.example` (fourni, **sans aucun secret réel**). Renseigner au
minimum `SECRET_KEY`, les accès PostgreSQL/Redis, `ALLOWED_HOSTS`,
`JITSI_DOMAIN`. Ne jamais committer le `.env` réel.

## 6. Vérification de l'installation

```bash
# Tests backend (SQLite, sans migrations)
cd backend && DJANGO_SETTINGS_MODULE=feba_project.settings.test_sqlite \
  .venv-test/bin/python -m pytest --no-migrations -q
# attendu : 300 passed, 1 skipped

# Tests + qualité + build frontend
cd frontend && npx vitest run     # attendu : 56 passed
npx eslint src                    # attendu : 0 erreur
npx vite build                    # attendu : ✓ built
```

Puis, dans le navigateur (http://localhost:5173) :
carrousel d'accueil à **5 slides** (flèches + points), page **Galerie**
remplie, menu desktop **sur une seule ligne**, hamburger propre sur mobile.
