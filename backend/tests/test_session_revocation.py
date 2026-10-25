"""
Le renouvellement automatique de session (frontend) ne doit JAMAIS
empêcher une révocation légitime : compte désactivé, déconnexion,
jeton expiré. Ces tests fixent le comportement du SERVEUR, qui fait foi.
"""
from datetime import timedelta
from unittest import mock

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import CustomUser
from apps.schools.models import School


class RevocationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.school = School.objects.create(name="Révocation", address="x", code="REVOC")
        cls.user = CustomUser.objects.create_user(username="revoc", email="revoc@test.io", password="Pass1234!x",
                                                  role="teacher", school=cls.school)

    def login(self):
        r = APIClient().post("/api/auth/login/", {"email": "revoc@test.io", "password": "Pass1234!x"}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        return r.json()["access"], r.json()["refresh"]

    def me(self, access):
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
        return client.get("/api/auth/me/").status_code

    def refresh(self, token):
        return APIClient().post("/api/auth/refresh/", {"refresh": token}, format="json")

    def test_compte_desactive_acces_et_renouvellement_refuses(self):
        access, refresh = self.login()
        self.assertEqual(self.me(access), 200)
        CustomUser.objects.filter(pk=self.user.pk).update(is_active=False)
        self.assertEqual(self.me(access), 401)
        self.assertEqual(self.refresh(refresh).status_code, 401)

    def test_deconnexion_revoque_le_jeton_de_renouvellement(self):
        access, refresh = self.login()
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
        self.assertIn(client.post("/api/auth/logout/", {"refresh": refresh}, format="json").status_code, (200, 205))
        self.assertEqual(self.refresh(refresh).status_code, 401)

    def test_rotation_ancien_jeton_refuse_nouveau_accepte(self):
        _, refresh = self.login()
        r = self.refresh(refresh)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.refresh(refresh).status_code, 401)
        self.assertEqual(self.refresh(r.json()["refresh"]).status_code, 200)

    def test_jeton_de_renouvellement_expire_refuse(self):
        token = RefreshToken.for_user(self.user)
        token.set_exp(from_time=timezone.now() - timedelta(days=30), lifetime=timedelta(days=1))
        self.assertEqual(self.refresh(str(token)).status_code, 401)

    def test_jeton_d_acces_expire_refuse(self):
        access, _ = self.login()
        with mock.patch("rest_framework_simplejwt.tokens.aware_utcnow",
                        return_value=timezone.now() + timedelta(hours=3)):
            self.assertEqual(self.me(access), 401)
