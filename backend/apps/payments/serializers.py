from rest_framework import serializers
from .models import Payment, PaymentHistory
from apps.core.academy_serializers import ACADEMY_FIELDS, AcademyMetadataMixin


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


class PaymentSerializer(AcademyMetadataMixin, serializers.ModelSerializer):
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

    class Meta:
        model = Payment
        fields = "__all__"
        # `currency` et `amount_minor` sont dérivés de l'académie et du
        # montant : les accepter en écriture laisserait un client choisir la
        # monnaie dans laquelle son école facture.
        read_only_fields = ["reference_number", "received_by", "currency", "amount_minor"]

    def validate_amount(self, value):
        if value is None or value <= 0:
            raise serializers.ValidationError(
                "Le montant doit être strictement positif."
            )
        return value

    def validate_payment_date(self, value):
        from django.utils import timezone
        if value and value > timezone.localdate():
            raise serializers.ValidationError(
                "La date de paiement ne peut pas être dans le futur."
            )
        return value

    def get_student_class(self, obj):
        if obj.student.current_class:
            return obj.student.current_class.name
        return "—"

    def get_received_by_name(self, obj):
        return obj.received_by.get_full_name() if obj.received_by else ""

    def get_receipt_url(self, obj):
        if obj.receipt_file:
            request = self.context.get("request")
            if request:
                return obj.receipt_file.url
            return obj.receipt_file.url
        return None
