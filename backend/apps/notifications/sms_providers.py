"""
apps/notifications/sms_providers.py — transports SMS et calculs d'encodage.

Twilio (API REST 2010-04-01, documentation officielle) :
  POST https://api.twilio.com/2010-04-01/Accounts/{AccountSid}/Messages.json
  authentification HTTP Basic (AccountSid, AuthToken), champs To, From,
  Body, StatusCallback. Un message est limité à 1 600 caractères ; Twilio
  le découpe et le RECOMPOSE sur le téléphone (SMS concaténé).
  Accusés de remise : X-Twilio-Signature = base64(HMAC-SHA1(AuthToken,
  URL + paramètres POST triés, clé et valeur concaténées)).

`capture` et `console` n'envoient RIEN : le statut est « captured », jamais
« sent ». Aucun mode de test n'est présenté comme une remise réelle.
"""
import base64
import hashlib
import hmac
import json
import logging
import math
import urllib.error
import urllib.parse
import urllib.request
import uuid

from django.conf import settings

logger = logging.getLogger("apps")

TWILIO_API = "https://api.twilio.com/2010-04-01"
#: Limite d'un message Twilio (corps), au-delà : refus 21617.
PROVIDER_MAX_CHARS = 1600

GSM_BASIC = set(
    "@£$¥èéùìòÇ\nØø\rÅåΔ_ΦΓΛΩΠΨΣΘΞÆæßÉ !\"#¤%&'()*+,-./0123456789:;<=>?"
    "¡ABCDEFGHIJKLMNOPQRSTUVWXYZÄÖÑÜ§¿abcdefghijklmnopqrstuvwxyzäöñüà"
)
GSM_EXTENDED = set("^{}\\[~]|€\f")


def encoding_of(text):
    """« GSM-7 » si chaque caractère y existe, sinon « UCS-2 » (accents ê, ç, œ…)."""
    return "GSM-7" if all(c in GSM_BASIC or c in GSM_EXTENDED for c in text) else "UCS-2"


def segment_count(text):
    """Nombre de segments facturés (160/153 en GSM-7, 70/67 en UCS-2)."""
    if not text:
        return 0
    if encoding_of(text) == "GSM-7":
        units = sum(2 if c in GSM_EXTENDED else 1 for c in text)
        return 1 if units <= 160 else math.ceil(units / 153)
    units = len(text.encode("utf-16-le")) // 2
    return 1 if units <= 70 else math.ceil(units / 67)


def split_for_provider(text, limit=PROVIDER_MAX_CHARS):
    """
    Découpe un texte trop long en messages de `limit` caractères au plus,
    numérotés « (i/n) », SANS rien retrancher : la concaténation des
    parties (préfixes ôtés) redonne le texte exact.

    Coupure de préférence entre paragraphes, puis entre lignes, puis entre
    mots ; jamais au milieu d'un mot, sauf mot plus long que la limite.
    """
    if len(text) <= limit:
        return [text]
    # Réserve pour « (99/99) ».
    room = limit - 8
    parts, rest = [], text
    while rest:
        if len(rest) <= room:
            parts.append(rest)
            break
        window = rest[:room]
        cut = max(window.rfind("\n\n"), -1)
        if cut < room // 2:
            cut = window.rfind("\n")
        if cut < room // 2:
            cut = window.rfind(" ")
        if cut <= 0:
            cut = room
        else:
            cut += 1  # le séparateur reste dans la partie (rien n'est perdu)
        parts.append(rest[:cut])
        rest = rest[cut:]
    n = len(parts)
    return [f"({i}/{n}) {p}" for i, p in enumerate(parts, 1)]


def strip_part_prefix(part):
    import re
    return re.sub(r"^\(\d+/\d+\) ", "", part, count=1)


class SmsProviderError(Exception):
    """Refus ou panne du fournisseur. `permanent` : inutile de réessayer."""

    def __init__(self, message, *, code="", permanent=False, opt_out=False):
        super().__init__(message)
        self.code = str(code or "")
        self.permanent = permanent
        self.opt_out = opt_out


class SmsNotConfigured(SmsProviderError):
    pass


# Codes d'erreur Twilio (https://www.twilio.com/docs/api/errors) : refus
# DÉFINITIFS pour ce destinataire ou ce contenu. Les autres (429, 5xx,
# réseau) sont temporaires. L'authentification refusée (20003) est une
# erreur de CONFIGURATION : réessayée, pour partir une fois corrigée.
PERMANENT_TWILIO_CODES = {
    "21211": "Numéro du destinataire invalide",
    "21214": "Numéro du destinataire injoignable",
    "21408": "Envoi vers ce pays non autorisé sur le compte Twilio",
    "21606": "Le numéro d'expédition ne peut pas envoyer de SMS (ou n'appartient pas au compte)",
    "21612": "Acheminement impossible entre ces deux numéros",
    "21614": "Le destinataire n'est pas un numéro mobile",
    "21617": "Message trop long",
    "21659": "Le numéro d'expédition n'appartient pas au compte",
    "21610": "Le destinataire a demandé l'arrêt des SMS (STOP)",
}


