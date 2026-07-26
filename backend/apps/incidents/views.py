"""API des incidents techniques — réservée aux super administrateurs (V8)."""
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.response import Response

from .models import TechnicalIncident
from .serializers import (
    TechnicalIncidentDetailSerializer, TechnicalIncidentListSerializer,
)


class IsSuperAdmin(BasePermission):
    """Seul le super administrateur accède aux incidents techniques.

    Admin / enseignant / parent / élève : aucun accès (les incidents peuvent
    contenir des informations transverses à plusieurs établissements).
    """
    message = "Accès réservé aux super administrateurs."

    def has_permission(self, request, view):
        user = request.user
        return bool(
            user and user.is_authenticated
            and getattr(user, "role", None) == "superadmin"
        )


class TechnicalIncidentViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, IsSuperAdmin]
    queryset = TechnicalIncident.objects.select_related("user", "school", "assigned_to")
    filterset_fields = ["status", "severity", "module", "school", "exception_type"]
    search_fields = ["reference", "message", "endpoint", "exception_type", "module"]
    ordering_fields = ["last_seen_at", "created_at", "occurrences", "severity"]
    http_method_names = ["get", "patch", "post", "head", "options"]

    def get_serializer_class(self):
        if self.action == "list":
            return TechnicalIncidentListSerializer
        return TechnicalIncidentDetailSerializer

    def create(self, request, *args, **kwargs):
        """Un incident se constate, il ne se saisit pas à la main.

        (POST reste autorisé sur le ViewSet pour les actions `resolve` /
        `reopen` ; sans cette surcharge, un POST sur la liste plantait — et
        générait ironiquement un incident technique.)
        """
        return Response(
            {"detail": "Les incidents techniques sont créés automatiquement."},
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    @action(detail=False, methods=["get"], url_path="stats")
    def stats(self, request):
        """Compteurs pour la pastille et les filtres."""
        qs = self.get_queryset()
        by_status = {key: qs.filter(status=key).count()
                     for key, _ in TechnicalIncident.STATUS_CHOICES}
        by_severity = {key: qs.filter(severity=key).count()
                       for key, _ in TechnicalIncident.SEVERITY_CHOICES}
        return Response({
            "total": qs.count(),
            "new": by_status.get("new", 0),
            "by_status": by_status,
            "by_severity": by_severity,
        })

    @action(detail=True, methods=["post"], url_path="resolve")
    def resolve(self, request, pk=None):
        incident = self.get_object()
        incident.status = "resolved"
        incident.resolved_at = timezone.now()
        notes = request.data.get("resolution_notes")
        if notes:
            incident.resolution_notes = notes
        incident.save(update_fields=["status", "resolved_at", "resolution_notes"])
        return Response(self.get_serializer(incident).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="reopen")
    def reopen(self, request, pk=None):
        incident = self.get_object()
        incident.status = "reopened"
        incident.resolved_at = None
        incident.save(update_fields=["status", "resolved_at"])
        return Response(self.get_serializer(incident).data, status=status.HTTP_200_OK)
