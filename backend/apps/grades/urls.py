from django.urls import path
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'', views.GradeViewSet, basename='grade')

# FIX v42 (404 bilingue) : les routes explicites doivent précéder
# router.urls. Le routeur DRF enregistré sur r'' génère une route <pk>/
# qui capturait « bilingual » et « all-history » comme des identifiants de
# note → 404 (d'où « Calcul bilingue indisponible » dans l'UI, qui n'était
# pas un problème de données mais un vrai 404). Même correctif que
# notifications/unread-count en v41.
urlpatterns = [
    path('bilingual/', views.bilingual_averages_view, name='grade-bilingual'),
    path('all-history/', views.all_history_view, name='grade-all-history'),
] + router.urls
