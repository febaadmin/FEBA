"""
Audit — escalade de rôle sur les écritures.

Défauts constatés :
  - `bulk-delete` (BulkDeleteMixin) n'était soumis à AUCUN contrôle de rôle
    sur les paiements, notes, absences, devoirs, bulletins et annonces :
    un parent ou un élève pouvait supprimer en masse ce qu'il voit ;
  - la vue des absences n'avait aucun contrôle de rôle : un parent pouvait
    transformer l'absence de son enfant en présence, ou la supprimer ;
  - la suppression groupée de paiements ne laissait aucune trace
    (historique) et ne les marquait pas annulés, contrairement à la
    suppression unitaire.
"""
import datetime
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import CustomUser
from apps.attendance.models import Attendance
from apps.parents.models import Parent, ParentStudent
from apps.payments.models import Payment, PaymentHistory
from apps.schools.models import School, SchoolYear
from apps.students.models import Student


class RoleEscalationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.school = School.objects.create(name="Esc", address="x", code="ESC")
        cls.year = SchoolYear.objects.create(school=cls.school, name="2026-2027", is_current=True,
                                             start_date="2026-09-01", end_date="2027-07-01")
        cls.parent_user = CustomUser.objects.create_user(
            username="esc_parent", email="esc.parent@test.io", password="x", role="parent", school=cls.school)
        cls.student_user = CustomUser.objects.create_user(
            username="esc_student", email="esc.student@test.io", password="x", role="student", school=cls.school)
        cls.admin = CustomUser.objects.create_user(
            username="esc_admin", email="esc.admin@test.io", password="x", role="admin", school=cls.school)
        cls.student = Student.objects.create(school=cls.school, school_year=cls.year, first_name="K",
                                             last_name="D", user=cls.student_user)
        ParentStudent.objects.create(parent=Parent.objects.create(user=cls.parent_user), student=cls.student)

    def setUp(self):
        self.payment = Payment.objects.create(
            student=self.student, school_year=self.year, payment_type="mensualite",
            amount=Decimal("1000"), payment_method="cash", payment_date=datetime.date(2026, 10, 1))
        self.absence = Attendance.objects.create(
            student=self.student, date=datetime.date(2026, 10, 1), status="absent", school_year=self.year)

    def api(self, user):
        client = APIClient()
        client.force_authenticate(user)
        return client

    def test_parent_and_student_cannot_bulk_delete_payments(self):
        for user in (self.parent_user, self.student_user):
            resp = self.api(user).post("/api/payments/bulk-delete/", {"ids": [self.payment.id]}, format="json")
            self.assertEqual(resp.status_code, 403, (user.role, resp.content))
        self.payment.refresh_from_db()
        self.assertFalse(self.payment.is_deleted)

    def test_parent_cannot_alter_or_delete_attendance(self):
        client = self.api(self.parent_user)
        self.assertEqual(client.patch(f"/api/attendance/{self.absence.id}/", {"status": "present"},
                                      format="json").status_code, 403)
        self.assertEqual(client.delete(f"/api/attendance/{self.absence.id}/").status_code, 403)
        self.assertEqual(client.post("/api/attendance/bulk-delete/", {"ids": [self.absence.id]},
                                     format="json").status_code, 403)
        self.assertEqual(client.post("/api/attendance/", {
            "student": self.student.id, "date": "2026-10-02", "status": "present"}, format="json").status_code, 403)
        self.absence.refresh_from_db()
        self.assertEqual(self.absence.status, "absent")
        # Lecture toujours permise.
        self.assertEqual(client.get("/api/attendance/").status_code, 200)

    def test_bulk_delete_other_endpoints_forbidden_to_parent(self):
        client = self.api(self.parent_user)
        for url in ("/api/grades/bulk-delete/", "/api/homework/bulk-delete/",
                    "/api/bulletins/bulk-delete/", "/api/announcements/bulk-delete/"):
            self.assertEqual(client.post(url, {"ids": [1]}, format="json").status_code, 403, url)

    def test_admin_bulk_delete_payments_is_audited(self):
        resp = self.api(self.admin).post("/api/payments/bulk-delete/", {"ids": [self.payment.id]}, format="json")
        self.assertEqual(resp.status_code, 200, resp.content)
        self.payment.refresh_from_db()
        self.assertTrue(self.payment.is_deleted)
        self.assertFalse(self.payment.is_confirmed)
        self.assertIsNotNone(self.payment.deleted_at)
        self.assertEqual(self.payment.deleted_by, self.admin)
        self.assertTrue(PaymentHistory.objects.filter(payment=self.payment, action="cancel").exists())
        # Et la restauration rend l'état d'avant.
        self.assertEqual(self.api(self.admin).post(f"/api/payments/{self.payment.id}/restore/").status_code, 200)
        self.payment.refresh_from_db()
        self.assertTrue(self.payment.is_confirmed)

    def test_admin_still_manages_attendance(self):
        client = self.api(self.admin)
        self.assertEqual(client.patch(f"/api/attendance/{self.absence.id}/", {"status": "late"},
                                      format="json").status_code, 200)


class WriteActionsRequireStaffTests(TestCase):
    """
    StudentViewSet.get_permissions() écrasait les `permission_classes`
    déclarées sur ses actions : enroll, promote, end-of-year-assistant…
    étaient ouvertes à tout utilisateur authentifié de l'académie. Même
    défaut sur la création/modification des bulletins et la suppression
    des pièces jointes de devoirs.
    """

    @classmethod
    def setUpTestData(cls):
        cls.school = School.objects.create(name="Esc2", address="x", code="ESC2")
        cls.year = SchoolYear.objects.create(school=cls.school, name="2026-2027", is_current=True,
                                             start_date="2026-09-01", end_date="2027-07-01")
        cls.parent_user = CustomUser.objects.create_user(
            username="esc2_parent", email="esc2.parent@test.io", password="x", role="parent", school=cls.school)
        cls.student = Student.objects.create(school=cls.school, school_year=cls.year, first_name="K", last_name="D")
        ParentStudent.objects.create(parent=Parent.objects.create(user=cls.parent_user), student=cls.student)

    def test_parent_cannot_run_student_admin_actions(self):
        client = APIClient()
        client.force_authenticate(self.parent_user)
        sid = self.student.id
        for url in (f"/api/students/{sid}/enroll/", f"/api/students/{sid}/remove-from-year/",
                    f"/api/students/{sid}/reactivate/", "/api/students/promote/",
                    "/api/students/end-of-year-assistant/", "/api/students/enroll-class/",
                    "/api/students/enroll-all-from-year/", "/api/students/bulk-remove-from-year/",
                    "/api/students/bulk-delete/"):
            self.assertEqual(client.post(url, {}, format="json").status_code, 403, url)
        self.assertEqual(client.get("/api/students/").status_code, 200)

    def test_parent_cannot_write_bulletins(self):
        from apps.bulletins.models import Bulletin
        bulletin = Bulletin.objects.create(student=self.student, school_year=self.year, period="T1")
        client = APIClient()
        client.force_authenticate(self.parent_user)
        self.assertEqual(client.patch(f"/api/bulletins/{bulletin.id}/", {"period": "T2"},
                                      format="json").status_code, 403)
        self.assertEqual(client.post("/api/bulletins/", {"student": self.student.id,
                                     "school_year": self.year.id, "period": "T3"},
                                     format="json").status_code, 403)
