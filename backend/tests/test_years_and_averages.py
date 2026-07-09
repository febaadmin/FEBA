"""
Tests — Années scolaires (création/validation) & moteur de moyennes (FIX v32).

Couvre les causes racines corrigées :
  1. Un superadmin crée une année scolaire (le tenant vient du payload ou,
     à défaut, de l'unique établissement) — plus d'IntegrityError 500.
  2. Validations métier : fin > début ; nom unique par établissement
     (message explicite, plus d'erreur brute).
  3. Une seule année active : en créer/activer une désactive les autres ;
     l'action close/ clôture l'année active.
  4. Moteur de moyennes : une matière SANS note est exclue de la moyenne
     générale (elle ne compte plus 0 avec son coefficient).
"""
import datetime

from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status

from apps.accounts.models import CustomUser
from apps.classes.models import Class
from apps.grades.models import Grade
from apps.schools.models import School, SchoolYear, Level
from apps.students.models import Student
from apps.subjects.models import Subject
from apps.teachers.models import Teacher


def auth(client, email, password="Pass1234!"):
    resp = client.post("/api/auth/login/", {"email": email, "password": password})
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {resp.data.get('access', '')}")


class SchoolYearCreationTests(TestCase):
    def setUp(self):
        self.school = School.objects.create(name="Ecole Y", address="X")
        self.superadmin = CustomUser.objects.create_user(
            username="sa2", email="sa2@test.bj", password="Pass1234!",
            role="superadmin", first_name="S", last_name="A",
        )
        self.client = APIClient()
        auth(self.client, "sa2@test.bj")

    def test_superadmin_creates_year_school_from_payload(self):
        resp = self.client.post("/api/schools/years/", {
            "name": "2026-2027", "school": self.school.id,
            "start_date": "2026-08-31", "end_date": "2027-07-31",
        }, format="json")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        self.assertEqual(SchoolYear.objects.get(name="2026-2027").school_id, self.school.id)

    def test_superadmin_creates_year_single_school_inferred(self):
        """Sans school dans le payload : mono-établissement → déduit."""
        resp = self.client.post("/api/schools/years/", {
            "name": "2027-2028",
            "start_date": "2027-09-01", "end_date": "2028-07-31",
        }, format="json")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)

    def test_end_date_must_be_after_start_date(self):
        resp = self.client.post("/api/schools/years/", {
            "name": "2026-2027", "school": self.school.id,
            "start_date": "2027-07-31", "end_date": "2026-08-31",
        }, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("end_date", resp.data)

    def test_duplicate_year_name_rejected_with_clear_message(self):
        SchoolYear.objects.create(
            school=self.school, name="2026-2027",
            start_date="2026-08-31", end_date="2027-07-31",
        )
        resp = self.client.post("/api/schools/years/", {
            "name": "2026-2027", "school": self.school.id,
            "start_date": "2026-08-31", "end_date": "2027-07-31",
        }, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("name", resp.data)

    def test_single_current_year_enforced_and_close(self):
        y1 = SchoolYear.objects.create(
            school=self.school, name="2025-2026", is_current=True,
            start_date="2025-10-01", end_date="2026-07-31",
        )
        resp = self.client.post("/api/schools/years/", {
            "name": "2026-2027", "school": self.school.id, "is_current": True,
            "start_date": "2026-08-31", "end_date": "2027-07-31",
        }, format="json")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        y1.refresh_from_db()
        self.assertFalse(y1.is_current)
        self.assertEqual(SchoolYear.objects.filter(school=self.school, is_current=True).count(), 1)

        y2 = SchoolYear.objects.get(name="2026-2027")
        resp2 = self.client.post(f"/api/schools/years/{y2.id}/close/")
        self.assertEqual(resp2.status_code, status.HTTP_200_OK)
        y2.refresh_from_db()
        self.assertFalse(y2.is_current)


class AverageEngineTests(TestCase):
    """Une matière non notée ne compte plus 0 dans la moyenne générale."""

    def setUp(self):
        self.school = School.objects.create(name="Ecole M", address="X")
        self.year = SchoolYear.objects.create(
            school=self.school, name="2025-2026", is_current=True,
            start_date="2025-10-01", end_date="2026-07-31",
        )
        level = Level.objects.create(school=self.school, name="CM2", order=5)
        self.cls = Class.objects.create(name="CM2-A", level=level, school_year=self.year)
        self.math = Subject.objects.create(school=self.school, name="Maths", code="MATH", coefficient=4)
        self.fr = Subject.objects.create(school=self.school, name="Français", code="FR", coefficient=2)
        self.cls.subjects.set([self.math, self.fr])
        self.student = Student.objects.create(
            school=self.school, first_name="A", last_name="B",
            current_class=self.cls, school_year=self.year,
        )
        tu = CustomUser.objects.create_user(
            username="tm", email="tm@test.bj", password="Pass1234!",
            role="teacher", first_name="T", last_name="M", school=self.school,
        )
        self.teacher = Teacher.objects.create(user=tu)

    def test_ungraded_subject_excluded_from_general_average(self):
        # Une seule note : Maths 16/20. Le Français (coeff 2) n'est PAS noté.
        Grade.objects.create(
            student=self.student, subject=self.math, school_year=self.year,
            teacher=self.teacher, period="T1", value=16,
        )
        avgs = Grade.get_subject_averages(self.student, self.year, "T1")
        self.assertIsNone(avgs[self.fr.id]["average"])          # non noté → None
        self.assertEqual(float(avgs[self.math.id]["average"]), 16.0)

        general = Grade.calculate_average(self.student, self.year, "T1")
        # Ancien comportement (bug) : (16*4 + 0*2) / 6 = 10.67
        # Nouveau : seule la matière notée compte → 16.00
        self.assertEqual(float(general), 16.0)

    def test_no_grades_general_average_is_none(self):
        self.assertIsNone(Grade.calculate_average(self.student, self.year, "T1"))

    def test_weighted_by_note_and_subject_coefficients(self):
        # Maths : devoir 10 (coeff note 1) + contrôle 16 (coeff note 2) → 14
        Grade.objects.create(student=self.student, subject=self.math, school_year=self.year,
                             teacher=self.teacher, period="T1", value=10, note_coefficient=1)
        Grade.objects.create(student=self.student, subject=self.math, school_year=self.year,
                             teacher=self.teacher, period="T1", value=16, note_coefficient=2)
        # Français : 8
        Grade.objects.create(student=self.student, subject=self.fr, school_year=self.year,
                             teacher=self.teacher, period="T1", value=8)
        general = Grade.calculate_average(self.student, self.year, "T1")
        # (14*4 + 8*2) / (4+2) = 72/6 = 12.00
        self.assertEqual(float(general), 12.0)
