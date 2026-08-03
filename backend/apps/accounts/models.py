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
    # Positionné à True quand un administrateur réinitialise le mot de passe :
    # l'utilisateur doit choisir un nouveau mot de passe à sa prochaine
    # connexion (le frontend force le parcours, change-password remet à False).
    must_change_password = models.BooleanField(
        default=False,
        help_text="L'utilisateur doit changer son mot de passe à la prochaine connexion.",
    )
    # Tenant : établissement de rattachement. Obligatoire pour tout rôle
    # sauf 'superadmin' (rôle plateforme, transverse à tous les
    # établissements). Voir apps/core/tenancy.py pour les règles d'usage.
    school = models.ForeignKey(
        'schools.School', on_delete=models.PROTECT, null=True, blank=True,
        related_name='users',
        help_text="Établissement de rattachement. Obligatoire sauf pour le rôle superadmin.",
    )
    # Entité active du Super Administrateur, PERSISTÉE CÔTÉ SERVEUR.
    # C'est la seule source d'autorité du contexte d'entité : le frontend
    # ne peut pas l'imposer via localStorage ni via un entity_id de payload.
    # Ignoré pour les autres rôles, dont le contexte est toujours `school`.
    active_organization = models.ForeignKey(
        'schools.School', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='active_for_users',
        help_text=(
            "Entité active du superadmin (NULL = mode « toutes les entités »). "
            "Modifiable uniquement via l'endpoint de bascule, qui journalise le changement."
        ),
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

    def can_reset_password_of(self, target_user):
        """
        Règles métier de la réinitialisation de mot de passe (P2 v4) :
        - personne ne réinitialise son PROPRE mot de passe ici (parcours
          « changer mon mot de passe » distinct, avec ancien mot de passe) ;
        - superadmin → admin / teacher / parent / student, jamais un autre
          superadmin (pas de règle métier l'autorisant) ;
        - admin → teacher / parent / student de SON établissement uniquement,
          jamais un admin ni un superadmin ;
        - tous les autres rôles → jamais.
        """
        if target_user.pk == self.pk:
            return False
        if self.is_superadmin():
            return target_user.role in ('admin', 'teacher', 'parent', 'student')
        if self.is_admin():
            if target_user.school_id != self.school_id:
                return False
            return target_user.role in ('teacher', 'parent', 'student')
        return False


class PasswordResetLog(models.Model):
    """
    Journal d'audit des réinitialisations de mot de passe par un
    administrateur. NE CONTIENT JAMAIS le mot de passe (ni en clair, ni haché).
    """
    performed_by = models.ForeignKey(
        CustomUser, on_delete=models.SET_NULL, null=True,
        related_name='password_resets_performed',
    )
    target_user = models.ForeignKey(
        CustomUser, on_delete=models.CASCADE,
        related_name='password_resets_received',
    )
    performed_by_email = models.EmailField(
        help_text="Copie de l'email de l'auteur (résiste à la suppression du compte).",
    )
    target_email = models.EmailField()
    target_role = models.CharField(max_length=12)
    school = models.ForeignKey(
        'schools.School', on_delete=models.SET_NULL, null=True, blank=True,
    )
    performed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Réinitialisation de mot de passe'
        verbose_name_plural = 'Réinitialisations de mot de passe'
        ordering = ['-performed_at']

    def __str__(self):
        return (
            f'{self.performed_by_email} → {self.target_email} '
            f'({self.target_role}) le {self.performed_at:%Y-%m-%d %H:%M}'
        )
