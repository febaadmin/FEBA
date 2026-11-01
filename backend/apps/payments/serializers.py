import datetime
import re

from django.utils import timezone
from rest_framework import serializers
from .models import Payment, PaymentHistory
from apps.core.academy_serializers import (
    ACADEMY_FIELDS, STUDENT_AGE_FIELDS, AcademyMetadataMixin, StudentAgeMixin,
)


class PaymentHistorySerializer(serializers.ModelSerializer):
    performed_by_name = serializers.CharField(
        source="performed_by.get_full_name", read_only=True, default=""
    )
    action_label = serializers.CharField(source="get_action_display", read_only=True)

    class Meta:
        model = PaymentHistory
        fields = [
            "id", "action", "action_label", "performed_by_name",
            "amount_snapshot", "is_confirmed_before", "is_confirmed_after",
            "justification", "notes", "performed_at",
        ]


class MonthField(serializers.Field):
    """
    « Mois concerné » : accepte `AAAA-MM` (champ <input type="month">) ou
    une date complète, stocke le 1er du mois, restitue `AAAA-MM`.
    """

    default_error_messages = {"invalid": "Mois invalide : format attendu AAAA-MM."}

    def to_internal_value(self, data):
        if data in (None, ""):
            return None
        match = re.fullmatch(r"(\d{4})-(\d{2})(?:-\d{2})?", str(data).strip())
        if not match:
            self.fail("invalid")
        year, month = int(match.group(1)), int(match.group(2))
        if not 1 <= month <= 12:
            self.fail("invalid")
        return datetime.date(year, month, 1)

    def to_representation(self, value):
        return value.strftime("%Y-%m") if value else None


