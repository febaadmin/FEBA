"""
Tests de la commande `clean_previous_usage_data`.

La commande efface les données d'USAGE en préservant la STRUCTURE. Comme
elle est destinée à être lancée une fois sur une base réelle, chaque
garde-fou est testé explicitement : une erreur ici serait irréversible.

Couverture (20 scénarios) :
   1. dry-run n'écrit rien
   2. --execute sans confirmation refusé
   3. mauvaise confirmation refusée
   4. académies conservées
   5. matières / classes / niveaux conservés
   6. comptes superadmin / admin / teacher conservés
   7. profils enseignants conservés
   8. comptes parent / élève supprimés
   9. profils parent / élève supprimés
  10. liens parent-élève et inscriptions supprimés
  11. notes / bulletins / présences / paiements supprimés
  12. messages / notifications / documents / formulaires supprimés
  13. memberships des comptes conservés préservés
  14. memberships des comptes supprimés supprimés
  15. absence d'orphelins multi-académies
  16. rollback si une vérification échoue
  17. seconde exécution idempotente
  18. filtre --academy
  19. les comptes conservés peuvent encore se connecter
  20. de nouvelles créations restent possibles après nettoyage
"""
import json
import tempfile
from datetime import date, timedelta
from io import StringIO
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from rest_framework.test import APIClient

from apps.attendance.models import Attendance
from apps.bulletins.models import Bulletin
from apps.classes.models import Class
from apps.grades.models import Grade
from apps.messaging.models import Conversation, Message
from apps.notifications.models import Notification
from apps.parents.models import Parent, ParentStudent
from apps.payments.models import Payment
from apps.schools.models import (
    Level, OrganizationMembership, School, SchoolYear,
)
from apps.students.models import Student, StudentEnrollment
from apps.subjects.models import Subject
from apps.teachers.models import Teacher
from apps.website.models import ContactMessage, FHAEnrollmentApplication

User = get_user_model()

CONFIRM = "DELETE-PREVIOUS-USAGE-DATA"


