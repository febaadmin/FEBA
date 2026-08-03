"""
apps/schedule/serializers.py — Emplois du temps FEBA et FEBA FHA

Deux serializers distincts pour deux métiers distincts (voir models.py) :
les champs affichés, les validations et même la notion de conflit ne sont
pas les mêmes. Un serializer unique aurait dû rendre optionnels tous les
champs des deux côtés — donc n'en valider aucun.
"""
from rest_framework import serializers

from apps.core.academy_serializers import ACADEMY_FIELDS, AcademyMetadataMixin

from .models import ClassSchedule, OnlineSessionSchedule


class ClassScheduleSerializer(AcademyMetadataMixin, serializers.ModelSerializer):
    """Créneau présentiel FEBA — classe, matière, enseignant, salle physique."""

    #: L'année scolaire porte l'académie (une classe n'a pas de champ école).
    academy_source = "school_year.school"

    class_name = serializers.CharField(source="cls.name", read_only=True)
    subject_name = serializers.CharField(source="subject.name", read_only=True)
    subject_code = serializers.CharField(source="subject.code", read_only=True)
    teacher_name = serializers.SerializerMethodField()
    teacher_email = serializers.SerializerMethodField()
    day_label = serializers.CharField(source="get_day_of_week_display", read_only=True)
    school_year_name = serializers.CharField(source="school_year.name", read_only=True)

    class Meta:
        model = ClassSchedule
        fields = "__all__"

    def get_teacher_name(self, obj):
        return obj.teacher.user.get_full_name() if obj.teacher else ""

    def get_teacher_email(self, obj):
        return obj.teacher.user.email if obj.teacher else ""

    def validate(self, attrs):
        """Validation métier des créneaux :
        - heure de fin strictement après l'heure de début ;
        - pas de chevauchement pour la même CLASSE, le même ENSEIGNANT
          ou la même SALLE (même jour, même année scolaire) ;
        - aucune relation entre objets d'académies différentes.
        """
        def field(name):
            if name in attrs:
                return attrs[name]
            return getattr(self.instance, name, None) if self.instance else None

        # Cohérence d'académie AVANT tout le reste : un créneau qui mélange
        # deux académies ne doit même pas être testé pour les conflits
        # horaires, la question ne se pose pas.
        candidate = ClassSchedule(
            cls=field("cls"), subject=field("subject"),
            teacher=field("teacher"), school_year=field("school_year"),
            day_of_week=field("day_of_week") or 0,
            start_time=field("start_time"), end_time=field("end_time"),
        )
        try:
            candidate.clean()
        except Exception as exc:  # ValidationError Django → ValidationError DRF
            raise serializers.ValidationError(getattr(exc, "messages", [str(exc)]))

        start, end = field("start_time"), field("end_time")
        if start and end and end <= start:
            raise serializers.ValidationError(
                {"end_time": "L'heure de fin doit être postérieure à l'heure de début."}
            )

        day = field("day_of_week")
        year = field("school_year")
        if start is None or end is None or day is None:
            return attrs

        overlapping = ClassSchedule.objects.filter(
            day_of_week=day,
            start_time__lt=end,
            end_time__gt=start,
        )
        if year is not None:
            overlapping = overlapping.filter(school_year=year)
        if self.instance:
            overlapping = overlapping.exclude(pk=self.instance.pk)

        cls = field("cls")
        if cls and overlapping.filter(cls=cls).exists():
            raise serializers.ValidationError(
                "Conflit d'horaire : cette classe a déjà un cours sur ce créneau."
            )
        teacher = field("teacher")
        if teacher and overlapping.filter(teacher=teacher).exists():
            raise serializers.ValidationError(
                "Conflit d'horaire : cet enseignant a déjà un cours sur ce créneau."
            )
        room = field("room")
        if room and overlapping.filter(room=room).exists():
            raise serializers.ValidationError(
                "Conflit d'horaire : cette salle est déjà occupée sur ce créneau."
            )
        return attrs


