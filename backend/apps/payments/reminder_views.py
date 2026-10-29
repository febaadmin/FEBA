"""
apps/payments/reminder_views.py — Administration des échéanciers et relances.

    /api/payments/fee-schedules/             tarifs + échéances (CRUD)
    /api/payments/fee-arrangements/          abonnements, exonérations, réductions
    /api/payments/reminders/status/          état du service (dégradé ou non, et pourquoi)
    /api/payments/reminders/policy/          règles de relance de l'académie
    /api/payments/reminders/preview/         simulation : échéances, montants, relances prévues
    /api/payments/reminders/run/             lancement manuel (réel)
    /api/payments/reminders/history/         relances produites
    /api/payments/reminders/runs/            exécutions du moteur

Toutes les routes : administrateur de l'académie, ou super-administrateur
sur une académie explicitement choisie. Tout objet lié (élève, année,
niveau, tarif) est revalidé dans le périmètre de l'académie.
"""
from datetime import timedelta
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_date
from rest_framework import serializers, status, viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsAdminOrAbove
from apps.core.age import academy_today
from apps.core.currency import Money, get_currency
from apps.notifications.campaign_views import resolve_academy
from apps.notifications.mailer import provider_is_configured

from .models import (
    FeeInstallment, FeeSchedule, Payment, PaymentReminder, PaymentReminderPolicy,
    ReminderRun, StudentFeeArrangement,
)
from .reminders import (
    STATUS_LABELS, reminders_globally_enabled, run_reminders, type_label,
)


def _to_minor(value, currency_code, field):
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError):
        raise ValidationError({field: "Montant invalide."})
    if amount < 0:
        raise ValidationError({field: "Le montant ne peut pas être négatif."})
    return get_currency(currency_code).to_minor(amount)


def _from_minor(minor, currency_code):
    return str(get_currency(currency_code).to_decimal(minor))


class AcademyScopedMixin:
    permission_classes = [IsAuthenticated, IsAdminOrAbove]

    def academy(self):
        if not hasattr(self, "_academy"):
            self._academy = resolve_academy(self.request)
        return self._academy


# ── Échéanciers ───────────────────────────────────────────────────────

class InstallmentSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(required=False)
    amount = serializers.CharField(write_only=True)
    amount_value = serializers.SerializerMethodField()
    amount_display = serializers.SerializerMethodField()

    class Meta:
        model = FeeInstallment
        fields = ["id", "label", "due_date", "amount", "amount_value", "amount_display", "order"]

    def get_amount_value(self, obj):
        return _from_minor(obj.amount_minor, obj.fee_schedule.currency)

    def get_amount_display(self, obj):
        return Money(obj.amount_minor, obj.fee_schedule.currency).formatted()


