from rest_framework.routers import DefaultRouter
from . import views
router = DefaultRouter()
router.register(r"", views.BulletinViewSet, basename="bulletin")
urlpatterns = router.urls