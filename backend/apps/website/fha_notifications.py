"""
apps/website/fha_notifications.py — Notifications du parcours d'admission FHA

Chaque notification :
  - porte une ENTITÉ (jamais de fuite vers l'autre entité) ;
  - vise un destinataire autorisé ;
  - référence l'objet source (numéro de dossier) ;
  - est bilingue lorsque la famille est anglophone.

Les e-mails partent via le backend e-mail configuré. En test, Django
utilise le backend `locmem` : les envois sont vérifiables sans réseau.
"""
import logging

from django.conf import settings
from django.core.mail import send_mail

logger = logging.getLogger("apps")


def _entity_from(application):
    return application.entity


def _admissions_recipients(entity):
    """
    Destinataires internes des notifications d'admission : les
    administrateurs de CETTE entité uniquement.
    """
    from apps.accounts.models import CustomUser

    return list(
        CustomUser.objects
        .filter(school=entity, role__in=("admin",), is_active=True)
        .exclude(email="")
        .values_list("email", flat=True)
    )


def _send(subject, body, recipients):
    if not recipients:
        logger.info("Notification FHA non envoyée (aucun destinataire) : %s", subject)
        return 0
    try:
        return send_mail(
            subject=subject,
            message=body,
            from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
            recipient_list=list(recipients),
            fail_silently=True,
        )
    except Exception as exc:  # pragma: no cover - ne bloque jamais la soumission
        logger.warning("Échec d'envoi de notification FHA (%s) : %s", subject, exc)
        return 0


def notify_application_submitted(application):
    """
    Fiche soumise : accusé de réception au parent + notification de
    l'équipe admissions de l'entité.
    """
    entity = _entity_from(application)
    reference = application.reference

    # Le parent choisit sa langue : on envoie dans celle qu'il a déclarée.
    if application.parent1_preferred_language == "fr":
        subject = f"[{entity.name}] Votre fiche d'inscription — dossier {reference}"
        body = (
            f"Bonjour {application.parent1_first_name},\n\n"
            f"Nous avons bien reçu la fiche de renseignements de "
            f"{application.child_first_name}.\n"
            f"Votre numéro de dossier est : {reference}\n\n"
            "Prochaine étape : la réservation du test de placement "
            "(15 à 20 minutes).\n\n"
            f"— {entity.legal_name or entity.name}"
        )
    else:
        subject = f"[{entity.name}] Your enrollment form — file {reference}"
        body = (
            f"Hello {application.parent1_first_name},\n\n"
            f"We have received the enrollment form for "
            f"{application.child_first_name}.\n"
            f"Your file number is: {reference}\n\n"
            "Next step: booking the French placement assessment "
            "(15 to 20 minutes).\n\n"
            f"— {entity.legal_name or entity.name}"
        )

    sent = _send(subject, body, [application.parent1_email])

    # Notification interne — uniquement aux admins de cette entité.
    admin_subject = f"[{entity.name}] Nouvelle fiche d'inscription — {reference}"
    admin_body = (
        f"Dossier : {reference}\n"
        f"Enfant : {application.child_first_name} {application.child_last_name} "
        f"({application.child_age} ans)\n"
        f"Groupe suggéré (âge) : {application.suggested_group or 'à déterminer'}\n"
        f"Parent : {application.parent1_first_name} {application.parent1_last_name} "
        f"<{application.parent1_email}>\n"
        f"Pays : {application.child_country or 'non précisé'}\n"
        f"Fuseau famille : {application.family_timezone or 'non précisé'}\n"
    )
    _send(admin_subject, admin_body, _admissions_recipients(entity))

    logger.info("FHA — notification « fiche reçue » émise pour %s", reference)
    return sent


def notify_status_changed(application, previous_status):
    """
    Changement d'état du dossier : informe le parent avec un message
    adapté à l'état atteint.
    """
    entity = _entity_from(application)
    reference = application.reference
    label = dict(application.STATUS_CHOICES).get(application.status, application.status)

    is_fr = application.parent1_preferred_language == "fr"
    if is_fr:
        subject = f"[{entity.name}] Dossier {reference} — {label}"
        body = (
            f"Bonjour {application.parent1_first_name},\n\n"
            f"L'état de votre dossier {reference} a évolué : {label}.\n\n"
            f"— {entity.legal_name or entity.name}"
        )
    else:
        subject = f"[{entity.name}] File {reference} — status updated"
        body = (
            f"Hello {application.parent1_first_name},\n\n"
            f"Your file {reference} has a new status: {label}.\n\n"
            f"— {entity.legal_name or entity.name}"
        )

    logger.info(
        "FHA — notification de changement d'état %s : %s → %s",
        reference, previous_status, application.status,
    )
    return _send(subject, body, [application.parent1_email])


