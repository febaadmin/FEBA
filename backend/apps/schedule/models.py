"""
apps/schedule/models.py — Emplois du temps des deux académies

DEUX MÉTIERS, DEUX MODÈLES (P3)
-------------------------------
Un seul modèle servait les deux académies, alors qu'elles ne planifient
pas la même chose :

    FEBA (campus)      un cours a lieu dans une SALLE PHYSIQUE, à l'heure
                       locale de Cotonou, pour une classe présentielle.
                       La contrainte critique est l'occupation des salles.

    FEBA FHA (ligne)   une séance a lieu dans une SALLE VIRTUELLE, pour un
                       groupe en ligne, et est suivie depuis plusieurs
                       fuseaux horaires (États-Unis, Canada, Bénin). Il n'y
                       a pas de salle physique à réserver ; en revanche
                       l'heure doit être stockée en UTC — sinon deux
                       familles dans deux fuseaux ne voient pas la même
                       heure — et un rappel doit partir avant la séance.

Forcer les deux dans une table unique obligeait à laisser vides la moitié
des colonnes et rendait impossible toute contrainte utile : une salle
physique n'a aucun sens pour un cours en ligne, un fuseau d'affichage
aucun sens pour un cours à Akpakpa.

RELATIONS INTER-ACADÉMIES
-------------------------
Les deux modèles refusent qu'un créneau relie des objets appartenant à des
académies différentes (classe FEBA + matière FHA, par exemple). La
vérification est faite dans `clean()`, appelée depuis `save()` : elle
s'applique donc aussi bien à l'API qu'à l'admin Django, à un import ou à
un shell — et pas seulement au serializer.
"""
import datetime

from django.core.exceptions import ValidationError
from django.db import models

from apps.classes.models import Class
from apps.schools.models import School, SchoolYear
from apps.subjects.models import Subject

DAYS = [
    (0, "Lundi"), (1, "Mardi"), (2, "Mercredi"),
    (3, "Jeudi"), (4, "Vendredi"), (5, "Samedi"), (6, "Dimanche"),
]


def academy_of_class(cls):
    """Académie d'une classe, via son année scolaire."""
    if cls is None:
        return None
    year = getattr(cls, "school_year", None)
    return getattr(year, "school", None) if year is not None else None


def academy_of_teacher(teacher):
    """
    Académie d'un enseignant.

    `Teacher` n'a pas de champ `school` : son rattachement est celui de son
    compte utilisateur. Le dériver ici évite de le redécouvrir dans chaque
    appelant — et de se tromper de chemin.
    """
    if teacher is None:
        return None
    user = getattr(teacher, "user", None)
    return getattr(user, "school", None) if user is not None else None


def assert_single_academy(pairs, expected=None):
    """
    Vérifie que tous les objets liés appartiennent à la MÊME académie.

    `pairs` est une liste de couples (libellé, académie). Les académies
    nulles sont ignorées : un enseignant non renseigné ne doit pas faire
    échouer la validation, seule une INCOHÉRENCE est une erreur.

    Lève `ValidationError` en nommant les deux académies en conflit — un
    message « incohérent » sans dire lesquelles serait inexploitable.
    """
    reference = expected
    reference_label = "l'académie du créneau"

    for label, academy in pairs:
        if academy is None:
            continue
        if reference is None:
            reference, reference_label = academy, label
            continue
        if academy.pk != reference.pk:
            raise ValidationError(
                f"Relation inter-académies interdite : {label} appartient à "
                f"« {academy.name} » alors que {reference_label} appartient à "
                f"« {reference.name} ». Un créneau ne peut relier que des "
                f"objets d'une même académie."
            )
    return reference


