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
# Django 5.1 a supprimé STATICFILES_STORAGE : déclaration par STORAGES.
STORAGES = {
    'default': {'BACKEND': 'apps.core.fichiers_prives.StockageMedia'},
    'staticfiles': {'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage'},
}

MEDIA_URL = '/media/'
# Durée d'un lien vers un fichier privé (apps.core.fichiers_prives).
PRIVATE_FILE_LINK_SECONDS = config('PRIVATE_FILE_LINK_SECONDS', default=6 * 3600, cast=int)
MEDIA_ROOT = config('MEDIA_ROOT', default=str(BASE_DIR / 'media'))

# Documents officiels (diplômes, certificats) — HORS du répertoire servi
# publiquement. Un diplôme déposé dans MEDIA_ROOT est accessible à qui
# devine son nom de fichier, et un nom de fichier n'est pas un secret.
# L'accès passe obligatoirement par /api/documents/<id>/download/, qui
# vérifie l'appartenance avant de diffuser l'octet.
PRIVATE_MEDIA_ROOT = config('PRIVATE_MEDIA_ROOT', default=str(BASE_DIR / 'private_media'))
# Conversion des gabarits bureautiques (DOCX, ODT, RTF, PPTX…) par LibreOffice
# sans interface — installé dans l'image Docker (backend/Dockerfile.prod).
# Académie alimentée par les formulaires publics « en ligne » du site
# (inscription, test de placement) — voir School.features.
PUBLIC_SITE_ONLINE_ACADEMY_CODE = config('PUBLIC_SITE_ONLINE_ACADEMY_CODE', default='FEBA_FHA')
# Académie présentielle alimentée par les formulaires publics du site
# (contact, préinscriptions).
PUBLIC_SITE_CAMPUS_ACADEMY_CODE = config('PUBLIC_SITE_CAMPUS_ACADEMY_CODE', default='FEBA')
DOCUMENT_CONVERSION_TIMEOUT = config('DOCUMENT_CONVERSION_TIMEOUT', default=90, cast=int)
LIBREOFFICE_BINARY = config('LIBREOFFICE_BINARY', default='')
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
    # Un jeton d'accès cesse de valoir dès que le mot de passe change.
    'CHECK_REVOKE_TOKEN': True,
    'REVOKE_TOKEN_CLAIM': 'hash_password',
    'ALGORITHM': 'HS256',
    'AUTH_HEADER_TYPES': ('Bearer',),
    'AUTH_TOKEN_CLASSES': ('rest_framework_simplejwt.tokens.AccessToken',),
}

# ── Identité institutionnelle du groupe FEBA ──────────────────────────
#
# Numéro imprimé sur TOUS les documents officiels (reçus, bulletins,
# certificats, diplômes, fiches). Voir apps/schools/institution.py : ce
# n'est pas une valeur d'affichage mais la coordonnée par laquelle une
# famille rappelle le groupe. Elle ne dépend ni de l'entité émettrice, ni
# du profil qui déclenche la génération.
#
# Vide = valeur de référence du module (0160011717). La variable existe
# pour permettre une ROTATION de ligne téléphonique sans modification de
# code ; un numéro retiré du service y est refusé à l'exécution.
FEBA_OFFICIAL_PHONE = config('FEBA_OFFICIAL_PHONE', default='')

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
# (voir scripts/bootstrap.sh) et écrites dans .env.jitsi + .env.dev, hors Git.
JITSI_DOMAIN = config('JITSI_DOMAIN', default='')
JITSI_APP_ID = config('JITSI_APP_ID', default='')
JITSI_APP_SECRET = config('JITSI_APP_SECRET', default='')

# P7 — URL INTERNE, pour les appels du BACKEND vers Jitsi (healthcheck).
#
# PROBLÈME RÉSOLU : le backend testait la joignabilité de Jitsi via
# JITSI_DOMAIN (ex. « localhost:8443 ») — la bonne adresse pour un
# NAVIGATEUR, mais depuis l'INTÉRIEUR du conteneur backend, « localhost »
# désigne ce conteneur lui-même, jamais Jitsi. Résultat : « make
# jitsi-health » échouait toujours, même Jitsi parfaitement opérationnel.
#
# JITSI_INTERNAL_URL cible le service Docker directement (voir
# docker-compose.yml / docker-compose.jitsi.yml, réseau
# « feba_jitsi_shared ») : http://jitsi-web:80 en développement. Si non
# défini, on retombe sur JITSI_DOMAIN — utile en production, où le
# backend et Jitsi peuvent légitimement partager la même URL publique
# (deux domaines distincts sur le même serveur, pas deux conteneurs).
JITSI_INTERNAL_URL = config('JITSI_INTERNAL_URL', default='')

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


