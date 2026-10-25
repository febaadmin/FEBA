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


def _sync_linked_records(delivery):
    """Reporte le résultat d'une nouvelle tentative sur les objets métier liés."""
    from .campaigns import recipient_for_delivery, refresh_campaign_status, sync_recipient

    recipient = recipient_for_delivery(delivery)
    if recipient is not None:
        recipient.attempts += 1
        sync_recipient(recipient, delivery)
        refresh_campaign_status(recipient.campaign)
    try:
        from apps.payments.reminders import sync_reminders_with_delivery
        sync_reminders_with_delivery(delivery)
    except ImportError:  # pragma: no cover
        pass


def _retry_legacy_fha_ack(delivery):
    """Envois FHA antérieurs à l'archivage du contenu : corps reconstruit."""
    from apps.website.fha_enrollment import parent_ack_bodies
    from apps.website.models import FHAEnrollmentApplication

    from .mailer import create_content

    application = FHAEnrollmentApplication.objects.filter(reference=delivery.subject_reference).first()
    if application is None:
        return False
    attachments = []
    if application.has_sheet:
        from apps.website.fha_pdf import sheet_filename
        with open(application.sheet_absolute_path, "rb") as handle:
            attachments = [(sheet_filename(application), handle.read(), "application/pdf")]
    subject, text, html_body = parent_ack_bodies(application)
    delivery.content = create_content(subject=subject, text_body=text, html_body=html_body,
                                      attachments=attachments)
    delivery.save(update_fields=["content", "updated_at"])
    return True


#: Envois HISTORIQUES (sans contenu archivé) dont le corps peut être
#: reconstruit. Les envois récents sont tous rejouables depuis l'archive.
LEGACY_REBUILDERS = {
    "fha_enrollment_ack": _retry_legacy_fha_ack,
}


@shared_task(name="notifications.retry_due_deliveries", ignore_result=True)
def retry_due_deliveries(limit=200):
    """
    Nouvelles tentatives des envois en « échec temporaire » dont l'heure est
    venue. Tout envoi au contenu archivé est rejouable ; les envois
    historiques sans contenu ne le sont que si leur corps peut être
    reconstruit, sinon ils passent en échec définitif, avec la raison.
    """
    from .email_models import EmailDelivery
    from .mailer import retry_due

    with transaction.atomic():
        due = list(
            EmailDelivery.objects.select_for_update(skip_locked=True)
            .filter(status=EmailDelivery.RETRY, next_retry_at__lte=timezone.now())
            .order_by("next_retry_at")[:limit]
        )
        # Réservés : un second worker ne les reprendra pas pendant l'envoi.
        EmailDelivery.objects.filter(pk__in=[d.pk for d in due]).update(
            status=EmailDelivery.PENDING, next_retry_at=None,
        )
    handled = 0
    for delivery in due:
        delivery.refresh_from_db()
        try:
            if delivery.content_id is None:
                rebuild = LEGACY_REBUILDERS.get(delivery.purpose)
                if rebuild is None or not rebuild(delivery):
                    delivery.status = EmailDelivery.FAILED
                    delivery.last_error = (delivery.last_error + "\nContenu non archivé pour cet "
                                           "envoi historique : relance automatique impossible.").strip()
                    delivery.save(update_fields=["status", "last_error", "updated_at"])
                    continue
            retry_due(delivery)
            _sync_linked_records(delivery)
            handled += 1
        except Exception as exc:
            logger.exception("Relance de l'envoi %s impossible : %s", delivery.pk, exc)
            delivery.status = EmailDelivery.RETRY
            delivery.next_retry_at = timezone.now() + timedelta(minutes=30)
            delivery.save(update_fields=["status", "next_retry_at", "updated_at"])
    return handled


@shared_task(name="notifications.send_sms", ignore_result=True)
def send_sms(sms_id):
    """Une tentative pour un SMS (idempotent : voir sms.deliver)."""
    from .sms import deliver
    deliver(sms_id)


@shared_task(name="notifications.retry_due_sms", ignore_result=True)
def retry_due_sms():
    """Reprise des SMS en nouvel essai, restés en file ou interrompus."""
    from .sms import retry_due
    return retry_due()
