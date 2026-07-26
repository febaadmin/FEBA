"""
V8 — Le processus de préparation de la base de démonstration.

Contexte du défaut corrigé : les réglages `dev_sqlite` neutralisent la chaîne
de migrations, si bien que la migration de données qui ramène tous les poids
d'évaluation à 1 n'était JAMAIS exécutée sur une base de démonstration. Une
installation neuve pouvait donc conserver d'anciens poids ≠ 1 — et donc des
moyennes fausses — alors que la production (PostgreSQL) était correcte.

Ces tests verrouillent les deux garde-fous :
  1. la vérification est BLOQUANTE (elle échoue si un poids ≠ 1 subsiste) ;
  2. la migration de données est rejouable et répare une base non conforme.
"""
import importlib
from decimal import Decimal
from io import StringIO

from django.apps import apps as global_apps
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection
from django.test import TestCase

from apps.classes.models import Class
from apps.grades.grading import ASSESSMENT_WEIGHT
from apps.grades.models import Grade
from apps.schools.models import Level, School, SchoolYear
from apps.students.models import Student
from apps.subjects.models import Subject


class BootstrapDemoWeightCheckTests(TestCase):
    """La vérification obligatoire « poids != 1 → 0 »."""

    @classmethod
    def setUpTestData(cls):
        cls.school = School.objects.create(name="FEBA", address="Cotonou")
        cls.year = SchoolYear.objects.create(
            school=cls.school, name="2025-2026",
            start_date="2025-09-01", end_date="2026-07-31", is_current=True)
        cls.level = Level.objects.create(school=cls.school, name="CE1",
                                         cycle="primaire", order=2)
        cls.klass = Class.objects.create(name="CE1-A", level=cls.level,
                                         school_year=cls.year)
        cls.subject = Subject.objects.create(school=cls.school, name="Maths",
                                             code="MATH", coefficient=4,
                                             language="fr")
        cls.student = Student.objects.create(
            school=cls.school, first_name="Koffi", last_name="Codjo",
            current_class=cls.klass, school_year=cls.year)

    def _grade(self, value="12"):
        return Grade.objects.create(
            student=self.student, subject=self.subject, school_year=self.year,
            period="T1", value=Decimal(value), note_type="devoir")

    def _force_weight_in_db(self, grade, weight):
        """Écrit un poids hérité en SQL brut (contourne Grade.save())."""
        with connection.cursor() as cur:
            cur.execute(
                "UPDATE grades_grade SET note_coefficient = %s WHERE id = %s",
                [weight, grade.id])

    def _run_check(self):
        out = StringIO()
        call_command("bootstrap_demo", "--check-only", stdout=out)
        return out.getvalue()

    def test_base_conforme_la_verification_passe(self):
        self._grade()
        sortie = self._run_check()
        self.assertIn("!= 1 = 0", sortie.replace("d'évaluation ", ""))
        self.assertIn("conforme", sortie)

    def test_un_poids_herite_fait_echouer_la_verification(self):
        """Le garde-fou doit BLOQUER, pas se contenter d'un avertissement."""
        grade = self._grade()
        self._force_weight_in_db(grade, 3)
        with self.assertRaises(CommandError) as ctx:
            self._run_check()
        self.assertIn("3", str(ctx.exception))
        self.assertIn("pas conforme", str(ctx.exception).lower())

    def test_la_migration_de_donnees_repare_une_base_non_conforme(self):
        grades = [self._grade(), self._grade("15"), self._grade("7")]
        for g, poids in zip(grades, (2, 3, 2)):
            self._force_weight_in_db(g, poids)
        self.assertEqual(
            Grade.objects.exclude(note_coefficient=ASSESSMENT_WEIGHT).count(), 3)

        module = importlib.import_module(
            "apps.grades.migrations.0011_assessment_weight_one")
        module.forwards(global_apps, None)

        self.assertEqual(
            Grade.objects.exclude(note_coefficient=ASSESSMENT_WEIGHT).count(), 0)
        # Les NOTES elles-mêmes ne bougent pas : seul leur poids est normalisé.
        for g, attendu in zip(grades, ("12", "15", "7")):
            g.refresh_from_db()
            self.assertEqual(g.value, Decimal(attendu))
        self.assertIn("conforme", self._run_check())


class SeedWeightTests(TestCase):
    """Le seed lui-même ne doit plus réintroduire d'anciens poids."""

    def test_le_seed_n_ecrit_jamais_un_poids_different_de_1(self):
        import inspect

        from apps.schools.management.commands import seed_demo_data

        source = inspect.getsource(seed_demo_data)
        self.assertNotIn("random.choice([1, 1, 2])", source,
                         "Le seed tire encore un poids d'évaluation au hasard.")
        self.assertIn("note_coefficient=ASSESSMENT_WEIGHT", source)
