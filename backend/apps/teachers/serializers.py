"""
TeacherSerializer — v2 (BUG FIX)

ROOT CAUSE of 500 error on teacher creation:
  1. Frontend sends `user_write` (user PK) but serializer had no writable user field.
  2. Frontend sends `class_ids` / `subject_ids` but serializer used `classes` / `subjects`
     as BOTH the writable M2M field AND source for the read-only detail fields — causing
     a DRF source conflict and breaking create().
  3. DRF's default create() cannot handle ManyToMany fields; requires explicit set().

FIXES:
  - `user_write`: new writable PrimaryKeyRelatedField mapped to user on create.
  - `subject_ids` / `class_ids`: properly named writable M2M inputs (no source conflict).
  - `subjects_detail` / `classes_detail`: read-only nested serializers kept with explicit source.
  - Custom create() / update() that call .set() for M2M after instance is persisted.
"""
from rest_framework import serializers
from apps.subjects.serializers import SubjectSerializer
from apps.classes.serializers import ClassSerializer
from apps.accounts.models import CustomUser
from apps.subjects.models import Subject
from apps.classes.models import Class
from .models import Teacher
from apps.core.academy_serializers import ACADEMY_FIELDS, AcademyMetadataMixin


class TeacherSerializer(AcademyMetadataMixin, serializers.ModelSerializer):
    #: Chemin ORM vers l'académie propriétaire de l'objet.
    academy_source = "user.school"

    # Read-only display fields
    user_id         = serializers.IntegerField(source="user.id",         read_only=True)
    user_first_name = serializers.CharField(source="user.first_name",    read_only=True)
    user_last_name  = serializers.CharField(source="user.last_name",     read_only=True)
    user_email      = serializers.CharField(source="user.email",         read_only=True)
    user_phone      = serializers.CharField(source="user.phone",         read_only=True)
    user_is_active  = serializers.BooleanField(source="user.is_active",  read_only=True)
    user_photo      = serializers.SerializerMethodField()
    full_name       = serializers.SerializerMethodField()

    # Nested detail lists (read-only — no source conflict with writable fields)
    subjects_detail = SubjectSerializer(source="subjects", many=True, read_only=True)
    classes_detail  = ClassSerializer(source="classes",   many=True, read_only=True)

    # Writable inputs
    # FIX: user_write — accept user PK on creation (matches frontend field name)
    user_write = serializers.PrimaryKeyRelatedField(
        queryset=CustomUser.objects.filter(role="teacher"),
        write_only=True,
        required=False,
        allow_null=True,
        source="user",
    )
    # FIX: subject_ids / class_ids — distinct names from the read fields above
    subject_ids = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=Subject.objects.all(),
        write_only=True,
        required=False,
        source="subjects",
    )
    class_ids = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=Class.objects.all(),
        write_only=True,
        required=False,
        source="classes",
    )

    class Meta:
        model = Teacher
        fields = [
            "id",
            "user_write",
            "user_id",
            "user_first_name", "user_last_name", "user_email",
            "user_phone", "user_photo", "user_is_active",
            "full_name",
            "employee_id", "specialization", "hire_date",
            "contract_type", "bio", "created_at",
            "subject_ids",
            "subjects_detail",
            "class_ids",
            "classes_detail",
        ] + ACADEMY_FIELDS

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # FIX SÉCURITÉ (v29) : sans ce filtrage, un admin pouvait — en
        # connaissant ou devinant un ID — créer un enseignant à partir
        # d'un compte utilisateur d'un AUTRE établissement, ou lui
        # assigner des matières/classes d'un autre établissement.
        from apps.core.tenancy import get_request_school
        request = self.context.get("request")
        school = get_request_school(request) if request else None
        if school is not None:
            self.fields["user_write"].queryset = CustomUser.objects.filter(role="teacher", school=school)
            # V8 — FAILLE CORRIGÉE : pour un PrimaryKeyRelatedField(many=True),
            # DRF enveloppe le champ dans un ManyRelatedField. Affecter
            # `.queryset` sur l'ENVELOPPE n'a aucun effet : la validation
            # utilise `child_relation.queryset`. Le filtrage par établissement
            # était donc silencieusement inopérant et un administrateur pouvait
            # rattacher des matières/classes d'un AUTRE établissement.
            self.fields["subject_ids"].child_relation.queryset = Subject.objects.filter(
                school=school
            )
            self.fields["class_ids"].child_relation.queryset = Class.objects.filter(
                school_year__school=school
            )

    def get_full_name(self, obj):
        return obj.user.get_full_name()

    def get_user_photo(self, obj):
        # FIX v42 : chemin relatif, indépendant de la présence du request
        try:
            if hasattr(obj.user, "avatar") and obj.user.avatar:
                return obj.user.avatar.url
        except Exception:
            pass
        return None

    def validate_user_write(self, value):
        """On creation, ensure no Teacher profile already exists for this user."""
        if not self.instance:
            if Teacher.objects.filter(user=value).exists():
                raise serializers.ValidationError(
                    f"Un profil enseignant existe deja pour l'utilisateur {value.email}."
                )
        return value

    def validate(self, attrs):
        """V8 : le compte utilisateur est OBLIGATOIRE à la création.

        Sans lui, `Teacher.objects.create()` violait la contrainte NOT NULL sur
        `user_id` → IntegrityError → 500. On renvoie désormais un 400 explicite.
        """
        if not self.instance and not attrs.get("user"):
            raise serializers.ValidationError(
                {"user_write": "Sélectionnez le compte utilisateur (rôle enseignant)."}
            )
        return attrs

    def create(self, validated_data):
        # V8 — création ATOMIQUE : le profil ET ses relations (matières,
        # classes) sont enregistrés ensemble, ou rien du tout. Aucune donnée
        # partielle (profil sans matières, relations orphelines) ne subsiste.
        from django.db import IntegrityError, transaction

        subjects = validated_data.pop("subjects", [])
        classes  = validated_data.pop("classes",  [])

        try:
            with transaction.atomic():
                teacher = Teacher.objects.create(**validated_data)
                # Les M2M ne peuvent être posées qu'une fois l'instance en base.
                if subjects:
                    teacher.subjects.set(subjects)
                if classes:
                    teacher.classes.set(classes)
                return teacher
        except IntegrityError as exc:
            # Traduction en erreur métier exploitable (jamais de 500 ni de
            # traceback exposé à l'utilisateur).
            message = str(exc).lower()
            if "user_id" in message:
                raise serializers.ValidationError(
                    {"user_write": "Ce compte possède déjà un profil enseignant."}
                )
            raise serializers.ValidationError(
                {"detail": "Impossible d'enregistrer ce profil enseignant : "
                           "conflit de données. Réessayez."}
            )

    def update(self, instance, validated_data):
        # FIX: Pop M2M data before updating
        subjects = validated_data.pop("subjects", None)
        classes  = validated_data.pop("classes",  None)

        # user_write must NOT change after creation
        validated_data.pop("user", None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if subjects is not None:
            instance.subjects.set(subjects)
        if classes is not None:
            instance.classes.set(classes)

        return instance
