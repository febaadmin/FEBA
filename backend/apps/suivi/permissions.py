"""
Qui voit quel élève dans le suivi. Le serveur décide ; l'écran ne fait que suivre.

  - superadmin : l'académie active ;
  - admin : son académie ;
  - enseignant : les élèves de ses classes, et n'écrit sur une matière que si
    elle lui est affectée dans cette classe ;
  - élève et parent : soi-même et ses enfants, seulement si l'académie a ouvert
    le suivi aux familles (drapeau suivi_familles), et seulement ce qui est validé.
"""
from rest_framework.exceptions import PermissionDenied

from apps.core.features import entity_has_feature
from apps.core.tenancy import get_request_school
from apps.students.models import Student
from apps.teachers.affectations import paires_autorisees


def est_famille(user):
    return user.is_student() or user.is_parent()


def eleves_visibles(request):
    user, school = request.user, get_request_school(request)
    if school is None:
        return Student.objects.none()
    eleves = Student.objects.filter(school=school)
    if user.role_level >= 80:
        return eleves
    if user.is_teacher():
        teacher = getattr(user, "teacher_profile", None)
        if teacher is None:
            return Student.objects.none()
        return eleves.filter(current_class__in=teacher.classes.all(), is_active=True)
    if not entity_has_feature(school, "suivi_familles"):
        return Student.objects.none()
    if user.is_student():
        return eleves.filter(user=user)
    if user.is_parent():
        return eleves.filter(parents__parent__user=user)
    return Student.objects.none()


def controler_ecriture(request, student, subject=None):
    """Refuse (403) toute écriture hors du périmètre de l'utilisateur."""
    user = request.user
    if est_famille(user) or user.role_level < 50:
        raise PermissionDenied("Le suivi se consulte seulement depuis ce compte.")
    if not eleves_visibles(request).filter(pk=student.pk).exists():
        raise PermissionDenied("Cet élève n'est pas dans votre périmètre.")
    if subject is not None and user.is_teacher():
        teacher = user.teacher_profile
        if (student.current_class_id, subject.pk) not in paires_autorisees(teacher):
            raise PermissionDenied(f"Vous n'êtes pas affecté à {subject.name} dans la classe de cet élève.")
