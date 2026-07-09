from django.db import models
from apps.students.models import Student
from apps.schools.models import SchoolYear

class Bulletin(models.Model):
    PERIOD_CHOICES = [("T1","Trimestre 1"),("T2","Trimestre 2"),("T3","Trimestre 3"),("annual","Annuel")]
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="bulletins")
    school_year = models.ForeignKey(SchoolYear, on_delete=models.CASCADE)
    enrollment = models.ForeignKey(
        "students.StudentEnrollment", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="bulletins",
        help_text="Inscription annuelle de l'élève correspondant à ce bulletin.",
    )
    period = models.CharField(max_length=7, choices=PERIOD_CHOICES)
    pdf_file = models.FileField(upload_to="bulletins/", null=True, blank=True)
    generated_at = models.DateTimeField(auto_now_add=True)
    general_comment = models.TextField(blank=True)
    average = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)
    rank_in_class = models.PositiveIntegerField(null=True, blank=True)
    appreciation = models.CharField(max_length=100, blank=True)

    class Meta:
        verbose_name = "Bulletin"
        unique_together = ("student","school_year","period")
        ordering = ["-generated_at"]

    def __str__(self):
        return f"{self.student} - {self.period} - {self.school_year}"