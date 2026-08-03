import os
from pathlib import Path
from celery.schedules import crontab
from decouple import config
from datetime import timedelta

BASE_DIR = Path(__file__).resolve().parent.parent.parent

SECRET_KEY = config('SECRET_KEY', default='django-insecure-dev-key-change-in-production')

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # Third party
    'rest_framework',
    'rest_framework_simplejwt',
    'rest_framework_simplejwt.token_blacklist',
    'corsheaders',
    'django_filters',
    'channels',
    # Apps
    'apps.core',
    'apps.accounts',
    'apps.schools',
    'apps.students',
    'apps.parents',
    'apps.teachers',
    'apps.classes',
    'apps.subjects',
    'apps.grades',
    'apps.bulletins',
    'apps.attendance',
    'apps.homework',
    'apps.schedule',
    'apps.payments',
    'apps.documents',
    'apps.messaging',
    'apps.announcements',
    'apps.notifications',
    'apps.user_files',
    'apps.dashboard',
    'apps.virtualclass',
    'apps.website',
    'apps.monthly_reports',
    'apps.incidents',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    # i18n : localise les messages du framework (DRF/Django) selon
    # l'en-tête Accept-Language envoyé par le frontend (fr/en).
    'django.middleware.locale.LocaleMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    # P0 : annonce dans chaque réponse l'académie qui a servi à la calculer
    # (en-tête X-Academy-Scope), pour que le frontend puisse rejeter les
    # réponses arrivées après un changement d'académie. Placé en dernier :
    # il doit s'exécuter APRÈS l'authentification JWT de DRF.
    'apps.core.academy_scope.AcademyScopeMiddleware',
]

ROOT_URLCONF = 'feba_project.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'feba_project.wsgi.application'
ASGI_APPLICATION = 'feba_project.asgi.application'

AUTH_USER_MODEL = 'accounts.CustomUser'

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator', 'OPTIONS': {'min_length': 8}},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'fr-fr'
# Langues servies par LocaleMiddleware (négociées via Accept-Language).
LANGUAGES = [
    ('fr', 'Français'),
    ('en', 'English'),
]
TIME_ZONE = 'Africa/Porto-Novo'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

MEDIA_URL = '/media/'
MEDIA_ROOT = config('MEDIA_ROOT', default=str(BASE_DIR / 'media'))

# Documents officiels (diplômes, certificats) — HORS du répertoire servi
# publiquement. Un diplôme déposé dans MEDIA_ROOT est accessible à qui
# devine son nom de fichier, et un nom de fichier n'est pas un secret.
# L'accès passe obligatoirement par /api/documents/<id>/download/, qui
# vérifie l'appartenance avant de diffuser l'octet.
PRIVATE_MEDIA_ROOT = config('PRIVATE_MEDIA_ROOT', default=str(BASE_DIR / 'private_media'))
DOCUMENT_TEMPLATES_ROOT = config(
    'DOCUMENT_TEMPLATES_ROOT', default=str(BASE_DIR / 'document_templates'))

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# REST Framework
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ],
    'DEFAULT_PAGINATION_CLASS': 'feba_project.pagination.FlexiblePagination',
    'PAGE_SIZE': 20,
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
    ],
    # V8 : les erreurs 500 inattendues créent un incident technique réel,
    # notifient les super administrateurs et renvoient une référence ERR-XXXXXX.
    'EXCEPTION_HANDLER': 'apps.incidents.handlers.feba_exception_handler',
}

# JWT Settings
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=config('JWT_ACCESS_TOKEN_LIFETIME_MINUTES', default=60, cast=int)),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=config('JWT_REFRESH_TOKEN_LIFETIME_DAYS', default=7, cast=int)),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'UPDATE_LAST_LOGIN': True,
    'ALGORITHM': 'HS256',
    'AUTH_HEADER_TYPES': ('Bearer',),
    'AUTH_TOKEN_CLASSES': ('rest_framework_simplejwt.tokens.AccessToken',),
}

# Redis
REDIS_URL = config('REDIS_URL', default='redis://localhost:6379/0')

