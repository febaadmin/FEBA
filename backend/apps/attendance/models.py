from django.db import models
from apps.students.models import Student
from apps.accounts.models import CustomUser

class Attendance(models.Model):
    STATUS_CHOICES = [("present","Présent"),("absent","Absent"),("late","En retard"),("excused","Excusé")]
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="attendance_records")
    date = models.DateField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="present")
    justification = models.TextField(blank=True)
    justification_file = models.FileField(upload_to="attendance/", null=True, blank=True)
    notified_parent = models.BooleanField(default=False)
    created_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, related_name="attendance_created")
    school_year = models.ForeignKey("schools.SchoolYear", on_delete=models.CASCADE, null=True, blank=True)
    enrollment = models.ForeignKey(
        "students.StudentEnrollment", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="attendance_records",
        help_text="Inscription annuelle de l'élève correspondant à cette présence.",
    )
    subject = models.ForeignKey("subjects.Subject", on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Présence"
        ordering = ["-date"]

    def __str__(self):
        return f"{self.student} - {self.date} - {self.status}"