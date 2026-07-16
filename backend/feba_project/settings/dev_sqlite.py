"""
Développement local SANS Docker ni PostgreSQL/Redis.

Base SQLite fichier + cache mémoire + channels en mémoire : permet de lancer
l'application complète sur une machine sans services externes :

    cd backend
    DJANGO_SETTINGS_MODULE=feba_project.settings.dev_sqlite python manage.py migrate
    DJANGO_SETTINGS_MODULE=feba_project.settings.dev_sqlite python manage.py seed_demo_data
    DJANGO_SETTINGS_MODULE=feba_project.settings.dev_sqlite python manage.py runserver 8000

    cd frontend
    BACKEND_ORIGIN=http://localhost:8000 npm run dev

NB : réservé au développement/à la démonstration. La production utilise
PostgreSQL (settings.prod).
"""
from .base import *  # noqa: F401,F403

DEBUG = True
ALLOWED_HOSTS = ["localhost", "127.0.0.1"]

INSTALLED_APPS = [a for a in INSTALLED_APPS if a != "debug_toolbar"]  # noqa: F405
MIDDLEWARE = [m for m in MIDDLEWARE if "debug_toolbar" not in m]  # noqa: F405

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db_dev.sqlite3",  # noqa: F405
    }
}

CACHES = {
    "default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"},
}

CHANNEL_LAYERS = {
    "default": {"BACKEND": "channels.layers.InMemoryChannelLayer"},
}

CORS_ALLOWED_ORIGINS = ["http://localhost:5173", "http://127.0.0.1:5173"]
CORS_ALLOW_CREDENTIALS = True

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# Celery en mode synchrone (pas de worker ni de broker nécessaires)
CELERY_TASK_ALWAYS_EAGER = True

# Le rate-limit nécessite un cache partagé fiable ; inutile en local
RATELIMIT_ENABLE = False


# Certaines migrations historiques (v29 multi-tenant) contiennent du SQL brut
# PostgreSQL (« ADD COLUMN IF NOT EXISTS ») incompatible avec SQLite. En mode
# démo local, le schéma est créé directement depuis les modèles :
#     python manage.py migrate --run-syncdb
# (même stratégie que la suite de tests : pytest --no-migrations).
class _DisableMigrations(dict):
    def __contains__(self, item):
        return True

    def __getitem__(self, item):
        return None


MIGRATION_MODULES = _DisableMigrations()
