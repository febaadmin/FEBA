from celery import shared_task

from .services import cloturer_echues


@shared_task(name="evaluations.cloturer_echues")
def cloturer_echues_task():
    return cloturer_echues()
