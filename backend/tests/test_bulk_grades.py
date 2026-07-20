"""
Tests V6 — Priorité 7 : saisie GROUPÉE de notes (endpoint atomique).

POST /api/grades/bulk-create/ :
  - une seule ou plusieurs notes en une opération ;
  - transaction atomique (une ligne invalide → rollback total) ;
  - permissions backend (enseignant→ses matières/classes ; admin→établissement ;
    superadmin→établissement courant ; contournement d'ID bloqué) ;
  - validations (note > barème, coefficient, matière non assignée, élève hors
    classe, autre établissement, doublon strict) ;
  - appréciation calculée par le backend ; moyennes recalculées.
"""
from decimal import Decimal

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

URL = "/api/grades/bulk-create/"


def auth(client, email, password="Pass1234!"):
    r = client.post("/api/auth/login/", {"email": email, "password": password})
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {r.data['access']}")


class BulkGradeFixture(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.school = School.objects.create(name="FEBA", address="Cotonou")
        cls.other = School.objects.create(name="Autre", address="Porto-Novo")
        cls.year = SchoolYear.objects.create(
            school=cls.school, name="2025-2026",
            start_date="2025-09-01", end_date="2026-07-31", is_current=True,
        )
        cls.other_year = SchoolYear.objects.create(
            school=cls.other, name="2025-2026", start_date="2025-09-01",
            end_date="2026-07-31", is_current=True,
        )
        level = Level.objects.create(school=cls.school, name="CM2", order=5)
        cls.cls1 = Class.objects.create(name="CM2-A", level=level, school_year=cls.year)
        cls.cls2 = Class.objects.create(name="CM2-B", level=level, school_year=cls.year)
        cls.math = Subject.objects.create(school=cls.school, name="Maths", code="MATH", coefficient=4, language="fr")
        cls.fr = Subject.objects.create(school=cls.school, name="Français", code="FR", coefficient=3, language="fr")
        cls.eng = Subject.objects.create(school=cls.school, name="English", code="EN", coefficient=2, language="en")
        cls.hist = Subject.objects.create(school=cls.school, name="Histoire", code="HIST", coefficient=1, language="fr")
        cls.cls1.subjects.set([cls.math, cls.fr, cls.eng, cls.hist])
        # Élève de CM2-A
        cls.student = Student.objects.create(
            school=cls.school, first_name="Ayo", last_name="Codjo",
            current_class=cls.cls1, school_year=cls.year,
        )
        # Élève d'une autre classe (pas dans les classes de l'enseignant)
        cls.student_b = Student.objects.create(
            school=cls.school, first_name="Bea", last_name="Loko",
            current_class=cls.cls2, school_year=cls.year,
        )
        # Élève d'un autre établissement
        cls.student_other = Student.objects.create(
            school=cls.other, first_name="Cid", last_name="Xoo",
            school_year=cls.other_year,
        )
        # Enseignant : maths + français + anglais, classe CM2-A (pas histoire)
        tu = CustomUser.objects.create_user(
            username="prof", email="prof@test.bj", password="Pass1234!",
            role="teacher", first_name="T", last_name="P", school=cls.school,
        )
        cls.teacher = Teacher.objects.create(user=tu)
        cls.teacher.subjects.set([cls.math, cls.fr, cls.eng])
        cls.teacher.classes.set([cls.cls1])
        cls.admin = CustomUser.objects.create_user(
            username="adm", email="adm@test.bj", password="Pass1234!",
            role="admin", first_name="A", last_name="D", school=cls.school,
        )
        cls.superadmin = CustomUser.objects.create_user(
            username="sa", email="sa@test.bj", password="Pass1234!",
            role="superadmin", first_name="S", last_name="A",
        )

    def line(self, subject, value, note_type="controle", period="T1", coeff=1):
        return {"subject": subject.id, "period": period, "value": str(value),
                "note_type": note_type, "note_coefficient": coeff}


class BulkSuccessTests(BulkGradeFixture):
    def setUp(self):
        self.client = APIClient()
        auth(self.client, "prof@test.bj")

    def test_single_line_via_bulk(self):
        resp = self.client.post(URL, {
            "student": self.student.id, "school_year": self.year.id,
            "grades": [self.line(self.math, 15, coeff=2)],
        }, format="json")
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data["created"], 1)
        self.assertEqual(Grade.objects.filter(student=self.student, is_deleted=False).count(), 1)

    def test_multiple_lines_atomic_success(self):
        resp = self.client.post(URL, {
            "student": self.student.id, "school_year": self.year.id,
            "grades": [
                self.line(self.math, 15, "controle", "T1", 2),
                self.line(self.fr, 14, "interrogation", "T1", 1),
                self.line(self.eng, 17, "examen", "T1", 3),
            ],
        }, format="json")
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data["created"], 3)
        self.assertEqual(sorted(resp.data["subjects"]), ["English", "Français", "Maths"])
        self.assertEqual(Grade.objects.filter(student=self.student).count(), 3)
        # Appréciation calculée par le backend (barème V4)
        apprs = {g["subject_name"]: g["appreciation"] for g in resp.data["grades"]}
        self.assertEqual(apprs["English"], "TRÈS SATISFAISANT")  # 17
        self.assertEqual(apprs["Maths"], "SATISFAISANT")          # 15

    def test_year_optional_uses_active(self):
        resp = self.client.post(URL, {
            "student": self.student.id,
            "grades": [self.line(self.math, 12)],
        }, format="json")
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(Grade.objects.get(student=self.student).school_year, self.year)

    def test_averages_recomputed(self):
        self.client.post(URL, {
            "student": self.student.id, "school_year": self.year.id,
            "grades": [self.line(self.math, 16, coeff=1), self.line(self.fr, 10, coeff=1)],
        }, format="json")
        avg = Grade.calculate_average(self.student, self.year, "T1")
        # (16*4 + 10*3) / (4+3) ≈ 13.43 (pondération coefficients matière)
        self.assertAlmostEqual(float(avg), 13.43, places=1)


