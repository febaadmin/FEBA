"""
Salles virtuelles (visioconférence) — module FEBA.

Moteur : plugNmeet AUTO-HÉBERGÉ (apps/virtualclass/plugnmeet.py) ; Jitsi
ne subsiste que comme moteur de retour arrière (VIDEO_PROVIDER=jitsi).
La salle est identifiée par un `room_code` non devinable, qui sert aussi
d'identifiant de salle côté plugNmeet. Aucune instance publique.

Sécurité :
 - le room_code contient un segment aléatoire (uuid) → non énumérable ;
 - l'accès à la liste des salles est filtré par tenant (établissement)
   et par rôle (élève/parent : uniquement les salles de leur classe ou
   les salles générales de l'établissement).
"""
import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone
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
        help_text="Identifiant de la salle (plugNmeet). Généré automatiquement (non devinable).",
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
    # ── Ciblage par RÔLE ─────────────────────────────────────────────────
    #
    # Une salle pouvait viser une classe, ou toute l'académie — rien entre
    # les deux. Il manquait le cas courant : la réunion pédagogique
    # réservée aux enseignants, le conseil réservé aux administrateurs.
    # Sans ce champ, une « salle générale » créée pour l'équipe était
    # ouverte à tous les élèves de l'académie.
    #
    # Liste vide = aucun filtre de rôle (comportement historique). Les
    # salles existantes restent donc strictement inchangées.
    target_roles = models.JSONField(
        default=list, blank=True,
        verbose_name="Rôles autorisés",
        help_text=(
            "Rôles pouvant rejoindre la salle (admin, teacher, student, "
            "parent). Vide = tous les rôles autorisés par ailleurs."
        ),
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
        help_text="Salle d'attente : les participants attendent l'admission par l'enseignant.",
    )
    allow_recording = models.BooleanField(
        default=False, db_default=False,
        help_text=("Enregistrement autorisé dans cette salle (effectif seulement si le "
                   "service d'enregistrement est déployé : PLUGNMEET_RECORDING_ENABLED)."),
    )
    # ── Réunion en cours ou dernière réunion côté plugNmeet ─────────────
    # Une même salle FEBA (permanente) accueille plusieurs réunions ; `sid`
    # distingue chaque réunion, et donc chaque série de présences.
    meeting_sid = models.CharField(max_length=64, blank=True, default="", db_default="")
    meeting_started_at = models.DateTimeField(null=True, blank=True)
    meeting_ended_at = models.DateTimeField(null=True, blank=True)
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
    joined_at = models.DateTimeField(default=timezone.now)
    left_at = models.DateTimeField(null=True, blank=True)
    duration_seconds = models.PositiveIntegerField(null=True, blank=True)
    # ── Suivi par réunion (plugNmeet) ───────────────────────────────────
    # Une ligne par (salle, utilisateur, réunion). Les entrées, sorties et
    # reconnexions sont RECALCULÉES à partir des événements reçus
    # (VirtualRoomEvent), dans l'ordre chronologique : un événement reçu
    # deux fois ou en désordre ne change pas le résultat.
    session_sid = models.CharField(max_length=64, blank=True, default="", db_default="")
    reconnections = models.PositiveIntegerField(default=0, db_default=0)
    SOURCE_API, SOURCE_WEBHOOK = "api", "webhook"
    source = models.CharField(
        max_length=10, default=SOURCE_API, db_default=SOURCE_API,
        choices=[(SOURCE_API, "Appels rejoindre/quitter"), (SOURCE_WEBHOOK, "Événements plugNmeet")],
    )

    class Meta:
        verbose_name = "Participation salle virtuelle"
        ordering = ["-joined_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["room", "user", "session_sid"], condition=~Q(session_sid=""),
                name="uniq_attendance_per_meeting",
            ),
        ]

    def __str__(self):
        return f"{self.user} → {self.room} ({self.joined_at:%d/%m/%Y %H:%M})"


class VirtualRoomEvent(models.Model):
    """
    Événement reçu de plugNmeet (webhook signé), conservé tel quel.

    `event_id` est unique : un webhook rejoué (plugNmeet réessaie en cas
    d'échec réseau) n'est traité qu'une fois. Les présences sont recalculées
    à partir de CES lignes, triées par `occurred_at`.
    """
    event_id = models.CharField(max_length=64, unique=True)
    event = models.CharField(max_length=40, db_index=True)
    room = models.ForeignKey(VirtualRoom, on_delete=models.SET_NULL, null=True, blank=True,
                             related_name="events")
    external_room_id = models.CharField(max_length=128, blank=True, default="")
    session_sid = models.CharField(max_length=64, blank=True, default="", db_index=True)
    identity = models.CharField(max_length=128, blank=True, default="")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
                             blank=True, related_name="virtual_room_events")
    occurred_at = models.DateTimeField()
    received_at = models.DateTimeField(auto_now_add=True)
    payload = models.JSONField(default=dict)
    note = models.CharField(max_length=255, blank=True, default="")

    class Meta:
        verbose_name = "Événement de visioconférence"
        ordering = ["occurred_at", "id"]
        indexes = [models.Index(fields=["room", "session_sid", "user", "occurred_at"])]

    def __str__(self):
        return f"{self.event} {self.identity} @ {self.occurred_at:%d/%m %H:%M:%S}"
