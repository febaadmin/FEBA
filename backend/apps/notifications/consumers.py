import json
from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer

from apps.accounts.sessions_temps_reel import (
    CODE_SESSION_TERMINEE, groupe_sessions, session_toujours_valide,
)


class NotificationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope["user"]
        if self.user.is_anonymous:
            await self.close()
            return
        self.group_name = f"notifications_{self.user.id}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.channel_layer.group_add(groupe_sessions(self.user.pk), self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)
            await self.channel_layer.group_discard(groupe_sessions(self.user.pk), self.channel_name)

    async def session_terminee(self, event):
        await self.close(code=CODE_SESSION_TERMINEE)

    async def notification_message(self, event):
        if not await database_sync_to_async(session_toujours_valide)(self.user.pk, self.user.password):
            await self.close(code=CODE_SESSION_TERMINEE)
            return
        await self.send(text_data=json.dumps(event["data"]))
