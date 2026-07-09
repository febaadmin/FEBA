"""FIX v44 — pas de matière en double (nom + langue) dans un établissement."""
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status

from apps.accounts.models import CustomUser
from apps.schools.models import School
from apps.subjects.models import Subject


def auth(client, email, password="Pass1234!"):
    r = client.post("/api/auth/login/", {"email": email, "password": password})
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {r.data.get('access','')}")


class SubjectDedupTests(TestCase):
    def setUp(self):
        self.school = School.objects.create(name="Ecole S", address="X")
        self.admin = CustomUser.objects.create_user(
            username="a", email="a@test.bj", password="Pass1234!",
            role="admin", first_name="A", last_name="B", school=self.school,
        )
        Subject.objects.create(school=self.school, name="test", code="TST", coefficient=1, language="fr")
        self.client = APIClient()
        auth(self.client, "a@test.bj")

    def test_duplicate_subject_rejected(self):
        resp = self.client.post("/api/subjects/", {
            "school": self.school.id, "name": "test", "code": "TST2",
            "coefficient": 1, "language": "fr",
        }, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("name", resp.data)

    def test_same_name_other_language_allowed(self):
        resp = self.client.post("/api/subjects/", {
            "school": self.school.id, "name": "test", "code": "TSTEN",
            "coefficient": 1, "language": "en",
        }, format="json")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
