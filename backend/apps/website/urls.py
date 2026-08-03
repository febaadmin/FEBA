from django.urls import path, include
from rest_framework.routers import DefaultRouter

from . import fha_views, views

router = DefaultRouter()
router.register('admin/hero-slides', views.AdminHeroSlideViewSet, basename='admin-hero')
router.register('admin/news', views.AdminNewsViewSet, basename='admin-news')
router.register('admin/gallery-albums', views.AdminGalleryAlbumViewSet, basename='admin-albums')
router.register('admin/gallery-items', views.AdminGalleryItemViewSet, basename='admin-gallery-items')
router.register('admin/contact-messages', views.AdminContactMessageViewSet, basename='admin-contact')
router.register('admin/preregistrations', views.AdminPreRegistrationViewSet, basename='admin-prereg')
# Dossiers d'inscription FEBA French Heritage Academy (modèle distinct
# de la préinscription FEBA, boîte de réception séparée).
router.register('admin/fha-applications', fha_views.FHAApplicationViewSet, basename='admin-fha-applications')
# Demandes de test de placement : boîte SÉPARÉE des inscriptions.
router.register('admin/fha-placement-tests', fha_views.FHAPlacementTestViewSet, basename='admin-fha-placement-tests')

urlpatterns = [
    # Public — lecture
    path('settings/', views.PublicSettingsView.as_view(), name='site-settings'),
    path('hero-slides/', views.PublicHeroSlidesView.as_view(), name='site-hero'),
    path('news/', views.PublicNewsListView.as_view(), name='site-news'),
    path('news/<slug:slug>/', views.PublicNewsDetailView.as_view(), name='site-news-detail'),
    path('gallery/', views.PublicGalleryView.as_view(), name='site-gallery'),
    # Public — formulaires
    path('contact/', views.ContactMessageCreateView.as_view(), name='site-contact'),
    path('preregistrations/', views.PreRegistrationCreateView.as_view(), name='site-prereg'),
    # Public — formulaires FEBA French Heritage Academy (entité imposée
    # par la route, jamais par le client).
    path('fha/contact/', fha_views.FHAContactCreateView.as_view(), name='fha-contact'),
    path('fha/enroll/', fha_views.FHAEnrollmentCreateView.as_view(), name='fha-enroll'),
    # « Réserver un test » ≠ « Inscrire mon enfant » : deux parcours,
    # deux modèles, deux numérotations, deux boîtes de réception.
    path('fha/placement-test/', fha_views.FHAPlacementTestCreateView.as_view(), name='fha-placement-test'),
    path('fha/program/', fha_views.FHAProgramInfoView.as_view(), name='fha-program'),
    # Admin — paramètres (singleton) + CRUD via router
    path('admin/settings/', views.AdminSiteSettingsView.as_view(), name='site-admin-settings'),
    path('', include(router.urls)),
]
