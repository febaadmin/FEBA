"""
Audit du 26/10/2026 — défauts confirmés (reproduits sur le code livré
FEBA_VERSION_FINALE_VALIDEE_PRODUCTION) et leurs tests de non-régression.
"""
from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import CustomUser
from apps.schools.models import Level, Room, RoomType, School


class EntityTypeIsPlatformOnlyTests(TestCase):
    """Un administrateur d'académie ne change pas le type de son académie."""

    def setUp(self):
        self.feba = School.objects.create(name="FEBA", address="X", entity_type="campus", code="FEBA-A")
        self.admin = CustomUser.objects.create_user(
            username="a", email="a@a.test", password="Pass1234!", role="admin", school=self.feba,
            first_name="A", last_name="A")
        self.su = CustomUser.objects.create_user(
            username="s", email="s@a.test", password="Pass1234!", role="superadmin",
            first_name="S", last_name="U")

    def test_admin_ne_debloque_pas_les_fonctions_en_ligne(self):
        c = APIClient()
        c.force_authenticate(self.admin)
        r = c.patch(f"/api/schools/schools/{self.feba.pk}/", {"entity_type": "online", "phone": "0100"}, format="json")
        self.assertEqual(r.status_code, 200)
        self.feba.refresh_from_db()
        self.assertEqual(self.feba.entity_type, "campus")        # avant : "online"
        self.assertEqual(self.feba.phone, "0100")                 # les autres champs restent modifiables
        self.assertFalse(self.feba.has_feature("monolingual_classes"))
        self.assertFalse(self.feba.has_feature("placement_tests"))

    def test_le_super_administrateur_peut_le_modifier(self):
        c = APIClient()
        c.force_authenticate(self.su)
        r = c.patch(f"/api/schools/schools/{self.feba.pk}/", {"entity_type": "online"}, format="json")
        self.assertEqual(r.status_code, 200)
        self.feba.refresh_from_db()
        self.assertEqual(self.feba.entity_type, "online")


class SchoolStructureStaysInItsAcademyTests(TestCase):
    """Un niveau, un type de salle ou une salle ne changent pas d'académie."""

    def setUp(self):
        self.a = School.objects.create(name="A", address="X", code="AC-A")
        self.b = School.objects.create(name="B", address="X", code="AC-B")
        self.admin = CustomUser.objects.create_user(
            username="aa", email="aa@a.test", password="Pass1234!", role="admin", school=self.a,
            first_name="A", last_name="A")
        self.level = Level.objects.create(school=self.a, name="CE1", order=1)
        self.rt_a = RoomType.objects.create(school=self.a, name="Salle de classe")
        self.rt_b = RoomType.objects.create(school=self.b, name="Labo B")
        self.room = Room.objects.create(school=self.a, name="Salle 1", room_type_obj=self.rt_a)
        self.c = APIClient()
        self.c.force_authenticate(self.admin)

    def test_patch_school_refuse(self):
        for url, obj in ((f"/api/schools/levels/{self.level.pk}/", self.level),
                         (f"/api/schools/room-types/{self.rt_a.pk}/", self.rt_a),
                         (f"/api/schools/rooms/{self.room.pk}/", self.room)):
            r = self.c.patch(url, {"school": self.b.pk}, format="json")
            self.assertEqual(r.status_code, 400, url)
            obj.refresh_from_db()
            self.assertEqual(obj.school_id, self.a.pk, url)       # avant : déplacé dans B

    def test_type_de_salle_d_une_autre_academie_refuse(self):
        r = self.c.patch(f"/api/schools/rooms/{self.room.pk}/", {"room_type_obj": self.rt_b.pk}, format="json")
        self.assertEqual(r.status_code, 400)
        r = self.c.post("/api/schools/rooms/", {"name": "Intrus", "room_type_obj": self.rt_b.pk}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_les_modifications_normales_restent_possibles(self):
        r = self.c.patch(f"/api/schools/levels/{self.level.pk}/", {"name": "CE1 bis", "school": self.a.pk},
                         format="json")
        self.assertEqual(r.status_code, 200, r.data)
        r = self.c.post("/api/schools/levels/", {"name": "CE2", "order": 2, "school": self.a.pk}, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(Level.objects.get(name="CE2").school, self.a)


class AdmissionFilesStayInTheirAcademyTests(TestCase):
    """Un dossier d'admission ou un test de placement ne change pas d'académie par PATCH."""

    def setUp(self):
        from datetime import date
        from apps.website.models import FHAEnrollmentApplication, FHAPlacementTestRequest
        self.fha = School.objects.create(name="FHA", address="X", code="FHA-T", entity_type="online")
        self.feba = School.objects.create(name="FEBA", address="X", code="FEBA-T")
        self.admin = CustomUser.objects.create_user(
            username="fh", email="fh@a.test", password="Pass1234!", role="admin", school=self.fha,
            first_name="F", last_name="H")
        self.app = FHAEnrollmentApplication.objects.create(
            entity=self.fha, child_first_name="Ben", child_last_name="Smith",
            child_birth_date=date(2016, 3, 2), parent1_first_name="Paul", parent1_last_name="Smith",
            parent1_phone="+15550000000", parent1_email="p@x.com")
        self.test_req = FHAPlacementTestRequest.objects.create(
            entity=self.fha, child_first_name="Ben", child_last_name="Smith",
            child_birth_date=date(2016, 3, 2), parent_email="p@x.com", parent_first_name="Paul",
            parent_last_name="Smith", parent_phone="+15550000000")
        self.c = APIClient()
        self.c.force_authenticate(self.admin)

    def test_dossier_non_transfere(self):
        self.c.patch(f"/api/website/admin/fha-applications/{self.app.pk}/", {"entity": self.feba.pk},
                     format="json")
        self.app.refresh_from_db()
        self.assertEqual(self.app.entity_id, self.fha.pk)          # avant : transféré à FEBA

    def test_test_de_placement_non_transfere(self):
        self.c.patch(f"/api/website/admin/fha-placement-tests/{self.test_req.pk}/",
                     {"entity": self.feba.pk}, format="json")
        self.test_req.refresh_from_db()
        self.assertEqual(self.test_req.entity_id, self.fha.pk)
