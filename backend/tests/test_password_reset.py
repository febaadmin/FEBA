"""
Tests V4 — Priorité 2 : réinitialisation du mot de passe par un administrateur.

Matrice de permissions (appliquée CÔTÉ BACKEND) :
  admin      → teacher / parent / student (même établissement) : AUTORISÉ
  admin      → admin / superadmin / autre établissement / soi-même : REFUSÉ
  superadmin → admin / teacher / parent / student : AUTORISÉ
  superadmin → superadmin (y compris soi-même) : REFUSÉ
  teacher / parent / student → quiconque : REFUSÉ

Effets vérifiés : hachage Django, ancien mot de passe refusé, nouveau accepté,
must_change_password, révocation des refresh tokens, journal d'audit sans
mot de passe, parcours complet de changement obligatoire.
"""
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status

from apps.accounts.models import CustomUser, PasswordResetLog
from apps.schools.models import School

OLD_PWD = "AncienMdp#2026"
NEW_PWD = "NouveauMdp#2026"


def login(client, email, password=OLD_PWD):
    resp = client.post("/api/auth/login/", {"email": email, "password": password})
    return resp


def auth(client, email, password=OLD_PWD):
    resp = login(client, email, password)
    assert resp.status_code == 200, resp.data
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {resp.data['access']}")
    return resp


class PasswordResetFixture(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.school = School.objects.create(name="FEBA", address="Akpakpa, Cotonou")
        cls.other_school = School.objects.create(name="Autre École", address="Porto-Novo")

        def mk(username, role, school=None):
            return CustomUser.objects.create_user(
                username=username, email=f"{username}@test.bj", password=OLD_PWD,
                role=role, first_name=username.capitalize(), last_name="Feba",
                school=school,
            )

        cls.superadmin  = mk("superadmin", "superadmin")
        cls.superadmin2 = mk("superadmin2", "superadmin")
        cls.admin       = mk("admin", "admin", cls.school)
        cls.admin2      = mk("admin2", "admin", cls.school)
        cls.teacher     = mk("teacher", "teacher", cls.school)
        cls.parent      = mk("parent", "parent", cls.school)
        cls.student     = mk("student", "student", cls.school)
        cls.other_teacher = mk("otherteacher", "teacher", cls.other_school)

    def reset(self, client, target, new=NEW_PWD, confirm=None):
        return client.post(
            f"/api/auth/users/{target.pk}/reset-password/",
            {"new_password": new, "confirm_password": confirm or new},
            format="json",
        )


class AdminPermissionTests(PasswordResetFixture):
    """Un admin réinitialise teacher/parent/student, jamais admin/superadmin."""

    def setUp(self):
        self.client = APIClient()
        auth(self.client, "admin@test.bj")

    def test_admin_resets_teacher(self):
        resp = self.reset(self.client, self.teacher)
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)

    def test_admin_resets_parent(self):
        resp = self.reset(self.client, self.parent)
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)

    def test_admin_resets_student(self):
        resp = self.reset(self.client, self.student)
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)

    def test_admin_cannot_reset_admin(self):
        resp = self.reset(self.client, self.admin2)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        self.admin2.refresh_from_db()
        self.assertTrue(self.admin2.check_password(OLD_PWD))

    def test_admin_cannot_reset_superadmin(self):
        resp = self.reset(self.client, self.superadmin)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        self.superadmin.refresh_from_db()
        self.assertTrue(self.superadmin.check_password(OLD_PWD))

    def test_admin_cannot_reset_himself(self):
        resp = self.reset(self.client, self.admin)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_cannot_reset_other_school_user(self):
        """Contournement horizontal : ID d'un autre établissement dans l'URL."""
        resp = self.reset(self.client, self.other_teacher)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        self.other_teacher.refresh_from_db()
        self.assertTrue(self.other_teacher.check_password(OLD_PWD))


class SuperAdminPermissionTests(PasswordResetFixture):
    def setUp(self):
        self.client = APIClient()
        auth(self.client, "superadmin@test.bj")

    def test_superadmin_resets_admin(self):
        resp = self.reset(self.client, self.admin)
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)

    def test_superadmin_resets_teacher(self):
        resp = self.reset(self.client, self.teacher)
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)

    def test_superadmin_resets_parent(self):
        resp = self.reset(self.client, self.parent)
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)

    def test_superadmin_resets_student(self):
        resp = self.reset(self.client, self.student)
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)

    def test_superadmin_cannot_reset_superadmin(self):
        """Pas de règle métier autorisant superadmin → superadmin : refus."""
        resp = self.reset(self.client, self.superadmin2)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_superadmin_cannot_reset_himself(self):
        resp = self.reset(self.client, self.superadmin)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)


class UnauthorizedRolesTests(PasswordResetFixture):
    """Les rôles non administratifs appellent l'API directement : refus."""

    def test_teacher_parent_student_forbidden(self):
        for email in ("teacher@test.bj", "parent@test.bj", "student@test.bj"):
            with self.subTest(caller=email):
                client = APIClient()
                auth(client, email)
                resp = self.reset(client, self.student)
                self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_anonymous_forbidden(self):
        client = APIClient()
        resp = self.reset(client, self.student)
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)