class FeeScheduleSerializer(serializers.ModelSerializer):
    amount = serializers.CharField(write_only=True)
    amount_value = serializers.SerializerMethodField()
    amount_display = serializers.SerializerMethodField()
    installments = InstallmentSerializer(many=True, required=False)
    installments_total_display = serializers.SerializerMethodField()
    is_consistent = serializers.SerializerMethodField()
    payment_type_label = serializers.SerializerMethodField()
    school_year_name = serializers.CharField(source="school_year.name", read_only=True, default=None)
    level_name = serializers.CharField(source="level.name", read_only=True, default=None)

    class Meta:
        model = FeeSchedule
        fields = [
            "id", "payment_type", "payment_type_label", "label", "school_year", "school_year_name",
            "level", "level_name", "amount", "amount_value", "amount_display", "currency",
            "is_active", "is_mandatory", "installment_mode", "installments",
            "installments_total_display", "is_consistent",
        ]
        read_only_fields = ["currency"]

    def get_amount_value(self, obj):
        return _from_minor(obj.amount_minor, obj.currency)

    def get_amount_display(self, obj):
        return obj.money.formatted()

    def get_payment_type_label(self, obj):
        return type_label(obj.payment_type)

    def get_installments_total_display(self, obj):
        return Money(sum(i.amount_minor for i in obj.installments.all()), obj.currency).formatted()

    def get_is_consistent(self, obj):
        if obj.installment_mode != FeeSchedule.INSTALLMENTS_SPLIT or not obj.installments.all():
            return True
        return sum(i.amount_minor for i in obj.installments.all()) == obj.amount_minor

    def validate_payment_type(self, value):
        if value not in dict(Payment.PAYMENT_TYPES):
            raise serializers.ValidationError("Type de frais inconnu.")
        return value

    def validate(self, attrs):
        academy = self.context["academy"]
        for field in ("school_year", "level"):
            obj = attrs.get(field)
            if obj is not None and obj.school_id != academy.pk:
                raise serializers.ValidationError({field: "Appartient à une autre académie."})
        return attrs

    def _save_installments(self, fee, rows):
        keep = []
        existing = {i.pk: i for i in fee.installments.all()}
        for index, row in enumerate(rows):
            minor = _to_minor(row.get("amount"), fee.currency, "installments")
            inst = existing.get(row.get("id")) or FeeInstallment(fee_schedule=fee)
            inst.label = row["label"]
            inst.due_date = row["due_date"]
            inst.amount_minor = minor
            inst.order = row.get("order", index)
            try:
                inst.save()
            except Exception as exc:  # contrainte de validation lisible
                raise ValidationError({"installments": [str(exc)]})
            keep.append(inst.pk)
        fee.installments.exclude(pk__in=keep).delete()

    @transaction.atomic
    def create(self, validated):
        rows = validated.pop("installments", [])
        academy = self.context["academy"]
        amount = validated.pop("amount")
        fee = FeeSchedule(academy=academy, **validated)
        fee.amount_minor = _to_minor(amount, academy.currency_code, "amount")
        try:
            fee.save()
        except Exception as exc:
            raise ValidationError({"non_field_errors": [str(exc)]})
        self._save_installments(fee, rows)
        return fee

    @transaction.atomic
    def update(self, fee, validated):
        rows = validated.pop("installments", None)
        if "amount" in validated:
            fee.amount_minor = _to_minor(validated.pop("amount"), fee.academy.currency_code, "amount")
        for key, value in validated.items():
            setattr(fee, key, value)
        try:
            fee.save()
        except Exception as exc:
            raise ValidationError({"non_field_errors": [str(exc)]})
        if rows is not None:
            self._save_installments(fee, rows)
        return fee


class FeeScheduleViewSet(AcademyScopedMixin, viewsets.ModelViewSet):
    serializer_class = FeeScheduleSerializer
    pagination_class = None
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_queryset(self):
        return (
            FeeSchedule.objects.filter(academy=self.academy())
            .select_related("school_year", "level").prefetch_related("installments")
            .order_by("payment_type", "level__order", "pk")
        )

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["academy"] = self.academy()
        return ctx


class ArrangementSerializer(serializers.ModelSerializer):
    discount = serializers.CharField(write_only=True, required=False, allow_blank=True)
    discount_display = serializers.SerializerMethodField()
    student_name = serializers.CharField(source="student.get_full_name", read_only=True)
    fee_label = serializers.SerializerMethodField()
    kind_label = serializers.CharField(source="get_kind_display", read_only=True)

    class Meta:
        model = StudentFeeArrangement
        fields = ["id", "student", "student_name", "fee_schedule", "fee_label", "kind", "kind_label",
                  "discount", "discount_display", "start_date", "end_date", "reason", "created_at"]

    def get_discount_display(self, obj):
        return Money(obj.discount_minor, obj.fee_schedule.currency).formatted() if obj.discount_minor else ""

    def get_fee_label(self, obj):
        return obj.fee_schedule.label or type_label(obj.fee_schedule.payment_type)

    def validate(self, attrs):
        academy = self.context["academy"]
        student = attrs.get("student") or getattr(self.instance, "student", None)
        fee = attrs.get("fee_schedule") or getattr(self.instance, "fee_schedule", None)
        if student is not None and student.school_id != academy.pk:
            raise serializers.ValidationError({"student": "Élève d'une autre académie."})
        if fee is not None and fee.academy_id != academy.pk:
            raise serializers.ValidationError({"fee_schedule": "Tarif d'une autre académie."})
        return attrs

    def _apply(self, instance, validated):
        discount = validated.pop("discount", None)
        for key, value in validated.items():
            setattr(instance, key, value)
        if discount not in (None, ""):
            instance.discount_minor = _to_minor(discount, instance.fee_schedule.currency, "discount")
        elif instance.kind != StudentFeeArrangement.DISCOUNT:
            instance.discount_minor = 0
        try:
            instance.save()
        except Exception as exc:
            raise ValidationError({"non_field_errors": [str(exc)]})
        return instance

    def create(self, validated):
        return self._apply(StudentFeeArrangement(created_by=self.context["request"].user), validated)

    def update(self, instance, validated):
        return self._apply(instance, validated)


