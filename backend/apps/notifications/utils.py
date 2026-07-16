import logging
logger = logging.getLogger("apps")

# FIX (redirections notifications) : chaque rôle a son propre espace de
# routes côté frontend (/admin/..., /parent/..., /teacher/..., /student/...,
# /superadmin/...). Un related_url généré sans préfixe de rôle (ex.
# "/messages/5/") ne correspond à AUCUNE route déclarée : React Router le
# fait tomber dans la route catch-all "*", perçue par l'utilisateur comme une
# déconnexion ou un renvoi vers la page de connexion. Toute création de
# notification doit donc passer par `notification_path(user, ...)` pour que
# le chemin soit préfixé selon le rôle du DESTINATAIRE (pas de l'émetteur).
ROLE_PREFIXES = {
    "superadmin": "/superadmin",
    "admin": "/admin",
    "teacher": "/teacher",
    "parent": "/parent",
    "student": "/student",
}


def notification_path(user, path):
    """Construit une URL frontend valide et propre au rôle du destinataire.

    `path` est le segment relatif à l'espace de rôle, ex. "grades",
    "attendance", "messages?conversation=5". Ne jamais construire de
    related_url "en dur" ailleurs dans le code : toujours passer par cette
    fonction pour garantir la cohérence des redirections.
    """
    prefix = ROLE_PREFIXES.get(getattr(user, "role", None), "")
    if not prefix:
        # Rôle inconnu/absent : pas d'URL de destination fiable — mieux vaut
        # une notification non cliquable qu'une redirection erronée.
        return ""
    path = path.lstrip("/")
    return f"{prefix}/{path}"


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