"""
Audit — annonces publiées par le super-administrateur.

Défaut : la portée des annonces était déduite de l'ACADÉMIE DE L'AUTEUR
(`author__school`). Le super-administrateur n'a pas d'académie : une
annonce qu'il publiait pour l'académie active (année scolaire de cette
académie) n'apparaissait nulle part — ni chez les parents et enseignants,
ni chez les administrateurs, ni chez lui-même — et son détail répondait 403.
"""
from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import CustomUser
from apps.announcements.models import Announcement
from apps.schools.models import School, SchoolYear


class SuperadminAnnouncementTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.feba = School.objects.create(name="FEBA Ann", address="x", code="ANN-FEBA")
        cls.fha = School.objects.create(name="FHA Ann", address="x", code="ANN-FHA")
        cls.year = SchoolYear.objects.create(school=cls.feba, name="2026-2027", is_current=True,
                                             start_date="2026-09-01", end_date="2027-07-01")
        SchoolYear.objects.create(school=cls.fha, name="2026-2027", is_current=True,
                                  start_date="2026-09-01", end_date="2027-07-01")
        cls.superadmin = CustomUser.objects.create_user(
            username="ann_super", email="ann.super@test.io", password="x", role="superadmin")
        cls.superadmin.active_organization = cls.feba
        cls.superadmin.save()
        cls.admin = CustomUser.objects.create_user(
            username="ann_admin", email="ann.admin@test.io", password="x", role="admin", school=cls.feba)
        cls.parent = CustomUser.objects.create_user(
            username="ann_parent", email="ann.parent@test.io", password="x", role="parent", school=cls.feba)
        cls.fha_parent = CustomUser.objects.create_user(
            username="ann_fha_parent", email="ann.fhaparent@test.io", password="x", role="parent", school=cls.fha)

    def api(self, user):
        client = APIClient()
        client.force_authenticate(user)
        return client

    def ids(self, user):
        data = self.api(user).get("/api/announcements/").json()
        return [a["id"] for a in data.get("results", data)]

    def test_superadmin_announcement_reaches_its_academy_only(self):
        resp = self.api(self.superadmin).post("/api/announcements/", {
            "title": "Rentrée", "content": "Lundi", "target_roles": ["all"]}, format="json")
        self.assertEqual(resp.status_code, 201, resp.content)
        ann_id = resp.json()["id"]
        self.assertEqual(Announcement.objects.get(pk=ann_id).school_year, self.year)
        self.assertIn(ann_id, self.ids(self.superadmin))
        self.assertIn(ann_id, self.ids(self.admin))
        self.assertIn(ann_id, self.ids(self.parent))
        self.assertNotIn(ann_id, self.ids(self.fha_parent))
        self.assertEqual(self.api(self.admin).get(f"/api/announcements/{ann_id}/").status_code, 200)
        self.assertEqual(self.api(self.fha_parent).get(f"/api/announcements/{ann_id}/").status_code, 404)
