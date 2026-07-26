"""
V8 — Priorités 4 & 5.

P4 : toutes les évaluations pèsent 1 (un examen ne compte pas plus qu'une
     interrogation) → moyenne ARITHMÉTIQUE. Cas imposé : 12 et 5 → 8,5.
P5 : bulletins des niveaux 1 à 11 (Garderie → CM2) sur 10 ; Collège et au-delà
     sur 20. Les appréciations et lettres restent calculées sur l'échelle
     interne /20 (6/10 ≡ 12/20 → même appréciation).
"""
from decimal import Decimal

from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient

from apps.accounts.models import CustomUser
from apps.classes.models import Class
from apps.grades.grading import (
    ASSESSMENT_WEIGHT, convert_average_for_scale, get_grading_scale,
    scale_label, subject_average,
)
from apps.grades.models import Grade, get_appreciation, get_letter_grade
from apps.schools.models import Level, School, SchoolYear
from apps.students.models import Student
from apps.subjects.models import Subject
from apps.teachers.models import Teacher


class SubjectAverageTests(SimpleTestCase):
    """P4 — moyenne arithmétique, tous types confondus."""

    def test_cas_impose_12_et_5_donne_8_5(self):
        self.assertEqual(subject_average([Decimal("12"), Decimal("5")]), Decimal("8.5"))

    def test_cas_de_reference(self):
        cases = [
            ([10, 10], Decimal("10")),
            ([0, 20], Decimal("10")),
            ([10], Decimal("10")),
            ([Decimal("10.5"), Decimal("9.5")], Decimal("10")),
            ([12, 5, 10], Decimal("9")),                     # trois types
            ([8, 12, 16, 4, 20], Decimal("12")),             # cinq notes
        ]
        for values, expected in cases:
            self.assertEqual(subject_average([Decimal(str(v)) for v in values]), expected,
                             f"moyenne incorrecte pour {values}")

    def test_zero_reel_compte_non_note_ignore(self):
        # Un 0 réel fait baisser la moyenne…
        self.assertEqual(subject_average([Decimal("0"), Decimal("10")]), Decimal("5"))
        # …alors qu'une absence de note (None) est ignorée, pas comptée 0.
        self.assertEqual(subject_average([None, Decimal("10")]), Decimal("10"))
        self.assertIsNone(subject_average([]))
        self.assertIsNone(subject_average([None]))

    def test_baremes_differents_normalises(self):
        # 45/50 → 18/20 ; moyenne avec 16/20 → 17
        self.assertEqual(
            subject_average([Decimal("45"), Decimal("16")], [50, 20]),
            Decimal("17"),
        )

    def test_poids_unique(self):
        self.assertEqual(ASSESSMENT_WEIGHT, 1)


