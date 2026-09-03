# Guide d'installation — FEBA

Installation depuis zéro, sur une machine neuve, jusqu'à une application
utilisable.

---

## 1. Prérequis

| Outil | Version | Vérifier |
|---|---|---|
| Docker + Compose v2 | récente | `docker compose version` |
| Git | ≥ 2.30 | `git --version` |
| `openssl` | — | `openssl version` |
| `make` | — | `make --version` |

Installation **sans Docker** (développement) : Python 3.11, PostgreSQL 16,
Redis 7, Node.js 20+.

---

## 2. Installation avec Docker — chemin recommandé

```bash
unzip feba_corrected_production_ready.zip
cd feba_v6_version_finale_corrigee

cp .env.dev.example .env.dev          # aucun secret à inventer
make install                          # doctor + bootstrap + contrôles
```

`make install` enchaîne : contrôle de l'environnement, génération des
secrets, démarrage des conteneurs, migrations, création des académies,
données de démonstration, puis vérifications post-installation.

| Service | Adresse |
|---|---|
| Application | http://localhost:5173 |
| API | http://localhost:8000/api/ |
| Back-office Django | http://localhost:8000/django-admin/ |
| Mailpit (courriers de test) | http://localhost:8025 |

### Visioconférence (facultatif en développement)

```bash
make jitsi-up          # génère les secrets et démarre la pile locale
make jitsi-health      # doit finir par « OPÉRATIONNEL »
```

Sans cette étape, les salles virtuelles affichent un bandeau de diagnostic
et refusent d'ouvrir une session. **C'est voulu** : il n'existe aucun repli
vers une instance publique, y compris en développement. Voir
[`JITSI_PRODUCTION_GUIDE.md`](JITSI_PRODUCTION_GUIDE.md).

---

## 3. Installation sans Docker

```bash
# ── Base de données ────────────────────────────────────────────────
sudo -u postgres psql -c "CREATE USER feba_user WITH PASSWORD 'feba_dev_pass' CREATEDB;"
sudo -u postgres psql -c "CREATE DATABASE feba_dev OWNER feba_user;"
redis-server --daemonize yes

# ── Backend ────────────────────────────────────────────────────────
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements/dev.txt

cat > .env <<'EOF'
DJANGO_ENV=dev
SECRET_KEY=dev-secret-key-not-for-production-use-change-me
DATABASE_URL=postgresql://feba_user:feba_dev_pass@localhost:5432/feba_dev
REDIS_URL=redis://localhost:6379/0
CORS_ALLOWED_ORIGINS=http://localhost:5173
ALLOWED_HOSTS=localhost,127.0.0.1
EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
JITSI_DOMAIN=
JITSI_APP_ID=
JITSI_APP_SECRET=
EOF

python manage.py migrate
python manage.py init_academies
python manage.py seed_demo_data          # facultatif
python manage.py runserver 127.0.0.1:8000

# ── Frontend (autre terminal) ──────────────────────────────────────
cd frontend
npm ci
BACKEND_ORIGIN=http://localhost:8000 npm run dev
```

---

## 4. Comptes de démonstration

Créés par `seed_demo_data`. **À supprimer avant toute mise en production.**

| Académie | Rôle | Identifiant | Mot de passe |
|---|---|---|---|
| FEBA | Administration | `admin@feba.bj` | `Admin@2024` |
| FEBA | Enseignant | `prof1@feba.bj` | `Teacher@2024` |
| FEBA | Parent | `parent1@feba.bj` | `Parent@2024` |
| FEBA | Élève | `eleve1@feba.bj` | `Student@2024` |
| FEBA FHA | Administration | `admin@febafha.org` | `Admin@2024` |
| FEBA FHA | Enseignant | `prof@febafha.org` | `Teacher@2024` |
| FEBA FHA | Parent | `parent@febafha.org` | `Parent@2024` |
| FEBA FHA | Élève | `eleve1@febafha.org` | `Student@2024` |

La connexion se fait par **adresse e-mail** (`USERNAME_FIELD = "email"`).

---

## 5. Vérifier que l'installation est saine

