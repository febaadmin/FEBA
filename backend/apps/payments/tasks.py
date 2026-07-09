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