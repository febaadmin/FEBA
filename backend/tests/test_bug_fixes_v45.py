"""
Tests de régression — corrections v45 (BUGS N°1 à N°9).

  BUG N°6 : formule bilingue = (FR × 60%) + (EN × 40%)
  BUG N°2 : statistiques de classe (min/max FR, EN, bilingue) ; plus de rang
  BUG N°1 : bulletin PDF généré avec les parties FR et EN séparées
  BUG N°3 : dashboards élève et parent — moyenne générale renseignée
  BUG N°4 : l'admin crée élève/parent/enseignant mais jamais admin/superadmin
  BUG N°5 : CRUD années scolaires — gardes de suppression
  BUG N°8 : matricules FEBA_26_0001 séquentiels et compatibles
"""
import datetime
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import CustomUser
from apps.classes.models import Class
from apps.grades.models import Grade
from apps.parents.models import Parent, ParentStudent
from apps.schools.models import School, SchoolYear, Level
from apps.students.models import Student, StudentEnrollment, generate_matricule
from apps.subjects.models import Subject
from apps.teachers.models import Teacher


def auth(client, email, password="Pass1234!"):
    resp = client.post("/api/auth/login/", {"email": email, "password": password})
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {resp.data.get('access', '')}")


class BaseSchoolSetup(TestCase):
    """École + année active + classe bilingue + 2 élèves notés."""

    def setUp(self):
        self.school = School.objects.create(
            name="École Test", address="X", matricule_prefix="FEBA",
        )
        self.year = SchoolYear.objects.create(
            school=self.school, name="2025-2026",
            start_date=datetime.date(2025, 10, 1),
            end_date=datetime.date(2026, 7, 31),
            is_current=True,
        )
        self.level = Level.objects.create(school=self.school, name="CE1", order=1)
        self.cls = Class.objects.create(name="CE1-A", level=self.level, school_year=self.year)
        self.fr = Subject.objects.create(
            school=self.school, name="Français", code="FR", coefficient=2, language="fr")
        self.en = Subject.objects.create(
            school=self.school, name="English", code="ENG", coefficient=2, language="en")
        self.cls.subjects.set([self.fr, self.en])

        self.admin = CustomUser.objects.create_user(
            username="adm", email="adm@test.bj", password="Pass1234!",
            role="admin", first_name="A", last_name="D", school=self.school,
        )
        tu = CustomUser.objects.create_user(
            username="t1", email="t1@test.bj", password="Pass1234!",
            role="teacher", first_name="T", last_name="One", school=self.school,
        )
        self.teacher = Teacher.objects.create(user=tu)

        def mk_student(i, fr_val, en_val):
            u = CustomUser.objects.create_user(
                username=f"el{i}", email=f"el{i}@test.bj", password="Pass1234!",
                role="student", first_name=f"E{i}", last_name="Test", school=self.school,
            )
            s = Student.objects.create(
                user=u, school=self.school, first_name=f"E{i}", last_name="Test",
                current_class=self.cls, school_year=self.year,
            )
            StudentEnrollment.objects.create(
                student=s, school_year=self.year, class_obj=self.cls)
            Grade.objects.create(student=s, subject=self.fr, school_year=self.year,
                                 teacher=self.teacher, period="T1", value=fr_val)
            Grade.objects.create(student=s, subject=self.en, school_year=self.year,
                                 teacher=self.teacher, period="T1", value=en_val)
            return s

        self.s1 = mk_student(1, 15, 10)   # bilingue = 15*0.6 + 10*0.4 = 13
        self.s2 = mk_student(2, 8, 18)    # bilingue = 8*0.6 + 18*0.4 = 12


class BilingualFormulaTests(BaseSchoolSetup):
    """BUG N°6 — la formule est (FR × 60%) + (EN × 40%) partout."""

    def test_bilingual_average_is_60_40(self):
        data = Grade.calculate_bilingual_averages(self.s1, self.year, "T1")
        self.assertEqual(data["fr_average"], Decimal("15"))
        self.assertEqual(data["en_average"], Decimal("10"))
        self.assertEqual(data["bilingual_average"], Decimal("13.00"))

    def test_formula_label_updated(self):
        data = Grade.calculate_bilingual_averages(self.s1, self.year, "T1")
        self.assertIn("60%", data["formula"])
        self.assertIn("40%", data["formula"])
        self.assertIn("FR × 60%", data["formula"])

    def test_bilingual_endpoint_uses_new_formula(self):
        client = APIClient()
        auth(client, "adm@test.bj")
        resp = client.get(
            f"/api/grades/bilingual/?student={self.s1.id}&period=T1&school_year={self.year.id}")
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(float(resp.data["bilingual_average"]), 13.0)


