"""
Service JWT Jitsi — FIX v35.

Émet des jetons signés (HS256) conformes au format Jitsi (lib-jitsi-meet /
prosody token_verification). Seul le backend FEBA connaît JITSI_APP_SECRET :
aucune salle de l'instance auto-hébergée ne peut être ouverte sans passer
par la vérification de permissions Django.

Si JITSI_APP_SECRET n'est pas configuré (par ex. démo locale sur l'instance
publique meet.jit.si), aucun jeton n'est émis — le client rejoint sans JWT.
"""
import time

from django.conf import settings


def build_jitsi_jwt(user, room, moderator=False, ttl_seconds=3600 * 3):
    """
    Retourne un JWT Jitsi pour `user` et la salle `room`, ou None si
    l'instance n'est pas configurée en mode authentifié.

    Payload conforme Jitsi :
      iss = APP_ID · aud = "jitsi" · sub = domaine · room = code de salle
      context.user = identité affichée · context.user.moderator
    """
    secret = getattr(settings, "JITSI_APP_SECRET", "") or ""
    app_id = getattr(settings, "JITSI_APP_ID", "") or ""
    if not secret or not app_id:
        return None

    import jwt  # PyJWT (dépendance de simplejwt, épinglée dans base.txt)

    domain = (getattr(settings, "JITSI_DOMAIN", "") or "*").split(":")[0] or "*"
    now = int(time.time())
    payload = {
        "iss": app_id,
        "aud": "jitsi",
        "sub": domain,
        "room": room,
        "iat": now,
        "nbf": now - 10,
        "exp": now + ttl_seconds,
        "context": {
            "user": {
                "id": str(user.id),
                "name": user.get_full_name() or user.username,
                "email": user.email or "",
                "moderator": "true" if moderator else "false",
            },
        },
        "moderator": bool(moderator),
    }
    return jwt.encode(payload, secret, algorithm="HS256")
