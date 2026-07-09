from rest_framework.routers import DefaultRouter
from . import views
router = DefaultRouter()
router.register(r"", views.ClassViewSet, basename="class")
urlpatterns = router.urls