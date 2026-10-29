"""
Reusable mixin that adds a bulk_delete action to any DRF ViewSet.

POST /endpoint/bulk-delete/
Body: { "ids": [1, 2, 3] }

- Soft-delete if the model has `is_deleted` field (sets is_deleted=True)
- Hard-delete otherwise
- Wrapped in a DB transaction
- Logs each deletion in Django's auth log (or any future audit system)
- Returns 204 on success, 400 if no ids provided, 403 if not permitted
"""
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status
from django.db import transaction
import logging

logger = logging.getLogger(__name__)


class BulkDeleteMixin:
    """
    Add to a ModelViewSet to get a POST /bulk-delete/ action.
    Override `get_bulk_delete_queryset` for custom filtering.
    """

    def get_bulk_delete_permissions(self):
        """
        Permissions EN PLUS de celles de la vue.

        FAILLE CORRIGÉE (audit octobre 2026) : cette action n'était soumise
        qu'aux permissions par défaut de la vue (« authentifié, même
        académie ») — un parent ou un élève pouvait supprimer en masse les
        paiements, notes ou absences qu'il voit. Par défaut : administrateurs
        uniquement. Une vue qui gère déjà `bulk_delete` dans
        `get_permissions()` peut renvoyer [] ici.
        """
        from apps.accounts.permissions import IsAdminOrAbove
        return [IsAdminOrAbove()]

    def perform_bulk_soft_delete(self, queryset, request):
        """Suppression logique groupée. Surchargée pour tracer l'historique."""
        queryset.update(is_deleted=True)

    @action(detail=False, methods=["post"], url_path="bulk-delete")
    def bulk_delete(self, request, *args, **kwargs):
        for permission in self.get_bulk_delete_permissions():
            if not permission.has_permission(request, self):
                self.permission_denied(request, message=getattr(permission, "message", None))
        ids = request.data.get("ids", [])
        if not ids or not isinstance(ids, list):
            return Response({"error": "ids list required"}, status=status.HTTP_400_BAD_REQUEST)

        qs = self.get_bulk_delete_queryset(ids)
        count = qs.count()

        if count == 0:
            return Response({"deleted": 0}, status=status.HTTP_204_NO_CONTENT)

        with transaction.atomic():
            model = qs.model
            has_soft = hasattr(model, "is_deleted") and "is_deleted" in [
                f.name for f in model._meta.get_fields()
            ]
            if has_soft:
                self.perform_bulk_soft_delete(qs, request)
                action_str = "soft-deleted"
            else:
                qs.delete()
                action_str = "hard-deleted"

        logger.info(
            "BulkDelete: user=%s model=%s ids=%s action=%s count=%d",
            getattr(request.user, "username", "?"),
            model.__name__,
            ids,
            action_str,
            count,
        )
        return Response({"deleted": count}, status=status.HTTP_200_OK)

    def get_bulk_delete_queryset(self, ids):
        """
        Return queryset filtered to the given ids.
        Override to add extra restrictions (e.g. same school).
        """
        return self.get_queryset().filter(pk__in=ids)
