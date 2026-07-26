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
        # V8 — CORRECTION DU 500 À LA CRÉATION D'UN ENSEIGNANT.
        #
        # Cause racine : l'ancien code générait `ENS-<année>-<count()+1>`.
        # `count()` n'est PAS une séquence : dès qu'un enseignant est supprimé
        # (ou que deux créations s'entrecroisent), la valeur retombe sur un
        # matricule DÉJÀ pris → IntegrityError « UNIQUE constraint failed:
        # teachers_teacher.employee_id » → erreur 500 côté interface.
        #
        # Correctif : on repart du plus grand suffixe RÉELLEMENT utilisé pour
        # l'année, et on réessaie tant que le matricule est pris (course entre
        # deux requêtes simultanées).
        if not self.employee_id:
            self.employee_id = self._generate_employee_id()

        from django.db import IntegrityError, transaction
        for _ in range(10):
            try:
                with transaction.atomic():
                    return super().save(*args, **kwargs)
            except IntegrityError as exc:
                # On ne retente QUE la collision de matricule ; toute autre
                # erreur d'intégrité (utilisateur en double…) doit remonter.
                if "employee_id" not in str(exc) or kwargs.get("force_update"):
                    raise
                self.employee_id = self._generate_employee_id()
        # Dernière tentative : laisse remonter l'erreur si elle persiste.
        return super().save(*args, **kwargs)

    @staticmethod
    def _generate_employee_id():
        """Matricule ENS-<année>-<n> basé sur le plus grand suffixe existant."""
        from django.utils import timezone
        year = timezone.now().year
        prefix = f"ENS-{year}-"
        used = Teacher.objects.filter(employee_id__startswith=prefix).values_list(
            "employee_id", flat=True
        )
        top = 0
        for value in used:
            suffix = value[len(prefix):]
            if suffix.isdigit():
                top = max(top, int(suffix))
        return f"{prefix}{top + 1:04d}"