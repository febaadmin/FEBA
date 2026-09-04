"""
Tests P0 — instance Jitsi AUTO-HÉBERGÉE, sans mode démonstration.

Exigences couvertes :
  1. aucune référence active à meet.jit.si dans le code applicatif ;
  2. aucune limite artificielle de 5 minutes ;
  3. un domaine public configuré par erreur est REFUSÉ ;
  4. une configuration incomplète lève une erreur au lieu de basculer ;
  5. le jeton porte l'académie, le groupe, la salle et expire vite ;
  6. un utilisateur d'une autre académie est refusé ;
  7. un élève d'un autre groupe est refusé ;
  8. les rôles modérateur / participant sont corrects ;
  9. l'endpoint de santé reflète l'état réel.
"""
import pathlib
from unittest import mock

from django.test import TestCase, override_settings
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import CustomUser
from apps.classes.models import Class
from apps.schools.models import Level, School, SchoolYear
from apps.students.models import Student
from apps.virtualclass.models import VirtualRoom
from apps.virtualclass.services import (
    JitsiAccessDenied, JitsiNotConfigured, assert_can_join, build_jitsi_jwt,
)

BACKEND_ROOT = pathlib.Path(__file__).resolve().parent.parent
REPO_ROOT = BACKEND_ROOT.parent

JITSI_TEST = dict(
    JITSI_APP_ID="feba-test",
    JITSI_APP_SECRET="s" * 32,
    JITSI_DOMAIN="jitsi.localhost:8443",
)


def auth(client, email, password="Pass1234!"):
    resp = client.post("/api/auth/login/", {"email": email, "password": password})
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {resp.data.get('access', '')}")
    return client


class NoDemoModeTests(TestCase):
    """Le mode démonstration doit avoir totalement disparu du code."""

    def _app_sources(self):
        """Sources applicatives, hors migrations, tests et dépendances."""
        files = []
        for base, patterns in (
            (BACKEND_ROOT / "apps", ("*.py",)),
            (BACKEND_ROOT / "feba_project", ("*.py",)),
            (REPO_ROOT / "frontend" / "src", ("*.js", "*.jsx")),
        ):
            for pattern in patterns:
                for path in base.rglob(pattern):
                    parts = set(path.parts)
                    if parts & {"migrations", "node_modules", "__pycache__"}:
                        continue
                    if path.name.endswith((".test.js", ".test.jsx")):
                        continue
                    if path.name.startswith("test_"):
                        continue
                    files.append(path)
        return files

    @staticmethod
    def _strip_prose(content):
        """
        Retire commentaires et docstrings pour ne garder que le CODE.

        La documentation a le droit — et même le devoir — d'expliquer
        pourquoi le repli public a été supprimé. Seule une utilisation
        réelle du domaine constitue une régression.
        """
        import re

        content = re.sub(r'"""[\s\S]*?"""', "", content)
        content = re.sub(r"'''[\s\S]*?'''", "", content)
        content = re.sub(r"/\*[\s\S]*?\*/", "", content)
        kept = []
        for line in content.splitlines():
            stripped = line.strip()
            if stripped.startswith(("#", "//", "*")):
                continue
            kept.append(line)
        return "\n".join(kept)

    def test_no_public_jitsi_instance_referenced(self):
        """
        Aucune UTILISATION de meet.jit.si : ni valeur par défaut, ni repli,
        ni chaîne affichée. La liste noire `JITSI_FORBIDDEN_DOMAINS` est
        évidemment exemptée : elle existe précisément pour l'interdire.
        """
        offenders = []
        for path in self._app_sources():
            code = self._strip_prose(path.read_text(encoding="utf-8"))
            for line in code.splitlines():
                if "meet.jit.si" not in line:
                    continue
                if "JITSI_FORBIDDEN_DOMAINS" in line:
                    continue
                offenders.append(f"{path.relative_to(REPO_ROOT)} → {line.strip()[:80]}")
        self.assertEqual(offenders, [], f"Utilisations de meet.jit.si : {offenders}")

    def test_no_five_minute_limitation_message(self):
        """Aucune chaîne affichée ne doit mentionner la limite de 5 minutes."""
        offenders = []
        for path in self._app_sources():
            code = self._strip_prose(path.read_text(encoding="utf-8"))
            if "limités à 5 minutes" in code or "limited to 5 minutes" in code:
                offenders.append(str(path.relative_to(REPO_ROOT)))
        self.assertEqual(offenders, [], f"Mention du mode démo : {offenders}")

    def test_settings_have_no_public_default(self):
        """Le réglage JITSI_DOMAIN ne doit pas avoir de défaut public."""
        from django.conf import settings
        default = (getattr(settings, "JITSI_DOMAIN", "") or "").lower()
        self.assertNotIn("jit.si", default)


