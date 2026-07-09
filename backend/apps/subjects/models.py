from django.db import models
from apps.schools.models import School, Level


class Subject(models.Model):
    LANGUAGE_CHOICES = [
        ('fr', 'Français'),
        ('en', 'Anglais'),
        ('bilingual', 'Bilingue'),
    ]

    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="subjects")
    level = models.ForeignKey(Level, on_delete=models.CASCADE, related_name="subjects", null=True, blank=True)
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=20)
    coefficient = models.PositiveIntegerField(default=1)
    language = models.CharField(
        max_length=10, choices=LANGUAGE_CHOICES, default='fr',
        help_text="Langue de la matière — utilisé pour le calcul de la moyenne bilingue"
    )
    order = models.PositiveIntegerField(default=0, help_text="Ordre d'affichage dans le bulletin")

    class Meta:
        verbose_name = "Matière"
        ordering = ["order", "name"]

    def __str__(self):
        return f"{self.name} (coeff {self.coefficient})"

    def is_french(self):
        return self.language == 'fr'

    def is_english(self):
        return self.language == 'en'
