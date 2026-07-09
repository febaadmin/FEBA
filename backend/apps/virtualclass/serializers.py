from django.conf import settings
from rest_framework import serializers

from .models import VirtualRoom, VirtualRoomAttendance


class VirtualRoomSerializer(serializers.ModelSerializer):
    class_name = serializers.CharField(source="class_obj.name", read_only=True, default=None)
    subject_name = serializers.CharField(source="subject.name", read_only=True, default=None)
    created_by_name = serializers.SerializerMethodField()
    join_domain = serializers.SerializerMethodField()
    participants_count = serializers.SerializerMethodField()

    class Meta:
        model = VirtualRoom
        fields = [
            "id", "name", "description", "room_code", "school",
            "class_obj", "class_name", "subject", "subject_name",
            "school_year", "scheduled_at", "duration_minutes",
            "status", "is_active", "lobby_enabled",
            "created_by", "created_by_name", "created_at",
            "join_domain", "participants_count",
        ]
        read_only_fields = ["room_code", "created_by", "school", "created_at"]

    def get_created_by_name(self, obj):
        if obj.created_by:
            return obj.created_by.get_full_name() or obj.created_by.username
        return None

    def get_join_domain(self, obj):
        """Domaine Jitsi à utiliser côté client (auto-hébergé ou public)."""
        return getattr(settings, "JITSI_DOMAIN", "meet.jit.si")

    def get_participants_count(self, obj):
        return obj.attendances.values("user").distinct().count()


class VirtualRoomAttendanceSerializer(serializers.ModelSerializer):
    user_name = serializers.SerializerMethodField()
    user_role = serializers.CharField(source="user.role", read_only=True)

    class Meta:
        model = VirtualRoomAttendance
        fields = ["id", "room", "user", "user_name", "user_role", "joined_at"]
        read_only_fields = ["user", "joined_at"]

    def get_user_name(self, obj):
        return obj.user.get_full_name() or obj.user.username
