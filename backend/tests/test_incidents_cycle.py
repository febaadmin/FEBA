"""Cycle de vie d'un incident : à valider, résolu, réouverture, historique, compteurs."""
from django.test import TestCase
from rest_framework.test import APIClient

from apps.incidents.models import TechnicalIncident, changer_statut
from apps.incidents.services import report_incident
from tests.test_virtualclass import make_school, make_user


class CycleTests(TestCase):
    def setUp(self):
        self.su = make_user("su-inc@test.bj", "superadmin", make_school())
        self.api = APIClient()
        self.api.force_authenticate(self.su)
        self.inc = report_incident(ValueError("boum"), module="essai")

    def test_nouvelle_occurrence_apres_correction_rouvre_le_meme_incident(self):
        for statut in ("corrected", "resolved"):
            changer_statut(self.inc, statut, self.su)
            revu = report_incident(ValueError("boum"), module="essai")
            self.assertEqual(revu.pk, self.inc.pk, statut)
            self.inc.refresh_from_db()
            self.assertEqual(self.inc.status, "reopened", statut)
            self.assertIsNone(self.inc.resolved_at)
        self.assertEqual(TechnicalIncident.objects.count(), 1)
        self.assertEqual(self.inc.occurrences, 3)

    def test_incident_ignore_reste_ignore(self):
        changer_statut(self.inc, "ignored", self.su)
        report_incident(ValueError("boum"), module="essai")
        self.inc.refresh_from_db()
        self.assertEqual(self.inc.status, "ignored")

    def test_compteurs_filtres_et_historique(self):
        url = f"/api/incidents/{self.inc.pk}/"
        self.assertEqual(self.api.patch(url, {"status": "corrected", "resolution_notes": "PR 1"}, format="json").status_code, 200)
        self.assertEqual(self.api.get("/api/incidents/stats/").data["by_status"]["corrected"], 1)
        liste = self.api.get("/api/incidents/", {"status": "corrected"}).data
        self.assertEqual(liste.get("count", len(liste)), 1)
        self.assertEqual(self.api.post(f"{url}resolve/", {"resolution_notes": "preuve"}, format="json").status_code, 200)
        self.inc.refresh_from_db()
        self.assertEqual(self.inc.status, "resolved")
        self.assertIsNotNone(self.inc.resolved_at)
        self.assertEqual(self.api.post(f"{url}reopen/", {}, format="json").status_code, 200)
        evenements = self.api.get(url).data["status_events"]
        self.assertEqual([e["to_status"] for e in evenements], ["corrected", "resolved", "reopened"])
        self.assertEqual(evenements[0]["performed_by_email"], self.su.email)

    def test_note_malformee_ne_provoque_pas_d_erreur_serveur(self):
        rep = self.api.post(f"/api/incidents/{self.inc.pk}/resolve/", {"resolution_notes": {"a": 1}}, format="json")
        self.assertEqual(rep.status_code, 400)
        self.assertEqual(TechnicalIncident.objects.count(), 1)