class BulkAtomicRollbackTests(BulkGradeFixture):
    def setUp(self):
        self.client = APIClient()
        auth(self.client, "prof@test.bj")

    def test_one_invalid_line_rolls_back_all(self):
        resp = self.client.post(URL, {
            "student": self.student.id, "school_year": self.year.id,
            "grades": [
                self.line(self.math, 15),        # valide
                self.line(self.fr, 25),          # note > barème (invalide)
                self.line(self.eng, 17),         # valide
            ],
        }, format="json")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("grades", resp.data)
        self.assertIn("value", resp.data["grades"][1])
        # AUCUNE note créée (atomicité)
        self.assertEqual(Grade.objects.filter(student=self.student).count(), 0)

    def test_errors_indexed_by_line(self):
        resp = self.client.post(URL, {
            "student": self.student.id, "school_year": self.year.id,
            "grades": [
                self.line(self.math, 15),        # ok
                self.line(self.hist, 12),        # matière non assignée à l'enseignant
                self.line(self.eng, -3),         # note négative
            ],
        }, format="json")
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.data["grades"][0], {})
        self.assertIn("subject", resp.data["grades"][1])
        self.assertIn("value", resp.data["grades"][2])
        self.assertEqual(Grade.objects.filter(student=self.student).count(), 0)

    def test_invalid_coefficient(self):
        resp = self.client.post(URL, {
            "student": self.student.id, "school_year": self.year.id,
            "grades": [{"subject": self.math.id, "period": "T1", "value": "12",
                        "note_type": "devoir", "note_coefficient": 0}],
        }, format="json")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("note_coefficient", resp.data["grades"][0])

    def test_duplicate_line_rejected_but_distinct_allowed(self):
        # Deux lignes STRICTEMENT identiques → doublon
        resp = self.client.post(URL, {
            "student": self.student.id, "school_year": self.year.id,
            "grades": [self.line(self.math, 15, "controle", "T1", 2),
                       self.line(self.math, 15, "controle", "T1", 2)],
        }, format="json")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("subject", resp.data["grades"][1])
        self.assertEqual(Grade.objects.filter(student=self.student).count(), 0)
        # Deux évaluations DIFFÉRENTES d'une même matière → autorisées
        ok = self.client.post(URL, {
            "student": self.student.id, "school_year": self.year.id,
            "grades": [self.line(self.math, 15, "controle", "T1", 2),
                       self.line(self.math, 18, "examen", "T1", 3)],
        }, format="json")
        self.assertEqual(ok.status_code, 201, ok.data)
        self.assertEqual(Grade.objects.filter(student=self.student, subject=self.math).count(), 2)


class BulkPermissionTests(BulkGradeFixture):
    def test_teacher_subject_not_assigned(self):
        c = APIClient(); auth(c, "prof@test.bj")
        resp = c.post(URL, {
            "student": self.student.id, "school_year": self.year.id,
            "grades": [self.line(self.hist, 14)],  # histoire non assignée
        }, format="json")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("subject", resp.data["grades"][0])

    def test_teacher_student_not_in_class(self):
        c = APIClient(); auth(c, "prof@test.bj")
        resp = c.post(URL, {
            "student": self.student_b.id, "school_year": self.year.id,  # CM2-B
            "grades": [self.line(self.math, 14)],
        }, format="json")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("student", resp.data)
        self.assertEqual(Grade.objects.count(), 0)

    def test_teacher_cannot_target_other_school_student_idor(self):
        c = APIClient(); auth(c, "prof@test.bj")
        resp = c.post(URL, {
            "student": self.student_other.id,  # autre établissement
            "school_year": self.year.id,
            "grades": [self.line(self.math, 14)],
        }, format="json")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("student", resp.data)
        self.assertEqual(Grade.objects.count(), 0)

    def test_admin_can_bulk_in_school(self):
        c = APIClient(); auth(c, "adm@test.bj")
        resp = c.post(URL, {
            "student": self.student.id, "school_year": self.year.id,
            "grades": [self.line(self.math, 15), self.line(self.hist, 13)],  # admin peut histoire
        }, format="json")
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data["created"], 2)

    def test_superadmin_can_bulk(self):
        c = APIClient(); auth(c, "sa@test.bj")
        resp = c.post(f"{URL}?school_id={self.school.id}", {
            "student": self.student.id, "school_year": self.year.id,
            "grades": [self.line(self.math, 15)],
        }, format="json")
        self.assertEqual(resp.status_code, 201, resp.data)

    def test_parent_forbidden(self):
        pu = CustomUser.objects.create_user(
            username="par", email="par@test.bj", password="Pass1234!",
            role="parent", first_name="P", last_name="A", school=self.school,
        )
        c = APIClient(); auth(c, "par@test.bj")
        resp = c.post(URL, {
            "student": self.student.id, "school_year": self.year.id,
            "grades": [self.line(self.math, 15)],
        }, format="json")
        self.assertEqual(resp.status_code, 403)

    def test_anonymous_unauthorized(self):
        resp = APIClient().post(URL, {
            "student": self.student.id, "grades": [self.line(self.math, 15)],
        }, format="json")
        self.assertEqual(resp.status_code, 401)

    def test_empty_grades_rejected(self):
        c = APIClient(); auth(c, "prof@test.bj")
        resp = c.post(URL, {"student": self.student.id, "grades": []}, format="json")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("grades", resp.data)
