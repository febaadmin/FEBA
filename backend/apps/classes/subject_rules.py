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
    "bilingual": ("commune (bilingue)", "communes (bilingues)"),
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


# ── Programme linguistique de l'ACADÉMIE ────────────────────────────────
#
# Niveau au-dessus du parcours de classe. `School.curriculum_language_mode`
# dit quelles matières l'académie enseigne :
#
#   french_only   matières françaises seulement ; toutes ses classes sont
#                 francophones ; aucune moyenne bilingue.
#   english_only  matières anglaises seulement ; toutes ses classes sont
#                 anglophones ; aucune moyenne bilingue.
#   bilingual     matières françaises, anglaises et « communes » ; classes
#                 bilingues, et monolingues si l'académie les autorise
#                 (drapeau `monolingual_classes`, règle existante).
#   (vide)        académie antérieure non encore configurée : le
#                 fonctionnement historique s'applique tel quel.
#
# MATIÈRE « BILINGUE » (`Subject.language == "bilingual"`)
# --------------------------------------------------------
# Sens retenu : matière COMMUNE, enseignée dans les deux langues. Elle
# n'appartient ni à la moyenne française ni à l'anglaise — elle n'est donc
# jamais comptée deux fois, ni dans la pondération 60/40 —, entre UNE fois
# dans la moyenne générale avec son coefficient, et s'imprime dans la
# section « Autres matières » du bulletin (comportement de calcul et
# d'impression existant, inchangé). Elle n'est admise que dans une académie
# bilingue et dans une classe au parcours bilingue.

#: Langues de matières admises par programme.
CURRICULUM_LANGUAGES = {
    "french_only": ("fr",),
    "english_only": ("en",),
    "bilingual": ("fr", "en", "bilingual"),
}
#: Libellé d'une langue de matière, pour les messages.
SUBJECT_LANGUAGE_LABELS = {"fr": "française", "en": "anglaise", "bilingual": "commune (bilingue)"}


def curriculum_mode(school):
    """Programme linguistique de l'académie, ou None (non configuré)."""
    mode = getattr(school, "curriculum_language_mode", None) if school is not None else None
    return mode if mode in CURRICULUM_LANGUAGES else None


def academy_subject_languages(school):
    """
    Langues de matières que l'académie peut créer et utiliser, ou None si
    son programme n'est pas configuré (aucune restriction nouvelle).
    """
    mode = curriculum_mode(school)
    return CURRICULUM_LANGUAGES[mode] if mode else None


def academy_tracks(school) -> tuple:
    """Parcours de classe que l'académie admet."""
    from .models import Class

    mode = curriculum_mode(school)
    if mode == "french_only":
        return (Class.TRACK_FRANCOPHONE,)
    if mode == "english_only":
        return (Class.TRACK_ANGLOPHONE,)
    if allows_monolingual(school) or (school is None):
        return (Class.TRACK_BILINGUAL, Class.TRACK_FRANCOPHONE, Class.TRACK_ANGLOPHONE)
    return (Class.TRACK_BILINGUAL,)


def default_track(school) -> str:
    """Parcours d'une nouvelle classe quand rien n'est précisé."""
    return academy_tracks(school)[0]


def subject_language_error(school, language):
    """
    Motif de refus d'une matière de cette langue dans cette académie, ou
    None. Utilisé par TOUS les chemins d'écriture (matières, notes,
    emplois du temps) : un écran ne peut pas accepter ce que l'API refuse.
    """
    allowed = academy_subject_languages(school)
    if allowed is None or language in allowed:
        return None
    mode_label = dict(_curriculum_choices()).get(curriculum_mode(school), "")
    return (
        f"{school.name} a pour programme « {mode_label} » : une matière "
        f"{SUBJECT_LANGUAGE_LABELS.get(language, language)} n'y est pas admise."
    )


def _curriculum_choices():
    from apps.schools.models import School

    return School.CURRICULUM_CHOICES


def track_error(school, track):
    """Motif de refus d'un parcours de classe dans cette académie, ou None."""
    from .models import Class

    if track in academy_tracks(school):
        return None
    labels = dict(Class.LANGUAGE_TRACKS)
    admis = ", ".join(labels[t] for t in academy_tracks(school))
    return (
        f"Parcours « {labels.get(track, track)} » non admis pour {school.name}. "
        f"Parcours possibles : {admis}."
    )


def grade_subject_error(student, subject, school_year=None):
    """
    Motif de refus d'une NOUVELLE note sur cette matière pour cet élève,
    ou None. Appliqué seulement si le programme de l'académie est
    configuré : une académie antérieure garde son fonctionnement.

      - la langue de la matière doit être admise par le programme ;
      - la classe de l'élève (pour l'année) doit enseigner cette langue :
        une note d'anglais n'a pas de place dans une classe francophone,
        elle ressortirait sur son bulletin sans y être attendue.
    """
    school = getattr(student, "school", None)
    if subject is None or curriculum_mode(school) is None:
        return None
    refus = subject_language_error(school, subject.language)
    if refus:
        return refus
    from apps.grades.models import Grade

    klass = Grade._class_for_year(student, school_year)
    if klass is not None and subject.language not in allowed_languages(klass):
        return (
            f"La classe {klass.name} ({_track_label(klass)}) n'enseigne pas de matière "
            f"{SUBJECT_LANGUAGE_LABELS.get(subject.language, subject.language)} : "
            f"pas de note de « {subject.name} » pour cet élève."
        )
    return None


