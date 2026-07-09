import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async

class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope["user"]
        if self.user.is_anonymous:
            await self.close()
            return
        self.room_name = self.scope["url_route"]["kwargs"]["room_id"]
        self.group_name = f"chat_{self.room_name}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data):
        data = json.loads(text_data)
        message = data.get("message", "")
        recipient_id = data.get("recipient_id")
        if message and recipient_id:
            saved = await self.save_message(recipient_id, message)
            await self.channel_layer.group_send(self.group_name, {
                "type": "chat_message",
                "message": message,
                "sender_id": self.user.id,
                "sender_name": self.user.get_full_name(),
                "message_id": saved.id,
            })

    async def chat_message(self, event):
        await self.send(text_data=json.dumps(event))

    @database_sync_to_async
    def save_message(self, recipient_id, body):
        from apps.messaging.models import Message
        from apps.accounts.models import CustomUser
        try:
            recipient = CustomUser.objects.get(pk=recipient_id)
            return Message.objects.create(sender=self.user, recipient=recipient, subject="Message direct", body=body)
        except Exception:
            return None