# ── Visioconférence : instance Jitsi AUTO-HÉBERGÉE UNIQUEMENT ──────────
#
# AUCUN REPLI VERS UNE INSTANCE PUBLIQUE.
# L'ancienne valeur par défaut `meet.jit.si` a été supprimée : elle faisait
# basculer silencieusement des cours de mineurs vers un serveur tiers, sans
# authentification, avec une limite de 5 minutes. Un défaut de configuration
# doit produire une ERREUR D'INFRASTRUCTURE explicite, jamais une session
# publique.
#
# Les trois valeurs sont générées automatiquement par `make install`
# (voir scripts/bootstrap.sh) et écrites dans .env.jitsi + .env, hors Git.
JITSI_DOMAIN = config('JITSI_DOMAIN', default='')
JITSI_APP_ID = config('JITSI_APP_ID', default='')
JITSI_APP_SECRET = config('JITSI_APP_SECRET', default='')

# Domaines publics explicitement interdits : ils ne doivent jamais être
# atteints, même par une variable d'environnement mal renseignée.
JITSI_FORBIDDEN_DOMAINS = ('meet.jit.si', 'jitsi.org', '8x8.vc')


def jitsi_is_configured():
    """
    True si l'instance auto-hébergée est complètement configurée.

    Les trois valeurs sont requises : sans secret, aucun jeton ne peut être
    signé, et une salle ouverte sans jeton serait une salle non protégée.
    """
    host = (JITSI_DOMAIN or '').split(':')[0].strip().lower()
    if not host or host in JITSI_FORBIDDEN_DOMAINS:
        return False
    return bool(JITSI_APP_ID and JITSI_APP_SECRET)

# Channels
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            'hosts': [REDIS_URL],
        },
    },
}

# Celery
CELERY_BROKER_URL = REDIS_URL
CELERY_RESULT_BACKEND = REDIS_URL
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'Africa/Porto-Novo'

# ── P3 — Rapports mensuels FEBA FHA ───────────────────────────────────
#
# Le planificateur déclenche le lot du mois ÉCOULÉ. Le jour et l'heure
# sont configurables : une école qui clôture ses saisies le 3 ne veut pas
# d'un rapport produit le 1er, qui rendrait compte d'un mois incomplet
# tout en ayant l'air définitif.
MONTHLY_REPORTS_DAY = config('MONTHLY_REPORTS_DAY', default=1, cast=int)
MONTHLY_REPORTS_HOUR = config('MONTHLY_REPORTS_HOUR', default=6, cast=int)
MONTHLY_REPORTS_MINUTE = config('MONTHLY_REPORTS_MINUTE', default=0, cast=int)

# Deux modes, au choix de l'établissement :
#   False (défaut) — les rapports sont produits, puis un administrateur
#                    relit et déclenche l'envoi. C'est le défaut PARCE
#                    QUE l'envoi automatique d'un document nominatif à
#                    des familles ne doit pas s'activer par surprise ;
#   True           — envoi immédiat après génération.
MONTHLY_REPORTS_AUTO_SEND = config('MONTHLY_REPORTS_AUTO_SEND',
                                   default=False, cast=bool)

CELERY_BEAT_SCHEDULE = {
    'rapports-mensuels-feba-fha': {
        'task': 'monthly_reports.generate_month',
        'schedule': crontab(
            day_of_month=str(MONTHLY_REPORTS_DAY),
            hour=str(MONTHLY_REPORTS_HOUR),
            minute=str(MONTHLY_REPORTS_MINUTE),
        ),
        'kwargs': {'academy_code': 'FEBA_FHA'},
        'options': {
            # Si le worker n'a pas pris la tâche dans l'heure, elle est
            # abandonnée plutôt que rejouée tardivement : un rapport
            # « de mars » produit le 20 avril induit en erreur.
            'expires': 3600,
        },
    },
}

