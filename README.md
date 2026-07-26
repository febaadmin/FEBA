# FEBA School Management — v3 bilingue (FR/EN)

Plateforme SaaS multi-établissements de gestion scolaire. Conçue à l'origine pour le Groupe Scolaire FEBA (Cotonou, Bénin), désormais architecturée pour héberger plusieurs établissements clients de façon isolée (multi-tenant) : écoles primaires, collèges, lycées, centres de formation.

> 🌍 **Application entièrement bilingue français–anglais** : voir
> [`AUDIT_REPORT.md`](./AUDIT_REPORT.md), [`CHANGELOG_FIXES.md`](./CHANGELOG_FIXES.md)
> et [`VERIFICATION_CHECKLIST.md`](./VERIFICATION_CHECKLIST.md).

## Bilinguisme (FR / EN)

- **Page de connexion** : tous les textes sont affichés simultanément en
  français et en anglais (« Connexion / Login », « Mot de passe / Password »…).
- **Après connexion** : sélecteur **FR | EN** dans l'en-tête de chaque espace
  (superadmin, admin, enseignant, parent, élève). Le changement est
  **immédiat**, sans déconnexion.
- **Persistance** : le choix est conservé dans le navigateur
  (localStorage `feba-lang`) **et** dans le profil utilisateur
  (`preferred_language`, PATCH `/api/auth/me/`). À la reconnexion, la
  préférence du profil est prioritaire.
- **Architecture** : un seul système centralisé — `frontend/src/i18n/`
  (`index.js` : `t()`, `useI18n()`, `tBoth()`, `dateLocale()` ;
  `translations.js` : dictionnaire FR→EN, la chaîne française est la clé,
  repli automatique sur le français). Les messages du backend sont localisés
  via `Accept-Language` (LocaleMiddleware) et le dictionnaire frontend.
- **Ajouter/corriger une traduction** : éditer
  `frontend/src/i18n/translations.js` (une ligne par chaîne).

> 📋 **Audit et refonte v29** : voir [`RAPPORT_V29_AUDIT_REFONTE.md`](./RAPPORT_V29_AUDIT_REFONTE.md) pour le détail des failles de sécurité corrigées (isolation multi-tenant), de la refonte du pivot "années scolaires", et du périmètre couvert.
>
> 📦 **Installation locale** : [`guide_installation_local.pdf`](./guide_installation_local.pdf)
> 🚀 **Déploiement production** : [`guide_deploiement_production.pdf`](./guide_deploiement_production.pdf)

## Stack technique
- **Backend** : Django 5 + DRF + JWT + Celery + Channels (WebSocket)
- **Frontend** : React 18 + Vite + TailwindCSS + Recharts
- **Base de données** : PostgreSQL 16
- **Cache / Queue** : Redis 7
- **PDF** : ReportLab (bulletins + reçus)
- **Visioconférence** : module « Salles virtuelles » basé sur Jitsi Meet (open source) — cours en ligne, réunions, historique de participation ; domaine configurable via `JITSI_DOMAIN`
- **Infra** : Docker + Docker Compose + Nginx (prod)
- **Multi-tenant** : isolation par établissement au niveau API (voir `backend/apps/core/tenancy.py`)

## Prérequis
- Docker 24+ et Docker Compose 2+
- Git

## Installation DEV — 4 commandes

```bash
# 1. Dézipper et se placer dans le dossier
unzip feba_v29.zip && cd feba_v29

# 2. Démarrer tous les services (build automatique)
make dev

# 3. Charger les données de démonstration (attendre que le backend soit "healthy")
make seed

# 4. Accéder à l'application
# Frontend : http://localhost:5173
# API      : http://localhost:8000/api/
# Admin    : http://localhost:8000/django-admin/
```

> **Note :** `make dev` démarre PostgreSQL → Redis → backend (check + migrate automatique) → Celery → frontend, dans l'ordre garanti. Suivre la progression en temps réel : `make logs`

