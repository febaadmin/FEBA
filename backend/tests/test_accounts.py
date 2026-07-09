"""
Tests — accounts (FEBA v29.1)

Couvre :
  1. UserCreateSerializer — plus d'AssertionError DRF au chargement
  2. Anti-escalade de privilège (admin ne peut pas créer un superadmin)
  3. Isolation tenant sur la création : un admin crée toujours dans son école
  4. CustomTokenObtainPairSerializer — login, école suspendue, pas de comptes actifs
  5. Changement de mot de passe
  6. IDOR sur UserDetailView (un admin d'un établissement ne voit pas un autre)

Chaque test couvre un bug qui a existé dans le projet (bug régression guard).
"""
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status
from apps.accounts.models import CustomUser
from apps.schools.models import School


def make_school(name="Test School"):
    return School.objects.create(name=name, address="Test")


def make_user(email, role, school=None, password="Pass1234!", first_name="Test", last_name="User"):
    u = CustomUser.objects.create_user(
        username=email.split("@")[0],
        email=email,
        password=password,
        role=role,
        first_name=first_name,
        last_name=last_name,
        school=school,
    )
    return u


def get_token(client, email, password="Pass1234!"):
    resp = client.post("/api/auth/login/", {"email": email, "password": password})
    return resp.data.get("access", "")


# ─────────────────────────────────────────────────────────────────────────────
# 1. BUG GUARD — Plus d'AssertionError DRF au chargement du module
# ─────────────────────────────────────────────────────────────────────────────

class UserCreateSerializerImportTest(TestCase):
    """
    Régression guard pour le bug critique v29 :
    `PrimaryKeyRelatedField(queryset=None)` levait une AssertionError
    à l'import du module, faisant crasher le backend au démarrage.
    Ce test échoue si le bug réapparaît.
    """

    def test_import_does_not_raise(self):
        """Le simple import de UserCreateSerializer ne doit pas lever d'exception."""
        # Si le bug réapparaît, cette ligne lève AssertionError et le test échoue
        from apps.accounts.serializers import UserCreateSerializer
        self.assertIsNotNone(UserCreateSerializer)

    def test_serializer_instantiation_without_data(self):
        """Instancier UserCreateSerializer vide ne doit pas crasher."""
        from apps.accounts.serializers import UserCreateSerializer
        s = UserCreateSerializer()
        # Le champ 'school' doit être présent et avoir un queryset valide
        self.assertIn("school", s.fields)
        # queryset doit être un QuerySet (pas None)
        field = s.fields["school"]
        self.assertIsNotNone(field.queryset)


# ─────────────────────────────────────────────────────────────────────────────
# 2. Anti-escalade de privilège
# ─────────────────────────────────────────────────────────────────────────────

class PrivilegeEscalationTest(TestCase):

    def setUp(self):
        self.school = make_school()
        self.admin = make_user("admin@test.bj", "admin", self.school)
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {get_token(self.client, 'admin@test.bj')}")

    def test_admin_cannot_create_superadmin(self):
        """Un admin ne peut pas créer un compte superadmin."""
        resp = self.client.post("/api/auth/users/", {
            "email": "newsuper@test.bj",
            "username": "newsuper",
            "role": "superadmin",
            "password": "Pass1234!",
            "password2": "Pass1234!",
        })
        self.assertIn(resp.status_code, [400, 403], "Admin ne devrait pas pouvoir créer un superadmin")

    def test_admin_cannot_create_admin(self):
        """Un admin ne peut pas créer un autre admin (même niveau)."""
        resp = self.client.post("/api/auth/users/", {
            "email": "newadmin@test.bj",
            "username": "newadmin",
            "role": "admin",
            "password": "Pass1234!",
            "password2": "Pass1234!",
        })
        self.assertIn(resp.status_code, [400, 403])

    def test_admin_can_create_teacher(self):
        """Un admin peut créer un compte enseignant dans son école."""
        resp = self.client.post("/api/auth/users/", {
            "email": "teacher@test.bj",
            "username": "teacher",
            "role": "teacher",
            "first_name": "Test",
            "last_name": "Teacher",
            "password": "Pass1234!",
            "password2": "Pass1234!",
            "school": self.school.id,
        })
        self.assertEqual(resp.status_code, 201, resp.data)

    def test_admin_creates_in_own_school_always(self):
        """
        Un admin ne peut PAS rattacher un compte à un AUTRE établissement,
        même en passant l'ID de l'autre école dans le body.
        Le serializer doit forcer school=admin.school.
        """
        other_school = make_school("Other School")
        resp = self.client.post("/api/auth/users/", {
            "email": "teacher2@test.bj",
            "username": "teacher2",
            "role": "teacher",
            "password": "Pass1234!",
            "password2": "Pass1234!",
            "school": other_school.id,  # Tentative de créer dans une autre école
        })
        if resp.status_code == 201:
            # Le compte a été créé — vérifier qu'il est dans l'école de l'admin
            created_user = CustomUser.objects.get(email="teacher2@test.bj")
            self.assertEqual(
                created_user.school_id, self.school.id,
                "L'admin a créé un compte dans une autre école — IDOR tenant!"
            )


# ─────────────────────────────────────────────────────────────────────────────
# 3. Login JWT et validation tenant
# ─────────────────────────────────────────────────────────────────────────────

