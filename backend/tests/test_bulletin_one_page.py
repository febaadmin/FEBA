"""
Le bulletin tient sur UNE page — test de référence, sur le PDF réellement produit.

DÉFAUT CORRIGÉ
--------------
Mesuré : dès 6 matières françaises et 4 anglaises, le bulletin standard
sortait sur deux pages (signatures, cachet et pied de page seuls sur la
seconde). Les tests existants (`test_bulletin_layout.py`) n'utilisaient que
2 à 4 matières : la régression était invisible.

Ce fichier passe par la base et par l'API réelles :
  - académies créées par le service (`create_academy`), primaire /10 et
    secondaire /20 ;
  - matières, classes, élèves, notes en base ; moyennes calculées par le
    modèle, jamais fournies au générateur ;
  - aperçu (POST /api/bulletins/preview/), génération (POST
    /api/bulletins/generate/), fichier PDF enregistré (celui que l'on
    télécharge), génération d'une classe entière ;
et vérifie sur chaque PDF : exactement une page A4, chaque matière, chaque
information d'identité, la moyenne générale attendue, le commentaire
complet, la zone de validation et le pied de page ; aucun caractère hors de
la page ; aucune police sous 7 pt.
"""
import datetime
from io import BytesIO

import pypdfium2 as pdfium
from django.test import TestCase, override_settings
from pypdf import PdfReader
from rest_framework.test import APIClient

from apps.accounts.models import CustomUser
from apps.bulletins import pdf_generator as G
from apps.bulletins.models import GENERAL_COMMENT_MAX_LENGTH, Bulletin
from apps.grades.models import Grade
from apps.subjects.models import Subject
from apps.students.models import Student, StudentEnrollment
from tests.academy_fixtures import build_academy

A4_W, A4_H = 595, 842
LONG_COMMENT = ("Élève sérieuse et appliquée ; des progrès très nets en expression écrite, "
                "poursuivre l'effort en calcul mental et en lecture à voix haute. ") * 9
LONG_COMMENT = LONG_COMMENT[:GENERAL_COMMENT_MAX_LENGTH]

FR_NAMES = ["Mathématiques", "Français — Expression écrite", "Lecture et compréhension",
            "Sciences de la Vie et de la Terre", "Histoire-Géographie", "Éducation civique et morale",
            "Physique-Chimie", "Éducation artistique", "Éducation physique et sportive",
            "Technologie", "Philosophie", "Économie", "Informatique", "Musique"]
EN_NAMES = ["English Language", "Reading Comprehension", "Creative Writing", "Spelling & Grammar",
            "Social Studies", "Science (English)", "Mathematics (English)", "Phonics",
            "Literature", "Public Speaking", "Drama", "Geography (English)"]


def pdf_pages(content):
    return PdfReader(BytesIO(content)).pages


def pdf_text(content):
    return " ".join(" ".join(p.extract_text() or "" for p in pdf_pages(content)).split())


def chars_outside_page(content):
    """Caractères dont la boîte déborde de la page (texte coupé à l'impression)."""
    doc = pdfium.PdfDocument(content)
    outside = 0
    for i in range(len(doc)):
        page = doc[i]
        width, height = page.get_size()
        text = page.get_textpage()
        for c in range(text.count_chars()):
            left, bottom, right, top = text.get_charbox(c)
            if right > left and (left < -0.5 or bottom < -0.5 or right > width + 0.5 or top > height + 0.5):
                outside += 1
    return outside


