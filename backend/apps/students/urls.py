from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import StudentViewSet, StudentEnrollmentViewSet

router = DefaultRouter()
# `enrollments` AVANT la route générique : enregistrée après, elle était
# capturée par le détail élève (`/students/<pk>/` avec pk="enrollments")
# et répondait 404 — l'historique des inscriptions était inaccessible.
router.register('enrollments', StudentEnrollmentViewSet, basename='enrollment')
router.register('', StudentViewSet, basename='student')

urlpatterns = router.urls
