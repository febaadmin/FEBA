"""
Tests — Invariant « une seule année active par établissement » (FIX v39).

Cause racine (vidéo) : plusieurs années pouvaient porter is_current=True,
désynchronisant la puce « Année active » et le contenu affiché.
"""
from django.db import IntegrityError, transaction
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status

from apps.accounts.models import CustomUser
from apps.schools.models import School, SchoolYear


def auth(client, email, password="Pass1234!"):
    resp = client.post("/api/auth/login/", {"email": email, "password": password})
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {resp.data.get('access', '')}")


class SingleActiveYearTests(TestCase):
    def setUp(self):
        self.school = School.objects.create(name="Ecole SA", address="X")
        self.y1 = SchoolYear.objects.create(
            school=self.school, name="2024-2025", is_current=True,
            start_date="2024-10-01", end_date="2025-07-31",
        )
        self.admin = CustomUser.objects.create_user(
            username="sav", email="sav@test.bj", password="Pass1234!",
            role="admin", first_name="S", last_name="A", school=self.school,
        )
        self.client = APIClient()
        auth(self.client, "sav@test.bj")

    def test_model_save_unsets_previous_active(self):
        y2 = SchoolYear.objects.create(
            school=self.school, name="2025-2026", is_current=True,
            start_date="2025-10-01", end_date="2026-07-31",
        )
        self.y1.refresh_from_db()
        self.assertFalse(self.y1.is_current)
        self.assertTrue(y2.is_current)
        self.assertEqual(
            SchoolYear.objects.filter(school=self.school, is_current=True).count(), 1
        )

    def test_constraint_blocks_two_active(self):
        """Insertion directe (contournant save()) → la contrainte DB refuse."""
        y2 = SchoolYear.objects.create(
            school=self.school, name="2025-2026", is_current=False,
            start_date="2025-10-01", end_date="2026-07-31",
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                SchoolYear.objects.filter(pk=y2.pk).update(is_current=True)

    def test_set_current_switches_atomically(self):
        y2 = SchoolYear.objects.create(
            school=self.school, name="2025-2026", is_current=False,
            start_date="2025-10-01", end_date="2026-07-31",
        )
        resp = self.client.post(f"/api/schools/years/{y2.id}/set_current/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.y1.refresh_from_db(); y2.refresh_from_db()
        self.assertFalse(self.y1.is_current)
        self.assertTrue(y2.is_current)
        self.assertEqual(
            SchoolYear.objects.filter(school=self.school, is_current=True).count(), 1
        )

    def test_two_schools_each_keep_their_own_active(self):
        other = School.objects.create(name="Ecole B", address="Y")
        oy = SchoolYear.objects.create(
            school=other, name="2024-2025", is_current=True,
            start_date="2024-10-01", end_date="2025-07-31",
        )
        # La contrainte est PAR établissement : les deux actives coexistent.
        self.assertTrue(self.y1.is_current)
        self.assertTrue(oy.is_current)
