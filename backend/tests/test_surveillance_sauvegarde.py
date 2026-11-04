"""
Surveillance de la sauvegarde plugNmeet (incident ERR-310AC0) : une sauvegarde
récente ne lève rien ; une sauvegarde de plus de 26 h, une date illisible ou un
serveur injoignable lèvent une anomalie, signalée en incident critique.
"""
import datetime
from unittest import mock

from django.test import TestCase, override_settings
from django.utils import timezone

from apps.incidents import tasks
from apps.incidents.models import TechnicalIncident

URL = "https://video.example.test"


def faux_lire(date_sauvegarde=None, erreur=None):
    def lire(url):
        if url.endswith("/healthCheck"):
            return "Healthy"
        if erreur:
            raise erreur
        return date_sauvegarde
    return lire


@override_settings(PLUGNMEET_SERVER_URL=URL, PUBLIC_BASE_URL="")
@mock.patch.object(tasks, "jours_restants_certificat", return_value=90)
class SurveillanceSauvegardeTests(TestCase):
    def constats(self, **kw):
        with mock.patch.object(tasks, "lire", faux_lire(**kw)):
            return [c for c in tasks.anomalies() if "Sauvegarde" in c]

    def test_sauvegarde_recente(self, _):
        recente = (timezone.now() - datetime.timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
        self.assertEqual(self.constats(date_sauvegarde=recente), [])

    def test_sauvegarde_trop_ancienne(self, _):
        ancienne = (timezone.now() - datetime.timedelta(hours=27)).strftime("%Y-%m-%dT%H:%M:%SZ")
        self.assertEqual(self.constats(date_sauvegarde=ancienne), ["Sauvegarde plugNmeet : aucune réussite depuis plus de 26 h."])

    def test_date_illisible(self, _):
        self.assertEqual(self.constats(date_sauvegarde="<html>404</html>"), ["Sauvegarde plugNmeet : date de réussite illisible."])

    def test_fichier_injoignable(self, _):
        self.assertEqual(self.constats(erreur=OSError("refusé")), ["Sauvegarde plugNmeet : date de réussite illisible."])

    def test_incident_critique_cree(self, _):
        ancienne = (timezone.now() - datetime.timedelta(hours=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
        with mock.patch.object(tasks, "lire", faux_lire(date_sauvegarde=ancienne)):
            tasks.surveillance_plateforme()
            tasks.surveillance_plateforme()
        incident = TechnicalIncident.objects.get(message__contains="Sauvegarde plugNmeet")
        self.assertEqual((incident.severity, incident.module, incident.occurrences), ("critical", "surveillance", 2))