```bash
make install-check          # contrôles post-installation
make branding-check         # identité visuelle des deux académies
make jitsi-config-check     # cohérence Jitsi, sans réseau
make jitsi-health           # état réel de l'instance
make seed-check             # cohérence des données de démonstration
```

### Tests

```bash
make test-sqlite            # suite backend, sans service externe
make test-postgres          # suite backend sur PostgreSQL — la référence
make test-frontend          # Vitest
cd frontend && npm run lint && npm run build
```

**Toujours valider sur PostgreSQL avant une livraison.** SQLite n'applique
pas les longueurs de colonnes ni certaines contraintes : un défaut réel y
passe inaperçu.

#### Les tests qui lisent des fichiers hors de `backend/`

Une partie de la suite vérifie des **fichiers de livraison** —
`.env.*.example`, `Makefile`, `docker-compose*.yml`, `scripts/`. Ils
vivent à la racine, un niveau au-dessus de `backend/`.

Dans le conteneur, `./backend` est monté sur `/app` : la racine n'y
existerait pas. `docker-compose.yml` la monte donc **en lecture seule**
sur `/repo`, et `backend/tests/repo_root.py` la retrouve par trois
chemins indépendants (variable `FEBA_REPO_ROOT`, remontée
d'arborescence, montage `/repo`).

Conséquence pratique : **si vous modifiez `docker-compose.yml`,
recréez le conteneur**, sinon l'ancien montage persiste.

```bash
docker compose up -d --force-recreate backend-dev
```

Ces tests **ne s'ignorent jamais**. Un « skipped » sur un fichier de
configuration se lit comme un succès alors que rien n'a été vérifié :
c'est ainsi qu'un `.env.dev.example` revenu au backend console était
passé inaperçu. Si la racine est introuvable, ils échouent avec un
message qui dit quoi faire.

### Environnements couverts

| | Où | Ce qui résout la racine du dépôt |
|---|---|---|
| **A. Développement local** | Docker Compose | montage `.:/repo:ro` + `FEBA_REPO_ROOT` |
| **B. Tests** | checkout Git, hors conteneur | remontée d'arborescence |
| **C. CI GitHub** | `.github/workflows/ci.yml` | remontée d'arborescence (checkout complet) |
| **D. Production FEBA** | `docker-compose.prod.yml` | sans objet — aucun test n'y tourne |
| **E. Jitsi production** | `JITSI_PRODUCTION_GUIDE.md` | sans objet |

### Intégration continue (C)

`.github/workflows/ci.yml` valide chaque Pull Request : suites backend
sur PostgreSQL **et** SQLite, tests et build frontend, validité des
fichiers Compose, cohérence Jitsi, syntaxe Nginx, sûreté du dépôt.

Elle **ne requiert aucun secret de production** : une Pull Request venue
d'un fork est validée comme les autres. Le déploiement reste
exclusivement l'affaire de `deploy.yml`, inchangé.

---

## 6. Problèmes fréquents

| Symptôme | Cause | Geste |
|---|---|---|
| `port is already allocated` | 5173, 8000, 5432 ou 6379 occupés | `make down`, ou libérer le port |
| `password authentication failed` | `DATABASE_URL` ne correspond pas au conteneur | vérifier `.env.dev` |
| Écran de connexion sans réponse | origine absente de `CORS_ALLOWED_ORIGINS` | ajouter l'adresse du frontend |
| Bandeau « Visioconférence indisponible » | instance Jitsi non démarrée | `make jitsi-up` puis `make jitsi-health` |
| `CSRF verification failed` sur `/django-admin/` | `CSRF_TRUSTED_ORIGINS` absent en production | voir `.env.prod.example` |
| Documents sans logo | ressources absentes de `static_files/` | `make documents-check` |

---

## 7. Passage en production

Ne pas déployer `.env.dev` ni les comptes de démonstration. Voir
[`DEPLOYMENT_PRODUCTION.md`](DEPLOYMENT_PRODUCTION.md) et
[`MANUAL_PRODUCTION_ACTIONS.md`](MANUAL_PRODUCTION_ACTIONS.md).
