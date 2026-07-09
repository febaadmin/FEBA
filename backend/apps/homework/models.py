from django.db import models
from apps.subjects.models import Subject
from apps.classes.models import Class
from apps.schools.models import SchoolYear

class Homework(models.Model):
    title = models.CharField(max_length=200)
    description = models.TextField()
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name="homework")
    teacher = models.ForeignKey("teachers.Teacher", on_delete=models.SET_NULL, null=True, related_name="homework")
    cls = models.ForeignKey(Class, on_delete=models.CASCADE, related_name="homework", db_column="class_id")
    due_date = models.DateField()
    assigned_date = models.DateField(auto_now_add=True)
    school_year = models.ForeignKey(SchoolYear, on_delete=models.CASCADE, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Devoir"
        ordering = ["due_date"]

    def __str__(self):
        return f"{self.title} - {self.cls} - {self.due_date}"

class HomeworkAttachment(models.Model):
    homework = models.ForeignKey(Homework, on_delete=models.CASCADE, related_name="attachments")
    file = models.FileField(upload_to="homework/")
    name = models.CharField(max_length=200, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)