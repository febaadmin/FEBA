from rest_framework import serializers
from .models import Class
from apps.core.academy_serializers import ACADEMY_FIELDS, AcademyMetadataMixin


class ClassSerializer(AcademyMetadataMixin, serializers.ModelSerializer):
    # P3 : chaque objet expose son académie, sans quoi la vue
    # « Toutes les Académies » ne peut pas étiqueter ses lignes.
    academy_source = "school_year.school"
    level_name       = serializers.CharField(source="level.name",       read_only=True)
    level_cycle      = serializers.CharField(source="level.cycle",      read_only=True)
    school_year_name = serializers.CharField(source="school_year.name", read_only=True)
    student_count    = serializers.SerializerMethodField()
    subjects_detail  = serializers.SerializerMethodField()
    has_bilingual    = serializers.SerializerMethodField()
    fr_subject_count = serializers.SerializerMethodField()
    en_subject_count = serializers.SerializerMethodField()

    # IDs pour écriture — ListField simple, pas de queryset au niveau classe
    subject_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        required=False,
        write_only=False,
        allow_empty=True,
    )

    class Meta:
        model = Class
        fields = [
            "id", "name", "level", "level_name", "level_cycle",
            "school_year", "school_year_name", "max_students",
            "student_count",
            "subjects_detail", "subject_ids",
            "has_bilingual", "fr_subject_count", "en_subject_count",
            "created_at",
        ] + ACADEMY_FIELDS

    def get_student_count(self, obj):
        # FIX v37 (vidéo 3) : l'effectif d'une classe se compte via les
        # INSCRIPTIONS annuelles (une classe appartient à une année), plus
        # via le pointeur current_class — les classes des années passées
        # affichaient toutes 0/30 alors que leurs inscriptions existent.
        count = obj.enrollments.filter(student__is_active=True).values("student").distinct().count()
        if count:
            return count
        # Repli : élèves jamais formellement inscrits (pointeur seul)
        return obj.students.filter(is_active=True).count()

    def get_subjects_detail(self, obj):
        from apps.subjects.serializers import SubjectSerializer
        return SubjectSerializer(
            obj.subjects.all().order_by("language", "order", "name"),
            many=True,
        ).data

    def get_has_bilingual(self, obj):
        return obj.has_bilingual_subjects()

    def get_fr_subject_count(self, obj):
        return obj.get_fr_subjects().count()

    def get_en_subject_count(self, obj):
        return obj.get_en_subjects().count()

    def to_representation(self, instance):
        """Ajoute subject_ids (liste d'entiers) dans la réponse GET."""
        rep = super().to_representation(instance)
        rep["subject_ids"] = list(
            instance.subjects.values_list("id", flat=True)
        )
        return rep

    def _set_subjects(self, instance, subject_ids):
        """Applique la liste de sujets sur l'instance."""
        if subject_ids is None:
            return
        from apps.subjects.models import Subject
        subjects = Subject.objects.filter(id__in=subject_ids)
        instance.subjects.set(subjects)

    def create(self, validated_data):
        subject_ids = validated_data.pop("subject_ids", None)
        instance = super().create(validated_data)
        self._set_subjects(instance, subject_ids)
        return instance

    def update(self, instance, validated_data):
        subject_ids = validated_data.pop("subject_ids", None)
        instance = super().update(instance, validated_data)
        self._set_subjects(instance, subject_ids)
        return instance
