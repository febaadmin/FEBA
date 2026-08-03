from decimal import Decimal
from rest_framework import serializers
from .grading import ASSESSMENT_WEIGHT
from .models import Grade, GradeHistory, get_letter_grade, get_appreciation
from apps.core.academy_serializers import ACADEMY_FIELDS, AcademyMetadataMixin


class GradeHistorySerializer(serializers.ModelSerializer):
    changed_by_name = serializers.SerializerMethodField()

    class Meta:
        model = GradeHistory
        fields = ['id', 'grade', 'changed_by', 'changed_by_name', 'old_value',
                  'new_value', 'old_comment', 'new_comment', 'justification',
                  'action', 'changed_at']

    def get_changed_by_name(self, obj):
        return obj.changed_by.get_full_name() if obj.changed_by else None


class GradeSerializer(AcademyMetadataMixin, serializers.ModelSerializer):
    #: Chemin ORM vers l'académie propriétaire de l'objet.
    academy_source = "student.school"

    student_name    = serializers.SerializerMethodField()
    subject_name    = serializers.SerializerMethodField()
    teacher_name    = serializers.SerializerMethodField()
    school_year_name = serializers.SerializerMethodField()
    note_type_display = serializers.SerializerMethodField()
    # FIX v20: alias pour compatibilité frontend
    note_type_label = serializers.SerializerMethodField()
    subject_coefficient = serializers.SerializerMethodField()
    letter          = serializers.SerializerMethodField()
    meaning         = serializers.SerializerMethodField()
    appreciation    = serializers.SerializerMethodField()
    deleted_by_name = serializers.SerializerMethodField()
    history         = GradeHistorySerializer(many=True, read_only=True)

    class Meta:
        model = Grade
        # V8 : note_coefficient est imposé à 1 par le backend — jamais saisi.
        read_only_fields = ['note_coefficient']
        fields = [
            'id', 'student', 'student_name', 'subject', 'subject_name',
            'subject_coefficient', 'teacher', 'teacher_name',
            'school_year', 'school_year_name',
            'period', 'value', 'note_type', 'note_type_display', 'note_type_label',
            'note_coefficient', 'comment', 'graded_at',
            'letter', 'meaning', 'appreciation',
            'is_deleted', 'deleted_at', 'deleted_by', 'deleted_by_name',
            'created_at', 'updated_at',
            'history',
        ] + ACADEMY_FIELDS

    def get_note_type_label(self, obj):
        return obj.get_note_type_display()

    def get_subject_coefficient(self, obj):
        return obj.subject.coefficient if obj.subject else 1

    def get_appreciation(self, obj):
        from .models import get_appreciation
        return get_appreciation(obj.value)

    def get_deleted_by_name(self, obj):
        if obj.deleted_by:
            return obj.deleted_by.get_full_name()
        return None

    def get_student_name(self, obj):
        return obj.student.get_full_name() if obj.student else None

    def get_subject_name(self, obj):
        return obj.subject.name if obj.subject else None

    def get_teacher_name(self, obj):
        if obj.teacher and obj.teacher.user:
            return obj.teacher.user.get_full_name()
        return None

    def get_school_year_name(self, obj):
        return obj.school_year.name if obj.school_year else None

    def get_note_type_display(self, obj):
        return obj.get_note_type_display()

    def get_letter(self, obj):
        letter, _, _ = get_letter_grade(obj.value)
        return letter

    def get_meaning(self, obj):
        _, meaning, _ = get_letter_grade(obj.value)
        return meaning


# ── Saisie GROUPÉE de notes (V6) ────────────────────────────────────────────

class BulkGradeLineSerializer(serializers.Serializer):
    """
    Une ligne de la saisie groupée. Validation de champ uniquement (types,
    bornes, choix). Les contrôles métier (matière assignée à l'enseignant,
    élève de la classe, tenant, année) sont faits dans la vue avec des
    erreurs indexées par ligne.
    """
    subject = serializers.IntegerField(min_value=1)
    period = serializers.ChoiceField(choices=[c[0] for c in Grade.PERIOD_CHOICES])
    value = serializers.DecimalField(
        max_digits=4, decimal_places=2, min_value=Decimal("0"), max_value=Decimal("20"),
        error_messages={
            "min_value": "La note doit être comprise entre 0 et 20.",
            "max_value": "La note dépasse le barème (max 20).",
            "invalid": "La note doit être numérique.",
        },
    )
    note_type = serializers.ChoiceField(
        choices=[c[0] for c in Grade.NOTE_TYPE_CHOICES], default="devoir",
    )
    # V8 : le poids d'une évaluation vaut toujours 1. Le champ reste accepté
    # (compatibilité des clients existants) mais sa valeur est NORMALISÉE :
    # une requête envoyant 2 ou 3 n'accorde aucun avantage à l'évaluation.
    note_coefficient = serializers.IntegerField(
        min_value=1, default=ASSESSMENT_WEIGHT, required=False,
        error_messages={"min_value": "Le coefficient doit être au moins 1."},
    )

    comment = serializers.CharField(required=False, allow_blank=True, default="")
    justification = serializers.CharField(required=False, allow_blank=True, default="")

    def validate_note_coefficient(self, value):
        return ASSESSMENT_WEIGHT


class BulkGradeCreateSerializer(serializers.Serializer):
    """Enveloppe de la saisie groupée : un élève, une année, N lignes de notes."""
    student = serializers.IntegerField(min_value=1)
    school_year = serializers.IntegerField(min_value=1, required=False, allow_null=True)
    grades = BulkGradeLineSerializer(
        many=True,
        error_messages={"empty": "Ajoutez au moins une note.", "min_length": "Ajoutez au moins une note."},
    )

    def validate_grades(self, value):
        if not value:
            raise serializers.ValidationError("Ajoutez au moins une note.")
        return value


class StudentGradeSummarySerializer(serializers.Serializer):
    """Serializer for the student summary view."""
    student_id = serializers.IntegerField()
    student_name = serializers.CharField()
    class_name = serializers.CharField(allow_null=True)
    school_year = serializers.CharField()
    period = serializers.CharField()
    average = serializers.DecimalField(max_digits=4, decimal_places=2, allow_null=True)
    letter = serializers.CharField(allow_null=True)
    meaning = serializers.CharField(allow_null=True)
    rank = serializers.IntegerField(allow_null=True)
    total_in_class = serializers.IntegerField()
    subjects = serializers.ListField()