Pour la procédure détaillée et la résolution de problèmes, voir `guide_installation_local.pdf`.

## Comptes de démo

| Rôle        | Email                  | Mot de passe  | Portée |
|-------------|------------------------|---------------|--------|
| Superadmin  | superadmin@feba.bj     | SuperAdmin@2024 | Plateforme (tous établissements) |
| Admin       | admin@feba.bj          | Admin@2024    | École FEBA |
| Admin       | directeur@feba.bj      | Admin@2024    | École FEBA |
| Enseignant  | prof.math@feba.bj      | Teacher@2024  | École FEBA |
| Enseignant  | prof.francais@feba.bj  | Teacher@2024  | École FEBA |
| Parent      | parent1@feba.bj        | Parent@2024   | École FEBA |
| Élève       | eleve1@feba.bj         | Student@2024  | École FEBA |

## Commandes utiles

```bash
make dev         # Démarre l'environnement (build + up + attente healthcheck)
make logs        # Logs du backend en temps réel
make logs-all    # Logs de tous les conteneurs
make ps          # État de tous les conteneurs
make migrate     # Applique les migrations (si vous modifiez des modèles)
make seed        # (Re)charge les données de démonstration
make test        # Lance toute la suite de tests
make shell       # Shell Django interactif
make superuser   # Crée un compte superadmin
make diagnose    # Diagnostic complet si quelque chose ne démarre pas
make reset       # Réinitialise tout (down -v + up) — efface les données dev
make down        # Arrête les conteneurs (conserve les données)
make prod        # Démarre l'environnement de production

# Exemples équivalents sans Make (si make n'est pas disponible)
docker compose logs -f backend-dev
docker compose exec backend-dev python manage.py migrate
docker compose exec backend-dev python manage.py seed_demo_data
docker compose exec backend-dev python manage.py test tests/
docker compose down -v && docker compose up --build -d
```

## Mode local SANS Docker (démo / développement léger)

Pour lancer l'application sans PostgreSQL/Redis/Docker (SQLite fichier,
Celery synchrone) :

```bash
# Backend (Python 3.12+)
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements/dev.txt
export DJANGO_SETTINGS_MODULE=feba_project.settings.dev_sqlite
python manage.py bootstrap_demo          # migrations + migrations de données V8 + seeds + vérification
python manage.py runserver 8000

# Frontend (Node 20+), autre terminal
cd frontend
npm install
BACKEND_ORIGIN=http://localhost:8000 npm run dev
# → http://localhost:5173
```

> Ce mode est réservé à la démonstration : la production utilise PostgreSQL
> (`settings.prod`). Détail : `backend/feba_project/settings/dev_sqlite.py`.

## Tests

```bash
# Rapide, sans services externes (SQLite en mémoire)
cd backend
DJANGO_SETTINGS_MODULE=feba_project.settings.test_sqlite pytest --no-migrations
# → 219 passed, 1 skipped (test de concurrence : nécessite un serveur de BD)

# Complet, contre PostgreSQL (stack docker démarrée : make dev)
DJANGO_SETTINGS_MODULE=feba_project.settings.test_postgres pytest
# → 220 passed  (identifiants configurables via TEST_DB_* — voir test_postgres.py)

# Frontend
cd frontend && npm run build
```

## Déploiement PRODUCTION

Voir `guide_deploiement_production.pdf` pour la procédure complète (serveur, SSL, variables d'environnement, création du premier établissement client via l'API plateforme).

### Résumé rapide

```bash
git clone <votre-repo> /opt/feba && cd /opt/feba
cp backend/.env.prod.example backend/.env.prod
nano backend/.env.prod  # SECRET_KEY, ALLOWED_HOSTS, DATABASE_URL, etc.

docker-compose -f docker-compose.prod.yml up --build -d
docker-compose -f docker-compose.prod.yml exec backend-prod python manage.py migrate
docker-compose -f docker-compose.prod.yml exec backend-prod python manage.py collectstatic --no-input
docker-compose -f docker-compose.prod.yml exec backend-prod python manage.py createsuperuser
```

