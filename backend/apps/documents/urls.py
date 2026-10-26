from django.urls import path

from . import academy_template_views as tv
from . import views

urlpatterns = [
    path("templates/", views.DocumentTemplateListView.as_view(),
         name="document-templates"),
    path("", views.DocumentListCreateView.as_view(), name="document-list"),
    path("check/", tv.DocumentCheckView.as_view(), name="document-check"),
    path("preview/", tv.DocumentPreviewView.as_view(), name="document-preview"),
    path("batch/", tv.DocumentBatchView.as_view(), name="document-batch"),
    path("batch-issue/", tv.DocumentBatchIssueView.as_view(), name="document-batch-issue"),
    path("academy-templates/", tv.AcademyTemplateListView.as_view(),
         name="academy-templates"),
    path("academy-templates/<int:pk>/", tv.AcademyTemplateDetailView.as_view(),
         name="academy-template-detail"),
    path("academy-templates/<int:pk>/background/", tv.AcademyTemplateBackgroundView.as_view(),
         name="academy-template-background"),
    path("academy-templates/<int:pk>/original/", tv.AcademyTemplateOriginalView.as_view(),
         name="academy-template-original"),
    path("academy-templates/<int:pk>/preview/", tv.AcademyTemplatePreviewView.as_view(),
         name="academy-template-preview"),
    *[
        path(f"academy-templates/<int:pk>/{action}/",
             tv.AcademyTemplateActionView.as_view(action=action),
             name=f"academy-template-{action}")
        for action in ("validate", "activate", "disable", "reactivate", "duplicate")
    ],
    path("<int:pk>/issue/", views.DocumentIssueView.as_view(), name="document-issue"),
    path("<int:pk>/revoke/", views.DocumentRevokeView.as_view(), name="document-revoke"),
    path("<int:pk>/replace/", views.DocumentReplaceView.as_view(), name="document-replace"),
    path("<int:pk>/download/", views.DocumentDownloadView.as_view(),
         name="document-download"),
    path("<int:pk>/history/", views.DocumentHistoryView.as_view(),
         name="document-history"),
]
