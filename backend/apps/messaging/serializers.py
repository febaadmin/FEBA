from rest_framework import serializers
from apps.accounts.models import CustomUser
from .models import Conversation, Message


class ShortUserSerializer(serializers.ModelSerializer):
    """Minimal user info for message display."""
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = CustomUser
        fields = ["id", "first_name", "last_name", "email", "role", "full_name"]

    def get_full_name(self, obj):
        return obj.get_full_name()


class MessageSerializer(serializers.ModelSerializer):
    sender = ShortUserSerializer(read_only=True)
    recipient_detail = ShortUserSerializer(source="recipient", read_only=True)
    has_attachment = serializers.SerializerMethodField()
    recipient = serializers.PrimaryKeyRelatedField(
        queryset=CustomUser.objects.all(),
        write_only=True,
        required=False,
        allow_null=True,
    )

    class Meta:
        model = Message
        fields = [
            "id", "conversation", "sender", "recipient", "recipient_detail",
            "subject", "body", "attachment", "attachment_name",
            "is_read", "sent_at", "read_at", "has_attachment", "thread_id",
            "parent_message",
        ]
        read_only_fields = ["sender", "sent_at", "read_at", "thread_id"]

    def get_has_attachment(self, obj):
        return bool(obj.attachment)


class ConversationSerializer(serializers.ModelSerializer):
    """Full conversation with all messages — used for thread view."""
    participants = ShortUserSerializer(many=True, read_only=True)
    messages = MessageSerializer(many=True, read_only=True)
    latest_message = serializers.SerializerMethodField()
    unread_count = serializers.SerializerMethodField()

    class Meta:
        model = Conversation
        fields = [
            "id", "subject", "participants", "messages",
            "latest_message", "unread_count", "created_at", "updated_at",
        ]

    def get_latest_message(self, obj):
        msg = obj.messages.order_by("-sent_at").first()
        if msg:
            return {
                "id": msg.id,
                "body": msg.body,  # FIX: Full body, no truncation in thread view
                "sender_name": msg.sender.get_full_name(),
                "sent_at": msg.sent_at,
                "is_read": msg.is_read,
            }
        return None

    def get_unread_count(self, obj):
        request = self.context.get("request")
        if not request:
            return 0
        return obj.messages.filter(
            is_read=False,
            recipient=request.user,
        ).count()


class ConversationListSerializer(serializers.ModelSerializer):
    """Lightweight listing — preview only, no full message list."""
    participants = ShortUserSerializer(many=True, read_only=True)
    latest_message = serializers.SerializerMethodField()
    unread_count = serializers.SerializerMethodField()
    other_participant = serializers.SerializerMethodField()

    class Meta:
        model = Conversation
        fields = [
            "id", "subject", "participants", "other_participant",
            "latest_message", "unread_count", "updated_at",
        ]

    def get_latest_message(self, obj):
        msg = obj.messages.order_by("-sent_at").first()
        if msg:
            preview = msg.body[:120] + ("…" if len(msg.body) > 120 else "")
            return {
                "id": msg.id,
                "body": preview,
                "sender_name": msg.sender.get_full_name(),
                "sent_at": msg.sent_at,
                "is_read": msg.is_read,
            }
        return None

    def get_unread_count(self, obj):
        request = self.context.get("request")
        if not request:
            return 0
        return obj.messages.filter(is_read=False, recipient=request.user).count()

    def get_other_participant(self, obj):
        request = self.context.get("request")
        if not request:
            return None
        other = obj.participants.exclude(id=request.user.id).first()
        return ShortUserSerializer(other).data if other else None
