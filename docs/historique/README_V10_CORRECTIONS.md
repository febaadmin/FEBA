# FEBA School Management — Corrections V10

## 🚨 Erreurs corrigées

### 1. CRITIQUE — SyntaxError bloquant (`apps/accounts/urls.py`)

**Erreur :**
```
File "/app/apps/accounts/urls.py", line 15
]from . import views as v
^^^^
SyntaxError: invalid syntax
```

**Cause :** La fermeture du premier `urlpatterns` (`]`) et le second `from` import étaient sur la même ligne, sans saut de ligne.

**Correction :** Fusion des deux blocs `urlpatterns` en une liste unique et propre. `AvatarUploadView` est maintenant inclus directement dans `urlpatterns`.

---

### 2. Docker Dev — Migrations non exécutées (`docker-compose.dev.yml`)

**Problème :** Le service `backend-dev` lançait `runserver` directement, sans jamais exécuter `migrate`. Au premier démarrage, les tables n'existaient pas → erreur 500 sur toutes les requêtes API.

**Correction :**
```yaml
command: >
  sh -c "python manage.py migrate --no-input &&
         python manage.py runserver 0.0.0.0:8000"
```

**Bonus :** `celery-dev` dépend maintenant directement de `postgres-dev` et `redis-dev` (healthcheck) au lieu de dépendre de `backend-dev`.

---

### 3. Docker Prod — Backend sans migration + Frontend volume vide (`docker-compose.prod.yml`)

**Problème A :** `backend-prod` n'avait aucun `command:`, il utilisait le CMD du Dockerfile (gunicorn seul, sans migrate).

**Correction A :**
```yaml
command: >
  sh -c "python manage.py migrate --no-input &&
         python manage.py collectstatic --no-input &&
         gunicorn feba_project.wsgi:application --bind 0.0.0.0:8000 --workers 4 --timeout 120"
```

**Problème B :** Le volume `frontend_build` était monté dans `frontend-prod` à `/app/dist`, mais le Dockerfile multi-stage copie les fichiers dans `/usr/share/nginx/html` (stage nginx), pas dans `/app/dist`. Le volume restait **vide** → nginx-prod servait une **page blanche**.

**Correction B :** Suppression du volume `frontend_build`. `nginx-prod` proxie maintenant directement vers le conteneur `frontend-prod` qui tourne son propre nginx avec les fichiers buildés embarqués.

---

### 4. Package système incorrect (`backend/Dockerfile.prod`)

**Problème :** `libgdk-pixbuf2.0-0` est l'ancien nom Debian Bullseye. Sur Debian Bookworm (python:3.12-slim), le build échoue avec `E: Unable to locate package libgdk-pixbuf2.0-0`.

**Correction :** `libgdk-pixbuf2.0-0` → `libgdk-pixbuf-2.0-0`

Également, le `RUN python manage.py collectstatic` au build-time a été retiré (les variables d'env ne sont pas disponibles au moment du build Docker, et collectstatic est maintenant dans la commande de démarrage du conteneur).

---

### 5. Frontend prod — Nginx ne sert pas les fichiers (`nginx/nginx.prod.conf`)

**Problème :** `location /` servait depuis `/var/www/html` (volume vide, cf. point 3B).

**Correction :** Proxy vers `http://frontend-prod:80` qui tourne l'image nginx avec les fichiers buildés.

---

## ✅ Fichiers modifiés

| Fichier | Type de correction |
|---|---|
| `backend/apps/accounts/urls.py` | Syntaxe Python — CRITIQUE |
| `docker-compose.dev.yml` | Migrations + dépendances Celery |
| `docker-compose.prod.yml` | Migrations + collectstatic + frontend volume |
| `backend/Dockerfile.prod` | Package apt + collectstatic prématuré |
| `nginx/nginx.prod.conf` | Proxy frontend vers conteneur |
| `.env.prod.example` | Documentation améliorée |

---

## 🚀 Démarrage

### Développement
```bash
docker-compose -f docker-compose.dev.yml up --build
```
- Frontend : http://localhost:5173
- Backend API : http://localhost:8000/api/
- Health check : http://localhost:8000/api/health/

### Production
```bash
cp .env.prod.example .env.prod
# Éditez .env.prod avec vos vraies valeurs
docker-compose -f docker-compose.prod.yml up --build -d
```

### Données de démonstration
```bash
docker exec feba_backend_dev python manage.py seed_demo_data
```
