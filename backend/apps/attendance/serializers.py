from apps.core.tenancy import TenantRelationsMixin
from rest_framework import serializers
from .models import Attendance
from apps.core.academy_serializers import (
    ACADEMY_FIELDS, STUDENT_AGE_FIELDS, AcademyMetadataMixin, StudentAgeMixin,
)


class AttendanceSerializer(TenantRelationsMixin, AcademyMetadataMixin, StudentAgeMixin, serializers.ModelSerializer):
    #: Isolation des relations écrites (voir apps.core.tenancy.TenantRelationsMixin).
    tenant_relations = {"student": "school", "subject": "school", "school_year": "school"}
    #: Chemin ORM vers l'académie propriétaire de l'objet.
    academy_source = "student.school"

    student_name = serializers.CharField(source="student.get_full_name", read_only=True)
    student_class = serializers.CharField(source="student.current_class.name", read_only=True)
    created_by_name = serializers.SerializerMethodField()
    status_label = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = Attendance
        fields = "__all__"

    def get_created_by_name(self, obj):
        return obj.created_by.get_full_name() if obj.created_by else ""

    def validate_date(self, value):
        # « Futur » s'apprécie dans le fuseau de l'ACADÉMIE de l'élève (FEBA
        # FHA : New York), pas dans celui du serveur (Porto-Novo).
        from apps.core.age import academy_today
        student = None
        raw = self.initial_data.get("student") if hasattr(self, "initial_data") else None
        if raw:
            from apps.students.models import Student
            student = Student.objects.select_related("school").filter(pk=raw).first()
        elif self.instance is not None:
            student = self.instance.student
        if value and value > academy_today(getattr(student, "school", None)):
            raise serializers.ValidationError(
                "La date ne peut pas être dans le futur."
            )
        return value

    def validate(self, attrs):
        # Prévention des doublons : un seul enregistrement par élève, date et
        # matière (matière nulle = présence journalière globale).
        student = attrs.get("student") or (self.instance and self.instance.student)
        date = attrs.get("date") or (self.instance and self.instance.date)
        subject = attrs.get("subject", self.instance.subject if self.instance else None)
        if student and date:
            qs = Attendance.objects.filter(student=student, date=date, subject=subject)
            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError(
                    "Une présence est déjà enregistrée pour cet élève à cette date."
                )
        return attrs