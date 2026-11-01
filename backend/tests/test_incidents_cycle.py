"""Cycle de vie d'un incident : à valider, résolu, réouverture, historique, compteurs."""
from django.test import TestCase
from rest_framework.test import APIClient

from apps.incidents.models import NIVEAUX_VALIDATION, validations_manquantes, TechnicalIncident, changer_statut
from apps.incidents.services import report_incident
from tests.test_virtualclass import make_school, make_user


class CycleTests(TestCase):
    def setUp(self):
        self.su = make_user("su-inc@test.bj", "superadmin", make_school())
        self.api = APIClient()
        self.api.force_authenticate(self.su)
        self.inc = report_incident(ValueError("boum"), module="essai")

    def valider(self, sauf=()):
        self.inc.validations = {n: {"fait": True, "preuve": "preuve"} for n in NIVEAUX_VALIDATION if n not in sauf}
        self.inc.save(update_fields=["validations"])

    def test_resolution_refusee_sans_preuve_de_production_et_d_utilisateur(self):
        url = f"/api/incidents/{self.inc.pk}/"
        for sauf in (("test_production",), ("utilisateur",), ("developpe",), ("tests_auto",)):
            self.valider(sauf)
            for rep in (self.api.post(f"{url}resolve/", {}, format="json"),
                        self.api.patch(url, {"status": "resolved"}, format="json")):
                self.assertEqual(rep.status_code, 400, sauf)
            self.inc.refresh_from_db()
            self.assertNotEqual(self.inc.status, "resolved")
        self.valider(("test_local",))     # un test local n'est jamais obligatoire ni suffisant
        self.assertEqual(self.api.patch(url, {"status": "resolved"}, format="json").status_code, 200)

    def test_coche_sans_preuve_ne_compte_pas(self):
        self.inc.validations = {n: {"fait": True, "preuve": " "} for n in NIVEAUX_VALIDATION}
        self.inc.save(update_fields=["validations"])
        self.assertEqual(len(validations_manquantes(self.inc)), 4)

    def test_validations_mal_formees_refusees(self):
        url = f"/api/incidents/{self.inc.pk}/"
        for corps in ("x", {"inconnu": {"fait": True}}, {"utilisateur": {"fait": "oui"}}, {"utilisateur": 1}):
            self.assertEqual(self.api.patch(url, {"validations": corps}, format="json").status_code, 400, corps)

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
        self.valider()
        self.assertEqual(self.api.post(f"{url}resolve/", {"resolution_notes": "preuve"}, format="json").status_code, 200)
        self.inc.refresh_from_db()
        self.assertEqual(self.inc.status, "resolved")
        self.assertIsNotNone(self.inc.resolved_at)
        self.assertEqual(self.api.post(f"{url}reopen/", {}, format="json").status_code, 200)
        evenements = self.api.get(url).data["status_events"]
        self.assertEqual([e["to_status"] for e in evenements], ["corrected", "resolved", "reopened"])
        self.assertEqual(evenements[0]["performed_by_email"], self.su.email)

    def test_note_malformee_ne_provoque_pas_d_erreur_serveur(self):
        self.valider()
        rep = self.api.post(f"/api/incidents/{self.inc.pk}/resolve/", {"resolution_notes": {"a": 1}}, format="json")
        self.assertEqual(rep.status_code, 400)
        self.assertEqual(TechnicalIncident.objects.count(), 1)
