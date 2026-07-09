import logging
logger = logging.getLogger("apps")
from django.db import models
from django.utils.text import slugify


class School(models.Model):
    """
    Établissement scolaire — racine "tenant" de la plateforme SaaS.

    Chaque établissement est un client isolé : ses données (élèves,
    enseignants, classes, notes, paiements...) ne sont jamais visibles
    par un autre établissement. Voir apps/core/tenancy.py pour les
    règles d'isolation appliquées au niveau API.
    """
    PLAN_CHOICES = [
        ("trial", "Essai gratuit"),
        ("standard", "Standard"),
        ("premium", "Premium"),
    ]

    name = models.CharField(max_length=200)
    slug = models.SlugField(
        max_length=80, unique=True, blank=True,
        help_text="Identifiant court unique (sous-domaine / sélection tenant). Généré automatiquement si vide.",
    )
    address = models.TextField()
    city = models.CharField(max_length=100, default="Cotonou")
    country = models.CharField(max_length=100, default="Bénin")
    phone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    logo = models.ImageField(upload_to="school/", null=True, blank=True)
    description = models.TextField(blank=True)

    # --- Champs "tenant" (gestion commerciale SaaS) -----------------------
    is_active = models.BooleanField(
        default=True,
        help_text="Un établissement désactivé ne peut plus se connecter (suspension d'abonnement, impayé...).",
    )
    plan = models.CharField(max_length=20, choices=PLAN_CHOICES, default="trial")
    max_students = models.PositiveIntegerField(
        default=0, help_text="0 = illimité. Quota contractuel selon le plan souscrit.",
    )
    trial_ends_at = models.DateField(null=True, blank=True)
    subscription_notes = models.TextField(
        blank=True, help_text="Notes internes (équipe commerciale/support), non visibles par l'établissement.",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "École"

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.name)[:70] or "ecole"
            slug = base
            i = 1
            while School.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                i += 1
                slug = f"{base}-{i}"
            self.slug = slug
        super().save(*args, **kwargs)

    def is_over_quota(self):
        """True si l'établissement a dépassé son quota d'élèves actifs."""
        if not self.max_students:
            return False
        return self.students.filter(is_active=True).count() > self.max_students

    def get_active_logo_url(self, request=None):
        try:
            branding = self.branding_versions.filter(is_active=True).latest("uploaded_at")
            if branding.logo and request:
                return branding.logo.url
            elif branding.logo:
                return branding.logo.url
        except Exception as exc:
            logger.warning("Erreur non bloquante ignorée : %s", exc, exc_info=True)
        if self.logo:
            if request:
                return self.logo.url
            return self.logo.url
        return None


class SchoolBranding(models.Model):
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="branding_versions")
    logo = models.ImageField(upload_to="branding/", null=True, blank=True)
    is_active = models.BooleanField(default=False)
    label = models.CharField(max_length=100, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    uploaded_by = models.ForeignKey(
        "accounts.CustomUser", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="uploaded_brandings",
    )

    class Meta:
        verbose_name = "Version branding"
        ordering = ["-uploaded_at"]

    def __str__(self):
        status = "Active" if self.is_active else "Archive"
        return f"{self.school.name} [{status}]"

    def activate(self):
        SchoolBranding.objects.filter(school=self.school, is_active=True).update(is_active=False)
        self.is_active = True
        self.save(update_fields=["is_active"])

    @classmethod
    def get_active_logo_path(cls, school):
        try:
            b = cls.objects.filter(school=school, is_active=True).latest("uploaded_at")
            if b.logo:
                return b.logo.path
        except cls.DoesNotExist as exc:
            logger.warning("Erreur non bloquante ignorée : %s", exc, exc_info=True)
        if school.logo:
            return school.logo.path
        return None


class SchoolYear(models.Model):
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="years")
    name = models.CharField(max_length=20)
    start_date = models.DateField()
    end_date = models.DateField()
    is_current = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Année scolaire"
        ordering = ["-start_date"]
        # FIX v32 : pas deux années du même nom dans un établissement.
        # FIX v39 : au plus UNE année active (is_current=True) par
        # établissement — garantit au niveau base que la puce « Année active »
        # et le contenu filtré désignent toujours la même année.
        constraints = [
            models.UniqueConstraint(fields=["school", "name"], name="uniq_schoolyear_school_name"),
            models.UniqueConstraint(
                fields=["school"], condition=models.Q(is_current=True),
                name="uniq_current_year_per_school",
            ),
        ]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if self.is_current:
            SchoolYear.objects.filter(school=self.school, is_current=True).update(is_current=False)
        super().save(*args, **kwargs)


class Level(models.Model):
    CYCLE_CHOICES = [
        ("maternelle", "Maternelle"),
        ("primaire", "Primaire"),
        ("college", "Collège"),
        ("lycee", "Lycée"),
    ]
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="levels")
    name = models.CharField(max_length=50)
    order = models.PositiveIntegerField(default=0)
    cycle = models.CharField(max_length=20, choices=CYCLE_CHOICES, default="primaire")

    class Meta:
        verbose_name = "Niveau"
        ordering = ["order"]

    def __str__(self):
        return self.name

    def is_maternelle(self):
        return self.cycle == "maternelle"


class RoomType(models.Model):
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="room_types")
    name = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Type de salle"
        ordering = ["name"]
        unique_together = [["school", "name"]]

    def __str__(self):
        return self.name


class Room(models.Model):
    ROOM_TYPES = [
        ("classroom", "Salle de classe"),
        ("computer", "Salle informatique"),
        ("canteen", "Cantine"),
        ("library", "Bibliothèque"),
        ("sports", "Salle de sport"),
        ("dance", "Salle de danse"),
        ("admin", "Bureau administratif"),
        ("custom", "Type personnalisé"),
        ("other", "Autre"),
    ]
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="rooms")
    name = models.CharField(max_length=100)
    room_type = models.CharField(max_length=20, choices=ROOM_TYPES, default="classroom")
    custom_type_label = models.CharField(max_length=100, blank=True)
    room_type_obj = models.ForeignKey(
        RoomType, on_delete=models.SET_NULL, null=True, blank=True, related_name="rooms"
    )
    capacity = models.PositiveIntegerField(default=30)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Salle"
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.get_room_type_display()})"

    def get_display_type(self):
        if self.room_type_obj:
            return self.room_type_obj.name
        if self.room_type == "custom" and self.custom_type_label:
            return self.custom_type_label
        return self.get_room_type_display()
