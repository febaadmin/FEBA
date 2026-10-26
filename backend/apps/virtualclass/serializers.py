from django.conf import settings
from rest_framework import serializers

from .models import VirtualRoom, VirtualRoomAttendance
from apps.core.academy_serializers import ACADEMY_FIELDS, AcademyMetadataMixin
from apps.core.tenancy import TenantRelationsMixin

ROLES = ("admin", "teacher", "student", "parent")


class VirtualRoomSerializer(TenantRelationsMixin, AcademyMetadataMixin, serializers.ModelSerializer):
    #: Chemin ORM vers l'académie propriétaire de l'objet.
    academy_source = "school"
    #: Isolation des relations écrites : une salle FEBA ne peut pas viser la
    #: classe, la matière ou l'année d'une autre académie. Ce contrôle
    #: manquait — la création acceptait n'importe quel identifiant.
    tenant_relations = {"class_obj": "school_year.school", "subject": "school",
                        "school_year": "school"}

    class_name = serializers.CharField(source="class_obj.name", read_only=True, default=None)
    subject_name = serializers.CharField(source="subject.name", read_only=True, default=None)
    created_by_name = serializers.SerializerMethodField()
    join_domain = serializers.SerializerMethodField()
    participants_count = serializers.SerializerMethodField()
    video_provider = serializers.SerializerMethodField()
    capabilities = serializers.SerializerMethodField()
    can_manage = serializers.SerializerMethodField()

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
            "video_provider", "capabilities", "can_manage",
        ] + ACADEMY_FIELDS
        read_only_fields = ["room_code", "created_by", "school", "created_at",
                            "meeting_started_at", "meeting_ended_at"]

    def validate_target_roles(self, value):
        if value in (None, ""):
            return []
        if not isinstance(value, list) or any(r not in ROLES for r in value):
            raise serializers.ValidationError(f"Rôles autorisés : {', '.join(ROLES)}.")
        return sorted(set(value))

    def validate(self, attrs):
        attrs = super().validate(attrs)
        # La classe et l'année doivent concorder (une classe 2025-2026 dans une
        # salle 2026-2027 donnerait une liste d'élèves incohérente).
        class_obj = attrs.get("class_obj", getattr(self.instance, "class_obj", None))
        year = attrs.get("school_year", getattr(self.instance, "school_year", None))
        if class_obj is not None and year is not None and class_obj.school_year_id != year.id:
            raise serializers.ValidationError(
                {"class_obj": "Cette classe n'appartient pas à l'année scolaire choisie."})
        return attrs

    def get_can_manage(self, obj):
        """Mêmes règles que VirtualRoomViewSet._assert_can_manage."""
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if user is None or not user.is_authenticated or user.role_level < 50:
            return False
        if user.role_level >= 80 or obj.created_by_id == user.id:
            return True
        if "_teacher_class_ids" not in self.context:
            teacher = getattr(user, "teacher_profile", None)
            self.context["_teacher_class_ids"] = set(
                teacher.classes.values_list("pk", flat=True)) if teacher else set()
        return obj.class_obj_id in self.context["_teacher_class_ids"]

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