class GradingScaleTests(SimpleTestCase):
    """P5 — barème d'affichage par niveau."""

    def test_niveaux_1_a_11_sur_10(self):
        for order in range(1, 12):
            level = type("L", (), {"order": order})()
            self.assertEqual(get_grading_scale(level), Decimal("10"),
                             f"niveau {order} doit être sur 10")

    def test_niveau_12_et_au_dela_sur_20(self):
        for order in (12, 13, 15):
            level = type("L", (), {"order": order})()
            self.assertEqual(get_grading_scale(level), Decimal("20"),
                             f"niveau {order} doit rester sur 20")

    def test_niveau_inconnu_reste_sur_20(self):
        self.assertEqual(get_grading_scale(None), Decimal("20"))

    def test_conversions(self):
        cases = [
            (Decimal("20"), Decimal("10.00")), (Decimal("19"), Decimal("9.50")),
            (Decimal("15"), Decimal("7.50")),  (Decimal("12"), Decimal("6.00")),
            (Decimal("10"), Decimal("5.00")),  (Decimal("8.5"), Decimal("4.25")),
            (Decimal("5"), Decimal("2.50")),   (Decimal("0"), Decimal("0.00")),
        ]
        for internal, displayed in cases:
            self.assertEqual(convert_average_for_scale(internal, Decimal("10")), displayed)
            # Sur 20, la valeur est inchangée.
            self.assertEqual(convert_average_for_scale(internal, Decimal("20")),
                             internal.quantize(Decimal("0.01")))

    def test_libelle_entete(self):
        self.assertEqual(scale_label(Decimal("10")), "Moy. /10")
        self.assertEqual(scale_label(Decimal("20")), "Moy. /20")

    def test_appreciation_identique_quel_que_soit_l_affichage(self):
        """6/10 ≡ 12/20 : même appréciation et même lettre."""
        internal = Decimal("12")
        self.assertEqual(convert_average_for_scale(internal, Decimal("10")), Decimal("6.00"))
        # Barème officiel V4 : 12/20 ∈ [11, 13[ → PEUT MIEUX FAIRE, lettre B-.
        self.assertEqual(get_appreciation(internal), "PEUT MIEUX FAIRE")
        self.assertEqual(get_letter_grade(internal)[0], "B-")
        # L'affichage sur 10 ne doit JAMAIS être reclassé avec les seuils /20
        # (6 serait alors « INSUFFISANT » — c'est précisément l'erreur à éviter).
        self.assertNotEqual(get_appreciation(Decimal("6")), get_appreciation(internal))


class GradeWeightEnforcementTests(TestCase):
    """P4 — le backend impose le poids 1, même si l'API en demande un autre."""

    @classmethod
    def setUpTestData(cls):
        cls.school = School.objects.create(name="FEBA", address="Cotonou")
        cls.year = SchoolYear.objects.create(
            school=cls.school, name="2025-2026",
            start_date="2025-09-01", end_date="2026-07-31", is_current=True)
        cls.level = Level.objects.create(school=cls.school, name="CM2", order=11)
        cls.klass = Class.objects.create(name="CM2-A", level=cls.level, school_year=cls.year)
        cls.subject = Subject.objects.create(school=cls.school, name="Maths", code="MATH",
                                             coefficient=4, language="fr")
        cls.klass.subjects.set([cls.subject])
        cls.student = Student.objects.create(
            school=cls.school, first_name="Ayo", last_name="Codjo",
            current_class=cls.klass, school_year=cls.year)
        tu = CustomUser.objects.create_user(
            username="prof", email="prof@test.bj", password="Pass1234!",
            role="teacher", first_name="T", last_name="P", school=cls.school)
        cls.teacher = Teacher.objects.create(user=tu)
        cls.teacher.subjects.set([cls.subject])
        cls.teacher.classes.set([cls.klass])
        cls.admin = CustomUser.objects.create_user(
            username="adm", email="adm@test.bj", password="Pass1234!",
            role="admin", first_name="A", last_name="D", school=cls.school)

    def api(self, user):
        client = APIClient()
        client.force_authenticate(user=user)
        return client

    def test_coefficient_force_a_1_en_base(self):
        grade = Grade.objects.create(
            student=self.student, subject=self.subject, school_year=self.year,
            period="T1", value=Decimal("12"), note_type="examen", note_coefficient=3)
        grade.refresh_from_db()
        self.assertEqual(grade.note_coefficient, 1)

    def test_saisie_simple_coefficient_ignore(self):
        resp = self.api(self.admin).post("/api/grades/", {
            "student": self.student.id, "subject": self.subject.id,
            "school_year": self.year.id, "period": "T1", "value": "12",
            "note_type": "examen", "note_coefficient": 3,
        }, format="json")
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(Grade.objects.get(id=resp.data["id"]).note_coefficient, 1)

    def test_saisie_groupee_coefficient_ignore(self):
        resp = self.api(self.admin).post("/api/grades/bulk-create/", {
            "student": self.student.id, "school_year": self.year.id,
            "grades": [{"subject": self.subject.id, "period": "T1", "value": "12",
                        "note_type": "examen", "note_coefficient": 3}],
        }, format="json")
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertTrue(all(g.note_coefficient == 1 for g in Grade.objects.all()))

    def test_moyenne_matiere_12_interrogation_et_5_examen_donne_8_5(self):
        """Le cas exact de la demande, de bout en bout (API → moyenne)."""
        client = self.api(self.admin)
        for value, note_type in (("12", "interrogation"), ("5", "examen")):
            resp = client.post("/api/grades/", {
                "student": self.student.id, "subject": self.subject.id,
                "school_year": self.year.id, "period": "T1", "value": value,
                "note_type": note_type, "note_coefficient": 3,
            }, format="json")
            self.assertEqual(resp.status_code, 201, resp.data)

        data = Grade.get_subject_averages(self.student, self.year, "T1")
        self.assertEqual(Decimal(str(data[self.subject.id]["average"])), Decimal("8.50"))


