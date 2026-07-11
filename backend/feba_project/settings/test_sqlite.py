"""
Réglages de test légers (SQLite en mémoire, cache local, pas de service
externe). Permet d'exécuter la suite de tests sans PostgreSQL, Redis,
WeasyPrint ni debug-toolbar — utile en CI et en local.

Usage :
    DJANGO_SETTINGS_MODULE=feba_project.settings.test_sqlite pytest
"""
from .base import *  # noqa: F401,F403

DEBUG = False
ALLOWED_HOSTS = ["*"]

# Importer un sous-module de settings déclenche feba_project/settings/__init__.py
# qui charge dev.py ; dev.py fait « INSTALLED_APPS += ['debug_toolbar'] » et
# mute la liste de base. On repart donc d'une liste propre (sans debug_toolbar
# ni son middleware, absents de l'environnement de test).
INSTALLED_APPS = [a for a in INSTALLED_APPS if a != "debug_toolbar"]  # noqa: F405
MIDDLEWARE = [m for m in MIDDLEWARE if "debug_toolbar" not in m]  # noqa: F405

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
    }
}

CHANNEL_LAYERS = {
    "default": {"BACKEND": "channels.layers.InMemoryChannelLayer"},
}

# Rate-limit désactivé et hachage rapide des mots de passe en test.
RATELIMIT_ENABLE = False
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

# Les e-mails ne partent pas pendant les tests.
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
