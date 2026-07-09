from rest_framework.routers import DefaultRouter
from . import views
router = DefaultRouter()
router.register(r"", views.PaymentViewSet, basename="payment")
urlpatterns = router.urls