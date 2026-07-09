from rest_framework import serializers
from .models import ClassSchedule


class ClassScheduleSerializer(serializers.ModelSerializer):
    class_name = serializers.CharField(source="cls.name", read_only=True)
    subject_name = serializers.CharField(source="subject.name", read_only=True)
    subject_code = serializers.CharField(source="subject.code", read_only=True)
    teacher_name = serializers.SerializerMethodField()
    teacher_email = serializers.SerializerMethodField()
    day_label = serializers.CharField(source="get_day_of_week_display", read_only=True)
    school_year_name = serializers.CharField(source="school_year.name", read_only=True)

    class Meta:
        model = ClassSchedule
        fields = "__all__"

    def get_teacher_name(self, obj):
        return obj.teacher.user.get_full_name() if obj.teacher else ""

    def get_teacher_email(self, obj):
        return obj.teacher.user.email if obj.teacher else ""
