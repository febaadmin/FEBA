from decimal import Decimal
from rest_framework import serializers
from .models import Grade, GradeHistory, get_letter_grade, get_appreciation


class GradeHistorySerializer(serializers.ModelSerializer):
    changed_by_name = serializers.SerializerMethodField()

    class Meta:
        model = GradeHistory
        fields = ['id', 'grade', 'changed_by', 'changed_by_name', 'old_value',
                  'new_value', 'old_comment', 'new_comment', 'justification',
                  'action', 'changed_at']

    def get_changed_by_name(self, obj):
        return obj.changed_by.get_full_name() if obj.changed_by else None


class GradeSerializer(serializers.ModelSerializer):
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
        ]

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
