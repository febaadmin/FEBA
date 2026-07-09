from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import UserFileViewSet

router = DefaultRouter()
router.register("", UserFileViewSet, basename="user-file")

urlpatterns = router.urls
