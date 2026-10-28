from celery import shared_task
import logging
logger = logging.getLogger("apps")

@shared_task
def generate_receipt_pdf(payment_id):
    from apps.payments.models import Payment
    from apps.payments.pdf_generator import generate_receipt
    try:
        payment = Payment.objects.get(pk=payment_id)
        generate_receipt(payment)
        logger.info(f"Receipt generated for payment {payment.reference_number}")
    except Payment.DoesNotExist:
        logger.error(f"Payment {payment_id} not found")

@shared_task(name="payments.run_payment_reminders", ignore_result=True)
def run_payment_reminders():
    """
    Relances quotidiennes (Celery Beat), académie par académie.

    Ne relance QUE si l'interrupteur global `PAYMENT_REMINDERS_ENABLED` est
    actif ET que la politique de l'académie est activée. Sinon, une
    exécution « non exécutée » est journalisée avec sa raison : l'écran
    d'état voit ainsi que la planification tourne, et pourquoi rien ne part.

    Un verrou par académie (cache partagé Redis en production) évite deux
    exécutions simultanées ; la clé d'idempotence en base reste la garantie
    finale contre les doublons.
    """
    from django.core.cache import cache
    from django.utils import timezone

    from apps.core.age import academy_today
    from apps.payments.models import PaymentReminderPolicy, ReminderRun
    from apps.payments.reminders import reminders_globally_enabled, run_reminders
    from apps.schools.models import School

    done = 0
    for academy in School.objects.filter(is_active=True):
        policy = PaymentReminderPolicy.objects.filter(academy=academy).first()
        reason = ""
        if not reminders_globally_enabled():
            reason = "Interrupteur global PAYMENT_REMINDERS_ENABLED désactivé."
        elif policy is None or not policy.enabled:
            reason = "Relances automatiques désactivées pour cette académie."
        if reason:
            ReminderRun.objects.create(
                academy=academy, trigger=ReminderRun.TRIGGER_BEAT,
                reference_date=academy_today(academy), status=ReminderRun.SKIPPED,
                error=reason, finished_at=timezone.now(),
            )
            continue
        lock = f"payment-reminders-lock:{academy.pk}"
        if not cache.add(lock, "1", timeout=3600):
            logger.warning("Relances %s : une exécution est déjà en cours.", academy.code)
            continue
        try:
            run_reminders(academy, trigger=ReminderRun.TRIGGER_BEAT)
            done += 1
        finally:
            cache.delete(lock)
    return done


@shared_task(name="payments.run_payment_reminders_for", ignore_result=True)
def run_payment_reminders_for(academy_id, user_id=None):
    """Lancement manuel, demandé depuis l'écran « Relances de paiement »."""
    from django.core.cache import cache

    from apps.accounts.models import CustomUser
    from apps.payments.models import ReminderRun
    from apps.payments.reminders import reminders_globally_enabled, run_reminders
    from apps.schools.models import School

    academy = School.objects.filter(pk=academy_id).first()
    if academy is None or not reminders_globally_enabled():
        return None
    lock = f"payment-reminders-lock:{academy.pk}"
    if not cache.add(lock, "1", timeout=3600):
        logger.warning("Relances %s : une exécution est déjà en cours.", academy.code)
        return None
    try:
        user = CustomUser.objects.filter(pk=user_id).first() if user_id else None
        return run_reminders(academy, trigger=ReminderRun.TRIGGER_MANUAL, user=user).pk
    finally:
        cache.delete(lock)