class Base(TestCase):
    """Une académie primaire (/10) et une secondaire (/20), créées par le service."""

    @classmethod
    def setUpTestData(cls):
        cls.root = CustomUser.objects.create_user(
            username="root1p", email="root1p@bulletin.test", password="Pass1234!", role="superadmin")
        cls.primary = build_academy("PRIM", "physical_primary", superadmin=cls.root)
        cls.secondary = build_academy("SECO", "physical_secondary", superadmin=cls.root)

    def make_class(self, built, n_fr, n_en, *, name="Zoé-Hélène Çaëlle", last="Œuvray-Adjovi de Saint-Éloi",
                    missing=(), periods=("T1",), comment=""):
        """Classe de `n_fr` + `n_en` matières, un élève noté sur `periods` (sauf `missing`)."""
        school, year = built.school, built.year
        subjects = []
        for i, nom in enumerate(FR_NAMES[:n_fr]):
            subjects.append(Subject.objects.create(school=school, name=nom, code=f"F{i}{built.tag}",
                                                   coefficient=(i % 4) + 1, language="fr"))
        for i, nom in enumerate(EN_NAMES[:n_en]):
            subjects.append(Subject.objects.create(school=school, name=nom, code=f"E{i}{built.tag}",
                                                   coefficient=(i % 3) + 1, language="en"))
        klass = built.klass
        klass.subjects.set(subjects)
        pupil = Student.objects.create(school=school, first_name=name, last_name=last,
                                       current_class=klass, school_year=year, gender="F",
                                       date_of_birth=datetime.date(2015, 3, 2))
        enrollment = StudentEnrollment.objects.create(student=pupil, school_year=year, class_obj=klass)
        for period in periods:
            for i, subject in enumerate(subjects):
                if subject.name in missing:
                    continue
                for value in (8 + (i % 11), 10 + (i % 9)):
                    Grade.objects.create(student=pupil, subject=subject, school_year=year,
                                         teacher=built.teacher, period=period, value=value,
                                         enrollment=enrollment)
        if comment:
            Bulletin.objects.create(student=pupil, school_year=year, period=periods[0],
                                    general_comment=comment)
        return pupil, subjects

    def api_for(self, built):
        client = APIClient()
        client.force_authenticate(built.admin)
        return client

    def assert_complete_one_page(self, content, pupil, subjects, built, period_label, *, comment=""):
        pages = pdf_pages(content)
        self.assertEqual(len(pages), 1, f"{len(pages)} pages")
        box = pages[0].mediabox
        self.assertEqual((round(float(box.width)), round(float(box.height))), (A4_W, A4_H))
        text = pdf_text(content)
        for subject in subjects:
            self.assertIn(" ".join(subject.name.split()), text, subject.name)
        for expected in (pupil.matricule, built.school.name.upper(), built.klass.name, period_label,
                         built.year.name, "Moyenne Générale", "La Direction", "Signature du Parent",
                         "Généré le"):
            self.assertIn(expected, text, expected)
        self.assertIn(pupil.last_name.split()[0], text)
        if comment:
            # Commentaire imprimé EN ENTIER (aucune troncature).
            self.assertIn(" ".join(comment.split())[-60:], text)
        self.assertEqual(chars_outside_page(content), 0)
        return text


