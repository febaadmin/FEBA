from django.urls import path

from . import views

urlpatterns = [
    path("etat/", views.EtatView.as_view(), name="boite-mail-etat"),
    path("messages/", views.MessagesView.as_view(), name="boite-mail-messages"),
    path("messages/<int:pk>/", views.MessageDetailView.as_view(), name="boite-mail-message"),
    path("messages/<int:pk>/action/", views.ActionView.as_view(), name="boite-mail-action"),
    path("actions/", views.ActionView.as_view(), name="boite-mail-actions"),
    path("pieces/<int:pk>/", views.PieceView.as_view(), name="boite-mail-piece"),
    path("envoyer/", views.EnvoyerView.as_view(), name="boite-mail-envoyer"),
    path("synchroniser/", views.SynchroniserView.as_view(), name="boite-mail-synchroniser"),
    path("acces/", views.AccesView.as_view(), name="boite-mail-acces"),
    path("journal/", views.JournalView.as_view(), name="boite-mail-journal"),
]
