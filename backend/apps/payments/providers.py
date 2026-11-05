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

    def supports_currency(self, code):
        """Devise acceptée par ce prestataire (Stripe : toutes celles de FEBA)."""
        return True

    def fetch(self, provider_id):
        """État de la transaction chez le prestataire (vérification serveur à serveur)."""
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


class FedaPayPaymentProvider(PaymentProvider):
    """
    FedaPay (Cotonou, Bénin) : page de paiement hébergée, cartes Visa/Mastercard
    et Mobile Money, en francs CFA (XOF).

    Pourquoi FedaPay : Stripe n'ouvre pas de compte marchand à une entreprise
    établie au Bénin ; FedaPay est un établissement béninois qui encaisse en XOF
    (voir docs/livraison/phase7/RAPPORT_VALIDATION_PAIEMENTS.md, comparatif).

    Rien n'est cru sur parole :
    - le webhook est authentifié (en-tête X-FEDAPAY-SIGNATURE : « t=<horodatage>,s=<HMAC-SHA256
      hexadécimal de "<t>.<corps>"> », tolérance 5 minutes, comparaison à temps constant) ;
    - même authentifié, l'événement ne sert qu'à désigner la transaction : son statut,
      son montant et sa devise sont RELUS chez FedaPay (appel serveur à serveur) ;
    - le retour du navigateur ne déclenche qu'une vérification serveur à serveur.

    Les données de carte ne transitent jamais par FEBA (page hébergée par FedaPay).
    """

    name = "fedapay"
    DEVISES = {"XOF"}            # seule devise documentée par FedaPay pour l'encaissement
    TOLERANCE_SECONDES = 300
    URLS = {"sandbox": "https://sandbox-api.fedapay.com/v1", "live": "https://api.fedapay.com/v1"}
    #: Statut FedaPay → statut FEBA (PaymentTransaction).
    STATUTS = {
        "pending": "pending", "approved": "succeeded", "transferred": "succeeded",
        "declined": "failed", "canceled": "cancelled", "cancelled": "cancelled",
        "expired": "expired", "refunded": "refunded",
    }

    def is_configured(self):
        return bool(getattr(settings, "CARD_PAYMENTS_ENABLED", False)
                    and getattr(settings, "FEDAPAY_SECRET_KEY", "")
                    and getattr(settings, "FEDAPAY_WEBHOOK_SECRET", ""))

    def assert_configured(self):
        if not self.is_configured():
            raise PaymentProviderNotConfigured(
                "Le paiement par carte n'est pas configuré sur cette instance "
                "(compte marchand FedaPay, clé secrète et secret de webhook requis)."
            )

    def supports_currency(self, code):
        return (code or "").upper() in self.DEVISES

    @property
    def environnement(self):
        env = (getattr(settings, "FEDAPAY_ENVIRONMENT", "sandbox") or "sandbox").lower()
        return env if env in self.URLS else "sandbox"

    def _requete(self, methode, chemin, corps=None):
        """Appel authentifié à l'API FedaPay (bibliothèque standard, délai borné)."""
        import json
        import urllib.error
        import urllib.request
        requete = urllib.request.Request(
            self.URLS[self.environnement] + chemin, method=methode,
            data=json.dumps(corps).encode() if corps is not None else None,
            headers={"Authorization": f"Bearer {settings.FEDAPAY_SECRET_KEY}",
                     "Content-Type": "application/json", "Accept": "application/json"},
        )
        try:
            with urllib.request.urlopen(requete, timeout=20) as reponse:
                return json.loads(reponse.read().decode() or "{}")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode(errors="ignore")[:300]
            # Jamais la clé dans le journal : seulement le code et le message du prestataire.
            logger.warning("FedaPay %s %s : HTTP %s %s", methode, chemin, exc.code, detail)
            raise PaymentProviderError(f"Le prestataire a refusé la demande (HTTP {exc.code}).") from exc
        except (urllib.error.URLError, TimeoutError, ValueError) as exc:
            logger.warning("FedaPay %s %s injoignable : %s", methode, chemin, exc)
            raise PaymentProviderError("Le prestataire de paiement est injoignable. Réessayez dans un instant.") from exc

    @staticmethod
    def _objet(reponse, cle="transaction"):
        """L'API enveloppe ses objets (« v1/transaction ») ; on accepte les deux formes."""
        if not isinstance(reponse, dict):
            return {}
        for k in (f"v1/{cle}", cle):
            if isinstance(reponse.get(k), dict):
                return reponse[k]
        return reponse

    def create_checkout(self, transaction, success_url, cancel_url, description=""):
        self.assert_configured()
        if not self.supports_currency(transaction.currency):
            raise PaymentProviderError(
                f"FedaPay n'encaisse pas en {transaction.currency} : paiement en ligne indisponible pour cette académie.")
        from apps.core.currency import currency_for
        unite = currency_for(transaction.academy).minor_units_per_unit
        if transaction.amount_minor % unite:
            raise PaymentProviderError("Montant non représentable dans la devise du prestataire.")
        payeur = transaction.payer
        corps = {
            "description": (description or "Frais de scolarité")[:250],
            "amount": transaction.amount_minor // unite,
            "currency": {"iso": transaction.currency},
            "callback_url": success_url,
            # Métadonnées NON SENSIBLES : rapprochement de secours.
            "custom_metadata": {"transaction_id": str(transaction.pk), "reference": transaction.idempotency_key,
                                "academy_code": transaction.academy.code or ""},
        }
        if payeur and payeur.email:
            corps["customer"] = {"firstname": (payeur.first_name or "")[:60], "lastname": (payeur.last_name or "")[:60],
                                 "email": payeur.email}
        cree = self._objet(self._requete("POST", "/transactions", corps))
        if not cree.get("id"):
            raise PaymentProviderError("Réponse du prestataire inattendue (transaction sans identifiant).")
        jeton = self._requete("POST", f"/transactions/{cree['id']}/token")
        url = (jeton or {}).get("url") or self._objet(jeton, "token").get("url")
        if not url:
            raise PaymentProviderError("Réponse du prestataire inattendue (lien de paiement absent).")
        return str(cree["id"]), url

    def fetch(self, provider_id):
        """Transaction telle que FedaPay la connaît : {statut, montant (unités), devise, brut}."""
        self.assert_configured()
        t = self._objet(self._requete("GET", f"/transactions/{int(provider_id)}"))
        devise = t.get("currency", {})
        if isinstance(devise, dict):
            devise = devise.get("iso") or devise.get("code")
        return {"statut": (t.get("status") or "").lower(), "montant": t.get("amount"),
                "devise": (devise or "").upper() or None, "id": str(t.get("id") or provider_id),
                "metadata": t.get("custom_metadata") or {}}

    def verify_webhook(self, payload, signature_header):
        import hashlib
        import hmac
        import json
        import time
        secret = getattr(settings, "FEDAPAY_WEBHOOK_SECRET", "")
        if not secret:
            raise PaymentProviderNotConfigured(
                "FEDAPAY_WEBHOOK_SECRET n'est pas configuré : les événements ne peuvent pas être authentifiés.")
        morceaux = [x.split("=", 1) for x in (signature_header or "").split(",") if "=" in x]
        horodatage = next((v for k, v in morceaux if k.strip() == "t"), "")
        signatures = [v.strip() for k, v in morceaux if k.strip() == "s"]
        if not horodatage.isdigit() or not signatures:
            raise ValidationError("Signature de webhook absente ou illisible.")
        if abs(time.time() - int(horodatage)) > self.TOLERANCE_SECONDES:
            raise ValidationError("Signature de webhook périmée (rejeu possible).")
        corps = payload if isinstance(payload, bytes) else str(payload).encode()
        attendue = hmac.new(secret.encode(), horodatage.encode() + b"." + corps, hashlib.sha256).hexdigest()
        if not any(hmac.compare_digest(attendue, s) for s in signatures):
            raise ValidationError("Signature de webhook invalide.")
        try:
            return json.loads(corps.decode())
        except ValueError as exc:
            raise ValidationError("Corps de webhook illisible.") from exc

    def refund(self, transaction, amount_minor):
        # FedaPay ne documente pas de remboursement par API : il se fait depuis son tableau de bord.
        raise PaymentProviderError(
            "Le remboursement d'un paiement FedaPay se fait depuis le tableau de bord FedaPay ; "
            "enregistrez-le ensuite dans FEBA.")


#: Prestataires disponibles.
PROVIDERS = {StripePaymentProvider.name: StripePaymentProvider, FedaPayPaymentProvider.name: FedaPayPaymentProvider}


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
