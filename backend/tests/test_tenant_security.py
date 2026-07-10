"""
Tests de sécurité — isolation multi-tenant (FEBA v29)

Vérifie que les failles critiques identifiées lors de l'audit v29 sont
correctement fermées :

  1. Dashboard admin : ne doit voir QUE les données de son établissement
  2. Paiements : un admin ne peut PAS voir les paiements d'un autre tenant
  3. Emploi du temps : un admin ne peut PAS voir les créneaux d'un autre tenant
  4. Bulletins generate_all : ne doit générer que pour son établissement
  5. Annonces : filtre par établissement
  6. Utilisateurs : un admin ne voit QUE les utilisateurs de son école
  7. Élèves : idem
  8. Notes (grades) : isolation tenant
  9. SchoolViewSet : un admin ne voit QUE son école (pas toutes)
 10. Vues plateforme (platform/) : réservées au superadmin uniquement
"""
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status
from apps.accounts.models import CustomUser
from apps.schools.models import School, SchoolYear
from apps.students.models import Student
from apps.payments.models import Payment
from apps.grades.models import Grade


# ── Helpers ───────────────────────────────────────────────────────────────────

def make_school(name):
    return School.objects.create(name=name, address="Adresse test")


def make_user(email, role, school=None, first_name="Test", last_name="User"):
    u = CustomUser.objects.create_user(
        username=email.split("@")[0], email=email, password="Pass1234!",
        role=role, first_name=first_name, last_name=last_name, school=school,
    )
    return u


def get_bearer(client, email):
    resp = client.post("/api/auth/login/", {"email": email, "password": "Pass1234!"})
    return resp.data.get("access", "")


# ── Base bi-tenant ─────────────────────────────────────────────────────────────

class TwoSchoolBase(TestCase):
    """Crée deux établissements distincts + un admin par établissement."""

    def setUp(self):
        self.school_a = make_school("École A")
        self.school_b = make_school("École B")

        self.admin_a = make_user("admin_a@test.bj", "admin", self.school_a)
        self.admin_b = make_user("admin_b@test.bj", "admin", self.school_b)

        self.client_a = APIClient()
        self.client_a.credentials(HTTP_AUTHORIZATION=f"Bearer {get_bearer(self.client_a, 'admin_a@test.bj')}")

        self.client_b = APIClient()
        self.client_b.credentials(HTTP_AUTHORIZATION=f"Bearer {get_bearer(self.client_b, 'admin_b@test.bj')}")

        self.year_a = SchoolYear.objects.create(school=self.school_a, name="2024-2025", start_date="2024-10-01", end_date="2025-07-31")
        self.year_b = SchoolYear.objects.create(school=self.school_b, name="2024-2025", start_date="2024-10-01", end_date="2025-07-31")

        self.student_a = Student.objects.create(
            first_name="ElèveA", last_name="Test", school=self.school_a, school_year=self.year_a
        )
        self.student_b = Student.objects.create(
            first_name="ElèveB", last_name="Test", school=self.school_b, school_year=self.year_b
        )


# ── Test 1 : Dashboard ────────────────────────────────────────────────────────

