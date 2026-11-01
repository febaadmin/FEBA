from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("questions", views.QuestionViewSet, basename="eval-question")
router.register("epreuves", views.EpreuveViewSet, basename="eval-epreuve")
router.register("copies", views.CopieViewSet, basename="eval-copie")
router.register("passage", views.PassageViewSet, basename="eval-passage")
urlpatterns = router.urls