class LoginTest(TestCase):

    def setUp(self):
        self.school = make_school("Bonne École")
        self.client = APIClient()

    def test_login_success_returns_tokens(self):
        """Login réussi retourne access + refresh tokens."""
        user = make_user("ok@test.bj", "admin", self.school)
        resp = self.client.post("/api/auth/login/", {"email": "ok@test.bj", "password": "Pass1234!"})
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertIn("access", resp.data)
        self.assertIn("refresh", resp.data)

    def test_login_wrong_password_returns_400(self):
        make_user("wrong@test.bj", "admin", self.school)
        resp = self.client.post("/api/auth/login/", {"email": "wrong@test.bj", "password": "BadPassword!"})
        self.assertEqual(resp.status_code, 400)

    def test_login_suspended_school_blocked(self):
        """
        Un utilisateur d'un établissement suspendu (is_active=False) ne
        doit pas pouvoir se connecter — retour 400 avec message clair.
        """
        self.school.is_active = False
        self.school.save()
        make_user("suspended@test.bj", "admin", self.school)
        resp = self.client.post("/api/auth/login/", {"email": "suspended@test.bj", "password": "Pass1234!"})
        self.assertNotEqual(resp.status_code, 200, "Un compte d'école suspendue ne doit pas pouvoir se connecter")

    def test_login_inactive_account_blocked(self):
        """Un compte utilisateur inactif (is_active=False) ne peut pas se connecter."""
        user = make_user("inactive@test.bj", "admin", self.school)
        user.is_active = False
        user.save()
        resp = self.client.post("/api/auth/login/", {"email": "inactive@test.bj", "password": "Pass1234!"})
        self.assertNotEqual(resp.status_code, 200)

    def test_login_no_school_blocked(self):
        """Un utilisateur sans école (ni superadmin) ne peut pas se connecter."""
        user = make_user("noschool@test.bj", "admin", school=None)
        resp = self.client.post("/api/auth/login/", {"email": "noschool@test.bj", "password": "Pass1234!"})
        self.assertNotEqual(resp.status_code, 200, "Un compte sans école ne devrait pas pouvoir se connecter")

    def test_login_superadmin_without_school_succeeds(self):
        """Le rôle superadmin n'a pas besoin d'école pour se connecter."""
        make_user("super@test.bj", "superadmin", school=None)
        resp = self.client.post("/api/auth/login/", {"email": "super@test.bj", "password": "Pass1234!"})
        self.assertEqual(resp.status_code, 200, resp.data)

    def test_login_response_contains_school_claims(self):
        """Le JWT doit contenir school_id et school_slug pour le frontend."""
        import base64, json
        user = make_user("claims@test.bj", "admin", self.school)
        resp = self.client.post("/api/auth/login/", {"email": "claims@test.bj", "password": "Pass1234!"})
        self.assertEqual(resp.status_code, 200)
        token = resp.data["access"]
        payload_b64 = token.split(".")[1]
        # Padding
        payload_b64 += "=" * (4 - len(payload_b64) % 4)
        payload = json.loads(base64.b64decode(payload_b64))
        self.assertIn("school_id", payload, "JWT doit contenir school_id")
        self.assertIn("school_slug", payload, "JWT doit contenir school_slug")
        self.assertEqual(payload["school_id"], self.school.id)


# ─────────────────────────────────────────────────────────────────────────────
# 4. IDOR — Un admin ne peut pas voir les comptes d'un autre établissement
# ─────────────────────────────────────────────────────────────────────────────

class UserDetailIsorTest(TestCase):

    def setUp(self):
        self.school_a = make_school("École A")
        self.school_b = make_school("École B")
        self.admin_a = make_user("admin_a@test.bj", "admin", self.school_a)
        self.user_b = make_user("user_b@test.bj", "teacher", self.school_b)
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {get_token(self.client, 'admin_a@test.bj')}")

    def test_admin_cannot_retrieve_user_from_other_school(self):
        """IDOR guard : admin A ne peut pas lire le profil d'un user de l'école B."""
        resp = self.client.get(f"/api/auth/users/{self.user_b.id}/")
        self.assertIn(resp.status_code, [403, 404], "Admin A ne devrait pas voir user de l'école B")

    def test_admin_can_list_own_school_users_only(self):
        """La liste des utilisateurs ne doit retourner que ceux de l'école de l'admin."""
        resp = self.client.get("/api/auth/users/")
        self.assertEqual(resp.status_code, 200)
        ids = [u["id"] for u in resp.data.get("results", resp.data)]
        self.assertNotIn(self.user_b.id, ids, "user_b (école B) ne devrait pas apparaître dans la liste admin A")


# ─────────────────────────────────────────────────────────────────────────────
# 5. Changement de mot de passe
# ─────────────────────────────────────────────────────────────────────────────

class ChangePasswordTest(TestCase):

    def setUp(self):
        self.school = make_school()
        self.user = make_user("pwd@test.bj", "teacher", self.school)
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {get_token(self.client, 'pwd@test.bj')}")

    def test_change_password_success(self):
        resp = self.client.post("/api/auth/change-password/", {
            "old_password": "Pass1234!",
            "new_password": "NewPass5678!",
        })
        self.assertEqual(resp.status_code, 200, resp.data)
        # Re-login avec le nouveau mot de passe
        client2 = APIClient()
        resp2 = client2.post("/api/auth/login/", {"email": "pwd@test.bj", "password": "NewPass5678!"})
        self.assertEqual(resp2.status_code, 200)

    def test_wrong_old_password_returns_400(self):
        resp = self.client.post("/api/auth/change-password/", {
            "old_password": "WrongOldPass!",
            "new_password": "NewPass5678!",
        })
        self.assertEqual(resp.status_code, 400)
