"""
Audit — isolation des académies en ÉCRITURE.

Faille constatée : les serializers acceptaient l'identifiant d'un élève,
d'une matière, d'une classe ou d'un enseignant d'une AUTRE académie. Un
administrateur FEBA pouvait ainsi créer une absence sur un élève FHA (et
notifier ses parents), une note, un devoir, un créneau, rattacher un élève
à une classe FHA… Ces tests vérifient le refus, objet par objet, et que les
écritures légitimes restent possibles.
"""
from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import CustomUser
from apps.attendance.models import Attendance
from apps.classes.models import Class
from apps.grades.models import Grade
from apps.schools.models import Level, School, SchoolYear
from apps.students.models import Student
from apps.subjects.models import Subject
from apps.teachers.models import Teacher


class CrossAcademyWriteTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.data = {}
        for key in ("a", "b"):
            school = School.objects.create(name=f"Ecole {key}", address="x", code=f"XW-{key.upper()}")
            year = SchoolYear.objects.create(school=school, name="2026-2027", is_current=True,
                                             start_date="2026-09-01", end_date="2027-07-01")
            level = Level.objects.create(school=school, name=f"CE1-{key}")
            klass = Class.objects.create(name=f"CE1-{key}", level=level, school_year=year)
            subject = Subject.objects.create(school=school, name=f"Maths {key}", code=f"M{key}")
            student = Student.objects.create(school=school, school_year=year, current_class=klass,
                                             first_name="E", last_name=key)
            teacher_user = CustomUser.objects.create_user(
                username=f"xw_t_{key}", email=f"xw.t.{key}@test.io", password="x", role="teacher", school=school)
            teacher = Teacher.objects.create(user=teacher_user)
            admin = CustomUser.objects.create_user(
                username=f"xw_a_{key}", email=f"xw.a.{key}@test.io", password="x", role="admin", school=school)
            cls.data[key] = dict(school=school, year=year, level=level, klass=klass, subject=subject,
                                 student=student, teacher=teacher, admin=admin)
        cls.superadmin = CustomUser.objects.create_user(
            username="xw_super", email="xw.super@test.io", password="x", role="superadmin")

    def api(self, user):
        client = APIClient()
        client.force_authenticate(user)
        return client

    def test_attendance_on_other_academy_student_refused(self):
        a, b = self.data["a"], self.data["b"]
        resp = self.api(a["admin"]).post("/api/attendance/", {
            "student": b["student"].id, "date": "2026-10-01", "status": "absent"}, format="json")
        self.assertEqual(resp.status_code, 400, resp.content)
        self.assertFalse(Attendance.objects.filter(student=b["student"]).exists())
        ok = self.api(a["admin"]).post("/api/attendance/", {
            "student": a["student"].id, "date": "2026-10-01", "status": "absent"}, format="json")
        self.assertEqual(ok.status_code, 201, ok.content)

    def test_grade_with_foreign_student_or_subject_refused(self):
        a, b = self.data["a"], self.data["b"]
        for student, subject in ((b["student"], a["subject"]), (a["student"], b["subject"])):
            resp = self.api(a["admin"]).post("/api/grades/", {
                "student": student.id, "subject": subject.id, "school_year": a["year"].id,
                "period": "T1", "value": "12", "note_type": "devoir"}, format="json")
            self.assertEqual(resp.status_code, 400, resp.content)
        self.assertFalse(Grade.objects.exists())

    def test_homework_on_foreign_class_refused(self):
        a, b = self.data["a"], self.data["b"]
        resp = self.api(a["admin"]).post("/api/homework/", {
            "title": "Devoir", "description": "x", "cls": b["klass"].id, "subject": a["subject"].id,
            "due_date": "2026-10-20"}, format="json")
        self.assertEqual(resp.status_code, 400, resp.content)

    def test_student_cannot_be_put_in_foreign_class(self):
        a, b = self.data["a"], self.data["b"]
        resp = self.api(a["admin"]).patch(f"/api/students/{a['student'].id}/", {
            "current_class": b["klass"].id}, format="json")
        self.assertEqual(resp.status_code, 400, resp.content)
        a["student"].refresh_from_db()
        self.assertEqual(a["student"].current_class_id, a["klass"].id)

    def test_class_with_foreign_level_refused(self):
        a, b = self.data["a"], self.data["b"]
        resp = self.api(a["admin"]).post("/api/classes/", {
            "name": "X", "level": b["level"].id, "school_year": a["year"].id}, format="json")
        self.assertEqual(resp.status_code, 400, resp.content)

    def test_teacher_cannot_get_foreign_subjects(self):
        a, b = self.data["a"], self.data["b"]
        resp = self.api(a["admin"]).patch(f"/api/teachers/{a['teacher'].id}/", {
            "subject_ids": [b["subject"].id]}, format="json")
        self.assertEqual(resp.status_code, 400, resp.content)
        self.assertFalse(a["teacher"].subjects.filter(pk=b["subject"].pk).exists())

    def test_superadmin_cannot_mix_academies_in_one_object(self):
        a, b = self.data["a"], self.data["b"]
        resp = self.api(self.superadmin).post(f"/api/grades/?school_id={a['school'].id}", {
            "student": a["student"].id, "subject": b["subject"].id, "school_year": a["year"].id,
            "period": "T1", "value": "12", "note_type": "devoir"}, format="json")
        self.assertEqual(resp.status_code, 400, resp.content)

    def test_mixin_consistency_without_request_school(self):
        """Super-admin en vue consolidée : relations d'académies différentes refusées."""
        from rest_framework.test import APIRequestFactory
        from apps.attendance.serializers import AttendanceSerializer

        a, b = self.data["a"], self.data["b"]
        request = APIRequestFactory().post("/")
        request.user = self.superadmin
        request.query_params = {}
        serializer = AttendanceSerializer(data={
            "student": a["student"].id, "subject": b["subject"].id, "date": "2026-10-01",
            "status": "absent"}, context={"request": request})
        self.assertFalse(serializer.is_valid())
        self.assertIn("non_field_errors", serializer.errors)
