"""
Tests bilinguisme backend :
 - persistance de la préférence de langue dans le profil (PATCH /auth/me/) ;
 - exposition de `preferred_language` dans /auth/me/ (restauration au login) ;
 - valeur par défaut « fr » ;
 - rejet d'une langue non supportée ;
 - la préférence d'un utilisateur ne fuit pas vers un autre.
"""
import pytest
from rest_framework.test import APIClient

from apps.accounts.models import CustomUser
from apps.schools.models import School

pytestmark = pytest.mark.django_db


@pytest.fixture
def school(db):
    return School.objects.create(name="FEBA Test", slug="feba-test")


@pytest.fixture
def user(school):
    u = CustomUser.objects.create_user(
        username="lang_user", email="lang_user@feba.test",
        password="Str0ngPass!42", first_name="Awa", last_name="Kone",
        role="teacher", school=school,
    )
    return u


@pytest.fixture
def client(user):
    c = APIClient()
    c.force_authenticate(user=user)
    return c


class TestPreferredLanguage:
    def test_default_is_french(self, user):
        assert user.preferred_language == "fr"

    def test_me_exposes_preferred_language(self, client):
        r = client.get("/api/auth/me/")
        assert r.status_code == 200
        assert r.data["preferred_language"] == "fr"

    def test_patch_me_persists_language(self, client, user):
        r = client.patch("/api/auth/me/", {"preferred_language": "en"}, format="json")
        assert r.status_code == 200
        assert r.data["preferred_language"] == "en"
        user.refresh_from_db()
        assert user.preferred_language == "en"

    def test_patch_me_rejects_unsupported_language(self, client, user):
        r = client.patch("/api/auth/me/", {"preferred_language": "de"}, format="json")
        assert r.status_code == 400
        user.refresh_from_db()
        assert user.preferred_language == "fr"

    def test_language_restored_after_relogin(self, user, school):
        """La préférence survit à une reconnexion : le nouveau /auth/me/ la renvoie."""
        user.preferred_language = "en"
        user.save()
        fresh = APIClient()
        login = fresh.post(
            "/api/auth/login/",
            {"email": "lang_user@feba.test", "password": "Str0ngPass!42"},
            format="json",
        )
        assert login.status_code == 200, login.content
        fresh.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        me = fresh.get("/api/auth/me/")
        assert me.status_code == 200
        assert me.data["preferred_language"] == "en"

    def test_preference_is_per_user(self, client, user, school):
        other = CustomUser.objects.create_user(
            username="other_lang", email="other_lang@feba.test",
            password="Str0ngPass!42", first_name="Bob", last_name="Doe",
            role="teacher", school=school,
        )
        client.patch("/api/auth/me/", {"preferred_language": "en"}, format="json")
        other.refresh_from_db()
        assert other.preferred_language == "fr"

    def test_patch_me_cannot_change_role(self, client, user):
        """Le PATCH /auth/me/ ignore les champs non autorisés (role, école)."""
        r = client.patch(
            "/api/auth/me/",
            {"preferred_language": "en", "role": "admin", "is_active": False},
            format="json",
        )
        assert r.status_code == 200
        user.refresh_from_db()
        assert user.role == "teacher"
        assert user.is_active is True
        assert user.preferred_language == "en"
