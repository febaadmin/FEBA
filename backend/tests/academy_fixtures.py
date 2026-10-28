"""
Académies complètes pour les tests multi-académies (P0 du 26/10/2026).

`build_academy` crée l'académie PAR LE SERVICE RÉEL (`create_academy`, comme
l'écran « Académies »), puis la peuple de données marquées de son étiquette :
classe, matières, comptes de chaque rôle, élèves notés, parent, paiement,
bulletin, salle virtuelle. Chaque nom porte l'étiquette `tag`, ce qui permet
de détecter dans n'importe quelle réponse une donnée d'une AUTRE académie.
"""
import datetime

from apps.accounts.models import CustomUser
from apps.classes.models import Class
from apps.grades.models import Grade
from apps.parents.models import Parent, ParentStudent
from apps.payments.models import Payment
from apps.schools.academy_setup import create_academy
from apps.students.models import Student, StudentEnrollment
from apps.subjects.models import Subject
from apps.teachers.models import Teacher

TYPES = ("online", "physical_primary", "physical_secondary")


class BuiltAcademy:
    """Accès commode aux objets d'une académie de test."""

    def __init__(self, **kw):
        self.__dict__.update(kw)

    def users(self):
        return {"admin": self.admin, "teacher": self.teacher_user,
                "parent": self.parent_user, "student": self.student_user}


def build_academy(tag, academy_type, *, grades=(16, 12), superadmin=None):
    tag = tag.upper()
    school = create_academy({
        "name": f"Académie {tag}", "code": f"AC_{tag}", "academy_type": academy_type,
        "address": f"Adresse {tag}", "timezone": "Africa/Porto-Novo",
        "currency_code": "XOF", "default_language": "fr",
        "school_year_name": "2026-2027",
        "school_year_start": datetime.date(2026, 9, 1),
        "school_year_end": datetime.date(2027, 7, 31),
    }, created_by=superadmin)
    year = school.years.get(is_current=True)
    # Premier niveau hors maternelle : le bulletin de maternelle est en
    # lettres seulement, sans moyenne ni appréciation.
    level = school.levels.exclude(cycle="maternelle").order_by("order").first()
    if level is None:                       # académie en ligne : groupes à créer
        level = school.levels.create(name=f"Groupe {tag}", cycle="primaire", order=1)
    klass = Class.objects.create(name=f"Classe-{tag}", level=level, school_year=year)
    fr = Subject.objects.create(school=school, name=f"Français {tag}", code=f"FR{tag}"[:20],
                                coefficient=2, language="fr")
    en = Subject.objects.create(school=school, name=f"English {tag}", code=f"EN{tag}"[:20],
                                coefficient=1, language="en")
    klass.subjects.set([fr, en])

    def user(role, suffix):
        return CustomUser.objects.create_user(
            username=f"{role}{suffix}{tag}".lower(), email=f"{role}.{suffix}.{tag}@iso.test".lower(),
            password="Pass1234!", role=role, first_name=f"{role.title()}{tag}",
            last_name=f"Nom{tag}", school=school)

    admin = user("admin", "a")
    teacher_user = user("teacher", "t")
    teacher = Teacher.objects.create(user=teacher_user)
    teacher.classes.add(klass)
    teacher.subjects.add(fr, en)
    student_user = user("student", "s")
    student = Student.objects.create(
        user=student_user, school=school, first_name=f"Eleve{tag}", last_name=f"Nom{tag}",
        current_class=klass, school_year=year, gender="F")
    enrollment = StudentEnrollment.objects.create(student=student, school_year=year, class_obj=klass)
    for subject, value in zip((fr, en), grades):
        Grade.objects.create(student=student, subject=subject, school_year=year,
                             teacher=teacher, period="T1", value=value, enrollment=enrollment)
    parent_user = user("parent", "p")
    parent = Parent.objects.create(user=parent_user)
    ParentStudent.objects.create(student=student, parent=parent)
    payment = Payment.objects.create(
        student=student, school_year=year, amount="100.00", payment_type="inscription",
        payment_method="cash", payment_date=datetime.date(2026, 9, 15))
    return BuiltAcademy(
        tag=tag, school=school, year=year, level=level, klass=klass, subjects=(fr, en),
        admin=admin, teacher=teacher, teacher_user=teacher_user, student=student,
        student_user=student_user, parent=parent, parent_user=parent_user, payment=payment,
        enrollment=enrollment,
    )