# Email
EMAIL_BACKEND = config('EMAIL_BACKEND', default='django.core.mail.backends.console.EmailBackend')
EMAIL_HOST = config('EMAIL_HOST', default='')
EMAIL_PORT = config('EMAIL_PORT', default=587, cast=int)
EMAIL_HOST_USER = config('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='')
EMAIL_USE_TLS = config('EMAIL_USE_TLS', default=True, cast=bool)
EMAIL_USE_SSL = config('EMAIL_USE_SSL', default=False, cast=bool)
# Un serveur SMTP injoignable bloquait la requête jusqu'au timeout par
# défaut du système. Une famille qui envoie une fiche d'inscription
# attendait alors la page de confirmation pendant des minutes.
EMAIL_TIMEOUT = config('EMAIL_TIMEOUT', default=10, cast=int)
DEFAULT_FROM_EMAIL = config('DEFAULT_FROM_EMAIL', default='noreply@feba.bj')

# Expéditeur PROPRE À CHAQUE ACADÉMIE. Un parent de l'académie en ligne ne
# doit pas recevoir un message venant de l'adresse de l'école de Cotonou :
# il répondrait au mauvais secrétariat. Vide = DEFAULT_FROM_EMAIL.
FEBA_FROM_EMAIL = config('FEBA_FROM_EMAIL', default='')
FHA_FROM_EMAIL = config('FHA_FROM_EMAIL', default='')
EMAIL_REPLY_TO = config('EMAIL_REPLY_TO', default='')

# File upload
FILE_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024  # 10MB
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024

import logging
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'apps': {
            'handlers': ['console'],
            'level': 'DEBUG',
            'propagate': False,
        },
    },
}


# ── Portée d'académie (P0) ───────────────────────────────────────────────
# `X-Academy-Scope` circule dans les DEUX sens :
#   - en requête, le navigateur annonce la portée qu'il croit active
#     (valeur purement indicative, sans aucune autorité côté serveur) ;
#   - en réponse, le serveur annonce la portée réellement utilisée.
# Sans ces deux réglages, le navigateur refuserait d'envoyer l'en-tête
# (pré-vol CORS) et JavaScript ne pourrait pas lire celui de la réponse —
# le frontend serait alors incapable de détecter une réponse périmée.
from corsheaders.defaults import default_headers  # noqa: E402

CORS_ALLOW_HEADERS = list(default_headers) + ["x-academy-scope"]
CORS_EXPOSE_HEADERS = ["X-Academy-Scope"]


# ── Paiement par carte (P1) ──────────────────────────────────────────────
#
# Aucune clé n'est écrite ici ni dans Git : elles viennent de
# l'environnement, renseigné par `make payments-setup`.
#
# `CARD_PAYMENTS_ENABLED` est un interrupteur explicite. Sans lui, une
# instance mal configurée afficherait un bouton « Payer par carte » qui
# échoue au clic — pire qu'un bouton absent.
CARD_PAYMENTS_ENABLED = config('CARD_PAYMENTS_ENABLED', default=False, cast=bool)
PAYMENT_PROVIDER = config('PAYMENT_PROVIDER', default='stripe')
STRIPE_MODE = config('STRIPE_MODE', default='test')
STRIPE_PUBLISHABLE_KEY = config('STRIPE_PUBLISHABLE_KEY', default='')
STRIPE_SECRET_KEY = config('STRIPE_SECRET_KEY', default='')
STRIPE_WEBHOOK_SECRET = config('STRIPE_WEBHOOK_SECRET', default='')

# Adresse publique de l'instance : sert à construire les URL de retour et
# celle du webhook. En production, elle DOIT être en HTTPS — Stripe refuse
# d'envoyer des événements en clair, et une redirection non chiffrée
# exposerait l'identifiant de session.
PUBLIC_BASE_URL = config('PUBLIC_BASE_URL', default='http://localhost:5173')
STRIPE_SUCCESS_URL = config(
    'STRIPE_SUCCESS_URL', default=f'{PUBLIC_BASE_URL}/parent/payments?paiement=succes',
)
STRIPE_CANCEL_URL = config(
    'STRIPE_CANCEL_URL', default=f'{PUBLIC_BASE_URL}/parent/payments?paiement=annule',
)
STRIPE_WEBHOOK_URL = config(
    'STRIPE_WEBHOOK_URL', default=f'{PUBLIC_BASE_URL}/api/payments/webhook/stripe/',
)
