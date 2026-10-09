"""
Routes de l'application « paiements ».

L'ordre compte : le routeur DRF est enregistré sur le préfixe vide, donc
`r""` capture aussi bien `""` que `"<pk>/"`. Les routes carte doivent donc
être déclarées AVANT, sinon `card/config/` serait interprété comme le
détail d'un paiement dont l'identifiant serait « card ».
"""
from django.urls import path
from rest_framework.routers import DefaultRouter

from . import card_views, reminder_views, views

router = DefaultRouter()
router.register(r"", views.PaymentViewSet, basename="payment")

# Échéanciers et dispositions : routeurs séparés, montés AVANT le routeur
# des paiements (sinon « fee-schedules » serait lu comme un identifiant).
schedules_router = DefaultRouter()
schedules_router.register(r"fee-schedules", reminder_views.FeeScheduleViewSet, basename="fee-schedule")
schedules_router.register(r"fee-arrangements", reminder_views.ArrangementViewSet, basename="fee-arrangement")

urlpatterns = [
    # ── Relances de paiement ──────────────────────────────────────────
    path("reminders/status/", reminder_views.ReminderStatusView.as_view(), name="reminders-status"),
    path("reminders/policy/", reminder_views.ReminderPolicyView.as_view(), name="reminders-policy"),
    path("reminders/preview/", reminder_views.ReminderPreviewView.as_view(), name="reminders-preview"),
    path("reminders/run/", reminder_views.ReminderRunView.as_view(), name="reminders-run"),
    path("reminders/history/", reminder_views.ReminderHistoryView.as_view(), name="reminders-history"),
    path("reminders/runs/", reminder_views.ReminderRunsView.as_view(), name="reminders-runs"),
] + schedules_router.urls + [
    # ── Paiement par carte ────────────────────────────────────────────
    path("card/config/", card_views.CardPaymentConfigView.as_view(),
         name="card-payment-config"),
    path("card/fees/", card_views.PayableItemsView.as_view(),
         name="card-payable-items"),
    path("card/checkout/", card_views.CreateCardPaymentView.as_view(),
         name="card-payment-checkout"),
    path("card/transactions/", card_views.CardTransactionListView.as_view(),
         name="card-transaction-list"),
    path("card/<int:pk>/refund/", card_views.RefundCardPaymentView.as_view(),
         name="card-payment-refund"),
    path("card/<int:pk>/receipt/", card_views.CardReceiptView.as_view(),
         name="card-payment-receipt"),

    # ── Webhook du prestataire ────────────────────────────────────────
    # Non authentifié au sens applicatif : c'est la SIGNATURE de l'événement
    # qui tient lieu d'authentification. Voir card_views.stripe_webhook.
    path("webhook/stripe/", card_views.stripe_webhook, name="stripe-webhook"),
] + router.urls
