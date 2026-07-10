from .base import *
import dj_database_url

DEBUG = True

ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='localhost,127.0.0.1').split(',')

DATABASES = {
    'default': dj_database_url.parse(
        config('DATABASE_URL', default='postgresql://feba_user:feba_dev_pass@localhost:5432/feba_dev')
    )
}

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'LOCATION': REDIS_URL,
    }
}

# ── Mode test ────────────────────────────────────────────────────────────────
# La suite de tests s'authentifie via POST /api/auth/login/ (plusieurs
# centaines d'appels depuis la même IP). Le rate-limit « 20/min » stocké
# dans Redis persiste d'un test à l'autre et faisait échouer ~80 tests
# avec « L'en-tête Authorization doit contenir deux valeurs » (token vide).
# En mode test : rate-limit désactivé + cache mémoire isolé par processus.
import sys
if 'test' in sys.argv or 'pytest' in sys.modules:
    RATELIMIT_ENABLE = False
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        }
    }
    CHANNEL_LAYERS = {
        'default': {'BACKEND': 'channels.layers.InMemoryChannelLayer'},
    }
    # Hachage rapide des mots de passe : accélère surtout les setUp()
    PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']

CORS_ALLOWED_ORIGINS = config('CORS_ALLOWED_ORIGINS', default='http://localhost:5173').split(',')
CORS_ALLOW_CREDENTIALS = True

INSTALLED_APPS += ['debug_toolbar']
MIDDLEWARE += ['debug_toolbar.middleware.DebugToolbarMiddleware']
INTERNAL_IPS = ['127.0.0.1']
