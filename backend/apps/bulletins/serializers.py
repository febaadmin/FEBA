from rest_framework import serializers
from .models import Bulletin
from apps.core.academy_serializers import ACADEMY_FIELDS, AcademyMetadataMixin


class BulletinSerializer(AcademyMetadataMixin, serializers.ModelSerializer):
    #: Chemin ORM vers l'académie propriétaire de l'objet.
    academy_source = "student.school"

    student_name = serializers.CharField(source="student.get_full_name", read_only=True)
    student_class = serializers.CharField(source="student.current_class.name", read_only=True, default="—")
    school_year_name = serializers.CharField(source="school_year.name", read_only=True)
    period_label = serializers.CharField(source="get_period_display", read_only=True)
    pdf_url = serializers.SerializerMethodField()

    class Meta:
        model = Bulletin
        fields = "__all__"

    def get_pdf_url(self, obj):
        if obj.pdf_file:
            request = self.context.get("request")
            if request:
                return obj.pdf_file.url
            return obj.pdf_file.url
        return None
