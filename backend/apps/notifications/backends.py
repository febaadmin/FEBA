"""
apps/notifications/backends.py — Backend Django qui TRACE tout envoi.

`EMAIL_BACKEND` vaut ce backend ; le transport réel (SMTP, console…) est
`EMAIL_TRANSPORT_BACKEND`, lu dans l'environnement sous le nom habituel
`EMAIL_BACKEND` (voir settings/base.py).

- Un message émis par `mailer` porte l'en-tête X-FEBA-Tracking-Id : il est
  déjà journalisé, on le transmet tel quel.
- Tout AUTRE message (un futur module qui appellerait `send_mail`, un
  e-mail de Django lui-même) est journalisé ici, un enregistrement par
  destinataire, contenu archivé et EXPURGÉ des liens de sécurité, puis
  transmis. Aucun module ne peut donc envoyer sans laisser de trace.
"""
import logging

from django.core.mail import get_connection
from django.core.mail.backends.base import BaseEmailBackend
from django.utils import timezone

logger = logging.getLogger("apps")


class TrackingEmailBackend(BaseEmailBackend):
    def __init__(self, fail_silently=False, **kwargs):
        super().__init__(fail_silently=fail_silently)
        from .mailer import transport_backend

        self.inner = get_connection(transport_backend(), fail_silently=fail_silently, **kwargs)

    def open(self):
        return self.inner.open()

    def close(self):
        return self.inner.close()

    def send_messages(self, email_messages):
        from .mailer import TRACKING_HEADER

        total = 0
        for message in email_messages or []:
            if TRACKING_HEADER in (message.extra_headers or {}):
                total += self.inner.send_messages([message]) or 0
                continue
            total += self._send_untracked(message)
        return total

    def _send_untracked(self, message):
        from django.conf import settings

        from .email_models import EmailDelivery
        from .mailer import create_content, current_transport, normalize_sender, smtp_target, transport_backend

        # Même règle d'expéditeur que la couche centrale : jamais l'adresse
        # retirée, quel que soit le module qui a construit le message.
        message.from_email = normalize_sender(message.from_email or settings.DEFAULT_FROM_EMAIL)

        html = ""
        for alt_content, mimetype in getattr(message, "alternatives", []) or []:
            if mimetype == "text/html":
                html = alt_content
        attachments = []
        for item in message.attachments or []:
            if isinstance(item, tuple) and len(item) == 3 and isinstance(item[1], (bytes, str)):
                data = item[1].encode() if isinstance(item[1], str) else item[1]
                attachments.append((item[0] or "piece-jointe", data, item[2] or "application/octet-stream"))
        content = create_content(subject=message.subject, text_body=message.body, html_body=html,
                                 attachments=attachments, sensitive=True)
        deliveries = [
            EmailDelivery.objects.create(
                purpose="untracked_module", to_email=address, subject=(message.subject or "")[:255],
                from_email=message.from_email or "", backend=transport_backend(),
                transport=current_transport(), smtp_host=smtp_target(), content=content,
                status=EmailDelivery.PENDING, attempts=1, last_attempt_at=timezone.now(),
            )
            for address in list(message.to or []) + list(message.cc or []) + list(message.bcc or [])
        ]
        # Copie SMS, comme pour tout autre e-mail (le contenu archivé est
        # expurgé s'il porte un lien de sécurité : le SMS est alors exclu).
        from .sms import schedule_for_email
        for delivery in deliveries:
            try:
                schedule_for_email(delivery)
            except Exception:
                logger.exception("SMS miroir de l'envoi %s non enregistré.", delivery.pk)
        error = ""
        sent = 0
        try:
            sent = self.inner.send_messages([message]) or 0
            if not sent:
                error = "Le backend d'envoi a accepté 0 message sans signaler d'erreur."
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"[:2000]
            if not self.fail_silently:
                self._record(deliveries, error)
                raise
        self._record(deliveries, error)
        if error:
            logger.warning("E-mail hors couche centrale (%s) : échec — %s", message.subject, error)
        return sent

    @staticmethod
    def _record(deliveries, error):
        from .email_models import EmailDelivery, EmailDeliveryAttempt

        now = timezone.now()
        for delivery in deliveries:
            delivery.status = EmailDelivery.FAILED if error else EmailDelivery.SENT
            delivery.last_error = error
            delivery.sent_at = None if error else now
            delivery.save(update_fields=["status", "last_error", "sent_at", "updated_at"])
            EmailDeliveryAttempt.objects.create(
                delivery=delivery, outcome=delivery.status, transport=delivery.transport,
                smtp_host=delivery.smtp_host, error=error,
            )
