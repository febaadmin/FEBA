"""
Surveillance de la plateforme, sans service externe : chaque anomalie devient un
incident technique, dédoublonné, et notifie les super-administrateurs.
"""
import datetime
import shutil
import socket
import ssl
import urllib.request
from urllib.parse import urlparse

from celery import shared_task
from celery.signals import task_failure
from django.conf import settings
from django.utils import timezone

from .services import report_incident

SEUIL_CERTIFICAT_JOURS = 21
SEUIL_DISQUE_POURCENT = 90
AGE_MAX_SAUVEGARDE = datetime.timedelta(hours=26)


class AnomaliePlateforme(Exception):
    """Anomalie détectée par la surveillance."""


def lire(url):
    with urllib.request.urlopen(url, timeout=10) as reponse:
        return reponse.read(200).decode("utf-8", "replace").strip()


def jours_restants_certificat(host):
    contexte = ssl.create_default_context()
    with socket.create_connection((host, 443), timeout=10) as brut:
        with contexte.wrap_socket(brut, server_hostname=host) as tls:
            fin = ssl.cert_time_to_seconds(tls.getpeercert()["notAfter"])
    return (datetime.datetime.fromtimestamp(fin, datetime.timezone.utc) - timezone.now()).days


def anomalies():
    """Liste de messages stables (ils servent au regroupement des incidents)."""
    constats = []
    video = (settings.PLUGNMEET_SERVER_URL or "").rstrip("/")
    if video:
        try:
            if lire(f"{video}/healthCheck") != "Healthy":
                constats.append("Visioconférence : healthCheck en échec.")
        except OSError:
            constats.append("Visioconférence injoignable.")
        try:
            date = datetime.datetime.fromisoformat(lire(f"{video}/assets/feba/sauvegarde.txt").replace("Z", "+00:00"))
            if timezone.now() - date > AGE_MAX_SAUVEGARDE:
                constats.append("Sauvegarde plugNmeet : aucune réussite depuis plus de 26 h.")
        except (OSError, ValueError):
            constats.append("Sauvegarde plugNmeet : date de réussite illisible.")
    for url in (video, getattr(settings, "PUBLIC_BASE_URL", "")):
        host = urlparse(url or "").hostname
        if not host or url.startswith("http://"):
            continue
        try:
            if jours_restants_certificat(host) < SEUIL_CERTIFICAT_JOURS:
                constats.append(f"Certificat de {host} : moins de {SEUIL_CERTIFICAT_JOURS} jours.")
        except (OSError, ssl.SSLError):
            constats.append(f"Certificat de {host} : contrôle impossible.")
    disque = shutil.disk_usage("/")
    if 100 * disque.used / disque.total > SEUIL_DISQUE_POURCENT:
        constats.append(f"Disque du serveur FEBA rempli à plus de {SEUIL_DISQUE_POURCENT} %.")
    return constats


@shared_task(name="incidents.surveillance_plateforme")
def surveillance_plateforme():
    constats = anomalies()
    for message in constats:
        report_incident(AnomaliePlateforme(message), module="surveillance",
                        attempted_action="Surveillance planifiée", severity="critical", status_code=0)
    return constats


@task_failure.connect
def incident_sur_echec_de_tache(sender=None, exception=None, **kwargs):
    """Une tâche Celery en échec devient un incident, regroupé par tâche."""
    if exception is not None:
        report_incident(exception, module=getattr(sender, "name", "celery")[:80],
                        attempted_action="Tâche asynchrone", severity="high", status_code=0)
