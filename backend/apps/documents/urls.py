from django.urls import path

from . import views

urlpatterns = [
    path("templates/", views.DocumentTemplateListView.as_view(),
         name="document-templates"),
    path("", views.DocumentListCreateView.as_view(), name="document-list"),
    path("<int:pk>/issue/", views.DocumentIssueView.as_view(), name="document-issue"),
    path("<int:pk>/revoke/", views.DocumentRevokeView.as_view(), name="document-revoke"),
    path("<int:pk>/replace/", views.DocumentReplaceView.as_view(), name="document-replace"),
    path("<int:pk>/download/", views.DocumentDownloadView.as_view(),
         name="document-download"),
    path("<int:pk>/history/", views.DocumentHistoryView.as_view(),
         name="document-history"),
]
