import logging

from celery import shared_task

logger = logging.getLogger("apps")


@shared_task(name="boite_mail.synchroniser", ignore_result=True)
def synchroniser():
    """Synchronisation périodique de la boîte contact (incrémentale ; ne bloque rien d'autre)."""
    from .imap import configuration, synchroniser_tout
    if not configuration()["configuree"]:
        return {"configuree": False}
    bilan = synchroniser_tout()
    if bilan.get("erreur"):
        logger.warning("Boîte contact : %s", bilan["erreur"])
    return bilan
