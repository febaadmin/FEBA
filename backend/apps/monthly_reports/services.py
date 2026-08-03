"""
P3 — Génération et envoi des rapports mensuels.

LES DEUX RÈGLES QUI TIENNENT TOUT LE RESTE
------------------------------------------

**1. Relancer la tâche ne doit rien casser ni rien dupliquer.**
Le planificateur peut rejouer un mois ; un administrateur peut relancer
après incident ; un worker peut redémarrer au milieu d'un lot. La
génération est donc idempotente : elle retrouve le rapport existant de la
période au lieu d'en créer un second. La contrainte d'unicité en base est
le filet — si deux processus passent en même temps, la base tranche, et
le perdant récupère la ligne gagnante au lieu d'échouer.

**2. « Envoyé » est une affirmation sur le MONDE, pas sur nous.**
Écrire un PDF ne l'envoie pas. Remettre un message à Django ne l'envoie
pas non plus si le backend est la console. Le statut `SENT` demande deux
choses : une tentative marquée réussie ET un identifiant rendu par un
fournisseur. Sans le second, le rapport reste dans un état qui dit la
vérité — `generated`, `ready`, ou `failed`.
"""
import logging

from django.db import IntegrityError, transaction
from django.utils import timezone

from .aggregation import build_report_data
from .models import (
    InvalidTransition, MonthlyReportAttempt, MonthlyReportStatus,
    MonthlyStudentReport,
)

logger = logging.getLogger("apps")


class ReportError(RuntimeError):
    """Erreur métier explicite, destinée à être montrée à un humain."""


def eligible_students(academy):
    """
    Les élèves actifs de l'académie.

    Filtré sur l'académie ET sur l'activité : produire un rapport pour un
    élève parti serait envoyer un courrier à une famille qui a quitté
    l'établissement.
    """
    from apps.students.models import Student

    return Student.objects.filter(school=academy, is_active=True)


def current_school_year(academy):
    from apps.schools.models import SchoolYear

    return SchoolYear.objects.filter(school=academy, is_current=True).first()


@transaction.atomic
def generate_report(student, year, month, *, user=None, force_new_version=False):
    """
    Produit (ou retrouve) le rapport d'un élève pour une période.

    Renvoie `(report, created)`. `created=False` signale que la période
    avait déjà son rapport : c'est le cas NORMAL d'une relance, pas une
    anomalie.
    """
    academy = student.school
    if academy is None:
        raise ReportError(
            f"L'élève {student} n'est rattaché à aucune académie : "
            f"impossible de savoir quelle identité porterait le rapport."
        )

    existing = (MonthlyStudentReport.objects
                .filter(academy=academy, student=student, year=year, month=month)
                .order_by("-version").first())

    if existing and not force_new_version:
        if not existing.is_editable:
            # Un rapport déjà envoyé n'est pas régénéré en place : le
            # corriger produirait un document différent portant la
            # référence de celui que la famille détient déjà.
            return existing, False
        _fill(existing, student, year, month, user=user)
        return existing, False

    version = (existing.version + 1) if existing else 1
    report = MonthlyStudentReport(
        academy=academy, student=student, year=year, month=month,
        version=version, school_year=current_school_year(academy),
        created_by=user, updated_by=user,
    )
    if existing:
        # Une nouvelle version reprend le texte humain de la précédente :
        # le perdre obligerait l'administration à le réécrire, et c'est
        # exactement ainsi qu'on finit par ne plus le réécrire du tout.
        report.editable_content = dict(existing.editable_content or {})
    try:
        report.save()
    except IntegrityError:
        # Course entre deux processus : la base a tranché. On récupère la
        # ligne gagnante plutôt que de remonter une erreur au parent.
        logger.info("Rapport mensuel déjà créé en parallèle (%s, %d-%02d)",
                    student, year, month)
        gagnant = (MonthlyStudentReport.objects
                   .filter(academy=academy, student=student, year=year,
                           month=month, version=version).first())
        if gagnant is None:
            raise
        return gagnant, False

    _fill(report, student, year, month, user=user)
    return report, True


def _fill(report, student, year, month, *, user=None):
    """Relève les données, produit le PDF, enregistre l'état."""
    report.generated_data = build_report_data(student, year, month)
    report.updated_by = user

    from .pdf import generate_report_pdf

    try:
        content = generate_report_pdf(report)
    except Exception as exc:
        report.last_error = f"{type(exc).__name__}: {exc}"[:2000]
        report.save(update_fields=["generated_data", "last_error",
                                   "updated_by", "updated_at"])
        logger.exception("Rapport mensuel — PDF non produit pour %s",
                         report.reference)
        raise ReportError(report.last_error) from exc

    report.store_pdf(content)
    report.last_error = ""
    if report.status == MonthlyReportStatus.DRAFT:
        report.status = MonthlyReportStatus.GENERATED
    report.save(update_fields=[
        "generated_data", "pdf_path", "pdf_sha256", "generated_at",
        "status", "last_error", "updated_by", "updated_at",
    ])
    return report


