import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async

from apps.accounts.sessions_temps_reel import (
    CODE_SESSION_TERMINEE, groupe_sessions, session_toujours_valide,
)


class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope["user"]
        if self.user.is_anonymous:
            await self.close()
            return
        self.room_name = self.scope["url_route"]["kwargs"]["room_id"]
        # Un salon « 12-34 » ne s'ouvre qu'à ses deux participants.
        if str(self.user.pk) not in self.room_name.split("-"):
            await self.close()
            return
        self.group_name = f"chat_{self.room_name}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.channel_layer.group_add(groupe_sessions(self.user.pk), self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)
            await self.channel_layer.group_discard(groupe_sessions(self.user.pk), self.channel_name)

    async def session_terminee(self, event):
        await self.close(code=CODE_SESSION_TERMINEE)

    async def receive(self, text_data):
        if not await database_sync_to_async(session_toujours_valide)(self.user.pk, self.user.password):
            await self.close(code=CODE_SESSION_TERMINEE)
            return
        data = json.loads(text_data)
        message = data.get("message", "")
        recipient_id = data.get("recipient_id")
        if message and recipient_id:
            saved = await self.save_message(recipient_id, message)
            if saved is None:
                return
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
        from apps.accounts.views import allowed_message_recipients
        from apps.messaging.models import Message
        try:
            # Même règle que l'API de messagerie.
            recipient = allowed_message_recipients(self.user).get(pk=recipient_id)
            return Message.objects.create(sender=self.user, recipient=recipient, subject="Message direct", body=body)
        except Exception:
            return None
