import logging
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from apps.core.tenancy import get_request_school
from .models import Notification
from .serializers import NotificationSerializer

logger = logging.getLogger("apps")


class NotificationViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Notifications d'un utilisateur.

    Isolation tenant : un utilisateur ne voit QUE ses propres notifications
    (filtre user=request.user) — garanti même si un superadmin interroge
    l'endpoint sans ?school_id=, il ne verra que ses notifications
    personnelles (comportement correct : le superadmin plateforme a ses
    propres notifications système, distinctes des données d'établissement).
    """
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Notification.objects.filter(
            user=self.request.user
        ).order_by("-created_at")

    @action(detail=True, methods=["put", "patch"])
    def read(self, request, pk=None):
        notif = self.get_object()
        notif.is_read = True
        notif.save(update_fields=["is_read"])
        return Response({"detail": "Lu."})

    @action(detail=False, methods=["put", "patch"])
    def read_all(self, request):
        updated = self.get_queryset().filter(is_read=False).update(is_read=True)
        logger.debug("read_all: %d notification(s) marquées lues pour %s", updated, request.user.email)
        return Response({"detail": "Toutes les notifications marquées comme lues."})

    @action(detail=False, methods=["get"])
    def unread_count(self, request):
        count = self.get_queryset().filter(is_read=False).count()
        return Response({"count": count})
