"""
apps/payments/providers.py — Abstraction du prestataire de paiement

POURQUOI UNE ABSTRACTION
------------------------
Appeler l'API du prestataire depuis chaque vue lierait la logique métier —
« créer une tentative », « rapprocher un encaissement », « rembourser » —
à une bibliothèque tierce. Changer de prestataire, ou simplement le tester
sans réseau, deviendrait impossible sans réécrire les vues.

Le contrat ci-dessous est volontairement minimal : trois opérations et une
vérification de signature. Tout le reste — statuts, idempotence,
rapprochement — appartient à l'application, pas au prestataire.

FLUX RETENU : CHECKOUT HÉBERGÉ
------------------------------
Le formulaire de carte est celui de Stripe, affiché sur son domaine. Les
données de carte ne touchent donc jamais nos serveurs, ce qui maintient
l'application hors du champ d'application complet de PCI-DSS. L'alternative
(Payment Element intégré) offre une meilleure intégration visuelle au prix
d'une surface de conformité plus large et d'un formulaire à maintenir ;
pour une école qui encaisse quelques dizaines de paiements par mois, le
compromis penche nettement du côté du Checkout hébergé.
"""
import logging

from django.conf import settings
from django.core.exceptions import ValidationError

logger = logging.getLogger("apps")


class PaymentProviderError(Exception):
    """Erreur renvoyée par le prestataire, présentable à l'utilisateur."""


class PaymentProviderNotConfigured(PaymentProviderError):
    """Le prestataire n'est pas configuré : le paiement carte est indisponible."""


class PaymentProvider:
    """Contrat que doit respecter tout prestataire de paiement."""

    name = "abstract"

    def is_configured(self):
        raise NotImplementedError

    def create_checkout(self, transaction, success_url, cancel_url, description=""):
        """Crée une session de paiement et renvoie `(session_id, url)`."""
        raise NotImplementedError

    def verify_webhook(self, payload, signature_header):
        """Vérifie la signature et renvoie l'événement, ou lève une erreur."""
        raise NotImplementedError

    def refund(self, transaction, amount_minor):
        """Rembourse tout ou partie d'une transaction encaissée."""
        raise NotImplementedError


class StripePaymentProvider(PaymentProvider):
    """Stripe, en Checkout hébergé."""

    name = "stripe"

    def _stripe(self):
        """
        Import tardif : l'application doit démarrer même sans le paquet.
        Une école qui n'encaisse pas par carte n'a aucune raison
        d'installer une dépendance de paiement.
        """
        try:
            import stripe
        except ImportError as exc:  # pragma: no cover — dépend de l'installation
            raise PaymentProviderNotConfigured(
                "Le paquet « stripe » n'est pas installé. "
                "Installez-le avec : pip install stripe"
            ) from exc
        stripe.api_key = settings.STRIPE_SECRET_KEY
        return stripe

    def is_configured(self):
        return bool(
            getattr(settings, "CARD_PAYMENTS_ENABLED", False)
            and getattr(settings, "STRIPE_SECRET_KEY", "")
            and getattr(settings, "STRIPE_PUBLISHABLE_KEY", "")
        )

    def assert_configured(self):
        if not self.is_configured():
            raise PaymentProviderNotConfigured(
                "Le paiement par carte n'est pas configuré sur cette instance. "
                "Lancez « make payments-setup » puis « make payments-check »."
            )

    def create_checkout(self, transaction, success_url, cancel_url, description=""):
        self.assert_configured()
        stripe = self._stripe()

        try:
            session = stripe.checkout.Session.create(
                mode="payment",
                # La clé d'idempotence est portée par la transaction : un
                # double clic ou un rejeu réseau retombe sur LA MÊME session
                # côté Stripe, au lieu de créer un second débit.
                idempotency_key=transaction.idempotency_key,
                line_items=[{
                    "price_data": {
                        "currency": transaction.currency.lower(),
                        # Stripe attend le montant en unité mineure : c'est
                        # exactement la forme dans laquelle nous le stockons,
                        # donc aucune conversion — donc aucune erreur d'échelle.
                        "unit_amount": transaction.amount_minor,
                        "product_data": {
                            "name": description or "Frais de scolarité",
                        },
                    },
                    "quantity": 1,
                }],
                success_url=success_url,
                cancel_url=cancel_url,
                client_reference_id=str(transaction.pk),
                metadata={
                    # Métadonnées NON SENSIBLES : elles permettent de
                    # rapprocher un événement même si l'identifiant de
                    # session a été perdu. Aucune donnée personnelle.
                    "transaction_id": str(transaction.pk),
                    "academy_code": transaction.academy.code or "",
                    "student_id": str(transaction.student_id),
                },
            )
        except Exception as exc:
            logger.warning("Création de session Stripe refusée : %s", exc)
            raise PaymentProviderError(str(exc)) from exc

        return session.id, session.url

    def verify_webhook(self, payload, signature_header):
        """
        Vérifie la signature de l'événement.

        Sans cette vérification, n'importe qui connaissant l'URL pourrait
        déclarer un paiement réussi en envoyant un simple POST. C'est la
        seule chose qui distingue un encaissement réel d'une affirmation.
        """
        secret = getattr(settings, "STRIPE_WEBHOOK_SECRET", "")
        if not secret:
            raise PaymentProviderNotConfigured(
                "STRIPE_WEBHOOK_SECRET n'est pas configuré : les événements "
                "ne peuvent pas être authentifiés, ils sont donc tous refusés."
            )
        stripe = self._stripe()
        try:
            return stripe.Webhook.construct_event(payload, signature_header, secret)
        except Exception as exc:
            raise ValidationError(f"Signature de webhook invalide : {exc}") from exc

    def refund(self, transaction, amount_minor):
        self.assert_configured()
        stripe = self._stripe()
        if not transaction.provider_intent_id:
            raise PaymentProviderError(
                "Cette transaction n'a pas d'identifiant de paiement chez le "
                "prestataire : elle ne peut pas être remboursée automatiquement."
            )
        try:
            return stripe.Refund.create(
                payment_intent=transaction.provider_intent_id,
                amount=amount_minor,
                # Un remboursement rejoué ne doit pas rendre l'argent deux fois.
                idempotency_key=f"refund-{transaction.pk}-{transaction.amount_refunded_minor}",
            )
        except Exception as exc:
            logger.warning("Remboursement Stripe refusé : %s", exc)
            raise PaymentProviderError(str(exc)) from exc


#: Prestataires disponibles.
PROVIDERS = {StripePaymentProvider.name: StripePaymentProvider}


def get_provider(name=None):
    """Prestataire configuré pour cette instance."""
    key = (name or getattr(settings, "PAYMENT_PROVIDER", "stripe")).lower()
    provider_class = PROVIDERS.get(key)
    if provider_class is None:
        raise PaymentProviderNotConfigured(
            f"Prestataire de paiement inconnu : « {key} ». "
            f"Disponibles : {', '.join(sorted(PROVIDERS))}."
        )
    return provider_class()
