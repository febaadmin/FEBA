"""
Contrôles de configuration de la visioconférence (`manage.py check`).

Un webhook refusé par Django (hôte absent d'ALLOWED_HOSTS → 400) ne se
voit nulle part : plugNmeet réessaie puis abandonne, et les présences
restent incomplètes. Constaté pendant l'essai réel ; on le signale donc
dès le démarrage.
"""
from urllib.parse import urlparse

from django.conf import settings
from django.core.checks import Warning, register


@register()
def plugnmeet_configuration(app_configs, **kwargs):
    issues = []
    if getattr(settings, "VIDEO_PROVIDER", "plugnmeet") != "plugnmeet":
        return issues
    url = getattr(settings, "PLUGNMEET_WEBHOOK_URL", "") or ""
    if url:
        host = (urlparse(url).hostname or "").lower()
        allowed = [h.lower() for h in settings.ALLOWED_HOSTS]
        ok = "*" in allowed or any(
            host == h or (h.startswith(".") and (host == h[1:] or host.endswith(h))) for h in allowed
        )
        if not ok:
            issues.append(Warning(
                f"L'hôte « {host} » de PLUGNMEET_WEBHOOK_URL n'est pas dans ALLOWED_HOSTS : "
                "Django refusera les webhooks plugNmeet (HTTP 400) et les présences ne seront "
                "pas suivies.",
                id="virtualclass.W001",
            ))
    if settings.PLUGNMEET_SERVER_URL and not (settings.PLUGNMEET_API_KEY and settings.PLUGNMEET_API_SECRET):
        issues.append(Warning(
            "PLUGNMEET_SERVER_URL est défini sans PLUGNMEET_API_KEY / PLUGNMEET_API_SECRET : "
            "aucune salle ne pourra s'ouvrir.",
            id="virtualclass.W002",
        ))
    return issues