class ClassSchedule(models.Model):
    """
    Emploi du temps FEBA — cours présentiel dans une salle physique.

    Les heures sont exprimées dans le fuseau de l'académie (Cotonou) : un
    cours de 8 h est à 8 h pour tout le monde, personne ne le suit depuis
    un autre fuseau. Stocker de l'UTC ici n'apporterait rien et rendrait
    la saisie plus fragile.
    """
    DAYS = DAYS[:6]  # FEBA ne planifie pas le dimanche.

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
        ordering = ["day_of_week", "start_time"]

    def __str__(self):
        return f"{self.cls} - {self.subject} - {self.get_day_of_week_display()} {self.start_time}"

    @property
    def academy(self):
        """Académie propriétaire — l'année scolaire fait autorité."""
        return getattr(self.school_year, "school", None)

    def clean(self):
        super().clean()
        academy = assert_single_academy([
            ("l'année scolaire", getattr(self.school_year, "school", None)),
            ("la classe", academy_of_class(self.cls)),
            ("la matière", getattr(self.subject, "school", None)),
            ("l'enseignant", academy_of_teacher(self.teacher)),
        ])

        # Un cours en salle physique n'a pas de sens pour une académie en
        # ligne : c'est le modèle OnlineSessionSchedule qui la sert.
        if academy is not None and academy.entity_type == "online":
            raise ValidationError(
                f"« {academy.name} » est une académie en ligne : ses séances "
                f"se planifient dans l'emploi du temps FEBA FHA (salle "
                f"virtuelle, fuseau horaire), pas dans l'emploi du temps "
                f"présentiel."
            )

    def save(self, *args, **kwargs):
        # `clean()` n'est PAS appelé automatiquement par `save()` en Django.
        # L'appeler ici rend la règle inviolable quel que soit le chemin
        # d'écriture (API, admin, shell, import de données).
        self.clean()
        return super().save(*args, **kwargs)


