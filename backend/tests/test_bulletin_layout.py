"""
Tests de mise en page du bulletin PDF — anti-débordement (BUG N°1).

On vérifie, sur des scénarios de stress, que le bulletin :
  - tient sur UNE seule page A4 portrait (pas de 2ᵉ page involontaire) ;
  - se génère sans exception, y compris avec des intitulés de matières et
    des appréciations très longs (qui débordaient auparavant sur les
    colonnes voisines) ;
  - conserve la taille de page A4 (595 × 842 pt).

Ces tests n'exigent pas de base « complète » : ils appellent directement les
constructeurs de bulletin avec des données fabriquées, ce qui les rend
rapides et ciblés sur la mise en page.
"""
from io import BytesIO
from types import SimpleNamespace

import pytest
from pypdf import PdfReader

from apps.bulletins import pdf_generator as G
from tests.branding_fixtures import make_palette

A4_W, A4_H = 595, 842  # points (portrait)


def _ctx():
    school = SimpleNamespace(name="Groupe Scolaire FEBA",
                             address="Rue des Cocotiers, Akpakpa",
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
    bull = SimpleNamespace(appreciation="ACCEPTABLE", general_comment="", rank_in_class=None)
    return student, sy, bull


def _subj(name, lang, coeff=2, avg=12.34):
    return {"subject_id": id(name) + hash(lang) % 1000, "subject_name": name,
            "coefficient": coeff, "language": lang, "average": avg,
            "letter": "B", "meaning": "Bien",
            "trimester_avgs": {"T1": avg, "T2": avg, "T3": avg},
            "has_notes": True, "notes": []}


def _standard_pdf(fr, en, period="T1"):
    student, sy, bull = _ctx()
    subject_data = {e["subject_id"]: e for e in fr + en}
    bilingual = {"fr_average": 13.61, "en_average": 8.93, "bilingual_average": 11.74}
    stats = {"fr_min": 10.82, "fr_max": 14.71, "en_min": 8.93, "en_max": 16.39,
             "bi_min": 10.85, "bi_max": 15.33}
    buf = BytesIO()
    G._build_standard_pdf(buf, student, period, sy, subject_data, bilingual,
                          stats, 11.63, bull, make_palette())
    return buf.getvalue()


def _pages(pdf_bytes):
    return PdfReader(BytesIO(pdf_bytes)).pages


LONG_FR = "Éducation Civique, Morale et Instruction à la Citoyenneté Démocratique et Républicaine"
LONG_EN = "Social Studies and Comprehensive Citizenship Education Programme for Junior Secondary"


def test_few_subjects_single_page():
    pdf = _standard_pdf([_subj("Maths", "fr", 4)], [_subj("English", "en", 4)])
    assert len(_pages(pdf)) == 1


def test_many_subjects_single_page():
    fr = [_subj(n, "fr") for n in ["Mathématiques", "Français", "Sciences",
                                   "Histoire-Géo", "Éducation Civique", "Sport"]]
    en = [_subj(n, "en") for n in ["English", "Mathematics", "Science", "Social Studies"]]
    pdf = _standard_pdf(fr, en)
    assert len(_pages(pdf)) == 1


def test_long_subject_names_single_page_and_no_crash():
    fr = [_subj(LONG_FR, "fr"), _subj("Mathématiques", "fr")]
    en = [_subj(LONG_EN, "en"), _subj("English", "en")]
    pdf = _standard_pdf(fr, en)
    assert len(_pages(pdf)) == 1


def test_very_long_unbreakable_string_wraps():
    """Un « mot » sans espace ne doit pas forcer une largeur hors cadre."""
    fr = [_subj("Matièreeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee", "fr")]
    en = [_subj("English", "en")]
    pdf = _standard_pdf(fr, en)
    assert len(_pages(pdf)) == 1


def test_page_is_a4_portrait():
    pdf = _standard_pdf([_subj("Maths", "fr")], [_subj("English", "en")])
    box = _pages(pdf)[0].mediabox
    assert round(float(box.width)) == A4_W
    assert round(float(box.height)) == A4_H


def test_annual_period_single_page():
    fr = [_subj(n, "fr") for n in ["Mathématiques", "Français", "Sciences", LONG_FR]]
    en = [_subj(n, "en") for n in ["English", "Mathematics", LONG_EN]]
    pdf = _standard_pdf(fr, en, period="annual")
    assert len(_pages(pdf)) == 1


def test_maternelle_single_page_with_long_names():
    student, sy, bull = _ctx()
    student.current_class.level = SimpleNamespace(name="Maternelle", is_maternelle=lambda: True)
    data = [
        _subj("Langage et Communication Orale et Écrite Approfondie et Structurée", "fr", 1, 16),
        _subj("Graphisme", "fr", 1, 14),
        _subj("Reading Readiness and Phonological Awareness Development", "en", 1, 15),
    ]
    sd = {e["subject_id"]: e for e in data}
    buf = BytesIO()
    G._build_maternelle_pdf(buf, student, "T1", sy, sd, 15.0, bull, make_palette())
    assert len(_pages(buf.getvalue())) == 1
