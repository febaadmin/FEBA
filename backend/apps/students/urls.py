from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import StudentViewSet, StudentEnrollmentViewSet

router = DefaultRouter()
router.register('', StudentViewSet, basename='student')
router.register('enrollments', StudentEnrollmentViewSet, basename='enrollment')

urlpatterns = router.urls
