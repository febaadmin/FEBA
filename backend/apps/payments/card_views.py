"""
apps/payments/card_views.py — Paiement par carte : tentative, webhook, remboursement

TROIS RÈGLES QUI STRUCTURENT CE MODULE
--------------------------------------

1. **Le montant est recalculé côté serveur.** Le navigateur envoie ce qu'il
   veut payer ; le serveur décide combien. Accepter un montant transmis
   permettrait de régler une facture de 1 250 $ avec 1 $.

2. **La redirection n'est pas une preuve.** L'URL de succès est devinable
   et un paiement peut être annulé après coup. Seul le webhook signé fait
   foi : c'est lui, et lui seul, qui crée l'encaissement.

3. **Tout est idempotent.** Double clic, rechargement, webhook rejoué,
   remboursement relancé : chaque opération doit pouvoir être répétée sans
   débiter ni créditer deux fois.
"""
import logging

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction as db_transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.request_text import identifiant
from apps.core.currency import Money
from apps.core.tenancy import get_request_school
from apps.payments.providers import (
    PaymentProviderError, PaymentProviderNotConfigured, get_provider,
)
from apps.payments.transaction_models import PaymentTransaction, WebhookEvent

logger = logging.getLogger("apps")


def _visible_students(user):
    """
    Élèves pour lesquels cet utilisateur peut légitimement payer.

    Un parent ne paie que pour SES enfants. Sans ce filtre, il suffirait de
    changer un identifiant dans la requête pour régler — ou consulter — la
    facture d'un autre élève.
    """
    from apps.students.models import Student

    if user.is_superadmin():
        return Student.objects.all()
    if user.role_level >= 80:
        return Student.objects.filter(school=user.school)
    if user.is_parent():
        try:
            return Student.objects.filter(parents__parent__user=user)
        except Exception:
            return Student.objects.none()
    if user.is_student():
        return Student.objects.filter(user=user)
    return Student.objects.none()


class CardPaymentConfigView(APIView):
    """
    GET /api/payments/card/config/

    Indique si le paiement par carte est réellement utilisable, et pourquoi
    il ne l'est pas le cas échéant. Le frontend s'en sert pour ne PAS
    afficher un bouton qui échouerait au clic.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        academy = get_request_school(request)
        try:
            provider = get_provider()
            configured = provider.is_configured()
            reason = "" if configured else (
                "Le paiement par carte n'est pas configuré sur cette instance."
            )
        except PaymentProviderNotConfigured as exc:
            provider, configured, reason = None, False, str(exc)

        devise = getattr(academy, "currency_code", None)
        devise_ok = bool(provider and devise and provider.supports_currency(devise))
        if configured and devise and not devise_ok:
            reason = f"Le prestataire de paiement n'encaisse pas en {devise} : paiement en ligne indisponible pour cette académie."
        return Response({
            "enabled": bool(configured) and (devise is None or devise_ok),
            "provider": getattr(provider, "name", settings.PAYMENT_PROVIDER),
            "environment": getattr(provider, "environnement", settings.STRIPE_MODE) if provider else "",
            "mode": settings.STRIPE_MODE,
            "publishable_key": settings.STRIPE_PUBLISHABLE_KEY if configured else "",
            "currency": getattr(academy, "currency_code", None),
            "currency_symbol": getattr(academy, "currency_symbol", None),
            "reason": reason,
        })


class PayableItemsView(APIView):
    """
    GET /api/payments/card/fees/?student=<id>

    Ce que l'académie de cet élève facture, et à quel prix. Le payeur
    choisit une LIGNE, pas un montant : c'est ce qui rend le montant
    non falsifiable côté navigateur.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from apps.payments.fee_models import FeeSchedule
        from apps.payments.models import Payment

        student = _visible_students(request.user).filter(
            pk=identifiant(request.query_params.get("student")),
        ).select_related("school").first()
        if student is None:
            return Response({"detail": "Élève introuvable ou hors de votre périmètre."},
                            status=status.HTTP_404_NOT_FOUND)

        academy = student.school
        year = academy.years.filter(is_current=True).first() if academy else None

        items = []
        for code, label in Payment.PAYMENT_TYPES:
            fee = FeeSchedule.resolve(student, code, year)
            if fee is None:
                continue
            items.append({
                "payment_type": code,
                "label": fee.display_label or label,
                "amount_minor": fee.amount_minor,
                "currency": fee.currency,
                "amount_display": fee.money.formatted(),
            })

        return Response({
            "student": student.pk,
            "academy_code": getattr(academy, "code", None),
            "academy_name": getattr(academy, "name", None),
            "currency": getattr(academy, "currency_code", None),
            "items": items,
        })


