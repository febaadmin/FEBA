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

        return Response({
            "enabled": bool(configured),
            "provider": getattr(provider, "name", settings.PAYMENT_PROVIDER),
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
            pk=request.query_params.get("student"),
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

        student_id = request.data.get("student")
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
        description = f"{student.get_full_name()} — {label}"

        try:
            session_id, checkout_url = provider.create_checkout(
                attempt,
                success_url=settings.STRIPE_SUCCESS_URL,
                cancel_url=settings.STRIPE_CANCEL_URL,
                description=description,
            )
        except PaymentProviderError as exc:
            attempt.mark_failed(reason=str(exc))
            return Response({"detail": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)

        attempt.provider_session_id = session_id or ""
        attempt.provider_metadata = {"checkout_url": checkout_url}
        attempt.status = PaymentTransaction.PENDING
        attempt.save(update_fields=[
            "provider_session_id", "provider_metadata", "status", "updated_at",
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
        logger.error("Webhook refusé — configuration absente : %s", exc)
        return Response({"detail": "Webhook non configuré."},
                        status=status.HTTP_503_SERVICE_UNAVAILABLE)
    except ValidationError as exc:
        # Sans signature valide, l'événement n'est qu'une affirmation :
        # n'importe qui connaissant l'URL pourrait déclarer un paiement.
        logger.warning("Webhook refusé — signature invalide.")
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
        logger.info("Événement %s déjà traité — ignoré.", event_id)
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
        try:
            provider.refund(attempt, amount_minor)
        except (PaymentProviderError, PaymentProviderNotConfigured) as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)

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
                "payment_id": tx.payment_id,
            }
            for tx in queryset[:500]
        ])
