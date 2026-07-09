"""
Tests — Gestion des années scolaires & promotions (FIX v31).

Chaque test couvre une cause racine corrigée :
  1. Le filtre ?school_year= de la liste élèves interroge l'HISTORIQUE des
     inscriptions (un élève promu reste visible dans ses années passées),
     et la classe affichée est celle de l'année demandée.
  2. Un SUPERADMIN (sans établissement propre) peut lancer un passage de
     niveau : le tenant est déduit de l'année scolaire cible.
  3. Le passage crée une NOUVELLE inscription sans modifier l'ancienne.
  4. L'endpoint history renvoie le dossier par année (stats) et le drapeau
     is_current_year (badge "Actuel" correct).
  5. Un superadmin crée un élève : le tenant est déduit de l'année fournie.
"""
import datetime

from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status

from apps.accounts.models import CustomUser
from apps.classes.models import Class
from apps.grades.models import Grade
from apps.schools.models import School, SchoolYear, Level
from apps.students.models import Student, StudentEnrollment
from apps.teachers.models import Teacher


def auth(client, email, password="Pass1234!"):
    resp = client.post("/api/auth/login/", {"email": email, "password": password})
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {resp.data.get('access', '')}")


class SchoolYearHistoryTests(TestCase):
    def setUp(self):
        self.school = School.objects.create(name="Ecole H", address="X")
        self.year_prev = SchoolYear.objects.create(
            school=self.school, name="2024-2025",
            start_date=datetime.date(2024, 10, 1), end_date=datetime.date(2025, 7, 31),
        )
        self.year_curr = SchoolYear.objects.create(
            school=self.school, name="2025-2026", is_current=True,
            start_date=datetime.date(2025, 10, 1), end_date=datetime.date(2026, 7, 31),
        )
        lvl_cm1 = Level.objects.create(school=self.school, name="CM1", order=4)
        lvl_cm2 = Level.objects.create(school=self.school, name="CM2", order=5)
        self.cls_prev = Class.objects.create(name="CM1-A", level=lvl_cm1, school_year=self.year_prev)
        self.cls_curr = Class.objects.create(name="CM2-A", level=lvl_cm2, school_year=self.year_curr)

        self.superadmin = CustomUser.objects.create_user(
            username="sa", email="sa@test.bj", password="Pass1234!", role="superadmin",
            first_name="S", last_name="A",
        )
        self.admin = CustomUser.objects.create_user(
            username="ad", email="ad@test.bj", password="Pass1234!", role="admin",
            first_name="A", last_name="D", school=self.school,
        )

        self.student = Student.objects.create(
            school=self.school, first_name="Emeka", last_name="Adjou",
            current_class=self.cls_prev, school_year=self.year_prev,
        )
        StudentEnrollment.objects.create(
            student=self.student, school_year=self.year_prev,
            class_obj=self.cls_prev, promotion_status="new",
        )
        self.client = APIClient()

    def _promote_via_api(self):
        auth(self.client, "sa@test.bj")
        return self.client.post("/api/students/enroll-all-from-year/", {
            "source_year_id": self.year_prev.id,
            "target_year_id": self.year_curr.id,
        }, format="json")

    def test_superadmin_can_bulk_promote_without_own_school(self):
        """FIX v31 : le tenant est déduit de l'année cible pour le superadmin."""
        resp = self._promote_via_api()
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(
            StudentEnrollment.objects.filter(student=self.student).count(), 2,
        )

    def test_promotion_creates_new_enrollment_without_touching_old(self):
        old = StudentEnrollment.objects.get(student=self.student, school_year=self.year_prev)
        self._promote_via_api()
        old.refresh_from_db()
        self.assertEqual(old.class_obj_id, self.cls_prev.id)
        self.assertEqual(old.promotion_status, "new")
        new = StudentEnrollment.objects.get(student=self.student, school_year=self.year_curr)
        self.assertNotEqual(new.pk, old.pk)

    def test_past_year_filter_uses_enrollment_history(self):
        """L'élève promu reste visible dans l'année passée, avec sa classe d'alors."""
        self._promote_via_api()
        # Affecter la classe de l'année courante pour vérifier la distinction
        enr = StudentEnrollment.objects.get(student=self.student, school_year=self.year_curr)
        enr.class_obj = self.cls_curr
        enr.save(update_fields=["class_obj"])
        self.student.current_class = self.cls_curr
        self.student.school_year = self.year_curr
        self.student.save(update_fields=["current_class", "school_year"])

        auth(self.client, "ad@test.bj")
        resp = self.client.get(f"/api/students/?school_year={self.year_prev.id}")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        results = resp.data.get("results", resp.data)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["class_name"], "CM1-A")       # classe de l'année demandée
        self.assertEqual(results[0]["school_year_name"], "2024-2025")

        resp2 = self.client.get(f"/api/students/?school_year={self.year_curr.id}")
        results2 = resp2.data.get("results", resp2.data)
        self.assertEqual(len(results2), 1)
        self.assertEqual(results2[0]["class_name"], "CM2-A")      # classe de l'année courante

    def test_history_endpoint_returns_stats_and_current_flag(self):
        self._promote_via_api()
        teacher_u = CustomUser.objects.create_user(
            username="t1", email="t1@test.bj", password="Pass1234!", role="teacher",
            first_name="T", last_name="U", school=self.school,
        )
        teacher = Teacher.objects.create(user=teacher_u)
        from apps.subjects.models import Subject
        subj = Subject.objects.create(school=self.school, name="Maths", code="MATH", coefficient=4)
        Grade.objects.create(
            student=self.student, subject=subj, school_year=self.year_prev,
            teacher=teacher, period="T1", value=14,
        )

        auth(self.client, "ad@test.bj")
        resp = self.client.get(f"/api/students/{self.student.id}/history/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        by_year = {e["school_year_name"]: e for e in resp.data}
        self.assertIn("2024-2025", by_year)
        self.assertIn("2025-2026", by_year)
        self.assertEqual(by_year["2024-2025"]["stats"]["grades_count"], 1)
        self.assertAlmostEqual(by_year["2024-2025"]["stats"]["grades_average"], 14.0)
        # Badge "Actuel" : uniquement l'année active
        self.assertFalse(by_year["2024-2025"]["is_current_year"])
        self.assertTrue(by_year["2025-2026"]["is_current_year"])

    def test_superadmin_creates_student_tenant_inferred_from_year(self):
        auth(self.client, "sa@test.bj")
        resp = self.client.post("/api/students/", {
            "first_name": "Awa", "last_name": "Diallo",
            "school_year": self.year_curr.id,
        }, format="json")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        s = Student.objects.get(pk=resp.data["id"])
        self.assertEqual(s.school_id, self.school.id)
