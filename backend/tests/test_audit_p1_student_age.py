"""
P1 — Âge des élèves dans toutes les listes.

Ce que ces tests verrouillent :
  - le calcul en années révolues (anniversaire passé / pas encore passé) ;
  - le 29 février (anniversaire atteint le 1er mars les années non
    bissextiles) ;
  - la date de naissance absente (« missing ») ou future (« invalid »),
    jamais un âge négatif ;
  - « aujourd'hui » pris dans le fuseau DE L'ACADÉMIE (FHA = New York) ;
  - la présence de l'âge dans les réponses des différents serializers
    (élèves paginés, paiements, absences, notes, inscriptions, enfants du
    parent, moyennes de classe), pour deux académies ;
  - le refus d'une date de naissance future à la saisie.
"""
import datetime
from decimal import Decimal
from unittest import mock

from django.test import SimpleTestCase, TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import CustomUser
from apps.core.age import (
    AGE_INVALID, AGE_MISSING, AGE_OK, academy_today, age_info, age_label,
    compute_age, validate_birth_date,
)
from apps.schools.models import School, SchoolYear


class ComputeAgeTests(SimpleTestCase):
    def test_birthday_already_passed_this_year(self):
        self.assertEqual(compute_age(datetime.date(2015, 3, 12), datetime.date(2026, 10, 9)), 11)

    def test_birthday_not_yet_passed_this_year(self):
        self.assertEqual(compute_age(datetime.date(2015, 12, 25), datetime.date(2026, 10, 9)), 10)

    def test_birthday_today(self):
        self.assertEqual(compute_age(datetime.date(2016, 10, 9), datetime.date(2026, 10, 9)), 10)

    def test_day_before_birthday(self):
        self.assertEqual(compute_age(datetime.date(2016, 10, 10), datetime.date(2026, 10, 9)), 9)

    def test_born_29_february_non_leap_year(self):
        born = datetime.date(2016, 2, 29)
        # 2026 n'est pas bissextile : le 28 février, l'anniversaire n'est
        # pas encore atteint ; il l'est le 1er mars.
        self.assertEqual(compute_age(born, datetime.date(2026, 2, 28)), 9)
        self.assertEqual(compute_age(born, datetime.date(2026, 3, 1)), 10)

    def test_born_29_february_leap_year(self):
        born = datetime.date(2016, 2, 29)
        self.assertEqual(compute_age(born, datetime.date(2028, 2, 28)), 11)
        self.assertEqual(compute_age(born, datetime.date(2028, 2, 29)), 12)

    def test_missing_birth_date(self):
        self.assertEqual(age_info(None, on=datetime.date(2026, 10, 9)),
                         {"age": None, "age_status": AGE_MISSING})
        self.assertEqual(age_label(age_info(None)), "Non renseigné")

    def test_future_birth_date_is_flagged_never_negative(self):
        info = age_info(datetime.date(2030, 1, 1), on=datetime.date(2026, 10, 9))
        self.assertEqual(info, {"age": None, "age_status": AGE_INVALID})
        self.assertIsNone(compute_age(datetime.date(2030, 1, 1), datetime.date(2026, 10, 9)))

    def test_absurd_past_birth_date_is_flagged(self):
        info = age_info(datetime.date(201, 1, 1), on=datetime.date(2026, 10, 9))
        self.assertEqual(info["age_status"], AGE_INVALID)

    def test_iso_string_accepted(self):
        self.assertEqual(age_info("2015-03-12", on="2026-10-09"),
                         {"age": 11, "age_status": AGE_OK})

    def test_labels(self):
        self.assertEqual(age_label({"age": 1, "age_status": AGE_OK}), "1 an")
        self.assertEqual(age_label({"age": 7, "age_status": AGE_OK}), "7 ans")
        self.assertEqual(age_label({"age": None, "age_status": AGE_INVALID}),
                         "Date de naissance invalide")

    def test_validate_birth_date(self):
        with mock.patch("apps.core.age.timezone.now",
                        return_value=datetime.datetime(2026, 10, 9, 12, tzinfo=datetime.timezone.utc)):
            self.assertIsNone(validate_birth_date(datetime.date(2015, 1, 1)))
            self.assertIn("futur", validate_birth_date(datetime.date(2026, 10, 10)))
            self.assertIsNone(validate_birth_date(None))


class AcademyTimezoneTests(SimpleTestCase):
    """« Aujourd'hui » est celui de l'académie, pas celui du serveur."""

    def test_new_york_is_still_yesterday_late_utc(self):
        # 9 octobre 2026, 02:30 UTC = 8 octobre 22:30 à New York.
        now = datetime.datetime(2026, 10, 9, 2, 30, tzinfo=datetime.timezone.utc)
        fha = School(timezone="America/New_York")
        feba = School(timezone="Africa/Porto-Novo")
        self.assertEqual(academy_today(fha, now), datetime.date(2026, 10, 8))
        self.assertEqual(academy_today(feba, now), datetime.date(2026, 10, 9))

    def test_birthday_does_not_arrive_early_in_new_york(self):
        now = datetime.datetime(2026, 10, 9, 2, 30, tzinfo=datetime.timezone.utc)
        fha = School(timezone="America/New_York")
        with mock.patch("apps.core.age.timezone.now", return_value=now):
            info = age_info(datetime.date(2016, 10, 9), fha)
        self.assertEqual(info["age"], 9)

    def test_unknown_timezone_falls_back(self):
        school = School(timezone="Not/AZone")
        self.assertIsInstance(academy_today(school), datetime.date)


