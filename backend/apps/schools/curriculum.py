"""
Classement du programme linguistique d'une académie EXISTANTE d'après ses
données — fonction pure, utilisée par la migration 0021 et par
`manage.py academy_languages_report`.

Règle : on ne devine jamais.
  - matières en français ET en anglais (ou matière « bilingue »)  → bilingue ;
  - toutes les matières dans une seule langue, toutes les classes déclarées
    dans le parcours monolingue correspondant, et parcours monolingues
    permis par l'académie                                           → cette langue ;
  - sinon (aucune matière, classes « bilingues » par défaut avec des
    matières d'une seule langue, …)                                 → None,
    « à configurer » par le super administrateur.
"""

# Valeurs STOCKÉES de Class.language_track (majuscules).
TRACK_FOR = {"fr": "FRANCOPHONE", "en": "ANGLOPHONE"}
MODE_FOR = {"fr": "french_only", "en": "english_only"}


def classify_curriculum(subject_languages, class_tracks, monolingual_allowed):
    """Renvoie (mode | None, motif)."""
    languages = set(subject_languages)
    tracks = set(class_tracks)
    if "bilingual" in languages or {"fr", "en"} <= languages:
        return "bilingual", "matières en français et en anglais"
    if not languages:
        return None, "aucune matière : programme impossible à déduire"
    (language,) = tuple(languages)
    if not tracks:
        return None, f"matières uniquement en « {language} » mais aucune classe"
    if tracks != {TRACK_FOR[language]}:
        return None, (f"matières uniquement en « {language} » mais classes de parcours "
                      f"{', '.join(sorted(tracks))}")
    if not monolingual_allowed:
        return None, "classes monolingues alors que l'académie ne les permet pas"
    return MODE_FOR[language], f"matières et classes uniquement en « {language} »"
