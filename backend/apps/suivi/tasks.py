from celery import shared_task

from .alertes import detecter_toutes


@shared_task(name="suivi.detecter_alertes")
def detecter_alertes():
    return detecter_toutes()
