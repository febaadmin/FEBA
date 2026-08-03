"""
Routes de l'application « paiements ».

L'ordre compte : le routeur DRF est enregistré sur le préfixe vide, donc
`r""` capture aussi bien `""` que `"<pk>/"`. Les routes carte doivent donc
être déclarées AVANT, sinon `card/config/` serait interprété comme le
détail d'un paiement dont l'identifiant serait « card ».
"""
from django.urls import path
from rest_framework.routers import DefaultRouter

from . import card_views, views

router = DefaultRouter()
router.register(r"", views.PaymentViewSet, basename="payment")

urlpatterns = [
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