class ClassStatsTests(BaseSchoolSetup):
    """BUG N°2 — min/max de classe calculés dynamiquement."""

    def test_class_min_max(self):
        stats = Grade.get_class_bilingual_stats(self.cls, self.year, "T1")
        self.assertEqual(stats["fr_min"], Decimal("8"))
        self.assertEqual(stats["fr_max"], Decimal("15"))
        self.assertEqual(stats["en_min"], Decimal("10"))
        self.assertEqual(stats["en_max"], Decimal("18"))
        self.assertEqual(stats["bi_min"], Decimal("12.00"))
        self.assertEqual(stats["bi_max"], Decimal("13.00"))
        self.assertEqual(stats["students_count"], 2)

    def test_empty_class_returns_none(self):
        empty_cls = Class.objects.create(
            name="CE1-B", level=self.level, school_year=self.year)
        stats = Grade.get_class_bilingual_stats(empty_cls, self.year, "T1")
        self.assertIsNone(stats["fr_min"])
        self.assertIsNone(stats["bi_max"])


class BulletinGenerationTests(BaseSchoolSetup):
    """BUG N°1 / N°2 — bulletin PDF : sections FR/EN, sans rang."""

    def test_bulletin_pdf_generated_without_rank(self):
        from apps.bulletins.pdf_generator import generate_bulletin
        bulletin = generate_bulletin(self.s1, "T1", self.year)
        self.assertTrue(bulletin.pdf_file)
        self.assertGreater(bulletin.pdf_file.size, 1000)
        self.assertIsNone(bulletin.rank_in_class)
        self.assertEqual(bulletin.average, Decimal("12.50"))  # (15*2+10*2)/4

    def test_bulletin_pdf_contains_fr_and_en_sections(self):
        from apps.bulletins.pdf_generator import generate_bulletin
        from pypdf import PdfReader
        from io import BytesIO
        bulletin = generate_bulletin(self.s1, "T1", self.year)
        text = "".join(
            page.extract_text() for page in
            PdfReader(BytesIO(bulletin.pdf_file.read())).pages
        )
        self.assertIn("PARTIE FRANÇAISE", text)
        self.assertIn("ENGLISH SECTION", text)
        self.assertIn("Moy. min. classe", text)
        self.assertIn("Moy. max. classe", text)
        self.assertIn("60%", text)
        self.assertNotIn("Rang", text)

    def test_annual_bulletin_with_missing_trimesters(self):
        """FIX BUG N°9 : None > 0 plantait le bulletin annuel (TypeError)."""
        from apps.bulletins.pdf_generator import generate_bulletin
        bulletin = generate_bulletin(self.s1, "annual", self.year)
        self.assertTrue(bulletin.pdf_file)


class DashboardTests(BaseSchoolSetup):
    """BUG N°3 — moyenne générale affichée sur les dashboards."""

    def test_student_dashboard_average(self):
        client = APIClient()
        auth(client, "el1@test.bj")
        resp = client.get("/api/dashboard/student/")
        self.assertEqual(resp.status_code, 200, resp.data)
        kpis = resp.data["kpis"]
        self.assertEqual(kpis["average"], 12.5)
        self.assertEqual(kpis["average_t1"], 12.5)
        self.assertIsNone(kpis["average_t2"])
        self.assertEqual(kpis["annual_average"], 12.5)
        self.assertEqual(kpis["appreciation"], "Bien")

    def test_parent_dashboard_average(self):
        pu = CustomUser.objects.create_user(
            username="par", email="par@test.bj", password="Pass1234!",
            role="parent", first_name="P", last_name="T", school=self.school,
        )
        parent = Parent.objects.create(user=pu)
        ParentStudent.objects.create(parent=parent, student=self.s1, relationship="father")
        client = APIClient()
        auth(client, "par@test.bj")
        resp = client.get("/api/dashboard/parent/")
        self.assertEqual(resp.status_code, 200, resp.data)
        child = resp.data["children"][0]
        self.assertEqual(child["average"], 12.5)
        self.assertEqual(child["average_t1"], 12.5)
        self.assertEqual(child["appreciation"], "Bien")


class AdminUserManagementTests(BaseSchoolSetup):
    """BUG N°4 — l'admin crée élève/parent/enseignant, jamais admin/superadmin."""

    def setUp(self):
        super().setUp()
        self.client = APIClient()
        auth(self.client, "adm@test.bj")
        self.base = {
            "first_name": "New", "last_name": "User",
            "password": "Xk9#mPq2vL", "password2": "Xk9#mPq2vL",
        }

    def test_admin_creates_allowed_roles(self):
        for role in ("student", "parent", "teacher"):
            resp = self.client.post("/api/auth/users/", {
                **self.base, "email": f"new.{role}@test.bj", "role": role,
            })
            self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
            created = CustomUser.objects.get(email=f"new.{role}@test.bj")
            self.assertEqual(created.school_id, self.school.id)

    def test_admin_cannot_create_admin_or_superadmin(self):
        for role in ("admin", "superadmin"):
            resp = self.client.post("/api/auth/users/", {
                **self.base, "email": f"bad.{role}@test.bj", "role": role,
            })
            self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST, resp.data)
            self.assertFalse(CustomUser.objects.filter(email=f"bad.{role}@test.bj").exists())

    def test_admin_cannot_escalate_role(self):
        target = CustomUser.objects.get(email="el1@test.bj")
        resp = self.client.patch(f"/api/auth/users/{target.id}/", {"role": "admin"})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        target.refresh_from_db()
        self.assertEqual(target.role, "student")

    def test_admin_cannot_see_admin_accounts(self):
        resp = self.client.get("/api/auth/users/?role=admin")
        rows = resp.data.get("results", resp.data)
        self.assertEqual(len(rows), 0)


