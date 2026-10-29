from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (SchoolViewSet, SchoolYearViewSet, LevelViewSet, RoomViewSet, RoomTypeViewSet,
                    SchoolBrandingViewSet, PublicBrandingView)

router = DefaultRouter()
router.register('schools', SchoolViewSet, basename='school')
router.register('years', SchoolYearViewSet, basename='schoolyear')
router.register('levels', LevelViewSet, basename='level')
router.register('rooms', RoomViewSet, basename='room')
router.register('room-types', RoomTypeViewSet, basename='roomtype')
router.register('branding', SchoolBrandingViewSet, basename='branding')

urlpatterns = [
    path('public-branding/<str:code>/', PublicBrandingView.as_view(), name='public-branding'),
    path('public-branding/<str:code>/logo/', PublicBrandingView.as_view(), {'asset': 'logo'},
         name='public-branding-logo'),
    path('public-branding/<str:code>/favicon-<int:size>.png', PublicBrandingView.as_view(),
         {'asset': 'favicon'}, name='public-branding-favicon'),
] + router.urls
