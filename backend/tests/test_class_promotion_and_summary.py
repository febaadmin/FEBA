"""
Tests — Passage par classe, Résumé/Bilingue superadmin, classe par année (FIX v33).

Causes racines couvertes :
  1. bulk_promote_students(scope='class') retrouve les élèves via l'HISTORIQUE
     des inscriptions dans la classe (plus "0 élève inscrit" après une 1re promo).
  2. Le Résumé par élève et le Bilingue fonctionnent pour un superadmin
     (tenant déduit de l'élève) et pour une année passée (classe = celle de
     l'inscription de cette année-là).
  3. Grade._class_for_year renvoie la classe de l'inscription demandée.
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
from apps.students.services import bulk_promote_students
from apps.subjects.models import Subject
from apps.teachers.models import Teacher


def auth(client, email, password="Pass1234!"):
    resp = client.post("/api/auth/login/", {"email": email, "password": password})
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {resp.data.get('access', '')}")


class ClassPromotionTests(TestCase):
    def setUp(self):
        self.school = School.objects.create(name="Ecole P", address="X")
        self.y1 = SchoolYear.objects.create(
            school=self.school, name="2025-2026", is_current=False,
            start_date="2025-10-01", end_date="2026-07-31",
        )
        self.y2 = SchoolYear.objects.create(
            school=self.school, name="2026-2027", is_current=True,
            start_date="2026-10-01", end_date="2027-07-31",
        )
        lvl = Level.objects.create(school=self.school, name="4ème", order=8)
        lvl3 = Level.objects.create(school=self.school, name="3ème", order=9)
        self.cls_y1 = Class.objects.create(name="4ème-A", level=lvl, school_year=self.y1)
        self.cls_y2 = Class.objects.create(name="3ème-A", level=lvl3, school_year=self.y2)

        # 3 élèves inscrits en 4ème-A (année 1)
        self.students = []
        for i in range(3):
            s = Student.objects.create(
                school=self.school, first_name=f"E{i}", last_name="Test",
                current_class=self.cls_y1, school_year=self.y1,
            )
            StudentEnrollment.objects.create(
                student=s, school_year=self.y1, class_obj=self.cls_y1, promotion_status="new",
            )
            self.students.append(s)

    def test_class_promotion_finds_students_via_history(self):
        """Même après avoir bougé le pointeur, la classe source retrouve ses élèves."""
        # Simule une promotion antérieure : les pointeurs ne pointent plus vers cls_y1
        for s in self.students:
            s.current_class = self.cls_y2
            s.school_year = self.y2
            s.save(update_fields=["current_class", "school_year"])

        result = bulk_promote_students(
            school=self.school, target_year_id=self.y2.id, scope="class",
            source_class_id=self.cls_y1.id, target_class_id=self.cls_y2.id,
        )
        # Les 3 élèves sont retrouvés via leur inscription historique en 4ème-A
        self.assertEqual(result["enrolled"] + result["skipped"], 3)
        for s in self.students:
            self.assertTrue(
                StudentEnrollment.objects.filter(student=s, school_year=self.y2).exists()
            )

    def test_class_promotion_reports_zero_when_class_empty(self):
        empty = Class.objects.create(
            name="Vide-A", level=self.cls_y1.level, school_year=self.y1,
        )
        result = bulk_promote_students(
            school=self.school, target_year_id=self.y2.id, scope="class",
            source_class_id=empty.id,
        )
        self.assertEqual(result["enrolled"], 0)


class SummaryBilingualSuperadminTests(TestCase):
    def setUp(self):
        self.school = School.objects.create(name="Ecole S", address="X")
        self.year = SchoolYear.objects.create(
            school=self.school, name="2025-2026", is_current=True,
            start_date="2025-10-01", end_date="2026-07-31",
        )
        lvl = Level.objects.create(school=self.school, name="CE1", order=3)
        self.cls = Class.objects.create(name="CE1-A", level=lvl, school_year=self.year)
        self.fr = Subject.objects.create(school=self.school, name="Français", code="FR", coefficient=2, language="fr")
        self.en = Subject.objects.create(school=self.school, name="English", code="ENG", coefficient=2, language="en")
        self.cls.subjects.set([self.fr, self.en])

        self.superadmin = CustomUser.objects.create_user(
            username="sa3", email="sa3@test.bj", password="Pass1234!",
            role="superadmin", first_name="S", last_name="A",
        )
        self.student = Student.objects.create(
            school=self.school, first_name="Grace", last_name="Acakpo",
            current_class=self.cls, school_year=self.year,
        )
        StudentEnrollment.objects.create(
            student=self.student, school_year=self.year, class_obj=self.cls, promotion_status="new",
        )
        tu = CustomUser.objects.create_user(
            username="ts", email="ts@test.bj", password="Pass1234!",
            role="teacher", first_name="T", last_name="S", school=self.school,
        )
        self.teacher = Teacher.objects.create(user=tu)
        Grade.objects.create(student=self.student, subject=self.fr, school_year=self.year,
                             teacher=self.teacher, period="T1", value=15)
        Grade.objects.create(student=self.student, subject=self.en, school_year=self.year,
                             teacher=self.teacher, period="T1", value=10)
        self.client = APIClient()
        auth(self.client, "sa3@test.bj")

    def test_summary_works_for_superadmin(self):
        resp = self.client.get(
            f"/api/grades/student-summary/?student={self.student.id}&period=T1&school_year={self.year.id}"
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        self.assertEqual(resp.data["class_name"], "CE1-A")
        self.assertIsNotNone(resp.data["average"])

    def test_bilingual_works_for_superadmin(self):
        resp = self.client.get(
            f"/api/grades/bilingual/?student={self.student.id}&period=T1&school_year={self.year.id}"
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        # FR 15 (40%) + EN 10 (60%) = 6 + 6 = 12
        self.assertEqual(float(resp.data["bilingual_average"]), 12.0)
        self.assertTrue(resp.data["has_fr_subjects"])
        self.assertTrue(resp.data["has_en_subjects"])

    def test_class_for_year_resolution(self):
        self.assertEqual(Grade._class_for_year(self.student, self.year).id, self.cls.id)
