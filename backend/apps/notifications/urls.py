from django.urls import path
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r"", views.NotificationViewSet, basename="notification")

# FIX v41 (404 console) : les routes explicites doivent précéder router.urls.
# Le routeur DRF enregistré sur r"" génère une route <pk>/ qui capturait
# « unread-count » comme un identifiant → 404. En plaçant les alias AVANT,
# ils sont résolus en priorité. Le frontend appelle /unread-count/ (tiret) ;
# le routeur expose /unread_count/ (underscore) — les deux fonctionnent.
from . import outbox_views, sms_views

urlpatterns = [
    # Boîte d'envoi et diagnostic SMTP — avant le routeur (préfixe vide).
    path("outbox/", outbox_views.OutboxListView.as_view(), name="outbox-list"),
    path("outbox/<int:pk>/", outbox_views.OutboxDetailView.as_view(), name="outbox-detail"),
    path("outbox/<int:pk>/retry/", outbox_views.OutboxRetryView.as_view(), name="outbox-retry"),
    path("outbox/<int:pk>/attachments/<int:attachment_id>/", outbox_views.OutboxAttachmentView.as_view(),
         name="outbox-attachment"),
    path("sms/", sms_views.SmsListView.as_view(), name="sms-list"),
    path("sms/<int:pk>/retry/", sms_views.SmsRetryView.as_view(), name="sms-retry"),
    path("sms/status/", sms_views.TwilioStatusCallbackView.as_view(), name="sms-status-callback"),
    path("email-config/", outbox_views.EmailConfigView.as_view(), name="email-config"),
    path("email-config/test/", outbox_views.EmailConfigTestView.as_view(), name="email-config-test"),
    path("unread-count/", views.NotificationViewSet.as_view({"get": "unread_count"}), name="notification-unread-count"),
    path("read-all/", views.NotificationViewSet.as_view({"put": "read_all", "patch": "read_all"}), name="notification-read-all"),
    path("<int:pk>/read/", views.NotificationViewSet.as_view({"put": "read", "patch": "read"}), name="notification-read"),
] + router.urls
