"""
apps/notifications/mailer.py — Couche d'envoi unique, traçable et honnête.

RÈGLE
-----
Tout envoi passe par ce module (et, en dernier recours, par le backend
`TrackingEmailBackend` qui trace ce qui lui échapperait). Chaque message :

  1. est ENREGISTRÉ avant toute tentative (`EmailDelivery`), avec son
     contenu archivé (`EmailContent`) et ses pièces jointes
     (`EmailAttachment`, fichiers privés) ;
  2. est tenté ; chaque tentative est journalisée (`EmailDeliveryAttempt`)
     avec son résultat EXACT ;
  3. porte le TRANSPORT réellement utilisé : console, mémoire, serveur de
     test (Mailpit — capturé, jamais distribué), ou SMTP réel.

CE QUE CETTE COUCHE NE PRÉTEND PAS
----------------------------------
Elle ne dit jamais qu'un e-mail est ARRIVÉ. L'état le plus fort constatable
est « accepté par le serveur de messagerie ». Un message accepté par Mailpit
n'a quitté aucune machine : il est affiché comme « capturé ».

Les secrets SMTP ne sont jamais écrits dans le journal, les erreurs ou les
réponses d'API.
"""
import hashlib
import logging
import re
from datetime import timedelta

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.mail import EmailMultiAlternatives, get_connection
from django.utils import timezone

from .email_models import EmailAttachment, EmailContent, EmailDelivery, EmailDeliveryAttempt

logger = logging.getLogger("apps")

#: Délais des nouvelles tentatives automatiques, en minutes.
RETRY_DELAYS_MINUTES = (5, 30, 180)
#: Au-delà, échec définitif : une décision humaine est nécessaire.
MAX_ATTEMPTS = len(RETRY_DELAYS_MINUTES) + 1

TRACKING_HEADER = "X-FEBA-Tracking-Id"
TRACKING_BACKEND = "apps.notifications.backends.TrackingEmailBackend"

#: Hôtes de serveurs de CAPTURE (développement) : un message accepté par
#: eux n'est jamais distribué. Complétable par EMAIL_CAPTURE_HOSTS.
DEFAULT_CAPTURE_HOSTS = {"mailpit", "mailhog", "mailcatcher", "smtp4dev", "maildev"}


# ── Transport ─────────────────────────────────────────────────────────

def transport_backend():
    """Backend de TRANSPORT effectif (celui qu'enveloppe le backend de traçage)."""
    backend = getattr(settings, "EMAIL_BACKEND", "") or ""
    if backend == TRACKING_BACKEND:
        return (getattr(settings, "EMAIL_TRANSPORT_BACKEND", "")
                or "django.core.mail.backends.console.EmailBackend")
    return backend


def capture_hosts():
    extra = getattr(settings, "EMAIL_CAPTURE_HOSTS", "") or ""
    if isinstance(extra, str):
        extra = [h.strip() for h in extra.split(",") if h.strip()]
    return DEFAULT_CAPTURE_HOSTS | {h.lower() for h in extra}


def current_transport():
    """
    Ce que deviendra réellement un message envoyé maintenant.

    `EMAIL_DELIVERY_MODE` (auto | capture | real) force la qualification
    d'un hôte que l'heuristique ne reconnaîtrait pas.
    """
    backend = transport_backend().lower()
    if "console" in backend:
        return EmailDelivery.TRANSPORT_CONSOLE
    if "locmem" in backend or "dummy" in backend:
        return EmailDelivery.TRANSPORT_MEMORY
    if "filebased" in backend:
        return EmailDelivery.TRANSPORT_FILE
    if "smtp" in backend:
        host = (getattr(settings, "EMAIL_HOST", "") or "").strip().lower()
        if not host:
            return EmailDelivery.TRANSPORT_UNCONFIGURED
        mode = (getattr(settings, "EMAIL_DELIVERY_MODE", "auto") or "auto").lower()
        if mode == "capture":
            return EmailDelivery.TRANSPORT_CAPTURE
        if mode == "real":
            return EmailDelivery.TRANSPORT_SMTP
        if host in capture_hosts():
            return EmailDelivery.TRANSPORT_CAPTURE
        return EmailDelivery.TRANSPORT_SMTP
    return EmailDelivery.TRANSPORT_OTHER


def smtp_target():
    """`hôte:port` visé, sans aucune donnée d'authentification."""
    if "smtp" not in transport_backend().lower():
        return ""
    host = getattr(settings, "EMAIL_HOST", "") or ""
    return f"{host}:{getattr(settings, 'EMAIL_PORT', '')}" if host else ""


def provider_is_configured():
    """Vrai seulement si un VRAI serveur de messagerie est configuré."""
    return current_transport() in EmailDelivery.REAL_TRANSPORTS


