"""
apps/students/serializers.py — v29.2

Corrections :
  - StudentEnrollmentSerializer : `student` rendu read_only (fourni via
    serializer.save(student=...) dans la vue, pas dans le payload).
    Sans ça, le frontend obtenait une erreur "student: Champ requis."
    invisible lors de l'inscription individuelle.
  - StudentSerializer : ajout de 'enrolled_at_class' pour afficher la date
    d'inscription dans la classe courante.
"""
import logging
from rest_framework import serializers
from .models import Student, StudentEnrollment
from apps.core.academy_serializers import ACADEMY_FIELDS, AcademyMetadataMixin

logger = logging.getLogger("apps.students")


class StudentEnrollmentSerializer(serializers.ModelSerializer):
    class_name       = serializers.SerializerMethodField()
    school_year_name = serializers.SerializerMethodField()
    student_name     = serializers.SerializerMethodField()
    # FIX v31 : "Actuel" doit refléter l'ANNÉE SCOLAIRE ACTIVE, pas le flag
    # is_active de l'inscription (toutes les inscriptions valides sont actives,
    # ce qui affichait "Actuel" sur chaque ligne de l'historique).
    is_current_year        = serializers.SerializerMethodField()
    promotion_status_label = serializers.CharField(source='get_promotion_status_display', read_only=True)

    class Meta:
        model  = StudentEnrollment
        fields = [
            'id', 'student', 'student_name',
            'school_year', 'school_year_name',
            'class_obj', 'class_name',
            'enrolled_at', 'is_active', 'is_current_year',
            'note', 'promotion_status', 'promotion_status_label',
        ]
        # 'student' est read_only : on le passe via serializer.save(student=...)
        # dans la vue, jamais dans le payload du frontend. Sans ce read_only,
        # DRF le considère comme requis et renvoie "student: Champ requis."
        # même quand il est fourni via save().
        read_only_fields = ['student', 'enrolled_at']

    def get_class_name(self, obj):
        return obj.class_obj.name if obj.class_obj else None

    def get_school_year_name(self, obj):
        return obj.school_year.name if obj.school_year else None

    def get_student_name(self, obj):
        return obj.student.get_full_name() if obj.student_id else None

    def get_is_current_year(self, obj):
        return bool(obj.school_year and obj.school_year.is_current)

    def validate_school_year(self, value):
        if not value:
            raise serializers.ValidationError("L'année scolaire est obligatoire.")
        return value

    def validate(self, attrs):
        # Vérifier que le duo (student, school_year) n'existe pas déjà —
        # SAUF si on est en UPDATE (pk présent dans la vue).
        # La contrainte unique_together est gérée à la DB mais on préfère
        # un message explicite plutôt qu'une IntegrityError.
        request = self.context.get('request')
        view    = self.context.get('view')
        student = attrs.get('student') or getattr(getattr(view, '_enrollment_student', None), 'student', None)
        year    = attrs.get('school_year')

        if student and year and not self.instance:
            if StudentEnrollment.objects.filter(student=student, school_year=year).exists():
                raise serializers.ValidationError({
                    'school_year': f"Cet élève est déjà inscrit pour l'année {year.name}. "
                                   "Utilisez la modification pour changer sa classe."
                })
        return attrs


