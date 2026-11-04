"""
Couche commune du centre d'analyse : filtres contextuels et périmètre d'accès.

Toutes les analyses passent par `Contexte` :
- l'académie (sélecteur du super administrateur, sinon celle du compte) ;
- l'année scolaire (par défaut l'année en cours de l'académie) ;
- les filtres : période (T1, T2, T3, examen), cycle, niveau, classe, matière,
  enseignant, élève, genre ;
- le périmètre du profil, appliqué côté serveur, jamais par l'écran :
  * super administrateur et administrateur : toute l'académie ;
  * enseignant : ses classes (classes rattachées et affectations), aucune finance ;
  * parent : ses enfants ; élève : lui-même (vue personnelle uniquement).

Un identifiant hors de l'académie ou hors du périmètre est refusé (404), jamais
ignoré : l'utilisateur ne voit pas une analyse vide en croyant qu'elle est filtrée.
"""
from dataclasses import dataclass, field

from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError

PERIODES = ("T1", "T2", "T3", "exam")
GENRES = ("M", "F")


class AcademieRequise(ValidationError):
    pass


@dataclass
class Contexte:
    user: object
    academie: object
    annee: object
    periode: str = None
    cycle: str = None
    niveau: object = None
    classe: object = None
    matiere: object = None
    enseignant: object = None
    eleve: object = None
    genre: str = None
    classes_autorisees: set = None      # None : toutes les classes de l'académie
    eleves_autorises: set = None        # None : tous les élèves du périmètre
    est_personnel: bool = False         # administration (voit l'analyse par enseignant)
    actifs: dict = field(default_factory=dict)

    def filtrer_classes(self, qs, champ="id"):
        """Restreint un queryset de classes (ou de lignes portant une classe) au périmètre."""
        if self.classes_autorisees is not None:
            qs = qs.filter(**{f"{champ}__in": self.classes_autorisees})
        return qs


def _identifiant(params, cle, erreurs):
    from apps.core.request_text import identifiant
    brut = params.get(cle)
    if not brut:
        return None
    v = identifiant(brut)
    if v is None:
        erreurs[cle] = "Identifiant invalide."
    return v


def _classes_enseignant(user):
    from apps.teachers.models import Teacher, TeacherAssignment
    prof = Teacher.objects.filter(user=user).first()
    if prof is None:
        return prof, set()
    classes = set(prof.classes.values_list("id", flat=True))
    classes |= set(TeacherAssignment.objects.filter(teacher=prof).values_list("class_obj_id", flat=True))
    return prof, classes


def resoudre(request, personnel_seulement=True):
    """Contexte d'une requête d'analyse. Lève 400, 403 ou 404 explicites."""
    from apps.classes.models import Class
    from apps.core.tenancy import get_request_school
    from apps.schools.models import Level, SchoolYear
    from apps.students.models import Student
    from apps.subjects.models import Subject
    from apps.teachers.models import Teacher

    user = request.user
    if personnel_seulement and not (user.is_superadmin() or user.is_admin() or user.is_teacher()):
        raise PermissionDenied("Les analyses d'établissement sont réservées au personnel.")
    academie = get_request_school(request)
    if academie is None:
        raise AcademieRequise({"academie": "Choisissez une académie dans le sélecteur : les analyses portent sur une académie à la fois."})

    p, erreurs = request.query_params, {}
    ids = {cle: _identifiant(p, cle, erreurs) for cle in ("annee", "niveau", "classe", "matiere", "enseignant", "eleve")}
    periode = p.get("periode") or None
    if periode and periode not in PERIODES:
        erreurs["periode"] = f"Valeur attendue : {', '.join(PERIODES)}."
    genre = p.get("genre") or None
    if genre and genre not in GENRES:
        erreurs["genre"] = "Valeur attendue : M ou F."
    cycle = p.get("cycle") or None
    if cycle and cycle not in dict(Level.CYCLE_CHOICES):
        erreurs["cycle"] = "Cycle inconnu."
    if erreurs:
        raise ValidationError(erreurs)

    def objet(modele, cle, **portee):
        if ids[cle] is None:
            return None
        o = modele.objects.filter(pk=ids[cle], **portee).first()
        if o is None:
            raise NotFound(f"{cle.capitalize()} introuvable dans cette académie.")
        return o

    if ids["annee"]:
        annee = objet(SchoolYear, "annee", school=academie)
    else:
        annee = SchoolYear.objects.filter(school=academie, is_current=True).first()
        if annee is None:
            raise ValidationError({"annee": "Aucune année scolaire active pour cette académie."})

    ctx = Contexte(user=user, academie=academie, annee=annee, periode=periode, cycle=cycle, genre=genre,
                   est_personnel=user.is_superadmin() or user.is_admin())
    ctx.niveau = objet(Level, "niveau", school=academie)
    ctx.classe = objet(Class, "classe", level__school=academie)
    ctx.matiere = objet(Subject, "matiere", school=academie)
    ctx.enseignant = objet(Teacher, "enseignant", user__school=academie)
    ctx.eleve = objet(Student, "eleve", school=academie)

    if user.is_teacher():
        prof, classes = _classes_enseignant(user)
        ctx.classes_autorisees = classes
        if ctx.classe is not None and ctx.classe.pk not in classes:
            raise PermissionDenied("Cette classe ne fait pas partie de vos classes.")
        if ctx.eleve is not None and ctx.eleve.current_class_id not in classes:
            raise PermissionDenied("Cet élève ne fait pas partie de vos classes.")
        if ctx.enseignant is not None and (prof is None or ctx.enseignant.pk != prof.pk):
            raise PermissionDenied("Vous ne pouvez consulter que vos propres classes.")
    elif user.is_parent():
        ctx.eleves_autorises = set(Student.objects.filter(parents__parent__user=user).values_list("id", flat=True))
    elif user.is_student():
        ctx.eleves_autorises = set(Student.objects.filter(user=user).values_list("id", flat=True))

    ctx.actifs = {k: v for k, v in {
        "annee": annee.pk, "periode": periode, "cycle": cycle, "genre": genre,
        **{k: ids[k] for k in ("niveau", "classe", "matiere", "enseignant", "eleve")},
    }.items() if v is not None}
    return ctx
