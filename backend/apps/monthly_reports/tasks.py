"""
P3 — Les tâches planifiées des rapports mensuels.

POURQUOI UN VERROU EN PLUS DE LA CONTRAINTE D'UNICITÉ
-----------------------------------------------------
La contrainte en base empêche le DOUBLON D'OBJET. Elle n'empêche pas
deux workers de produire le même lot en parallèle : chacun régénérerait
les PDF, écraserait les fichiers de l'autre, et pourrait déclencher deux
envois vers les mêmes parents avant que le premier n'ait marqué le
rapport comme envoyé.

Le verrou Redis règle ce second problème. Il porte sur (académie, année,
mois) : deux mois différents peuvent tourner en même temps, le même mois
non. Il expire tout seul — un worker tué net ne laisse pas le lot bloqué
jusqu'à la prochaine intervention humaine.

Si Redis est indisponible, la tâche NE S'EXÉCUTE PAS et le dit. Produire
sans verrou « parce que Redis est tombé » est exactement la situation où
le doublon se produit.
"""
import datetime
import logging
from contextlib import contextmanager
from datetime import date

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger("apps")

#: Durée de vie du verrou. Assez longue pour un lot complet, assez courte
#: pour qu'un worker mort ne bloque pas le mois suivant.
LOCK_TIMEOUT_SECONDS = 30 * 60


class LockUnavailable(RuntimeError):
    """Le verrou n'a pas pu être pris : un autre lot travaille déjà."""


@contextmanager
def batch_lock(key):
    """
    Verrou distribué, par (académie, période).

    Utilise le cache Django, configuré sur Redis. `add()` est atomique :
    il ne pose la clé que si elle n'existe pas, et renvoie faux sinon —
    c'est cette atomicité qui fait le verrou, pas la paire get/set qu'on
    écrirait spontanément et qui laisse une fenêtre entre les deux.
    """
    from django.core.cache import cache

    nom = f"monthly-reports:lock:{key}"
    try:
        obtenu = cache.add(nom, timezone.now().isoformat(),
                           LOCK_TIMEOUT_SECONDS)
    except Exception as exc:  # Redis injoignable
        raise LockUnavailable(
            f"Verrou indisponible ({type(exc).__name__}) : le lot n'est pas "
            f"lancé. Produire sans verrou exposerait les familles à un "
            f"double envoi."
        ) from exc

    if not obtenu:
        raise LockUnavailable(f"Un lot est déjà en cours pour « {key} ».")
    try:
        yield
    finally:
        try:
            cache.delete(nom)
        except Exception:  # pragma: no cover — le TTL prendra le relais
            logger.warning("Verrou %s non libéré ; il expirera seul", nom)


def previous_month(today=None):
    """
    Le mois à rapporter : celui qui vient de se terminer.

    La tâche s'exécute au début d'un mois pour rendre compte du
    précédent. Rapporter le mois COURANT le premier jour du mois
    produirait un rapport vide et le présenterait comme un bilan.
    """
    today = today or timezone.localdate()
    first = date(today.year, today.month, 1)
    last_of_previous = first - datetime.timedelta(days=1)
    return last_of_previous.year, last_of_previous.month


@shared_task(name="monthly_reports.generate_month", bind=True,
             max_retries=3, default_retry_delay=300)
def generate_month_task(self, academy_code=None, year=None, month=None,
                        send=None):
    """
    Produit le lot d'un mois, puis envoie si la configuration le demande.

    Idempotente : relancée, elle retrouve les rapports existants au lieu
    d'en créer de nouveaux, et n'envoie pas ceux qu'un fournisseur a déjà
    acceptés.
    """
    from django.conf import settings

    from apps.schools.models import School

    from .services import generate_month, send_report
    from .models import MonthlyReportStatus, MonthlyStudentReport

    academy_code = academy_code or School.CODE_FEBA_FHA
    academy = School.objects.filter(code=academy_code).first()
    if academy is None:
        logger.error("Rapports mensuels — académie « %s » introuvable",
                     academy_code)
        return {"erreur": f"académie {academy_code} introuvable"}

    if year is None or month is None:
        year, month = previous_month()

    if send is None:
        send = getattr(settings, "MONTHLY_REPORTS_AUTO_SEND", False)

    try:
        with batch_lock(f"{academy_code}:{year}-{month:02d}"):
            logger.info("Rapports mensuels — lot %s %04d-%02d démarré",
                        academy_code, year, month)
            resultats = generate_month(academy, year, month)

            envois = {"envoyes": 0, "echecs": 0, "ignores": 0}
            if send:
                rapports = MonthlyStudentReport.objects.filter(
                    academy=academy, year=year, month=month,
                ).exclude(status__in=[MonthlyReportStatus.CANCELLED,
                                      MonthlyReportStatus.ARCHIVED])
                for rapport in rapports:
                    if rapport.really_sent:
                        envois["ignores"] += 1
                        continue
                    try:
                        send_report(rapport)
                    except Exception:  # noqa: BLE001
                        logger.exception("Rapport %s — envoi impossible",
                                         rapport.reference)
                    rapport.refresh_from_db()
                    if rapport.status == MonthlyReportStatus.SENT:
                        envois["envoyes"] += 1
                    else:
                        envois["echecs"] += 1

            resultats["envois"] = envois
            logger.info("Rapports mensuels — lot %s %04d-%02d terminé : %s",
                        academy_code, year, month, resultats)
            return resultats
    except LockUnavailable as exc:
        # Ce n'est PAS une erreur : c'est le verrou qui fait son travail.
        logger.info("Rapports mensuels — lot ignoré : %s", exc)
        return {"ignore": str(exc)}


@shared_task(name="monthly_reports.send_one", bind=True, max_retries=4)
def send_report_task(self, report_id, user_id=None):
    """
    Envoie un rapport, avec réessais espacés.

    Les délais croissent (5, 30, 180 minutes) : un serveur de messagerie
    momentanément indisponible se rétablit souvent en quelques minutes,
    et réessayer toutes les dix secondes ne ferait qu'ajouter de la
    charge au moment où il en manque.
    """
    from .models import MonthlyReportStatus, MonthlyStudentReport
    from .services import send_report

    rapport = MonthlyStudentReport.objects.filter(pk=report_id).first()
    if rapport is None:
        return {"erreur": "rapport introuvable"}
    if rapport.really_sent:
        return {"ignore": "déjà accepté par un fournisseur"}

    utilisateur = None
    if user_id:
        from apps.accounts.models import CustomUser

        utilisateur = CustomUser.objects.filter(pk=user_id).first()

    send_report(rapport, user=utilisateur)
    rapport.refresh_from_db()

    if rapport.status == MonthlyReportStatus.FAILED:
        delais = [300, 1800, 10800, 10800]
        if self.request.retries < len(delais):
            raise self.retry(countdown=delais[self.request.retries])

    return {"statut": rapport.status,
            "reellement_envoye": rapport.really_sent}
