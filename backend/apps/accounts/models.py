from django.contrib.auth.models import AbstractUser
from django.db import models


class CustomUser(AbstractUser):
    ROLE_CHOICES = [
        ('superadmin', 'Super Administrateur'),
        ('admin', 'Administrateur'),
        ('teacher', 'Enseignant'),
        ('parent', 'Parent'),
        ('student', 'Élève'),
    ]

    # Role level mapping for hierarchical checks
    ROLE_LEVELS = {
        'superadmin': 100,
        'admin': 80,
        'teacher': 50,
        'parent': 30,
        'student': 10,
    }

    LANGUAGE_CHOICES = [
        ('fr', 'Français'),
        ('en', 'English'),
    ]

    email = models.EmailField(unique=True)
    role = models.CharField(max_length=12, choices=ROLE_CHOICES, default='student')
    role_level = models.PositiveSmallIntegerField(default=10)
    phone = models.CharField(max_length=20, blank=True)
    # Préférence linguistique de l'interface (fr/en). Prioritaire sur le
    # choix local du navigateur lorsque l'utilisateur se reconnecte.
    preferred_language = models.CharField(
        max_length=5, choices=LANGUAGE_CHOICES, default='fr',
        help_text="Langue préférée de l'interface / Preferred interface language.",
    )
    avatar = models.ImageField(upload_to='avatars/', null=True, blank=True)
    is_active = models.BooleanField(default=True)
    # Tenant : établissement de rattachement. Obligatoire pour tout rôle
    # sauf 'superadmin' (rôle plateforme, transverse à tous les
    # établissements). Voir apps/core/tenancy.py pour les règles d'usage.
    school = models.ForeignKey(
        'schools.School', on_delete=models.PROTECT, null=True, blank=True,
        related_name='users',
        help_text="Établissement de rattachement. Obligatoire sauf pour le rôle superadmin.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username', 'first_name', 'last_name']

    class Meta:
        verbose_name = 'Utilisateur'
        verbose_name_plural = 'Utilisateurs'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.get_full_name()} ({self.email})"

    def save(self, *args, **kwargs):
        # Always sync role_level from role
        self.role_level = self.ROLE_LEVELS.get(self.role, 10)
        super().save(*args, **kwargs)

    # ── Role helpers ──────────────────────────────────────────────────────────
    def is_superadmin(self):
        return self.role == 'superadmin'

    def is_admin(self):
        return self.role == 'admin'

    def is_admin_or_above(self):
        return self.role_level >= self.ROLE_LEVELS['admin']

    def is_teacher(self):
        return self.role == 'teacher'

    def is_parent(self):
        return self.role == 'parent'

    def is_student(self):
        return self.role == 'student'

    def can_manage(self, target_user):
        """Can self manage/edit target_user?"""
        if self.is_superadmin():
            return True
        if self.is_admin():
            # Admin cannot manage superadmins or other admins,
            # and never manages a user from another établissement.
            if target_user.school_id != self.school_id:
                return False
            return target_user.role_level < self.ROLE_LEVELS['admin']
        return False

    def requires_school(self):
        """Tout rôle sauf superadmin doit être rattaché à un établissement."""
        return self.role != 'superadmin'
