"""Un bulletin généré devient périmé dès qu'une de ses notes change, et le reste après restauration."""
from datetime import timedelta

from django.core.files.base import ContentFile
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.bulletins.models import Bulletin
from apps.classes.models import Class
from apps.grades.models import Grade, GradeHistory
from apps.schools.models import Level, SchoolYear
from apps.students.models import Student
from apps.subjects.models import Subject
from tests.test_virtualclass import make_school, make_user


class BulletinPerimeTests(TestCase):
    def setUp(self):
        self.school = make_school()
        self.year = SchoolYear.objects.create(school=self.school, name="2026-2027", start_date="2026-09-01",
                                              end_date="2027-06-30", is_current=True)
        level = Level.objects.create(school=self.school, name="CM1", order=1, cycle="primaire")
        self.cls = Class.objects.create(name="CM1", level=level, school_year=self.year)
        self.subject = Subject.objects.create(school=self.school, name="Dictée", coefficient=1, level=level)
        self.student = Student.objects.create(school=self.school, first_name="A", last_name="B", current_class=self.cls)
        self.grade = Grade.objects.create(student=self.student, subject=self.subject, school_year=self.year,
                                          period="T1", value=8)
        self.bulletin = Bulletin.objects.create(student=self.student, school_year=self.year, period="T1")
        self.bulletin.pdf_file.save("b.pdf", ContentFile(b"%PDF"), save=True)
        self.bulletin.generated_at = timezone.now() + timedelta(seconds=1)
        self.bulletin.save(update_fields=["generated_at"])
        self.admin = make_user("adm@test.bj", "admin", self.school)
        self.client = APIClient()
        self.client.force_authenticate(self.admin)

    def retarder(self):
        Bulletin.objects.filter(pk=self.bulletin.pk).update(generated_at=timezone.now() - timedelta(minutes=1))
        self.bulletin.refresh_from_db()

    def test_suppression_puis_restauration(self):
        self.assertFalse(self.bulletin.pdf_outdated)
        self.retarder()
        resp = self.client.delete(f"/api/grades/{self.grade.pk}/", {"justification": "Erreur de saisie"}, format="json")
        self.assertEqual(resp.status_code, 204)
        self.assertTrue(self.bulletin.pdf_outdated)
        # Régénéré : à jour. Restauré : de nouveau périmé, une seule ligne ajoutée.
        Bulletin.objects.filter(pk=self.bulletin.pk).update(generated_at=timezone.now() + timedelta(seconds=1))
        self.bulletin.refresh_from_db()
        self.assertFalse(self.bulletin.pdf_outdated)
        self.retarder()
        avant = GradeHistory.objects.filter(grade=self.grade).count()
        self.assertEqual(self.client.post(f"/api/grades/{self.grade.pk}/restore/").status_code, 200)
        self.assertEqual(self.client.post(f"/api/grades/{self.grade.pk}/restore/").status_code, 400)
        self.assertEqual(GradeHistory.objects.filter(grade=self.grade).count(), avant + 1)
        self.grade.refresh_from_db()
        self.assertFalse(self.grade.is_deleted)
        self.assertTrue(self.bulletin.pdf_outdated)

    def test_autre_periode_sans_effet(self):
        autre = Grade.objects.create(student=self.student, subject=self.subject, school_year=self.year, period="T2", value=9)
        GradeHistory.objects.create(grade=autre, changed_by=self.admin, new_value=9, action="create")
        self.retarder()
        GradeHistory.objects.filter(grade=autre).update(changed_at=timezone.now())
        self.assertFalse(self.bulletin.pdf_outdated)