class CleanPreviousUsageDataTests(TestCase):
    """Base de démonstration miniature couvrant les deux académies."""

    def setUp(self):
        # Les deux académies sont déjà créées par une migration de données :
        # on les récupère plutôt que de les recréer.
        self.feba, _ = School.objects.get_or_create(
            code="FEBA", defaults={"name": "FEBA", "address": "Cotonou"},
        )
        self.fha, _ = School.objects.get_or_create(
            code="FEBA_FHA", defaults={"name": "FEBA FHA", "address": "En ligne"},
        )

        self.year_feba = SchoolYear.objects.create(
            school=self.feba, name="2025-2026",
            start_date=date(2025, 9, 1), end_date=date(2026, 7, 1),
        )
        self.year_fha = SchoolYear.objects.create(
            school=self.fha, name="2025-2026",
            start_date=date(2025, 9, 1), end_date=date(2026, 7, 1),
        )
        self.level = Level.objects.create(school=self.feba, name="6e", order=1)
        self.subject = Subject.objects.create(
            school=self.feba, name="Français", code="FR",
        )
        self.klass = Class.objects.create(
            name="6e A", level=self.level, school_year=self.year_feba,
        )

        # ── Comptes d'encadrement (à conserver) ──────────────────────────
        self.superadmin = self._user("superadmin@feba.bj", "superadmin", self.feba)
        self.admin = self._user("admin@feba.bj", "admin", self.feba)
        self.teacher_user = self._user("prof@feba.bj", "teacher", self.feba)
        self.teacher = Teacher.objects.create(user=self.teacher_user)

        # L'appartenance principale est créée automatiquement à la sauvegarde
        # de l'utilisateur (sync_primary_membership) : on complète seulement
        # la seconde académie du super administrateur.
        OrganizationMembership.objects.get_or_create(
            user=self.superadmin, organization=self.feba,
            defaults={"role": "superadmin"},
        )
        OrganizationMembership.objects.get_or_create(
            user=self.superadmin, organization=self.fha,
            defaults={"role": "superadmin"},
        )

        # ── Comptes d'usage (à supprimer) ────────────────────────────────
        self.student_user = self._user("eleve@feba.bj", "student", self.feba)
        self.parent_user = self._user("parent@feba.bj", "parent", self.feba)
        self.student = Student.objects.create(
            user=self.student_user, school=self.feba,
            first_name="Ama", last_name="Doe", date_of_birth=date(2012, 5, 1),
        )
        self.parent = Parent.objects.create(user=self.parent_user)
        ParentStudent.objects.create(parent=self.parent, student=self.student)
        StudentEnrollment.objects.create(
            student=self.student, class_obj=self.klass, school_year=self.year_feba,
        )
        OrganizationMembership.objects.get_or_create(
            user=self.student_user, organization=self.feba,
            defaults={"role": "student"},
        )

        # Élève côté FHA, pour tester --academy.
        self.fha_student_user = self._user("eleve@fha.com", "student", self.fha)
        self.fha_student = Student.objects.create(
            user=self.fha_student_user, school=self.fha,
            first_name="Ben", last_name="Smith", date_of_birth=date(2013, 3, 2),
        )

        # ── Données transactionnelles ────────────────────────────────────
        Grade.objects.create(
            student=self.student, subject=self.subject, school_year=self.year_feba,
            period=1, value=15,
        )
        Bulletin.objects.create(
            student=self.student, school_year=self.year_feba, period=1,
        )
        Attendance.objects.create(
            student=self.student, date=date(2025, 10, 1), status="absent",
        )
        Payment.objects.create(
            student=self.student, payment_type="tuition", amount=50000,
            currency="XOF", payment_date=date(2025, 10, 1),
        )
        conv = Conversation.objects.create(subject="Bonjour")
        conv.participants.add(self.parent_user, self.teacher_user)
        Message.objects.create(
            conversation=conv, sender=self.parent_user,
            recipient=self.teacher_user, body="Bonjour",
        )
        Notification.objects.create(
            user=self.parent_user, type="info", title="Info", message="Test",
        )
        ContactMessage.objects.create(
            entity=self.feba, name="Visiteur", email="v@x.com",
            subject="Question", message="Bonjour",
        )
        FHAEnrollmentApplication.objects.create(
            entity=self.fha, child_first_name="Ben", child_last_name="Smith",
            child_birth_date=date(2013, 3, 2),
            parent1_first_name="Paul", parent1_last_name="Smith",
            parent1_phone="+1555000000", parent1_email="p@x.com",
        )

    def _user(self, email, role, school):
        # L'adresse complète sert de nom d'utilisateur : deux comptes
        # « eleve@… » d'académies différentes ne doivent pas entrer en
        # collision sur la partie locale.
        return User.objects.create_user(
            username=email, email=email, password="Pass1234!",
            role=role, school=school, first_name=role.title(), last_name="Test",
        )

    def _run(self, **kwargs):
        out = StringIO()
        call_command("clean_previous_usage_data", stdout=out, **kwargs)
        return out.getvalue()

    # ── 1-3 : sécurité des options ───────────────────────────────────────
    def test_01_dry_run_n_ecrit_rien(self):
        before = {
            "users": User.objects.count(),
            "students": Student.objects.count(),
            "grades": Grade.objects.count(),
            "payments": Payment.objects.count(),
        }
        self._run(dry_run=True)
        self.assertEqual(User.objects.count(), before["users"])
        self.assertEqual(Student.objects.count(), before["students"])
        self.assertEqual(Grade.objects.count(), before["grades"])
        self.assertEqual(Payment.objects.count(), before["payments"])

    def test_02_execute_sans_confirmation_refuse(self):
        with self.assertRaises(CommandError) as ctx:
            self._run(execute=True)
        self.assertIn("confirm", str(ctx.exception).lower())
        self.assertTrue(Student.objects.exists())

    def test_02b_ni_dry_run_ni_execute_refuse(self):
        with self.assertRaises(CommandError):
            self._run()

    def test_02c_dry_run_et_execute_ensemble_refuses(self):
        with self.assertRaises(CommandError):
            self._run(dry_run=True, execute=True, confirm=CONFIRM)

    def test_03_mauvaise_confirmation_refusee(self):
        with self.assertRaises(CommandError):
            self._run(execute=True, confirm="SUPPRIMER")
        self.assertTrue(Student.objects.exists())

    # ── 4-7 : ce qui doit survivre ───────────────────────────────────────
    def test_04_academies_conservees(self):
        ids = set(School.objects.values_list("id", flat=True))
        self._run(execute=True, confirm=CONFIRM)
        self.assertEqual(set(School.objects.values_list("id", flat=True)), ids)

    def test_05_structure_pedagogique_conservee(self):
        subjects = set(Subject.objects.values_list("id", flat=True))
        classes = set(Class.objects.values_list("id", flat=True))
        levels = set(Level.objects.values_list("id", flat=True))
        self._run(execute=True, confirm=CONFIRM)
        self.assertEqual(set(Subject.objects.values_list("id", flat=True)), subjects)
        self.assertEqual(set(Class.objects.values_list("id", flat=True)), classes)
        self.assertEqual(set(Level.objects.values_list("id", flat=True)), levels)

    def test_06_comptes_encadrement_conserves(self):
        self._run(execute=True, confirm=CONFIRM)
        for email in ("superadmin@feba.bj", "admin@feba.bj", "prof@feba.bj"):
            self.assertTrue(
                User.objects.filter(email=email).exists(),
                f"{email} aurait dû être conservé",
            )

    def test_07_profils_enseignants_conserves(self):
        self._run(execute=True, confirm=CONFIRM)
        self.assertTrue(Teacher.objects.filter(pk=self.teacher.pk).exists())

    # ── 8-12 : ce qui doit disparaître ───────────────────────────────────
    def test_08_comptes_parent_et_eleve_supprimes(self):
        self._run(execute=True, confirm=CONFIRM)
        self.assertFalse(User.objects.filter(role__in=("student", "parent")).exists())

    def test_09_profils_parent_et_eleve_supprimes(self):
        self._run(execute=True, confirm=CONFIRM)
        self.assertEqual(Student.objects.count(), 0)
        self.assertEqual(Parent.objects.count(), 0)

    def test_10_liens_et_inscriptions_supprimes(self):
        self._run(execute=True, confirm=CONFIRM)
        self.assertEqual(ParentStudent.objects.count(), 0)
        self.assertEqual(StudentEnrollment.objects.count(), 0)

    def test_11_notes_bulletins_presences_paiements_supprimes(self):
        self._run(execute=True, confirm=CONFIRM)
        self.assertEqual(Grade.objects.count(), 0)
        self.assertEqual(Bulletin.objects.count(), 0)
        self.assertEqual(Attendance.objects.count(), 0)
        self.assertEqual(Payment.objects.count(), 0)

    def test_12_messages_notifications_formulaires_supprimes(self):
        self._run(execute=True, confirm=CONFIRM)
        self.assertEqual(Message.objects.count(), 0)
        self.assertEqual(Conversation.objects.count(), 0)
        self.assertEqual(Notification.objects.count(), 0)
        self.assertEqual(ContactMessage.objects.count(), 0)
        self.assertEqual(FHAEnrollmentApplication.objects.count(), 0)

    # ── 13-15 : appartenances et orphelins ───────────────────────────────
    def test_13_memberships_des_comptes_conserves_preserves(self):
        self._run(execute=True, confirm=CONFIRM)
        self.assertEqual(
            OrganizationMembership.objects.filter(user=self.superadmin).count(), 2,
        )

    def test_14_memberships_des_comptes_supprimes_supprimes(self):
        self._run(execute=True, confirm=CONFIRM)
        self.assertFalse(
            OrganizationMembership.objects.filter(role="student").exists()
        )

    def test_15_aucun_orphelin_multi_academies(self):
        self._run(execute=True, confirm=CONFIRM)
        # Toute appartenance restante pointe vers un compte existant.
        user_ids = set(User.objects.values_list("id", flat=True))
        membership_users = set(
            OrganizationMembership.objects.values_list("user_id", flat=True)
        )
        self.assertTrue(membership_users.issubset(user_ids))

    # ── 16-17 : robustesse ───────────────────────────────────────────────
    def test_16_rollback_si_verification_echoue(self):
        """
        Une vérification post-suppression en échec doit TOUT annuler : la
        base doit se retrouver exactement dans son état initial.
        """
        students_before = Student.objects.count()
        users_before = User.objects.count()
        grades_before = Grade.objects.count()

        target = (
            "apps.core.management.commands.clean_previous_usage_data."
            "Command._verify"
        )
        with mock.patch(target, side_effect=Exception("panne simulée")):
            with self.assertRaises(Exception):
                self._run(execute=True, confirm=CONFIRM)

        self.assertEqual(Student.objects.count(), students_before)
        self.assertEqual(User.objects.count(), users_before)
        self.assertEqual(Grade.objects.count(), grades_before)

    def test_17_seconde_execution_idempotente(self):
        self._run(execute=True, confirm=CONFIRM)
        snapshot = {
            "users": User.objects.count(),
            "schools": School.objects.count(),
            "subjects": Subject.objects.count(),
        }
        # La seconde passe ne doit ni échouer ni rien changer.
        self._run(execute=True, confirm=CONFIRM)
        self.assertEqual(User.objects.count(), snapshot["users"])
        self.assertEqual(School.objects.count(), snapshot["schools"])
        self.assertEqual(Subject.objects.count(), snapshot["subjects"])

    # ── 18 : filtre par académie ─────────────────────────────────────────
    def test_18_filtre_academy_ne_touche_que_l_academie_visee(self):
        self._run(execute=True, confirm=CONFIRM, academy="FEBA_FHA")
        # L'élève FHA est parti…
        self.assertFalse(User.objects.filter(email="eleve@fha.com").exists())
        # …celui de FEBA est toujours là.
        self.assertTrue(User.objects.filter(email="eleve@feba.bj").exists())
        self.assertTrue(Student.objects.filter(pk=self.student.pk).exists())

    def test_18b_academy_inconnue_refusee(self):
        with self.assertRaises(CommandError):
            self._run(execute=True, confirm=CONFIRM, academy="INEXISTANTE")

    # ── 19-20 : la base reste exploitable ────────────────────────────────
    def test_19_les_comptes_conserves_peuvent_se_connecter(self):
        self._run(execute=True, confirm=CONFIRM)
        client = APIClient()
        resp = client.post(
            "/api/auth/login/",
            {"email": "admin@feba.bj", "password": "Pass1234!"},
            format="json",
        )
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertIn("access", resp.data)

    def test_20_nouvelles_creations_possibles_apres_nettoyage(self):
        self._run(execute=True, confirm=CONFIRM)
        user = User.objects.create_user(
            username="neo", email="neo@feba.bj", password="Pass1234!",
            role="student", school=self.feba,
        )
        student = Student.objects.create(
            user=user, school=self.feba, first_name="Neo", last_name="New",
            date_of_birth=date(2014, 1, 1),
        )
        self.assertTrue(Student.objects.filter(pk=student.pk).exists())
        self.assertTrue(student.matricule, "Le matricule doit être généré")

    # ── Rapport JSON ─────────────────────────────────────────────────────
    def test_rapport_json_complet(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
            path = tmp.name
        self._run(dry_run=True, report_json=path)
        with open(path, encoding="utf-8") as fh:
            report = json.load(fh)

        for key in (
            "counts_before", "counts_after", "direct_deletions",
            "cascade_deletions", "kept_accounts", "deleted_accounts",
            "academies_processed", "anomalies", "media_files", "status",
        ):
            self.assertIn(key, report)
        self.assertEqual(report["status"], "SUCCESS")
        self.assertEqual(report["mode"], "dry-run")
        # Le mot de passe de la base ne doit jamais fuiter : la chaîne de
        # connexion publiée ne contient ni identifiants ni « @ » de
        # séparation user:pass@host.
        self.assertNotIn("@", report["database"])
        self.assertNotIn("PASSWORD", report)

    def test_dry_run_signale_les_suppressions_prevues(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
            path = tmp.name
        self._run(dry_run=True, report_json=path)
        with open(path, encoding="utf-8") as fh:
            report = json.load(fh)
        self.assertIn("students.Student", report["direct_deletions"])
        self.assertIn("accounts.CustomUser", report["direct_deletions"])
        # …mais rien n'a réellement disparu.
        self.assertTrue(Student.objects.exists())

    def test_aucune_cascade_sur_les_modeles_structurels(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
            path = tmp.name
        self._run(dry_run=True, report_json=path)
        with open(path, encoding="utf-8") as fh:
            report = json.load(fh)
        for label in ("schools.School", "subjects.Subject", "classes.Class", "schools.Level"):
            self.assertNotIn(
                label, report["cascade_deletions"],
                f"{label} ne doit jamais être emporté par cascade",
            )
