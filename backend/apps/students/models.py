from django.db import models, transaction
from django.utils import timezone
from apps.accounts.models import CustomUser
from apps.schools.models import SchoolYear
from apps.classes.models import Class


import re


def _school_matricule_prefix(school):
    """
    Préfixe court du matricule pour un établissement.
    Priorité : School.matricule_prefix (configurable) → dernier segment du
    slug s'il est parlant (groupe-scolaire-feba → FEBA) → début du slug.
    """
    if school is None:
        return "ECOLE"
    configured = (getattr(school, "matricule_prefix", "") or "").strip()
    if configured:
        return re.sub(r"[^A-Z0-9]", "", configured.upper())[:8] or "ECOLE"
    slug = (school.slug or "").strip()
    if slug:
        last = slug.split("-")[-1]
        if len(last) >= 3:
            return last.upper()[:8]
        return slug.upper().replace("-", "")[:8]
    return "ECOLE"


def _matricule_base(school, year):
    """Préfixe complet d'un matricule pour une école et une année : ``FEBA-26-``."""
    prefix = _school_matricule_prefix(school)
    return f"{prefix}-{year % 100:02d}-"


def _seed_last_number(school, base):
    """
    Valeur initiale du compteur pour un (établissement, année) donné.

    On repart du plus grand numéro DÉJÀ présent en base pour ce préfixe
    ``FEBA-26-`` afin de ne jamais entrer en collision avec d'anciens
    matricules importés/hérités qui partageraient le même format. Renvoie 0
    si aucun matricule de ce format n'existe encore.
    """
    qs = Student.objects.filter(matricule__startswith=base)
    if school is not None:
        qs = qs.filter(school=school)
    max_seq = 0
    pattern = re.compile(re.escape(base) + r"(\d+)$")
    for matricule in qs.values_list("matricule", flat=True):
        match = pattern.match(matricule)
        if match:
            max_seq = max(max_seq, int(match.group(1)))
    return max_seq


def generate_matricule(school=None):
    """
    Génère un matricule au format officiel ``FEBA-YY-NNNN``.

      - ``FEBA`` : préfixe court de l'établissement (configurable, sinon
        dérivé du slug) ;
      - ``YY``   : DEUX DERNIERS CHIFFRES DE L'ANNÉE SYSTÈME au moment de la
        création (``timezone.now().year``) — jamais une valeur codée en dur ;
      - ``NNNN`` : numéro séquentiel sur 4 chiffres, redémarrant à 0001
        pour chaque nouvelle année système et chaque établissement.

    Concurrence : le compteur est matérialisé dans
    :class:`StudentMatriculeSequence` (unique par établissement + année) et
    incrémenté sous ``select_for_update()`` dans une transaction atomique.
    Deux créations simultanées obtiennent donc deux numéros distincts (pas
    de doublon), contrairement à un ``count() + 1`` naïf.

    Compatibilité : les anciens matricules (``FEBA_25_0005``,
    ``GROUPESCOL-2026-0005``…) ne sont jamais modifiés ; la séquence est
    amorcée sur le plus grand numéro existant du même format pour éviter
    toute collision.
    """
    year = timezone.now().year
    base = _matricule_base(school, year)

    with transaction.atomic():
        seq, _created = StudentMatriculeSequence.objects.get_or_create(
            school=school, year=year,
            defaults={"last_number": _seed_last_number(school, base)},
        )
        # Verrou de ligne : sérialise les générations concurrentes pour ce
        # couple (établissement, année). No-op sous SQLite, effectif sous
        # PostgreSQL (le SGBD de production).
        seq = (
            StudentMatriculeSequence.objects
            .select_for_update()
            .get(pk=seq.pk)
        )
        seq.last_number += 1
        seq.save(update_fields=["last_number"])
        return f"{base}{seq.last_number:04d}"


class StudentMatriculeSequence(models.Model):
    """
    Compteur séquentiel de matricules, unique par (établissement, année
    système). Garantit des numéros ``NNNN`` sans trou de doublon même en
    création concurrente, et un redémarrage automatique à chaque année.
    """
    school = models.ForeignKey(
        "schools.School", on_delete=models.CASCADE, null=True, blank=True,
        related_name="matricule_sequences",
    )
    year = models.PositiveIntegerField(help_text="Année système (ex. 2026).")
    last_number = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = "Séquence de matricules"
        verbose_name_plural = "Séquences de matricules"
        constraints = [
            models.UniqueConstraint(
                fields=["school", "year"], name="unique_matricule_sequence_per_school_year"
            ),
        ]

    def __str__(self):
        return f"{self.school_id or '—'} / {self.year} → {self.last_number:04d}"


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
        # légitimement attribuer le même matricule "FEBA-26-0001"
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
