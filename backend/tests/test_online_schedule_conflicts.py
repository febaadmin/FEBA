"""
tests/test_online_schedule_conflicts.py — Régression P2 (juillet 2026).

BUG RÉSOLU
----------
`ClassScheduleSerializer` (FEBA) empêchait déjà trois conflits : classe,
enseignant, salle. `OnlineSessionScheduleSerializer` (FEBA FHA) n'en
empêchait qu'UN SEUL — l'enseignant. Un groupe pouvait donc se voir
planifier deux séances qui se chevauchent, et une salle virtuelle être
réservée deux fois en même temps : exactement le « CRUD partiel »
signalé pour FEBA FHA, mais au niveau des règles métier plutôt que de
l'écran.

Ces tests verrouillent la PARITÉ : les mêmes catégories de conflit sont
désormais détectées des deux côtés.
"""
import datetime

from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import CustomUser
from apps.classes.models import Class
from apps.schools.models import Level, School, SchoolYear
from apps.subjects.models import Subject
from apps.teachers.models import Teacher
from apps.virtualclass.models import VirtualRoom


def auth(client, email, password="Pass1234!"):
    resp = client.post("/api/auth/login/", {"email": email, "password": password})
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {resp.data.get('access', '')}")
    return client


class OnlineScheduleConflictTests(TestCase):
    """FEBA FHA : mêmes catégories de conflit que FEBA — groupe, enseignant, salle."""

    @classmethod
    def setUpTestData(cls):
        cls.fha = School.objects.create(
            name="FEBA French Heritage Academy", address="En ligne",
            entity_type="online", code="CONF-FHA",
        )
        cls.year = SchoolYear.objects.create(
            school=cls.fha, name="2025-2026", is_current=True,
            start_date="2025-09-01", end_date="2026-07-01",
        )
        cls.level = Level.objects.create(school=cls.fha, name="En ligne", order=1)
        cls.group_a = Class.objects.create(school_year=cls.year, level=cls.level, name="Junior Roots")
        cls.group_b = Class.objects.create(school_year=cls.year, level=cls.level, name="French Explorers")
        cls.subject = Subject.objects.create(school=cls.fha, name="Français", code="FR")

        cls.teacher_1_user = CustomUser.objects.create_user(
            username="conf_teacher_1", email="conf.teacher.1@test.io",
            password="Pass1234!", role="teacher", school=cls.fha,
            first_name="Prof", last_name="Un",
        )
        cls.teacher_1 = Teacher.objects.create(user=cls.teacher_1_user)
        cls.teacher_2_user = CustomUser.objects.create_user(
            username="conf_teacher_2", email="conf.teacher.2@test.io",
            password="Pass1234!", role="teacher", school=cls.fha,
            first_name="Prof", last_name="Deux",
        )
        cls.teacher_2 = Teacher.objects.create(user=cls.teacher_2_user)

        cls.room_1 = VirtualRoom.objects.create(school=cls.fha, name="Salle 1")
        cls.room_2 = VirtualRoom.objects.create(school=cls.fha, name="Salle 2")

        cls.admin = CustomUser.objects.create_user(
            username="conf_admin_fha", email="conf.admin.fha@test.io",
            password="Pass1234!", role="admin", school=cls.fha,
            first_name="Admin", last_name="FHA",
        )

    def setUp(self):
        self.client_admin = auth(APIClient(), "conf.admin.fha@test.io")

    def _payload(self, **overrides):
        payload = {
            "group": self.group_a.id, "subject": self.subject.id,
            "teacher": self.teacher_1.id, "school_year": self.year.id,
            "virtual_room": self.room_1.id,
            "day_of_week": 1, "start_time_utc": "17:00:00",
            "duration_minutes": 60, "display_timezone": "America/New_York",
        }
        payload.update(overrides)
        return payload

    def test_meme_groupe_meme_creneau_est_refuse(self):
        """
        PARITÉ AVEC FEBA : équivalent du conflit de CLASSE.

        Chevauchement partiel (17h00–18h00 puis 17h30–18h30), volontairement
        PAS le même horaire exact — la contrainte d'unicité du modèle
        bloque déjà les doublons exacts ; ce test vérifie la détection de
        CHEVAUCHEMENT ajoutée par ce correctif, un cas qu'elle ne couvre pas.
        """
        first = self.client_admin.post("/api/schedule/online-sessions/", self._payload(), format="json")
        self.assertEqual(first.status_code, 201, first.data)

        clash = self.client_admin.post(
            "/api/schedule/online-sessions/",
            self._payload(teacher=self.teacher_2.id, virtual_room=self.room_2.id,
                          start_time_utc="17:30:00"),
            format="json",
        )
        self.assertEqual(clash.status_code, 400)
        self.assertIn("groupe", str(clash.data).lower())

    def test_meme_enseignant_meme_creneau_est_refuse(self):
        first = self.client_admin.post("/api/schedule/online-sessions/", self._payload(), format="json")
        self.assertEqual(first.status_code, 201, first.data)

        clash = self.client_admin.post(
            "/api/schedule/online-sessions/",
            self._payload(group=self.group_b.id, virtual_room=self.room_2.id),
            format="json",
        )
        self.assertEqual(clash.status_code, 400)
        self.assertIn("enseignant", str(clash.data).lower())

    def test_meme_salle_virtuelle_meme_creneau_est_refusee(self):
        """PARITÉ AVEC FEBA : équivalent du conflit de SALLE."""
        first = self.client_admin.post("/api/schedule/online-sessions/", self._payload(), format="json")
        self.assertEqual(first.status_code, 201, first.data)

        clash = self.client_admin.post(
            "/api/schedule/online-sessions/",
            self._payload(group=self.group_b.id, teacher=self.teacher_2.id),
            format="json",
        )
        self.assertEqual(clash.status_code, 400)
        self.assertIn("salle virtuelle", str(clash.data).lower())

    def test_creneaux_qui_ne_se_chevauchent_pas_sont_acceptes(self):
        first = self.client_admin.post("/api/schedule/online-sessions/", self._payload(), format="json")
        self.assertEqual(first.status_code, 201, first.data)

        later = self.client_admin.post(
            "/api/schedule/online-sessions/", self._payload(start_time_utc="18:00:00"), format="json",
        )
        self.assertEqual(later.status_code, 201, later.data)

    def test_jour_different_meme_heure_est_accepte(self):
        first = self.client_admin.post("/api/schedule/online-sessions/", self._payload(day_of_week=1), format="json")
        self.assertEqual(first.status_code, 201, first.data)

        other_day = self.client_admin.post(
            "/api/schedule/online-sessions/", self._payload(day_of_week=2), format="json",
        )
        self.assertEqual(other_day.status_code, 201, other_day.data)

    def test_modifier_une_seance_sans_la_comparer_a_elle_meme(self):
        """Éditer une séance ne doit pas se signaler comme son propre conflit."""
        created = self.client_admin.post("/api/schedule/online-sessions/", self._payload(), format="json")
        self.assertEqual(created.status_code, 201, created.data)
        session_id = created.data["id"]

        patched = self.client_admin.patch(
            f"/api/schedule/online-sessions/{session_id}/",
            {"duration_minutes": 90}, format="json",
        )
        self.assertEqual(patched.status_code, 200, patched.data)

    def test_seance_inactive_ne_bloque_pas_un_nouveau_creneau(self):
        """
        Une fois désactivée, une séance ne compte plus comme un conflit
        pour un chevauchement PARTIEL — le doublon EXACT reste, lui,
        bloqué par la contrainte d'unicité du modèle (comportement déjà
        en place, non modifié par ce correctif).
        """
        created = self.client_admin.post("/api/schedule/online-sessions/", self._payload(), format="json")
        self.assertEqual(created.status_code, 201, created.data)
        session_id = created.data["id"]
        self.client_admin.patch(
            f"/api/schedule/online-sessions/{session_id}/", {"is_active": False}, format="json")

        replacement = self.client_admin.post(
            "/api/schedule/online-sessions/", self._payload(start_time_utc="17:30:00"), format="json")
        self.assertEqual(replacement.status_code, 201, replacement.data)
