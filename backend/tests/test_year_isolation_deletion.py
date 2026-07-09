"""
Tests — Isolation par année & sémantique de suppression (FIX v34).

Causes racines couvertes :
  1. DELETE /students/{id}/ = DÉSACTIVATION : l'historique multi-années
     est intégralement conservé ; l'élève disparaît des listes actives.
  2. Suppression DÉFINITIVE (?hard=true) refusée (409) tant que des
     données pédagogiques existent.
  3. remove-from-year : retire UNE inscription annuelle ; les autres
     années restent intactes ; le pointeur "année courante" est
     repositionné sur l'inscription restante la plus récente.
  4. L'API classes ne renvoie par défaut QUE les classes de l'année
     active (plus de triplets CP1/CP1/CP1 dans les formulaires) ;
     ?school_year= et ?all_years=1 restent disponibles.
  5. DELETE /parents/{id}/ = désactivation ; définitif refusé si liens.
"""
import datetime

from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status

from apps.accounts.models import CustomUser
from apps.classes.models import Class
from apps.grades.models import Grade
from apps.parents.models import Parent, ParentStudent
from apps.schools.models import School, SchoolYear, Level
from apps.students.models import Student, StudentEnrollment
from apps.subjects.models import Subject
from apps.teachers.models import Teacher


def auth(client, email, password="Pass1234!"):
    resp = client.post("/api/auth/login/", {"email": email, "password": password})
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {resp.data.get('access', '')}")


class BaseYearSetup(TestCase):
    def setUp(self):
        self.school = School.objects.create(name="Ecole ISO", address="X")
        self.y1 = SchoolYear.objects.create(
            school=self.school, name="2024-2025",
            start_date="2024-10-01", end_date="2025-07-31",
        )
        self.y2 = SchoolYear.objects.create(
            school=self.school, name="2025-2026", is_current=True,
            start_date="2025-10-01", end_date="2026-07-31",
        )
        lvl = Level.objects.create(school=self.school, name="CP1", order=1)
        self.cls_y1 = Class.objects.create(name="CP1-A", level=lvl, school_year=self.y1)
        self.cls_y2 = Class.objects.create(name="CP1-A", level=lvl, school_year=self.y2)

        self.admin = CustomUser.objects.create_user(
            username="adm", email="adm@test.bj", password="Pass1234!",
            role="admin", first_name="A", last_name="D", school=self.school,
        )
        self.student = Student.objects.create(
            school=self.school, first_name="Koffi", last_name="Codjo",
            current_class=self.cls_y2, school_year=self.y2,
        )
        self.e1 = StudentEnrollment.objects.create(
            student=self.student, school_year=self.y1, class_obj=self.cls_y1, promotion_status="new",
        )
        self.e2 = StudentEnrollment.objects.create(
            student=self.student, school_year=self.y2, class_obj=self.cls_y2, promotion_status="normal",
        )
        self.client = APIClient()
        auth(self.client, "adm@test.bj")


class DeletionSemanticsTests(BaseYearSetup):
    def test_default_delete_is_soft_and_preserves_history(self):
        resp = self.client.delete(f"/api/students/{self.student.id}/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data.get("soft_deleted"))
        self.student.refresh_from_db()
        self.assertFalse(self.student.is_active)
        # Historique intact
        self.assertEqual(self.student.enrollments.count(), 2)
        # Masqué des listes actives
        lst = self.client.get("/api/students/")
        ids = [s["id"] for s in lst.data.get("results", lst.data)]
        self.assertNotIn(self.student.id, ids)
        # Visible avec include_inactive
        lst2 = self.client.get("/api/students/?include_inactive=1")
        ids2 = [s["id"] for s in lst2.data.get("results", lst2.data)]
        self.assertIn(self.student.id, ids2)

    def test_hard_delete_blocked_by_dependencies(self):
        resp = self.client.delete(f"/api/students/{self.student.id}/?hard=true")
        self.assertEqual(resp.status_code, 409)
        self.assertIn("inscriptions", resp.data.get("dependencies", {}))
        self.assertTrue(Student.objects.filter(pk=self.student.pk).exists())

    def test_remove_from_year_keeps_other_years_and_repoints(self):
        resp = self.client.post(
            f"/api/students/{self.student.id}/remove-from-year/",
            {"school_year_id": self.y2.id}, format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        # L'inscription y2 a disparu, y1 est intacte
        self.assertFalse(
            StudentEnrollment.objects.filter(student=self.student, school_year=self.y2).exists()
        )
        self.assertTrue(
            StudentEnrollment.objects.filter(student=self.student, school_year=self.y1).exists()
        )
        # Pointeur repositionné sur l'année restante la plus récente (y1)
        self.student.refresh_from_db()
        self.assertEqual(self.student.school_year_id, self.y1.id)
        self.assertEqual(self.student.current_class_id, self.cls_y1.id)

    def test_bulk_delete_is_soft(self):
        resp = self.client.post("/api/students/bulk-delete/", {"ids": [self.student.id]}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data.get("soft"))
        self.student.refresh_from_db()
        self.assertFalse(self.student.is_active)
        self.assertEqual(self.student.enrollments.count(), 2)


class ClassesYearIsolationTests(BaseYearSetup):
    def test_classes_default_to_active_year_only(self):
        resp = self.client.get("/api/classes/")
        results = resp.data.get("results", resp.data)
        ids = {c["id"] for c in results}
        self.assertIn(self.cls_y2.id, ids)      # année active
        self.assertNotIn(self.cls_y1.id, ids)   # année passée exclue par défaut

    def test_classes_explicit_year_and_all_years(self):
        resp1 = self.client.get(f"/api/classes/?school_year={self.y1.id}")
        ids1 = {c["id"] for c in resp1.data.get("results", resp1.data)}
        self.assertEqual(ids1, {self.cls_y1.id})

        resp2 = self.client.get("/api/classes/?all_years=1")
        ids2 = {c["id"] for c in resp2.data.get("results", resp2.data)}
        self.assertEqual(ids2, {self.cls_y1.id, self.cls_y2.id})


class ParentDeletionTests(BaseYearSetup):
    def setUp(self):
        super().setUp()
        pu = CustomUser.objects.create_user(
            username="par", email="par@test.bj", password="Pass1234!",
            role="parent", first_name="P", last_name="C", school=self.school,
        )
        self.parent = Parent.objects.create(user=pu)
        ParentStudent.objects.create(parent=self.parent, student=self.student, relationship="father")

    def test_parent_delete_is_soft_and_links_preserved(self):
        resp = self.client.delete(f"/api/parents/{self.parent.id}/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data.get("soft_deleted"))
        self.parent.user.refresh_from_db()
        self.assertFalse(self.parent.user.is_active)
        self.assertEqual(self.parent.children_links.count(), 1)

    def test_parent_hard_delete_blocked_when_linked(self):
        resp = self.client.delete(f"/api/parents/{self.parent.id}/?hard=true")
        self.assertEqual(resp.status_code, 409)
        self.assertTrue(Parent.objects.filter(pk=self.parent.pk).exists())
