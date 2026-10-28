"""
Audit — cohérence comptable des paiements.

1. Le tableau de bord additionnait les paiements ANNULÉS (is_confirmed=False)
   dans « encaissé ce mois », le cumul annuel et le graphique mensuel, alors
   que l'écran Paiements (summary) les exclut : deux totaux différents pour
   la même caisse.
2. Restaurer un paiement supprimé le remettait TOUJOURS « confirmé », y
   compris un paiement annulé (avec justification) avant sa suppression :
   un encaissement annulé redevenait une recette.
"""
import datetime
from decimal import Decimal
from unittest import mock

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import CustomUser
from apps.payments.models import Payment
from apps.schools.models import School, SchoolYear
from apps.students.models import Student

NOW = datetime.datetime(2026, 10, 9, 12, tzinfo=datetime.timezone.utc)


class PaymentAccountingTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.school = School.objects.create(name="Compta", address="x", code="CPT", currency_code="XOF")
        cls.year = SchoolYear.objects.create(school=cls.school, name="2026-2027", is_current=True,
                                             start_date="2026-09-01", end_date="2027-07-01")
        cls.student = Student.objects.create(school=cls.school, school_year=cls.year, first_name="A", last_name="B")
        cls.admin = CustomUser.objects.create_user(
            username="cpt_admin", email="cpt.admin@test.io", password="x", role="admin", school=cls.school)

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(self.admin)

    def pay(self, amount, **kw):
        return Payment.objects.create(student=self.student, school_year=self.year, payment_type="mensualite",
                                      amount=Decimal(amount), payment_method="cash",
                                      payment_date=datetime.date(2026, 10, 2), **kw)

    def test_dashboard_excludes_cancelled_payments(self):
        self.pay("100000")
        self.pay("50000", is_confirmed=False)       # annulé
        self.pay("70000", is_deleted=True, is_confirmed=False)
        with mock.patch("django.utils.timezone.now", return_value=NOW):
            dash = self.client.get("/api/dashboard/admin/").json()
            summary = self.client.get("/api/payments/summary/").json()
        october = next(m for m in dash["monthly_revenue"] if m["month"] == 10)
        self.assertEqual(october["amount_minor"], 100000)
        self.assertEqual(summary["consolidated_total"]["amount_minor"], 100000)

    def test_restore_keeps_cancellation(self):
        cancelled = self.pay("50000")
        self.assertEqual(self.client.post(f"/api/payments/{cancelled.id}/cancel/",
                                          {"justification": "Chèque rejeté"}, format="json").status_code, 200)
        self.assertEqual(self.client.delete(f"/api/payments/{cancelled.id}/").status_code, 204)
        resp = self.client.post(f"/api/payments/{cancelled.id}/restore/")
        self.assertEqual(resp.status_code, 200, resp.content)
        cancelled.refresh_from_db()
        self.assertFalse(cancelled.is_deleted)
        self.assertFalse(cancelled.is_confirmed)

        confirmed = self.pay("30000")
        self.client.delete(f"/api/payments/{confirmed.id}/")
        self.client.post(f"/api/payments/{confirmed.id}/restore/")
        confirmed.refresh_from_db()
        self.assertTrue(confirmed.is_confirmed)


class GradeRestoreScopeTests(TestCase):
    """Restauration d'une note : portée de l'académie et droits de l'enseignant."""

    @classmethod
    def setUpTestData(cls):
        from apps.classes.models import Class
        from apps.grades.models import Grade
        from apps.schools.models import Level
        from apps.subjects.models import Subject
        from apps.teachers.models import Teacher

        cls.a = School.objects.create(name="GA", address="x", code="GR-A")
        cls.b = School.objects.create(name="GB", address="x", code="GR-B")
        year_b = SchoolYear.objects.create(school=cls.b, name="2026-2027", is_current=True,
                                           start_date="2026-09-01", end_date="2027-07-01")
        level = Level.objects.create(school=cls.b, name="CE1")
        klass = Class.objects.create(name="CE1", level=level, school_year=year_b)
        subject = Subject.objects.create(school=cls.b, name="Maths", code="M")
        student = Student.objects.create(school=cls.b, school_year=year_b, current_class=klass,
                                         first_name="S", last_name="B")
        cls.grade = Grade.objects.create(student=student, subject=subject, school_year=year_b,
                                         period="T1", value=Decimal("12"), note_type="devoir", is_deleted=True)
        cls.admin_a = CustomUser.objects.create_user(
            username="gr_admin_a", email="gr.a@test.io", password="x", role="admin", school=cls.a)
        cls.admin_b = CustomUser.objects.create_user(
            username="gr_admin_b", email="gr.b@test.io", password="x", role="admin", school=cls.b)
        teacher_user = CustomUser.objects.create_user(
            username="gr_teacher_b", email="gr.tb@test.io", password="x", role="teacher", school=cls.b)
        Teacher.objects.create(user=teacher_user)           # n'enseigne pas cette matière
        cls.teacher_b = teacher_user

    def post(self, user, pk):
        client = APIClient()
        client.force_authenticate(user)
        return client.post(f"/api/grades/{pk}/restore/")

    def test_other_academy_cannot_restore(self):
        self.assertEqual(self.post(self.admin_a, self.grade.pk).status_code, 404)
        self.grade.refresh_from_db()
        self.assertTrue(self.grade.is_deleted)

    def test_unknown_id_is_404_not_500(self):
        self.assertEqual(self.post(self.admin_b, 999999).status_code, 404)

    def test_teacher_without_rights_cannot_restore(self):
        self.assertEqual(self.post(self.teacher_b, self.grade.pk).status_code, 403)

    def test_own_admin_restores(self):
        self.assertEqual(self.post(self.admin_b, self.grade.pk).status_code, 200)
        self.grade.refresh_from_db()
        self.assertFalse(self.grade.is_deleted)
