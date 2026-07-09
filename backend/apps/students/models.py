from django.db import models
from django.utils import timezone
from apps.accounts.models import CustomUser
from apps.schools.models import SchoolYear
from apps.classes.models import Class


def generate_matricule(school=None):
    """Génère un matricule unique POUR UN ÉTABLISSEMENT donné.
    Le préfixe reprend le slug de l'établissement (ex: FEBA, LYCEE-X)
    pour rester lisible même quand plusieurs tenants partagent la même
    base de données.
    """
    year = timezone.now().year
    prefix = (school.slug.upper().replace("-", "")[:10] if school and school.slug else "ECOLE")
    qs = Student.objects.filter(enrollment_date__year=year)
    if school is not None:
        qs = qs.filter(school=school)
    count = qs.count() + 1
    return f"{prefix}-{year}-{count:04d}"


class Student(models.Model):
    GENDER_CHOICES = [("M", "Masculin"), ("F", "Féminin")]
    user = models.OneToOneField(CustomUser, on_delete=models.SET_NULL, null=True, blank=True, related_name="student_profile")
    # Tenant : établissement de rattachement. Champ direct (et non
    # seulement déductible via school_year/enrollments) car un élève
    # entre une réinscription et la suivante, ou un élève sans aucune
    # inscription encore créée, doit malgré tout être rattaché sans
    # ambiguïté à un établissement.
    school = models.ForeignKey(
        "schools.School", on_delete=models.PROTECT, null=True, blank=True,
        related_name="students",
    )
    matricule = models.CharField(max_length=20, blank=True)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES, blank=True)
    photo = models.ImageField(upload_to="students/", null=True, blank=True)
    address = models.TextField(blank=True)
    current_class = models.ForeignKey(Class, on_delete=models.SET_NULL, null=True, blank=True, related_name="students")
    school_year = models.ForeignKey(SchoolYear, on_delete=models.CASCADE, related_name="students", null=True, blank=True)
    is_active = models.BooleanField(default=True)
    enrollment_date = models.DateField(auto_now_add=True)

    EXIT_REASON_CHOICES = [
        ("", "—"),
        ("graduated", "Diplômé / fin de cycle"),
        ("transferred_out", "Transféré vers un autre établissement"),
        ("excluded", "Exclu"),
        ("withdrawn", "Retiré par la famille / déménagement"),
    ]
    exit_reason = models.CharField(max_length=20, choices=EXIT_REASON_CHOICES, blank=True, default="")
    exit_date = models.DateField(null=True, blank=True)
    exit_notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Élève"
        ordering = ["last_name", "first_name"]
        # Le matricule est unique PAR établissement (et non plus
        # globalement) : deux écoles clientes différentes peuvent
        # légitimement attribuer le même matricule "FEBA-2026-0001"
        # si elles partagent le même générateur par défaut.
        constraints = [
            models.UniqueConstraint(fields=["school", "matricule"], name="unique_matricule_per_school"),
        ]

    def __str__(self):
        return f"{self.last_name} {self.first_name} ({self.matricule})"

    def save(self, *args, **kwargs):
        if not self.matricule:
            for _ in range(5):  # garde-fou contre une collision concurrente improbable
                candidate = generate_matricule(self.school)
                if not Student.objects.filter(school=self.school, matricule=candidate).exclude(pk=self.pk).exists():
                    self.matricule = candidate
                    break
            else:
                import uuid
                self.matricule = f"TMP-{uuid.uuid4().hex[:8].upper()}"
        super().save(*args, **kwargs)

    def get_full_name(self):
        return f"{self.first_name} {self.last_name}"

    def get_enrollment_for_year(self, school_year):
        """Return the StudentEnrollment for a given school year, or None."""
        return self.enrollments.filter(school_year=school_year).first()

    def get_class_for_year(self, school_year):
        """Return the class the student was enrolled in for a given year."""
        enrollment = self.get_enrollment_for_year(school_year)
        if enrollment:
            return enrollment.class_obj
        return self.current_class


class StudentEnrollment(models.Model):
    """
    Multi-year enrollment tracking.
    Each record links a student to a class for a specific school year.
    This preserves complete academic history across years.
    """
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="enrollments")
    school_year = models.ForeignKey(SchoolYear, on_delete=models.CASCADE, related_name="enrollments")
    class_obj = models.ForeignKey(Class, on_delete=models.SET_NULL, null=True, blank=True, related_name="enrollments")
    enrolled_at = models.DateField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    note = models.TextField(blank=True, help_text="Notes sur l'inscription (redoublement, transfert, etc.)")

    PROMOTION_CHOICES = [
        ('normal', 'Passage normal'),
        ('honor', 'Passage avec mention'),
        ('repeat', 'Redoublement'),
        ('transfer', 'Transfert (changement de filière/classe)'),
        ('new', 'Nouvelle inscription'),
        ('graduated', 'Diplômé / fin de cycle'),
        ('excluded', 'Exclu'),
        ('withdrawn', 'Retiré (départ établissement)'),
    ]
    promotion_status = models.CharField(max_length=20, choices=PROMOTION_CHOICES, default='new')

    class Meta:
        verbose_name = "Inscription annuelle"
        ordering = ["-school_year__start_date"]
        unique_together = [["student", "school_year"]]

    def __str__(self):
        cls_name = self.class_obj.name if self.class_obj else "—"
        return f"{self.student} — {self.school_year} — {cls_name}"
