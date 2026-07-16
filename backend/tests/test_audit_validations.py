"""
Tests des validations serveur ajoutées lors de l'audit V3 :
 - paiements : montant strictement positif, date non future ;
 - présences : date non future, prévention des doublons (élève+date+matière) ;
 - emploi du temps : fin > début, conflits classe / enseignant / salle.
"""
import datetime

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import CustomUser
from apps.schools.models import School, SchoolYear
from apps.classes.models import Class
from apps.schools.models import Level
from apps.students.models import Student
from apps.subjects.models import Subject
from apps.teachers.models import Teacher

pytestmark = pytest.mark.django_db

TODAY = datetime.date.today()


@pytest.fixture
def school(db):
    return School.objects.create(name="FEBA Audit", slug="feba-audit")


@pytest.fixture
def year(school):
    return SchoolYear.objects.create(
        school=school, name="2025-2026",
        start_date=TODAY.replace(month=1, day=1),
        end_date=TODAY.replace(month=12, day=31),
        is_current=True,
    )


@pytest.fixture
def admin(school):
    return CustomUser.objects.create_user(
        username="audit_admin", email="audit_admin@feba.test",
        password="Str0ngPass!42", first_name="Ada", last_name="Admin",
        role="admin", school=school,
    )


@pytest.fixture
def client(admin):
    c = APIClient()
    c.force_authenticate(user=admin)
    return c


@pytest.fixture
def level(school):
    return Level.objects.create(school=school, name="CM2", order=1)


@pytest.fixture
def klass(school, year, level):
    return Class.objects.create(name="CM2-A", level=level, school_year=year)


@pytest.fixture
def student(school, year, klass):
    return Student.objects.create(
        school=school, first_name="Sory", last_name="Eleve",
        current_class=klass, school_year=year,
    )


class TestPaymentValidation:
    def _payload(self, student, year, **over):
        base = {
            "student": student.id,
            "school_year": year.id,
            "payment_type": "mensualite",
            "amount": "5000.00",
            "payment_date": str(TODAY),
            "payment_method": "cash",
        }
        base.update(over)
        return base

    def test_negative_amount_rejected(self, client, student, year):
        r = client.post("/api/payments/", self._payload(student, year, amount="-100.00"), format="json")
        assert r.status_code == 400
        assert "amount" in r.data

    def test_zero_amount_rejected(self, client, student, year):
        r = client.post("/api/payments/", self._payload(student, year, amount="0.00"), format="json")
        assert r.status_code == 400

    def test_future_date_rejected(self, client, student, year):
        r = client.post(
            "/api/payments/",
            self._payload(student, year, payment_date=str(TODAY + datetime.timedelta(days=3))),
            format="json",
        )
        assert r.status_code == 400
        assert "payment_date" in r.data

    def test_valid_payment_accepted(self, client, student, year):
        r = client.post("/api/payments/", self._payload(student, year), format="json")
        assert r.status_code == 201, r.data


class TestAttendanceValidation:
    def _payload(self, student, year, **over):
        base = {"student": student.id, "date": str(TODAY), "status": "absent",
                "school_year": year.id}
        base.update(over)
        return base

    def test_future_date_rejected(self, client, student, year):
        r = client.post(
            "/api/attendance/",
            self._payload(student, year, date=str(TODAY + datetime.timedelta(days=2))),
            format="json",
        )
        assert r.status_code == 400
        assert "date" in r.data

    def test_duplicate_rejected(self, client, student, year):
        r1 = client.post("/api/attendance/", self._payload(student, year), format="json")
        assert r1.status_code == 201, r1.data
        r2 = client.post("/api/attendance/", self._payload(student, year), format="json")
        assert r2.status_code == 400

    def test_update_does_not_trigger_duplicate(self, client, student, year):
        r1 = client.post("/api/attendance/", self._payload(student, year), format="json")
        pk = r1.data["id"]
        r2 = client.patch(f"/api/attendance/{pk}/", {"status": "late"}, format="json")
        assert r2.status_code == 200, r2.data
        assert r2.data["status"] == "late"


class TestScheduleConflicts:
    @pytest.fixture
    def subject(self, school):
        return Subject.objects.create(school=school, name="Mathématiques", code="MATH")

    @pytest.fixture
    def teacher(self, school):
        u = CustomUser.objects.create_user(
            username="audit_teacher", email="audit_teacher@feba.test",
            password="Str0ngPass!42", first_name="Tara", last_name="Prof",
            role="teacher", school=school,
        )
        return Teacher.objects.create(user=u)

    def _payload(self, klass, subject, teacher, year, **over):
        base = {
            "cls": klass.id, "subject": subject.id, "teacher": teacher.id,
            "school_year": year.id, "day_of_week": 0,
            "start_time": "08:00", "end_time": "09:00", "room": "S1",
        }
        base.update(over)
        return base

    def test_end_before_start_rejected(self, client, klass, subject, teacher, year):
        r = client.post(
            "/api/schedule/",
            self._payload(klass, subject, teacher, year, start_time="10:00", end_time="09:00"),
            format="json",
        )
        assert r.status_code == 400
        assert "end_time" in r.data

    def test_class_overlap_rejected(self, client, klass, subject, teacher, year):
        r1 = client.post("/api/schedule/", self._payload(klass, subject, teacher, year), format="json")
        assert r1.status_code == 201, r1.data
        r2 = client.post(
            "/api/schedule/",
            self._payload(klass, subject, teacher, year, start_time="08:30", end_time="09:30", room="S2"),
            format="json",
        )
        assert r2.status_code == 400

    def test_room_overlap_rejected(self, client, klass, subject, teacher, year, school, level):
        other_class = Class.objects.create(name="CM2-B", level=level, school_year=year)
        r1 = client.post("/api/schedule/", self._payload(klass, subject, teacher, year), format="json")
        assert r1.status_code == 201, r1.data
        other_teacher_user = CustomUser.objects.create_user(
            username="audit_teacher2", email="audit_teacher2@feba.test",
            password="Str0ngPass!42", first_name="Tom", last_name="Prof2",
            role="teacher", school=school,
        )
        other_teacher = Teacher.objects.create(user=other_teacher_user)
        r2 = client.post(
            "/api/schedule/",
            self._payload(other_class, subject, other_teacher, year,
                          start_time="08:30", end_time="09:30", room="S1"),
            format="json",
        )
        assert r2.status_code == 400

    def test_non_overlapping_accepted(self, client, klass, subject, teacher, year):
        r1 = client.post("/api/schedule/", self._payload(klass, subject, teacher, year), format="json")
        assert r1.status_code == 201, r1.data
        r2 = client.post(
            "/api/schedule/",
            self._payload(klass, subject, teacher, year, start_time="09:00", end_time="10:00"),
            format="json",
        )
        assert r2.status_code == 201, r2.data
