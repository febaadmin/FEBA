"""
Tests V4 — Priorités 1 & 3.

P1 : renommage des libellés de types de notes (valeurs internes stables) :
  - 'interrogation' → « Interrogation / Devoir de classe »
  - 'examen'        → « Examen / Évaluation »

P3 : nouveau barème officiel des appréciations (source unique
apps.grades.models.get_appreciation) :
  19–20 EXCELLENT ; 17–<19 TRÈS SATISFAISANT ; 15–<17 SATISFAISANT ;
  13–<15 ACCEPTABLE ; 11–<13 PEUT MIEUX FAIRE ; 9–<11 INSUFFISANT ;
  7–<9 TRÈS INSUFFISANT ; 4–<7 FAIBLE ; 0–<4 TRÈS FAIBLE.
  Normalisation des barèmes ≠ 20, rejet des valeurs invalides.
"""
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status

from apps.accounts.models import CustomUser
from apps.classes.models import Class
from apps.grades.models import Grade, get_appreciation, APPRECIATION_SCALE
from apps.grades.serializers import GradeSerializer
from apps.schools.models import School, SchoolYear, Level
from apps.students.models import Student
from apps.subjects.models import Subject
from apps.teachers.models import Teacher


def auth(client, email, password="Pass1234!"):
    resp = client.post("/api/auth/login/", {"email": email, "password": password})
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {resp.data.get('access', '')}")


# ─────────────────────────────────────────────────────────────────────────────
# P3 — Barème des appréciations
# ─────────────────────────────────────────────────────────────────────────────

class AppreciationScaleTests(TestCase):
    """Bornes exhaustives du barème /20 (entiers et décimales)."""

    def test_integer_boundaries(self):
        expected = {
            0: 'TRÈS FAIBLE', 1: 'TRÈS FAIBLE', 2: 'TRÈS FAIBLE', 3: 'TRÈS FAIBLE',
            4: 'FAIBLE', 5: 'FAIBLE', 6: 'FAIBLE',
            7: 'TRÈS INSUFFISANT', 8: 'TRÈS INSUFFISANT',
            9: 'INSUFFISANT', 10: 'INSUFFISANT',
            11: 'PEUT MIEUX FAIRE', 12: 'PEUT MIEUX FAIRE',
            13: 'ACCEPTABLE', 14: 'ACCEPTABLE',
            15: 'SATISFAISANT', 16: 'SATISFAISANT',
            17: 'TRÈS SATISFAISANT', 18: 'TRÈS SATISFAISANT',
            19: 'EXCELLENT', 20: 'EXCELLENT',
        }
        for note, label in expected.items():
            with self.subTest(note=note):
                self.assertEqual(get_appreciation(note), label)

    def test_decimal_boundaries(self):
        cases = [
            ('3.99', 'TRÈS FAIBLE'),
            ('6.99', 'FAIBLE'),
            ('6.50', 'FAIBLE'),
            ('8.99', 'TRÈS INSUFFISANT'),
            ('8.75', 'TRÈS INSUFFISANT'),
            ('10.99', 'INSUFFISANT'),
            ('10.50', 'INSUFFISANT'),
            ('12.99', 'PEUT MIEUX FAIRE'),
            ('12.25', 'PEUT MIEUX FAIRE'),
            ('14.99', 'ACCEPTABLE'),
            ('14.75', 'ACCEPTABLE'),
            ('16.99', 'SATISFAISANT'),
            ('18.99', 'TRÈS SATISFAISANT'),
            ('17.50', 'TRÈS SATISFAISANT'),
            ('19.00', 'EXCELLENT'),
            ('19.01', 'EXCELLENT'),
            ('20.00', 'EXCELLENT'),
        ]
        for note, label in cases:
            with self.subTest(note=note):
                self.assertEqual(get_appreciation(Decimal(note)), label)

    def test_no_gap_between_intervals(self):
        """Balayage au centième : aucune valeur de [0;20] sans appréciation."""
        valid_labels = {label for _, label in APPRECIATION_SCALE}
        v = Decimal('0')
        step = Decimal('0.01')
        while v <= Decimal('20'):
            self.assertIn(get_appreciation(v), valid_labels, f'trou du barème à {v}')
            v += step

    def test_accented_labels(self):
        """« TRÈS » avec accent, jamais « TRES »."""
        for _, label in APPRECIATION_SCALE:
            self.assertNotIn('TRES ', label)
        self.assertEqual(get_appreciation(18), 'TRÈS SATISFAISANT')
        self.assertEqual(get_appreciation(8), 'TRÈS INSUFFISANT')
        self.assertEqual(get_appreciation(1), 'TRÈS FAIBLE')

    def test_none_returns_dash(self):
        self.assertEqual(get_appreciation(None), '—')

    def test_other_scales_normalized(self):
        # 45/50 = 18/20 → TRÈS SATISFAISANT (exemple du cahier des charges)
        self.assertEqual(get_appreciation(45, max_value=50), 'TRÈS SATISFAISANT')
        self.assertEqual(get_appreciation(9, max_value=10), 'TRÈS SATISFAISANT')
        self.assertEqual(get_appreciation(90, max_value=100), 'TRÈS SATISFAISANT')
        self.assertEqual(get_appreciation(5, max_value=5), 'EXCELLENT')
        self.assertEqual(get_appreciation(Decimal('2.5'), max_value=5), 'INSUFFISANT')
        self.assertEqual(get_appreciation(25, max_value=25), 'EXCELLENT')
        self.assertEqual(get_appreciation(0, max_value=100), 'TRÈS FAIBLE')

    def test_invalid_inputs_rejected(self):
        with self.assertRaises(ValueError):      # note négative
            get_appreciation(-1)
        with self.assertRaises(ValueError):      # note > barème
            get_appreciation(21)
        with self.assertRaises(ValueError):      # note > barème personnalisé
            get_appreciation(55, max_value=50)
        with self.assertRaises(ValueError):      # barème nul
            get_appreciation(10, max_value=0)
        with self.assertRaises(ValueError):      # barème négatif
            get_appreciation(10, max_value=-20)
        with self.assertRaises(ValueError):      # non numérique
            get_appreciation('abc')
        with self.assertRaises(ValueError):      # barème non numérique
            get_appreciation(10, max_value='xyz')

    def test_old_labels_gone(self):
        """Les anciens libellés ne sont plus jamais produits."""
        old = {'Excellent', 'Très Bien', 'Bien', 'Assez Bien', 'Passable', 'Insuffisant'}
        v = Decimal('0')
        while v <= Decimal('20'):
            self.assertNotIn(get_appreciation(v), old)
            v += Decimal('0.25')


