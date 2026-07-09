from rest_framework import serializers
from .models import Attendance


class AttendanceSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source="student.get_full_name", read_only=True)
    student_class = serializers.CharField(source="student.current_class.name", read_only=True)
    created_by_name = serializers.SerializerMethodField()
    status_label = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = Attendance
        fields = "__all__"

    def get_created_by_name(self, obj):
        return obj.created_by.get_full_name() if obj.created_by else ""