def sender_for(entity):
    """Adresse d'expédition propre à l'académie (sinon DEFAULT_FROM_EMAIL)."""
    code = getattr(entity, "code", "") or ""
    specific = {
        "FEBA": getattr(settings, "FEBA_FROM_EMAIL", ""),
        "FEBA_FHA": getattr(settings, "FHA_FROM_EMAIL", ""),
    }.get(code, "")
    return specific or getattr(settings, "DEFAULT_FROM_EMAIL", "") or ""


# ── Expurgation des secrets ───────────────────────────────────────────

_SECRET_URL = re.compile(
    r"https?://\S*(?:reset|password|token|activate|confirm|verify|magic|invitation|uid)\S*",
    re.IGNORECASE,
)
_SECRET_PARAM = re.compile(r"(?i)\b(token|code|key|password|pwd|secret)=([^\s&\"'<]+)")
REDACTED_LINK = "[lien de sécurité masqué dans l'archive]"


def redact(text):
    """Masque liens et paramètres porteurs de secrets. Renvoie (texte, modifié)."""
    if not text:
        return text, False
    new = _SECRET_URL.sub(REDACTED_LINK, text)
    new = _SECRET_PARAM.sub(lambda m: f"{m.group(1)}=[masqué]", new)
    return new, new != text


# ── Archivage ─────────────────────────────────────────────────────────

def create_content(*, subject, text_body, html_body=None, attachments=None, sensitive=False):
    """
    Archive le contenu et ses pièces jointes.

    `attachments` : liste de (nom, octets, type MIME).
    `sensitive` : expurgation des liens et jetons de sécurité dans l'archive.
    """
    text, red1 = redact(text_body or "") if sensitive else (text_body or "", False)
    html, red2 = redact(html_body or "") if sensitive else (html_body or "", False)
    redacted = bool(sensitive and (red1 or red2))
    content = EmailContent.objects.create(
        subject=(subject or "")[:255], text_body=text, html_body=html, is_redacted=redacted,
        redaction_note="Liens et jetons de sécurité masqués dans l'archive." if redacted else "",
    )
    for item in attachments or []:
        store_attachment(content, *item)
    return content


def store_attachment(content, name, data, mimetype):
    from .attachments import safe_filename

    digest = hashlib.sha256(data).hexdigest()
    name = safe_filename(name)
    existing = content.attachments.filter(sha256=digest, original_name=name).first()
    if existing is not None:
        return existing
    attachment = EmailAttachment(
        content=content, original_name=name, content_type=mimetype or "application/octet-stream",
        size=len(data), sha256=digest,
    )
    attachment.file.save(name, ContentFile(data), save=False)
    attachment.save()
    return attachment


def create_delivery(*, purpose, to_email, subject, text_body="", html_body=None, entity=None,
                    reference="", language="", cc=None, attachments=None, reply_to=None,
                    content=None, initiated_by=None, sensitive=False,
                    status=EmailDelivery.QUEUED):
    """Enregistre un envoi (et son contenu) SANS le tenter."""
    if content is None:
        content = create_content(subject=subject, text_body=text_body, html_body=html_body,
                                 attachments=attachments, sensitive=sensitive)
    return EmailDelivery.objects.create(
        entity=entity, purpose=purpose, subject_reference=(reference or "")[:64],
        to_email=to_email, cc_emails=list(cc or []), from_email=sender_for(entity),
        reply_to=reply_to or getattr(settings, "EMAIL_REPLY_TO", "") or "",
        subject=(content.subject or subject or "")[:255], language=language or "",
        backend=transport_backend(), transport=current_transport(), smtp_host=smtp_target(),
        content=content, initiated_by=initiated_by, status=status,
    )


# ── Envoi ─────────────────────────────────────────────────────────────

def send_tracked_email(*, purpose, to_email, subject, text_body, html_body=None, entity=None,
                       reference="", language="", cc=None, attachments=None, reply_to=None,
                       initiated_by=None, sensitive=False):
    """
    Enregistre ET tente l'envoi. Ne lève JAMAIS : un échec d'envoi ne doit
    pas annuler l'opération métier qui l'a déclenché ; il est enregistré,
    visible et relançable.

    `sensitive` : le message part intact, mais son archive est expurgée.
    """
    delivery = create_delivery(
        purpose=purpose, to_email=to_email, subject=subject, text_body=text_body,
        html_body=html_body, entity=entity, reference=reference, language=language, cc=cc,
        attachments=attachments, reply_to=reply_to, initiated_by=initiated_by,
        sensitive=sensitive, status=EmailDelivery.PENDING,
    )
    live = (text_body, html_body) if sensitive else None
    return _attempt(delivery, live_bodies=live)