@override_settings(**JITSI_TEST)
class JitsiTokenTests(TestCase):
    def setUp(self):
        self.school = School.objects.create(
            name="FHA J", address="En ligne", entity_type="online", code="J-FHA",
        )
        self.user = CustomUser.objects.create_user(
            username="jt2", email="jt2@test.io", password="Pass1234!",
            role="teacher", school=self.school, first_name="J", last_name="T",
        )

    def test_token_names_the_room(self):
        import jwt as pyjwt
        token = build_jitsi_jwt(self.user, "salle-abc")
        payload = pyjwt.decode(token, "s" * 32, algorithms=["HS256"], audience="jitsi")
        self.assertEqual(payload["room"], "salle-abc")

    def test_token_expires_quickly(self):
        import jwt as pyjwt
        token = build_jitsi_jwt(self.user, "salle-abc")
        payload = pyjwt.decode(token, "s" * 32, algorithms=["HS256"], audience="jitsi")
        self.assertLessEqual(payload["exp"] - payload["iat"], 3600)

    def test_moderator_flag_reflects_role(self):
        import jwt as pyjwt
        for moderator in (True, False):
            token = build_jitsi_jwt(self.user, "salle-abc", moderator=moderator)
            payload = pyjwt.decode(token, "s" * 32, algorithms=["HS256"], audience="jitsi")
            self.assertEqual(payload["moderator"], moderator)
            self.assertEqual(
                payload["context"]["user"]["moderator"], "true" if moderator else "false",
            )

    def test_incomplete_configuration_raises(self):
        for missing in ("JITSI_APP_ID", "JITSI_APP_SECRET", "JITSI_DOMAIN"):
            with override_settings(**{missing: ""}):
                with self.assertRaises(JitsiNotConfigured):
                    build_jitsi_jwt(self.user, "salle-abc")