### Gestion multi-tenant (API plateforme, réservée au superadmin)

```bash
# Créer un nouvel établissement client
POST /api/platform/schools/  { "name": "...", "plan": "standard", ... }

# Suspendre un établissement (impayé)
POST /api/platform/schools/{slug}/suspend/

# Statistiques globales de la plateforme
GET /api/platform/stats/
```

### Sauvegardes automatiques

```bash
crontab -e
# 0 2 * * * /opt/feba/scripts/backup.sh >> /var/log/feba-backup.log 2>&1
```

## Architecture du projet

```
feba/
├── backend/                    # Django + DRF
│   ├── feba_project/           # Settings, URLs, ASGI, Celery
│   ├── apps/
│   │   ├── core/                # Isolation multi-tenant (tenancy.py) + API plateforme
│   │   ├── students/             # Élèves + StudentEnrollment (pivot années scolaires)
│   │   ├── accounts/, schools/, students/, parents/, teachers/
│   │   ├── classes/, subjects/, grades/, bulletins/, attendance/
│   │   ├── homework/, payments/, schedule/, announcements/
│   │   ├── messaging/, notifications/, dashboard/, user_files/
│   └── tests/                  # test_tenant_security.py, test_parent_student.py
├── frontend/                   # React 18 + Vite
│   └── src/
│       ├── api/                 # Axios + intercepteurs JWT + platformAPI
│       ├── components/          # Composants réutilisables
│       ├── layouts/              # Layouts par rôle
│       ├── pages/                # Pages par rôle (admin/teacher/parent/student)
│       ├── store/                # Zustand (état global, claims JWT tenant)
│       └── router/               # Routes protégées
├── nginx/                       # Configs Nginx dev + prod
├── scripts/                     # backup.sh, restore.sh, deploy.sh, verify_feba.py
├── docs/historique/              # Rapports de versions précédentes (V9 à V28)
├── RAPPORT_V29_AUDIT_REFONTE.md  # Audit et refonte multi-tenant (cette version)
├── guide_installation_local.pdf
├── guide_deploiement_production.pdf
├── docker-compose.yml
├── docker-compose.prod.yml
└── .env.dev / .env.prod
```

## FAQ

**Q: `docker compose up` démarre mais `backend-dev` disparaît de `docker compose ps` ?**
```bash
make diagnose   # Affiche les 150 dernières lignes de log backend + état détaillé
# ou directement :
docker compose logs --tail=150 backend-dev
```
L'entrypoint `entrypoint.dev.py` exécute `manage.py check` avant `migrate` : la cause réelle d'un crash apparaît clairement dans ces logs (import cassé, erreur de configuration, conflit de migration...).

**Q: `make dev` dit "Port already in use" ?**
```bash
make down   # Arrête les conteneurs existants
make dev    # Redémarre
```

**Q: Les données de démo ont disparu ?**
```bash
make seed   # Recharge les données de démo sans réinitialiser la base
```

**Q: Je veux repartir de zéro (base vide) ?**
```bash
make reset   # Arrête + supprime les volumes (efface TOUTES les données dev)
# Puis :
make seed    # Recrée les données de démo
```

**Q: Comment ajouter une nouvelle app Django ?**
```bash
docker compose exec backend-dev python manage.py startapp mon_app apps/mon_app
# Ajouter 'apps.mon_app' dans INSTALLED_APPS (backend/feba_project/settings/base.py)
# Créer models.py, serializers.py, views.py, urls.py
# Ajouter le path dans backend/feba_project/urls.py
# Si le modèle expose des données métier : filtrer par tenant
# (voir backend/apps/core/tenancy.py — get_request_school / IsSameTenant)
```

**Q: Comment vérifier qu'un nouveau module respecte l'isolation multi-tenant ?**
```bash
make test   # Lance tests/test_tenant_security.py (16 scénarios cross-tenant)
```
