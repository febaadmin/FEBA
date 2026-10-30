"""
apps/virtualclass/plugnmeet.py — client SERVEUR de l'API plugNmeet (v2.5).

Protocole (documentation officielle et code source plugNmeet-server
v2.5.3, vérifiés contre une instance réelle) :

- Toutes les méthodes : POST <serveur>/auth/<méthode>, corps JSON.
- En-têtes : `API-KEY` et `HASH-SIGNATURE` = HMAC-SHA256 du corps EXACT
  envoyé, clé = secret de l'API, en hexadécimal minuscule.
- Webhooks : en-tête `Hash-Token` (copie de `Authorization`) = JWT HS256
  signé avec le secret de l'API, émetteur = clé de l'API, revendication
  `sha256` = base64(SHA-256(corps)), validité 5 minutes.

La clé et le secret ne quittent JAMAIS le backend : le navigateur ne
reçoit qu'un jeton d'adhésion de courte durée (10 min), émis après le contrôle
des permissions FEBA.
"""
import base64
import hashlib
import hmac
import json
import logging
import urllib.error
import urllib.request

from django.conf import settings

logger = logging.getLogger("apps")

#: Préfixe des identités FEBA dans plugNmeet. Toute autre identité
#: (robot d'enregistrement, diffusion RTMP) n'est pas un utilisateur FEBA.
IDENTITY_PREFIX = "feba-"
#: plugNmeet limite room_id à 64 caractères (colonne `roomId`).
MAX_ROOM_ID = 64


class PlugNmeetError(RuntimeError):
    """Réponse négative de plugNmeet (status false)."""

    def __init__(self, message, status_code=""):
        super().__init__(message)
        self.status_code = status_code


class PlugNmeetUnavailable(PlugNmeetError):
    """Serveur injoignable, délai dépassé, erreur 5xx ou non configuré."""


class PlugNmeetNotConfigured(PlugNmeetUnavailable):
    """URL, clé ou secret de l'API manquant."""


def is_configured():
    return bool(settings.PLUGNMEET_SERVER_URL and settings.PLUGNMEET_API_KEY
                and settings.PLUGNMEET_API_SECRET)


def public_url():
    return settings.PLUGNMEET_SERVER_URL.rstrip("/")


def api_base():
    return (settings.PLUGNMEET_INTERNAL_URL or settings.PLUGNMEET_SERVER_URL).rstrip("/")


def sign(raw: bytes) -> str:
    return hmac.new(settings.PLUGNMEET_API_SECRET.encode(), raw, hashlib.sha256).hexdigest()


