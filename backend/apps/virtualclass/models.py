"""
Salles virtuelles (visioconférence) — module FEBA.

Implémentation basée sur Jitsi Meet (open source, gratuit) :
la salle est identifiée par un `room_code` non devinable ; le client
rejoint la réunion via l'API externe Jitsi (iframe), soit sur
l'instance FEBA AUTO-HÉBERGÉE configurée via JITSI_DOMAIN.
Aucune instance publique n'est utilisée : voir apps/virtualclass/services.py.

Sécurité :
 - le room_code contient un segment aléatoire (uuid) → non énumérable ;
 - l'accès à la liste des salles est filtré par tenant (établissement)
   et par rôle (élève/parent : uniquement les salles de leur classe ou
   les salles générales de l'établissement).
"""
import uuid

from django.conf import settings
from django.db import models
from django.utils.text import slugify


def generate_room_code(name, school=None):
    """Code de salle unique, lisible et non devinable."""
    base = slugify(name)[:30] or "salle"
    prefix = (school.slug if school and school.slug else "feba")[:20]
    return f"{prefix}-{base}-{uuid.uuid4().hex[:10]}"


class VirtualRoom(models.Model):
    STATUS_CHOICES = [
        ("scheduled", "Planifiée"),
        ("live", "En cours"),
        ("ended", "Terminée"),
        ("cancelled", "Annulée"),
    ]

    school = models.ForeignKey(
        "schools.School", on_delete=models.CASCADE, related_name="virtual_rooms",
    )
    school_year = models.ForeignKey(
        "schools.SchoolYear", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="virtual_rooms",
    )
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    room_code = models.CharField(
        max_length=80, unique=True, blank=True,
        help_text="Identifiant Jitsi de la salle. Généré automatiquement (non devinable).",
    )
    class_obj = models.ForeignKey(
        "classes.Class", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="virtual_rooms", db_column="class_id",
        help_text="Classe concernée. Vide = salle générale (tout l'établissement).",
    )
    subject = models.ForeignKey(
        "subjects.Subject", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="virtual_rooms",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
        related_name="virtual_rooms_created",
    )
    scheduled_at = models.DateTimeField(
        null=True, blank=True, help_text="Date/heure planifiée. Vide = salle permanente.",
    )
    duration_minutes = models.PositiveIntegerField(default=60)
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default="scheduled")
    is_active = models.BooleanField(default=True)
    lobby_enabled = models.BooleanField(
        default=True,
        help_text="Salle d'attente Jitsi recommandée côté client (les invités attendent l'hôte).",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Salle virtuelle"
        verbose_name_plural = "Salles virtuelles"
        ordering = ["-scheduled_at", "-created_at"]

    def __str__(self):
        return f"{self.name} ({self.room_code})"

    def save(self, *args, **kwargs):
        if not self.room_code:
            for _ in range(5):
                candidate = generate_room_code(self.name, self.school)
                if not VirtualRoom.objects.filter(room_code=candidate).exclude(pk=self.pk).exists():
                    self.room_code = candidate
                    break
            else:  # pragma: no cover — collision uuid quasi impossible
                self.room_code = f"feba-{uuid.uuid4().hex}"
        super().save(*args, **kwargs)


class VirtualRoomAttendance(models.Model):
    """
    Historique de participation aux cours virtuels.
    FIX v35 : pour un élève, la présence est liée à son INSCRIPTION
    ANNUELLE (modèle métier : la présence appartient à l'année), avec
    suivi de la sortie et de la durée.
    """
    room = models.ForeignKey(VirtualRoom, on_delete=models.CASCADE, related_name="attendances")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="virtual_room_attendances",
    )
    enrollment = models.ForeignKey(
        "students.StudentEnrollment", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="virtual_attendances",
        help_text="Inscription annuelle de l'élève (null pour enseignants/admins).",
    )
    joined_at = models.DateTimeField(auto_now_add=True)
    left_at = models.DateTimeField(null=True, blank=True)
    duration_seconds = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        verbose_name = "Participation salle virtuelle"
        ordering = ["-joined_at"]

    def __str__(self):
        return f"{self.user} → {self.room} ({self.joined_at:%d/%m/%Y %H:%M})"
