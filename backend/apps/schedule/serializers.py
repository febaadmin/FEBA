from rest_framework import serializers
from .models import ClassSchedule


class ClassScheduleSerializer(serializers.ModelSerializer):
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
        """Validation métier des créneaux (mission audit) :
        - heure de fin strictement après l'heure de début ;
        - pas de chevauchement pour la même CLASSE, le même ENSEIGNANT
          ou la même SALLE (même jour, même année scolaire).
        """
        def field(name):
            if name in attrs:
                return attrs[name]
            return getattr(self.instance, name, None) if self.instance else None

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
