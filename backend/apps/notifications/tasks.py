"""
apps/notifications/tasks.py — Tâches de fond des envois d'e-mails.

- `notifications.send_campaign` : envoie une campagne (envoi groupé).
- `notifications.process_pending_campaigns` (planifiée) : reprend les
  campagnes dont des destinataires attendent encore — après une panne du
  broker ou un redémarrage de Celery.
- `notifications.retry_due_deliveries` (planifiée) : relance les envois
  en « nouvel essai programmé » dont l'heure est venue. Avant cette tâche,
  `next_retry_at` était calculé… et jamais relu.

Toutes sont rejouables : elles ne prennent que des lignes en attente, sous
verrou `skip_locked`, et ne renvoient jamais un message déjà remis.
"""
import logging
from datetime import timedelta

from celery import shared_task
from django.db import transaction
from django.utils import timezone

logger = logging.getLogger("apps")


@shared_task(name="notifications.send_campaign", ignore_result=True)
def send_campaign(campaign_id):
    from .campaigns import process_campaign

    return process_campaign(campaign_id)


@shared_task(name="notifications.process_pending_campaigns", ignore_result=True)
def process_pending_campaigns():
    from .campaign_models import EmailCampaign, EmailCampaignRecipient
    from .campaigns import process_campaign

    ids = list(
        EmailCampaign.objects.filter(
            recipients__status__in=[EmailCampaignRecipient.PENDING, EmailCampaignRecipient.SENDING],
        ).values_list("pk", flat=True).distinct()
    )
    for campaign_id in ids:
        try:
            process_campaign(campaign_id)
        except Exception as exc:  # une campagne en erreur ne bloque pas les autres
            logger.exception("Reprise de l'envoi groupé %s impossible : %s", campaign_id, exc)
    return len(ids)


def _retry_campaign(delivery):
    from .campaign_models import EmailCampaignRecipient
    from .campaigns import rebuild_for_delivery
    from .email_models import EmailDelivery
    from .mailer import retry_due

    rebuilt = rebuild_for_delivery(delivery)
    if rebuilt is None:
        return False
    text, html_body, recipient = rebuilt
    if recipient.status == EmailCampaignRecipient.SENT:
        return True
    delivery = retry_due(delivery, text, html_body)
    recipient.attempts += 1
    if delivery.status in (EmailDelivery.SENT, EmailDelivery.ACCEPTED):
        recipient.status = EmailCampaignRecipient.SENT
        recipient.sent_at = delivery.sent_at
        recipient.error = ""
    elif delivery.status == EmailDelivery.RETRY:
        recipient.status = EmailCampaignRecipient.RETRY
        recipient.error = delivery.last_error
    else:
        recipient.status = EmailCampaignRecipient.FAILED
        recipient.error = delivery.last_error
    recipient.save(update_fields=["status", "sent_at", "error", "attempts", "updated_at"])
    from .campaigns import refresh_campaign_status
    refresh_campaign_status(recipient.campaign)
    return True


def _retry_fha_ack(delivery):
    from apps.website.fha_enrollment import parent_ack_bodies
    from apps.website.models import FHAEnrollmentApplication

    from .mailer import retry_due

    application = FHAEnrollmentApplication.objects.filter(
        reference=delivery.subject_reference,
    ).first()
    if application is None:
        return False
    attachments = []
    if application.has_sheet:
        from apps.website.fha_pdf import sheet_filename
        with open(application.sheet_absolute_path, "rb") as handle:
            attachments = [(sheet_filename(application), handle.read(), "application/pdf")]
    _subject, text, html_body = parent_ack_bodies(application)
    retry_due(delivery, text, html_body, attachments)
    return True


def _retry_payment_reminder(delivery):
    from apps.payments.reminders import retry_reminder_delivery

    return retry_reminder_delivery(delivery)


#: Objets d'envoi dont le corps peut être reconstruit pour une relance
#: automatique. Les autres restent en « nouvel essai » visible, et
#: l'administration dispose d'une action de renvoi manuelle.
RETRY_HANDLERS = {
    "academy_mass_email": _retry_campaign,
    "fha_enrollment_ack": _retry_fha_ack,
    "payment_reminder": _retry_payment_reminder,
}


@shared_task(name="notifications.retry_due_deliveries", ignore_result=True)
def retry_due_deliveries(limit=200):
    from .email_models import EmailDelivery

    with transaction.atomic():
        due = list(
            EmailDelivery.objects.select_for_update(skip_locked=True)
            .filter(status=EmailDelivery.RETRY, next_retry_at__lte=timezone.now(),
                    purpose__in=list(RETRY_HANDLERS))
            .order_by("next_retry_at")[:limit]
        )
        # Réservées : passées « en attente » pour qu'un second worker ne
        # les reprenne pas pendant l'envoi.
        EmailDelivery.objects.filter(pk__in=[d.pk for d in due]).update(
            status=EmailDelivery.PENDING, next_retry_at=None,
        )
    handled = 0
    for delivery in due:
        delivery.refresh_from_db()
        try:
            if RETRY_HANDLERS[delivery.purpose](delivery):
                handled += 1
            else:
                delivery.status = EmailDelivery.FAILED
                delivery.last_error = (delivery.last_error + "\nObjet d'origine introuvable : relance impossible.").strip()
                delivery.save(update_fields=["status", "last_error", "updated_at"])
        except Exception as exc:
            logger.exception("Relance de l'envoi %s impossible : %s", delivery.pk, exc)
            delivery.status = EmailDelivery.RETRY
            delivery.next_retry_at = timezone.now() + timedelta(minutes=30)
            delivery.save(update_fields=["status", "next_retry_at", "updated_at"])
    return handled