class GradeFixtureMixin:
    def _build_school(self):
        self.school = School.objects.create(name="FEBA Test", address="Cotonou")
        self.year = SchoolYear.objects.create(
            school=self.school, name="2026-2027",
            start_date="2026-09-01", end_date="2027-07-31", is_current=True,
        )
        level = Level.objects.create(school=self.school, name="CM2", order=5)
        self.cls = Class.objects.create(name="CM2-A", level=level, school_year=self.year)
        self.math = Subject.objects.create(school=self.school, name="Maths", code="MATH", coefficient=4)
        self.cls.subjects.set([self.math])
        self.student = Student.objects.create(
            school=self.school, first_name="Awa", last_name="K",
            current_class=self.cls, school_year=self.year,
        )
        tu = CustomUser.objects.create_user(
            username="prof1", email="prof1@test.bj", password="Pass1234!",
            role="teacher", first_name="T", last_name="M", school=self.school,
        )
        self.teacher = Teacher.objects.create(user=tu)
        self.admin = CustomUser.objects.create_user(
            username="adm1", email="adm1@test.bj", password="Pass1234!",
            role="admin", first_name="A", last_name="D", school=self.school,
        )


class AppreciationApiTests(GradeFixtureMixin, TestCase):
    """L'API expose l'appréciation de référence calculée par le backend."""

    def setUp(self):
        self._build_school()
        self.client = APIClient()
        auth(self.client, "adm1@test.bj")

    def test_serializer_uses_new_scale(self):
        grade = Grade.objects.create(
            student=self.student, subject=self.math, school_year=self.year,
            teacher=self.teacher, period="T1", value=Decimal('17.50'),
        )
        data = GradeSerializer(grade).data
        self.assertEqual(data['appreciation'], 'TRÈS SATISFAISANT')

    def test_api_grade_list_appreciation(self):
        Grade.objects.create(
            student=self.student, subject=self.math, school_year=self.year,
            teacher=self.teacher, period="T1", value=Decimal('12.25'),
        )
        resp = self.client.get("/api/grades/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        rows = resp.data["results"] if isinstance(resp.data, dict) and "results" in resp.data else resp.data
        self.assertEqual(rows[0]["appreciation"], 'PEUT MIEUX FAIRE')

    def test_student_summary_appreciation(self):
        Grade.objects.create(
            student=self.student, subject=self.math, school_year=self.year,
            teacher=self.teacher, period="T1", value=Decimal('19.00'),
        )
        resp = self.client.get(
            f"/api/grades/student-summary/?student={self.student.id}"
            f"&school_year={self.year.id}&period=T1"
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        self.assertEqual(resp.data["appreciation"], 'EXCELLENT')


class BulletinAppreciationMigrationTests(GradeFixtureMixin, TestCase):
    """La migration de données recalcule les appréciations stockées."""

    def setUp(self):
        self._build_school()

    def test_forwards_recomputes_stored_labels(self):
        from apps.bulletins.models import Bulletin
        from apps.bulletins.migrations import (
            __path__,  # noqa: F401 — garantit que le paquet existe
        )
        import importlib
        mig = importlib.import_module(
            'apps.bulletins.migrations.0005_recompute_appreciations'
        )
        b1 = Bulletin.objects.create(
            student=self.student, school_year=self.year, period="T1",
            average=Decimal('15.50'), appreciation="Bien",
        )
        b2 = Bulletin.objects.create(
            student=self.student, school_year=self.year, period="T2",
            average=Decimal('8.00'), appreciation="Passable",
        )
        b3 = Bulletin.objects.create(
            student=self.student, school_year=self.year, period="T3",
            average=None, appreciation="",
        )

        class _Apps:
            @staticmethod
            def get_model(app_label, model_name):
                assert (app_label, model_name) == ('bulletins', 'Bulletin')
                return Bulletin

        mig.forwards(_Apps, None)
        b1.refresh_from_db(); b2.refresh_from_db(); b3.refresh_from_db()
        self.assertEqual(b1.appreciation, 'SATISFAISANT')
        self.assertEqual(b2.appreciation, 'TRÈS INSUFFISANT')
        self.assertEqual(b3.appreciation, '')  # pas de moyenne → intouché


# ─────────────────────────────────────────────────────────────────────────────
# P1 — Types de notes
# ─────────────────────────────────────────────────────────────────────────────

class NoteTypeLabelTests(GradeFixtureMixin, TestCase):
    def setUp(self):
        self._build_school()
        self.client = APIClient()
        auth(self.client, "adm1@test.bj")

    def test_internal_values_unchanged(self):
        """Les identifiants stockés en base restent stables (compatibilité)."""
        values = [v for v, _ in Grade.NOTE_TYPE_CHOICES]
        self.assertEqual(
            values, ['devoir', 'interrogation', 'controle', 'examen', 'tp', 'autre']
        )

    def test_display_labels_renamed(self):
        labels = dict(Grade.NOTE_TYPE_CHOICES)
        self.assertEqual(labels['interrogation'], 'Interrogation / Devoir de classe')
        self.assertEqual(labels['examen'], 'Examen / Évaluation')
        # Les autres libellés ne changent pas
        self.assertEqual(labels['devoir'], 'Devoir')
        self.assertEqual(labels['controle'], 'Contrôle')

    def test_old_grades_still_readable(self):
        """Une note existante avec l'ancienne valeur interne reste lisible."""
        grade = Grade.objects.create(
            student=self.student, subject=self.math, school_year=self.year,
            teacher=self.teacher, period="T1", value=14, note_type='interrogation',
        )
        self.assertEqual(grade.get_note_type_display(), 'Interrogation / Devoir de classe')
        data = GradeSerializer(grade).data
        self.assertEqual(data['note_type'], 'interrogation')
        self.assertEqual(data['note_type_display'], 'Interrogation / Devoir de classe')
        self.assertEqual(data['note_type_label'], 'Interrogation / Devoir de classe')

    def test_create_grade_via_api_with_each_renamed_type(self):
        for note_type, expected_label in [
            ('interrogation', 'Interrogation / Devoir de classe'),
            ('examen', 'Examen / Évaluation'),
        ]:
            with self.subTest(note_type=note_type):
                resp = self.client.post("/api/grades/", {
                    "student": self.student.id, "subject": self.math.id,
                    "school_year": self.year.id, "period": "T1",
                    "value": "15.00", "note_type": note_type,
                }, format="json")
                self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
                self.assertEqual(resp.data["note_type"], note_type)
                self.assertEqual(resp.data["note_type_display"], expected_label)

    def test_update_grade_note_type(self):
        grade = Grade.objects.create(
            student=self.student, subject=self.math, school_year=self.year,
            teacher=self.teacher, period="T1", value=10, note_type='devoir',
        )
        resp = self.client.patch(f"/api/grades/{grade.id}/", {
            "note_type": "examen", "justification": "correction de saisie",
        }, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        grade.refresh_from_db()
        self.assertEqual(grade.note_type, 'examen')
        self.assertEqual(grade.get_note_type_display(), 'Examen / Évaluation')

    def test_filter_by_note_type_still_works(self):
        Grade.objects.create(
            student=self.student, subject=self.math, school_year=self.year,
            teacher=self.teacher, period="T1", value=12, note_type='interrogation',
        )
        Grade.objects.create(
            student=self.student, subject=self.math, school_year=self.year,
            teacher=self.teacher, period="T1", value=16, note_type='examen',
        )
        resp = self.client.get("/api/grades/?note_type=interrogation")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        rows = resp.data["results"] if isinstance(resp.data, dict) and "results" in resp.data else resp.data
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["note_type"], "interrogation")

    def test_invalid_note_type_rejected(self):
        resp = self.client.post("/api/grades/", {
            "student": self.student.id, "subject": self.math.id,
            "school_year": self.year.id, "period": "T1",
            "value": "15.00", "note_type": "Interrogation / Devoir de classe",
        }, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
