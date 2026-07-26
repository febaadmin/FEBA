"""
V8 — Vérification des MIGRATIONS DE DONNÉES.

Les migrations ne peuvent pas être rejouées de bout en bout sur SQLite dans cet
environnement (limitation PRÉ-EXISTANTE : une migration historique utilise une
syntaxe refusée par la SQLite embarquée — les tests du projet tournent donc
avec `--no-migrations`, y compris avant la V8). On valide donc ici la LOGIQUE
des migrations de données en appelant directement leurs fonctions `forwards`
sur les modèles réels, avec le même contrat (rapport avant / exécution /
vérification après).
"""
from decimal import Decimal
from importlib import import_module

from django.apps import apps as django_apps
from django.test import TestCase

from apps.classes.models import Class
from apps.grades.models import Grade
from apps.schools.models import Level, School, SchoolYear
from apps.students.models import Student
from apps.subjects.models import Subject


class AssessmentWeightMigrationTests(TestCase):
    """grades/0011 : tous les poids d'évaluation ramenés à 1."""

    @classmethod
    def setUpTestData(cls):
        cls.school = School.objects.create(name="FEBA", address="Cotonou")
        cls.year = SchoolYear.objects.create(
            school=cls.school, name="2025-2026",
            start_date="2025-09-01", end_date="2026-07-31", is_current=True)
        level = Level.objects.create(school=cls.school, name="CM2", order=11)
        klass = Class.objects.create(name="CM2-A", level=level, school_year=cls.year)
        cls.subject = Subject.objects.create(school=cls.school, name="Maths",
                                             code="MATH", coefficient=4, language="fr")
        cls.student = Student.objects.create(
            school=cls.school, first_name="Ayo", last_name="Codjo",
            current_class=klass, school_year=cls.year)

    def _legacy_grade(self, value, weight, note_type="devoir"):
        """Crée une note « héritée » avec un poids ≠ 1.

        `Grade.save()` normalise désormais à 1 : on écrit donc directement en
        base pour reproduire l'état ANTÉRIEUR à la V8.
        """
        grade = Grade.objects.create(
            student=self.student, subject=self.subject, school_year=self.year,
            period="T1", value=Decimal(str(value)), note_type=note_type)
        Grade.objects.filter(pk=grade.pk).update(note_coefficient=weight)
        return grade

    def test_migration_normalise_les_poids_existants(self):
        self._legacy_grade(12, 1, "interrogation")
        self._legacy_grade(5, 3, "examen")          # examen jadis pondéré ×3
        self._legacy_grade(8, 2, "controle")
        # 2 notes sur 3 ont un poids ≠ 1 (l'interrogation vaut déjà 1).
        self.assertEqual(
            Grade.objects.exclude(note_coefficient=1).count(), 2,
            "l'état « avant migration » doit bien contenir des poids ≠ 1")

        migration = import_module("apps.grades.migrations.0011_assessment_weight_one")
        migration.forwards(django_apps, None)

        self.assertEqual(Grade.objects.exclude(note_coefficient=1).count(), 0)
        self.assertEqual(Grade.objects.count(), 3, "aucune note ne doit être perdue")

    def test_les_valeurs_des_notes_ne_sont_pas_modifiees(self):
        """Seul le POIDS change : les notes elles-mêmes sont préservées."""
        self._legacy_grade(12, 1, "interrogation")
        self._legacy_grade(5, 3, "examen")
        before = sorted(str(v) for v in Grade.objects.values_list("value", flat=True))

        migration = import_module("apps.grades.migrations.0011_assessment_weight_one")
        migration.forwards(django_apps, None)

        after = sorted(str(v) for v in Grade.objects.values_list("value", flat=True))
        self.assertEqual(before, after)

    def test_moyenne_apres_migration_est_la_moyenne_arithmetique(self):
        """Impact métier : 12 (interro) et 5 (examen ×3) → 8,5 après migration."""
        self._legacy_grade(12, 1, "interrogation")
        self._legacy_grade(5, 3, "examen")

        migration = import_module("apps.grades.migrations.0011_assessment_weight_one")
        migration.forwards(django_apps, None)

        data = Grade.get_subject_averages(self.student, self.year, "T1")
        self.assertEqual(Decimal(str(data[self.subject.id]["average"])), Decimal("8.50"))

    def test_migration_idempotente(self):
        self._legacy_grade(10, 2)
        migration = import_module("apps.grades.migrations.0011_assessment_weight_one")
        migration.forwards(django_apps, None)
        migration.forwards(django_apps, None)   # rejouée : aucun effet de bord
        self.assertEqual(Grade.objects.exclude(note_coefficient=1).count(), 0)
        self.assertEqual(Grade.objects.count(), 1)


class OfficialNameMigrationTests(TestCase):
    """V7 rappel : schools/0011 renomme l'établissement (toujours valide en V8)."""

    def test_renommage_cible_uniquement_l_ancien_libelle(self):
        old = School.objects.create(name="Groupe Scolaire FEBA", address="Cotonou")
        other = School.objects.create(name="Autre École", address="Porto-Novo")

        migration = import_module("apps.schools.migrations.0011_official_school_name")
        migration.forwards(django_apps, None)

        old.refresh_from_db(); other.refresh_from_db()
        self.assertEqual(old.name, "Faith & Excellence Bilingual Academy")
        self.assertEqual(other.name, "Autre École", "les autres écoles ne changent pas")
