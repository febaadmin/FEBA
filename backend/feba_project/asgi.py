import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import AllowedHostsOriginValidator

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'feba_project.settings')

django_asgi_app = get_asgi_application()

from apps.messaging.routing import websocket_urlpatterns as chat_ws
from apps.notifications.routing import websocket_urlpatterns as notif_ws
from apps.accounts.middleware import JWTAuthMiddlewareStack

application = ProtocolTypeRouter({
    'http': django_asgi_app,
    'websocket': AllowedHostsOriginValidator(
        JWTAuthMiddlewareStack(
            URLRouter(chat_ws + notif_ws)
        )
    ),
})
