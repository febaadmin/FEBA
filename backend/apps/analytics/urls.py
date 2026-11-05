from django.urls import path

from . import views

urlpatterns = [
    path("filtres/", views.OptionsView.as_view(), name="analytics-filtres"),
    path("effectifs/", views.EffectifsView.as_view(), name="analytics-effectifs"),
    path("resultats/", views.ResultatsView.as_view(), name="analytics-resultats"),
    path("matieres/", views.MatieresView.as_view(), name="analytics-matieres"),
    path("enseignants/", views.EnseignantsView.as_view(), name="analytics-enseignants"),
    path("presences/", views.PresencesView.as_view(), name="analytics-presences"),
    path("eleves/<int:pk>/", views.EleveView.as_view(), name="analytics-eleve"),
    path("vue-ensemble/", views.VueEnsembleView.as_view(), name="analytics-vue-ensemble"),
    path("matieres/detail/", views.MatieresDetailView.as_view(), name="analytics-matieres-detail"),
    path("classes/", views.ClassesView.as_view(), name="analytics-classes"),
    path("enseignants/profils/", views.EnseignantsProfilsView.as_view(), name="analytics-enseignants-profils"),
    path("mes-eleves/", views.MesElevesView.as_view(), name="analytics-mes-eleves"),
]
