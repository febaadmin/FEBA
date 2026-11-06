from django.urls import path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register(r"", views.TechnicalIncidentViewSet, basename="technical-incident")

# Avant les routes du routeur : « frontend » ne doit pas être lu comme un identifiant.
urlpatterns = [
    path("frontend/", views.SignalementInterfaceView.as_view({"post": "create"}), name="incident-frontend"),
] + router.urls