class AgeInListsApiTests(TestCase):
    """L'âge est présent dans les listes servies par plusieurs serializers."""

    @classmethod
    def setUpTestData(cls):
        from apps.parents.models import Parent, ParentStudent
        from apps.payments.models import Payment
        from apps.students.models import Student, StudentEnrollment

        cls.feba = School.objects.create(
            name="FEBA Age", address="Cotonou", code="AGE-FEBA",
            currency_code="XOF", timezone="Africa/Porto-Novo",
        )
        cls.fha = School.objects.create(
            name="FHA Age", address="En ligne", code="AGE-FHA", entity_type="online",
            currency_code="USD", timezone="America/New_York",
        )
        cls.year = {}
        for key, school in (("feba", cls.feba), ("fha", cls.fha)):
            cls.year[key] = SchoolYear.objects.create(
                school=school, name=f"2026-2027-{key}", is_current=True,
                start_date="2026-09-01", end_date="2027-07-01",
            )
        cls.admin = CustomUser.objects.create_user(
            username="age_admin", email="age.admin@test.io", password="x",
            role="admin", school=cls.feba,
        )
        cls.fha_admin = CustomUser.objects.create_user(
            username="age_admin_fha", email="age.admin.fha@test.io", password="x",
            role="admin", school=cls.fha,
        )
        cls.passed = Student.objects.create(
            school=cls.feba, school_year=cls.year["feba"], first_name="Passé",
            last_name="Anniv", date_of_birth=datetime.date(2015, 3, 12),
        )
        cls.not_yet = Student.objects.create(
            school=cls.feba, school_year=cls.year["feba"], first_name="Pas",
            last_name="Encore", date_of_birth=datetime.date(2015, 12, 25),
        )
        cls.missing = Student.objects.create(
            school=cls.feba, school_year=cls.year["feba"], first_name="Sans",
            last_name="Date",
        )
        # Donnée historique incohérente, insérée sans passer par l'API.
        cls.future = Student.objects.create(
            school=cls.feba, school_year=cls.year["feba"], first_name="Futur",
            last_name="Erreur", date_of_birth=datetime.date(2031, 1, 1),
        )
        cls.fha_student = Student.objects.create(
            school=cls.fha, school_year=cls.year["fha"], first_name="Fha",
            last_name="Kid", date_of_birth=datetime.date(2016, 2, 29),
        )
        # Pour la pagination : 25 élèves supplémentaires.
        for i in range(25):
            Student.objects.create(
                school=cls.feba, school_year=cls.year["feba"], first_name=f"Pag{i:02d}",
                last_name="Zz", date_of_birth=datetime.date(2014, 1, 1),
            )
        for student in (cls.passed, cls.not_yet):
            StudentEnrollment.objects.create(student=student, school_year=cls.year["feba"])
            Payment.objects.create(
                student=student, school_year=cls.year["feba"], payment_type="mensualite",
                amount=Decimal("1000"), payment_method="cash",
                payment_date=datetime.date(2026, 10, 1),
            )
        cls.parent_user = CustomUser.objects.create_user(
            username="age_parent", email="age.parent@test.io", password="x",
            role="parent", school=cls.feba,
        )
        parent = Parent.objects.create(user=cls.parent_user)
        ParentStudent.objects.create(parent=parent, student=cls.passed)

    def setUp(self):
        self.now = mock.patch(
            "apps.core.age.timezone.now",
            return_value=datetime.datetime(2026, 10, 9, 10, 0, tzinfo=datetime.timezone.utc),
        )
        self.now.start()
        self.addCleanup(self.now.stop)

    def client_for(self, user):
        client = APIClient()
        client.force_authenticate(user)
        return client

    def test_student_list_paginated_exposes_age(self):
        client = self.client_for(self.admin)
        page1 = client.get("/api/students/", {"page_size": 10}).json()
        self.assertEqual(page1["count"], 29)
        for row in page1["results"]:
            self.assertIn("age", row)
            self.assertIn("age_status", row)
        rows = client.get("/api/students/", {"page_size": 100}).json()["results"]
        by_id = {r["id"]: r for r in rows}
        self.assertEqual((by_id[self.passed.id]["age"], by_id[self.passed.id]["age_status"]), (11, "ok"))
        self.assertEqual(by_id[self.not_yet.id]["age"], 10)
        self.assertEqual((by_id[self.missing.id]["age"], by_id[self.missing.id]["age_status"]),
                         (None, "missing"))
        self.assertEqual((by_id[self.future.id]["age"], by_id[self.future.id]["age_status"]),
                         (None, "invalid"))
        # Isolation : l'élève FHA n'apparaît pas chez l'admin FEBA.
        self.assertNotIn(self.fha_student.id, by_id)

    def test_second_academy_uses_its_own_timezone(self):
        rows = self.client_for(self.fha_admin).get("/api/students/").json()["results"]
        self.assertEqual([r["id"] for r in rows], [self.fha_student.id])
        # Né un 29 février 2016 : 10 ans révolus au 8 octobre 2026.
        self.assertEqual(rows[0]["age"], 10)

    def test_payment_list_exposes_student_age(self):
        rows = self.client_for(self.admin).get("/api/payments/").json()["results"]
        ages = {r["student"]: (r["student_age"], r["student_age_status"]) for r in rows}
        self.assertEqual(ages[self.passed.id], (11, "ok"))
        self.assertEqual(ages[self.not_yet.id], (10, "ok"))

    def test_enrollment_list_exposes_student_age(self):
        resp = self.client_for(self.admin).get(
            "/api/students/enrollments/", {"student": self.passed.id})
        self.assertEqual(resp.status_code, 200, resp.content)
        data = resp.json()
        rows = data.get("results", data) if isinstance(data, dict) else data
        self.assertEqual(len(rows), 1)
        self.assertEqual((rows[0]["student_age"], rows[0]["student_age_status"]), (11, "ok"))

    def test_attendance_and_grades_expose_student_age(self):
        from apps.attendance.serializers import AttendanceSerializer
        from apps.grades.serializers import GradeSerializer

        self.assertIn("student_age", AttendanceSerializer().fields)
        self.assertIn("student_age_status", AttendanceSerializer().fields)
        self.assertIn("student_age", GradeSerializer().fields)

    def test_parent_children_expose_age(self):
        resp = self.client_for(self.parent_user).get("/api/parents/me/")
        self.assertEqual(resp.status_code, 200, resp.content)
        links = resp.json()["children_links"]
        self.assertEqual(links[0]["student_detail"]["age"], 11)
        self.assertEqual(links[0]["student_detail"]["age_status"], "ok")

    def test_future_birth_date_refused_on_create(self):
        resp = self.client_for(self.admin).post("/api/students/", {
            "first_name": "Nouveau", "last_name": "Futur",
            "date_of_birth": "2027-01-01", "school_year": self.year["feba"].id,
        }, format="json")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("date_of_birth", resp.json())

    def test_list_query_count_does_not_grow_per_student(self):
        """L'âge n'ajoute aucune requête par élève (pas de N+1)."""
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        client = self.client_for(self.admin)
        with CaptureQueriesContext(connection) as small:
            client.get("/api/students/", {"page_size": 5})
        with CaptureQueriesContext(connection) as large:
            client.get("/api/students/", {"page_size": 25})
        self.assertLessEqual(len(large.captured_queries), len(small.captured_queries) + 2)