class CreateCardPaymentView(APIView):
    """
    POST /api/payments/card/checkout/
        {"student": <id>, "payment_type": "mensualite"}

    Crée une tentative et renvoie l'URL du formulaire sécurisé du
    prestataire. Aucune donnée de carte ne transite par ce serveur.

    Le corps ne contient PAS de montant utilisable : celui-ci est résolu
    depuis la grille tarifaire de l'académie. Un champ `amount` transmis
    n'est lu que pour un membre de l'administration, et uniquement quand
    l'académie ne publie aucun tarif pour ce type de frais.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        provider = get_provider()
        try:
            provider.assert_configured()
        except PaymentProviderNotConfigured as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        student_id = identifiant(request.data.get("student"))
        student = _visible_students(request.user).filter(pk=student_id).first()
        if student is None:
            # Volontairement un 404 et non un 403 : confirmer l'existence
            # d'un élève qu'on n'a pas le droit de voir est déjà une fuite.
            return Response(
                {"detail": "Élève introuvable ou hors de votre périmètre."},
                status=status.HTTP_404_NOT_FOUND,
            )

        academy = student.school
        if academy is None:
            return Response(
                {"detail": "Cet élève n'est rattaché à aucune académie."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        from apps.payments.fee_models import FeeSchedule
        from apps.payments.models import Payment

        # Le type est contraint à la liste du modèle : il finira dans un
        # `Payment`, et un libellé libre y créerait une ligne comptable
        # impossible à agréger.
        payment_type = request.data.get("payment_type") or "mensualite"
        if payment_type not in dict(Payment.PAYMENT_TYPES):
            return Response(
                {"payment_type": "Type de paiement inconnu."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not provider.supports_currency(academy.currency_code):
            return Response(
                {"detail": f"Le prestataire de paiement n'encaisse pas en {academy.currency_code} : "
                           "réglez ces frais auprès du secrétariat."},
                status=status.HTTP_409_CONFLICT,
            )

        current_year = academy.years.filter(is_current=True).first()

        # ── LE MONTANT EST DÉCIDÉ ICI, PAS DANS LA REQUÊTE ────────────
        # `request.data["amount"]` n'est jamais lu pour un payeur : c'est
        # la grille tarifaire de l'académie qui fait foi. Sans cette
        # résolution, remplacer 1250 par 1 dans les outils de
        # développement suffirait à solder une année de scolarité.
        fee = FeeSchedule.resolve(student, payment_type, current_year)
        if fee is not None:
            amount_minor, amount_source = fee.amount_minor, "fee_schedule"
        elif request.user.role_level >= 80:
            # Hors grille : réservé à l'administration de l'académie, qui
            # engage sa responsabilité. Un parent n'a jamais ce droit.
            fee, amount_source = None, "staff"
            currency = academy.currency
            try:
                amount_minor = currency.to_minor(request.data.get("amount"))
            except Exception:
                amount_minor = None
            if not amount_minor or amount_minor <= 0:
                return Response(
                    {"amount": "Montant invalide."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        else:
            return Response(
                {"detail": (
                    "Aucun tarif n'est publié pour ce type de frais dans "
                    "cette académie. Contactez le secrétariat : un montant "
                    "saisi librement ne peut pas être encaissé en ligne."
                )},
                status=status.HTTP_409_CONFLICT,
            )

        # Une tentative encore ouverte pour le même élève et le même montant
        # est RÉUTILISÉE plutôt que dupliquée : c'est ce qui rend le double
        # clic inoffensif.
        existing = PaymentTransaction.objects.filter(
            student=student, payment_type=payment_type, amount_minor=amount_minor,
            status__in=PaymentTransaction.OPEN_STATUSES,
        ).order_by("-created_at").first()
        if existing and existing.provider_metadata.get("checkout_url"):
            return Response({
                "transaction_id": existing.pk,
                "checkout_url": existing.provider_metadata["checkout_url"],
                "amount_display": existing.money.formatted(),
                "reused": True,
            })

        attempt = PaymentTransaction.objects.create(
            academy=academy,
            payer=request.user,
            student=student,
            school_year=current_year,
            payment_type=payment_type,
            fee_schedule=fee,
            amount_source=amount_source,
            amount_minor=amount_minor,
            provider=provider.name,
            status=PaymentTransaction.CREATED,
        )

        label = fee.display_label if fee else dict(Payment.PAYMENT_TYPES).get(
            attempt.payment_type, attempt.payment_type,
        )
        description = f"{student.get_full_name()} - {label}"

        if provider.name == "stripe":
            success_url, cancel_url = settings.STRIPE_SUCCESS_URL, settings.STRIPE_CANCEL_URL
        else:
            success_url = settings.CARD_RETURN_URL.replace("{id}", str(attempt.pk))
            cancel_url = success_url
        try:
            session_id, checkout_url = provider.create_checkout(
                attempt,
                success_url=success_url,
                cancel_url=cancel_url,
                description=description,
            )
        except PaymentProviderError as exc:
            attempt.mark_failed(reason=str(exc))
            return Response({"detail": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)

        attempt.provider_session_id = session_id or ""
        if provider.name != "stripe":
            # FedaPay : l'identifiant de la transaction est la clé de toute vérification.
            attempt.provider_intent_id = session_id or ""
        attempt.provider_metadata = {"checkout_url": checkout_url}
        attempt.status = PaymentTransaction.PENDING
        attempt.save(update_fields=[
            "provider_session_id", "provider_intent_id", "provider_metadata", "status", "updated_at",
        ])

        return Response({
            "transaction_id": attempt.pk,
            "checkout_url": checkout_url,
            "amount_display": attempt.money.formatted(),
            "currency": attempt.currency,
            "reused": False,
        }, status=status.HTTP_201_CREATED)


@api_view(["POST"])
@authentication_classes([])          # le prestataire n'a pas de session
@permission_classes([AllowAny])      # la SIGNATURE fait l'authentification
def stripe_webhook(request):
    """
    POST /api/payments/webhook/stripe/

    Point d'entrée des événements du prestataire. C'est ici — et nulle part
    ailleurs — qu'un paiement devient un encaissement.

    La signature est vérifiée sur le CORPS BRUT : re-sérialiser le JSON
    parsé changerait un espace ou un ordre de clés et invaliderait la
    signature, ce qui ferait rejeter des événements parfaitement légitimes.
    """
    provider = get_provider("stripe")
    signature = request.META.get("HTTP_STRIPE_SIGNATURE", "")

    try:
        event = provider.verify_webhook(request.body, signature)
    except PaymentProviderNotConfigured as exc:
        logger.error("Webhook refusé : configuration absente : %s", exc)
        return Response({"detail": "Webhook non configuré."},
                        status=status.HTTP_503_SERVICE_UNAVAILABLE)
    except ValidationError as exc:
        # Sans signature valide, l'événement n'est qu'une affirmation :
        # n'importe qui connaissant l'URL pourrait déclarer un paiement.
        logger.warning("Webhook refusé : signature invalide.")
        return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    event_id = event.get("id") or ""
    event_type = event.get("type") or ""

    # Anti-double-traitement : l'unicité est en base, car deux instances du
    # serveur peuvent recevoir le même événement au même instant.
    try:
        with db_transaction.atomic():
            record = WebhookEvent.objects.create(
                provider="stripe", event_id=event_id, event_type=event_type,
            )
    except IntegrityError:
        logger.info("Événement %s déjà traité, ignoré.", event_id)
        return Response({"received": True, "duplicate": True})

    try:
        handled = _handle_event(event, record)
    except Exception as exc:  # pragma: no cover — filet de sécurité
        logger.exception("Échec de traitement du webhook %s", event_id)
        record.status = WebhookEvent.FAILED
        record.detail = str(exc)[:500]
        record.save(update_fields=["status", "detail"])
        # On répond 200 : un 500 ferait rejouer l'événement en boucle alors
        # que le problème est chez nous. L'incident est journalisé.
        return Response({"received": True, "handled": False})

    record.status = WebhookEvent.PROCESSED if handled else WebhookEvent.IGNORED
    record.processed_at = timezone.now()
    record.save(update_fields=["status", "processed_at"])
    return Response({"received": True, "handled": handled})


def _find_transaction(obj):
    """
    Retrouve la tentative concernée par un objet d'événement.

    Trois chemins, du plus fiable au plus large : l'identifiant que nous
    avons nous-mêmes posé, puis les identifiants du prestataire. Un
    événement peut arriver AVANT que nous ayons enregistré l'identifiant de
    PaymentIntent, d'où la recherche par session.
    """
    metadata = obj.get("metadata") or {}
    reference = metadata.get("transaction_id") or obj.get("client_reference_id")
    if reference:
        found = PaymentTransaction.objects.filter(pk=reference).first()
        if found:
            return found

    for field, value in (
        ("provider_session_id", obj.get("id")),
        ("provider_intent_id", obj.get("payment_intent") or obj.get("id")),
    ):
        if value:
            found = PaymentTransaction.objects.filter(**{field: value}).first()
            if found:
                return found
    return None


def _handle_event(event, record):
    """Applique l'événement. Renvoie True s'il a modifié quelque chose."""
    event_type = event.get("type") or ""
    obj = (event.get("data") or {}).get("object") or {}

    attempt = _find_transaction(obj)
    if attempt is None:
        record.detail = "Aucune tentative correspondante."
        return False
    record.transaction = attempt

    # Un événement peut arriver dans le désordre : un `succeeded` reçu après
    # un `failed` doit l'emporter, l'argent ayant réellement été encaissé.
    if event_type in ("checkout.session.completed", "payment_intent.succeeded"):
        intent = obj.get("payment_intent") or obj.get("id") or ""
        if intent and not attempt.provider_intent_id:
            attempt.provider_intent_id = intent
            attempt.save(update_fields=["provider_intent_id", "updated_at"])
        attempt.mark_succeeded(provider_status=event_type)
        return True

    # Étapes intermédiaires : elles ne créent aucun encaissement, mais les
    # ignorer laisserait un parent devant un statut « en attente » muet
    # alors que sa banque lui demande une authentification.
    if event_type in ("payment_intent.requires_action", "payment_intent.processing"):
        if attempt.is_settled:
            return False
        attempt.status = (
            PaymentTransaction.ACTION_REQUIRED
            if event_type.endswith("requires_action")
            else PaymentTransaction.PROCESSING
        )
        attempt.provider_status = event_type
        attempt.save(update_fields=["status", "provider_status", "updated_at"])
        return True

    if event_type == "payment_intent.canceled":
        if attempt.is_settled:
            return False
        attempt.mark_failed(
            reason="Paiement annulé avant encaissement.",
            provider_status=event_type, status=PaymentTransaction.CANCELLED,
        )
        return True

    if event_type == "payment_intent.payment_failed":
        if attempt.is_settled:
            # Déjà encaissé : un échec arrivé après coup ne doit pas effacer
            # une recette réelle.
            record.detail = "Échec ignoré : la transaction est déjà encaissée."
            return False
        reason = ((obj.get("last_payment_error") or {}).get("message")) or "Paiement refusé."
        attempt.mark_failed(reason=reason, provider_status=event_type)
        return True

    if event_type == "checkout.session.expired":
        if attempt.is_settled:
            return False
        attempt.mark_failed(
            reason="Session expirée avant paiement.",
            provider_status=event_type, status=PaymentTransaction.EXPIRED,
        )
        return True

    if event_type == "charge.refunded":
        refunded = int(obj.get("amount_refunded") or 0)
        delta = refunded - attempt.amount_refunded_minor
        if delta > 0:
            attempt.register_refund(delta)
            return True
        return False

    if event_type.startswith("charge.dispute"):
        attempt.status = PaymentTransaction.DISPUTED
        attempt.save(update_fields=["status", "updated_at"])
        return True

    record.detail = f"Type non géré : {event_type}"
    return False


class RefundCardPaymentView(APIView):
    """
    POST /api/payments/card/<id>/refund/   {"amount": "50.00"}

    Rembourse tout ou partie d'une transaction encaissée. Réservé aux
    administrateurs de l'académie concernée : un parent ne se rembourse pas
    lui-même.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        user = request.user
        if user.role_level < 80:
            return Response(
                {"detail": "Seule l'administration peut rembourser un paiement."},
                status=status.HTTP_403_FORBIDDEN,
            )

        attempt = PaymentTransaction.objects.filter(pk=pk).first()
        if attempt is None:
            return Response({"detail": "Transaction introuvable."},
                            status=status.HTTP_404_NOT_FOUND)

        academy = get_request_school(request)
        if academy is not None and attempt.academy_id != academy.pk:
            return Response(
                {"detail": "Cette transaction appartient à une autre académie."},
                status=status.HTTP_403_FORBIDDEN,
            )
        if academy is None and not user.is_superadmin():
            return Response({"detail": "Académie non déterminée."},
                            status=status.HTTP_403_FORBIDDEN)

        if not attempt.is_settled:
            return Response(
                {"detail": "Seul un paiement encaissé peut être remboursé."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        currency = attempt.academy.currency
        raw = request.data.get("amount")
        amount_minor = (
            currency.to_minor(raw) if raw not in (None, "") else attempt.refundable_minor
        )

        provider = get_provider(attempt.provider)
        hors_ligne = str(request.data.get("rembourse_chez_prestataire", "")).lower() in ("1", "true", "oui")
        if hors_ligne and attempt.provider == "stripe":
            return Response({"detail": "Un paiement Stripe se rembourse depuis FEBA."}, status=status.HTTP_400_BAD_REQUEST)
        if not hors_ligne:
            try:
                provider.refund(attempt, amount_minor)
            except (PaymentProviderError, PaymentProviderNotConfigured) as exc:
                code = status.HTTP_409_CONFLICT if attempt.provider == "fedapay" else status.HTTP_502_BAD_GATEWAY
                return Response({"detail": str(exc)}, status=code)
        logger.info("Remboursement carte %s : %s (%s) par %s", attempt.pk, amount_minor,
                    "constaté hors ligne" if hors_ligne else "via le prestataire", user.pk)

        try:
            refunded = attempt.register_refund(amount_minor)
        except ValidationError as exc:
            return Response({"detail": exc.messages[0]}, status=status.HTTP_400_BAD_REQUEST)

        return Response({
            "transaction_id": attempt.pk,
            "status": attempt.status,
            "refunded_total": refunded.formatted(),
            "remaining": Money(attempt.refundable_minor, attempt.currency).formatted(),
        })


class CardReceiptView(APIView):
    """
    GET /api/payments/card/<id>/receipt/

    Reçu de la transaction. Le reçu est normalement produit dès
    l'encaissement ; cette vue le régénère s'il manque, plutôt que de
    renvoyer un 404 à un parent qui a réellement payé.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        user = request.user
        attempt = PaymentTransaction.objects.filter(pk=pk).first()
        if attempt is None:
            return Response({"detail": "Transaction introuvable."},
                            status=status.HTTP_404_NOT_FOUND)

        # Anti-IDOR : l'appartenance est vérifiée sur l'ÉLÈVE, pas sur
        # l'identifiant fourni. Un parent qui incrémente le numéro dans
        # l'URL tombe sur un 404, jamais sur le reçu d'un autre foyer.
        if user.role_level < 80:
            if not _visible_students(user).filter(pk=attempt.student_id).exists():
                return Response({"detail": "Transaction introuvable."},
                                status=status.HTTP_404_NOT_FOUND)
        else:
            academy = get_request_school(request)
            if academy is not None and attempt.academy_id != academy.pk:
                return Response({"detail": "Transaction introuvable."},
                                status=status.HTTP_404_NOT_FOUND)

        if not attempt.is_settled or attempt.payment_id is None:
            return Response(
                {"detail": "Aucun reçu : ce paiement n'a pas été encaissé."},
                status=status.HTTP_409_CONFLICT,
            )

        payment = attempt.payment
        if not payment.receipt_file:
            from apps.payments.pdf_generator import generate_receipt

            payment = generate_receipt(payment)

        return Response({
            "transaction_id": attempt.pk,
            "payment_id": payment.pk,
            "reference": payment.reference_number,
            "amount_display": payment.formatted_amount,
            "currency": payment.currency,
            "receipt_url": payment.receipt_file.url if payment.receipt_file else None,
        })


class CardTransactionListView(APIView):
    """
    GET /api/payments/card/

    Journal des tentatives, filtré par académie. Un administrateur FEBA n'y
    voit jamais les transactions de FEBA FHA.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        academy = get_request_school(request)

        queryset = PaymentTransaction.objects.select_related(
            "academy", "student", "payer",
        )
        if academy is not None:
            queryset = queryset.filter(academy=academy)
        elif not user.is_superadmin():
            queryset = queryset.none()

        if user.role_level < 80:
            # Parent ou élève : uniquement ses propres tentatives.
            queryset = queryset.filter(student__in=_visible_students(user))

        status_filter = request.query_params.get("status")
        if status_filter:
            queryset = queryset.filter(status=status_filter)

        return Response([
            {
                "id": tx.pk,
                "academy_code": tx.academy.code,
                "academy_name": tx.academy.name,
                "student": tx.student.get_full_name(),
                "payment_type": tx.payment_type,
                "amount_minor": tx.amount_minor,
                "currency": tx.currency,
                "amount_display": tx.money.formatted(),
                "refunded_display": tx.refunded_money.formatted(),
                "status": tx.status,
                "status_display": tx.get_status_display(),
                "provider": tx.provider,
                "provider_reference": tx.reference,
                "failure_reason": tx.failure_reason,
                "created_at": tx.created_at,
                "succeeded_at": tx.succeeded_at,
                # Fuseau de l'académie : l'écran affiche l'heure locale de
                # la transaction, pas celle du navigateur.
                "academy_timezone": tx.academy.timezone,
                "payment_id": tx.payment_id,
            }
            for tx in queryset[:500]
        ])


# ── FedaPay : webhook, vérification au retour, rapprochement ──────────

def appliquer_etat_prestataire(attempt_pk, etat, origine):
    """
    Applique l'état RELU chez le prestataire (jamais celui annoncé par un navigateur
    ou un événement). Verrou de ligne : webhook, retour du navigateur et rapprochement
    peuvent arriver en même temps ; un seul encaissement est créé.

    Renvoie le statut FEBA obtenu, ou « ecart » si le montant ou la devise diffèrent.
    """
    from apps.core.currency import currency_for

    with db_transaction.atomic():
        attempt = PaymentTransaction.objects.select_for_update().get(pk=attempt_pk)
        provider = get_provider(attempt.provider)
        cible = getattr(provider, "STATUTS", {}).get(etat.get("statut"), "pending")
        brut = f"{origine}:{etat.get('statut')}"
        if cible == "succeeded":
            unite = currency_for(attempt.academy).minor_units_per_unit
            try:
                montant = int(etat.get("montant")) * unite
            except (TypeError, ValueError):
                montant = None
            if montant != attempt.amount_minor or (etat.get("devise") and etat["devise"] != attempt.currency):
                # Montant ou devise falsifiés / incohérents : aucun encaissement, alerte.
                logger.error("Paiement carte %s : écart prestataire (montant %s / attendu %s, devise %s / %s).",
                             attempt.pk, montant, attempt.amount_minor, etat.get("devise"), attempt.currency)
                if not attempt.is_settled:
                    # Jamais d'encaissement sur un montant non conforme : échec explicite, à vérifier
                    # à la main dans le tableau de bord du prestataire (pas « contesté », qui vaut encaissé).
                    attempt.mark_failed(reason="Montant ou devise différents chez le prestataire : vérification manuelle requise.",
                                        provider_status=f"{brut}:ecart")
                return "ecart"
            attempt.mark_succeeded(provider_status=brut)
            return attempt.status
        if cible in ("failed", "cancelled", "expired"):
            if not attempt.is_settled:
                attempt.mark_failed(
                    reason={"failed": "Paiement refusé.", "cancelled": "Paiement abandonné.",
                            "expired": "Paiement expiré."}[cible],
                    provider_status=brut, status=cible)
            return attempt.status
        if cible == "refunded":
            if attempt.is_settled and attempt.refundable_minor > 0:
                attempt.register_refund(attempt.refundable_minor)
            return attempt.status
        if attempt.status in PaymentTransaction.OPEN_STATUSES and attempt.provider_status != brut:
            attempt.provider_status = brut
            attempt.save(update_fields=["provider_status", "updated_at"])
        return attempt.status


@api_view(["POST"])
@authentication_classes([])          # le prestataire n'a pas de session
@permission_classes([AllowAny])      # la SIGNATURE fait l'authentification
def fedapay_webhook(request):
    """
    POST /api/payments/webhook/fedapay/

    Signature vérifiée sur le CORPS BRUT, événement dédoublonné en base, puis la
    transaction est RELUE chez FedaPay : l'événement désigne, il ne prouve pas.
    """
    import hashlib
    provider = get_provider("fedapay")
    try:
        event = provider.verify_webhook(request.body, request.META.get("HTTP_X_FEDAPAY_SIGNATURE", ""))
    except PaymentProviderNotConfigured:
        return Response({"detail": "Webhook non configuré."}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
    except ValidationError:
        logger.warning("Webhook FedaPay refusé : signature invalide.")
        return Response({"detail": "Signature invalide."}, status=status.HTTP_400_BAD_REQUEST)

    nom = event.get("name") or event.get("type") or ""
    entite = event.get("entity") or (event.get("data") or {}).get("object") or {}
    event_id = str(event.get("id") or hashlib.sha256(request.body).hexdigest())
    try:
        with db_transaction.atomic():
            record = WebhookEvent.objects.create(provider="fedapay", event_id=event_id[:255], event_type=nom[:100])
    except IntegrityError:
        return Response({"received": True, "duplicate": True})

    attempt = None
    if entite.get("id"):
        attempt = PaymentTransaction.objects.filter(provider="fedapay", provider_intent_id=str(entite["id"])).first()
    if attempt is None or not nom.startswith("transaction."):
        record.status = WebhookEvent.IGNORED
        record.detail = "Aucune tentative correspondante." if attempt is None else f"Type non géré : {nom}"
        record.processed_at = timezone.now()
        record.save(update_fields=["status", "detail", "processed_at"])
        return Response({"received": True, "handled": False})
    record.transaction = attempt
    try:
        etat = provider.fetch(attempt.provider_intent_id)
        resultat = appliquer_etat_prestataire(attempt.pk, etat, "webhook")
    except PaymentProviderError as exc:
        # Prestataire injoignable : 503 pour que FedaPay rejoue l'événement plus tard.
        logger.warning("Webhook FedaPay %s : vérification impossible (%s), rejeu attendu.", event_id, exc)
        record.delete()      # l'événement rejoué par FedaPay doit pouvoir être traité
        return Response({"detail": "Vérification impossible, réessayez."}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
    record.status = WebhookEvent.PROCESSED
    record.detail = f"Statut appliqué : {resultat}"
    record.processed_at = timezone.now()
    record.save(update_fields=["status", "detail", "processed_at", "transaction"])
    return Response({"received": True, "handled": True})


class VerifierPaiementCarteView(APIView):
    """
    POST /api/payments/card/<id>/verifier/

    Appelé par la page de retour : FEBA interroge le prestataire (serveur à serveur)
    et applique son état. Le navigateur ne constate rien ; il demande une vérification.
    Accès : le payeur, un parent de l'élève, l'administration de l'académie.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        attempt = PaymentTransaction.objects.filter(pk=pk, student__in=_visible_students(request.user)).first()
        if attempt is None:
            return Response({"detail": "Transaction introuvable."}, status=status.HTTP_404_NOT_FOUND)
        if attempt.status in PaymentTransaction.OPEN_STATUSES and attempt.provider_intent_id and attempt.provider != "stripe":
            try:
                appliquer_etat_prestataire(attempt.pk, get_provider(attempt.provider).fetch(attempt.provider_intent_id), "retour")
            except PaymentProviderError as exc:
                return Response({"detail": str(exc), "status": attempt.status}, status=status.HTTP_502_BAD_GATEWAY)
            attempt.refresh_from_db()
        return Response({
            "transaction_id": attempt.pk, "status": attempt.status, "status_display": attempt.get_status_display(),
            "amount_display": attempt.money.formatted(), "payment_id": attempt.payment_id,
            "reason": attempt.failure_reason,
        })


def rapprocher_tentatives(maintenant=None):
    """Tentatives ouvertes : statut relu chez le prestataire, expiration au-delà du délai."""
    from datetime import timedelta
    maintenant = maintenant or timezone.now()
    limite = maintenant - timedelta(hours=settings.CARD_ATTEMPT_EXPIRY_HOURS)
    ouvertes = PaymentTransaction.objects.filter(status__in=PaymentTransaction.OPEN_STATUSES,
                                                 created_at__lte=maintenant - timedelta(minutes=30)).exclude(provider="stripe")
    bilan = {"verifiees": 0, "expirees": 0, "erreurs": 0}
    for attempt in ouvertes[:500]:
        if attempt.provider_intent_id:
            try:
                appliquer_etat_prestataire(attempt.pk, get_provider(attempt.provider).fetch(attempt.provider_intent_id), "rapprochement")
                bilan["verifiees"] += 1
            except PaymentProviderError:
                bilan["erreurs"] += 1
                continue
            attempt.refresh_from_db()
        if attempt.status in PaymentTransaction.OPEN_STATUSES and attempt.created_at <= limite:
            attempt.mark_failed(reason="Paiement non finalisé dans le délai : tentative expirée.",
                                provider_status="rapprochement:expire", status=PaymentTransaction.EXPIRED)
            bilan["expirees"] += 1
    return bilan
