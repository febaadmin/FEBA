from rest_framework import serializers
from .models import Homework, HomeworkAttachment
from apps.core.academy_serializers import ACADEMY_FIELDS, AcademyMetadataMixin


class HomeworkAttachmentSerializer(serializers.ModelSerializer):
    file_url = serializers.SerializerMethodField()

    class Meta:
        model = HomeworkAttachment
        fields = "__all__"

    def get_file_url(self, obj):
        request = self.context.get("request")
        if obj.file:
            return obj.file.url if request else obj.file.url
        return None


class HomeworkSerializer(AcademyMetadataMixin, serializers.ModelSerializer):
    #: Chemin ORM vers l'académie propriétaire de l'objet.
    academy_source = "school_year.school"

    class_name = serializers.CharField(source="cls.name", read_only=True)
    subject_name = serializers.CharField(source="subject.name", read_only=True)
    teacher_name = serializers.SerializerMethodField()
    school_year_name = serializers.CharField(source="school_year.name", read_only=True)
    attachments = serializers.SerializerMethodField()

    def get_attachments(self, obj):
        return HomeworkAttachmentSerializer(
            obj.attachments.all(), many=True, context=self.context
        ).data
    is_overdue = serializers.SerializerMethodField()

    class Meta:
        model = Homework
        fields = "__all__"

    def get_teacher_name(self, obj):
        return obj.teacher.user.get_full_name() if obj.teacher else ""

    def get_is_overdue(self, obj):
        from django.utils import timezone
        return obj.due_date < timezone.now().date()