class ResetEffectsTests(PasswordResetFixture):
    def setUp(self):
        self.client = APIClient()
        auth(self.client, "admin@test.bj")

    def test_password_hashed_old_rejected_new_accepted(self):
        resp = self.reset(self.client, self.teacher)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.teacher.refresh_from_db()
        # Haché par le framework Django (format algo$…$hash), jamais en clair.
        # (Les settings de test substituent un hasher rapide ; en production
        # c'est le PBKDF2 par défaut de Django — aucun hasher custom.)
        self.assertNotEqual(self.teacher.password, NEW_PWD)
        self.assertNotIn(NEW_PWD, self.teacher.password)
        self.assertIn("$", self.teacher.password)
        self.assertTrue(self.teacher.check_password(NEW_PWD))
        self.assertFalse(self.teacher.check_password(OLD_PWD))
        # Ancien mot de passe refusé au login (400 « Identifiants incorrects »),
        # nouveau accepté
        c2 = APIClient()
        self.assertEqual(login(c2, "teacher@test.bj", OLD_PWD).status_code, 400)
        ok = login(c2, "teacher@test.bj", NEW_PWD)
        self.assertEqual(ok.status_code, 200)
        self.assertTrue(ok.data["must_change_password"])

    def test_password_never_in_response(self):
        resp = self.reset(self.client, self.teacher)
        self.assertNotIn(NEW_PWD, str(resp.data))

    def test_confirmation_mismatch_rejected(self):
        resp = self.reset(self.client, self.teacher, confirm="Différent#2026")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("confirm_password", resp.data)
        self.teacher.refresh_from_db()
        self.assertTrue(self.teacher.check_password(OLD_PWD))

    def test_weak_password_rejected(self):
        for weak in ("court", "12345678", "password"):
            with self.subTest(pwd=weak):
                resp = self.reset(self.client, self.teacher, new=weak, confirm=weak)
                self.assertEqual(resp.status_code, 400)
        self.teacher.refresh_from_db()
        self.assertTrue(self.teacher.check_password(OLD_PWD))

    def test_refresh_tokens_revoked_author_keeps_session(self):
        # La cible se connecte (crée un refresh token en circulation)
        target_client = APIClient()
        target_login = auth(target_client, "teacher@test.bj")
        refresh = target_login.data["refresh"]

        resp = self.reset(self.client, self.teacher)
        self.assertEqual(resp.status_code, 200, resp.data)

        # Le refresh token de la cible est révoqué
        r = APIClient().post("/api/auth/refresh/", {"refresh": refresh})
        self.assertEqual(r.status_code, 401)

        # L'auteur, lui, garde sa session (peut toujours appeler l'API)
        me = self.client.get("/api/auth/me/")
        self.assertEqual(me.status_code, 200)

    def test_audit_log_created_without_password(self):
        self.reset(self.client, self.parent)
        log = PasswordResetLog.objects.get(target_user=self.parent)
        self.assertEqual(log.performed_by, self.admin)
        self.assertEqual(log.performed_by_email, "admin@test.bj")
        self.assertEqual(log.target_email, "parent@test.bj")
        self.assertEqual(log.target_role, "parent")
        self.assertEqual(log.school, self.school)
        self.assertIsNotNone(log.performed_at)
        # Aucune trace du mot de passe dans le journal
        for field in (log.performed_by_email, log.target_email, log.target_role):
            self.assertNotIn(NEW_PWD, field)

    def test_no_log_on_refused_attempt_password_intact(self):
        self.reset(self.client, self.admin2)
        self.assertFalse(PasswordResetLog.objects.filter(target_user=self.admin2).exists())


class MustChangePasswordFlowTests(PasswordResetFixture):
    """Parcours complet : reset → login temporaire → changement forcé → normal."""

    def test_full_flow(self):
        admin_client = APIClient()
        auth(admin_client, "admin@test.bj")
        # 1. Réinitialisation par l'administrateur
        resp = admin_client.post(
            f"/api/auth/users/{self.student.pk}/reset-password/",
            {"new_password": NEW_PWD, "confirm_password": NEW_PWD}, format="json",
        )
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertTrue(resp.data["must_change_password"])

        # 2. Connexion avec le mot de passe temporaire
        student_client = APIClient()
        lg = login(student_client, "student@test.bj", NEW_PWD)
        self.assertEqual(lg.status_code, 200)
        self.assertTrue(lg.data["must_change_password"])
        student_client.credentials(HTTP_AUTHORIZATION=f"Bearer {lg.data['access']}")

        # 3. /me/ expose le drapeau (redirection frontend vers le formulaire)
        me = student_client.get("/api/auth/me/")
        self.assertTrue(me.data["must_change_password"])

        # 4. Choix d'un nouveau mot de passe personnel
        final_pwd = "MonNouveauMdp#2026"
        ch = student_client.post("/api/auth/change-password/", {
            "old_password": NEW_PWD, "new_password": final_pwd,
        })
        self.assertEqual(ch.status_code, 200, ch.data)

        # 5. Retour normal : drapeau levé, nouveau mot de passe fonctionnel
        self.student.refresh_from_db()
        self.assertFalse(self.student.must_change_password)
        lg2 = login(APIClient(), "student@test.bj", final_pwd)
        self.assertEqual(lg2.status_code, 200)
        self.assertFalse(lg2.data["must_change_password"])
