"""
Tests — Moyennes absentes sur la page Parent (« Toutes périodes » -> « — »).

Cause racine :
  Grade.period est un CharField obligatoire ('T1'/'T2'/'T3'), jamais NULL en
  base. Grade.calculate_average(student, school_year, period=None) délèguait
  à get_subject_averages(..., period=None), qui filtrait `period=None` et ne
  correspondait donc JAMAIS à une note réelle -> average toujours None dès
  que l'appelant ne précisait pas explicitement de période (cas de la page
  Parent, dont le filtre par défaut « Toutes périodes » n'envoie aucun
  paramètre `period` à l'API).

  Sur le frontend (frontend/src/pages/parent/Grades.jsx), un deuxième bug
  indépendant faisait lire des clés JSON inexistantes
  (overall_average / french_average / english_average) au lieu des clés
  réellement renvoyées par l'API (average / fr_average / en_average) — ces
  tests couvrent uniquement le contrat backend ; le frontend est couvert par
  la vérification manuelle décrite dans le rapport de correction.
"""
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status

from apps.accounts.models import CustomUser
from apps.classes.models import Class
from apps.grades.models import Grade
from apps.parents.models import Parent, ParentStudent
from apps.schools.models import School, SchoolYear, Level
from apps.students.models import Student, StudentEnrollment
from apps.subjects.models import Subject
from apps.teachers.models import Teacher


def auth(client, email, password="Pass1234!"):
    resp = client.post("/api/auth/login/", {"email": email, "password": password})
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {resp.data.get('access', '')}")


class CalculateAverageMissingPeriodTests(TestCase):
    """Tests unitaires sur Grade.calculate_average — le coeur de la régression."""

    def setUp(self):
        self.school = School.objects.create(name="Ecole Moy", address="X")
        self.year = SchoolYear.objects.create(
            school=self.school, name="2026-2027", is_current=True,
            start_date="2026-10-01", end_date="2027-07-31",
        )
        lvl = Level.objects.create(school=self.school, name="CE1", order=3)
        self.cls = Class.objects.create(name="CE1-A", level=lvl, school_year=self.year)
        self.fr = Subject.objects.create(school=self.school, name="Français", code="FR", coefficient=4, language="fr")
        self.en = Subject.objects.create(school=self.school, name="English", code="ENG", coefficient=4, language="en")
        self.cls.subjects.set([self.fr, self.en])

        student_user = CustomUser.objects.create_user(
            username="eleve1", email="eleve1@test.bj", password="Pass1234!",
            role="student", first_name="Eleve", last_name="Un", school=self.school,
        )
        self.student = Student.objects.create(
            user=student_user, school=self.school, first_name="Eleve", last_name="Un",
            current_class=self.cls, school_year=self.year,
        )
        StudentEnrollment.objects.create(student=self.student, school_year=self.year, class_obj=self.cls)

        tu = CustomUser.objects.create_user(
            username="prof1", email="prof1@test.bj", password="Pass1234!",
            role="teacher", first_name="Prof", last_name="Un", school=self.school,
        )
        self.teacher = Teacher.objects.create(user=tu)

        # Notes avec coefficients différents sur T1 et T2 (T3 volontairement vide)
        Grade.objects.create(student=self.student, subject=self.fr, school_year=self.year,
                              teacher=self.teacher, period="T1", value=14)
        Grade.objects.create(student=self.student, subject=self.en, school_year=self.year,
                              teacher=self.teacher, period="T1", value=10)
        Grade.objects.create(student=self.student, subject=self.fr, school_year=self.year,
                              teacher=self.teacher, period="T2", value=16)
        Grade.objects.create(student=self.student, subject=self.en, school_year=self.year,
                              teacher=self.teacher, period="T2", value=12)

    def test_period_none_equals_annual(self):
        """RÉGRESSION : period=None ne doit plus renvoyer None quand des notes existent."""
        result_none = Grade.calculate_average(self.student, self.year, period=None)
        result_empty_string = Grade.calculate_average(self.student, self.year, period="")
        result_annual = Grade.calculate_average(self.student, self.year, period="annual")

        self.assertIsNotNone(result_none, "period=None doit se comporter comme 'annual', pas renvoyer None")
        self.assertEqual(result_none, result_annual)
        self.assertEqual(result_empty_string, result_annual)

    def test_period_none_matches_manual_calculation(self):
        """La valeur calculée doit correspondre au calcul manuel pondéré par coefficient."""
        result = Grade.calculate_average(self.student, self.year, period=None)
        # T1 : (14*4 + 10*4)/8 = 12.0 ; T2 : (16*4 + 12*4)/8 = 14.0
        # Moyenne annuelle des deux périodes notées : (12.0 + 14.0) / 2 = 13.0
        self.assertEqual(round(float(result), 2), 13.0)

    def test_specific_period_still_scoped_correctly(self):
        """Non-régression : une période précise ne doit PAS être affectée par le fix."""
        result_t1 = Grade.calculate_average(self.student, self.year, period="T1")
        self.assertEqual(round(float(result_t1), 2), 12.0)
        result_t3 = Grade.calculate_average(self.student, self.year, period="T3")
        self.assertIsNone(result_t3, "T3 sans notes doit rester None (pas de donnée fictive)")

    def test_student_with_no_grades_returns_none_not_crash(self):
        """Un élève sans aucune note : period=None doit renvoyer None proprement, sans exception."""
        other_user = CustomUser.objects.create_user(
            username="eleve2", email="eleve2@test.bj", password="Pass1234!",
            role="student", first_name="Eleve", last_name="Deux", school=self.school,
        )
        other_student = Student.objects.create(
            user=other_user, school=self.school, first_name="Eleve", last_name="Deux",
            current_class=self.cls, school_year=self.year,
        )
        StudentEnrollment.objects.create(student=other_student, school_year=self.year, class_obj=self.cls)
        result = Grade.calculate_average(other_student, self.year, period=None)
        self.assertIsNone(result)