def deliver(delivery, *, manual=False):
    """
    Tente (ou retente) l'envoi d'un message ENREGISTRÉ, depuis son contenu
    archivé. `manual` : relance décidée par un humain — le compteur
    automatique repart de zéro ; l'historique des tentatives est conservé.
    """
    if manual:
        delivery.attempts = 0
    return _attempt(delivery, manual=manual)


def resend(delivery, text_body=None, html_body=None, attachments=None, initiated_by=None):
    """
    Renvoi MANUEL : crée un NOUVEL envoi ; le précédent reste visible dans
    la boîte d'envoi. Sans nouveaux corps, le contenu archivé est réutilisé.
    """
    content = delivery.content
    if text_body is not None or content is None:
        content = create_content(subject=delivery.subject, text_body=text_body or "",
                                 html_body=html_body, attachments=attachments)
    new = create_delivery(
        purpose=delivery.purpose, to_email=delivery.to_email, subject=delivery.subject,
        entity=delivery.entity, reference=delivery.subject_reference, language=delivery.language,
        cc=delivery.cc_emails, reply_to=delivery.reply_to or None, content=content,
        initiated_by=initiated_by, status=EmailDelivery.PENDING,
    )
    return _attempt(new, manual=True)


def retry_due(delivery):
    """Nouvelle tentative AUTOMATIQUE (le compteur n'est pas remis à zéro)."""
    return _attempt(delivery)


def build_message(delivery, live_bodies=None):
    """Message reconstruit depuis l'archive (ou les corps fournis)."""
    content = delivery.content
    if live_bodies is not None:
        text_body, html_body = live_bodies
    elif content is not None:
        text_body, html_body = content.text_body, content.html_body
    else:
        raise LookupError("Contenu non archivé pour cet envoi historique : impossible de le rejouer.")
    message = EmailMultiAlternatives(
        subject=delivery.subject,
        body=text_body or "",
        from_email=delivery.from_email or None,
        to=[delivery.to_email],
        cc=list(delivery.cc_emails or []) or None,
        reply_to=[delivery.reply_to] if delivery.reply_to else None,
        headers={TRACKING_HEADER: str(delivery.tracking_id)},
    )
    if html_body:
        message.attach_alternative(html_body, "text/html")
    if content is not None:
        for attachment in content.attachments.all():
            # Fichier manquant → échec explicite : partir sans la pièce
            # annoncée serait un succès mensonger.
            message.attach(attachment.original_name, attachment.read_bytes(), attachment.content_type)
    return message


def _attempt(delivery, *, manual=False, live_bodies=None):
    """Une tentative. Met à jour l'état et l'historique ; ne lève pas."""
    now = timezone.now()
    delivery.attempts += 1
    delivery.status = EmailDelivery.PENDING
    delivery.backend = transport_backend()
    delivery.transport = current_transport()
    delivery.smtp_host = smtp_target()
    delivery.last_attempt_at = now
    error, permanent = "", False
    try:
        message = build_message(delivery, live_bodies)
        message.connection = get_connection(fail_silently=False)
        accepted = message.send()
        try:
            delivery.message_id = (message.message().get("Message-ID") or "")[:255]
        except Exception:  # pragma: no cover — en-tête purement informatif
            pass
        if not accepted:
            error = "Le backend d'envoi a accepté 0 message sans signaler d'erreur."
    except LookupError as exc:
        error, permanent = str(exc), True
    except Exception as exc:
        # Erreur EXACTE conservée (jamais de secret : le mot de passe n'est
        # pas dans les messages d'erreur SMTP).
        error = f"{type(exc).__name__}: {exc}"[:2000]

    if error:
        delivery.last_error = error
        _schedule_retry_or_fail(delivery, permanent=permanent)
        logger.warning("E-mail %s → %s : échec (tentative %d/%d) — %s",
                       delivery.purpose, delivery.to_email, delivery.attempts, MAX_ATTEMPTS, error)
    else:
        delivery.status = EmailDelivery.SENT
        delivery.sent_at = now
        delivery.next_retry_at = None
        delivery.last_error = ""
        logger.info("E-mail %s → %s : accepté (%s %s, suivi %s)", delivery.purpose,
                    delivery.to_email, delivery.transport, delivery.smtp_host, delivery.tracking_id)
    delivery.save()
    EmailDeliveryAttempt.objects.create(
        delivery=delivery, outcome=delivery.status, transport=delivery.transport,
        smtp_host=delivery.smtp_host, error=error, manual=manual,
    )
    return delivery


def _schedule_retry_or_fail(delivery, permanent=False):
    if not permanent and delivery.attempts < MAX_ATTEMPTS:
        minutes = RETRY_DELAYS_MINUTES[delivery.attempts - 1]
        delivery.status = EmailDelivery.RETRY
        delivery.next_retry_at = timezone.now() + timedelta(minutes=minutes)
    else:
        delivery.status = EmailDelivery.FAILED
        delivery.next_retry_at = None