# ── Visioconférence : plugNmeet auto-hébergé (remplace Jitsi) ─────────
#
# VIDEO_PROVIDER choisit le moteur : « plugnmeet » (par défaut) ou
# « jitsi ». Jitsi ne reste sélectionnable que pour le RETOUR ARRIÈRE,
# tant que plugNmeet n'a pas été validé en production (voir
# PLUGNMEET_DEPLOYMENT_GUIDE.md § Retour arrière). Aucun repli
# automatique : un moteur mal configuré produit une erreur explicite.
VIDEO_PROVIDER = config('VIDEO_PROVIDER', default='plugnmeet').strip().lower()

# Adresse publique du serveur plugNmeet (navigateur ET backend), par ex.
# https://meet.globalfeba.com. Clé et secret de l'API : côté serveur
# UNIQUEMENT — ils ne sont jamais transmis au frontend.
PLUGNMEET_SERVER_URL = config('PLUGNMEET_SERVER_URL', default='').rstrip('/')
# Domaine public des classes virtuelles, contrôlé avant chaque déploiement.
VIDEO_PUBLIC_HOST = config('VIDEO_PUBLIC_HOST', default='meet.globalfeba.com')
# Retour arrière DÉLIBÉRÉ vers Jitsi (sinon refusé en production).
VIDEO_ROLLBACK_JITSI = config('VIDEO_ROLLBACK_JITSI', default=False, cast=bool)
# Adresse utilisée par le BACKEND s'il ne joint pas l'URL publique
# (réseau Docker interne). Vide = PLUGNMEET_SERVER_URL.
PLUGNMEET_INTERNAL_URL = config('PLUGNMEET_INTERNAL_URL', default='').rstrip('/')
PLUGNMEET_API_KEY = config('PLUGNMEET_API_KEY', default='')
PLUGNMEET_API_SECRET = config('PLUGNMEET_API_SECRET', default='')
PLUGNMEET_TIMEOUT = config('PLUGNMEET_TIMEOUT', default=10, cast=int)
# URL publique de FEBA à laquelle plugNmeet envoie ses webhooks
# (présences, début et fin de réunion). Vide = pas de webhook : les
# présences reposent alors sur les appels « rejoindre / quitter ».
PLUGNMEET_WEBHOOK_URL = config('PLUGNMEET_WEBHOOK_URL', default='')
# Fonctions dépendant d'un service SUPPLÉMENTAIRE : désactivées tant que
# ce service n'est pas déployé et vérifié. Les activer sans lui afficherait
# un bouton qui ne fait rien.
PLUGNMEET_RECORDING_ENABLED = config('PLUGNMEET_RECORDING_ENABLED', default=False, cast=bool)
PLUGNMEET_RTMP_ENABLED = config('PLUGNMEET_RTMP_ENABLED', default=False, cast=bool)
PLUGNMEET_INSIGHTS_ENABLED = config('PLUGNMEET_INSIGHTS_ENABLED', default=False, cast=bool)
# Bloc-notes partagé : seulement avec un serveur Etherpad déclaré à plugNmeet.
PLUGNMEET_SHARED_NOTEPAD_ENABLED = config('PLUGNMEET_SHARED_NOTEPAD_ENABLED', default=False, cast=bool)
# Fenêtre d'accès des élèves et parents à un cours planifié : de N minutes
# avant le début à N minutes après la fin prévue (modérateurs : sans limite ;
# cours ouvert par un modérateur : accessible). Voir services.assert_within_schedule.
VIRTUAL_ROOM_EARLY_JOIN_MINUTES = config('VIRTUAL_ROOM_EARLY_JOIN_MINUTES', default=15, cast=int)
VIRTUAL_ROOM_LATE_JOIN_MINUTES = config('VIRTUAL_ROOM_LATE_JOIN_MINUTES', default=15, cast=int)
# Durée maximale d'une réunion en minutes (0 = illimitée).
PLUGNMEET_MAX_ROOM_MINUTES = config('PLUGNMEET_MAX_ROOM_MINUTES', default=0, cast=int)


