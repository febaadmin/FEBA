"""Sérialisation des rapports mensuels."""
from rest_framework import serializers

from .models import MonthlyReportAttempt, MonthlyStudentReport


class MonthlyReportAttemptSerializer(serializers.ModelSerializer):
    triggered_by_name = serializers.CharField(
        source="triggered_by.get_full_name", read_only=True, default="")

    class Meta:
        model = MonthlyReportAttempt
        fields = "__all__"


class MonthlyReportListSerializer(serializers.ModelSerializer):
    student_name = serializers.SerializerMethodField()
    academy_code = serializers.CharField(source="academy.code", read_only=True)
    academy_name = serializers.CharField(source="academy.name", read_only=True)
    status_display = serializers.CharField(source="get_status_display",
                                           read_only=True)
    period_label = serializers.SerializerMethodField()
    #: L'état RÉEL du fichier, constaté sur le disque. Un booléen calculé
    #: côté écran à partir de `pdf_path` dirait « oui » pour un fichier
    #: effacé.
    pdf_available = serializers.SerializerMethodField()
    #: La seule affirmation honnête sur l'envoi : un fournisseur externe
    #: a-t-il accepté le message ? Le statut seul ne le dit pas.
    really_sent = serializers.BooleanField(read_only=True)
    is_editable = serializers.BooleanField(read_only=True)

    class Meta:
        model = MonthlyStudentReport
        fields = [
            "id", "reference", "student", "student_name", "academy",
            "academy_code", "academy_name", "year", "month", "period_label",
            "school_year", "version", "status", "status_display",
            "generated_at", "scheduled_at", "sent_at", "recipients",
            "attempts_count", "last_attempt_at", "last_error",
            "provider_message_id", "pdf_sha256", "pdf_available",
            "really_sent", "is_editable", "archived_at", "created_at",
            "updated_at",
        ]

    def get_student_name(self, obj):
        return f"{obj.student.first_name} {obj.student.last_name}".strip()

    def get_period_label(self, obj):
        return obj.period_label()

    def get_pdf_available(self, obj):
        return obj.has_pdf


class MonthlyReportDetailSerializer(MonthlyReportListSerializer):
    attempts = MonthlyReportAttemptSerializer(many=True, read_only=True)

    class Meta(MonthlyReportListSerializer.Meta):
        fields = MonthlyReportListSerializer.Meta.fields + [
            "generated_data", "editable_content", "attempts",
        ]


class MonthlyReportEditSerializer(serializers.ModelSerializer):
    """
    Ce qu'un administrateur a le droit de modifier : le texte humain.

    Les données agrégées ne sont PAS modifiables : elles décrivent ce qui
    a été saisi par les enseignants. Les corriger depuis cet écran ferait
    dire à un relevé de présence autre chose que ce qu'il contient.
    """

    class Meta:
        model = MonthlyStudentReport
        fields = ["editable_content"]

    def validate_editable_content(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError(
                "Le contenu rédigé doit être un objet.")
        autorises = {"summary", "progress", "difficulties", "recommendations",
                     "next_goals", "admin_message"}
        inconnus = set(value) - autorises
        if inconnus:
            raise serializers.ValidationError(
                f"Champs inconnus : {', '.join(sorted(inconnus))}.")
        for cle, texte in value.items():
            if texte is not None and not isinstance(texte, str):
                raise serializers.ValidationError(
                    f"« {cle} » doit être un texte.")
        return value
