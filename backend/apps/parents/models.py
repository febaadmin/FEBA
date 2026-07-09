from django.db import models, transaction
from django.core.exceptions import ValidationError
from django.db.utils import IntegrityError
from apps.accounts.models import CustomUser
from apps.students.models import Student


class Parent(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name="parent_profile")
    profession = models.CharField(max_length=100, blank=True)
    address = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Parent"

    def __str__(self):
        return self.user.get_full_name()


class ParentStudent(models.Model):
    """
    Lien parent ↔ élève — relation MANY-TO-MANY assumée (un élève peut
    avoir plusieurs parents/tuteurs ; un parent peut avoir plusieurs
    enfants). Avant la v29, une contrainte unique au niveau base de
    données limitait chaque élève à un seul parent — ce qui empêchait
    d'enregistrer un père ET une mère, ou un tuteur en plus d'un
    parent. Cette contrainte a été supprimée : voir
    parents/migrations/0003_remove_single_parent_constraint.py
    """
    RELATIONSHIP_CHOICES = [
        ("father", "Père"),
        ("mother", "Mère"),
        ("guardian", "Tuteur"),
        ("other", "Autre"),
    ]
    parent = models.ForeignKey(Parent, on_delete=models.CASCADE, related_name="children_links")
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="parents")
    relationship = models.CharField(max_length=10, choices=RELATIONSHIP_CHOICES, default="guardian")

    is_primary_contact = models.BooleanField(
        default=False, help_text="Contact prioritaire pour les communications de l'établissement.",
    )
    is_legal_guardian = models.BooleanField(
        default=True, help_text="Tuteur légal de l'élève (autorité parentale).",
    )
    is_financial_responsible = models.BooleanField(
        default=True, help_text="Responsable des paiements de scolarité de cet élève.",
    )
    can_pickup = models.BooleanField(
        default=True, help_text="Personne autorisée à récupérer l'élève à l'établissement.",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = (("parent", "student"),)
        verbose_name = "Lien parent-élève"
        verbose_name_plural = "Liens parent-élève"

    def __str__(self):
        return f"{self.parent} ↔ {self.student}"

    def clean(self):
        """
        Garde-fou tenant : un parent et un élève rattachés à des
        établissements différents ne peuvent pas être liés — cela
        constituerait une fuite de données entre deux clients SaaS.
        """
        parent_school = getattr(self.parent.user, "school_id", None) if self.parent_id else None
        student_school = getattr(self.student, "school_id", None) if self.student_id else None
        if parent_school and student_school and parent_school != student_school:
            raise ValidationError(
                "Ce parent et cet élève n'appartiennent pas au même établissement."
            )

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)
