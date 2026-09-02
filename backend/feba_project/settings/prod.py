from .base import *
import dj_database_url

DEBUG = False

ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='').split(',')

DATABASES = {
    'default': dj_database_url.parse(config('DATABASE_URL'))
}

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'LOCATION': REDIS_URL,
    }
}

CORS_ALLOWED_ORIGINS = [o for o in config('CORS_ALLOWED_ORIGINS', default='').split(',') if o]
CORS_ALLOW_CREDENTIALS = True

# ── CSRF derrière le proxy TLS ────────────────────────────────────────
#
# MANQUANT JUSQU'ICI, ET BLOQUANT EN PRODUCTION.
#
# Depuis Django 4, une requête POST portant un en-tête `Origin` est
# refusée si cette origine n'est pas listée ici — « CSRF verification
# failed. Origin checking failed ». L'API échappe au problème (elle
# s'authentifie par jeton JWT, sans cookie de session), ce qui rend le
# défaut invisible à l'usage courant : tout marche, jusqu'à ce qu'un
# administrateur tente de se connecter à /django-admin/, exposé par
# nginx/nginx.prod.conf. Il ne peut alors plus entrer du tout.
#
# Les origines sont dérivées d'ALLOWED_HOSTS quand la variable n'est pas
# renseignée : sans ce repli, une installation existante qui se contente
# de mettre à jour le code resterait cassée sans savoir pourquoi. Le
# schéma est obligatoire (Django l'exige), et c'est https : ce module ne
# sert que derrière TLS.
CSRF_TRUSTED_ORIGINS = [
    o for o in config('CSRF_TRUSTED_ORIGINS', default='').split(',') if o
] or [
    f"https://{host.strip()}"
    for host in ALLOWED_HOSTS
    if host.strip() and host.strip() not in ('*',)
]

# Le cookie de session ne doit pas accompagner une navigation venue d'un
# autre site : c'est ce qui rend une attaque CSRF inopérante même si une
# vue oubliait sa protection.
SESSION_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_SAMESITE = 'Lax'

SECURE_SSL_REDIRECT = config('SECURE_SSL_REDIRECT', default=True, cast=bool)
SECURE_HSTS_SECONDS = config('HSTS_SECONDS', default=31536000, cast=int)
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
