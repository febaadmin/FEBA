"""
apps/notifications/mailer.py — Couche d'envoi unique, traçable et honnête.

RÈGLE
-----
Aucun appel direct à `send_mail` ailleurs dans le projet. Tout passe par
`send_tracked_email()`, qui enregistre l'envoi AVANT de tenter quoi que ce
soit et met à jour son état ensuite. Un envoi non journalisé est un envoi
dont personne ne peut dire s'il a eu lieu.

CE QUI A CHANGÉ
---------------
`fail_silently=True` a disparu. Il transformait un serveur SMTP injoignable
en succès silencieux : l'écran public annonçait « vous recevrez un e-mail »
et l'administration n'avait aucune trace de l'échec. L'erreur est
désormais capturée, journalisée, exposée, et l'écran public ne parle
d'e-mail qu'après avoir vu le résultat.

CE QUE CETTE COUCHE NE PRÉTEND PAS
----------------------------------
Elle ne dit jamais qu'un e-mail est ARRIVÉ. Elle sait seulement si le
backend d'envoi l'a accepté sans erreur. Sur une installation sans
fournisseur configuré (backend `console` ou `locmem`), `used_real_provider`
vaut faux et les rapports doivent le refléter : douze e-mails écrits dans
la console ne sont pas douze e-mails envoyés.
"""
import logging

from django.conf import settings
from django.core.mail import EmailMultiAlternatives, get_connection
from django.utils import timezone

from .email_models import EmailDelivery

logger = logging.getLogger("apps")

#: Délais des nouvelles tentatives, en minutes. Croissants : un serveur
#: momentanément indisponible se remet rarement en dix secondes, et
#: marteler une adresse refusée ne la rend pas valide.
RETRY_DELAYS_MINUTES = (5, 30, 180)

#: Au-delà, on cesse d'essayer et on laisse la main à l'administration.
#: Une adresse mal saisie ne deviendra jamais correcte toute seule ; c'est
#: un humain qui doit la corriger.
MAX_ATTEMPTS = len(RETRY_DELAYS_MINUTES) + 1


def sender_for(entity):
    """
    Adresse d'expédition de cette académie.

    Chaque académie peut avoir la sienne (`FEBA_FROM_EMAIL`,
    `FHA_FROM_EMAIL`) : un parent de l'académie en ligne ne doit pas
    recevoir un message venant de l'adresse de l'école présentielle.
    """
    code = getattr(entity, "code", "") or ""
    specific = {
        "FEBA": getattr(settings, "FEBA_FROM_EMAIL", ""),
        "FEBA_FHA": getattr(settings, "FHA_FROM_EMAIL", ""),
    }.get(code, "")
    return specific or getattr(settings, "DEFAULT_FROM_EMAIL", "") or ""


def provider_is_configured():
    """
    Vrai si un fournisseur d'envoi réel est configuré.

    Sert aux rapports et aux écrans : sans fournisseur, on n'annonce pas
    un envoi externe. Le message reste enregistré, visible, relançable.
    """
    backend = (getattr(settings, "EMAIL_BACKEND", "") or "").lower()
    if any(marker in backend for marker in
           ("console", "locmem", "dummy", "filebased")):
        return False
    if "smtp" in backend:
        return bool(getattr(settings, "EMAIL_HOST", ""))
    # Backend tiers (API d'un prestataire) : on ne peut pas en juger ici.
    return True


def send_tracked_email(*, purpose, to_email, subject, text_body,
                       html_body=None, entity=None, reference="",
                       language="", cc=None, attachments=None,
                       reply_to=None):
    """
    Envoie un e-mail et renvoie la ligne de journal correspondante.

    Ne lève JAMAIS : un échec d'envoi ne doit pas annuler l'opération
    métier qui l'a déclenché. Une fiche d'inscription enregistrée reste
    enregistrée même si l'accusé de réception ne part pas — la perdre pour
    cette raison serait bien pire. L'échec est enregistré, visible, et une
    action de renvoi est offerte à l'administration.

    `attachments` : liste de (nom, contenu, type MIME).
    """
    from_email = sender_for(entity)
    delivery = EmailDelivery.objects.create(
        entity=entity,
        purpose=purpose,
        subject_reference=reference,
        to_email=to_email,
        cc_emails=list(cc or []),
        from_email=from_email,
        reply_to=reply_to or getattr(settings, "EMAIL_REPLY_TO", "") or "",
        subject=subject,
        language=language,
        backend=getattr(settings, "EMAIL_BACKEND", ""),
    )

    _attempt(delivery, text_body, html_body, attachments)
    return delivery


