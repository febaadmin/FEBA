"""
Le bulletin suit le PARCOURS LINGUISTIQUE DÉCLARÉ de la classe.

LE DÉFAUT CORRIGÉ
-----------------
Le bulletin standard imprimait toujours les deux parties. Pour une classe
francophone de FEBA FHA, chaque trimestre sortait donc avec :

    ACADEMIC RESULTS — ENGLISH SECTION / PARTIE ANGLAISE
    Aucune matière dans cette catégorie / No subject in this category.

    Moyenne Anglaise / English Average    —    —    —    —
    Moyenne Bilingue / Bilingual Average  …
    Formule bilingue : (Moyenne Française × 60%) + (Moyenne Anglaise × 40%)

Un document officiel remis aux parents annonçait un manque là où il n'y
avait rien à manquer, et affichait une moyenne pondérée par une langue que
la classe n'enseigne pas.

LA LIMITE À NE PAS FRANCHIR
---------------------------
« Adapter » ne veut pas dire « masquer ». Une classe BILINGUE à laquelle
il manque une langue continue d'afficher la section vide : c'est une
anomalie de configuration, et la taire la rendrait invisible. De même, des
notes anglaises présentes sur une classe déclarée francophone restent
imprimées — on ne perd jamais un résultat réel à cause d'une étiquette.

RÈGLE §37 — AUCUNE RÉGRESSION FEBA
----------------------------------
FEBA est bilingue : toutes ses classes valent BILINGUAL (valeur par
défaut du champ). `test_feba_bilingue_inchange` fixe cette sortie.
"""
from io import BytesIO
from types import SimpleNamespace

from pypdf import PdfReader

from apps.bulletins import pdf_generator as G
from apps.classes.models import Class
from apps.schools.models import Level
from tests.branding_fixtures import make_palette


SECTION_EN = "ENGLISH SECTION"
SECTION_FR = "PARTIE FRANÇAISE"
VIDE = "Aucune matière dans cette catégorie"
MOY_EN = "Moyenne Anglaise"
MOY_FR = "Moyenne Française"
MOY_BI = "Moyenne Bilingue"
FORMULE = "Bilingual formula"


def _ctx(track):
    """Un élève dont la classe déclare le parcours `track`."""
    school = SimpleNamespace(name="FEBA French Heritage Academy",
                             address="Cotonou", city="Cotonou",
                             country="Bénin", id=2)
    # De vraies instances (non sauvegardées) : le test porte sur les
    # méthodes réelles du modèle, pas sur une imitation qui pourrait mentir.
    level = Level(name="CM2", cycle="primaire", order=5)
    klass = Class(name="Junior Roots", language_track=track, level=level)
    student = SimpleNamespace(
        school_id=2, school=school, current_class=klass,
        date_of_birth="2014-03-02", gender="F",
        get_full_name=lambda: "Awa Koffi",
        get_gender_display=lambda: "Féminin",
        matricule="FHA-26-0007", school_year=None,
    )
    sy = SimpleNamespace(name="2025-2026", school_id=2, school=school)
    bull = SimpleNamespace(appreciation="EXCELLENT", general_comment="",
                           rank_in_class=None)
    return student, sy, bull, klass


def _subj(name, lang, coeff=2, avg=14.5):
    return {"subject_id": abs(hash((name, lang))) % 100000, "subject_name": name,
            "coefficient": coeff, "language": lang, "average": avg,
            "letter": "B", "meaning": "Bien",
            "trimester_avgs": {"T1": avg, "T2": avg, "T3": avg},
            "has_notes": True, "notes": []}