def generate_month(academy, year, month, *, user=None):
    """
    Le lot d'un mois pour une académie.

    Un élève en échec n'interrompt pas les autres : le lot continue et
    l'échec est consigné. Interrompre priverait de rapport toutes les
    familles suivantes à cause d'une seule donnée aberrante.
    """
    resultats = {"crees": 0, "existants": 0, "echecs": []}
    for student in eligible_students(academy):
        try:
            _, created = generate_report(student, year, month, user=user)
            resultats["crees" if created else "existants"] += 1
        except Exception as exc:  # noqa: BLE001 — on veut TOUS les échecs
            resultats["echecs"].append({"eleve": str(student),
                                        "erreur": f"{type(exc).__name__}: {exc}"})
            logger.exception("Rapport mensuel — échec pour %s", student)
    return resultats


# ── Destinataires ────────────────────────────────────────────────────


def report_recipients(report):
    """
    Les adresses des responsables habilités de l'élève.

    On ne devine pas : seuls les parents rattachés à l'élève et dotés
    d'une adresse valide sont retenus. Un rapport envoyé « au hasard »
    dans le domaine de l'école serait une fuite de données scolaires.
    """
    from apps.parents.models import ParentStudent

    liens = (ParentStudent.objects
             .filter(student=report.student)
             .select_related("parent__user"))
    adresses = []
    for lien in liens:
        user = getattr(lien.parent, "user", None)
        email = (getattr(user, "email", "") or "").strip()
        if email and email not in adresses:
            adresses.append(email)
    return adresses


def preferred_language(report):
    """Langue déclarée du premier responsable ; français par défaut."""
    from apps.parents.models import ParentStudent

    lien = (ParentStudent.objects
            .filter(student=report.student)
            .select_related("parent__user").first())
    user = getattr(getattr(lien, "parent", None), "user", None)
    langue = (getattr(user, "preferred_language", "") or "").lower()
    return "en" if langue.startswith("en") else "fr"


# ── Envoi ────────────────────────────────────────────────────────────


def send_report(report, *, user=None):
    """
    Tente l'envoi et enregistre ce qui s'est RÉELLEMENT passé.

    Ne lève pas : un échec d'envoi est un état du rapport, pas une panne
    de l'application. Renvoie le rapport rafraîchi.
    """
    from .emails import send_monthly_report_email

    if report.status == MonthlyReportStatus.SENT and report.really_sent:
        # Garde-fou anti-doublon : un rapport déjà accepté par un
        # fournisseur ne repart pas parce qu'une tâche a été rejouée.
        logger.info("Rapport %s déjà envoyé — nouvel envoi ignoré",
                    report.reference)
        return report

    if not report.has_pdf:
        raise ReportError(
            "Le PDF du rapport est absent : il n'y a rien à joindre. "
            "Régénérez le rapport avant de l'envoyer."
        )

    destinataires = report_recipients(report)
    if not destinataires:
        report.last_error = (
            "Aucun responsable de cet élève n'a d'adresse électronique "
            "enregistrée."
        )
        report.recipients = []
        report.attempts_count += 1
        report.last_attempt_at = timezone.now()
        _force_status(report, MonthlyReportStatus.FAILED, user=user)
        MonthlyReportAttempt.objects.create(
            report=report, recipients=[], succeeded=False,
            error=report.last_error, triggered_by=user)
        return report

    if report.status in (MonthlyReportStatus.GENERATED,
                         MonthlyReportStatus.FAILED):
        report.transition_to(MonthlyReportStatus.READY, user=user)
    if report.status == MonthlyReportStatus.READY:
        report.transition_to(MonthlyReportStatus.SENDING, user=user)
    elif report.status == MonthlyReportStatus.SENT:
        report.transition_to(MonthlyReportStatus.SENDING, user=user)

    report.recipients = destinataires
    report.attempts_count += 1
    report.last_attempt_at = timezone.now()

    outcome = send_monthly_report_email(report, destinataires)

    MonthlyReportAttempt.objects.create(
        report=report, recipients=destinataires,
        succeeded=outcome["accepted"],
        provider_message_id=outcome.get("message_id", "") or "",
        used_real_provider=outcome.get("used_real_provider", False),
        error=outcome.get("error", "") or "",
        triggered_by=user,
    )

    if outcome["accepted"]:
        report.provider_message_id = outcome.get("message_id", "") or ""
        report.sent_at = timezone.now()
        report.last_error = ""
        report.status = MonthlyReportStatus.SENT
    else:
        report.last_error = outcome.get("error", "Envoi refusé.")[:2000]
        report.status = MonthlyReportStatus.FAILED

    report.updated_by = user
    report.save(update_fields=[
        "status", "recipients", "attempts_count", "last_attempt_at",
        "last_error", "provider_message_id", "sent_at", "updated_by",
        "updated_at",
    ])
    return report


def _force_status(report, status, *, user=None):
    """
    Pose un état en contournant la table des transitions.

    Réservé aux cas où l'état courant n'a pas de chemin légal vers
    l'échec — un rapport en brouillon dont on découvre qu'aucun parent
    n'a d'adresse, par exemple. Le contournement est nommé et localisé
    ici plutôt que dispersé en affectations directes.
    """
    try:
        report.transition_to(status, user=user)
    except InvalidTransition:
        report.status = status
        report.updated_by = user
        report.save(update_fields=["status", "updated_by", "updated_at"])
    return report