class ParentAveragesEndpointTests(TestCase):
    """Tests API — reproduisent exactement l'appel fait par la page Parent (aucun `period` envoyé)."""

    def setUp(self):
        self.school = School.objects.create(name="Ecole Parent", address="X")
        self.year = SchoolYear.objects.create(
            school=self.school, name="2026-2027", is_current=True,
            start_date="2026-10-01", end_date="2027-07-31",
        )
        lvl = Level.objects.create(school=self.school, name="CE1", order=3)
        self.cls = Class.objects.create(name="CE1-A", level=lvl, school_year=self.year)
        self.fr = Subject.objects.create(school=self.school, name="Français", code="FR", coefficient=4, language="fr")
        self.en = Subject.objects.create(school=self.school, name="English", code="ENG", coefficient=4, language="en")
        self.cls.subjects.set([self.fr, self.en])

        tu = CustomUser.objects.create_user(
            username="prof2", email="prof2@test.bj", password="Pass1234!",
            role="teacher", first_name="Prof", last_name="Deux", school=self.school,
        )
        self.teacher = Teacher.objects.create(user=tu)

        # Parent avec DEUX enfants (cas explicitement exigé) — chacun avec ses propres notes.
        parent_user = CustomUser.objects.create_user(
            username="parent1", email="parent1t@test.bj", password="Pass1234!",
            role="parent", first_name="Papa", last_name="Test", school=self.school,
        )
        self.parent = Parent.objects.create(user=parent_user)

        child1_user = CustomUser.objects.create_user(
            username="enfant1", email="enfant1@test.bj", password="Pass1234!",
            role="student", first_name="Premier", last_name="Enfant", school=self.school,
        )
        self.child1 = Student.objects.create(
            user=child1_user, school=self.school, first_name="Premier", last_name="Enfant",
            current_class=self.cls, school_year=self.year,
        )
        StudentEnrollment.objects.create(student=self.child1, school_year=self.year, class_obj=self.cls)
        ParentStudent.objects.create(parent=self.parent, student=self.child1, relationship="father")

        child2_user = CustomUser.objects.create_user(
            username="enfant2", email="enfant2@test.bj", password="Pass1234!",
            role="student", first_name="Second", last_name="Enfant", school=self.school,
        )
        self.child2 = Student.objects.create(
            user=child2_user, school=self.school, first_name="Second", last_name="Enfant",
            current_class=self.cls, school_year=self.year,
        )
        StudentEnrollment.objects.create(student=self.child2, school_year=self.year, class_obj=self.cls)
        ParentStudent.objects.create(parent=self.parent, student=self.child2, relationship="father")

        # Enfant 1 : notes en FR et EN -> moyenne générale + bilingue calculables
        Grade.objects.create(student=self.child1, subject=self.fr, school_year=self.year,
                              teacher=self.teacher, period="T1", value=15)
        Grade.objects.create(student=self.child1, subject=self.en, school_year=self.year,
                              teacher=self.teacher, period="T1", value=11)

        # Enfant 2 : uniquement du français (pas d'anglais) -> average English doit rester None
        Grade.objects.create(student=self.child2, subject=self.fr, school_year=self.year,
                              teacher=self.teacher, period="T1", value=18)

        self.client = APIClient()
        auth(self.client, "parent1t@test.bj")

    def test_averages_no_period_param_returns_value_for_child1(self):
        """RÉGRESSION PRINCIPALE : appel identique à celui de la page Parent par défaut."""
        resp = self.client.get(f"/api/grades/averages/?student={self.child1.id}&school_year={self.year.id}")
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        self.assertIsNotNone(resp.data["average"], "La moyenne générale ne doit plus être None sans période")
        self.assertEqual(round(float(resp.data["average"]), 2), 13.0)

    def test_averages_no_period_matches_explicit_annual(self):
        """La réponse sans `period` doit être identique à period=annual (cohérence de contrat)."""
        resp_no_period = self.client.get(f"/api/grades/averages/?student={self.child1.id}&school_year={self.year.id}")
        resp_annual = self.client.get(f"/api/grades/averages/?student={self.child1.id}&period=annual&school_year={self.year.id}")
        self.assertEqual(resp_no_period.data["average"], resp_annual.data["average"])

    def test_bilingual_no_period_nested_annual_matches_flat_keys(self):
        """Le endpoint bilingual imbrique sous `annual` quand aucune période n'est fournie."""
        resp = self.client.get(f"/api/grades/bilingual/?student={self.child1.id}&school_year={self.year.id}")
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        annual = resp.data.get("annual")
        self.assertIsNotNone(annual, "La clé 'annual' doit être présente quand aucune période n'est fournie")
        self.assertIsNotNone(annual["fr_average"])
        self.assertIsNotNone(annual["en_average"])
        self.assertIsNotNone(annual["bilingual_average"])

    def test_each_child_gets_its_own_averages_not_mixed_up(self):
        """Un parent avec plusieurs enfants : chaque enfant garde ses propres moyennes."""
        resp1 = self.client.get(f"/api/grades/averages/?student={self.child1.id}&school_year={self.year.id}")
        resp2 = self.client.get(f"/api/grades/averages/?student={self.child2.id}&school_year={self.year.id}")
        self.assertNotEqual(resp1.data["average"], resp2.data["average"])
        self.assertEqual(round(float(resp1.data["average"]), 2), 13.0)
        self.assertEqual(round(float(resp2.data["average"]), 2), 18.0)

    def test_child_without_english_grades_reports_none_not_zero(self):
        """Enfant 2 n'a pas de note d'anglais : en_average doit être None, jamais 0 (donnée fictive interdite)."""
        resp = self.client.get(f"/api/grades/bilingual/?student={self.child2.id}&school_year={self.year.id}")
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        annual = resp.data.get("annual")
        self.assertIsNone(annual["en_average"])
        self.assertIsNotNone(annual["fr_average"])

    def test_parent_cannot_fetch_averages_of_unrelated_student(self):
        """Sécurité : un parent ne doit pas pouvoir lire les moyennes d'un élève qui n'est pas le sien."""
        other_school = School.objects.create(name="Autre Ecole", address="Y")
        other_year = SchoolYear.objects.create(
            school=other_school, name="2026-2027", is_current=True,
            start_date="2026-10-01", end_date="2027-07-31",
        )
        other_lvl = Level.objects.create(school=other_school, name="CE1", order=3)
        other_cls = Class.objects.create(name="CE1-B", level=other_lvl, school_year=other_year)
        stranger_user = CustomUser.objects.create_user(
            username="etranger", email="etranger@test.bj", password="Pass1234!",
            role="student", first_name="Etranger", last_name="Eleve", school=other_school,
        )
        stranger = Student.objects.create(
            user=stranger_user, school=other_school, first_name="Etranger", last_name="Eleve",
            current_class=other_cls, school_year=other_year,
        )
        resp = self.client.get(f"/api/grades/averages/?student={stranger.id}&school_year={self.year.id}")
        self.assertIn(resp.status_code, (status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND))