def plugnmeet_is_configured():
    """True si l'URL, la clé et le secret de l'API plugNmeet sont fournis."""
    return bool(PLUGNMEET_SERVER_URL and PLUGNMEET_API_KEY and PLUGNMEET_API_SECRET)

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

# ── Envois d'e-mails groupés (P1 — octobre 2026) ──────────────────────
# Garde-fous contre l'envoi massif involontaire. Valeurs prudentes par
# défaut ; un établissement plus grand les relève explicitement.
MASS_EMAIL_MAX_RECIPIENTS = config('MASS_EMAIL_MAX_RECIPIENTS', default=2000, cast=int)
MASS_EMAIL_MAX_CAMPAIGNS_PER_HOUR = config('MASS_EMAIL_MAX_CAMPAIGNS_PER_HOUR', default=10, cast=int)
MASS_EMAIL_BATCH_SIZE = config('MASS_EMAIL_BATCH_SIZE', default=50, cast=int)

# ── Relances de paiement (P1 — octobre 2026) ──────────────────────────
# Interrupteur GLOBAL : faux par défaut, et donc en développement et en
# test. Aucune relance réelle ne part tant qu'il n'est pas explicitement
# mis à True dans l'environnement de production ET que la politique de
# l'académie n'est pas activée depuis l'écran « Relances de paiement ».
PAYMENT_REMINDERS_ENABLED = config('PAYMENT_REMINDERS_ENABLED', default=False, cast=bool)
PAYMENT_REMINDERS_HOUR = config('PAYMENT_REMINDERS_HOUR', default=8, cast=int)
PAYMENT_REMINDERS_MINUTE = config('PAYMENT_REMINDERS_MINUTE', default=30, cast=int)

CELERY_BEAT_SCHEDULE = {
    'surveillance-plateforme': {
        'task': 'incidents.surveillance_plateforme',
        'schedule': crontab(minute='*/15'),
        'options': {'expires': 600},
    },
    'relances-paiements-quotidiennes': {
        'task': 'payments.run_payment_reminders',
        'schedule': crontab(hour=str(PAYMENT_REMINDERS_HOUR), minute=str(PAYMENT_REMINDERS_MINUTE)),
        # Pas de rattrapage tardif : une relance « du matin » exécutée le
        # soir après une panne attendra le lendemain.
        'options': {'expires': 6 * 3600},
    },
    # Reprise des envois groupés interrompus (broker indisponible au moment
    # de la création, worker redémarré pendant l'envoi).
    'envois-groupes-reprise': {
        'task': 'notifications.process_pending_campaigns',
        'schedule': crontab(minute='*/5'),
        'options': {'expires': 240},
    },
    # Nouvelles tentatives des envois en « nouvel essai programmé ». Sans
    # cette entrée, `next_retry_at` était calculé et jamais relu.
    'envois-email-nouvelles-tentatives': {
        'task': 'notifications.retry_due_deliveries',
        'schedule': crontab(minute='*/10'),
        'options': {'expires': 540},
    },
    # Filet de sécurité de la visioconférence : une salle « en cours » dont
    # la réunion n'existe plus côté plugNmeet (webhook perdu) est close.
    # SMS : nouvelles tentatives et reprise après arrêt d'un worker.
    'sms-nouvelles-tentatives': {
        'task': 'notifications.retry_due_sms',
        'schedule': crontab(minute='*/5'),
        'options': {'expires': 240},
    },
    'visio-reconciliation-salles': {
        'task': 'virtualclass.reconcile_live_rooms',
        'schedule': crontab(minute='*/10'),
        'options': {'expires': 540},
    },
    'rapports-mensuels-feba-fha': {
        'task': 'monthly_reports.generate_month',
        'schedule': crontab(
            day_of_month=str(MONTHLY_REPORTS_DAY),
            hour=str(MONTHLY_REPORTS_HOUR),
            minute=str(MONTHLY_REPORTS_MINUTE),
        ),
        'kwargs': {'academy_code': PUBLIC_SITE_ONLINE_ACADEMY_CODE},
        'options': {
            # Si le worker n'a pas pris la tâche dans l'heure, elle est
            # abandonnée plutôt que rejouée tardivement : un rapport
            # « de mars » produit le 20 avril induit en erreur.
            'expires': 3600,
        },
    },
}

