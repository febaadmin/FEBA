"""
Droit de noter : une affectation enseignant-classe-matière, seule autorité.

Les listes Teacher.classes et Teacher.subjects restent celles de la lecture
(élèves et classes visibles). Croisées, elles donnaient le droit de noter chaque
matière de l'enseignant dans chacune de ses classes.
"""
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.classes.models import Class
from apps.subjects.models import Subject

from .models import TeacherAssignment


def paires_autorisees(teacher):
    """Paires (classe, matière) que cet enseignant peut noter."""
    return set(
        TeacherAssignment.objects.filter(
            teacher=teacher, class_obj__in=teacher.classes.all(), subject__in=teacher.subjects.all(),
        ).values_list("class_obj_id", "subject_id")
    )


def peut_noter(teacher, subject_id, class_id):
    return bool(class_id) and (class_id, subject_id) in paires_autorisees(teacher)


def remplacer_affectations(teacher, lignes, user):
    """
    Remplace toutes les affectations, tout ou rien. L'école de référence est
    celle de l'enseignant : une classe ou une matière d'une autre académie est refusée.
    """
    if not isinstance(lignes, list):
        raise ValidationError({"assignments": "Une liste d'affectations est attendue."})
    school_id = teacher.user.school_id
    voulues = set()
    for ligne in lignes:
        try:
            voulues.add((int(ligne["class_id"]), int(ligne["subject_id"])))
        except (TypeError, ValueError, KeyError):
            raise ValidationError({"assignments": "Chaque ligne doit indiquer class_id et subject_id."})
    classes = Class.objects.filter(
        pk__in={c for c, _ in voulues}, school_year__school_id=school_id).prefetch_related("subjects").in_bulk()
    matieres = Subject.objects.filter(pk__in={s for _, s in voulues}, school_id=school_id).in_bulk()
    for class_id, subject_id in voulues:
        if class_id not in classes or subject_id not in matieres:
            raise ValidationError({"assignments": "Classe ou matière hors de l'académie de cet enseignant."})
        programme = {m.pk for m in classes[class_id].subjects.all()}
        if programme and subject_id not in programme:
            raise ValidationError({"assignments": (
                f"{matieres[subject_id].name} n'est pas au programme de {classes[class_id].name}.")})
    with transaction.atomic():
        teacher.assignments.exclude(
            pk__in=[a.pk for a in teacher.assignments.all() if (a.class_obj_id, a.subject_id) in voulues]
        ).delete()
        for class_id, subject_id in voulues:
            TeacherAssignment.objects.update_or_create(
                teacher=teacher, class_obj_id=class_id, subject_id=subject_id,
                defaults={"source": TeacherAssignment.SOURCE_ADMIN, "confirmed_by": user,
                          "confirmed_at": timezone.now()},
            )
        teacher.classes.add(*{c for c, _ in voulues})
        teacher.subjects.add(*{s for _, s in voulues})
