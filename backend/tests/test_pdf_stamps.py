"""
V8 — Priorités 6 & 7 : cachets et mise en page des documents officiels.

Règle stricte : deux autorités distinctes, deux cachets.
  - BULLETIN → cachet « LA DIRECTION » (cachet_feba.png)
  - REÇU     → cachet « LE SECRETARIAT » (cachet_secretariat.png)
Les intervertir est interdit.

Le reçu ne doit plus comporter « Signature du Caissier » ni « Cachet de
l'École / School Stamp » : une seule zone de validation « Le Secrétariat ».
"""
import hashlib
import os
from decimal import Decimal
from io import BytesIO

import fitz  # PyMuPDF
from django.test import SimpleTestCase, TestCase

from apps.grades.models import Grade, get_appreciation
from apps.schools.models import Level, School, SchoolYear
from apps.students.models import Student
from apps.subjects.models import Subject
from apps.classes.models import Class

STATIC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                      "feba_project", "static_files")
DIRECTION_STAMP = os.path.join(STATIC, "cachet_feba.png")
SECRETARIAT_STAMP = os.path.join(STATIC, "cachet_secretariat.png")


def _sha(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


# ── Identification du cachet réellement embarqué ────────────────────────────
# ReportLab ré-encode les images : comparer les octets du fichier source à ceux
# extraits du PDF ne fonctionne pas. On compare donc la SIGNATURE VISUELLE de
# la bande de texte du cachet (« LA DIRECTION » vs « LE SECRETARIAT »), seule
# zone où les deux sceaux diffèrent. Robuste au ré-échantillonnage (distance
# ≈ 2/1024 pour un même cachet, ≈ 223/1024 entre les deux cachets).
_SAME_STAMP_MAX_DISTANCE = 40


def _flatten(img):
    from PIL import Image as PILImage
    img = img.convert("RGBA")
    background = PILImage.new("RGBA", img.size, (255, 255, 255, 255))
    return PILImage.alpha_composite(background, img).convert("L")


def _stamp_signature(img):
    from PIL import Image as PILImage
    grey = _flatten(img)
    width, height = grey.size
    band = grey.crop((int(.10 * width), int(.55 * height),
                      int(.90 * width), int(.80 * height)))
    band = band.resize((64, 16), PILImage.LANCZOS)
    pixels = list(band.get_flattened_data())
    average = sum(pixels) / len(pixels)
    return "".join("1" if p > average else "0" for p in pixels)


def _distance(a, b):
    return sum(x != y for x, y in zip(a, b))


def _signature_of_file(path):
    from PIL import Image as PILImage
    with PILImage.open(path) as img:
        return _stamp_signature(img)


def _embedded_stamp_signatures(doc):
    """Signatures visuelles des images embarquées dans le PDF."""
    from PIL import Image as PILImage
    signatures = []
    for page_no in range(doc.page_count):
        for info in doc[page_no].get_images(full=True):
            data = doc.extract_image(info[0])["image"]
            try:
                with PILImage.open(BytesIO(data)) as img:
                    signatures.append(_stamp_signature(img))
            except Exception:
                continue
    return signatures


def _contains_stamp(doc, stamp_path):
    reference = _signature_of_file(stamp_path)
    return any(_distance(reference, sig) <= _SAME_STAMP_MAX_DISTANCE
               for sig in _embedded_stamp_signatures(doc))


class StampAssetsTests(SimpleTestCase):
    def test_les_deux_cachets_existent_et_sont_distincts(self):
        self.assertTrue(os.path.exists(DIRECTION_STAMP), "cachet Direction manquant")
        self.assertTrue(os.path.exists(SECRETARIAT_STAMP), "cachet Secrétariat manquant")
        self.assertNotEqual(_sha(DIRECTION_STAMP), _sha(SECRETARIAT_STAMP),
                            "les deux cachets doivent être des fichiers différents")

    def test_cachets_carres_et_haute_definition(self):
        from PIL import Image as PILImage
        for path in (DIRECTION_STAMP, SECRETARIAT_STAMP):
            with PILImage.open(path) as img:
                self.assertEqual(img.width, img.height,
                                 f"{os.path.basename(path)} : le cercle doit rester carré (non déformé)")
                self.assertGreaterEqual(img.width, 500,
                                        f"{os.path.basename(path)} : résolution insuffisante pour l'impression")


class ReceiptStampTests(TestCase):
    """P6 — le reçu porte « Le Secrétariat » et son cachet, et rien d'autre."""

    @classmethod
    def setUpTestData(cls):
        from apps.accounts.models import CustomUser
        from apps.payments.models import Payment
        cls.school = School.objects.create(name="Faith & Excellence Bilingual Academy",
                                           address="Akpakpa, Cotonou")
        cls.year = SchoolYear.objects.create(
            school=cls.school, name="2025-2026",
            start_date="2025-09-01", end_date="2026-07-31", is_current=True)
        level = Level.objects.create(school=cls.school, name="CM2", order=11)
        klass = Class.objects.create(name="CM2-A", level=level, school_year=cls.year)
        cls.student = Student.objects.create(
            school=cls.school, first_name="Ayo", last_name="Codjo",
            current_class=klass, school_year=cls.year)
        cls.cashier = CustomUser.objects.create_user(
            username="caisse", email="caisse@test.bj", password="Pass1234!",
            role="admin", first_name="C", last_name="A", school=cls.school)
        cls.payment = Payment.objects.create(
            student=cls.student, school_year=cls.year, amount=Decimal("150000"),
            payment_type="tuition", payment_method="cash", received_by=cls.cashier)

    def _receipt(self, payment=None):
        from apps.payments.pdf_generator import generate_receipt
        payment = payment or self.payment
        generate_receipt(payment)
        payment.refresh_from_db()
        data = payment.receipt_file.read()
        return data, fitz.open(stream=data, filetype="pdf")

    def test_mentions_supprimees(self):
        _, doc = self._receipt()
        text = "\n".join(p.get_text() for p in doc)
        self.assertNotIn("Signature du Caissier", text)
        self.assertNotIn("Cachet de l'École", text)
        self.assertNotIn("School Stamp", text)

    def test_zone_le_secretariat_presente(self):
        _, doc = self._receipt()
        text = "\n".join(p.get_text() for p in doc)
        self.assertIn("Le Secrétariat", text)

    def test_utilise_le_cachet_du_secretariat_et_pas_celui_de_la_direction(self):
        _, doc = self._receipt()
        self.assertTrue(_contains_stamp(doc, SECRETARIAT_STAMP),
                        "le cachet du SECRÉTARIAT doit figurer sur le reçu")
        self.assertFalse(_contains_stamp(doc, DIRECTION_STAMP),
                         "le cachet de la DIRECTION ne doit JAMAIS figurer sur un reçu")

    def test_reste_sur_une_page_a4(self):
        _, doc = self._receipt()
        self.assertEqual(doc.page_count, 1)
        rect = doc[0].rect
        self.assertEqual(round(rect.width), 595)
        self.assertEqual(round(rect.height), 842)

    def test_cachet_dans_la_page_et_sans_chevauchement_du_montant(self):
        """Le cachet reste dans la page et ne recouvre pas le montant."""
        _, doc = self._receipt()
        page = doc[0]
        stamp_rects = [page.get_image_bbox(i) for i in page.get_images(full=True)]
        self.assertTrue(stamp_rects, "aucune image trouvée sur le reçu")
        montant_spans = page.search_for("150")
        for rect in stamp_rects:
            self.assertGreaterEqual(rect.x0, 0)
            self.assertLessEqual(rect.x1, page.rect.width)
            self.assertLessEqual(rect.y1, page.rect.height)
            for m in montant_spans:
                self.assertFalse(rect.intersects(m),
                                 "le cachet ne doit pas recouvrir le montant")

    def test_montant_eleve_et_identite_longue(self):
        """Reçu « limite » : identité longue + gros montant → toujours 1 page."""
        from apps.payments.models import Payment
        self.student.first_name = "Marie-Emmanuelle Christiane"
        self.student.last_name = "Hounkpatin-Adjovi De Souza"
        self.student.save()
        payment = Payment.objects.create(
            student=self.student, school_year=self.year, amount=Decimal("1250000"),
            payment_type="tuition", payment_method="transfer",
            received_by=self.cashier,
            notes="Paiement partiel — solde restant à régler avant la fin du trimestre.")
        _, doc = self._receipt(payment)
        text = "\n".join(p.get_text() for p in doc)
        self.assertEqual(doc.page_count, 1)
        self.assertIn("Le Secrétariat", text)
        self.assertNotIn("Signature du Caissier", text)


class BulletinStampTests(TestCase):
    """P7 — zone de validation Direction propre, cachet non interverti."""

    @classmethod
    def setUpTestData(cls):
        cls.school = School.objects.create(name="Faith & Excellence Bilingual Academy",
                                           address="Akpakpa, Cotonou")
        cls.year = SchoolYear.objects.create(
            school=cls.school, name="2025-2026",
            start_date="2025-09-01", end_date="2026-07-31", is_current=True)
        cls.subject = Subject.objects.create(school=cls.school, name="Maths", code="MATH",
                                             coefficient=4, language="fr")

    def _bulletin(self, comment="Bon trimestre.", subjects=1, level_order=11):
        from apps.bulletins import pdf_generator as G
        level = Level.objects.create(school=self.school, name="CM2",
                                     order=level_order, cycle="primaire")
        klass = Class.objects.create(name="CM2-A", level=level, school_year=self.year)
        student = Student.objects.create(
            school=self.school, first_name="Ayo", last_name="Codjo",
            current_class=klass, school_year=self.year)
        subs = [self.subject]
        for i in range(subjects - 1):
            subs.append(Subject.objects.create(school=self.school, name=f"Matière {i}",
                                               code=f"M{i}", coefficient=2, language="fr"))
        klass.subjects.set(subs)
        for sub in subs:
            Grade.objects.create(student=student, subject=sub, school_year=self.year,
                                 period="T1", value=Decimal("12"), note_type="devoir")

        average = Grade.calculate_average(student, self.year, "T1")
        data = Grade.get_subject_averages(student, self.year, "T1")
        bilingual = Grade.calculate_bilingual_averages(student, self.year, "T1")
        bulletin = type("B", (), {"appreciation": get_appreciation(average),
                                  "general_comment": comment, "rank_in_class": None})()
        buf = BytesIO()
        G._build_standard_pdf(buf, student, "T1", self.year, data, bilingual, {},
                              average, bulletin, None)
        return fitz.open(stream=buf.getvalue(), filetype="pdf")

    def test_intitule_direction_present(self):
        doc = self._bulletin()
        text = "\n".join(p.get_text() for p in doc)
        self.assertIn("La Direction", text)

    def test_utilise_le_cachet_direction_et_pas_celui_du_secretariat(self):
        doc = self._bulletin()
        self.assertTrue(_contains_stamp(doc, DIRECTION_STAMP),
                        "le cachet de la DIRECTION doit figurer sur le bulletin")
        self.assertFalse(_contains_stamp(doc, SECRETARIAT_STAMP),
                         "le cachet du SECRÉTARIAT ne doit JAMAIS figurer sur un bulletin")

    def test_cachet_ne_deborde_pas_et_garde_une_marge_droite(self):
        doc = self._bulletin()
        page = doc[0]
        rects = [page.get_image_bbox(i) for i in page.get_images(full=True)]
        stamps = [r for r in rects if r.y0 > page.rect.height * 0.5]  # zone basse
        self.assertTrue(stamps, "cachet absent de la zone de validation")
        for rect in stamps:
            self.assertLessEqual(rect.x1, page.rect.width - 20,
                                 "le cachet est trop proche du bord droit")
            self.assertLessEqual(rect.y1, page.rect.height - 20,
                                 "le cachet est trop bas dans la page")
            # Cercle non déformé : la boîte reste (quasi) carrée.
            ratio = rect.width / rect.height
            self.assertAlmostEqual(ratio, 1.0, delta=0.05,
                                   msg="le cachet ne doit pas être étiré")

    def test_cachet_ne_chevauche_ni_la_date_ni_le_titre(self):
        doc = self._bulletin()
        page = doc[0]
        rects = [page.get_image_bbox(i) for i in page.get_images(full=True)]
        stamps = [r for r in rects if r.y0 > page.rect.height * 0.5]
        for label in ("La Direction", "Cotonou, le"):
            for target in page.search_for(label):
                for stamp in stamps:
                    self.assertFalse(stamp.intersects(target),
                                     f"le cachet chevauche « {label} »")

    def test_bulletin_court_et_bulletin_charge_restent_coherents(self):
        for subjects, comment in ((1, ""), (10, "Commentaire très détaillé. " * 20)):
            doc = self._bulletin(comment=comment, subjects=subjects)
            text = "\n".join(p.get_text() for p in doc)
            self.assertIn("La Direction", text)
            self.assertTrue(_contains_stamp(doc, DIRECTION_STAMP),
                            "le cachet doit rester avec sa zone de validation")

    def test_college_conserve_le_cachet_direction(self):
        doc = self._bulletin(level_order=12)
        self.assertTrue(_contains_stamp(doc, DIRECTION_STAMP))
        self.assertFalse(_contains_stamp(doc, SECRETARIAT_STAMP))


class ReceiptTextWrapTests(ReceiptStampTests):
    """V8 — aucun texte tronqué au bord droit du reçu.

    ReportLab ne coupe jamais une simple chaîne : une observation longue (ou
    une identité très longue) débordait de sa colonne et se retrouvait
    TRONQUÉE à l'impression. Les valeurs sont désormais des Paragraph.
    """

    def test_observation_longue_entierement_presente(self):
        from apps.payments.models import Payment
        note = ("Frais d'inscription, fournitures, cantine, transport et "
                "activités parascolaires pour l'année complète, réglés en une "
                "seule fois par chèque de banque.")
        payment = Payment.objects.create(
            student=self.student, school_year=self.year, amount=Decimal("1250000"),
            payment_type="registration", payment_method="cheque",
            received_by=self.cashier, notes=note)
        _, doc = self._receipt(payment)
        text = " ".join(" ".join(p.get_text().split()) for p in doc)
        # Le DERNIER mot doit être présent : preuve que rien n'est coupé.
        self.assertIn("banque", text, "l'observation est tronquée dans le reçu")
        self.assertIn("parascolaires", text)

    def test_identite_longue_entierement_presente(self):
        from apps.payments.models import Payment
        self.student.first_name = "Marie-Emmanuelle Christiane"
        self.student.last_name = "Hounkpatin-Adjovi De Souza"
        self.student.save()
        payment = Payment.objects.create(
            student=self.student, school_year=self.year, amount=Decimal("75000"),
            payment_type="tuition", payment_method="cash", received_by=self.cashier)
        _, doc = self._receipt(payment)
        text = " ".join(" ".join(p.get_text().split()) for p in doc)
        self.assertIn("Hounkpatin-Adjovi De Souza", text)
