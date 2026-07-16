"""
Messaging views — v7

Architecture:
  GET  /api/messages/conversations/         → list user's conversations
  GET  /api/messages/conversations/{id}/    → full thread with all messages
  POST /api/messages/conversations/         → start new conversation (compose)
  POST /api/messages/conversations/{id}/reply/ → reply in thread
  PUT  /api/messages/conversations/{id}/mark_read/ → mark all as read
  GET  /api/messages/unread_count/          → badge count
"""
from rest_framework import viewsets, status, views
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from django.utils import timezone
from django.db.models import Q
from .models import Conversation, Message
from .serializers import (
    ConversationSerializer, ConversationListSerializer, MessageSerializer
)
import logging

logger = logging.getLogger("apps")


class ConversationViewSet(viewsets.ModelViewSet):
    """
    Full CRUD on conversations.
    - List: shows conversations where request.user is a participant
    - Retrieve: returns full thread
    - Create: compose a new message (creates conversation + first message)
    """
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_queryset(self):
        return (
            Conversation.objects
            .filter(participants=self.request.user)
            .prefetch_related("participants", "messages__sender", "messages__recipient")
            .order_by("-updated_at")
        )

    def get_serializer_class(self):
        if self.action == "list":
            return ConversationListSerializer
        return ConversationSerializer

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["request"] = self.request
        return ctx

    def create(self, request, *args, **kwargs):
        """
        POST /api/messages/conversations/
        Body: { recipient_id, subject, body, attachment? }
        """
        recipient_id = request.data.get("recipient_id") or request.data.get("recipient")
        subject = request.data.get("subject", "").strip()
        body = request.data.get("body", "").strip()
        attachment = request.FILES.get("attachment")

        if not recipient_id or not body:
            return Response(
                {"error": "recipient_id et body sont requis."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not subject:
            subject = "(Sans sujet)"

        from apps.accounts.models import CustomUser
        from apps.core.tenancy import get_request_school
        school = get_request_school(request)
        recipient_qs = CustomUser.objects.all()
        # FIX SÉCURITÉ (v29) : un utilisateur ne doit pouvoir démarrer une
        # conversation qu'avec quelqu'un de SON établissement — sinon
        # n'importe qui pouvait contacter un utilisateur d'un autre tenant
        # en devinant son ID.
        if school is not None:
            recipient_qs = recipient_qs.filter(school=school)
        try:
            recipient = recipient_qs.get(pk=recipient_id)
        except CustomUser.DoesNotExist:
            return Response({"error": "Destinataire introuvable."}, status=404)

        # Find or create conversation
        conv, _ = Conversation.get_or_create_between(request.user, recipient, subject)

        # Create the first message in conversation
        msg_kwargs = dict(
            conversation=conv,
            sender=request.user,
            recipient=recipient,
            subject=subject,
            body=body,
            thread_id=conv.id,  # use conv.id as thread identifier
        )
        if attachment:
            msg_kwargs["attachment"] = attachment
            msg_kwargs["attachment_name"] = attachment.name

        msg = Message.objects.create(**msg_kwargs)

        # Update conversation timestamp
        conv.save()

        # Send notification
        try:
            from apps.notifications.utils import create_notification, notification_path
            create_notification(
                recipient, "message",
                f"Nouveau message de {request.user.get_full_name()}",
                subject,
                # FIX (redirections notifications) : "/messages/{id}/" ne
                # correspondait à AUCUNE route déclarée côté frontend (les
                # routes sont "/<role>/messages", sans segment id) — la
                # navigation tombait systématiquement dans le catch-all et
                # renvoyait l'utilisateur vers /login. La page Messages lit
                # désormais le paramètre ?conversation= pour ouvrir le bon
                # fil directement.
                related_url=notification_path(recipient, f"messages?conversation={conv.id}"),
            )
        except Exception as exc:
            logger.warning("Erreur non bloquante ignorée : %s", exc, exc_info=True)
        logger.info(f"Message sent: {request.user.email} → {recipient.email} [{subject}]")
        return Response(
            ConversationSerializer(conv, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"])
    def reply(self, request, pk=None):
        """
        POST /api/messages/conversations/{id}/reply/
        Body: { body, attachment? }
        """
        conv = self.get_object()
        body = request.data.get("body", "").strip()
        if not body:
            return Response({"error": "Le corps du message est requis."}, status=400)

        attachment = request.FILES.get("attachment")

        # Determine recipient (the other participant)
        other = conv.participants.exclude(id=request.user.id).first()
        if not other:
            return Response({"error": "Impossible de trouver le destinataire."}, status=400)

        msg_kwargs = dict(
            conversation=conv,
            sender=request.user,
            recipient=other,
            subject=conv.subject,
            body=body,
        )
        if attachment:
            msg_kwargs["attachment"] = attachment
            msg_kwargs["attachment_name"] = attachment.name

        msg = Message.objects.create(**msg_kwargs)
        conv.save()  # update updated_at

        # Mark existing unread messages as read for the replier
        conv.messages.filter(recipient=request.user, is_read=False).update(
            is_read=True, read_at=timezone.now()
        )

        # Notify the other participant
        try:
            from apps.notifications.utils import create_notification, notification_path
            create_notification(
                other, "message",
                f"Réponse de {request.user.get_full_name()}",
                conv.subject,
                related_url=notification_path(other, f"messages?conversation={conv.id}"),
            )
        except Exception as exc:
            logger.warning("Erreur non bloquante ignorée : %s", exc, exc_info=True)
        return Response(
            MessageSerializer(msg, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["put", "patch"])
    def mark_read(self, request, pk=None):
        """Mark all messages in conversation as read for request.user."""
        conv = self.get_object()
        updated = conv.messages.filter(
            recipient=request.user, is_read=False
        ).update(is_read=True, read_at=timezone.now())
        return Response({"marked_read": updated})

    @action(detail=False, methods=["get"])
    def unread_count(self, request):
        count = Message.objects.filter(
            recipient=request.user, is_read=False,
            conversation__participants=request.user,
        ).count()
        return Response({"count": count})


# ── Legacy compatibility view for flat messages (inbox/sent) ──────────────────
class MessageViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Legacy read-only access for backward compatibility.
    Prefer ConversationViewSet for new code.
    """
    serializer_class = MessageSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        return (
            Message.objects
            .filter(Q(sender=user) | Q(recipient=user))
            .select_related("sender", "recipient")
            .order_by("-sent_at")
        )

    @action(detail=False, methods=["get"])
    def inbox(self, request):
        msgs = Message.objects.filter(
            recipient=request.user
        ).select_related("sender").order_by("-sent_at")
        return Response(MessageSerializer(msgs, many=True, context={"request": request}).data)

    @action(detail=False, methods=["get"])
    def sent(self, request):
        msgs = Message.objects.filter(
            sender=request.user
        ).select_related("recipient").order_by("-sent_at")
        return Response(MessageSerializer(msgs, many=True, context={"request": request}).data)

    @action(detail=False, methods=["get"])
    def unread_count(self, request):
        count = Message.objects.filter(recipient=request.user, is_read=False).count()
        return Response({"count": count})

    @action(detail=True, methods=["put", "patch"])
    def read(self, request, pk=None):
        msg = self.get_object()
        if msg.recipient == request.user:
            msg.is_read = True
            msg.read_at = timezone.now()
            msg.save(update_fields=["is_read", "read_at"])
        return Response({"detail": "Lu."})

    @action(detail=True, methods=["post"])
    def reply(self, request, pk=None):
        original = self.get_object()
        recipient = original.sender if original.recipient == request.user else original.recipient
        body = request.data.get("body", "").strip()
        if not body:
            return Response({"error": "Corps du message requis."}, status=400)
        subject = original.subject if original.subject.startswith("Re: ") else f"Re: {original.subject}"
        msg = Message.objects.create(
            sender=request.user, recipient=recipient,
            subject=subject, body=body,
            thread_id=original.thread_id, parent_message=original,
        )
        attachment = request.FILES.get("attachment")
        if attachment:
            msg.attachment = attachment
            msg.attachment_name = attachment.name
            msg.save(update_fields=["attachment", "attachment_name"])
        return Response(MessageSerializer(msg).data, status=201)
