"""
apps/classes/subject_rules.py — quelles matières une classe peut porter.

POURQUOI CE MODULE EXISTE
-------------------------
L'écran « Matières » d'une classe francophone de FEBA FHA affichait :

    Cette classe est francophone : seules les matières françaises
    sont attendues.
    Configuration complète ✓ — 4 matière(s) FR

puis refusait l'enregistrement :

    Sélectionnez au moins une matière anglaise.

Deux logiques métier contradictoires cohabitaient dans le même écran :
l'affichage suivait le parcours déclaré de la classe, la garde de
soumission appliquait encore « une matière française ET une anglaise »,
écrite en dur. L'utilisateur voyait une configuration valide qu'il lui
était impossible d'enregistrer.

CE QUE L'AUDIT A TROUVÉ EN PLUS
-------------------------------
Le backend, lui, ne validait RIEN. Les deux chemins d'écriture
(`ClassViewSet.manage_subjects` et `ClassSerializer._set_subjects`)
faisaient tous deux :

    Subject.objects.filter(id__in=subject_ids)

sans restriction d'académie. N'importe quel identifiant posté était
accepté — y compris une matière appartenant à l'AUTRE académie. La règle
métier n'existait que côté navigateur, là où elle ne protège rien.

Ce module est donc la seule autorité : les deux chemins d'écriture
passent par lui, et le frontend ne fait plus que refléter sa décision.

LA DÉCISION DÉPEND DE DEUX CHOSES, PAS D'UNE
--------------------------------------------
Le parcours déclaré de la classe ne suffit pas. Faith & Excellence
Bilingual Academy est bilingue par construction : c'est son identité,
pas un réglage. FEBA French Heritage Academy accueille au contraire des
enfants de la diaspora dont certains ne suivent que le français ou que
l'anglais.

L'autorisation des parcours monolingues est donc portée par l'ACADÉMIE,
via la matrice de fonctionnalités déjà vérifiée côté serveur
(`School.features`). Pour une académie qui ne les autorise pas, le
parcours effectif est BILINGUE quelle que soit la valeur stockée — une
donnée corrompue ou un `language_track` posté ne peut pas transformer
une classe de FEBA en classe monolingue. C'est ce qui rend la
non-régression de FEBA structurelle plutôt que promise.
"""
from __future__ import annotations

#: Drapeau de fonctionnalité qui autorise les parcours monolingues.
#: Voir `School.FEATURE_FLAGS` — faux pour un campus, vrai pour une
#: académie en ligne.
FEATURE_MONOLINGUAL = "monolingual_classes"

#: Libellé humain d'une langue de matière, dans les deux nombres.
LANGUAGE_LABELS = {
    "fr": ("française", "françaises"),
    "en": ("anglaise", "anglaises"),
}


def academy_of(classroom):
    """Académie propriétaire de la classe, ou None si la chaîne est cassée."""
    year = getattr(classroom, "school_year", None)
    return getattr(year, "school", None) if year is not None else None


def allows_monolingual(school) -> bool:
    """
    Vrai si cette académie autorise des classes monolingues.

    Une académie inconnue renvoie False : on n'AFFIRME jamais qu'un
    parcours monolingue est autorisé sans en avoir la preuve. Voir
    `forbids_monolingual` pour la question inverse, qui n'est pas la
    négation de celle-ci.
    """
    if school is None:
        return False
    has_feature = getattr(school, "has_feature", None)
    return bool(has_feature(FEATURE_MONOLINGUAL)) if callable(has_feature) else False


def forbids_monolingual(school) -> bool:
    """
    Vrai seulement si l'académie est CONNUE et interdit le monolingue.

    « Inconnue » et « interdit » ne sont pas la même chose, et les
    confondre a un coût réel. Forcer BILINGUAL dès que l'académie n'est
    pas résolvable faisait réapparaître, sur le bulletin d'une classe
    francophone, la partie anglaise vide et la moyenne bilingue pondérée
    par une langue absente — exactement ce que le parcours déclaré sert à
    supprimer.

    Le renversement ne coûte aucune protection : `school_year` puis
    `school` sont des clés étrangères non nulles, donc toute classe
    ENREGISTRÉE a une académie. Le cas « inconnue » ne se rencontre que
    sur un objet non sauvegardé, hors de portée d'un attaquant. Et un
    `language_track` posté sur une classe de FEBA est bien intercepté :
    là, l'académie est connue et interdit le monolingue.
    """
    return school is not None and not allows_monolingual(school)