class RenderedBulletinTests(Base):
    """Le moteur officiel (render_bulletin_pdf), sur des données réelles en base."""

    def render(self, pupil, built, period="T1"):
        return G.render_bulletin_pdf(pupil, period, built.year)[0]

    def test_peu_de_matieres(self):
        pupil, subjects = self.make_class(self.secondary, 2, 1)
        self.assert_complete_one_page(self.render(pupil, self.secondary), pupil, subjects,
                                      self.secondary, "1ER TRIMESTRE")

    def test_classe_reelle_et_classe_chargee(self):
        # 10 matières = maximum observé dans les données de développement ;
        # 20 et 26 : classes très chargées.
        for n_fr, n_en in ((6, 4), (10, 10), (14, 12)):
            with self.subTest(matieres=n_fr + n_en):
                Subject.objects.filter(school=self.secondary.school).exclude(
                    pk__in=[s.pk for s in self.secondary.subjects]).delete()
                pupil, subjects = self.make_class(self.secondary, n_fr, n_en, name=f"Élève{n_fr}")
                self.assert_complete_one_page(self.render(pupil, self.secondary), pupil, subjects,
                                              self.secondary, "1ER TRIMESTRE")

    def test_commentaire_maximal_et_classe_chargee(self):
        pupil, subjects = self.make_class(self.primary, 12, 10, comment=LONG_COMMENT)
        self.assert_complete_one_page(self.render(pupil, self.primary), pupil, subjects,
                                      self.primary, "1ER TRIMESTRE", comment=LONG_COMMENT)

    def test_toutes_les_periodes(self):
        pupil, subjects = self.make_class(self.secondary, 10, 8, periods=("T1", "T2", "T3"))
        for period, label in (("T1", "1ER TRIMESTRE"), ("T2", "2ÈME TRIMESTRE"),
                              ("T3", "3ÈME TRIMESTRE"), ("annual", "ANNUEL")):
            with self.subTest(period=period):
                content = self.render(pupil, self.secondary, period)
                self.assertEqual(len(pdf_pages(content)), 1)
                for subject in subjects:
                    self.assertIn(" ".join(subject.name.split()), pdf_text(content))
                self.assertIn(G._period_label(period), pdf_text(content))

    def test_notes_manquantes_imprimees_non_notees(self):
        pupil, subjects = self.make_class(self.secondary, 8, 6, missing=("Physique-Chimie", "Social Studies"))
        text = self.assert_complete_one_page(self.render(pupil, self.secondary), pupil, subjects,
                                             self.secondary, "1ER TRIMESTRE")
        self.assertIn("Non noté", text)

    def test_moyenne_generale_ponderee_et_bareme(self):
        """La moyenne imprimée est celle du modèle (coefficients), dans le barème du niveau."""
        for built, scale in ((self.secondary, 20), (self.primary, 10)):
            with self.subTest(bareme=scale):
                pupil, subjects = self.make_class(built, 6, 4, name=f"Bar{scale}")
                avg = Grade.calculate_average(pupil, built.year, "T1")
                expected = G._fmt_scale_denom(avg, scale)
                text = self.assert_complete_one_page(self.render(pupil, built), pupil, subjects,
                                                     built, "1ER TRIMESTRE")
                self.assertIn(f"Moyenne Générale {expected}", text)
                self.assertIn(f"/{scale}", expected)

    def test_noms_longs_et_accents(self):
        pupil, subjects = self.make_class(
            self.primary, 8, 6, name="Marie-Élisabeth Anne-Sophie Ìyábọ̀",
            last="Çaëlle-Œuvray de la Fontaine-Saint-Éloi d'Akpakpa Ɖɛ̀gbɔ̀ Hounŋɔn")
        text = self.assert_complete_one_page(self.render(pupil, self.primary), pupil, subjects,
                                             self.primary, "1ER TRIMESTRE")
        self.assertIn("Marie-Élisabeth", text)
        # Lettres du fon et du yoruba (ɖ, ɛ, ɔ, ŋ, ọ, tons) : imprimées telles
        # quelles, jamais remplacées par un carré.
        self.assertNotIn("■", text)
        for word in ("Ɖɛ̀gbɔ̀", "Hounŋɔn", "Ìyábọ̀"):
            self.assertIn(word, text.replace("\u00a0", " "))

    def test_deux_academies_identite_de_chacune(self):
        a, sa = self.make_class(self.primary, 6, 4, name="Prim")
        b, sb = self.make_class(self.secondary, 6, 4, name="Seco")
        ta = self.assert_complete_one_page(self.render(a, self.primary), a, sa, self.primary, "1ER TRIMESTRE")
        tb = self.assert_complete_one_page(self.render(b, self.secondary), b, sb, self.secondary, "1ER TRIMESTRE")
        self.assertNotIn(self.secondary.school.name.upper(), ta)
        self.assertNotIn(self.primary.school.name.upper(), tb)

    def test_aucune_police_sous_7_points(self):
        """Même à la densité la plus compacte, aucune police sous 7 pt (sauf le pied de page, 6 pt, historique)."""
        import re

        pupil, _ = self.make_class(self.secondary, 14, 12, comment=LONG_COMMENT[:600])
        content = self.render(pupil, self.secondary)
        self.assertEqual(len(pdf_pages(content)), 1)
        data = pdf_pages(content)[0].get_contents().get_data().decode("latin-1")
        sizes = sorted({float(x) for x in re.findall(r"/F\d+ ([\d.]+) Tf", data)})
        self.assertTrue(sizes)
        # 6 pt : seuls le pied de page « Généré le… » et la clé de notation (inchangés).
        self.assertEqual([x for x in sizes if x < 7], [x for x in sizes if x < 7 and x >= 6])
        self.assertLessEqual(len([x for x in sizes if x < 7]), 1)