class EnrollmentEndpointRegressionTests(TestCase):
    """
    /api/students/enrollments/ répondait 404 (capturé par le détail élève)
    et un POST y aurait levé une erreur 500.
    """

    @classmethod
    def setUpTestData(cls):
        from apps.students.models import Student

        cls.a = School.objects.create(name="Enr A", address="x", code="ENR-A")
        cls.b = School.objects.create(name="Enr B", address="x", code="ENR-B")
        cls.year_a = SchoolYear.objects.create(school=cls.a, name="2026-2027",
                                               start_date="2026-09-01", end_date="2027-07-01")
        cls.year_b = SchoolYear.objects.create(school=cls.b, name="2026-2027",
                                               start_date="2026-09-01", end_date="2027-07-01")
        cls.student_a = Student.objects.create(school=cls.a, first_name="A", last_name="A")
        cls.student_b = Student.objects.create(school=cls.b, first_name="B", last_name="B")
        cls.admin_a = CustomUser.objects.create_user(
            username="enr_a", email="enr.a@test.io", password="x", role="admin", school=cls.a)

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(self.admin_a)

    def test_list_is_routed(self):
        self.assertEqual(self.client.get("/api/students/enrollments/").status_code, 200)

    def test_create_in_own_academy(self):
        resp = self.client.post("/api/students/enrollments/", {
            "student": self.student_a.id, "school_year": self.year_a.id}, format="json")
        self.assertEqual(resp.status_code, 201, resp.content)

    def test_cannot_enroll_student_of_other_academy(self):
        resp = self.client.post("/api/students/enrollments/", {
            "student": self.student_b.id, "school_year": self.year_a.id}, format="json")
        self.assertEqual(resp.status_code, 400)

    def test_cannot_use_year_of_other_academy(self):
        resp = self.client.post("/api/students/enrollments/", {
            "student": self.student_a.id, "school_year": self.year_b.id}, format="json")
        self.assertEqual(resp.status_code, 400)