def effective_track(classroom) -> str:
    """
    Parcours RÉELLEMENT appliqué à cette classe.

    C'est le parcours déclaré, sauf pour une académie qui n'autorise pas
    les parcours monolingues : là, il vaut toujours BILINGUAL. Une valeur
    stockée ou postée ne peut donc pas rendre monolingue une classe d'une
    académie bilingue par construction.
    """
    from .models import Class

    declared = getattr(classroom, "language_track", None) or Class.TRACK_BILINGUAL
    if declared not in Class.TRACK_LANGUAGES:
        declared = Class.TRACK_BILINGUAL
    if declared != Class.TRACK_BILINGUAL and forbids_monolingual(academy_of(classroom)):
        return Class.TRACK_BILINGUAL
    return declared


def allowed_languages(classroom) -> tuple:
    """
    Langues de matières que cette classe a le droit de porter.

    Un parcours monolingue est STRICT : une classe francophone n'accepte
    pas de matière anglaise. Sans cela, une matière glissée par erreur
    ressort ensuite dans le bulletin, dans les moyennes et dans l'emploi
    du temps, sans que rien ne l'ait jamais annoncée.
    """
    from .models import Class

    return Class.TRACK_LANGUAGES[effective_track(classroom)]


def required_languages(classroom) -> tuple:
    """
    Langues dont au moins une matière est obligatoire.

    Identiques aux langues autorisées : chaque langue du parcours doit
    être enseignée, aucune autre n'est admise.
    """
    return allowed_languages(classroom)


def _plural(lang, count):
    singulier, pluriel = LANGUAGE_LABELS.get(lang, (lang, lang))
    return pluriel if count > 1 else singulier


def validate_subject_configuration(classroom, subjects) -> list:
    """
    Vérifie une liste de matières pour cette classe.

    Renvoie la liste des motifs de refus, vide si la configuration est
    valide. Ne lève pas : l'appelant décide s'il répond 400, s'il affiche
    un avertissement, ou s'il journalise.

    Trois familles de refus, dans cet ordre de lecture :
      1. une matière n'appartient pas à l'académie de la classe ;
      2. une matière est dans une langue que le parcours n'admet pas ;
      3. une langue attendue par le parcours n'est pas enseignée.
    """
    erreurs = []
    subjects = list(subjects or [])

    ecole = academy_of(classroom)
    if ecole is not None:
        intruses = [s for s in subjects if getattr(s, "school_id", None) != ecole.id]
        if intruses:
            noms = ", ".join(sorted(s.name for s in intruses))
            erreurs.append(
                f"Ces matières n'appartiennent pas à {ecole.name} : {noms}."
            )
            # Les matières d'une autre académie sont écartées de la suite :
            # leur langue n'a pas à décider du parcours de cette classe.
            subjects = [s for s in subjects if getattr(s, "school_id", None) == ecole.id]

    autorisees = allowed_languages(classroom)
    hors_parcours = [s for s in subjects if getattr(s, "language", None) not in autorisees]
    if hors_parcours:
        par_langue = {}
        for s in hors_parcours:
            par_langue.setdefault(getattr(s, "language", "?"), []).append(s.name)
        for lang, noms in sorted(par_langue.items()):
            erreurs.append(
                f"Cette classe n'enseigne pas les matières "
                f"{_plural(lang, len(noms))} : {', '.join(sorted(noms))}."
            )

    presentes = {getattr(s, "language", None) for s in subjects}
    for lang in required_languages(classroom):
        if lang not in presentes:
            erreurs.append(
                f"Sélectionnez au moins une matière {_plural(lang, 1)}."
            )
    return erreurs


def missing_languages(classroom) -> list:
    """Langues attendues sans aucune matière ENREGISTRÉE sur la classe."""
    presentes = set(classroom.subjects.values_list("language", flat=True))
    return [lang for lang in required_languages(classroom) if lang not in presentes]


def describe(classroom) -> dict:
    """
    Ce que le frontend doit savoir pour refléter la règle sans la
    réinventer : le parcours effectif, ce qui est admis, ce qui manque.
    """
    return {
        "language_track": effective_track(classroom),
        "allowed_languages": list(allowed_languages(classroom)),
        "required_languages": list(required_languages(classroom)),
        "missing_languages": missing_languages(classroom),
        "monolingual_allowed": allows_monolingual(academy_of(classroom)),
    }
