from rest_framework import serializers

from .models import TechnicalIncident


class TechnicalIncidentListSerializer(serializers.ModelSerializer):
    severity_display = serializers.CharField(source="get_severity_display", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    school_name = serializers.CharField(source="school.name", read_only=True, default=None)
    user_email = serializers.CharField(source="user.email", read_only=True, default=None)

    class Meta:
        model = TechnicalIncident
        fields = [
            "id", "reference", "created_at", "severity", "severity_display",
            "status", "status_display", "module", "endpoint", "http_method",
            "status_code", "exception_type", "occurrences", "first_seen_at",
            "last_seen_at", "school", "school_name", "user_email", "user_role",
        ]
        read_only_fields = fields


class TechnicalIncidentDetailSerializer(TechnicalIncidentListSerializer):
    assigned_to_email = serializers.CharField(source="assigned_to.email",
                                              read_only=True, default=None)

    class Meta(TechnicalIncidentListSerializer.Meta):
        fields = TechnicalIncidentListSerializer.Meta.fields + [
            "environment", "frontend_route", "message", "location",
            "attempted_action", "context_data", "user_agent", "app_version",
            "release", "fingerprint", "assigned_to", "assigned_to_email",
            "resolution_notes", "resolved_at",
        ]
        # Seuls le traitement (statut, assignation, notes) est modifiable :
        # les données techniques de l'incident restent immuables.
        read_only_fields = [
            f for f in fields
            if f not in {"status", "assigned_to", "resolution_notes", "severity"}
        ]
