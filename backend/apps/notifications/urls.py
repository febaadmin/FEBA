from django.urls import path
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r"", views.NotificationViewSet, basename="notification")

# FIX v41 (404 console) : les routes explicites doivent précéder router.urls.
# Le routeur DRF enregistré sur r"" génère une route <pk>/ qui capturait
# « unread-count » comme un identifiant → 404. En plaçant les alias AVANT,
# ils sont résolus en priorité. Le frontend appelle /unread-count/ (tiret) ;
# le routeur expose /unread_count/ (underscore) — les deux fonctionnent.
urlpatterns = [
    path("unread-count/", views.NotificationViewSet.as_view({"get": "unread_count"}), name="notification-unread-count"),
    path("read-all/", views.NotificationViewSet.as_view({"put": "read_all", "patch": "read_all"}), name="notification-read-all"),
    path("<int:pk>/read/", views.NotificationViewSet.as_view({"put": "read", "patch": "read"}), name="notification-read"),
] + router.urls
