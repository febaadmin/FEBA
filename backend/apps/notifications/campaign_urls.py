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
]