class OnlineSessionScheduleSerializer(AcademyMetadataMixin, serializers.ModelSerializer):
    """
    Séance en direct FEBA FHA — groupe en ligne, salle virtuelle, UTC.

    Aucune notion de salle physique ici : le conflit à éviter n'est pas
    l'occupation d'une pièce mais le doublon d'un groupe ou la double
    réservation d'un enseignant.
    """

    academy_source = "academy"

    group_name = serializers.CharField(source="group.name", read_only=True)
    subject_name = serializers.CharField(source="subject.name", read_only=True)
    teacher_name = serializers.SerializerMethodField()
    day_label = serializers.CharField(source="get_day_of_week_display", read_only=True)
    school_year_name = serializers.CharField(source="school_year.name", read_only=True)

    end_time_utc = serializers.SerializerMethodField()
    local_start_label = serializers.SerializerMethodField()
    local_day_label = serializers.SerializerMethodField()
    virtual_room_name = serializers.CharField(source="virtual_room.name", read_only=True)
    join_endpoint = serializers.CharField(read_only=True)

    class Meta:
        model = OnlineSessionSchedule
        fields = "__all__"
        read_only_fields = ["academy", "created_at", "updated_at"]

    def get_teacher_name(self, obj):
        return obj.teacher.user.get_full_name() if obj.teacher else ""

    def get_end_time_utc(self, obj):
        end = obj.end_time_utc
        return end.strftime("%H:%M") if end else None

    def get_local_start_label(self, obj):
        """Heure de début rendue dans le fuseau d'affichage de la séance."""
        local = obj.local_start()
        return local.strftime("%H:%M") if local else None

    def get_local_day_label(self, obj):
        """
        Jour LOCAL de la séance.

        Il peut différer du jour UTC : une séance à 00 h 30 UTC le mardi a
        lieu le lundi soir sur la côte est. Sans ce champ, l'interface
        afficherait le mauvais jour aux familles.
        """
        local = obj.local_start()
        if local is None:
            return None
        return dict(OnlineSessionSchedule._meta.get_field("day_of_week").choices).get(
            local.weekday()
        )

    def validate(self, attrs):
        def field(name):
            if name in attrs:
                return attrs[name]
            return getattr(self.instance, name, None) if self.instance else None

        academy = self.context.get("academy")
        if academy is None and self.instance is not None:
            academy = self.instance.academy

        candidate = OnlineSessionSchedule(
            academy=academy,
            group=field("group"), subject=field("subject"),
            teacher=field("teacher"), school_year=field("school_year"),
            virtual_room=field("virtual_room"),
            day_of_week=field("day_of_week") or 0,
            start_time_utc=field("start_time_utc"),
            duration_minutes=field("duration_minutes") or 60,
            reminders_enabled=(
                True if field("reminders_enabled") is None else field("reminders_enabled")
            ),
            reminder_minutes_before=field("reminder_minutes_before") or 0,
        )
        try:
            candidate.clean()
        except Exception as exc:
            raise serializers.ValidationError(getattr(exc, "messages", [str(exc)]))

        # Chevauchement pour un même enseignant : une personne ne peut pas
        # animer deux groupes en même temps, même en ligne.
        teacher = field("teacher")
        start = field("start_time_utc")
        day = field("day_of_week")
        if teacher and start is not None and day is not None:
            end = candidate.end_time_utc
            clash = OnlineSessionSchedule.objects.filter(
                teacher=teacher, day_of_week=day, is_active=True,
            )
            if self.instance:
                clash = clash.exclude(pk=self.instance.pk)
            for other in clash:
                if other.start_time_utc < end and other.end_time_utc > start:
                    raise serializers.ValidationError(
                        "Conflit d'horaire : cet enseignant anime déjà une "
                        "séance sur ce créneau (heures comparées en UTC)."
                    )

        return attrs


#: Réexporté pour les vues qui construisent des réponses ad hoc.
__all__ = [
    "ACADEMY_FIELDS",
    "ClassScheduleSerializer",
    "OnlineSessionScheduleSerializer",
]