# Email
# Le TRANSPORT (SMTP, console…) se choisit toujours par la variable
# d'environnement EMAIL_BACKEND. Django, lui, passe par le backend de
# traçage, qui journalise tout envoi échappant à apps/notifications/mailer.py
# avant de le confier à ce transport.
EMAIL_TRANSPORT_BACKEND = config('EMAIL_BACKEND', default='django.core.mail.backends.console.EmailBackend')
EMAIL_BACKEND = 'apps.notifications.backends.TrackingEmailBackend'
# auto : un hôte de capture connu (mailpit, mailhog…) est signalé « capturé,
# non distribué » ; capture / real forcent la qualification.
EMAIL_DELIVERY_MODE = config('EMAIL_DELIVERY_MODE', default='auto')
EMAIL_CAPTURE_HOSTS = config('EMAIL_CAPTURE_HOSTS', default='')
# Interface web du serveur de capture (indiquée à l'utilisateur).
MAILPIT_UI_URL = config('MAILPIT_UI_URL', default='http://localhost:8025')
# Pièces jointes (validation serveur, voir apps/notifications/attachments.py).
EMAIL_ATTACHMENT_ALLOWED_EXTENSIONS = config('EMAIL_ATTACHMENT_ALLOWED_EXTENSIONS', default='')
EMAIL_ATTACHMENT_MAX_FILE_MB = config('EMAIL_ATTACHMENT_MAX_FILE_MB', default=10, cast=int)
EMAIL_ATTACHMENT_MAX_TOTAL_MB = config('EMAIL_ATTACHMENT_MAX_TOTAL_MB', default=20, cast=int)
EMAIL_ATTACHMENT_MAX_FILES = config('EMAIL_ATTACHMENT_MAX_FILES', default=10, cast=int)
# Test SMTP depuis l'écran d'administration : nombre maximal par heure et
# par utilisateur (protection contre l'usage abusif).
EMAIL_TEST_MAX_PER_HOUR = config('EMAIL_TEST_MAX_PER_HOUR', default=5, cast=int)
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
# Adresse d'expédition officielle : noreply@globalfeba.com (domaine dont le
# SPF autorise le serveur SMTP Hostinger, DKIM « hostingermail-a »). L'ancienne
# adresse noreply@feba.bj est retirée : si un environnement la contient
# encore, apps.notifications.mailer la remplace et `manage.py check` le signale.
DEFAULT_FROM_EMAIL = config('DEFAULT_FROM_EMAIL', default='noreply@globalfeba.com')
# Expéditeur des alertes d'erreur de Django (mail_admins). Sans lui, Django
# écrit depuis « root@localhost », refusé par tout serveur SMTP sérieux.
SERVER_EMAIL = config('SERVER_EMAIL', default=DEFAULT_FROM_EMAIL)

# Expéditeur PROPRE À CHAQUE ACADÉMIE. Un parent de l'académie en ligne ne
# doit pas recevoir un message venant de l'adresse de l'école de Cotonou :
# il répondrait au mauvais secrétariat. Vide = DEFAULT_FROM_EMAIL.
FEBA_FROM_EMAIL = config('FEBA_FROM_EMAIL', default='')
FHA_FROM_EMAIL = config('FHA_FROM_EMAIL', default='')
EMAIL_REPLY_TO = config('EMAIL_REPLY_TO', default='')

