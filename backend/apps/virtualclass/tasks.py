"""Tâches périodiques de la visioconférence."""
from celery import shared_task


@shared_task(name="virtualclass.reconcile_live_rooms")
def reconcile_live_rooms():
    """Aligne les salles « en cours » sur l'état réel de plugNmeet."""
    from .meetings import reconcile_live_rooms as run

    return run()
