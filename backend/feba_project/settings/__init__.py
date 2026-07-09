from decouple import config
env = config('DJANGO_ENV', default='dev')
if env == 'prod':
    from .prod import *
else:
    from .dev import *