def _texte(track, fr, en, bilingual=None):
    """Texte du bulletin produit pour une classe de parcours `track`."""
    student, sy, bull, klass = _ctx(track)
    subject_data = {e["subject_id"]: e for e in fr + en}
    # Les moyennes suivent le scénario : une classe sans matière anglaise
    # n'a pas de moyenne anglaise. Fournir un chiffre là où il n'y a rien
    # ferait passer le test pour de mauvaises raisons.
    if bilingual is None:
        bilingual = {
            "fr_average": 14.5 if fr else None,
            "en_average": 12.0 if en else None,
            "bilingual_average": 13.5 if (fr and en) else None,
        }
    stats = {"fr_min": 9.0, "fr_max": 17.0, "en_min": 8.0, "en_max": 16.0,
             "bi_min": 9.5, "bi_max": 16.5}
    buf = BytesIO()
    G._build_standard_pdf(
        buf, student, "T1", sy, subject_data, bilingual, stats, 13.5, bull,
        make_palette(), expected_languages=G._expected_languages(klass),
    )
    pages = PdfReader(BytesIO(buf.getvalue())).pages
    return "\n".join(p.extract_text() or "" for p in pages)


# ── Le parcours déclaré pilote les sections ──────────────────────────────

def test_feba_bilingue_inchange():
    """§37 : la sortie historique de FEBA reste identique."""
    texte = _texte(Class.TRACK_BILINGUAL,
                   [_subj("Mathématiques", "fr")], [_subj("English", "en")])
    for attendu in (SECTION_FR, SECTION_EN, MOY_FR, MOY_EN, MOY_BI, FORMULE):
        assert attendu in texte, f"disparu du bulletin bilingue : {attendu}"


def test_classe_francophone_sans_partie_anglaise():
    texte = _texte(Class.TRACK_FRANCOPHONE, [_subj("Mathématiques", "fr")], [])
    assert SECTION_FR in texte
    assert SECTION_EN not in texte, "la partie anglaise vide est toujours imprimée"
    assert VIDE not in texte, "le bulletin annonce encore une matière manquante"
    assert MOY_FR in texte
    assert MOY_EN not in texte
    assert MOY_BI not in texte, "moyenne bilingue sur une classe monolingue"
    assert FORMULE not in texte


def test_classe_anglophone_sans_partie_francaise():
    texte = _texte(Class.TRACK_ANGLOPHONE, [], [_subj("Mathematics", "en")])
    assert SECTION_EN in texte
    assert SECTION_FR not in texte
    assert VIDE not in texte
    assert MOY_EN in texte
    assert MOY_FR not in texte
    assert MOY_BI not in texte


# ── Les deux limites : on ne masque ni anomalie ni résultat ──────────────

def test_classe_bilingue_incomplete_montre_toujours_le_manque():
    """Une anomalie de configuration reste visible."""
    texte = _texte(Class.TRACK_BILINGUAL, [_subj("Mathématiques", "fr")], [])
    assert SECTION_EN in texte
    assert VIDE in texte, "le manque d'une langue attendue a été masqué"


def test_des_notes_dans_une_langue_non_attendue_restent_imprimees():
    """Une étiquette de classe ne fait pas disparaître des résultats réels."""
    texte = _texte(Class.TRACK_FRANCOPHONE,
                   [_subj("Mathématiques", "fr")],
                   [_subj("English Club", "en")])
    assert SECTION_EN in texte
    assert "English Club" in texte, "une note existante a été supprimée du bulletin"


# ── Le repli quand la classe est inconnue ────────────────────────────────

def test_sans_classe_le_bulletin_reste_bilingue():
    """Un bulletin ne perd jamais une section par accident."""
    assert G._expected_languages(None) == ("fr", "en")


def test_un_objet_sans_parcours_reste_bilingue():
    # Un modèle plus ancien, ou tout objet qui n'expose pas la méthode.
    assert G._expected_languages(SimpleNamespace(name="X")) == ("fr", "en")


def test_le_parcours_vient_bien_du_modele():
    assert G._expected_languages(Class(language_track=Class.TRACK_FRANCOPHONE)) == ("fr",)
    assert G._expected_languages(Class(language_track=Class.TRACK_ANGLOPHONE)) == ("en",)
    assert G._expected_languages(Class(language_track=Class.TRACK_BILINGUAL)) == ("fr", "en")
