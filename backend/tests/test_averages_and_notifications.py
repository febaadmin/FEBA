"""
Tests — Endpoint moyennes robuste & unread-count (FIX v41).

Causes racines (console élève) :
  1. GET /api/grades/averages/ renvoyait 500 :
     - float(None) sur une matière non notée (règle v32),
     - SchoolYear.DoesNotExist non gérée quand school=None (élève/superadmin).
  2. GET /api/notifications/unread-count/ → 404 (route masquée par le
     routeur DRF <pk>/).
"""
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status

from apps.accounts.models import CustomUser
from apps.classes.models import Class
from apps.grades.models import Grade
from apps.schools.models import School, SchoolYear, Level
from apps.students.models import Student, StudentEnrollment
from apps.subjects.models import Subject
from apps.teachers.models import Teacher


def auth(client, email, password="Pass1234!"):
    resp = client.post("/api/auth/login/", {"email": email, "password": password})
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {resp.data.get('access', '')}")


class AveragesEndpointTests(TestCase):
    def setUp(self):
        self.school = School.objects.create(name="Ecole Avg", address="X")
        self.year = SchoolYear.objects.create(
            school=self.school, name="2026-2027", is_current=True,
            start_date="2026-10-01", end_date="2027-07-31",
        )
        lvl = Level.objects.create(school=self.school, name="CE1", order=3)
        self.cls = Class.objects.create(name="CE1-A", level=lvl, school_year=self.year)
        self.fr = Subject.objects.create(school=self.school, name="Français", code="FR", coefficient=4, language="fr")
        self.en = Subject.objects.create(school=self.school, name="English", code="ENG", coefficient=4, language="en")
        self.cls.subjects.set([self.fr, self.en])

        self.student_user = CustomUser.objects.create_user(
            username="marie", email="marie@test.bj", password="Pass1234!",
            role="student", first_name="Marie", last_name="Agossou", school=self.school,
        )
        self.student = Student.objects.create(
            user=self.student_user, school=self.school,
            first_name="Marie", last_name="Agossou",
            current_class=self.cls, school_year=self.year,
        )
        StudentEnrollment.objects.create(
            student=self.student, school_year=self.year, class_obj=self.cls,
        )
        self.client = APIClient()
        auth(self.client, "marie@test.bj")

    def test_averages_no_grades_returns_200_null(self):
        """Élève sans note dans l'année : 200 + moyenne null, pas de 500."""
        resp = self.client.get(f"/api/grades/averages/?period=T1&school_year={self.year.id}")
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        self.assertIsNone(resp.data["average"])

    def test_averages_partial_grades_no_crash_on_none(self):
        """Une seule matière notée : l'autre a average=None → pas de float(None)."""
        tu = CustomUser.objects.create_user(
            username="t", email="t@test.bj", password="Pass1234!",
            role="teacher", first_name="T", last_name="U", school=self.school,
        )
        teacher = Teacher.objects.create(user=tu)
        Grade.objects.create(student=self.student, subject=self.fr, school_year=self.year,
                             teacher=teacher, period="T1", value=15)
        resp = self.client.get(f"/api/grades/averages/?period=T1&school_year={self.year.id}")
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        self.assertEqual(float(resp.data["average"]), 15.0)   # seule la matière notée compte
        by_subj = resp.data["by_subject"]
        # La matière anglaise non notée est présente avec average=None (pas de crash)
        en_entry = [v for v in by_subj.values() if v["name"] == "English"][0]
        self.assertIsNone(en_entry["average"])

    def test_averages_unknown_year_falls_back(self):
        """school_year inexistant → repli sur l'année active, pas de 500."""
        resp = self.client.get("/api/grades/averages/?period=T1&school_year=99999")
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)

    def test_averages_autodetects_student(self):
        """Sans paramètre student, l'élève connecté est auto-détecté."""
        resp = self.client.get(f"/api/grades/averages/?period=T1&school_year={self.year.id}")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(str(resp.data["student"]), str(self.student.id))