class OnlineSessionSchedule(models.Model):
    """
    Emploi du temps FEBA FHA — séance en direct d'un groupe en ligne.

    HEURE STOCKÉE EN UTC
    --------------------
    `start_time_utc` est l'heure de référence, en UTC. Chaque famille voit
    ensuite cette heure convertie dans SON fuseau. Stocker une heure locale
    « 17 h » serait ambigu : 17 h à Philadelphie et 17 h à Vancouver sont
    trois heures d'écart, et l'écart change deux fois par an avec l'heure
    d'été. `display_timezone` ne sert qu'à l'affichage de référence côté
    administration ; il ne définit jamais le moment réel de la séance.
    """
    ACADEMY_REQUIREMENT = "online"

    academy = models.ForeignKey(
        School, on_delete=models.CASCADE, related_name="online_sessions",
        help_text="Académie en ligne propriétaire de la séance.",
    )
    group = models.ForeignKey(
        Class, on_delete=models.CASCADE, related_name="online_sessions",
        db_column="group_id",
        help_text="Groupe en ligne (Junior Roots, French Explorers…).",
    )
    subject = models.ForeignKey(
        Subject, on_delete=models.CASCADE, related_name="online_sessions",
    )
    teacher = models.ForeignKey(
        "teachers.Teacher", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="online_sessions",
    )
    school_year = models.ForeignKey(
        SchoolYear, on_delete=models.CASCADE, related_name="online_sessions",
    )

    day_of_week = models.PositiveSmallIntegerField(
        choices=DAYS,
        help_text="Jour de la semaine EN UTC — le jour local peut différer.",
    )
    start_time_utc = models.TimeField(
        help_text="Heure de début en UTC. Référence unique de la séance.",
    )
    duration_minutes = models.PositiveSmallIntegerField(
        default=60, help_text="Durée en minutes (1 à 480).",
    )
    display_timezone = models.CharField(
        max_length=64, default="America/New_York",
        help_text=(
            "Fuseau de référence pour l'affichage administratif. "
            "N'influence PAS l'heure réelle de la séance."
        ),
    )

    virtual_room = models.ForeignKey(
        "virtualclass.VirtualRoom", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="scheduled_sessions",
        help_text="Salle virtuelle FEBA. Vide = lien à créer avant la séance.",
    )

    reminders_enabled = models.BooleanField(
        default=True,
        help_text="Envoie un rappel aux familles avant chaque séance.",
    )
    reminder_minutes_before = models.PositiveSmallIntegerField(
        default=30, help_text="Délai du rappel avant la séance, en minutes.",
    )

    recurrent = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Séance en ligne (FEBA FHA)"
        verbose_name_plural = "Séances en ligne (FEBA FHA)"
        ordering = ["day_of_week", "start_time_utc"]
        constraints = [
            models.CheckConstraint(
                check=models.Q(duration_minutes__gte=1) & models.Q(duration_minutes__lte=480),
                name="online_session_duration_between_1_and_480",
            ),
            models.CheckConstraint(
                check=models.Q(reminder_minutes_before__lte=1440),
                name="online_session_reminder_at_most_24h",
            ),
            # Un même groupe ne peut pas avoir deux séances au même instant.
            models.UniqueConstraint(
                fields=["group", "day_of_week", "start_time_utc"],
                name="uniq_online_session_group_slot",
            ),
        ]

    def __str__(self):
        return (
            f"{self.group} — {self.subject} — "
            f"{self.get_day_of_week_display()} {self.start_time_utc} UTC"
        )

    # ── Heures dérivées ──────────────────────────────────────────────────

    @property
    def end_time_utc(self):
        """Heure de fin en UTC, dérivée de la durée (jamais saisie deux fois)."""
        if self.start_time_utc is None or not self.duration_minutes:
            return None
        base = datetime.datetime.combine(datetime.date(2000, 1, 1), self.start_time_utc)
        return (base + datetime.timedelta(minutes=self.duration_minutes)).time()

    def local_start(self, timezone_name=None):
        """
        Heure de début dans le fuseau demandé, sous forme de datetime.

        Retourne un datetime complet — et non une heure seule — parce que la
        conversion peut changer le JOUR : une séance à 00 h 30 UTC le mardi
        est le lundi soir sur la côte est des États-Unis. Ne renvoyer que
        l'heure produirait un emploi du temps faux un jour sur deux.
        """
        from zoneinfo import ZoneInfo

        if self.start_time_utc is None:
            return None
        name = timezone_name or self.display_timezone or "UTC"
        # Semaine de référence arbitraire dont le lundi est le 3 janvier 2000 :
        # elle sert uniquement à porter le jour de la semaine.
        reference = datetime.date(2000, 1, 3) + datetime.timedelta(days=self.day_of_week or 0)
        aware = datetime.datetime.combine(
            reference, self.start_time_utc, tzinfo=datetime.timezone.utc,
        )
        try:
            return aware.astimezone(ZoneInfo(name))
        except Exception:
            # Fuseau inconnu (saisie libre, base de fuseaux incomplète) :
            # afficher l'UTC vaut mieux que ne rien afficher.
            return aware

    @property
    def join_endpoint(self):
        """
        Chemin d'entrée en visioconférence, si une salle est rattachée.

        On n'expose PAS d'URL Jitsi directe : rejoindre exige un jeton signé
        par le serveur, valable quinze minutes et lié à l'utilisateur (voir
        apps/virtualclass/services.py). Publier un lien permanent dans
        l'emploi du temps rendrait la salle accessible à quiconque le
        recopie, y compris hors de l'académie.
        """
        if self.virtual_room_id is None:
            return ""
        return f"/api/virtual-rooms/{self.virtual_room_id}/join/"

    # ── Validation métier ────────────────────────────────────────────────

    def clean(self):
        super().clean()

        if self.academy_id and self.academy.entity_type != self.ACADEMY_REQUIREMENT:
            raise ValidationError(
                f"« {self.academy.name} » est une école présentielle : ses "
                f"cours se planifient dans l'emploi du temps FEBA (classe et "
                f"salle physique), pas dans les séances en ligne."
            )

        assert_single_academy(
            [
                ("le groupe", academy_of_class(self.group)),
                ("la matière", getattr(self.subject, "school", None)),
                ("l'enseignant", academy_of_teacher(self.teacher)),
                ("l'année scolaire", getattr(self.school_year, "school", None)),
                ("la salle virtuelle", getattr(self.virtual_room, "school", None)),
            ],
            expected=self.academy if self.academy_id else None,
        )

        if self.duration_minutes and not (1 <= self.duration_minutes <= 480):
            raise ValidationError(
                {"duration_minutes": "La durée doit être comprise entre 1 et 480 minutes."}
            )

        if self.reminders_enabled and self.reminder_minutes_before > 1440:
            raise ValidationError(
                {"reminder_minutes_before": "Un rappel ne peut pas partir plus de 24 h à l'avance."}
            )

    def save(self, *args, **kwargs):
        self.clean()
        return super().save(*args, **kwargs)
