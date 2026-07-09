import logging
logger = logging.getLogger("apps")
def create_notification(user, notif_type, title, message, related_url=""):
    from apps.notifications.models import Notification
    notif = Notification.objects.create(
        user=user, type=notif_type, title=title,
        message=message, related_url=related_url
    )
    # Push via WebSocket channel layer
    try:
        from channels.layers import get_channel_layer
        from asgiref.sync import async_to_sync
        channel_layer = get_channel_layer()
        if channel_layer:
            async_to_sync(channel_layer.group_send)(
                f"notifications_{user.id}",
                {
                    "type": "notification_message",
                    "data": {
                        "id": notif.id,
                        "title": title,
                        "message": message,
                        "type": notif_type,
                        "created_at": notif.created_at.isoformat(),
                        "related_url": related_url,
                    },
                }
            )
    except Exception as exc:
        logger.warning("Erreur non bloquante ignorée : %s", exc, exc_info=True)
    return notif