class SchoolYearCrudGuardTests(BaseSchoolSetup):
    """BUG N°5 — CRUD des années : suppression protégée."""

    def setUp(self):
        super().setUp()
        self.client = APIClient()
        auth(self.client, "adm@test.bj")

    def test_cannot_delete_active_year(self):
        resp = self.client.delete(f"/api/schools/years/{self.year.id}/")
        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT)
        self.assertTrue(SchoolYear.objects.filter(pk=self.year.pk).exists())

    def test_cannot_delete_used_year(self):
        old = SchoolYear.objects.create(
            school=self.school, name="2024-2025",
            start_date=datetime.date(2024, 10, 1),
            end_date=datetime.date(2025, 7, 31),
        )
        old_cls = Class.objects.create(name="CE1-A", level=self.level, school_year=old)
        StudentEnrollment.objects.create(
            student=self.s1, school_year=old, class_obj=old_cls)
        resp = self.client.delete(f"/api/schools/years/{old.id}/")
        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT)
        self.assertIn("dependencies", resp.data)
        self.assertTrue(SchoolYear.objects.filter(pk=old.pk).exists())

    def test_delete_empty_year(self):
        empty = SchoolYear.objects.create(
            school=self.school, name="2030-2031",
            start_date=datetime.date(2030, 10, 1),
            end_date=datetime.date(2031, 7, 31),
        )
        resp = self.client.delete(f"/api/schools/years/{empty.id}/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertFalse(SchoolYear.objects.filter(pk=empty.pk).exists())

    def test_create_year_without_school_in_payload(self):
        """L'admin crée une année sans préciser school : tenant auto-résolu."""
        resp = self.client.post("/api/schools/years/", {
            "name": "2031-2032",
            "start_date": "2031-10-01", "end_date": "2032-07-31",
        })
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        self.assertEqual(
            SchoolYear.objects.get(name="2031-2032").school_id, self.school.id)

    def test_update_year(self):
        old = SchoolYear.objects.create(
            school=self.school, name="2028-2029",
            start_date=datetime.date(2028, 10, 1),
            end_date=datetime.date(2029, 7, 31),
        )
        resp = self.client.patch(f"/api/schools/years/{old.id}/", {"name": "2028-2029 v2"})
        self.assertEqual(resp.status_code, 200, resp.data)
        old.refresh_from_db()
        self.assertEqual(old.name, "2028-2029 v2")


class MatriculeTests(TestCase):
    """BUG N°2 — matricules FEBA-YY-NNNN (année système, format à tirets).

    NB : remplace l'ancien format à tirets bas ``FEBA_26_0001``. Tests
    exhaustifs (années multiples, concurrence, amorçage) dans
    ``tests/test_matricule.py``.
    """

    def setUp(self):
        self.school = School.objects.create(
            name="École Matricule", address="X", matricule_prefix="FEBA",
        )

    def test_new_format(self):
        yy = timezone.now().year % 100
        s = Student.objects.create(school=self.school, first_name="A", last_name="B")
        self.assertEqual(s.matricule, f"FEBA-{yy:02d}-0001")

    def test_sequential_and_unique(self):
        s1 = Student.objects.create(school=self.school, first_name="A", last_name="B")
        s2 = Student.objects.create(school=self.school, first_name="C", last_name="D")
        self.assertNotEqual(s1.matricule, s2.matricule)
        self.assertTrue(s2.matricule.endswith("-0002"))

    def test_old_matricules_still_compatible(self):
        old = Student.objects.create(
            school=self.school, first_name="O", last_name="L",
            matricule="GROUPESCOL-2026-0005",
        )
        self.assertEqual(old.matricule, "GROUPESCOL-2026-0005")
        # La séquence du nouveau format n'est pas polluée par les anciens
        s = Student.objects.create(school=self.school, first_name="A", last_name="B")
        self.assertTrue(s.matricule.endswith("-0001"))

    def test_prefix_derived_from_slug_when_not_configured(self):
        other = School.objects.create(name="Groupe Scolaire Demo", address="X")
        s = Student.objects.create(school=other, first_name="A", last_name="B")
        self.assertTrue(s.matricule.startswith("DEMO-"))

    def test_per_school_sequences_are_independent(self):
        other = School.objects.create(
            name="Autre École", address="X", matricule_prefix="FEBA")
        s1 = Student.objects.create(school=self.school, first_name="A", last_name="B")
        s2 = Student.objects.create(school=other, first_name="C", last_name="D")
        # Même préfixe, mais séquences par établissement
        self.assertTrue(s1.matricule.endswith("-0001"))
        self.assertTrue(s2.matricule.endswith("-0001"))
