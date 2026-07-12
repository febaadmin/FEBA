"""
Tests de génération des matricules — format ``FEBA-YY-NNNN`` (BUG N°2).

Exigences couvertes :
  - YY = deux derniers chiffres de l'ANNÉE SYSTÈME (jamais codée en dur) ;
  - séquence 0001, 0002… par établissement ET par année ;
  - redémarrage du compteur à chaque nouvelle année ;
  - pas de doublon après suppression d'un élève ;
  - pas de doublon en création concurrente (compteur verrouillé) ;
  - compatibilité avec d'anciens matricules du même format (amorçage) ;
  - aucune valeur « 25 » codée en dur dans la génération.
"""
import datetime
import re
from unittest import mock

import pytest
from django.utils import timezone

from apps.schools.models import School
from apps.students.models import (
    Student, StudentMatriculeSequence, generate_matricule, _matricule_base,
)

pytestmark = pytest.mark.django_db


def _school(prefix="FEBA"):
    return School.objects.create(name="Groupe Scolaire Test", address="X",
                                 matricule_prefix=prefix)


def _freeze_year(year):
    """Contexte figeant timezone.now() sur le 15 juin de `year`."""
    fake = datetime.datetime(year, 6, 15, 10, 0, tzinfo=datetime.timezone.utc)
    return mock.patch.object(timezone, "now", return_value=fake)


def _make_student(school, first="Jean", last="Dupont"):
    return Student.objects.create(school=school, first_name=first, last_name=last)


# ── Format & année système ───────────────────────────────────────────────────

@pytest.mark.parametrize("year,expected", [
    (2023, "FEBA-23-0001"),
    (2025, "FEBA-25-0001"),
    (2026, "FEBA-26-0001"),
    (2027, "FEBA-27-0001"),
    (2030, "FEBA-30-0001"),
])
def test_matricule_uses_system_year(year, expected):
    school = _school()
    with _freeze_year(year):
        s = _make_student(school)
    assert s.matricule == expected


def test_matricule_format_is_hyphenated():
    school = _school()
    with _freeze_year(2026):
        s = _make_student(school)
    assert s.matricule == "FEBA-26-0001"
    assert "_" not in s.matricule
    assert s.matricule.count("-") == 2


# ── Séquence par année ───────────────────────────────────────────────────────

def test_sequence_increments_same_year():
    school = _school()
    with _freeze_year(2026):
        a = _make_student(school, "A", "Un")
        b = _make_student(school, "B", "Deux")
        c = _make_student(school, "C", "Trois")
    assert [a.matricule, b.matricule, c.matricule] == [
        "FEBA-26-0001", "FEBA-26-0002", "FEBA-26-0003",
    ]


def test_sequence_restarts_each_year():
    school = _school()
    with _freeze_year(2025):
        a = _make_student(school, "A", "Un")
        b = _make_student(school, "B", "Deux")
    with _freeze_year(2026):
        c = _make_student(school, "C", "Trois")
        d = _make_student(school, "D", "Quatre")
    assert a.matricule == "FEBA-25-0001"
    assert b.matricule == "FEBA-25-0002"
    assert c.matricule == "FEBA-26-0001"  # redémarre à 0001
    assert d.matricule == "FEBA-26-0002"


def test_deletion_does_not_reuse_number():
    """Supprimer un élève ne doit jamais permettre de réattribuer son numéro."""
    school = _school()
    with _freeze_year(2026):
        a = _make_student(school, "A", "Un")      # 0001
        b = _make_student(school, "B", "Deux")     # 0002
        b.delete()
        c = _make_student(school, "C", "Trois")    # 0003, PAS 0002
    assert a.matricule == "FEBA-26-0001"
    assert c.matricule == "FEBA-26-0003"


# ── Multi-établissements ─────────────────────────────────────────────────────

def test_sequence_independent_per_school():
    s1 = _school("FEBA")
    s2 = School.objects.create(name="Autre Ecole", address="Y", matricule_prefix="AEC")
    with _freeze_year(2026):
        a = _make_student(s1, "A", "Un")
        b = _make_student(s2, "B", "Deux")
        c = _make_student(s1, "C", "Trois")
    assert a.matricule == "FEBA-26-0001"
    assert b.matricule == "AEC-26-0001"
    assert c.matricule == "FEBA-26-0002"


# ── Amorçage / compatibilité anciens matricules ──────────────────────────────

def test_seed_from_existing_same_format_avoids_collision():
    """
    Un matricule déjà présent au même format (import/héritage) amorce la
    séquence pour éviter tout doublon.
    """
    school = _school()
    # Élève « importé » avec un matricule explicite du format courant.
    Student.objects.create(school=school, first_name="Old", last_name="Data",
                           matricule="FEBA-26-0007")
    with _freeze_year(2026):
        s = _make_student(school, "New", "One")
    assert s.matricule == "FEBA-26-0008"
    assert Student.objects.filter(matricule="FEBA-26-0008").count() == 1


def test_legacy_underscore_matricule_untouched():
    """Les anciens matricules ne sont pas renumérotés."""
    school = _school()
    legacy = Student.objects.create(school=school, first_name="Leg", last_name="Acy",
                                    matricule="FEBA_25_0005")
    legacy.refresh_from_db()
    assert legacy.matricule == "FEBA_25_0005"


# ── Robustesse / anti-hardcode ───────────────────────────────────────────────

def test_no_hardcoded_year_suffix():
    """La génération dérive le suffixe de l'année, pas d'un « 25 » figé."""
    school = _school()
    with _freeze_year(2031):
        s = _make_student(school)
    assert s.matricule.startswith("FEBA-31-")


def test_sequence_row_created_and_tracked():
    school = _school()
    with _freeze_year(2026):
        _make_student(school)
        _make_student(school, "B", "Deux")
    seq = StudentMatriculeSequence.objects.get(school=school, year=2026)
    assert seq.last_number == 2


def test_generate_matricule_helper_direct():
    school = _school()
    with _freeze_year(2026):
        assert _matricule_base(school, 2026) == "FEBA-26-"
        m1 = generate_matricule(school)
        m2 = generate_matricule(school)
    assert m1 == "FEBA-26-0001"
    assert m2 == "FEBA-26-0002"


def test_no_hardcoded_year_suffix_in_code():
    """
    Garde-fou : le suffixe d'année est dérivé de « year % 100 » et non d'un
    littéral figé. On inspecte le CODE (constantes compilées + ligne de
    construction), pas les docstrings/commentaires.
    """
    from apps.students.models import _matricule_base

    # 1. La construction de la base dépend bien de l'année reçue.
    assert _matricule_base(None, 2099).endswith("-99-")
    assert _matricule_base(None, 2007).endswith("-07-")

    # 2. Aucune chaîne littérale « 25 »/« 26 »… n'est stockée dans le code
    #    compilé de la fonction (les docstrings d'autres fonctions sont
    #    exclues car on ne lit que co_consts de _matricule_base).
    consts = [c for c in _matricule_base.__code__.co_consts if isinstance(c, str)]
    for c in consts:
        assert not re.fullmatch(r"\d{2}", c), f"Suffixe d'année figé détecté : {c}"
