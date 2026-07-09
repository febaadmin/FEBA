from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import SchoolViewSet, SchoolYearViewSet, LevelViewSet, RoomViewSet, RoomTypeViewSet, SchoolBrandingViewSet

router = DefaultRouter()
router.register('schools', SchoolViewSet, basename='school')
router.register('years', SchoolYearViewSet, basename='schoolyear')
router.register('levels', LevelViewSet, basename='level')
router.register('rooms', RoomViewSet, basename='room')
router.register('room-types', RoomTypeViewSet, basename='roomtype')
router.register('branding', SchoolBrandingViewSet, basename='branding')

urlpatterns = router.urls
