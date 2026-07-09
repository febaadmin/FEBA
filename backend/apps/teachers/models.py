from django.db import models
from apps.accounts.models import CustomUser

class Teacher(models.Model):
    CONTRACT_CHOICES = [("permanent","Permanent"),("contractuel","Contractuel"),("vacataire","Vacataire")]
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name="teacher_profile")
    employee_id = models.CharField(max_length=20, unique=True, blank=True)
    specialization = models.CharField(max_length=100, blank=True)
    hire_date = models.DateField(null=True, blank=True)
    contract_type = models.CharField(max_length=20, choices=CONTRACT_CHOICES, default="permanent")
    subjects = models.ManyToManyField("subjects.Subject", blank=True, related_name="teachers")
    classes = models.ManyToManyField("classes.Class", blank=True, related_name="teacher_classes")
    bio = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Enseignant"

    def __str__(self):
        return self.user.get_full_name()

    def save(self, *args, **kwargs):
        if not self.employee_id:
            from django.utils import timezone
            count = Teacher.objects.count() + 1
            self.employee_id = f"ENS-{timezone.now().year}-{count:04d}"
        super().save(*args, **kwargs)