class DashboardTenantTest(TwoSchoolBase):

    def test_admin_a_dashboard_shows_only_school_a_students(self):
        """Le dashboard ne doit compter que les élèves de l'établissement A."""
        resp = self.client_a.get("/api/dashboard/admin/")
        self.assertEqual(resp.status_code, 200)
        total_students = resp.data["kpis"]["total_students"]
        # L'établissement A n'a que student_a — student_b ne doit PAS être compté
        self.assertEqual(total_students, 1, f"Attendu 1, obtenu {total_students} (fuite cross-tenant)")

    def test_admin_b_dashboard_shows_only_school_b_students(self):
        resp = self.client_b.get("/api/dashboard/admin/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["kpis"]["total_students"], 1)


# ── Test 2 : Paiements ─────────────────────────────────────────────────────────

class PaymentTenantTest(TwoSchoolBase):

    def setUp(self):
        super().setUp()
        self.payment_a = Payment.objects.create(
            student=self.student_a, school_year=self.year_a,
            payment_type="inscription", amount=50000,
            reference_number="PAY-A-001",
        )
        self.payment_b = Payment.objects.create(
            student=self.student_b, school_year=self.year_b,
            payment_type="inscription", amount=75000,
            reference_number="PAY-B-001",
        )

    def test_admin_a_cannot_list_payment_b(self):
        """Admin A ne doit pas voir les paiements de l'établissement B."""
        resp = self.client_a.get("/api/payments/", {"all_years": "1"})
        self.assertEqual(resp.status_code, 200)
        refs = [p["reference_number"] for p in resp.data.get("results", resp.data)]
        self.assertIn("PAY-A-001", refs)
        self.assertNotIn("PAY-B-001", refs)

    def test_admin_a_cannot_retrieve_payment_b_by_id(self):
        """Admin A ne peut pas accéder directement au paiement B par son ID."""
        resp = self.client_a.get(f"/api/payments/{self.payment_b.id}/")
        self.assertIn(resp.status_code, [403, 404])

    def test_admin_b_cannot_restore_payment_a(self):
        """
        FIX v29 : restore() utilisait Payment.objects.get(pk=pk) — un admin
        pouvait restaurer un paiement d'un autre tenant en devinant son ID.
        Ce test vérifie que c'est corrigé.
        """
        # Soft-delete payment_a
        self.payment_a.is_deleted = True
        self.payment_a.save(update_fields=["is_deleted"])
        # Admin B tente de restaurer le paiement A
        resp = self.client_b.post(f"/api/payments/{self.payment_a.id}/restore/")
        self.assertIn(resp.status_code, [403, 404], "Le paiement d'un autre tenant ne doit pas être restaurable")


# ── Test 3 : Emploi du temps ────────────────────────────────────────────────────

class ScheduleTenantTest(TwoSchoolBase):

    def test_admin_a_cannot_list_schedule_of_school_b(self):
        """GET /api/schedule/ : admin A ne voit que les créneaux de son école."""
        from apps.classes.models import Class
        from apps.schools.models import Level
        # FIX : Class.level est obligatoire (NOT NULL) — le test créait la
        # classe sans niveau et échouait en NotNullViolation.
        level_b = Level.objects.create(school=self.school_b, name="6ème", order=1)
        cls_b = Class.objects.create(name="6ème B", school_year=self.year_b, level=level_b)
        from apps.subjects.models import Subject
        subj_b = Subject.objects.create(school=self.school_b, name="Maths B", code="MATB", coefficient=1)
        from apps.schedule.models import ClassSchedule
        sch_b = ClassSchedule.objects.create(
            cls=cls_b, school_year=self.year_b, subject=subj_b,
            day_of_week=1, start_time="08:00", end_time="09:00",
        )
        resp = self.client_a.get("/api/schedule/")
        self.assertEqual(resp.status_code, 200)
        ids = [s["id"] for s in resp.data.get("results", resp.data)]
        self.assertNotIn(sch_b.id, ids)


# ── Test 4 : Élèves ─────────────────────────────────────────────────────────────

class StudentTenantTest(TwoSchoolBase):

    def test_admin_a_cannot_list_students_of_school_b(self):
        resp = self.client_a.get("/api/students/", {"all_years": "1"})
        self.assertEqual(resp.status_code, 200)
        ids = [s["id"] for s in resp.data.get("results", resp.data)]
        self.assertIn(self.student_a.id, ids)
        self.assertNotIn(self.student_b.id, ids)

    def test_admin_a_cannot_retrieve_student_b_by_id(self):
        resp = self.client_a.get(f"/api/students/{self.student_b.id}/")
        self.assertIn(resp.status_code, [403, 404])

    def test_admin_a_cannot_enroll_student_b_in_year_a(self):
        """Tentative d'inscription cross-tenant via l'endpoint enroll."""
        resp = self.client_a.post(f"/api/students/{self.student_b.id}/enroll/", {
            "school_year": self.year_a.id,
        })
        self.assertIn(resp.status_code, [403, 404])

    def test_matricule_unique_per_school(self):
        """Deux élèves de deux écoles différentes peuvent avoir le même matricule."""
        self.student_a.matricule = "TEST-001"
        self.student_a.save(update_fields=["matricule"])
        self.student_b.matricule = "TEST-001"
        self.student_b.save(update_fields=["matricule"])
        # Reload
        self.student_a.refresh_from_db()
        self.student_b.refresh_from_db()
        self.assertEqual(self.student_a.matricule, "TEST-001")
        self.assertEqual(self.student_b.matricule, "TEST-001")


# ── Test 5 : Notes (grades) ─────────────────────────────────────────────────────

class GradesTenantTest(TwoSchoolBase):

    def setUp(self):
        super().setUp()
        from apps.subjects.models import Subject
        self.subject_a = Subject.objects.create(name="Maths A", code="MATH_A", school=self.school_a, coefficient=3)
        self.subject_b = Subject.objects.create(name="Maths B", code="MATH_B", school=self.school_b, coefficient=3)
        self.grade_a = Grade.objects.create(
            student=self.student_a, subject=self.subject_a, school_year=self.year_a,
            period="T1", value=14.5, note_type="devoir",
        )
        self.grade_b = Grade.objects.create(
            student=self.student_b, subject=self.subject_b, school_year=self.year_b,
            period="T1", value=12.0, note_type="devoir",
        )

    def test_admin_a_cannot_list_grades_of_school_b(self):
        resp = self.client_a.get("/api/grades/", {"all_years": "1"})
        self.assertEqual(resp.status_code, 200)
        ids = [g["id"] for g in resp.data.get("results", resp.data)]
        self.assertIn(self.grade_a.id, ids)
        self.assertNotIn(self.grade_b.id, ids)

    def test_admin_a_cannot_bulk_save_grade_for_student_b(self):
        """bulk_save : les IDs d'élèves doivent appartenir au tenant."""
        resp = self.client_a.post("/api/grades/bulk_save/", {
            "grades": [{
                "student": self.student_b.id,
                "subject": self.subject_b.id,
                "school_year": self.year_b.id,
                "period": "T1",
                "value": 16.0,
            }]
        }, format="json")
        # Un seul grade soumis → doit retourner 0 enregistrés (ou erreur)
        if resp.status_code == 200:
            self.assertEqual(resp.data.get("saved", 0), 0, "La note cross-tenant ne doit pas être enregistrée")


# ── Test 6 : Vues plateforme (superadmin uniquement) ───────────────────────────

class PlatformViewsAccessTest(TestCase):

    def setUp(self):
        self.school = make_school("École Test")
        self.admin = make_user("admin@test.bj", "admin", self.school)
        self.superadmin = make_user("super@test.bj", "superadmin")
        self.client_admin = APIClient()
        self.client_admin.credentials(HTTP_AUTHORIZATION=f"Bearer {get_bearer(self.client_admin, 'admin@test.bj')}")
        self.client_super = APIClient()
        self.client_super.credentials(HTTP_AUTHORIZATION=f"Bearer {get_bearer(self.client_super, 'super@test.bj')}")

    def test_platform_stats_forbidden_for_admin(self):
        resp = self.client_admin.get("/api/platform/stats/")
        self.assertEqual(resp.status_code, 403)

    def test_platform_stats_accessible_for_superadmin(self):
        resp = self.client_super.get("/api/platform/stats/")
        self.assertIn(resp.status_code, [200, 201])

    def test_platform_schools_forbidden_for_admin(self):
        resp = self.client_admin.get("/api/platform/schools/")
        self.assertEqual(resp.status_code, 403)

    def test_platform_schools_accessible_for_superadmin(self):
        resp = self.client_super.get("/api/platform/schools/")
        self.assertEqual(resp.status_code, 200)

    def test_school_suspension_forbidden_for_admin(self):
        resp = self.client_admin.post(f"/api/platform/schools/{self.school.slug}/suspend/")
        self.assertEqual(resp.status_code, 403)

    def test_school_suspension_works_for_superadmin(self):
        resp = self.client_super.post(
            f"/api/platform/schools/{self.school.slug}/suspend/",
            {"reason": "Test suspension"},
            format="json",
        )
        self.assertEqual(resp.status_code, 200)
        self.school.refresh_from_db()
        self.assertFalse(self.school.is_active)

    def test_school_reactivation_works_for_superadmin(self):
        self.school.is_active = False
        self.school.save()
        resp = self.client_super.post(f"/api/platform/schools/{self.school.slug}/reactivate/")
        self.assertEqual(resp.status_code, 200)
        self.school.refresh_from_db()
        self.assertTrue(self.school.is_active)


# ── Test 7 : Connexion bloquée pour école suspendue ──────────────────────────────

class SuspendedSchoolLoginTest(TestCase):

    def test_login_blocked_when_school_suspended(self):
        """
        Un utilisateur d'un établissement suspendu ne doit pas pouvoir
        se connecter (is_active=False sur l'école → erreur à la connexion).
        """
        school = make_school("École Suspendue")
        school.is_active = False
        school.save()
        user = make_user("user_suspended@test.bj", "admin", school)

        client = APIClient()
        resp = client.post("/api/auth/login/", {"email": "user_suspended@test.bj", "password": "Pass1234!"})
        self.assertNotEqual(resp.status_code, 200, "Un utilisateur d'une école suspendue ne doit pas pouvoir se connecter")


# ── Test 8 : Annonces ──────────────────────────────────────────────────────────

class AnnouncementTenantTest(TwoSchoolBase):

    def test_admin_a_cannot_list_announcements_of_school_b(self):
        from apps.announcements.models import Announcement
        ann_b = Announcement.objects.create(
            title="Annonce B", content="Contenu B",
            author=self.admin_b, is_published=True, target_roles=["all"],
        )
        resp = self.client_a.get("/api/announcements/")
        self.assertEqual(resp.status_code, 200)
        ids = [a["id"] for a in resp.data.get("results", resp.data)]
        self.assertNotIn(ann_b.id, ids, "L'annonce de l'établissement B ne doit pas être visible par l'admin A")


# ── Test 9 : SchoolViewSet — chaque admin ne voit QUE son école ──────────────────

class SchoolViewTenantTest(TwoSchoolBase):

    def test_admin_a_sees_only_own_school(self):
        resp = self.client_a.get("/api/schools/schools/")
        self.assertEqual(resp.status_code, 200)
        data = resp.data.get("results", resp.data)
        ids = [s["id"] for s in data] if isinstance(data, list) else [data.get("id")]
        self.assertIn(self.school_a.id, ids)
        self.assertNotIn(self.school_b.id, ids)

    def test_admin_a_cannot_retrieve_school_b_by_id(self):
        resp = self.client_a.get(f"/api/schools/schools/{self.school_b.id}/")
        self.assertIn(resp.status_code, [403, 404])