class ArrangementViewSet(AcademyScopedMixin, viewsets.ModelViewSet):
    serializer_class = ArrangementSerializer
    pagination_class = None
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_queryset(self):
        qs = (
            StudentFeeArrangement.objects.filter(fee_schedule__academy=self.academy())
            .select_related("student", "fee_schedule")
        )
        fee = self.request.query_params.get("fee_schedule")
        if fee:
            qs = qs.filter(fee_schedule_id=fee)
        return qs.order_by("student__last_name", "student__first_name")

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["academy"] = self.academy()
        return ctx


# ── Relances ──────────────────────────────────────────────────────────

class PolicySerializer(serializers.ModelSerializer):
    min_amount = serializers.CharField(write_only=True, required=False)
    min_amount_value = serializers.SerializerMethodField()

    class Meta:
        model = PaymentReminderPolicy
        fields = ["enabled", "grace_days", "interval_days", "max_reminders", "min_amount",
                  "min_amount_value", "send_email", "send_notification", "payment_instructions",
                  "contact_text", "paused_reason", "updated_at"]

    def get_min_amount_value(self, obj):
        return _from_minor(obj.min_amount_minor, obj.academy.currency_code)

    def validate(self, attrs):
        if "max_reminders" in attrs and attrs["max_reminders"] < 1:
            raise serializers.ValidationError({"max_reminders": "Au moins une relance."})
        if "interval_days" in attrs and attrs["interval_days"] < 1:
            raise serializers.ValidationError({"interval_days": "Au moins un jour."})
        return attrs

    def update(self, instance, validated):
        min_amount = validated.pop("min_amount", None)
        if min_amount not in (None, ""):
            instance.min_amount_minor = max(_to_minor(min_amount, instance.academy.currency_code, "min_amount"), 1)
        for key, value in validated.items():
            setattr(instance, key, value)
        instance.updated_by = self.context["request"].user
        instance.save()
        return instance


def _run_payload(run):
    if run is None:
        return None
    return {
        "id": run.pk, "trigger": run.trigger, "trigger_display": run.get_trigger_display(),
        "status": run.status, "status_display": run.get_status_display(),
        "reference_date": run.reference_date, "started_at": run.started_at,
        "finished_at": run.finished_at, "stats": run.stats, "error": run.error,
        "triggered_by": getattr(run.triggered_by, "email", None),
    }


class ReminderStatusView(AcademyScopedMixin, APIView):
    def get(self, request):
        academy = self.academy()
        policy = PaymentReminderPolicy.objects.filter(academy=academy).first()
        last_beat = ReminderRun.objects.filter(academy=academy, trigger=ReminderRun.TRIGGER_BEAT).first()
        last_real = ReminderRun.objects.filter(
            academy=academy, trigger__in=[ReminderRun.TRIGGER_BEAT, ReminderRun.TRIGGER_MANUAL],
        ).exclude(status=ReminderRun.SKIPPED).first()
        issues = []
        if not reminders_globally_enabled():
            issues.append("Interrupteur global désactivé (PAYMENT_REMINDERS_ENABLED=False sur le serveur) : "
                          "aucune relance réelle ne peut partir.")
        if policy is None or not policy.enabled:
            issues.append("Relances automatiques désactivées pour cette académie.")
        if not provider_is_configured():
            issues.append("Aucun serveur SMTP réel configuré : les e-mails ne partiront pas sur Internet.")
        if last_beat is None:
            issues.append("Aucune exécution planifiée enregistrée : vérifiez que Celery Beat et le worker tournent.")
        elif timezone.now() - last_beat.started_at > timedelta(hours=26):
            issues.append("Dernière exécution planifiée il y a plus de 26 h : Celery Beat semble arrêté.")
        if not FeeInstallment.objects.filter(fee_schedule__academy=academy, fee_schedule__is_active=True).exists():
            issues.append("Aucun échéancier configuré : rien ne peut être en retard.")
        since = timezone.now() - timedelta(days=30)
        counts = {}
        for row in PaymentReminder.objects.filter(academy=academy, created_at__gte=since).values("status"):
            counts[row["status"]] = counts.get(row["status"], 0) + 1
        return Response({
            "academy": {"id": academy.pk, "code": academy.code, "name": academy.name},
            "operational": not issues,
            "issues": issues,
            "global_enabled": reminders_globally_enabled(),
            "policy_enabled": bool(policy and policy.enabled),
            "smtp_configured": provider_is_configured(),
            "last_beat_run": _run_payload(last_beat),
            "last_run": _run_payload(last_real),
            "last_30_days": counts,
            "today": academy_today(academy),
        })


