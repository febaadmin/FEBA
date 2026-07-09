from django.db import models
from apps.schools.models import SchoolYear, Level


class Class(models.Model):
    name = models.CharField(max_length=50)
    level = models.ForeignKey(Level, on_delete=models.CASCADE, related_name="classes")
    school_year = models.ForeignKey(SchoolYear, on_delete=models.CASCADE, related_name="classes")
    max_students = models.PositiveIntegerField(default=30)
    # M2M: matières assignées à cette classe (FR + EN)
    subjects = models.ManyToManyField(
        "subjects.Subject",
        blank=True,
        related_name="classes",
        verbose_name="Matières",
        help_text="Matières françaises ET anglaises assignées à cette classe",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Classe"
        ordering = ["name"]

    def __str__(self):
        return self.name

    def get_fr_subjects(self):
        """Retourne les matières françaises de cette classe."""
        return self.subjects.filter(language="fr")

    def get_en_subjects(self):
        """Retourne les matières anglaises de cette classe."""
        return self.subjects.filter(language="en")

    def has_bilingual_subjects(self):
        """Vérifie que la classe a au moins une matière FR et une EN."""
        return self.get_fr_subjects().exists() and self.get_en_subjects().exists()