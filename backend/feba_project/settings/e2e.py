"""
Réglages des tests navigateur (e2e/ci) : PostgreSQL jetable de la CI, serveur Django réel.
Jamais en production : base, secret et comptes sont ceux de la CI.
"""
from .test_postgres import *  # noqa: F401,F403
from decouple import config

ALLOWED_HOSTS = config("ALLOWED_HOSTS", default="localhost,127.0.0.1").split(",")
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = False
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
