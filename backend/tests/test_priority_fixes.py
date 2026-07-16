"""
Tests — Corrections prioritaires (itération courante) :

1. Notifications : related_url doit être préfixé par le rôle du
   DESTINATAIRE et pointer vers une route réellement déclarée côté
   frontend (plus de "/messages/{id}/" sans préfixe → catch-all → faux
   renvoi vers /login).
2. Tableaux de bord parent/élève : moyenne de français, moyenne d'anglais
   et moyenne par matière doivent être exposées (elles existaient déjà
   dans le moteur de calcul mais n'étaient jamais renvoyées par l'API).
3. Changement de mot de passe : doit fonctionner pour admin ET
   superadmin (l'endpoint existait déjà pour tout utilisateur authentifié
   — le bug était l'absence de formulaire frontend, couvert ici côté API
   pour garantir que rien ne régresse quand le formulaire est ajouté).
"""
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status

from apps.accounts.models import CustomUser
from apps.classes.models import Class
from apps.grades.models import Grade
from apps.notifications.utils import create_notification, notification_path, ROLE_PREFIXES
from apps.notifications.models import Notification
from apps.parents.models import Parent, ParentStudent
from apps.schools.models import School, SchoolYear, Level
from apps.students.models import Student, StudentEnrollment
from apps.subjects.models import Subject
from apps.teachers.models import Teacher


def auth(client, email, password="Pass1234!"):
    resp = client.post("/api/auth/login/", {"email": email, "password": password})
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {resp.data.get('access', '')}")
    return resp


# ─────────────────────────────────────────────────────────────────────────
# 1. Notifications — related_url préfixé par rôle
# ─────────────────────────────────────────────────────────────────────────

class NotificationPathTests(TestCase):
    def setUp(self):
        self.school = School.objects.create(name="Ecole N1", address="X")

    def _user(self, role, email):
        return CustomUser.objects.create_user(
            username=email, email=email, password="Pass1234!",
            role=role, first_name="T", last_name="U", school=self.school,
        )

    def test_all_roles_get_correct_prefix(self):
        """Chaque rôle connu produit un préfixe de route valide et distinct."""
        for role, prefix in ROLE_PREFIXES.items():
            user = self._user(role, f"{role}@test.bj")
            self.assertEqual(notification_path(user, "grades"), f"{prefix}/grades")

    def test_leading_slash_in_path_is_normalized(self):
        user = self._user("parent", "p1@test.bj")
        self.assertEqual(notification_path(user, "/grades"), "/parent/grades")

    def test_unknown_role_returns_empty_string_not_broken_url(self):
        """Un rôle inconnu ne doit jamais produire une URL non préfixée
        (qui tomberait dans le catch-all) — mieux vaut aucune URL."""
        user = self._user("parent", "p2@test.bj")
        user.role = "bogus"
        self.assertEqual(notification_path(user, "grades"), "")

    def test_create_notification_stores_related_url_verbatim(self):
        user = self._user("student", "s1@test.bj")
        notif = create_notification(user, "grade", "Titre", "Message", related_url="/student/grades")
        self.assertEqual(notif.related_url, "/student/grades")
        self.assertEqual(Notification.objects.get(pk=notif.pk).related_url, "/student/grades")


