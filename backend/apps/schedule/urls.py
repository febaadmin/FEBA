from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
# ORDRE IMPORTANT : le viewset des créneaux FEBA est enregistré sur le
# préfixe vide, donc son URL de détail est `/api/schedule/<pk>/`. Elle
# capturerait « online-sessions » comme identifiant si les séances FEBA FHA
# étaient déclarées après.
router.register(r"online-sessions", views.OnlineSessionScheduleViewSet, basename="online-session")
router.register(r"", views.ClassScheduleViewSet, basename="schedule")

urlpatterns = router.urls
