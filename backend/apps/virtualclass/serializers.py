from django.conf import settings
from rest_framework import serializers

from .models import VirtualRoom, VirtualRoomAttendance
from apps.core.academy_serializers import ACADEMY_FIELDS, AcademyMetadataMixin


class VirtualRoomSerializer(AcademyMetadataMixin, serializers.ModelSerializer):
    #: Chemin ORM vers l'académie propriétaire de l'objet.
    academy_source = "school"

    class_name = serializers.CharField(source="class_obj.name", read_only=True, default=None)
    subject_name = serializers.CharField(source="subject.name", read_only=True, default=None)
    created_by_name = serializers.SerializerMethodField()
    join_domain = serializers.SerializerMethodField()
    participants_count = serializers.SerializerMethodField()
    video_provider = serializers.SerializerMethodField()
    capabilities = serializers.SerializerMethodField()

    class Meta:
        model = VirtualRoom
        fields = [
            "id", "name", "description", "room_code", "school",
            "class_obj", "class_name", "subject", "subject_name",
            "school_year", "scheduled_at", "duration_minutes",
            "status", "is_active", "lobby_enabled",
            "created_by", "created_by_name", "created_at",
            "join_domain", "participants_count", "target_roles",
            "allow_recording", "meeting_started_at", "meeting_ended_at",
            "video_provider", "capabilities",
        ] + ACADEMY_FIELDS
        read_only_fields = ["room_code", "created_by", "school", "created_at",
                            "meeting_started_at", "meeting_ended_at"]

    def get_created_by_name(self, obj):
        if obj.created_by:
            return obj.created_by.get_full_name() or obj.created_by.username
        return None

    def get_join_domain(self, obj):
        """
        Domaine de l'instance AUTO-HÉBERGÉE du moteur actif. Chaîne vide si
        elle n'est pas configurée : le frontend affiche alors une erreur
        d'infrastructure au lieu d'ouvrir un serveur public.
        """
        from .meetings import provider
        if provider() == "plugnmeet":
            from urllib.parse import urlparse
            from . import plugnmeet
            return urlparse(plugnmeet.public_url()).netloc if plugnmeet.is_configured() else ""
        from .services import JitsiNotConfigured, jitsi_domain
        try:
            return jitsi_domain()
        except JitsiNotConfigured:
            return ""

    def get_video_provider(self, obj):
        from .meetings import provider
        return provider()

    def get_capabilities(self, obj):
        """
        Ce que la salle propose RÉELLEMENT. Une fonction qui dépend d'un
        service non déployé (enregistrement, diffusion, IA) est fausse ici,
        quelle que soit la préférence de l'enseignant.
        """
        from .meetings import provider
        if provider() != "plugnmeet":
            return {"audio_video": True, "screen_share": True, "chat": True}
        recording = bool(settings.PLUGNMEET_RECORDING_ENABLED and obj.allow_recording)
        return {
            "audio_video": True, "screen_share": True, "chat": True, "file_sharing": True,
            "whiteboard": True, "documents_on_whiteboard": True, "shared_notes": True,
            "breakout_rooms": True, "polls": True, "raise_hand": True, "waiting_room": obj.lobby_enabled,
            "moderation": True, "recording": recording,
            "rtmp_broadcast": bool(settings.PLUGNMEET_RTMP_ENABLED),
            "ai_insights": bool(settings.PLUGNMEET_INSIGHTS_ENABLED),
        }

    def get_participants_count(self, obj):
        return obj.attendances.values("user").distinct().count()


class VirtualRoomAttendanceSerializer(serializers.ModelSerializer):
    user_name = serializers.SerializerMethodField()
    user_role = serializers.CharField(source="user.role", read_only=True)

    class Meta:
        model = VirtualRoomAttendance
        fields = ["id", "room", "user", "user_name", "user_role", "joined_at", "left_at",
                  "duration_seconds", "reconnections", "session_sid", "source"]
        read_only_fields = fields

    def get_user_name(self, obj):
        return obj.user.get_full_name() or obj.user.username
