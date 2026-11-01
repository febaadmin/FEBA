from apps.core.tenancy import TenantRelationsMixin
from decimal import Decimal
from rest_framework import serializers
from .grading import ASSESSMENT_WEIGHT
from .models import Grade, GradeHistory, get_letter_grade, get_appreciation
from apps.core.academy_serializers import (
    ACADEMY_FIELDS, STUDENT_AGE_FIELDS, AcademyMetadataMixin, StudentAgeMixin,
)


class GradeHistorySerializer(serializers.ModelSerializer):
    changed_by_name = serializers.SerializerMethodField()

    class Meta:
        model = GradeHistory
        fields = ['id', 'grade', 'changed_by', 'changed_by_name', 'old_value',
                  'new_value', 'old_comment', 'new_comment', 'justification',
                  'action', 'changed_at']

    def get_changed_by_name(self, obj):
        return obj.changed_by.get_full_name() if obj.changed_by else None


class GradeSerializer(TenantRelationsMixin, AcademyMetadataMixin, StudentAgeMixin, serializers.ModelSerializer):
    #: Isolation des relations écrites (voir apps.core.tenancy.TenantRelationsMixin).
    tenant_relations = {"student": "school", "subject": "school", "teacher": "user.school", "school_year": "school"}
    #: Chemin ORM vers l'académie propriétaire de l'objet.
    academy_source = "student.school"

    student_name    = serializers.SerializerMethodField()
    # Faux pour une note lisible mais hors des matières de l'enseignant : l'écran
    # n'y propose ni modification ni suppression.
    peut_modifier   = serializers.SerializerMethodField()
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
            'peut_modifier',
            'id', 'student', 'student_name', 'subject', 'subject_name',
            'subject_coefficient', 'teacher', 'teacher_name',
            'school_year', 'school_year_name',
            'period', 'value', 'note_type', 'note_type_display', 'note_type_label',
            'note_coefficient', 'comment', 'graded_at',
            'letter', 'meaning', 'appreciation',
            'is_deleted', 'deleted_at', 'deleted_by', 'deleted_by_name',
            'created_at', 'updated_at',
            'history',
        ] + ACADEMY_FIELDS + STUDENT_AGE_FIELDS

    def validate(self, attrs):
        """Programme linguistique de l'académie et parcours de la classe."""
        attrs = super().validate(attrs)
        if self.instance is not None and not ({"student", "subject"} & set(attrs)):
            return attrs
        from apps.classes.subject_rules import grade_subject_error

        student = attrs.get("student") or getattr(self.instance, "student", None)
        subject = attrs.get("subject") or getattr(self.instance, "subject", None)
        year = attrs.get("school_year") or getattr(self.instance, "school_year", None)
        if student is not None:
            refus = grade_subject_error(student, subject, year)
            if refus:
                raise serializers.ValidationError({"subject": refus})
        return attrs

    def get_note_type_label(self, obj):
        return obj.get_note_type_display()

    def get_subject_coefficient(self, obj):
        return obj.subject.coefficient if obj.subject else 1

    def get_appreciation(self, obj):
        """
        Appréciation de la note selon le barème de l'académie de l'élève (et
        du cycle de sa classe). Les barèmes résolus sont mémorisés pour la
        durée de la réponse : une liste de notes ne relit pas la table à
        chaque ligne.
        """
        from .appreciations import cycle_of_class
        from .models import get_appreciation

        memo = self.context.setdefault('_appreciation_memo', {'scales': {}, 'cycles': {}})
        enrollment = getattr(obj, 'enrollment', None)
        klass = getattr(enrollment, 'class_obj', None) if enrollment else None
        klass = klass or getattr(obj.student, 'current_class', None)
        key = getattr(klass, 'pk', None)
        if key not in memo['cycles']:
            memo['cycles'][key] = cycle_of_class(klass)
        return get_appreciation(obj.value, academy=obj.student.school,
                                cycle=memo['cycles'][key], cache=memo['scales'])

    def get_deleted_by_name(self, obj):
        if obj.deleted_by:
            return obj.deleted_by.get_full_name()
        return None

    def get_peut_modifier(self, obj):
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if user is None or not getattr(user, "is_authenticated", False):
            return False
        if user.role_level >= 80:
            return True
        if not user.is_teacher():
            return False
        droits = self.context.get("_droits_enseignant")
        if droits is None:
            teacher = getattr(user, "teacher_profile", None)
            droits = (set(teacher.subjects.values_list("id", flat=True)),
                      set(teacher.classes.values_list("id", flat=True))) if teacher else (set(), set())
            self.context["_droits_enseignant"] = droits
        return obj.subject_id in droits[0] and obj.student.current_class_id in droits[1]

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
