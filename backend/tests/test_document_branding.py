"""
V7 — Priorités 1, 2, 3 : identité officielle et cachet sur les documents.

Génère un VRAI bulletin PDF et vérifie, par extraction de texte + inspection
des images embarquées :
  - le nom officiel « FAITH & EXCELLENCE BILINGUAL ACADEMY » (avec « & ») ;
  - la ligne groupe « GROUPE ÉDUCATIF FEBA » ;
  - l'ABSENCE de « GROUPE SCOLAIRE FEBA » et de « Faith Excellence » sans « & » ;
  - la présence du cachet officiel (image embarquée).
"""
from io import BytesIO
from types import SimpleNamespace

import fitz  # PyMuPDF
from django.test import SimpleTestCase

from apps.bulletins import pdf_generator as G
from tests.branding_fixtures import make_palette
from tests.test_bulletin_layout import _subj


def _bulletin_pdf(school_name="Faith & Excellence Bilingual Academy"):
    school = SimpleNamespace(name=school_name, address="Akpakpa, Cotonou",
                             city="Cotonou", country="Bénin", id=1)
    level = SimpleNamespace(name="6ème", is_maternelle=lambda: False)
    klass = SimpleNamespace(name="6ème-A", level=level, school_year=None)
    student = SimpleNamespace(
        school_id=1, school=school, current_class=klass,
        date_of_birth="2009-01-28", gender="M",
        get_full_name=lambda: "Paul Tokpanou", get_gender_display=lambda: "Masculin",
        matricule="FEBA-26-0023", school_year=None,
    )
    sy = SimpleNamespace(name="2025-2026", school_id=1, school=school)
    bull = SimpleNamespace(appreciation="ACCEPTABLE",
                           general_comment="Bon trimestre.", rank_in_class=None)
    fr = [_subj("Maths", "fr", 4, 10.0)]
    en = [_subj("English", "en", 4, 15.0)]
    subject_data = {e["subject_id"]: e for e in fr + en}
    bilingual = {"fr_average": 10.0, "en_average": 15.0, "bilingual_average": 12.0}
    stats = {"fr_min": 8.0, "fr_max": 14.0, "en_min": 9.0, "en_max": 16.0,
             "bi_min": 9.0, "bi_max": 15.0}
    buf = BytesIO()
    G._build_standard_pdf(buf, student, "T1", sy, subject_data, bilingual,
                          stats, 12.0, bull, make_palette(display_name=school_name))
    return buf.getvalue()


class BulletinBrandingTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.pdf = _bulletin_pdf()
        cls.doc = fitz.open(stream=cls.pdf, filetype="pdf")
        cls.text = "\n".join(p.get_text() for p in cls.doc)

    def test_nom_officiel_avec_esperluette(self):
        self.assertIn("FAITH & EXCELLENCE BILINGUAL ACADEMY", self.text.upper())

    def test_ligne_groupe_educatif(self):
        self.assertIn("GROUPE ÉDUCATIF FEBA", self.text)

    def test_plus_de_groupe_scolaire(self):
        self.assertNotIn("GROUPE SCOLAIRE FEBA", self.text.upper())

    def test_plus_de_nom_sans_esperluette(self):
        # « FAITH EXCELLENCE BILINGUAL ACADEMY » sans « & » ne doit plus apparaître.
        self.assertNotIn("FAITH EXCELLENCE BILINGUAL ACADEMY", self.text.upper())

    def test_cachet_embarque(self):
        images = [im for pno in range(self.doc.page_count) for im in self.doc[pno].get_images()]
        self.assertGreaterEqual(len(images), 1, "cachet absent du bulletin")

    def test_une_seule_page(self):
        self.assertEqual(self.doc.page_count, 1)