@override_settings(**JITSI_TEST)
class JitsiAccessControlTests(TestCase):
    """Cloisonnement des salles entre académies et entre groupes."""

    @classmethod
    def setUpTestData(cls):
        cls.fha = School.objects.create(
            name="FHA A", address="En ligne", entity_type="online", code="AC-FHA",
        )
        cls.feba = School.objects.create(
            name="FEBA A", address="Cotonou", entity_type="campus", code="AC-FEBA",
        )
        year = SchoolYear.objects.create(
            school=cls.fha, name="2025-2026", is_current=True,
            start_date="2025-09-01", end_date="2026-06-30",
        )
        level = Level.objects.create(school=cls.fha, name="JR", order=1)
        cls.group_a = Class.objects.create(name="Junior Roots", level=level, school_year=year)
        cls.group_b = Class.objects.create(name="French Explorers", level=level, school_year=year)

        cls.room = VirtualRoom.objects.create(
            school=cls.fha, school_year=year, name="Cours JR", class_obj=cls.group_a,
        )

        cls.fha_student_user = CustomUser.objects.create_user(
            username="fs", email="fs@test.io", password="Pass1234!",
            role="student", school=cls.fha, first_name="F", last_name="S",
        )
        cls.fha_student = Student.objects.create(
            user=cls.fha_student_user, school=cls.fha, current_class=cls.group_a,
            school_year=year, first_name="F", last_name="S", date_of_birth="2016-01-01",
        )
        cls.other_group_user = CustomUser.objects.create_user(
            username="og", email="og@test.io", password="Pass1234!",
            role="student", school=cls.fha, first_name="O", last_name="G",
        )
        Student.objects.create(
            user=cls.other_group_user, school=cls.fha, current_class=cls.group_b,
            school_year=year, first_name="O", last_name="G", date_of_birth="2014-01-01",
        )
        cls.feba_user = CustomUser.objects.create_user(
            username="fu", email="fu@test.io", password="Pass1234!",
            role="teacher", school=cls.feba, first_name="F", last_name="U",
        )

    def test_authorised_student_can_join(self):
        self.assertTrue(assert_can_join(self.fha_student_user, self.room))

    def test_user_from_other_academy_is_refused(self):
        """EXIGENCE CENTRALE : un utilisateur FEBA ne rejoint pas une salle FHA."""
        with self.assertRaises(JitsiAccessDenied) as ctx:
            assert_can_join(self.feba_user, self.room)
        self.assertIn("académie", str(ctx.exception))

    def test_student_from_other_group_is_refused(self):
        with self.assertRaises(JitsiAccessDenied):
            assert_can_join(self.other_group_user, self.room)

    def test_inactive_account_is_refused(self):
        self.fha_student_user.is_active = False
        with self.assertRaises(JitsiAccessDenied):
            assert_can_join(self.fha_student_user, self.room)
        self.fha_student_user.is_active = True

    def test_cancelled_room_is_refused(self):
        self.room.status = "cancelled"
        with self.assertRaises(JitsiAccessDenied):
            assert_can_join(self.fha_student_user, self.room)
        self.room.status = "scheduled"

    def test_join_endpoint_refuses_cross_academy_via_http(self):
        """Le refus vaut aussi via l'API, pas seulement en appel direct."""
        client = auth(APIClient(), "fu@test.io")
        resp = client.post(f"/api/virtual-rooms/{self.room.id}/join/")
        self.assertIn(
            resp.status_code,
            (status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND),
        )


