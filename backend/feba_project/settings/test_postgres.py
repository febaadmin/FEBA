"""
Réglages de test contre un vrai PostgreSQL local (pas de Redis/Celery
nécessaires pour la suite de tests API). Utilisé pour cette itération de
validation car certaines migrations (multi-tenant v29) utilisent une syntaxe
SQL PostgreSQL (ADD COLUMN IF NOT EXISTS) incompatible avec SQLite.

Usage :
    DJANGO_SETTINGS_MODULE=feba_project.settings.test_postgres pytest
"""
from .base import *  # noqa: F401,F403

DEBUG = False
ALLOWED_HOSTS = ["*"]

INSTALLED_APPS = [a for a in INSTALLED_APPS if a != "debug_toolbar"]  # noqa: F405
MIDDLEWARE = [m for m in MIDDLEWARE if "debug_toolbar" not in m]  # noqa: F405

# Identifiants configurables ; par défaut ceux de la stack docker de dev
# (docker-compose.yml, service postgres-dev).
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": config("TEST_DB_NAME", default="feba_test"),
        "USER": config("TEST_DB_USER", default="feba_user"),
        "PASSWORD": config("TEST_DB_PASSWORD", default="feba_dev_pass"),
        "HOST": config("TEST_DB_HOST", default="localhost"),
        "PORT": config("TEST_DB_PORT", default="5432"),
    }
}

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
    }
}

# Voir dev.py : le rate-limit login persistant entre tests fait échouer en
# cascade la suite entière (« Authorization header must contain two
# space-delimited values » = token vide car login bloqué par le rate-limit
# d'un test précédent).
RATELIMIT_ENABLE = False

CHANNEL_LAYERS = {
    "default": {"BACKEND": "channels.layers.InMemoryChannelLayer"},
}

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

# Ces réglages servent aussi à la VÉRIFICATION MANUELLE en navigateur
# (backend lancé avec ce module + frontend Vite). Sans origine autorisée,
# chaque appel API était bloqué par la politique CORS et l'écran de
# connexion échouait silencieusement — alors que l'API elle-même
# répondait correctement en ligne de commande.
CORS_ALLOWED_ORIGINS = config(
    "CORS_ALLOWED_ORIGINS",
    default="http://localhost:5173,http://127.0.0.1:5173,http://localhost:5174",
).split(",")
CORS_ALLOW_CREDENTIALS = True