class ReminderPolicyView(AcademyScopedMixin, APIView):
    def get(self, request):
        policy = PaymentReminderPolicy.objects.get_or_create(academy=self.academy())[0]
        return Response(PolicySerializer(policy).data)

    def patch(self, request):
        policy = PaymentReminderPolicy.objects.get_or_create(academy=self.academy())[0]
        serializer = PolicySerializer(policy, data=request.data, partial=True, context={"request": request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class ReminderPreviewView(AcademyScopedMixin, APIView):
    """Simulation : ne crée aucune relance, n'envoie rien."""

    def get(self, request):
        academy = self.academy()
        on = request.query_params.get("on")
        on_date = parse_date(on) if on else None
        if on and on_date is None:
            raise ValidationError({"on": "Date invalide : AAAA-MM-JJ."})
        run = run_reminders(academy, trigger=ReminderRun.TRIGGER_DRY_RUN, user=request.user,
                            on_date=on_date, dry_run=True)
        if run.status == ReminderRun.FAILED:
            return Response({"detail": run.error}, status=500)
        planned = {}
        for entry in run.plan:
            key = (entry["item"].installment.pk, entry["item"].student.pk)
            planned.setdefault(key, []).append({
                "recipient": entry["recipient"].get_full_name() or entry["recipient"].email,
                "email": entry["recipient"].email, "level": entry["level"],
            })
        show_all = request.query_params.get("all") == "1"
        items = []
        for item in run.computation.items:
            if not show_all and item.status not in ("overdue", "partial"):
                continue
            row = item.as_dict()
            row["planned_reminders"] = planned.get((item.installment.pk, item.student.pk), [])
            items.append(row)
        items.sort(key=lambda r: (r["due_date"], r["student_name"]))
        return Response({
            "reference_date": run.reference_date,
            "items": items,
            "anomalies": run.computation.anomalies,
            "planned_count": len(run.plan),
            "status_labels": STATUS_LABELS,
            "global_enabled": reminders_globally_enabled(),
        })


class ReminderRunView(AcademyScopedMixin, APIView):
    """Lancement MANUEL réel : confirmation explicite et interrupteur global requis."""

    def post(self, request):
        academy = self.academy()
        if request.data.get("confirm") is not True:
            raise ValidationError({"confirm": "Confirmation explicite requise."})
        if not reminders_globally_enabled():
            return Response({
                "detail": "Envoi réel impossible : l'interrupteur global PAYMENT_REMINDERS_ENABLED est "
                          "désactivé sur ce serveur. Utilisez la simulation.",
            }, status=status.HTTP_409_CONFLICT)
        from .tasks import run_payment_reminders_for

        try:
            run_payment_reminders_for.delay(academy.pk, request.user.pk)
        except Exception as exc:
            return Response({
                "detail": f"File d'attente indisponible (Redis/Celery) : {exc}. Rien n'a été envoyé.",
            }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        return Response({"queued": True}, status=status.HTTP_202_ACCEPTED)


class ReminderHistoryView(AcademyScopedMixin, APIView):
    def get(self, request):
        qs = (
            PaymentReminder.objects.filter(academy=self.academy())
            .select_related("student", "recipient", "email_delivery")
            .order_by("-created_at")
        )
        wanted = request.query_params.get("status")
        if wanted:
            qs = qs.filter(status=wanted)
        rows = []
        for r in qs[:500]:
            rows.append({
                "id": r.pk, "created_at": r.created_at, "student": r.student.get_full_name(),
                "recipient": r.recipient.get_full_name() or r.recipient.email, "email_to": r.email_to,
                "fee_label": r.fee_label, "installment_label": r.installment_label,
                "due_date": r.due_date, "level": r.level,
                "amount_due_display": Money(r.amount_due_minor, r.currency).formatted(),
                "status": r.status, "status_display": r.get_status_display(), "error": r.error,
                "used_real_provider": bool(r.email_delivery and r.email_delivery.used_real_provider),
            })
        return Response({"results": rows})


class ReminderRunsView(AcademyScopedMixin, APIView):
    def get(self, request):
        runs = ReminderRun.objects.filter(academy=self.academy()).select_related("triggered_by")[:50]
        return Response({"results": [_run_payload(r) for r in runs]})
