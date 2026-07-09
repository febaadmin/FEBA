from django.db import models
from apps.classes.models import Class
from apps.subjects.models import Subject
from apps.schools.models import SchoolYear

class ClassSchedule(models.Model):
    DAYS = [(0,"Lundi"),(1,"Mardi"),(2,"Mercredi"),(3,"Jeudi"),(4,"Vendredi"),(5,"Samedi")]
    cls = models.ForeignKey(Class, on_delete=models.CASCADE, related_name="schedules", db_column="class_id")
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    teacher = models.ForeignKey("teachers.Teacher", on_delete=models.SET_NULL, null=True, related_name="schedules")
    school_year = models.ForeignKey(SchoolYear, on_delete=models.CASCADE)
    day_of_week = models.PositiveSmallIntegerField(choices=DAYS)
    start_time = models.TimeField()
    end_time = models.TimeField()
    room = models.CharField(max_length=50, blank=True)
    recurrent = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Emploi du temps"
        ordering = ["day_of_week","start_time"]

    def __str__(self):
        return f"{self.cls} - {self.subject} - {self.get_day_of_week_display()} {self.start_time}"