# ── Notifications du parcours de test de placement ──────────────────────────

def notify_placement_test_requested(test_request):
    """
    Demande de test reçue : accusé au parent + notification de l'équipe
    admissions de l'entité (jamais les admins de l'autre académie).
    """
    entity = test_request.entity
    reference = test_request.reference
    is_fr = test_request.preferred_language == "fr"

    if is_fr:
        subject = f"[{entity.name}] Demande de test de placement — dossier {reference}"
        body = (
            f"Bonjour {test_request.parent_first_name},\n\n"
            f"Nous avons bien reçu votre demande de test de placement pour "
            f"{test_request.child_first_name}.\n"
            f"Numéro de dossier : {reference}\n\n"
            "Le test dure 15 à 20 minutes et se déroule en visioconférence. "
            "Nous vous confirmerons prochainement un créneau, affiché dans "
            "votre fuseau horaire.\n\n"
            f"— {entity.legal_name or entity.name}"
        )
    else:
        subject = f"[{entity.name}] Placement assessment request — file {reference}"
        body = (
            f"Hello {test_request.parent_first_name},\n\n"
            f"We have received your placement assessment request for "
            f"{test_request.child_first_name}.\n"
            f"File number: {reference}\n\n"
            "The assessment takes 15 to 20 minutes and is held by video "
            "conference. We will confirm a time slot shortly, shown in your "
            "local time zone.\n\n"
            f"— {entity.legal_name or entity.name}"
        )

    sent = _send(subject, body, [test_request.parent_email])

    admin_subject = f"[{entity.name}] Nouvelle demande de test — {reference}"
    admin_body = (
        f"Dossier : {reference}\n"
        f"Enfant : {test_request.child_first_name} {test_request.child_last_name} "
        f"({test_request.child_age} ans)\n"
        f"Groupe suggéré : {test_request.suggested_group or 'à déterminer'}\n"
        f"Niveau estimé par le parent : {test_request.get_estimated_level_display()}\n"
        f"Parent : {test_request.parent_first_name} {test_request.parent_last_name} "
        f"<{test_request.parent_email}>\n"
        f"Fuseau : {test_request.parent_timezone or 'non précisé'}\n"
        f"Créneau souhaité : {test_request.preferred_date or '—'} "
        f"{test_request.preferred_time or ''}\n"
    )
    _send(admin_subject, admin_body, _admissions_recipients(entity))

    logger.info("FHA — notification « demande de test » émise pour %s", reference)
    return sent


def notify_placement_test_scheduled(test_request):
    """Créneau confirmé : le parent reçoit la date et les instructions."""
    entity = test_request.entity
    reference = test_request.reference
    is_fr = test_request.preferred_language == "fr"

    # L'heure est communiquée dans le fuseau déclaré par la famille.
    moment = test_request.scheduled_at
    when = ""
    if moment is not None:
        try:
            import zoneinfo
            from django.utils import timezone as dj_timezone

            tz_name = test_request.parent_timezone or entity.timezone
            local = moment.astimezone(zoneinfo.ZoneInfo(tz_name))
            when = f"{local:%d/%m/%Y %H:%M} ({tz_name})"
        except Exception:
            when = f"{moment:%d/%m/%Y %H:%M} (UTC)"

    if is_fr:
        subject = f"[{entity.name}] Test de placement confirmé — {reference}"
        body = (
            f"Bonjour {test_request.parent_first_name},\n\n"
            f"Le test de placement de {test_request.child_first_name} est "
            f"confirmé.\n\n"
            f"Date et heure : {when}\n"
            f"Durée : 15 à 20 minutes\n\n"
            "Le lien de connexion sécurisé apparaîtra dans votre espace "
            "avant le rendez-vous. Il n'est jamais publié publiquement.\n\n"
            "Merci de prévoir un ordinateur ou une tablette avec caméra et "
            "micro, dans un endroit calme. La présence d'un parent est "
            "recommandée pour les plus jeunes.\n\n"
            f"— {entity.legal_name or entity.name}"
        )
    else:
        subject = f"[{entity.name}] Placement assessment confirmed — {reference}"
        body = (
            f"Hello {test_request.parent_first_name},\n\n"
            f"{test_request.child_first_name}'s placement assessment is "
            f"confirmed.\n\n"
            f"Date and time: {when}\n"
            f"Duration: 15 to 20 minutes\n\n"
            "The secure joining link will appear in your account before the "
            "appointment. It is never published publicly.\n\n"
            "Please have a computer or tablet with a camera and microphone "
            "ready, in a quiet place. A parent's presence is recommended for "
            "younger children.\n\n"
            f"— {entity.legal_name or entity.name}"
        )

    logger.info("FHA — notification « test planifié » émise pour %s", reference)
    return _send(subject, body, [test_request.parent_email])