class BulletinScaleTests(TestCase):
    """P5 — le bulletin PDF affiche /10 en primaire et /20 au collège."""

    @classmethod
    def setUpTestData(cls):
        cls.school = School.objects.create(name="FEBA", address="Cotonou")
        cls.year = SchoolYear.objects.create(
            school=cls.school, name="2025-2026",
            start_date="2025-09-01", end_date="2026-07-31", is_current=True)
        cls.subject = Subject.objects.create(school=cls.school, name="Maths", code="MATH",
                                             coefficient=4, language="fr")

    def _pdf_text(self, level_order, value):
        from io import BytesIO
        import fitz
        from apps.bulletins import pdf_generator as G

        level = Level.objects.create(school=self.school, name=f"N{level_order}",
                                     order=level_order, cycle="primaire")
        klass = Class.objects.create(name=f"C{level_order}", level=level,
                                     school_year=self.year)
        klass.subjects.set([self.subject])
        student = Student.objects.create(
            school=self.school, first_name="E", last_name=str(level_order),
            current_class=klass, school_year=self.year)
        Grade.objects.create(student=student, subject=self.subject,
                             school_year=self.year, period="T1",
                             value=Decimal(str(value)), note_type="devoir")

        average = Grade.calculate_average(student, self.year, "T1")
        subject_data = Grade.get_subject_averages(student, self.year, "T1")
        bilingual = Grade.calculate_bilingual_averages(student, self.year, "T1")
        bulletin = type("B", (), {"appreciation": get_appreciation(average),
                                  "general_comment": "", "rank_in_class": None})()
        buf = BytesIO()
        G._build_standard_pdf(buf, student, "T1", self.year, subject_data,
                              bilingual, {}, average, bulletin, None)
        doc = fitz.open(stream=buf.getvalue(), filetype="pdf")
        return "\n".join(p.get_text() for p in doc)

    def test_primaire_niveau_11_affiche_sur_10(self):
        text = self._pdf_text(11, 12)          # 12/20 interne
        self.assertIn("6.00/10", text)         # → 6,00/10 affiché
        self.assertIn("Moy. /10", text)
        self.assertNotIn("12.00/20", text)

    def test_college_niveau_12_reste_sur_20(self):
        text = self._pdf_text(12, 12)
        self.assertIn("12.00/20", text)
        self.assertIn("Moy. /20", text)
        self.assertNotIn("6.00/10", text)

    def test_niveau_1_garderie_sur_10(self):
        text = self._pdf_text(1, 15)           # 15/20 → 7,50/10
        self.assertIn("7.50/10", text)

    def test_appreciation_conservee_en_primaire(self):
        """6/10 (≡ 12/20) garde l'appréciation de 12/20."""
        text = self._pdf_text(11, 12)
        self.assertIn("6.00/10", text)
        self.assertIn(get_appreciation(Decimal("12")), text)  # ACCEPTABLE
