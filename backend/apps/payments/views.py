from feba_project.bulk_delete import BulkDeleteMixin
"""
Payments views — v29 (multi-tenant)

FIX SÉCURITÉ CRITIQUE (v29) :
  - get_queryset() ne filtrait par AUCUN établissement : un admin/
    comptable voyait l'ensemble des paiements de TOUS les clients
    SaaS (données financières — la fuite la plus grave de tout
    l'audit). Corrigé par filtrage systématique par tenant.
  - restore() utilisait Payment.objects.get(pk=pk) en contournant
    get_queryset() — un admin pouvait restaurer un paiement annulé
    appartenant à un AUTRE établissement en devinant son ID. Corrigé
    pour passer par self.get_object() (donc par le filtrage tenant).
  - Lien vers l'inscription annuelle (enrollment) à la création.

Corrections v9 conservées :
  - Soft delete: destroy() sets is_deleted=True with audit log
  - restore() action: POST /api/payments/{id}/restore/
  - get_queryset: excludes is_deleted=True by default (unless ?show_deleted=1)
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Sum
from django.utils import timezone
from apps.accounts.permissions import IsAdminOrAbove
from apps.core.tenancy import get_request_school, IsSameTenant
from .models import Payment, PaymentHistory
from .serializers import PaymentSerializer, PaymentHistorySerializer
import logging

logger = logging.getLogger("apps")


def _log_payment_action(payment, action, performed_by, justification="", notes="",
                         is_confirmed_before=None, is_confirmed_after=None):
    PaymentHistory.objects.create(
        payment=payment,
        action=action,
        performed_by=performed_by,
        amount_snapshot=payment.amount,
        is_confirmed_before=is_confirmed_before,
        is_confirmed_after=is_confirmed_after,
        justification=justification,
        notes=notes,
    )


class PaymentViewSet(BulkDeleteMixin, viewsets.ModelViewSet):
    serializer_class = PaymentSerializer
    permission_classes = [IsAuthenticated, IsSameTenant]
    filterset_fields = ["student", "school_year", "payment_type", "payment_method", "is_confirmed"]
    search_fields = ["reference_number", "student__first_name", "student__last_name"]
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]
    tenant_lookup = "student__school"

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["request"] = self.request
        return ctx

    def get_queryset(self):
        user = self.request.user
        school = get_request_school(self.request)
        show_deleted = self.request.query_params.get("show_deleted", "0") == "1"
        qs = Payment.objects.select_related(
            "student__current_class", "school_year", "received_by"
        ).prefetch_related("history__performed_by")

        # --- Isolation multi-tenant (FIX CRITIQUE v29) ----------------------
        # Avant ce correctif, cette méthode ne filtrait par AUCUN
        # établissement : n'importe quel admin voyait les paiements de
        # TOUS les clients de la plateforme. C'est la faille la plus
        # grave identifiée dans tout l'audit (données financières).
        if school is not None:
            qs = qs.filter(student__school=school)
        elif not user.is_superadmin():
            return qs.none()

        if not show_deleted:
            qs = qs.filter(is_deleted=False)

        # FIX: Default to current active year to avoid inactive year data leaking
        if not self.request.query_params.get("school_year") and self.request.query_params.get("all_years") != "1":
            from apps.core.tenancy import current_school_years
            current_years = current_school_years(school)
            if current_years.exists():
                qs = qs.filter(school_year__in=current_years)

        if user.role_level >= 80:
            return qs
        # BUG FIX: exclude payments for inactive students
        qs = qs.filter(student__is_active=True, student__user__is_active=True)
        if user.is_parent():
            return qs.filter(student__parents__parent__user=user)
        elif user.is_student():
            try:
                return qs.filter(student__user=user)
            except Exception:
                return qs.none()
        return qs.none()

    def get_permissions(self):
        if self.action in ["create", "update", "partial_update", "destroy", "restore", "cancel", "generate_receipt"]:
            return [IsAuthenticated(), IsAdminOrAbove()]
        return super().get_permissions()

    def perform_create(self, serializer):
        # Auto-assign active school year if not provided — prevents payments
        # from disappearing behind the active-year filter.
        from apps.students.services import get_or_create_enrollment

        school = get_request_school(self.request)
        extra_kwargs = {"received_by": self.request.user}
        school_year = serializer.validated_data.get("school_year")
        if not school_year:
            from apps.schools.models import SchoolYear
            school_year = SchoolYear.objects.filter(school=school, is_current=True).first()
            if school_year:
                extra_kwargs["school_year"] = school_year

        student = serializer.validated_data.get("student")
        if student and school_year:
            enrollment, _ = get_or_create_enrollment(student, school_year.id)
            extra_kwargs["enrollment"] = enrollment

        payment = serializer.save(**extra_kwargs)
        _log_payment_action(
            payment=payment,
            action="create",
            performed_by=self.request.user,
            notes=f"Création paiement {payment.reference_number}",
            is_confirmed_before=None,
            is_confirmed_after=payment.is_confirmed,
        )
        try:
            from apps.notifications.utils import create_notification, notification_path
            if payment.student.user:
                create_notification(
                    payment.student.user, "payment",
                    # V8 — « FCFA » était codé en dur : un parent de FEBA
                    # French Heritage Academy recevait « 125.50 FCFA » pour
                    # un paiement de 125,50 $.
                    f"Paiement enregistré : {payment.formatted_amount}",
                    f"Référence {payment.reference_number} — {payment.get_payment_type_display()}",
                    related_url=notification_path(payment.student.user, "payments"),
                )
            # FIX (notifications) : les paiements concernent au premier chef
            # les parents (ce sont eux qui paient) — ils n'étaient jamais
            # notifiés.
            for ps in payment.student.parents.select_related("parent__user").all():
                create_notification(
                    ps.parent.user, "payment",
                    f"Paiement enregistré pour {payment.student.get_full_name()} : "
                    f"{payment.formatted_amount}",
                    f"Référence {payment.reference_number} — {payment.get_payment_type_display()}",
                    related_url=notification_path(ps.parent.user, "payments"),
                )
        except Exception as exc:
            logger.warning("Erreur non bloquante ignorée : %s", exc, exc_info=True)
    def destroy(self, request, *args, **kwargs):
        """Soft delete — keeps data, logs action."""
        instance = self.get_object()
        if instance.is_deleted:
            return Response({"detail": "Déjà supprimé."}, status=status.HTTP_400_BAD_REQUEST)
        _log_payment_action(
            payment=instance,
            action="cancel",
            performed_by=request.user,
            justification=request.data.get("justification", "Suppression administrative"),
            notes=f"Soft delete: {instance.reference_number}",
            is_confirmed_before=instance.is_confirmed,
            is_confirmed_after=False,
        )
        instance.is_deleted = True
        instance.deleted_at = timezone.now()
        instance.deleted_by = request.user
        instance.is_confirmed = False
        instance.save(update_fields=["is_deleted", "deleted_at", "deleted_by", "is_confirmed"])
        logger.info(f"Payment soft-deleted: {instance.reference_number} by {request.user.email}")
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["post"])
    def restore(self, request, pk=None):
        """
        POST /api/payments/{id}/restore/ — restore a soft-deleted payment.
        FIX SÉCURITÉ (v29) : self.get_object() (et non plus
        Payment.objects.get(pk=pk)) pour bénéficier du filtrage tenant
        de get_queryset() — sinon un admin pouvait restaurer un
        paiement d'un AUTRE établissement en devinant son ID.
        """
        payment = self.get_object()
        if not payment.is_deleted:
            return Response({"detail": "Ce paiement n'est pas supprimé."}, status=400)
        payment.is_deleted = False
        payment.deleted_at = None
        payment.deleted_by = None
        payment.is_confirmed = True
        payment.save(update_fields=["is_deleted", "deleted_at", "deleted_by", "is_confirmed"])
        _log_payment_action(payment, "update", request.user, justification="Restauration du paiement")
        return Response(PaymentSerializer(payment, context={"request": request}).data)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        """POST /api/payments/{id}/cancel/ — annulation avec justification."""
        payment = self.get_object()
        justification = request.data.get("justification", "").strip()
        if not justification:
            return Response({"error": "Une justification est obligatoire pour annuler un paiement."}, status=400)
        _log_payment_action(
            payment=payment,
            action="cancel",
            performed_by=request.user,
            justification=justification,
            is_confirmed_before=payment.is_confirmed,
            is_confirmed_after=False,
        )
        payment.is_confirmed = False
        payment.save(update_fields=["is_confirmed"])
        return Response(PaymentSerializer(payment, context={"request": request}).data)

    @action(detail=True, methods=["get"])
    def history(self, request, pk=None):
        payment = self.get_object()
        return Response(PaymentHistorySerializer(payment.history.all(), many=True).data)

    @action(detail=True, methods=["post"], url_path="generate-receipt")
    def generate_receipt(self, request, pk=None):
        payment = self.get_object()
        try:
            from apps.payments.pdf_generator import generate_receipt
            payment = generate_receipt(payment)
            _log_payment_action(
                payment=payment,
                action="receipt",
                performed_by=request.user,
                notes="Reçu PDF généré",
            )
            url = None
            if payment.receipt_file:
                url = payment.receipt_file.url
            return Response({**PaymentSerializer(payment, context={"request": request}).data, "receipt_url": url})
        except Exception as e:
            logger.error(f"Receipt generation error: {e}", exc_info=True)
            return Response({"error": str(e)}, status=500)

    @action(detail=False, methods=["get"])
    def summary(self, request):
        qs = self.get_queryset().filter(is_confirmed=True)
        total = qs.aggregate(t=Sum("amount"))["t"] or 0
        by_type = {}
        for pt, _ in Payment.PAYMENT_TYPES:
            s = qs.filter(payment_type=pt).aggregate(t=Sum("amount"))["t"] or 0
            by_type[pt] = float(s)
        return Response({"total": float(total), "by_type": by_type, "count": qs.count()})

    @action(detail=False, methods=["get"])
    def pending(self, request):
        qs = self.get_queryset().filter(is_confirmed=False, is_deleted=False)
        return Response(PaymentSerializer(qs, many=True, context={"request": request}).data)