class TwilioProvider:
    name = "twilio"

    def _auth(self):
        sid, token = settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN
        if not (sid and token):
            raise SmsNotConfigured("Twilio non configuré (TWILIO_ACCOUNT_SID / TWILIO_AUTH_TOKEN).",
                                   code="not_configured")
        return sid, "Basic " + base64.b64encode(f"{sid}:{token}".encode()).decode()

    def _request(self, method, path, data=None):
        sid, auth = self._auth()
        url = f"{TWILIO_API}/Accounts/{sid}{path}"
        body = urllib.parse.urlencode(data).encode() if data is not None else None
        req = urllib.request.Request(url, data=body, method=method, headers={
            "Authorization": auth, "Accept": "application/json",
            **({"Content-Type": "application/x-www-form-urlencoded"} if body else {}),
        })
        try:
            with urllib.request.urlopen(req, timeout=settings.SMS_TIMEOUT) as response:
                return json.loads(response.read() or b"{}")
        except urllib.error.HTTPError as exc:
            try:
                payload = json.loads(exc.read() or b"{}")
            except ValueError:
                payload = {}
            code = str(payload.get("code") or exc.code)
            message = payload.get("message") or f"HTTP {exc.code}"
            if exc.code in (401, 403) or code == "20003":
                raise SmsProviderError(f"Authentification Twilio refusée : {message}", code=code) from exc
            if exc.code == 429 or exc.code >= 500:
                raise SmsProviderError(f"Twilio indisponible ({exc.code}) : {message}", code=code) from exc
            label = PERMANENT_TWILIO_CODES.get(code)
            raise SmsProviderError(f"{label or 'Refus Twilio'} ({code}) : {message}", code=code,
                                   permanent=True, opt_out=(code == "21610")) from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise SmsProviderError(f"Twilio injoignable : {exc}", code="network") from exc

    def send(self, to, from_, body):
        data = {"To": to, "From": from_, "Body": body}
        if settings.SMS_STATUS_CALLBACK_URL:
            data["StatusCallback"] = settings.SMS_STATUS_CALLBACK_URL
        payload = self._request("POST", "/Messages.json", data)
        if payload.get("error_code"):
            raise SmsProviderError(f"Refus Twilio ({payload['error_code']}) : {payload.get('error_message')}",
                                   code=payload["error_code"], permanent=True)
        return payload.get("sid", ""), payload.get("status", "queued")

    def verify_sender(self, number):
        """
        Le numéro appartient-il au compte, et peut-il envoyer des SMS ?
        Renvoie {"owned": bool, "sms": bool|None, "detail": str}.
        """
        query = urllib.parse.urlencode({"PhoneNumber": number})
        payload = self._request("GET", f"/IncomingPhoneNumbers.json?{query}")
        numbers = payload.get("incoming_phone_numbers") or []
        if not numbers:
            return {"owned": False, "sms": None,
                    "detail": f"{number} n'appartient pas à ce compte Twilio."}
        caps = numbers[0].get("capabilities") or {}
        sms = bool(caps.get("sms") or caps.get("SMS"))
        return {"owned": True, "sms": sms,
                "detail": f"{number} appartient au compte ; SMS {'autorisés' if sms else 'NON autorisés'}."}


class CaptureProvider:
    """Développement et tests : rien ne part ; le SMS est conservé dans FEBA."""
    name = "capture"
    captured = True

    def send(self, to, from_, body):
        return f"capture-{uuid.uuid4().hex[:16]}", "captured"

    def verify_sender(self, number):
        return {"owned": False, "sms": None, "detail": "Transport de capture : aucun fournisseur réel."}


class ConsoleProvider(CaptureProvider):
    name = "console"

    def send(self, to, from_, body):
        logger.info("SMS (console, NON envoyé) %s → %s : %s", from_, to, body[:200])
        return f"console-{uuid.uuid4().hex[:16]}", "captured"


def get_provider():
    name = (settings.SMS_PROVIDER or "capture").lower()
    return {"twilio": TwilioProvider, "capture": CaptureProvider, "console": ConsoleProvider}.get(
        name, CaptureProvider)()


def twilio_signature_valid(url, params, signature):
    """Vérifie X-Twilio-Signature (HMAC-SHA1 du jeton d'authentification)."""
    token = settings.TWILIO_AUTH_TOKEN
    if not (token and signature):
        return False
    data = url + "".join(f"{k}{params[k]}" for k in sorted(params))
    expected = base64.b64encode(hmac.new(token.encode(), data.encode(), hashlib.sha1).digest()).decode()
    return hmac.compare_digest(expected, signature)