class OverflowTests(Base):

    def test_classe_hors_limite_refusee_explicitement(self):
        """Au-delà de la densité la plus compacte : refus, jamais un PDF de deux pages."""
        school, year = self.secondary.school, self.secondary.year
        subjects = [Subject.objects.create(school=school, name=f"Matière supplémentaire n°{i}",
                                           code=f"X{i}", coefficient=1, language="fr" if i % 2 else "en")
                    for i in range(40)]
        self.secondary.klass.subjects.set(subjects)
        pupil = self.secondary.student
        with self.assertRaises(G.BulletinLayoutError) as ctx:
            G.render_bulletin_pdf(pupil, "T1", year)
        self.assertIn("ne tient pas sur une page", str(ctx.exception))
        client = self.api_for(self.secondary)
        r = client.post("/api/bulletins/preview/", {"student_id": pupil.pk, "school_year_id": year.pk,
                                                    "period": "T1"}, format="json")
        self.assertEqual(r.status_code, 422)
        self.assertIn("ne tient pas sur une page", r.data["error"])
        before = Bulletin.objects.filter(student=pupil).count()
        r = client.post("/api/bulletins/generate/", {"student_id": pupil.pk, "school_year_id": year.pk,
                                                     "period": "T1"}, format="json")
        self.assertEqual(r.status_code, 422)
        self.assertEqual(Bulletin.objects.filter(student=pupil, pdf_file__gt="").count(), 0)
        self.assertLessEqual(Bulletin.objects.filter(student=pupil).count(), before + 1)


@override_settings(CELERY_TASK_ALWAYS_EAGER=True)
class ApiBulletinTests(Base):
    """Aperçu, génération, fichier téléchargé, classe entière : une page chacun."""

    def test_apercu_generation_et_telechargement(self):
        pupil, subjects = self.make_class(self.secondary, 10, 8, comment=LONG_COMMENT[:800])
        client = self.api_for(self.secondary)
        payload = {"student_id": pupil.pk, "school_year_id": self.secondary.year.pk, "period": "T1"}

        r = client.post("/api/bulletins/preview/", payload, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r["Content-Type"], "application/pdf")
        text = self.assert_complete_one_page(r.content, pupil, subjects, self.secondary, "1ER TRIMESTRE",
                                             comment=LONG_COMMENT[:800])
        self.assertIn("APERÇU", text)

        r = client.post("/api/bulletins/generate/", payload, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        bulletin = Bulletin.objects.get(pk=r.data["id"])
        with bulletin.pdf_file.open("rb") as fh:
            stored = fh.read()   # le fichier servi au téléchargement et à l'impression
        text = self.assert_complete_one_page(stored, pupil, subjects, self.secondary, "1ER TRIMESTRE",
                                             comment=LONG_COMMENT[:800])
        self.assertNotIn("APERÇU", text)

    def test_classe_entiere(self):
        pupil, subjects = self.make_class(self.primary, 9, 7)
        others = []
        for k in range(3):
            other = Student.objects.create(school=self.primary.school, first_name=f"Camarade{k}",
                                           last_name="Dossou-Yovo", current_class=self.primary.klass,
                                           school_year=self.primary.year, gender="M")
            enrollment = StudentEnrollment.objects.create(student=other, school_year=self.primary.year,
                                                          class_obj=self.primary.klass)
            for i, subject in enumerate(subjects):   # un élève sans note n'a pas de bulletin
                Grade.objects.create(student=other, subject=subject, school_year=self.primary.year,
                                     teacher=self.primary.teacher, period="T1", value=9 + (i + k) % 10,
                                     enrollment=enrollment)
            others.append(other)
        from apps.bulletins.operations import apply_to_student, _new_result
        from apps.bulletins.models import BulletinOperation

        for student in [pupil, *others, self.primary.student]:
            apply_to_student(student, self.primary.year, "T1", action=BulletinOperation.ACTION_GENERATE,
                             comment="", regenerate=True, user=self.primary.admin, result=_new_result(1))
        bulletins = Bulletin.objects.filter(student__school=self.primary.school, period="T1")
        self.assertEqual(bulletins.count(), 5)
        for bulletin in bulletins:
            with bulletin.pdf_file.open("rb") as fh:
                self.assertEqual(len(pdf_pages(fh.read())), 1, bulletin.student.get_full_name())
