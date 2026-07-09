from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r"", views.VirtualRoomViewSet, basename="virtual-room")
urlpatterns = router.urls
