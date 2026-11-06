"""API des incidents techniques — réservée aux super administrateurs (V8)."""
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.response import Response

from apps.core.request_text import text_field

from .models import IncidentStatusEvent, TechnicalIncident, changer_statut, validations_manquantes
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

    def perform_update(self, serializer):
        ancien = serializer.instance.status
        incident = serializer.save()
        if incident.status != ancien:
            if incident.status != "resolved" and incident.resolved_at:
                incident.resolved_at = None
                incident.save(update_fields=["resolved_at"])
            IncidentStatusEvent.objects.create(incident=incident, from_status=ancien, to_status=incident.status,
                                               performed_by=self.request.user,
                                               note=text_field(self.request.data, "resolution_notes"))

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
        manque = validations_manquantes(incident)
        if manque:
            return Response({"detail": f"Validations manquantes : {', '.join(manque)}.", "manquantes": manque},
                            status=status.HTTP_400_BAD_REQUEST)
        notes = text_field(request.data, "resolution_notes")
        if notes:
            incident.resolution_notes = notes
            incident.save(update_fields=["resolution_notes"])
        changer_statut(incident, "resolved", request.user, notes)
        incident.resolved_at = timezone.now()
        incident.save(update_fields=["resolved_at"])
        return Response(self.get_serializer(incident).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="reopen")
    def reopen(self, request, pk=None):
        incident = self.get_object()
        changer_statut(incident, "reopened", request.user)
        return Response(self.get_serializer(incident).data, status=status.HTTP_200_OK)


class ErreurInterface(Exception):
    """Erreur remontée par l'interface (navigateur) — jamais levée côté serveur."""


class SignalementInterfaceView(viewsets.ViewSet):
    """POST /api/incidents/frontend/ — tout utilisateur connecté.

    Trace côté serveur les erreurs d'affichage (page d'erreur, module JavaScript
    introuvable après un déploiement…), sans rien renvoyer d'autre qu'un accusé.
    Limité à 20 signalements par heure et par compte ; texte assaini et tronqué ;
    dédoublonné par l'empreinte habituelle des incidents.
    """
    permission_classes = [IsAuthenticated]
    TYPES = {"chunk": "Module de l'interface introuvable (version périmée)", "rendu": "Erreur d'affichage"}

    def create(self, request):
        from django.core.cache import cache
        from .services import report_incident
        cle = f"incident-front:{request.user.pk}"
        n = cache.get(cle, 0)
        if n >= 20:
            return Response({"enregistre": False}, status=status.HTTP_429_TOO_MANY_REQUESTS)
        cache.set(cle, n + 1, 3600)
        if not isinstance(request.data, dict):
            return Response({"detail": "Objet JSON attendu."}, status=status.HTTP_400_BAD_REQUEST)
        genre = request.data.get("type")
        genre = genre if isinstance(genre, str) and genre in self.TYPES else "rendu"
        message = text_field(request.data, "message")[:500]
        route = text_field(request.data, "route")[:200]
        incident = report_incident(
            # Version périmée : un seul incident regroupé (le nom du fichier change à
            # chaque déploiement et ne doit pas multiplier les alertes).
            ErreurInterface(self.TYPES[genre] if genre == "chunk" else f"{self.TYPES[genre]} : {message}"), request=request, module="frontend",
            attempted_action=f"Affichage de {route}"[:255], severity="medium" if genre == "chunk" else "high",
            status_code=None, context={"route": route, "type": genre, "detail": message})
        return Response({"enregistre": incident is not None}, status=status.HTTP_201_CREATED)