def _attempt(delivery, text_body, html_body=None, attachments=None):
    """Une tentative d'envoi. Met à jour l'état du journal, ne lève pas."""
    delivery.attempts += 1

    try:
        connection = get_connection(fail_silently=False)
        message = EmailMultiAlternatives(
            subject=delivery.subject,
            body=text_body,
            from_email=delivery.from_email or None,
            to=[delivery.to_email],
            cc=list(delivery.cc_emails or []) or None,
            reply_to=[delivery.reply_to] if delivery.reply_to else None,
            connection=connection,
            headers={"X-FEBA-Tracking-Id": str(delivery.tracking_id)},
        )
        if html_body:
            message.attach_alternative(html_body, "text/html")
        for name, content, mimetype in (attachments or []):
            message.attach(name, content, mimetype)

        accepted = message.send()
    except Exception as exc:
        # L'erreur EXACTE est conservée. « Erreur d'envoi » ne permet ni de
        # distinguer une adresse invalide d'un mot de passe expiré, ni de
        # décider s'il faut relancer ou corriger.
        delivery.last_error = f"{type(exc).__name__}: {exc}"[:2000]
        _schedule_retry_or_fail(delivery)
        logger.warning(
            "E-mail %s → %s : échec (tentative %d/%d) — %s",
            delivery.purpose, delivery.to_email, delivery.attempts,
            MAX_ATTEMPTS, delivery.last_error,
        )
        return delivery

    if not accepted:
        # `send()` a renvoyé 0 : le backend n'a pas pris le message, sans
        # lever. Un succès muet serait pire qu'une erreur.
        delivery.last_error = (
            "Le backend d'envoi a accepté 0 message sans signaler d'erreur."
        )
        _schedule_retry_or_fail(delivery)
        return delivery

    delivery.status = EmailDelivery.SENT
    delivery.sent_at = timezone.now()
    delivery.next_retry_at = None
    delivery.last_error = ""
    delivery.save(update_fields=[
        "status", "attempts", "sent_at", "next_retry_at", "last_error",
        "updated_at",
    ])
    logger.info(
        "E-mail %s → %s : remis au backend (%s, suivi %s)",
        delivery.purpose, delivery.to_email, delivery.backend,
        delivery.tracking_id,
    )
    return delivery


def _schedule_retry_or_fail(delivery):
    from datetime import timedelta

    if delivery.attempts < MAX_ATTEMPTS:
        minutes = RETRY_DELAYS_MINUTES[delivery.attempts - 1]
        delivery.status = EmailDelivery.RETRY
        delivery.next_retry_at = timezone.now() + timedelta(minutes=minutes)
    else:
        delivery.status = EmailDelivery.FAILED
        delivery.next_retry_at = None
    delivery.save(update_fields=[
        "status", "attempts", "last_error", "next_retry_at", "updated_at",
    ])


def resend(delivery, text_body, html_body=None, attachments=None):
    """
    Relance un envoi depuis l'administration.

    Repart de zéro sur le compteur de tentatives : la relance est une
    décision humaine, prise après avoir corrigé quelque chose. Lui
    appliquer le quota d'un envoi automatique la ferait échouer d'emblée.
    """
    delivery.attempts = 0
    delivery.status = EmailDelivery.PENDING
    delivery.backend = getattr(settings, "EMAIL_BACKEND", "")
    delivery.save(update_fields=["attempts", "status", "backend", "updated_at"])
    return _attempt(delivery, text_body, html_body, attachments)
