from django.urls import path

from . import campaign_views as views

urlpatterns = [
    path("options/", views.MassEmailOptionsView.as_view(), name="mass-email-options"),
    path("recipients/", views.MassEmailRecipientsView.as_view(), name="mass-email-recipients"),
    path("preview/", views.MassEmailPreviewView.as_view(), name="mass-email-preview"),
    path("campaigns/", views.MassEmailCampaignListView.as_view(), name="mass-email-campaigns"),
    path("campaigns/<int:pk>/", views.MassEmailCampaignDetailView.as_view(), name="mass-email-campaign"),
    path("campaigns/<int:pk>/retry-failed/", views.MassEmailRetryFailedView.as_view(),
         name="mass-email-retry-failed"),
    path("brouillons/", views.BrouillonListeView.as_view(), name="mass-email-brouillons"),
    path("brouillons/<int:pk>/", views.BrouillonDetailView.as_view(), name="mass-email-brouillon"),
    path("brouillons/<int:pk>/pieces/", views.BrouillonPiecesView.as_view(), name="mass-email-brouillon-pieces"),
    path("brouillons/<int:pk>/pieces/<int:piece_id>/", views.BrouillonPiecesView.as_view(),
         name="mass-email-brouillon-piece"),
    path("signature/", views.SignatureView.as_view(), name="mass-email-signature"),
]
