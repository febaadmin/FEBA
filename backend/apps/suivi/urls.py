from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("referentiels", views.ReferentielViewSet, basename="suivi-referentiel")
router.register("competences", views.CompetenceViewSet, basename="suivi-competence")
router.register("niveaux", views.NiveauViewSet, basename="suivi-niveau")
router.register("evaluations-competences", views.EvaluationCompetenceViewSet, basename="suivi-eval-competence")
router.register("evaluations", views.EvaluationPedagogiqueViewSet, basename="suivi-evaluation")
router.register("observations", views.ObservationViewSet, basename="suivi-observation")
router.register("objectifs", views.ObjectifViewSet, basename="suivi-objectif")
router.register("plans", views.PlanViewSet, basename="suivi-plan")
router.register("actions", views.ActionViewSet, basename="suivi-action")
router.register("eleves", views.EleveViewSet, basename="suivi-eleve")
router.register("parametres", views.ParametresViewSet, basename="suivi-parametres")
router.register("rapports", views.RapportViewSet, basename="suivi-rapport")
router.register("alertes", views.AlerteViewSet, basename="suivi-alerte")
router.register("activation", views.ActivationViewSet, basename="suivi-activation")
urlpatterns = router.urls