class GradeNotificationRedirectTests(TestCase):
    """FIX prioritaire n°1 : une note créée notifie l'élève ET ses parents,
    chacun avec une related_url préfixée par SON PROPRE rôle."""

    def setUp(self):
        self.school = School.objects.create(name="Ecole N2", address="X")
        self.year = SchoolYear.objects.create(
            school=self.school, name="2026-2027", is_current=True,
            start_date="2026-10-01", end_date="2027-07-31",
        )
        lvl = Level.objects.create(school=self.school, name="CE1", order=3)
        self.cls = Class.objects.create(name="CE1-A", level=lvl, school_year=self.year)
        self.subject = Subject.objects.create(school=self.school, name="Français", code="FR", coefficient=4, language="fr")
        self.cls.subjects.set([self.subject])

        self.student_user = CustomUser.objects.create_user(
            username="marie", email="marie@test.bj", password="Pass1234!",
            role="student", first_name="Marie", last_name="A", school=self.school,
        )
        self.student = Student.objects.create(
            user=self.student_user, school=self.school, first_name="Marie", last_name="A",
            current_class=self.cls, school_year=self.year,
        )
        StudentEnrollment.objects.create(student=self.student, school_year=self.year, class_obj=self.cls)

        self.parent_user = CustomUser.objects.create_user(
            username="papa", email="papa@test.bj", password="Pass1234!",
            role="parent", first_name="Papa", last_name="A", school=self.school,
        )
        self.parent = Parent.objects.create(user=self.parent_user)
        ParentStudent.objects.create(parent=self.parent, student=self.student, relationship="father")

        self.teacher_user = CustomUser.objects.create_user(
            username="prof", email="prof@test.bj", password="Pass1234!",
            role="teacher", first_name="Prof", last_name="U", school=self.school,
        )
        self.teacher = Teacher.objects.create(user=self.teacher_user)

        self.admin_user = CustomUser.objects.create_user(
            username="admin_n2", email="admin_n2@test.bj", password="Pass1234!",
            role="admin", first_name="Admin", last_name="U", school=self.school,
        )

        self.client = APIClient()
        auth(self.client, "admin_n2@test.bj")

    def _create_grade_via_api(self):
        resp = self.client.post("/api/grades/", {
            "student": self.student.id, "subject": self.subject.id,
            "school_year": self.year.id, "period": "T1", "value": "15",
        })
        self.assertEqual(resp.status_code, 201, resp.data)
        return resp

    def test_grade_creation_notifies_student_with_student_prefixed_url(self):
        self._create_grade_via_api()
        notif = Notification.objects.filter(user=self.student_user, type="grade").first()
        self.assertIsNotNone(notif)
        self.assertTrue(notif.related_url.startswith("/student/"))
        self.assertNotEqual(notif.related_url, "/messages/")  # ancien format cassé

    def test_grade_creation_notifies_parent_with_parent_prefixed_url(self):
        """Avant correction : le parent n'était PAS notifié du tout."""
        self._create_grade_via_api()
        notif = Notification.objects.filter(user=self.parent_user, type="grade").first()
        self.assertIsNotNone(notif, "Le parent doit être notifié d'une nouvelle note")
        self.assertTrue(notif.related_url.startswith("/parent/"))


# ─────────────────────────────────────────────────────────────────────────
# 1b. Notifications — absences et paiements
# ─────────────────────────────────────────────────────────────────────────

class AttendanceAndPaymentNotificationTests(TestCase):
    def setUp(self):
        self.school = School.objects.create(name="Ecole N3", address="X")
        self.year = SchoolYear.objects.create(
            school=self.school, name="2026-2027", is_current=True,
            start_date="2026-10-01", end_date="2027-07-31",
        )
        lvl = Level.objects.create(school=self.school, name="CE1", order=3)
        self.cls = Class.objects.create(name="CE1-B", level=lvl, school_year=self.year)

        self.student_user = CustomUser.objects.create_user(
            username="marie2", email="marie2@test.bj", password="Pass1234!",
            role="student", first_name="Marie", last_name="B", school=self.school,
        )
        self.student = Student.objects.create(
            user=self.student_user, school=self.school, first_name="Marie", last_name="B",
            current_class=self.cls, school_year=self.year,
        )
        StudentEnrollment.objects.create(student=self.student, school_year=self.year, class_obj=self.cls)

        self.parent_user = CustomUser.objects.create_user(
            username="papa2", email="papa2@test.bj", password="Pass1234!",
            role="parent", first_name="Papa", last_name="B", school=self.school,
        )
        self.parent = Parent.objects.create(user=self.parent_user)
        ParentStudent.objects.create(parent=self.parent, student=self.student, relationship="father")

        self.admin_user = CustomUser.objects.create_user(
            username="admin_n3", email="admin_n3@test.bj", password="Pass1234!",
            role="admin", first_name="Admin", last_name="U", school=self.school,
        )
        self.client = APIClient()
        auth(self.client, "admin_n3@test.bj")

    def test_absence_notifies_parent_and_student_with_correct_prefixes(self):
        resp = self.client.post("/api/attendance/", {
            "student": self.student.id, "date": "2026-02-05",
            "status": "absent", "school_year": self.year.id,
        })
        self.assertEqual(resp.status_code, 201, resp.data)

        parent_notif = Notification.objects.filter(user=self.parent_user, type="absence").first()
        student_notif = Notification.objects.filter(user=self.student_user, type="absence").first()
        self.assertIsNotNone(parent_notif)
        self.assertIsNotNone(student_notif, "L'élève doit lui aussi être notifié de son absence")
        self.assertTrue(parent_notif.related_url.startswith("/parent/"))
        self.assertTrue(student_notif.related_url.startswith("/student/"))

    def test_payment_notifies_parent_and_student_with_correct_prefixes(self):
        resp = self.client.post("/api/payments/", {
            "student": self.student.id, "school_year": self.year.id,
            "payment_type": "mensualite", "amount": "25000",
            "payment_date": "2026-02-05", "payment_method": "cash",
        })
        self.assertEqual(resp.status_code, 201, resp.data)

        parent_notif = Notification.objects.filter(user=self.parent_user, type="payment").first()
        student_notif = Notification.objects.filter(user=self.student_user, type="payment").first()
        self.assertIsNotNone(parent_notif, "Le parent doit être notifié d'un paiement")
        self.assertIsNotNone(student_notif)
        self.assertTrue(parent_notif.related_url.startswith("/parent/"))
        self.assertTrue(student_notif.related_url.startswith("/student/"))


