from rest_framework.routers import DefaultRouter
from . import views
router = DefaultRouter()
router.register(r"", views.HomeworkViewSet, basename="homework")
urlpatterns = router.urls