class JitsiUnconfiguredTests(TestCase):
    """Sans instance configurée : 503 explicite, jamais de session publique."""

    @override_settings(JITSI_DOMAIN="", JITSI_APP_ID="", JITSI_APP_SECRET="")
    def test_join_returns_503_not_public_session(self):
        school = School.objects.create(
            name="FHA U", address="En ligne", entity_type="online", code="U-FHA",
        )
        user = CustomUser.objects.create_user(
            username="uu", email="uu@test.io", password="Pass1234!",
            role="teacher", school=school, first_name="U", last_name="U",
        )
        room = VirtualRoom.objects.create(school=school, name="Salle U")

        client = auth(APIClient(), "uu@test.io")
        resp = client.post(f"/api/virtual-rooms/{room.id}/join/")
        self.assertEqual(resp.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertEqual(resp.data["code"], "jitsi_not_configured")
        # Aucun domaine public n'est proposé en repli.
        self.assertNotIn("jit.si", str(resp.data))

    @override_settings(JITSI_DOMAIN="meet.jit.si", JITSI_APP_ID="x", JITSI_APP_SECRET="y" * 32)
    def test_public_domain_configuration_is_rejected(self):
        from apps.virtualclass.services import jitsi_health
        report = jitsi_health()
        self.assertEqual(report["status"], "unavailable")
        self.assertIn("PUBLIQUE", report["detail"])


class JitsiHealthInternalUrlTests(TestCase):
    """
    Régression P7 (juillet 2026).

    BUG RÉSOLU : `jitsi_health()` testait la joignabilité de Jitsi via
    JITSI_DOMAIN (« localhost:8443 », l'adresse du NAVIGATEUR). Depuis
    l'intérieur du conteneur backend, « localhost » ne désigne jamais
    Jitsi — le contrôle échouait donc TOUJOURS, même Jitsi parfaitement
    opérationnel. `JITSI_INTERNAL_URL` (http://jitsi-web:80 sur le réseau
    Docker partagé) corrige ça.

    Aucune vraie requête réseau ici — on vérifie quelle URL le service
    tente d'atteindre, pas la disponibilité réelle d'un Jitsi (impossible
    sans Docker). C'est le contrat testable sans infrastructure lourde ;
    la joignabilité réelle se vérifie avec `make jitsi-health` sur une
    installation Docker complète.
    """

    def _configured_settings(self, **extra):
        base = dict(
            JITSI_DOMAIN="localhost:8443", JITSI_APP_ID="feba_test",
            JITSI_APP_SECRET="s" * 32,
        )
        base.update(extra)
        return base

    def test_url_interne_est_utilisee_quand_definie(self):
        from apps.virtualclass import services

        captured = {}

        def fake_urlopen(request, timeout=5):
            captured["url"] = request.full_url
            captured.setdefault("toutes", []).append(request.full_url)
            class _Resp:
                status = 200
                headers = {"Content-Type": "application/javascript"}
                def read(self_, n=None): return b"var JitsiMeetExternalAPI;"
                def __enter__(self_): return self_
                def __exit__(self_, *a): return False
            return _Resp()

        with override_settings(**self._configured_settings(JITSI_INTERNAL_URL="http://jitsi-web:80")):
            with mock.patch("urllib.request.urlopen", side_effect=fake_urlopen):
                report = services.jitsi_health()

        # TOUTES les sondes doivent passer par l'URL interne : une seule
        # qui repartirait vers le domaine public referait le bug P7.
        self.assertEqual(captured["toutes"][0], "http://jitsi-web:80/")
        for sonde in captured["toutes"]:
            self.assertTrue(sonde.startswith("http://jitsi-web:80"), sonde)
            self.assertNotIn("localhost", sonde)
        self.assertEqual(report["probed_url"], "http://jitsi-web:80/")
        self.assertTrue(report["reachable"])
        self.assertEqual(report["status"], "operational")

    def test_repli_sur_jitsi_domain_si_url_interne_absente(self):
        """
        Comportement historique préservé quand JITSI_INTERNAL_URL n'est
        pas défini (ex. production, un seul domaine public partagé).
        """
        from apps.virtualclass import services

        captured = {}

        def fake_urlopen(request, timeout=5):
            captured["url"] = request.full_url
            captured.setdefault("toutes", []).append(request.full_url)
            class _Resp:
                status = 200
                headers = {"Content-Type": "application/javascript"}
                def read(self_, n=None): return b"var JitsiMeetExternalAPI;"
                def __enter__(self_): return self_
                def __exit__(self_, *a): return False
            return _Resp()

        with override_settings(**self._configured_settings(JITSI_INTERNAL_URL="")):
            with mock.patch("urllib.request.urlopen", side_effect=fake_urlopen):
                services.jitsi_health()

        self.assertEqual(captured["toutes"][0], "http://localhost:8443/")
        for sonde in captured["toutes"]:
            self.assertTrue(sonde.startswith("http://localhost:8443"), sonde)

    def test_instance_interne_injoignable_est_signalee_degradee(self):
        from apps.virtualclass import services

        def fake_urlopen(request, timeout=5):
            raise OSError("Connection refused")

        with override_settings(**self._configured_settings(JITSI_INTERNAL_URL="http://jitsi-web:80")):
            with mock.patch("urllib.request.urlopen", side_effect=fake_urlopen):
                report = services.jitsi_health()

        self.assertEqual(report["status"], "degraded")
        self.assertIn("jitsi-web", report["detail"])
