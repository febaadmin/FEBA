from rest_framework.routers import DefaultRouter
from . import views

from django.urls import path

router = DefaultRouter()
router.register(r"", views.VirtualRoomViewSet, basename="virtual-room")

urlpatterns = [
    # Doit précéder le routeur : « health » ne doit pas être interprété
    # comme un identifiant de salle par la route détail du ViewSet.
    path("health/", views.JitsiHealthView.as_view(), name="jitsi-health"),
] + router.urls
