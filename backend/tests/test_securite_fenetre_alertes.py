"""Fenêtre des séances hebdomadaires, comptes de démonstration, profils, surveillance."""
import datetime
import types
from io import StringIO
from unittest import mock

from django.core.management import CommandError, call_command
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.accounts.models import CustomUser
from apps.accounts.serializers import UserSerializer
from apps.classes.models import Class
from apps.incidents.models import TechnicalIncident
from apps.incidents import tasks
from apps.schedule.models import OnlineSessionSchedule
from apps.schools.models import Level, School, SchoolYear
from apps.subjects.models import Subject
from apps.teachers.models import Teacher
from apps.virtualclass.models import VirtualRoom
from apps.virtualclass.services import JoinOutsideSchedule, assert_within_schedule

UTC = datetime.timezone.utc
LUNDI_17H = datetime.datetime(2026, 11, 2, 17, 0, tzinfo=UTC)


@override_settings(VIRTUAL_ROOM_EARLY_JOIN_MINUTES=15, VIRTUAL_ROOM_LATE_JOIN_MINUTES=15)
class SeanceHebdomadaireTests(TestCase):
    def setUp(self):
        self.school = School.objects.create(name="FHA", address="x", entity_type="online",
                                            timezone="America/New_York")
        year = SchoolYear.objects.create(school=self.school, name="2026", start_date="2026-09-01",
                                         end_date="2027-06-30", is_current=True)
        level = Level.objects.create(school=self.school, name="N", order=1, cycle="primaire")
        cls = Class.objects.create(name="G", level=level, school_year=year)
        subject = Subject.objects.create(school=self.school, name="Fr", code="FR", coefficient=1)
        # Première date passée depuis longtemps : ne doit plus rien décider.
        self.room = VirtualRoom.objects.create(school=self.school, name="R", class_obj=cls,
                                               scheduled_at=LUNDI_17H - datetime.timedelta(days=60))
        self.seance = OnlineSessionSchedule(academy=self.school, group=cls, subject=subject, school_year=year,
                                            day_of_week=0, start_time_utc=datetime.time(17, 0),
                                            duration_minutes=60, virtual_room=self.room)
        self.seance.save()

    def eleve(self, now):
        return assert_within_schedule(self.room, moderator=False, now=now)

    def test_reproduction_eleve_a_l_heure_de_la_seance_accepte(self):
        for semaine in (0, 1, 5):
            base = LUNDI_17H + datetime.timedelta(weeks=semaine)
            for ecart in (-15, 0, 30, 75):
                self.assertTrue(self.eleve(base + datetime.timedelta(minutes=ecart)))

    def test_hors_de_la_seance_refuse_avec_la_prochaine_heure_locale(self):
        with self.assertRaises(JoinOutsideSchedule) as ctx:
            self.eleve(LUNDI_17H + datetime.timedelta(days=2))
        self.assertEqual(ctx.exception.code, "too_early")
        self.assertIn("09/11/2026 à 12:00 (America/New_York)", str(ctx.exception))

    def test_seance_a_cheval_sur_la_fin_de_semaine(self):
        self.seance.day_of_week = 6
        self.seance.start_time_utc = datetime.time(23, 30)
        self.seance.save()
        self.assertTrue(self.eleve(datetime.datetime(2026, 11, 2, 0, 10, tzinfo=UTC)))

    def test_seance_inactive_retombe_sur_la_date_de_la_salle(self):
        self.seance.is_active = False
        self.seance.save()
        with self.assertRaises(JoinOutsideSchedule) as ctx:
            self.eleve(LUNDI_17H)
        self.assertEqual(ctx.exception.code, "too_late")

    def test_moderateur_et_reunion_ouverte(self):
        now = LUNDI_17H + datetime.timedelta(days=2)
        self.assertTrue(assert_within_schedule(self.room, moderator=True, now=now))
        self.room.status = "live"
        self.assertTrue(self.eleve(now))


class ComptesEtProfilsTests(TestCase):
    def compte(self, email, role, mot_de_passe):
        return CustomUser.objects.create_user(username=email, email=email, password=mot_de_passe, role=role,
                                               first_name="A", last_name="B")

    def test_mots_de_passe_de_demonstration_signales_sans_les_afficher(self):
        expose = self.compte("admin@feba.bj", "admin", "Admin@2024")
        out = StringIO()
        with self.assertRaises(SystemExit):
            call_command("check_demo_passwords", stdout=out)
        self.assertIn(str(expose.pk), out.getvalue())
        self.assertNotIn("Admin@2024", out.getvalue())
        expose.set_password("Zk9!tYq3pLm-long")
        expose.save()
        call_command("check_demo_passwords", stdout=StringIO())

    def test_donnees_de_demonstration_refusees_en_production(self):
        with override_settings(SETTINGS_MODULE="feba_project.settings.prod"):
            with self.assertRaises(CommandError):
                call_command("seed_demo_data", stdout=StringIO())

    def test_changement_de_role_cree_le_profil(self):
        user = self.compte("x@test.bj", "parent", "Zk9!tYq3pLm-long")
        UserSerializer().update(user, {"role": "teacher"})
        self.assertTrue(Teacher.objects.filter(user=user).exists())


class SurveillanceTests(TestCase):
    @override_settings(PLUGNMEET_SERVER_URL="https://meet.test", PUBLIC_BASE_URL="https://feba.test")
    def test_tout_va_bien_aucun_incident(self):
        frais = timezone.now().isoformat()
        with mock.patch.object(tasks, "lire", side_effect=["Healthy", frais]), \
             mock.patch.object(tasks, "jours_restants_certificat", return_value=60):
            self.assertEqual(tasks.surveillance_plateforme(), [])
        self.assertFalse(TechnicalIncident.objects.exists())

    @override_settings(PLUGNMEET_SERVER_URL="https://meet.test", PUBLIC_BASE_URL="")
    def test_anomalies_regroupees_en_incidents(self):
        vieux = (timezone.now() - datetime.timedelta(days=3)).isoformat()
        for _ in range(2):
            with mock.patch.object(tasks, "lire", side_effect=["KO", vieux]), \
                 mock.patch.object(tasks, "jours_restants_certificat", return_value=5):
                self.assertEqual(len(tasks.surveillance_plateforme()), 3)
        self.assertEqual(TechnicalIncident.objects.count(), 3)
        self.assertEqual(set(TechnicalIncident.objects.values_list("occurrences", flat=True)), {2})

    def test_echec_de_tache_cree_un_incident(self):
        tasks.incident_sur_echec_de_tache(sender=types.SimpleNamespace(name="payments.x"), exception=ValueError("boum"))
        self.assertEqual(TechnicalIncident.objects.get().exception_type, "ValueError")