# ─────────────────────────────────────────────────────────────────────────
# 2. Moyennes tableaux de bord parent / élève
# ─────────────────────────────────────────────────────────────────────────

class DashboardSubjectAveragesTests(TestCase):
    """FIX prioritaire n°2 : moyenne de français / anglais / par matière
    exposées sur les tableaux de bord parent et élève."""

    def setUp(self):
        self.school = School.objects.create(name="Ecole Moy", address="X")
        self.year = SchoolYear.objects.create(
            school=self.school, name="2026-2027", is_current=True,
            start_date="2026-10-01", end_date="2027-07-31",
        )
        lvl = Level.objects.create(school=self.school, name="CE2", order=4)
        self.cls = Class.objects.create(name="CE2-A", level=lvl, school_year=self.year)
        self.fr = Subject.objects.create(school=self.school, name="Français", code="FR", coefficient=4, language="fr")
        self.en = Subject.objects.create(school=self.school, name="English", code="ENG", coefficient=4, language="en")
        self.cls.subjects.set([self.fr, self.en])

        self.student_user = CustomUser.objects.create_user(
            username="eleve1", email="eleve1@test.bj", password="Pass1234!",
            role="student", first_name="E", last_name="Un", school=self.school,
        )
        self.student = Student.objects.create(
            user=self.student_user, school=self.school, first_name="E", last_name="Un",
            current_class=self.cls, school_year=self.year,
        )
        StudentEnrollment.objects.create(student=self.student, school_year=self.year, class_obj=self.cls)

        self.parent_user = CustomUser.objects.create_user(
            username="parent1", email="parent1@test.bj", password="Pass1234!",
            role="parent", first_name="P", last_name="Un", school=self.school,
        )
        self.parent = Parent.objects.create(user=self.parent_user)
        ParentStudent.objects.create(parent=self.parent, student=self.student, relationship="father")

        teacher_user = CustomUser.objects.create_user(
            username="prof1", email="prof1@test.bj", password="Pass1234!",
            role="teacher", first_name="Prof", last_name="Un", school=self.school,
        )
        self.teacher = Teacher.objects.create(user=teacher_user)

        Grade.objects.create(student=self.student, subject=self.fr, school_year=self.year,
                              teacher=self.teacher, period="T1", value=Decimal("16"))
        Grade.objects.create(student=self.student, subject=self.en, school_year=self.year,
                              teacher=self.teacher, period="T1", value=Decimal("12"))

    def test_annual_subject_averages_helper_groups_by_subject(self):
        result = Grade.get_annual_subject_averages(self.student, self.year)
        fr_entry = result[self.fr.id]
        en_entry = result[self.en.id]
        self.assertEqual(float(fr_entry["average"]), 16.0)
        self.assertEqual(float(en_entry["average"]), 12.0)
        self.assertEqual(fr_entry["language"], "fr")
        self.assertEqual(en_entry["language"], "en")

    def test_student_dashboard_exposes_subject_and_bilingual_averages(self):
        client = APIClient()
        auth(client, "eleve1@test.bj")
        resp = client.get("/api/dashboard/student/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        kpis = resp.data["kpis"]
        self.assertIn("subject_averages", kpis)
        self.assertIn("bilingual", kpis)
        names = {s["subject_name"]: s["average"] for s in kpis["subject_averages"]}
        self.assertEqual(float(names["Français"]), 16.0)
        self.assertEqual(float(names["English"]), 12.0)
        self.assertEqual(float(kpis["bilingual"]["fr_average"]), 16.0)
        self.assertEqual(float(kpis["bilingual"]["en_average"]), 12.0)

    def test_parent_dashboard_exposes_subject_and_bilingual_averages_per_child(self):
        client = APIClient()
        auth(client, "parent1@test.bj")
        resp = client.get("/api/dashboard/parent/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        child = resp.data["children"][0]
        self.assertIn("subject_averages", child)
        self.assertIn("bilingual", child)
        names = {s["subject_name"]: s["average"] for s in child["subject_averages"]}
        self.assertEqual(float(names["Français"]), 16.0)
        self.assertEqual(float(names["English"]), 12.0)

    def test_subject_without_grades_reports_none_not_zero(self):
        """Règle métier existante (v32) : une matière non notée = None, pas 0."""
        math = Subject.objects.create(school=self.school, name="Maths", code="MA", coefficient=5, language="fr")
        self.cls.subjects.add(math)
        result = Grade.get_annual_subject_averages(self.student, self.year)
        self.assertIsNone(result[math.id]["average"])
        self.assertFalse(result[math.id]["has_notes"])

    def test_student_with_no_grades_at_all_dashboard_does_not_crash(self):
        """Élève sans aucune note : pas de 500, moyenne générale = None."""
        student_user2 = CustomUser.objects.create_user(
            username="eleve2", email="eleve2@test.bj", password="Pass1234!",
            role="student", first_name="E", last_name="Deux", school=self.school,
        )
        student2 = Student.objects.create(
            user=student_user2, school=self.school, first_name="E", last_name="Deux",
            current_class=self.cls, school_year=self.year,
        )
        StudentEnrollment.objects.create(student=student2, school_year=self.year, class_obj=self.cls)
        client = APIClient()
        auth(client, "eleve2@test.bj")
        resp = client.get("/api/dashboard/student/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        self.assertIsNone(resp.data["kpis"]["average"])


# ─────────────────────────────────────────────────────────────────────────
# 3. Changement de mot de passe — admin / superadmin
# ─────────────────────────────────────────────────────────────────────────

class AdminPasswordChangeTests(TestCase):
    """FIX prioritaire n°3 : l'endpoint /api/auth/change-password/ (déjà
    générique côté backend) doit fonctionner pour admin et superadmin
    exactement comme pour les autres rôles."""

    def setUp(self):
        self.school = School.objects.create(name="Ecole Pwd", address="X")

    def _create(self, role, email):
        return CustomUser.objects.create_user(
            username=email, email=email, password="OldPass123!",
            role=role, first_name="U", last_name=role,
            school=self.school if role != "superadmin" else None,
        )

    def test_admin_can_change_own_password(self):
        self._create("admin", "admin1@test.bj")
        client = APIClient()
        auth(client, "admin1@test.bj", "OldPass123!")
        resp = client.post("/api/auth/change-password/", {
            "old_password": "OldPass123!", "new_password": "NewSecurePass456!",
        })
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        # L'ancien mot de passe ne fonctionne plus, le nouveau oui.
        client2 = APIClient()
        stale = client2.post("/api/auth/login/", {"email": "admin1@test.bj", "password": "OldPass123!"})
        self.assertNotEqual(stale.status_code, status.HTTP_200_OK)
        fresh = client2.post("/api/auth/login/", {"email": "admin1@test.bj", "password": "NewSecurePass456!"})
        self.assertEqual(fresh.status_code, status.HTTP_200_OK)

    def test_superadmin_can_change_own_password(self):
        self._create("superadmin", "root1@test.bj")
        client = APIClient()
        auth(client, "root1@test.bj", "OldPass123!")
        resp = client.post("/api/auth/change-password/", {
            "old_password": "OldPass123!", "new_password": "NewSecurePass456!",
        })
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)

    def test_wrong_old_password_rejected_for_admin(self):
        self._create("admin", "admin2@test.bj")
        client = APIClient()
        auth(client, "admin2@test.bj", "OldPass123!")
        resp = client.post("/api/auth/change-password/", {
            "old_password": "WrongPassword!", "new_password": "NewSecurePass456!",
        })
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_weak_new_password_rejected_for_admin(self):
        self._create("admin", "admin3@test.bj")
        client = APIClient()
        auth(client, "admin3@test.bj", "OldPass123!")
        resp = client.post("/api/auth/change-password/", {
            "old_password": "OldPass123!", "new_password": "1234",
        })
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