class UnreadCountRouteTests(TestCase):
    def setUp(self):
        self.school = School.objects.create(name="Ecole N", address="X")
        self.user = CustomUser.objects.create_user(
            username="nu", email="nu@test.bj", password="Pass1234!",
            role="student", first_name="N", last_name="U", school=self.school,
        )
        self.client = APIClient()
        auth(self.client, "nu@test.bj")

    def test_unread_count_hyphen_route_ok(self):
        """La route à tiret n'est plus masquée par le routeur (plus de 404)."""
        resp = self.client.get("/api/notifications/unread-count/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        self.assertIn("count", resp.data)


class BilingualSafetyTests(TestCase):
    """FIX v42 — le calcul bilingue ne renvoie jamais 500 (message trompeur)."""
    def setUp(self):
        self.school = School.objects.create(name="Ecole Bil", address="X")
        self.year = SchoolYear.objects.create(
            school=self.school, name="2024-2025",
            start_date="2024-10-01", end_date="2025-07-31",
        )
        self.active = SchoolYear.objects.create(
            school=self.school, name="2025-2026", is_current=True,
            start_date="2025-10-01", end_date="2026-07-31",
        )
        lvl = Level.objects.create(school=self.school, name="CM1", order=5)
        self.cls = Class.objects.create(name="CM1-A", level=lvl, school_year=self.year)
        # Classe SANS matières FR/EN assignées → doit renvoyer has_*: false, pas 500
        self.student = Student.objects.create(
            school=self.school, first_name="Estelle", last_name="Acakpo",
            current_class=self.cls, school_year=self.year,
        )
        StudentEnrollment.objects.create(
            student=self.student, school_year=self.year, class_obj=self.cls,
        )
        admin = CustomUser.objects.create_user(
            username="ab", email="ab@test.bj", password="Pass1234!",
            role="admin", first_name="A", last_name="B", school=self.school,
        )
        self.client = APIClient()
        auth(self.client, "ab@test.bj")

    def test_bilingual_no_subjects_returns_200(self):
        resp = self.client.get(
            f"/api/grades/bilingual/?student={self.student.id}&period=T1&school_year={self.year.id}"
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        self.assertFalse(resp.data.get("has_fr_subjects"))
        self.assertFalse(resp.data.get("has_en_subjects"))

    def test_bilingual_annual_no_crash(self):
        resp = self.client.get(
            f"/api/grades/bilingual/?student={self.student.id}&school_year={self.year.id}"
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)


class BilingualRouteAndAvatarTests(TestCase):
    """
    FIX v42 :
      - /api/grades/bilingual/ n'est plus masqué par le routeur <pk>/ (200, pas 404).
      - L'avatar est sérialisé en chemin RELATIF (jamais http://backend-dev:8000).
    """
    def setUp(self):
        self.school = School.objects.create(name="Ecole RA", address="X")
        self.year = SchoolYear.objects.create(
            school=self.school, name="2025-2026", is_current=True,
            start_date="2025-10-01", end_date="2026-07-31",
        )
        lvl = Level.objects.create(school=self.school, name="CM1", order=5)
        self.cls = Class.objects.create(name="CM1-A", level=lvl, school_year=self.year)
        self.student = Student.objects.create(
            school=self.school, first_name="Estelle", last_name="Acakpo",
            current_class=self.cls, school_year=self.year,
        )
        StudentEnrollment.objects.create(
            student=self.student, school_year=self.year, class_obj=self.cls,
        )
        self.admin = CustomUser.objects.create_user(
            username="ra", email="ra@test.bj", password="Pass1234!",
            role="admin", first_name="R", last_name="A", school=self.school,
        )
        self.client = APIClient()
        auth(self.client, "ra@test.bj")

    def test_bilingual_route_not_shadowed_by_router(self):
        """La route explicite précède <pk>/ → 200, plus jamais 404."""
        resp = self.client.get(
            f"/api/grades/bilingual/?student={self.student.id}&period=T1&school_year={self.year.id}"
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        self.assertIn("has_fr_subjects", resp.data)

    def test_all_history_route_not_shadowed(self):
        resp = self.client.get(f"/api/grades/all-history/?student={self.student.id}")
        self.assertIn(resp.status_code, (200, 400))  # pas 404 (route résolue)

    def test_avatar_serialized_relative(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        # 1x1 GIF
        gif = (b"GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff!"
               b"\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01"
               b"\x00\x00\x02\x02D\x01\x00;")
        self.admin.avatar = SimpleUploadedFile("a.gif", gif, content_type="image/gif")
        self.admin.save()
        resp = self.client.get("/api/auth/me/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        avatar = resp.data.get("avatar")
        self.assertIsNotNone(avatar)
        self.assertTrue(avatar.startswith("/media/"), f"attendu relatif, reçu {avatar}")
        self.assertNotIn("backend-dev", avatar)
        self.assertNotIn("http", avatar)