def _track_label(classroom):
    """Libellé du parcours APPLIQUÉ (et non de la valeur stockée)."""
    from .models import Class

    return dict(Class.LANGUAGE_TRACKS).get(effective_track(classroom), "").lower()


def schedule_subject_error(classroom, subject):
    """
    Motif de refus d'un créneau (présentiel ou séance en ligne) de cette
    matière pour cette classe / ce groupe, ou None. Même condition que les
    notes : appliqué quand le programme de l'académie est configuré.
    """
    academy = academy_of(classroom)
    if subject is None or classroom is None or curriculum_mode(academy) is None:
        return None
    refus = subject_language_error(academy, subject.language)
    if refus:
        return refus
    if subject.language not in allowed_languages(classroom):
        return (
            f"{classroom.name} ({_track_label(classroom)}) n'enseigne pas "
            f"« {subject.name} » (matière {SUBJECT_LANGUAGE_LABELS.get(subject.language, subject.language)})."
        )
    return None


def curriculum_diagnostic(school, mode):
    """
    Données existantes qui ne respecteraient PAS le programme `mode`.

    Sert avant de changer le programme d'une académie : rien n'est
    supprimé ni converti, le super administrateur voit précisément ce qui
    devra être corrigé (matières à renommer ou retirer des classes, classes
    à repasser dans un autre parcours, notes rattachées).
    """
    from apps.grades.models import Grade
    from apps.subjects.models import Subject

    from .models import Class

    allowed = CURRICULUM_LANGUAGES.get(mode)
    if allowed is None:
        return {"ok": True, "subjects": [], "classes": [], "grades": 0}
    subjects = list(Subject.objects.filter(school=school).exclude(language__in=allowed)
                    .values("id", "name", "language"))
    # Le parcours d'une classe n'est pas un obstacle : dans une académie
    # monolingue il est imposé (`effective_track`) et la valeur stockée est
    # alignée au moment du changement (`align_class_tracks`). Seules les
    # MATIÈRES d'une autre langue posent problème : elles portent des notes.
    classes = []
    for klass in (Class.objects.filter(school_year__school=school)
                  .select_related("school_year").prefetch_related("subjects")):
        foreign = sorted(s.name for s in klass.subjects.all() if s.language not in allowed)
        if foreign:
            classes.append({"id": klass.id, "name": klass.name,
                            "school_year": klass.school_year.name,
                            "reasons": ["matières " + ", ".join(foreign)]})
    grades = Grade.objects.filter(subject__in=[s["id"] for s in subjects],
                                  is_deleted=False).count()
    return {"ok": not subjects and not classes, "subjects": subjects,
            "classes": classes, "grades": grades}


def align_class_tracks(school):
    """
    Après passage à un programme monolingue : la valeur STOCKÉE du parcours
    des classes rejoint celle qui est appliquée, pour que les écrans et
    l'édition d'une classe ne proposent pas un parcours refusé. Ne touche
    ni aux matières, ni aux notes. Renvoie le nombre de classes alignées.
    """
    from .models import Class

    target = {"french_only": Class.TRACK_FRANCOPHONE,
              "english_only": Class.TRACK_ANGLOPHONE}.get(curriculum_mode(school))
    if target is None:
        return 0
    return (Class.objects.filter(school_year__school=school)
            .exclude(language_track=target).update(language_track=target))


def effective_track(classroom) -> str:
    """
    Parcours RÉELLEMENT appliqué à cette classe.

    1. Académie « français uniquement » ou « anglais uniquement » : toutes
       ses classes ont ce parcours, quelle que soit la valeur stockée.
    2. Sinon, le parcours déclaré — sauf pour une académie qui n'autorise
       pas les parcours monolingues : là, il vaut toujours BILINGUAL. Une
       valeur stockée ou postée ne peut donc pas rendre monolingue une
       classe d'une académie bilingue par construction.
    """
    from .models import Class

    academy = academy_of(classroom)
    mode = curriculum_mode(academy)
    if mode == "french_only":
        return Class.TRACK_FRANCOPHONE
    if mode == "english_only":
        return Class.TRACK_ANGLOPHONE
    declared = getattr(classroom, "language_track", None) or Class.TRACK_BILINGUAL
    if declared not in Class.TRACK_LANGUAGES:
        declared = Class.TRACK_BILINGUAL
    if declared != Class.TRACK_BILINGUAL and forbids_monolingual(academy):
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

    track = effective_track(classroom)
    langues = Class.TRACK_LANGUAGES[track]
    # Matières communes : seulement dans une classe bilingue d'une
    # académie au programme bilingue (voir l'en-tête de section).
    if track == Class.TRACK_BILINGUAL and curriculum_mode(academy_of(classroom)) == "bilingual":
        langues = langues + ("bilingual",)
    return langues


def required_languages(classroom) -> tuple:
    """
    Langues dont au moins une matière est obligatoire : chaque langue du
    parcours doit être enseignée. Une matière commune n'en dispense pas.
    """
    from .models import Class

    return Class.TRACK_LANGUAGES[effective_track(classroom)]


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
        "curriculum_language_mode": curriculum_mode(academy_of(classroom)),
        "allowed_tracks": list(academy_tracks(academy_of(classroom))),
        "allowed_languages": list(allowed_languages(classroom)),
        "required_languages": list(required_languages(classroom)),
        "missing_languages": missing_languages(classroom),
        "monolingual_allowed": allows_monolingual(academy_of(classroom)),
    }
