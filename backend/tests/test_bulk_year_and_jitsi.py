"""
Tests — Suppression en masse par année, JWT Jitsi, présence virtuelle (FIX v35).

Causes racines couvertes (vidéos fournies) :
  1. bulk-remove-from-year : retirer 30 élèves depuis l'année A ne touche
     à AUCUNE autre année (le bug des vidéos : liste vidée partout).
  2. Jetons Jitsi signés par le backend quand l'instance auto-hébergée est
     configurée (payload conforme : iss/aud/room/context.user/moderator) ;
     pas de jeton en mode démo.
  3. La présence d'un élève à un cours virtuel est liée à son INSCRIPTION
     ANNUELLE ; leave/ enregistre sortie et durée.
"""
import datetime

from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from rest_framework import status

from apps.accounts.models import CustomUser
from apps.classes.models import Class
from apps.schools.models import School, SchoolYear, Level
from apps.students.models import Student, StudentEnrollment
from apps.virtualclass.models import VirtualRoom, VirtualRoomAttendance
from apps.virtualclass.services import build_jitsi_jwt


def auth(client, email, password="Pass1234!"):
    resp = client.post("/api/auth/login/", {"email": email, "password": password})
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {resp.data.get('access', '')}")


class BulkRemoveFromYearTests(TestCase):
    def setUp(self):
        self.school = School.objects.create(name="Ecole BR", address="X")
        self.y1 = SchoolYear.objects.create(
            school=self.school, name="2024-2025",
            start_date="2024-10-01", end_date="2025-07-31",
        )
        self.y2 = SchoolYear.objects.create(
            school=self.school, name="2025-2026", is_current=True,
            start_date="2025-10-01", end_date="2026-07-31",
        )
        lvl = Level.objects.create(school=self.school, name="CM1", order=4)
        self.c1 = Class.objects.create(name="CM1-A", level=lvl, school_year=self.y1)
        self.c2 = Class.objects.create(name="CM2-A", level=lvl, school_year=self.y2)
        self.admin = CustomUser.objects.create_user(
            username="badm", email="badm@test.bj", password="Pass1234!",
            role="admin", first_name="B", last_name="A", school=self.school,
        )
        self.students = []
        for i in range(3):
            s = Student.objects.create(
                school=self.school, first_name=f"S{i}", last_name="Bulk",
                current_class=self.c2, school_year=self.y2,
            )
            StudentEnrollment.objects.create(student=s, school_year=self.y1, class_obj=self.c1)
            StudentEnrollment.objects.create(student=s, school_year=self.y2, class_obj=self.c2)
            self.students.append(s)
        self.client = APIClient()
        auth(self.client, "badm@test.bj")

    def test_bulk_remove_only_touches_selected_year(self):
        """Scénario des vidéos : retirer tous les élèves de 2024-2025."""
        ids = [s.id for s in self.students]
        resp = self.client.post("/api/students/bulk-remove-from-year/",
                                {"ids": ids, "school_year_id": self.y1.id}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        self.assertEqual(resp.data["removed"], 3)
        for s in self.students:
            self.assertFalse(StudentEnrollment.objects.filter(student=s, school_year=self.y1).exists())
            # L'année 2025-2026 est STRICTEMENT intacte
            self.assertTrue(StudentEnrollment.objects.filter(student=s, school_year=self.y2).exists())
            s.refresh_from_db()
            self.assertTrue(s.is_active)                       # pas de désactivation
            self.assertEqual(s.school_year_id, self.y2.id)     # pointeur inchangé

    def test_bulk_remove_repoints_when_current_year_removed(self):
        ids = [self.students[0].id]
        resp = self.client.post("/api/students/bulk-remove-from-year/",
                                {"ids": ids, "school_year_id": self.y2.id}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        s = self.students[0]; s.refresh_from_db()
        self.assertEqual(s.school_year_id, self.y1.id)
        self.assertEqual(s.current_class_id, self.c1.id)


@override_settings(JITSI_APP_ID="feba", JITSI_APP_SECRET="s" * 32, JITSI_DOMAIN="meet.example.bj")
class JitsiJwtTests(TestCase):
    def setUp(self):
        # Salle virtuelle + JWT Jitsi = fonctionnalité des académies en
        # ligne (FEBA FHA). Une entité `campus` se voit refuser l'accès.
        self.school = School.objects.create(name="Ecole J", address="X", entity_type="online")
        self.year = SchoolYear.objects.create(
            school=self.school, name="2025-2026", is_current=True,
            start_date="2025-10-01", end_date="2026-07-31",
        )
        lvl = Level.objects.create(school=self.school, name="6e", order=6)
        self.cls = Class.objects.create(name="6e-A", level=lvl, school_year=self.year)
        self.teacher_u = CustomUser.objects.create_user(
            username="jt", email="jt@test.bj", password="Pass1234!",
            role="teacher", first_name="J", last_name="T", school=self.school,
        )
        self.student_u = CustomUser.objects.create_user(
            username="js", email="js@test.bj", password="Pass1234!",
            role="student", first_name="J", last_name="S", school=self.school,
        )
        self.student = Student.objects.create(
            user=self.student_u, school=self.school, first_name="J", last_name="S",
            current_class=self.cls, school_year=self.year,
        )
        self.enr = StudentEnrollment.objects.create(
            student=self.student, school_year=self.year, class_obj=self.cls,
        )
        self.room = VirtualRoom.objects.create(
            school=self.school, school_year=self.year, name="Cours 6e",
            class_obj=self.cls, created_by=self.teacher_u,
        )
        self.client = APIClient()

    def test_jwt_payload_conforms_to_jitsi_spec(self):
        import jwt as pyjwt
        token = build_jitsi_jwt(self.teacher_u, self.room.room_code, moderator=True)
        self.assertIsNotNone(token)
        payload = pyjwt.decode(token, "s" * 32, algorithms=["HS256"], audience="jitsi")
        self.assertEqual(payload["iss"], "feba")
        self.assertEqual(payload["room"], self.room.room_code)
        self.assertEqual(payload["sub"], "meet.example.bj")
        self.assertEqual(payload["context"]["user"]["moderator"], "true")

    def test_join_returns_jwt_and_links_attendance_to_enrollment(self):
        auth(self.client, "js@test.bj")
        resp = self.client.post(f"/api/virtual-rooms/{self.room.id}/join/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        self.assertTrue(resp.data.get("jwt"))
        att = VirtualRoomAttendance.objects.get(room=self.room, user=self.student_u)
        self.assertEqual(att.enrollment_id, self.enr.id)    # présence liée à l'inscription

        # leave/ enregistre sortie + durée
        resp2 = self.client.post(f"/api/virtual-rooms/{self.room.id}/leave/")
        self.assertEqual(resp2.status_code, status.HTTP_200_OK)
        att.refresh_from_db()
        self.assertIsNotNone(att.left_at)
        self.assertIsNotNone(att.duration_seconds)

    def test_missing_secret_raises_instead_of_falling_back(self):
        """
        V5 — CHANGEMENT DE CONTRAT VOLONTAIRE.

        L'ancienne version renvoyait None quand le secret manquait, et le
        client rejoignait alors meet.jit.si SANS jeton : une classe
        d'enfants basculait sur un serveur public non authentifié à cause
        d'une simple variable oubliée.

        Désormais une configuration incomplète LÈVE une exception, que la
        vue transforme en 503 explicite. Aucun repli public n'existe plus.
        """
        from apps.virtualclass.services import JitsiNotConfigured

        with override_settings(JITSI_APP_SECRET=""):
            with self.assertRaises(JitsiNotConfigured):
                build_jitsi_jwt(self.teacher_u, "room-x")

    def test_public_domain_is_rejected(self):
        """Un domaine public configuré par erreur doit être refusé."""
        from apps.virtualclass.services import JitsiNotConfigured

        for public in ("meet.jit.si", "8x8.vc"):
            with override_settings(JITSI_DOMAIN=public):
                with self.assertRaises(JitsiNotConfigured):
                    build_jitsi_jwt(self.teacher_u, "room-x")

    def test_jwt_carries_academy_and_group(self):
        """Le jeton porte l'académie et le groupe, et nomme la salle."""
        import jwt as pyjwt

        token = build_jitsi_jwt(
            self.teacher_u, "room-x", moderator=True,
            academy="FEBA_FHA", group="Junior Roots",
        )
        payload = pyjwt.decode(token, "s" * 32, algorithms=["HS256"], audience="jitsi")
        self.assertEqual(payload["room"], "room-x")
        self.assertEqual(payload["context"]["feba"]["academy"], "FEBA_FHA")
        self.assertEqual(payload["context"]["feba"]["group"], "Junior Roots")
        self.assertTrue(payload["moderator"])

    def test_jwt_lifetime_is_short(self):
        """Un jeton intercepté ne doit pas ouvrir un accès permanent."""
        import jwt as pyjwt

        token = build_jitsi_jwt(self.teacher_u, "room-x")
        payload = pyjwt.decode(token, "s" * 32, algorithms=["HS256"], audience="jitsi")
        self.assertLessEqual(payload["exp"] - payload["iat"], 3600)