class StudentSerializer(AcademyMetadataMixin, serializers.ModelSerializer):
    # P3 : chaque objet expose son académie, sans quoi la vue
    # « Toutes les Académies » ne peut pas étiqueter ses lignes.
    academy_source = "school"
    full_name        = serializers.SerializerMethodField()
    class_name       = serializers.SerializerMethodField()
    class_level      = serializers.SerializerMethodField()
    school_year_name = serializers.SerializerMethodField()
    photo_url        = serializers.SerializerMethodField()
    enrollments      = StudentEnrollmentSerializer(many=True, read_only=True)
    parent_user_id   = serializers.IntegerField(
        write_only=True, required=False, allow_null=True,
        help_text="ID du compte utilisateur parent à lier lors de la création.",
    )

    class Meta:
        model  = Student
        fields = [
            'id', 'user', 'school', 'matricule', 'first_name', 'last_name', 'full_name',
            'date_of_birth', 'gender', 'photo', 'photo_url', 'address',
            'current_class', 'class_name', 'class_level',
            'school_year', 'school_year_name',
            'is_active', 'exit_reason', 'exit_date', 'exit_notes',
            'enrollment_date', 'created_at', 'enrollments', 'parent_user_id',
        ] + ACADEMY_FIELDS
        read_only_fields = ['matricule', 'school']
        extra_kwargs = {
            'first_name': {'error_messages': {'required': 'Le prénom est obligatoire.'}},
            'last_name':  {'error_messages': {'required': 'Le nom est obligatoire.'}},
            # Le UniqueValidator auto-généré (OneToOne user) renvoyait le
            # message générique « Un objet Élève avec ce champ user existe
            # déjà » AVANT validate_user() ; on le retire pour laisser le
            # message métier clair (compte déjà associé → réinscription).
            'user': {'validators': []},
        }

    def get_full_name(self, obj):
        return obj.get_full_name()

    def validate_user(self, value):
        """
        FIX v37 (vidéo 1) : un compte utilisateur ne peut porter qu'UN profil
        élève (identité unique et permanente). Avant : IntegrityError 500
        brute. Désormais : message clair orientant vers la réinscription.
        """
        if value is None:
            return value
        from apps.students.models import Student
        existing = Student.objects.filter(user=value)
        if self.instance is not None:
            existing = existing.exclude(pk=self.instance.pk)
        linked = existing.select_related('school_year').first()
        if linked is not None:
            year = linked.school_year.name if linked.school_year else "?"
            raise serializers.ValidationError(
                f"Ce compte est déjà associé à l'élève {linked.get_full_name()} "
                f"({linked.matricule or 'sans matricule'}, année {year}). "
                "Pour l'inscrire dans une autre année, utilisez "
                "Inscriptions → Inscription individuelle — ne créez pas de doublon."
            )
        return value

    def _requested_year_id(self):
        """Année scolaire demandée par le client (?school_year=), sinon None."""
        request = self.context.get('request')
        if request is None:
            return None
        year = request.query_params.get('school_year')
        try:
            return int(year) if year else None
        except (TypeError, ValueError):
            return None

    def _enrollment_for_requested_year(self, obj):
        year_id = self._requested_year_id()
        if year_id is None:
            return None
        # enrollments est préfetché par la vue : itération en mémoire, pas de N+1
        for enr in obj.enrollments.all():
            if enr.school_year_id == year_id:
                return enr
        return None

    def get_class_name(self, obj):
        # FIX v31 : en consultation historique (?school_year=), afficher la
        # classe de l'inscription de CETTE année-là, pas la classe actuelle.
        enr = self._enrollment_for_requested_year(obj)
        if enr is not None:
            return enr.class_obj.name if enr.class_obj else None
        return obj.current_class.name if obj.current_class else None

    def get_class_level(self, obj):
        enr = self._enrollment_for_requested_year(obj)
        if enr is not None:
            if enr.class_obj and enr.class_obj.level:
                return enr.class_obj.level.name
            return None
        if obj.current_class and obj.current_class.level:
            return obj.current_class.level.name
        return None

    def get_school_year_name(self, obj):
        enr = self._enrollment_for_requested_year(obj)
        if enr is not None and enr.school_year:
            return enr.school_year.name
        return obj.school_year.name if obj.school_year else None

    def get_photo_url(self, obj):
        request = self.context.get('request')
        if obj.photo and request:
            return obj.photo.url
        return None

    def _link_parent(self, student, parent_user_id):
        from apps.accounts.models import CustomUser
        from apps.parents.models import Parent, ParentStudent

        try:
            parent_user = CustomUser.objects.get(pk=parent_user_id, role='parent')
        except CustomUser.DoesNotExist:
            raise serializers.ValidationError({
                'parent_user_id':
                    "Utilisateur introuvable ou ce compte n'a pas le rôle 'parent'."
            })
        if (student.school_id and parent_user.school_id and
                student.school_id != parent_user.school_id):
            raise serializers.ValidationError({
                'parent_user_id':
                    "Ce parent n'appartient pas au même établissement que l'élève."
            })
        parent, _ = Parent.objects.get_or_create(user=parent_user)
        ParentStudent.objects.get_or_create(
            parent=parent, student=student,
            defaults={'is_primary_contact': not student.parents.exists()},
        )
        logger.info("Lien parent-élève créé : %s ↔ %s", parent, student)

    def create(self, validated_data):
        parent_user_id = validated_data.pop('parent_user_id', None)
        student = super().create(validated_data)
        if parent_user_id:
            self._link_parent(student, parent_user_id)
        return student

    def update(self, instance, validated_data):
        parent_user_id = validated_data.pop('parent_user_id', None)
        student = super().update(instance, validated_data)
        if parent_user_id:
            self._link_parent(student, parent_user_id)
        return student
