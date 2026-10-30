"""
Fenêtre d'accès des cours planifiés (services.assert_within_schedule).

Élèves et parents : de VIRTUAL_ROOM_EARLY_JOIN_MINUTES avant le début à
VIRTUAL_ROOM_LATE_JOIN_MINUTES après la fin prévue, sauf réunion déjà
ouverte par un modérateur. Modérateurs et salles permanentes : sans limite.
"""
from datetime import datetime, timedelta, timezone as dt_tz

from django.test import TestCase, override_settings
from rest_framework import status
from rest_framework.test import APIClient

from apps.classes.models import Class
from apps.schools.models import Level, SchoolYear
from apps.students.models import Student
from apps.virtualclass.models import VirtualRoom
from apps.virtualclass.services import JoinOutsideSchedule, assert_within_schedule
from tests.test_virtualclass import auth, make_school, make_user

DEBUT = datetime(2026, 11, 2, 14, 0, tzinfo=dt_tz.utc)   # 09:00 à New York (EST)


@override_settings(VIRTUAL_ROOM_EARLY_JOIN_MINUTES=15, VIRTUAL_ROOM_LATE_JOIN_MINUTES=15)
class FenetreServiceTests(TestCase):
    def setUp(self):
        self.school = make_school()
        self.school.timezone = "America/New_York"
        self.school.save(update_fields=["timezone"])
        self.room = VirtualRoom.objects.create(
            school=self.school, name="Cours", scheduled_at=DEBUT, duration_minutes=60,
        )

    def eleve(self, now):
        return assert_within_schedule(self.room, moderator=False, now=now)

    def code(self, now):
        with self.assertRaises(JoinOutsideSchedule) as ctx:
            self.eleve(now)
        return ctx.exception.code

    def test_limites_de_la_fenetre(self):
        self.assertEqual(self.code(DEBUT - timedelta(minutes=15, seconds=1)), "too_early")
        self.assertTrue(self.eleve(DEBUT - timedelta(minutes=15)))
        self.assertTrue(self.eleve(DEBUT + timedelta(minutes=30)))
        self.assertTrue(self.eleve(DEBUT + timedelta(minutes=75)))      # fin + 15 min
        self.assertEqual(self.code(DEBUT + timedelta(minutes=75, seconds=1)), "too_late")

    def test_le_message_donne_l_heure_locale_de_l_academie(self):
        with self.assertRaises(JoinOutsideSchedule) as ctx:
            self.eleve(DEBUT - timedelta(days=1))
        self.assertIn("02/11/2026 à 09:00 (America/New_York)", str(ctx.exception))

    def test_le_moderateur_entre_a_tout_moment(self):
        for now in (DEBUT - timedelta(days=2), DEBUT + timedelta(days=2)):
            self.assertTrue(assert_within_schedule(self.room, moderator=True, now=now))

    def test_reunion_ouverte_par_un_moderateur(self):
        # Cours commencé en avance, ou qui déborde : l'élève peut entrer.
        self.room.status = "live"
        self.assertTrue(self.eleve(DEBUT - timedelta(hours=1)))
        self.assertTrue(self.eleve(DEBUT + timedelta(hours=3)))

    def test_salle_permanente_sans_fenetre(self):
        self.room.scheduled_at = None
        self.assertTrue(self.eleve(DEBUT + timedelta(days=30)))

    @override_settings(VIRTUAL_ROOM_EARLY_JOIN_MINUTES=0, VIRTUAL_ROOM_LATE_JOIN_MINUTES=0)
    def test_reglable(self):
        self.assertEqual(self.code(DEBUT - timedelta(minutes=1)), "too_early")
        self.assertEqual(self.code(DEBUT + timedelta(minutes=61)), "too_late")


class FenetreApiTests(TestCase):
    """Le refus passe par /join/ : 403 avec un code exploitable par l'interface."""

    def setUp(self):
        self.school = make_school()
        year = SchoolYear.objects.create(school=self.school, name="2026-2027",
                                         start_date="2026-09-01", end_date="2027-06-30", is_current=True)
        level = Level.objects.create(school=self.school, name="CM1", order=1, cycle="primaire")
        self.cls = Class.objects.create(name="CM1 A", level=level, school_year=year)
        self.eleve = make_user("eleve-fenetre@test.bj", "student", self.school)
        Student.objects.create(user=self.eleve, school=self.school, first_name="A", last_name="B",
                               current_class=self.cls)
        self.client = APIClient()

    def salle(self, debut):
        return VirtualRoom.objects.create(school=self.school, name="Cours", class_obj=self.cls,
                                          scheduled_at=debut, duration_minutes=60)

    def test_eleve_trop_tot_puis_trop_tard(self):
        from django.utils import timezone
        auth(self.client, "eleve-fenetre@test.bj")
        for debut, code in ((timezone.now() + timedelta(days=1), "too_early"),
                            (timezone.now() - timedelta(days=1), "too_late")):
            resp = self.client.post(f"/api/virtual-rooms/{self.salle(debut).id}/join/")
            self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN, code)
            self.assertEqual(resp.data["code"], code)


class ParentAccesTests(TestCase):
    """
    Parents : FEBA leur ouvre les salles de la classe de leurs enfants, comme
    simples participants (rôle < 50), avec la même fenêtre horaire qu'un élève.
    """

    def setUp(self):
        from django.utils import timezone

        from apps.parents.models import Parent, ParentStudent
        self.school = make_school()
        year = SchoolYear.objects.create(school=self.school, name="2026-2027",
                                         start_date="2026-09-01", end_date="2027-06-30", is_current=True)
        level = Level.objects.create(school=self.school, name="CM2", order=2, cycle="primaire")
        self.cls = Class.objects.create(name="CM2 A", level=level, school_year=year)
        self.autre = Class.objects.create(name="CM2 B", level=level, school_year=year)
        enfant = Student.objects.create(user=make_user("enfant@test.bj", "student", self.school),
                                        school=self.school, first_name="E", last_name="F",
                                        current_class=self.cls)
        self.parent_user = make_user("parent@test.bj", "parent", self.school)
        ParentStudent.objects.create(parent=Parent.objects.create(user=self.parent_user),
                                     student=enfant, relationship="mother")
        maintenant = timezone.now()
        self.salle = VirtualRoom.objects.create(school=self.school, name="Cours CM2 A", class_obj=self.cls,
                                                scheduled_at=maintenant, duration_minutes=60)
        self.salle_autre = VirtualRoom.objects.create(school=self.school, name="Cours CM2 B",
                                                      class_obj=self.autre, scheduled_at=maintenant)
        self.client = APIClient()
        auth(self.client, "parent@test.bj")

    def test_le_parent_voit_la_salle_de_son_enfant_seulement(self):
        resp = self.client.get("/api/virtual-rooms/")
        noms = {r["name"] for r in resp.data.get("results", resp.data)}
        self.assertIn("Cours CM2 A", noms)
        self.assertNotIn("Cours CM2 B", noms)

    def test_le_parent_entre_comme_participant_dans_la_salle_de_son_enfant(self):
        from apps.virtualclass.services import assert_can_join
        self.assertTrue(assert_can_join(self.parent_user, self.salle))
        self.assertLess(self.parent_user.role_level, 50)   # jamais modérateur
        self.assertTrue(assert_within_schedule(self.salle, moderator=False))

    def test_le_parent_est_refuse_ailleurs(self):
        resp = self.client.post(f"/api/virtual-rooms/{self.salle_autre.id}/join/")
        self.assertIn(resp.status_code, (status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND))