# ── SMS : copie textuelle des e-mails et des relances ─────────────────
# Voir SMS_CONFIGURATION_GUIDE.md. Désactivé par défaut : aucun SMS ne part
# tant que SMS_ENABLED n'est pas vrai ET que le fournisseur n'est pas
# configuré. Les secrets (jeton Twilio) ne sont lus QUE dans l'environnement.
SMS_ENABLED = config('SMS_ENABLED', default=False, cast=bool)
# twilio : envoi réel ; capture : enregistré dans FEBA, jamais envoyé
# (développement et tests) ; console : écrit dans le journal, jamais envoyé.
SMS_PROVIDER = config('SMS_PROVIDER', default='capture').strip().lower()
# Numéro d'expédition au format E.164. Il doit appartenir au compte du
# fournisseur et être autorisé pour l'envoi de SMS (`manage.py sms_check`).
SMS_FROM_NUMBER = config('SMS_FROM_NUMBER', default='')
TWILIO_ACCOUNT_SID = config('TWILIO_ACCOUNT_SID', default='')
TWILIO_AUTH_TOKEN = config('TWILIO_AUTH_TOKEN', default='')
# Adresse publique de FEBA à laquelle Twilio notifie la remise (delivered,
# undelivered…). Vide = pas de suivi de remise : le statut s'arrête à
# « accepté par le fournisseur ».
SMS_STATUS_CALLBACK_URL = config('SMS_STATUS_CALLBACK_URL', default='')
# Consentement : True = seuls les destinataires ayant ACCEPTÉ les SMS en
# reçoivent (valeur prudente). False = tous sauf ceux qui ont REFUSÉ —
# à n'activer qu'après validation juridique (clause du contrat de
# scolarité, par exemple).
SMS_REQUIRE_EXPLICIT_CONSENT = config('SMS_REQUIRE_EXPLICIT_CONSENT', default=True, cast=bool)
# Indicatif présumé d'un numéro saisi SANS « + », par académie
# (« CODE:PAYS,… »). Une académie absente de la liste : le numéro sans
# indicatif est refusé plutôt que deviné.
SMS_DEFAULT_REGIONS = config('SMS_DEFAULT_REGIONS', default='FEBA:BJ')
# Un message trop long pour un seul SMS concaténé (1 600 caractères chez
# Twilio) est découpé en plusieurs SMS numérotés, sans rien retrancher ;
# au-delà de ce nombre de SMS, l'envoi échoue explicitement.
SMS_MAX_MESSAGES_PER_NOTIFICATION = config('SMS_MAX_MESSAGES_PER_NOTIFICATION', default=5, cast=int)
SMS_TIMEOUT = config('SMS_TIMEOUT', default=15, cast=int)

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
# production : transports de test refusés au démarrage ; staging :
# préproduction, tolérés en avertissement (apps/core/preflight.py).
DEPLOYMENT_STAGE = config('DEPLOYMENT_STAGE', default='production')
STRIPE_SUCCESS_URL = config(
    'STRIPE_SUCCESS_URL', default=f'{PUBLIC_BASE_URL}/parent/payments?paiement=succes',
)
STRIPE_CANCEL_URL = config(
    'STRIPE_CANCEL_URL', default=f'{PUBLIC_BASE_URL}/parent/payments?paiement=annule',
)
STRIPE_WEBHOOK_URL = config(
    'STRIPE_WEBHOOK_URL', default=f'{PUBLIC_BASE_URL}/api/payments/webhook/stripe/',
)

# ── Conversion de devises — totaux consolidés multi-académies (P1) ──────
#
# PROBLÈME RÉSOLU : /superadmin/payments en mode « Toutes les Académies »
# additionnait directement des FCFA (FEBA) et des USD (FEBA FHA). Voir
# apps/core/currency_conversion.py pour le service qui remplace cette
# addition par une conversion explicite et tracée.
#
# `REPORTING_CURRENCY` est la devise dans laquelle un total qui mélange
# plusieurs académies est consolidé. XOF par défaut : c'est la devise de
# l'académie historique (FEBA) et celle du contexte béninois dans lequel
# la plateforme opère.
REPORTING_CURRENCY = config('REPORTING_CURRENCY', default='XOF')

# Taux de secours utilisé UNIQUEMENT quand aucun `ExchangeRate` daté n'est
# enregistré en base (Paiements ▸ Taux de change). Sert à ce qu'une
# installation neuve affiche un total consolidé dès le premier jour au
# lieu d'une erreur — mais toute réponse API utilisant ce taux le signale
# explicitement (`is_fallback: true`) : ce n'est pas un taux officiel.
#
# Clé : (devise_source, devise_cible) -> combien d'unités cible pour 1
# unité source. Le taux inverse se déduit automatiquement, inutile de
# répéter (XOF, USD).
FALLBACK_EXCHANGE_RATES = {
    ('USD', 'XOF'): config('FALLBACK_RATE_USD_XOF', default='600', cast=str),
}
