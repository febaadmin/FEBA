from rest_framework import serializers
from .models import Payment, PaymentHistory


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


class PaymentSerializer(serializers.ModelSerializer):
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
        read_only_fields = ["reference_number", "received_by"]

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
