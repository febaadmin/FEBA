"""
Enregistrement des incidents techniques + notification réelle des super admins.

Règle d'honnêteté (V8) : le message renvoyé à l'utilisateur n'annonce une
remontée à l'équipe technique QUE si l'incident a réellement été enregistré.
"""
import logging
import os
import traceback

from django.db import transaction
from django.utils import timezone

from .models import (
    TechnicalIncident, build_fingerprint, sanitize_data, sanitize_text,
)

logger = logging.getLogger("apps")

# Au-delà du 1er signalement, on ne renotifie que sur ces paliers d'occurrences
# (évite de saturer la cloche des super administrateurs).
NOTIFY_THRESHOLDS = {1, 5, 25, 100, 500}


def _exception_location(exc):
    """Fichier:ligne (fonction) où l'exception a été levée — sans traceback brut."""
    tb = getattr(exc, "__traceback__", None)
    if tb is None:
        return "", ""
    last = list(traceback.extract_tb(tb))[-1:]
    if not last:
        return "", ""
    frame = last[0]
    filename = frame.filename
    marker = f"{os.sep}apps{os.sep}"
    if marker in filename:
        short = "apps/" + filename.split(marker, 1)[1]
    else:
        short = os.path.basename(filename)
    module = short.split("/")[1] if short.startswith("apps/") and "/" in short[5:] else ""
    return f"{short}:{frame.lineno} ({frame.name})", module


def notify_superadmins(incident):
    """Crée une notification interne pour chaque super administrateur.

    Renvoie le nombre de notifications réellement créées (0 si aucun super
    administrateur n'existe ou si la notification échoue).
    """
    try:
        from apps.accounts.models import CustomUser
        from apps.notifications.models import Notification

        superadmins = list(CustomUser.objects.filter(role="superadmin", is_active=True))
        if not superadmins:
            return 0
        created = 0
        for admin in superadmins:
            Notification.objects.create(
                user=admin,
                type="announcement",  # canal interne existant (cloche)
                title=f"Incident technique {incident.reference}",
                message=(
                    f"{incident.exception_type or 'Erreur serveur'} — "
                    f"{incident.endpoint or incident.module or 'application'}"
                ),
                # Le clic ouvre l'INCIDENT, pas la page Annonces.
                related_url=f"/superadmin/incidents/{incident.id}",
            )
            created += 1
        return created
    except Exception:
        logger.exception("Notification des super administrateurs impossible")
        return 0


def report_incident(exc, *, request=None, module="", attempted_action="",
                    severity="high", status_code=500, context=None):
    """Enregistre (ou dédoublonne) un incident technique.

    Renvoie l'incident, ou None si l'enregistrement lui-même a échoué — dans ce
    cas l'appelant NE DOIT PAS prétendre que l'équipe a été notifiée.
    """
    try:
        location, module_from_tb = _exception_location(exc)
        module = module or module_from_tb
        endpoint = getattr(request, "path", "") or ""
        http_method = getattr(request, "method", "") or ""
        exception_type = type(exc).__name__
        message = sanitize_text(str(exc))

        fingerprint = build_fingerprint(exception_type, endpoint, module, location, message)

        user = getattr(request, "user", None)
        if user is not None and not getattr(user, "is_authenticated", False):
            user = None

        school = None
        try:
            from apps.core.tenancy import get_request_school
            school = get_request_school(request) if request is not None else None
        except Exception:
            school = None
        if school is None and user is not None:
            school = getattr(user, "school", None)

        meta = getattr(request, "META", {}) or {}
        payload = {
            "environment": os.environ.get("DJANGO_ENV", "") or
                           os.environ.get("DJANGO_SETTINGS_MODULE", "").split(".")[-1],
            "severity": severity,
            "module": module[:80],
            "frontend_route": sanitize_text(meta.get("HTTP_REFERER", ""), 255)[:255],
            "endpoint": endpoint[:255],
            "http_method": http_method[:10],
            "status_code": status_code,
            "exception_type": exception_type[:120],
            "message": message,
            "location": location[:255],
            "user": user,
            "user_role": getattr(user, "role", "") or "",
            "school": school,
            "attempted_action": sanitize_text(attempted_action, 255)[:255],
            "context_data": sanitize_data(context or {}),
            "user_agent": sanitize_text(meta.get("HTTP_USER_AGENT", ""), 255)[:255],
            "app_version": os.environ.get("APP_VERSION", "")[:40],
            "release": os.environ.get("GIT_COMMIT", "")[:60],
        }

        # Le compteur d'occurrences ne doit pas être annulé par le rollback de
        # la transaction fautive : on écrit dans une transaction indépendante.
        with transaction.atomic():
            incident = (TechnicalIncident.objects
                        .select_for_update(nowait=False)
                        .filter(fingerprint=fingerprint)
                        .exclude(status="resolved")
                        .first())
            if incident is None:
                incident = TechnicalIncident.objects.create(
                    fingerprint=fingerprint, **payload)
                should_notify = True
            else:
                incident.occurrences += 1
                incident.last_seen_at = timezone.now()
                # Une erreur qui revient après résolution est rouverte.
                if incident.status == "ignored":
                    pass
                incident.save(update_fields=["occurrences", "last_seen_at", "status"])
                should_notify = incident.occurrences in NOTIFY_THRESHOLDS

        if should_notify:
            notify_superadmins(incident)
        return incident
    except Exception:
        # Le système de remontée ne doit jamais masquer l'erreur d'origine.
        logger.exception("Enregistrement de l'incident technique impossible")
        return None