def call(method, body, timeout=None):
    """
    Appel signé. Renvoie le dictionnaire de réponse si `status` est vrai.

    Lève `PlugNmeetUnavailable` (réseau, délai, 5xx, réponse illisible) ou
    `PlugNmeetError` (refus métier, signature refusée). Le secret n'apparaît
    dans aucun message d'erreur.
    """
    if not is_configured():
        raise PlugNmeetNotConfigured(
            "plugNmeet n'est pas configuré (PLUGNMEET_SERVER_URL, PLUGNMEET_API_KEY, "
            "PLUGNMEET_API_SECRET)."
        )
    raw = json.dumps(body, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        f"{api_base()}/auth{method}", data=raw, method="POST",
        headers={"API-KEY": settings.PLUGNMEET_API_KEY, "HASH-SIGNATURE": sign(raw),
                 "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout or settings.PLUGNMEET_TIMEOUT) as response:
            payload = response.read()
    except urllib.error.HTTPError as exc:
        text = exc.read()[:500].decode("utf-8", "replace")
        if exc.code >= 500:
            raise PlugNmeetUnavailable(f"plugNmeet {method} : HTTP {exc.code}") from exc
        try:
            data = json.loads(text)
        except ValueError:
            data = {}
        raise PlugNmeetError(data.get("msg") or f"plugNmeet {method} : HTTP {exc.code}",
                             data.get("status_code", "")) from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise PlugNmeetUnavailable(f"plugNmeet injoignable ({method}) : {exc}") from exc
    try:
        data = json.loads(payload)
    except ValueError as exc:
        raise PlugNmeetUnavailable(f"Réponse illisible de plugNmeet ({method}).") from exc
    if not data.get("status"):
        raise PlugNmeetError(data.get("msg") or "Refus de plugNmeet.", data.get("status_code", ""))
    return data


# ── Identifiants ──────────────────────────────────────────────────────

def room_id_for(room):
    """Identifiant plugNmeet de la salle FEBA (stable, ≤ 64 caractères)."""
    code = room.room_code
    if len(code) <= MAX_ROOM_ID:
        return code
    digest = hashlib.sha256(code.encode()).hexdigest()[:16]
    return f"{code[:MAX_ROOM_ID - 17]}-{digest}"


def identity_for(user):
    return f"{IDENTITY_PREFIX}{user.pk}"


def user_pk_from_identity(identity):
    if not identity or not identity.startswith(IDENTITY_PREFIX):
        return None
    tail = identity[len(IDENTITY_PREFIX):]
    return int(tail) if tail.isdigit() else None


# ── Salles ────────────────────────────────────────────────────────────

def room_features(room):
    """
    Fonctions de la salle, TOUTES déclarées explicitement.

    Vérifié sur l'instance : une fonction omise est ACTIVÉE par défaut
    (diffusion RTMP, ingress, sous-blocs IA). Ne rien laisser au défaut,
    c'est ne proposer que ce qui fonctionne réellement.
    """
    recording = bool(settings.PLUGNMEET_RECORDING_ENABLED and room.allow_recording)
    rtmp = bool(settings.PLUGNMEET_RTMP_ENABLED)
    insights = bool(settings.PLUGNMEET_INSIGHTS_ENABLED)
    duration = settings.PLUGNMEET_MAX_ROOM_MINUTES or 0
    return {
        "allow_webcams": True,
        "mute_on_start": True,
        "allow_screen_share": True,
        "admin_only_webcams": False,
        "allow_view_other_webcams": True,
        "allow_view_other_users_list": True,
        "allow_raise_hand": True,
        "allow_virtual_bg": True,
        "enable_analytics": True,
        "auto_gen_user_id": False,
        "room_duration": duration,
        "recording_features": {
            "is_allow": recording, "is_allow_cloud": recording,
            # Enregistrement LOCAL (sur le poste du participant) refusé :
            # une classe de mineurs ne s'enregistre pas hors du serveur.
            "is_allow_local": False,
            "enable_auto_cloud_recording": False,
            "only_record_admin_webcams": False,
        },
        "chat_features": {"is_allow": True, "is_allow_file_upload": True},
        # Le bloc-notes partagé exige un serveur Etherpad (shared_notepad dans
        # la configuration de plugNmeet), non installé : bouton sans effet.
        "shared_note_pad_features": {"is_allow": settings.PLUGNMEET_SHARED_NOTEPAD_ENABLED},
        "whiteboard_features": {"is_allow": True},
        "external_media_player_features": {"is_allow": True},
        "external_broadcasting_features": {"is_allow": rtmp, "is_allow_rtmp": rtmp},
        "waiting_room_features": {"is_active": bool(room.lobby_enabled)},
        "breakout_room_features": {"is_allow": True, "allowed_number_rooms": 6,
                                   "allow_return_to_main_room": True, "allow_self_select": False},
        "display_external_link_features": {"is_allow": True},
        # Ingress (flux entrant RTMP/WHIP) : service livekit-ingress non déployé.
        "ingress_features": {"is_allow": False},
        "polls_features": {"is_allow": True},
        "insights_features": {
            "is_allow": insights,
            "transcription_features": {"is_allow": insights, "is_allow_translation": insights,
                                       "is_allow_speech_synthesis": insights},
            "chat_translation_features": {"is_allow": insights},
            "ai_features": {"is_allow": insights,
                            "ai_text_chat_features": {"is_allow": insights},
                            "meeting_summarization_features": {"is_allow": insights}},
        },
        "sip_dial_in_features": {"is_allow": False},
        "end_to_end_encryption_features": {"is_enabled": False},
    }


def create_room(room):
    """
    Crée la réunion (ou retrouve la réunion en cours). Renvoie `room_info`.
    """
    metadata = {
        "room_title": room.name[:255],
        "welcome_message": (room.description or "")[:1000],
        "room_features": room_features(room),
        "default_lock_settings": {
            # Les élèves ne partagent pas leur écran, n'écrivent pas au
            # tableau et ne modifient pas les notes tant que l'enseignant
            # ne l'a pas autorisé (réglable en direct par le modérateur).
            "lock_screen_sharing": True,
            "lock_whiteboard": True,
            "lock_shared_notepad": True,
        },
        "copyright_conf": {"display": True, "text": "FEBA"},
        "extra_data": {"feba_room": str(room.pk), "academy": getattr(room.school, "code", "") or ""},
    }
    if settings.PLUGNMEET_WEBHOOK_URL:
        metadata["webhook_url"] = settings.PLUGNMEET_WEBHOOK_URL
    base = (settings.PUBLIC_BASE_URL or "").rstrip("/")
    if base:
        metadata["logout_url"] = f"{base}/virtual-room/{room.pk}/ended"
    body = {"room_id": room_id_for(room), "metadata": metadata,
            # Réunion vide pendant 10 minutes → fermée par plugNmeet.
            "empty_timeout": 600}
    return call("/room/create", body).get("room_info") or {}


def join_token(room, user, *, is_admin, lang="fr"):
    """Jeton d'adhésion valable 10 min (client.token_validity), à consommer
    immédiatement. plugNmeet ne le rend PAS à usage unique : le même lien
    rouvre la salle tant qu'il est valide (vérifié le 30/10/2026)."""
    name = (user.get_full_name() or user.username or "Participant")[:100]
    body = {
        "room_id": room_id_for(room),
        "user_info": {
            "name": name,
            "user_id": identity_for(user),
            "is_admin": bool(is_admin),
            "is_hidden": False,
            "user_metadata": {
                "preferred_lang": "fr" if lang not in ("fr", "en") else lang,
                "extra_data": {"role": getattr(user, "role", "") or ""},
            },
        },
    }
    return call("/room/getJoinToken", body)["token"]


#: Un onglet rechargé longtemps après l'entrée présente un jeton expiré mais
#: authentique : il sert encore à retrouver l'académie de la salle (pas à
#: entrer dans la réunion, que plugNmeet contrôle lui-même).
BRANDING_TOKEN_MAX_AGE = 24 * 3600


def room_for_join_token(token):
    """
    Salle FEBA désignée par un jeton d'adhésion plugNmeet AUTHENTIQUE.

    Le jeton est un JWT HS256 signé avec le secret de l'API : sa signature
    et son émetteur sont vérifiés ; un jeton modifié (autre `room_id`) est
    refusé. Retourne la salle, ou None.
    """
    import time
    import jwt
    from .models import VirtualRoom

    if not token or not is_configured():
        return None
    try:
        claims = jwt.decode(token, settings.PLUGNMEET_API_SECRET, algorithms=["HS256"],
                            issuer=settings.PLUGNMEET_API_KEY,
                            options={"require": ["exp", "iss"], "verify_exp": False})
    except jwt.PyJWTError:
        return None
    if claims["exp"] < time.time() - BRANDING_TOKEN_MAX_AGE:
        return None
    room_id = str(claims.get("room_id") or "")
    if not room_id:
        return None
    room = VirtualRoom.objects.select_related("school").filter(room_code=room_id).first()
    if room is None and len(room_id) == MAX_ROOM_ID:
        for candidate in VirtualRoom.objects.select_related("school").filter(
                room_code__startswith=room_id[:MAX_ROOM_ID - 17]):
            if room_id_for(candidate) == room_id:
                return candidate
    return room


def join_url(token):
    from urllib.parse import quote

    return f"{public_url()}/?access_token={quote(token, safe='')}"


def is_room_active(room):
    return bool(call("/room/isRoomActive", {"room_id": room_id_for(room)}).get("is_active"))


#: Codes plugNmeet signifiant « aucune réunion en cours » (v2.5.3 : ROOM_NOT_FOUND).
NOT_ACTIVE_CODES = {"ROOM_NOT_FOUND", "ROOM_NOT_ACTIVE", "NOT_FOUND"}
#: plugNmeet attend jusqu'à 30 s que les participants se déconnectent avant
#: de répondre à endRoom (constaté sur v2.5.3) : délai propre à cet appel.
END_ROOM_TIMEOUT = 45


def end_room(room):
    """
    Ferme la réunion. Une réunion déjà inactive n'est pas une erreur.

    On demande d'abord si elle est active : sur v2.5.3, endRoom appelé sur
    une réunion déjà fermée met ~12 s à répondre ROOM_NOT_FOUND (mesuré).
    """
    if not is_room_active(room):
        return False
    try:
        call("/room/endRoom", {"room_id": room_id_for(room)}, timeout=END_ROOM_TIMEOUT)
        return True
    except PlugNmeetError as exc:
        if isinstance(exc, PlugNmeetUnavailable):
            raise
        if exc.status_code in NOT_ACTIVE_CODES or "not active" in str(exc).lower():
            return False
        raise


def fetch_recordings(room, limit=50):
    data = call("/recording/fetch", {"room_ids": [room_id_for(room)], "from": 0,
                                     "limit": limit, "order_by": "DESC"})
    result = data.get("result") or {}
    return result.get("recordings_list") or []


def recording_info(record_id):
    data = call("/recording/info", {"record_id": record_id})
    return data.get("recording_info") or {}


def recording_download_url(record_id):
    data = call("/recording/getDownloadToken", {"record_id": record_id})
    return f"{public_url()}/download/recording/{data['token']}"


# ── Webhooks ──────────────────────────────────────────────────────────

class WebhookRejected(ValueError):
    pass


def verify_webhook(body: bytes, token: str):
    """
    Vérifie un webhook plugNmeet (même schéma que LiveKit) et renvoie
    l'événement décodé. Lève `WebhookRejected` sinon.
    """
    import jwt

    if not is_configured():
        raise WebhookRejected("plugNmeet non configuré.")
    if not token:
        raise WebhookRejected("En-tête Hash-Token absent.")
    try:
        claims = jwt.decode(
            token, settings.PLUGNMEET_API_SECRET, algorithms=["HS256"],
            issuer=settings.PLUGNMEET_API_KEY, options={"require": ["exp", "iss"]},
            leeway=30,
        )
    except jwt.PyJWTError as exc:
        raise WebhookRejected(f"Jeton refusé : {exc}") from exc
    expected = base64.b64encode(hashlib.sha256(body).digest()).decode()
    if not hmac.compare_digest(str(claims.get("sha256", "")), expected):
        raise WebhookRejected("Empreinte du corps différente.")
    try:
        return json.loads(body)
    except ValueError as exc:
        raise WebhookRejected("Corps illisible.") from exc


def health(timeout=5):
    """
    État de plugNmeet : « operational », « degraded » ou « unavailable ».
    Ne lève jamais (alimente l'écran de diagnostic).
    """
    result = {"status": "unavailable", "provider": "plugnmeet", "configured": is_configured(),
              "server_url": public_url() if settings.PLUGNMEET_SERVER_URL else "",
              "checks": [], "detail": ""}

    def record(name, ok, detail=""):
        result["checks"].append({"name": name, "ok": bool(ok), "detail": detail})

    if not result["configured"]:
        result["detail"] = ("plugNmeet n'est pas configuré : renseignez PLUGNMEET_SERVER_URL, "
                            "PLUGNMEET_API_KEY et PLUGNMEET_API_SECRET.")
        record("configuration", False, result["detail"])
        return result
    record("configuration", True, f"Serveur {result['server_url']}.")
    try:
        with urllib.request.urlopen(f"{api_base()}/healthCheck", timeout=timeout) as response:
            ok = response.status == 200
        record("service", ok, f"/healthCheck → HTTP {response.status}")
    except Exception as exc:  # noqa: BLE001 — diagnostic : ne jamais lever
        record("service", False, f"/healthCheck injoignable : {exc}")
        result["status"] = "degraded"
        result["detail"] = result["checks"][-1]["detail"]
        return result
    try:
        call("/room/isRoomActive", {"room_id": "feba-healthcheck"})
        record("api_signee", True, "Requête signée acceptée (clé et secret valides).")
    except PlugNmeetUnavailable as exc:
        record("api_signee", False, str(exc))
    except PlugNmeetError as exc:
        # « salle inactive » = signature acceptée ; seul un refus
        # d'authentification est une panne de configuration.
        ok = exc.status_code not in ("INVALID_TOKEN_OR_SIGNATURE", "INVALID_API_KEY")
        record("api_signee", ok, "Requête signée acceptée." if ok else f"Clé ou secret refusés : {exc}")
    except Exception as exc:  # noqa: BLE001
        record("api_signee", False, f"Contrôle impossible : {exc}")
    ok = all(c["ok"] for c in result["checks"])
    result["status"] = "operational" if ok else "degraded"
    result["detail"] = "Instance plugNmeet opérationnelle." if ok else next(
        c["detail"] for c in result["checks"] if not c["ok"])
    return result