class PaymentSerializer(AcademyMetadataMixin, StudentAgeMixin, serializers.ModelSerializer):
    #: Chemin ORM vers l'académie propriétaire de l'objet.
    academy_source = "student.school"

    # ── Devise (P0) ───────────────────────────────────────────────────
    # Le montant seul ne veut rien dire : l'API renvoie systématiquement la
    # devise, son symbole et le montant DÉJÀ FORMATÉ. Sans cela, chaque
    # écran devait deviner l'unité — et se trompait pour FEBA FHA.
    currency = serializers.CharField(read_only=True)
    currency_symbol = serializers.SerializerMethodField()
    amount_display = serializers.SerializerMethodField()

    def get_currency_symbol(self, obj):
        from apps.core.currency import get_currency
        return get_currency(obj.currency).symbol

    def get_amount_display(self, obj):
        return obj.formatted_amount

    student_name = serializers.CharField(source="student.get_full_name", read_only=True)
    student_class = serializers.SerializerMethodField()
    student_matricule = serializers.CharField(source="student.matricule", read_only=True)
    received_by_name = serializers.SerializerMethodField()
    payment_type_label = serializers.CharField(
        source="get_payment_type_display", read_only=True
    )
    payment_method_label = serializers.CharField(
        source="get_payment_method_display", read_only=True
    )
    history = PaymentHistorySerializer(many=True, read_only=True)
    receipt_url = serializers.SerializerMethodField()

    # ── Date ET heure de la transaction (P1) ──────────────────────────
    # Entrée : `payment_time` (HH:MM, heure locale de l'académie). Sortie :
    # `paid_at` (instant UTC ISO), `paid_at_local` (heure murale de
    # l'académie, sans décalage) et `paid_at_display` (« 09/10/2026 14:37 »,
    # format de référence des exports). `has_time` vaut faux quand l'heure
    # n'a jamais été enregistrée : l'écran le dit au lieu d'inventer.
    payment_time = serializers.CharField(write_only=True, required=False, allow_blank=True)
    period_month = MonthField(required=False, allow_null=True)
    paid_at_local = serializers.SerializerMethodField()
    paid_at_display = serializers.SerializerMethodField()
    has_time = serializers.SerializerMethodField()
    academy_timezone = serializers.SerializerMethodField()

    class Meta:
        model = Payment
        fields = "__all__"
        # `currency` et `amount_minor` sont dérivés de l'académie et du
        # montant : les accepter en écriture laisserait un client choisir la
        # monnaie dans laquelle son école facture.
        read_only_fields = [
            "reference_number", "received_by", "currency", "amount_minor",
            "paid_at", "paid_at_source",
            # Ces états ont leurs actions (annuler, supprimer, restaurer, reçu),
            # qui exigent une justification et écrivent l'historique.
            "is_confirmed", "is_deleted", "deleted_at", "deleted_by",
            "receipt_file", "enrollment",
        ]

    def validate_amount(self, value):
        if value is None or value <= 0:
            raise serializers.ValidationError(
                "Le montant doit être strictement positif."
            )
        return value

    def validate_payment_date(self, value):
        # Le contrôle « pas dans le futur » est fait dans `validate()`, dans
        # le fuseau de L'ACADÉMIE : comparé à la date du serveur, un
        # paiement saisi à 20 h à New York (déjà le lendemain à Cotonou)
        # était accepté, et un paiement du jour même pouvait être refusé.
        return value

    def validate_payment_time(self, value):
        value = (value or "").strip()
        if not value:
            return ""
        if not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d(:[0-5]\d)?", value):
            raise serializers.ValidationError("Heure invalide : format attendu HH:MM.")
        return value[:5]

    def validate_student(self, value):
        """
        FAILLE CORRIGÉE : le champ acceptait N'IMPORTE QUEL élève. Un
        administrateur d'une académie pouvait enregistrer un paiement — et
        déclencher des notifications — sur un élève d'une autre académie
        en envoyant son identifiant.
        """
        from apps.core.tenancy import get_request_school

        request = self.context.get("request")
        if request is None or value is None:
            return value
        school = get_request_school(request)
        if school is not None and value.school_id != school.id:
            raise serializers.ValidationError(
                "Cet élève appartient à un autre établissement."
            )
        return value

    def validate(self, attrs):
        from apps.core.age import academy_today
        from zoneinfo import ZoneInfo

        attrs = super().validate(attrs)
        student = attrs.get("student") or getattr(self.instance, "student", None)
        academy = getattr(student, "school", None)

        school_year = attrs.get("school_year")
        if school_year is not None and student is not None and school_year.school_id != student.school_id:
            raise serializers.ValidationError({
                "school_year": "Cette année scolaire appartient à un autre établissement.",
            })

        payment_time = attrs.pop("payment_time", "")
        date_given = "payment_date" in attrs
        pay_date = attrs.get("payment_date") or getattr(self.instance, "payment_date", None)
        if pay_date is None:
            pay_date = academy_today(academy)
            attrs["payment_date"] = pay_date
        today = academy_today(academy)
        if pay_date > today:
            raise serializers.ValidationError({
                "payment_date": "La date de paiement ne peut pas être dans le futur.",
            })

        tz_name = getattr(academy, "timezone", None) or None
        try:
            zone = ZoneInfo(tz_name) if tz_name else timezone.get_current_timezone()
        except Exception:
            zone = timezone.get_current_timezone()

        if payment_time:
            hours, minutes = (int(x) for x in payment_time.split(":")[:2])
            local = datetime.datetime.combine(pay_date, datetime.time(hours, minutes), tzinfo=zone)
            if local > timezone.now().astimezone(zone):
                raise serializers.ValidationError({
                    "payment_time": "L'heure de paiement ne peut pas être dans le futur.",
                })
            attrs["paid_at"] = local
            attrs["paid_at_source"] = Payment.PAID_AT_RECORDED
        elif self.instance is None and pay_date == today:
            # Encaissement saisi le jour même, sans heure précisée : l'heure
            # réelle est celle de l'enregistrement.
            attrs["paid_at"] = timezone.now()
            attrs["paid_at_source"] = Payment.PAID_AT_RECORDED
        elif self.instance is not None and date_given and pay_date != self.instance.payment_date:
            # La date change sans heure : l'ancienne heure ne correspond plus
            # à rien — on ne la garde pas collée à un autre jour.
            attrs["paid_at"] = None
            attrs["paid_at_source"] = ""
        return attrs

    def get_paid_at_local(self, obj):
        local = obj.local_paid_at()
        return local.strftime("%Y-%m-%dT%H:%M") if local else None

    def get_paid_at_display(self, obj):
        local = obj.local_paid_at()
        if local is not None:
            return local.strftime("%d/%m/%Y %H:%M")
        return obj.payment_date.strftime("%d/%m/%Y") if obj.payment_date else ""

    def get_has_time(self, obj):
        return obj.paid_at is not None

    def get_academy_timezone(self, obj):
        return obj.academy_timezone

    def get_student_class(self, obj):
        if obj.student.current_class:
            return obj.student.current_class.name
        return "-"

    def get_received_by_name(self, obj):
        return obj.received_by.get_full_name() if obj.received_by else ""

    def get_receipt_url(self, obj):
        if obj.receipt_file:
            request = self.context.get("request")
            if request:
                return obj.receipt_file.url
            return obj.receipt_file.url
        return None
