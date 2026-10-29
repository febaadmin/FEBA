from apps.core.tenancy import TenantRelationsMixin
from rest_framework import serializers
from .models import Bulletin, BulletinOperation
from apps.core.academy_serializers import (
    ACADEMY_FIELDS, STUDENT_AGE_FIELDS, AcademyMetadataMixin, StudentAgeMixin,
)


class BulletinSerializer(TenantRelationsMixin, AcademyMetadataMixin, StudentAgeMixin, serializers.ModelSerializer):
    #: Isolation des relations écrites (voir apps.core.tenancy.TenantRelationsMixin).
    tenant_relations = {"student": "school", "school_year": "school"}
    #: Chemin ORM vers l'académie propriétaire de l'objet.
    academy_source = "student.school"

    student_name = serializers.CharField(source="student.get_full_name", read_only=True)
    student_class = serializers.CharField(source="student.current_class.name", read_only=True, default="—")
    school_year_name = serializers.CharField(source="school_year.name", read_only=True)
    period_label = serializers.CharField(source="get_period_display", read_only=True)
    pdf_url = serializers.SerializerMethodField()
    pdf_outdated = serializers.BooleanField(read_only=True)
    comment_updated_by_name = serializers.CharField(
        source="comment_updated_by.get_full_name", read_only=True, default=None)

    class Meta:
        model = Bulletin
        fields = "__all__"
        # Le commentaire se modifie par POST /bulletins/{id}/comment/ (texte
        # validé, PDF régénéré) ; les valeurs calculées, par la génération.
        read_only_fields = ("pdf_file", "generated_at", "general_comment", "comment_updated_at",
                            "comment_updated_by", "average", "rank_in_class", "appreciation",
                            "enrollment")

    def get_pdf_url(self, obj):
        if obj.pdf_file:
            request = self.context.get("request")
            if request:
                return obj.pdf_file.url
            return obj.pdf_file.url
        return None


class BulletinOperationSerializer(serializers.ModelSerializer):
    created_by_name = serializers.CharField(source="created_by.get_full_name", read_only=True, default=None)
    school_year_name = serializers.CharField(source="school_year.name", read_only=True)
    student_name = serializers.CharField(source="student.get_full_name", read_only=True, default=None)
    class_name = serializers.CharField(source="class_obj.name", read_only=True, default=None)
    scope_label = serializers.CharField(source="get_scope_display", read_only=True)
    action_label = serializers.CharField(source="get_action_display", read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = BulletinOperation
        fields = ("id", "school", "school_year", "school_year_name", "period", "scope", "scope_label",
                  "student", "student_name", "class_obj", "class_name", "action", "action_label",
                  "comment", "regenerate", "create_missing", "status", "status_label", "result",
                  "error", "created_by", "created_by_name", "created_at", "started_at", "finished_at")
        read_only_fields = fields
