"""
Régression V7 — Priorité 4 : la note saisie n'est JAMAIS altérée.

Bug : « 10 » était enregistré/affiché comme 9,5 ou 9,75. Cause racine côté
frontend (champ <input type="number" step="0.25"> modifié en silence par la
molette/les flèches). Le backend, lui, doit stocker et renvoyer EXACTEMENT la
valeur reçue — ces tests le prouvent de bout en bout (DB + API) pour la saisie
simple ET la saisie groupée, sur toute une plage de valeurs entières et
décimales.
"""
from decimal import Decimal

from rest_framework.test import APIClient
from rest_framework import status

from apps.grades.models import Grade
from tests.test_bulk_grades import BulkGradeFixture, auth, URL as BULK_URL

SINGLE_URL = "/api/grades/"
# Plage exigée par la mission.
VALUES = ["0", "0.25", "0.5", "1", "9.5", "9.75", "10",
          "10.25", "10.5", "10.75", "15", "19.5", "19.75", "20"]


class GradePrecisionSingleTests(BulkGradeFixture):
    def setUp(self):
        self.client = APIClient()
        auth(self.client, "prof@test.bj")

    def test_saisir_10_reste_exactement_10(self):
        """Régression explicite : saisir 10 doit stocker et renvoyer 10."""
        resp = self.client.post(SINGLE_URL, {
            "student": self.student.id, "subject": self.math.id,
            "school_year": self.year.id, "period": "T1",
            "value": "10", "note_type": "controle", "note_coefficient": 1,
        }, format="json")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        grade = Grade.objects.get(id=resp.data["id"])
        self.assertEqual(grade.value, Decimal("10.00"))
        self.assertEqual(Decimal(str(resp.data["value"])), Decimal("10"))
        # Jamais 9,5 ni 9,75.
        self.assertNotIn(grade.value, [Decimal("9.5"), Decimal("9.75")])

    def test_toutes_les_valeurs_conservees(self):
        for v in VALUES:
            resp = self.client.post(SINGLE_URL, {
                "student": self.student.id, "subject": self.math.id,
                "school_year": self.year.id, "period": "T2",
                "value": v, "note_type": "devoir", "note_coefficient": 1,
            }, format="json")
            self.assertEqual(resp.status_code, status.HTTP_201_CREATED, (v, resp.data))
            grade = Grade.objects.get(id=resp.data["id"])
            self.assertEqual(grade.value, Decimal(v), f"stockage altéré pour {v}")
            self.assertEqual(Decimal(str(resp.data["value"])), Decimal(v), f"API altérée pour {v}")
            grade.delete()

    def test_modification_conserve_la_valeur(self):
        # Crée via l'API (grade visible dans le queryset de l'enseignant), note 8…
        created = self.client.post(SINGLE_URL, {
            "student": self.student.id, "subject": self.math.id,
            "school_year": self.year.id, "period": "T1",
            "value": "8", "note_type": "devoir", "note_coefficient": 1,
        }, format="json")
        self.assertEqual(created.status_code, status.HTTP_201_CREATED, created.data)
        gid = created.data["id"]
        # …puis corrige à 10 (via l'admin, périmètre établissement) : la
        # nouvelle valeur doit être exactement 10.
        auth(self.client, "adm@test.bj")
        resp = self.client.patch(f"{SINGLE_URL}{gid}/", {"value": "10", "justification": "corr"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        self.assertEqual(Grade.objects.get(id=gid).value, Decimal("10.00"))


class GradePrecisionBulkTests(BulkGradeFixture):
    def setUp(self):
        self.client = APIClient()
        auth(self.client, "prof@test.bj")

    def test_bulk_saisir_10_reste_10(self):
        resp = self.client.post(BULK_URL, {
            "student": self.student.id, "school_year": self.year.id,
            "grades": [{"subject": self.math.id, "period": "T1", "value": "10",
                        "note_type": "controle", "note_coefficient": 1}],
        }, format="json")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        g = Grade.objects.filter(student=self.student, subject=self.math, period="T1").latest("id")
        self.assertEqual(g.value, Decimal("10.00"))

    def test_bulk_valeurs_decimales_conservees(self):
        for v in ["9.5", "9.75", "10", "10.25", "20"]:
            resp = self.client.post(BULK_URL, {
                "student": self.student.id, "school_year": self.year.id,
                "grades": [{"subject": self.math.id, "period": "T3", "value": v,
                            "note_type": "devoir", "note_coefficient": 1}],
            }, format="json")
            self.assertEqual(resp.status_code, status.HTTP_201_CREATED, (v, resp.data))
            g = Grade.objects.filter(student=self.student, period="T3").latest("id")
            self.assertEqual(g.value, Decimal(v), f"bulk altéré pour {v}")
            g.delete()
