from rest_framework import serializers
from django.db import transaction, IntegrityError
from apps.accounts.models import CustomUser
from .models import Parent, ParentStudent


class NestedStudentSerializer(serializers.Serializer):
    """Minimal student info embedded inside ParentStudentSerializer."""
    id = serializers.IntegerField(read_only=True)
    first_name = serializers.CharField(read_only=True)
    last_name = serializers.CharField(read_only=True)
    matricule = serializers.CharField(read_only=True)
    gender = serializers.CharField(read_only=True)
    full_name = serializers.SerializerMethodField()
    class_id = serializers.SerializerMethodField()
    class_name = serializers.SerializerMethodField()
    school_year_name = serializers.SerializerMethodField()
    photo = serializers.SerializerMethodField()

    def get_full_name(self, obj):
        return obj.get_full_name()

    def get_class_id(self, obj):
        return obj.current_class_id if obj.current_class else None

    def get_class_name(self, obj):
        return str(obj.current_class) if obj.current_class else None

    def get_school_year_name(self, obj):
        return str(obj.school_year) if obj.school_year else None

    def get_photo(self, obj):
        request = self.context.get("request")
        if obj.photo and request:
            return obj.photo.url
        return None


class ParentStudentSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source="student.get_full_name", read_only=True)
    parent_name  = serializers.CharField(source="parent.user.get_full_name", read_only=True)
    class_name   = serializers.SerializerMethodField()
    # FIX: nested student details so the frontend Children.jsx can access link.student_detail
    student_detail = NestedStudentSerializer(source="student", read_only=True)

    class Meta:
        model = ParentStudent
        fields = "__all__"

    def get_class_name(self, obj):
        if obj.student and obj.student.current_class:
            return obj.student.current_class.name
        return None


class ParentSerializer(serializers.ModelSerializer):
    user_first_name = serializers.CharField(source="user.first_name", read_only=True)
    user_last_name  = serializers.CharField(source="user.last_name",  read_only=True)
    user_email      = serializers.CharField(source="user.email",      read_only=True)
    user_id         = serializers.IntegerField(source="user.id",      read_only=True)
    # BUG FIX #3 & #5: Expose phone for contact principal
    user_phone      = serializers.CharField(source="user.phone",      read_only=True)
    full_name       = serializers.SerializerMethodField()
    children_count  = serializers.SerializerMethodField()
    children_names  = serializers.SerializerMethodField()
    children_links  = serializers.SerializerMethodField()
    user_photo      = serializers.SerializerMethodField()

    user = serializers.PrimaryKeyRelatedField(
        queryset=CustomUser.objects.all(),
        write_only=True,
        required=False,
    )

    class Meta:
        model = Parent
        fields = [
            "id", "user", "user_id", "user_first_name", "user_last_name",
            "user_email", "user_phone", "user_photo", "full_name", "profession", "address",
            "created_at", "children_count", "children_names", "children_links",
        ]

    def get_full_name(self, obj):
        return obj.user.get_full_name()

    def get_user_photo(self, obj):
        request = self.context.get("request")
        if hasattr(obj.user, 'photo') and obj.user.photo and request:
            return obj.user.photo.url
        return None

    def get_children_count(self, obj):
        return obj.children_links.count()

    def get_children_names(self, obj):
        return [
            {
                "id": link.student.id,
                "first_name": link.student.first_name,
                "last_name": link.student.last_name,
                "full_name": link.student.get_full_name(),
            }
            for link in obj.children_links.select_related("student").all()
        ]

    def get_children_links(self, obj):
        links = obj.children_links.select_related(
            "student__current_class__level", "student__school_year"
        ).all()
        return ParentStudentSerializer(
            links, many=True, context=self.context
        ).data

    def validate_user(self, value):
        if value.role != "parent":
            raise serializers.ValidationError(
                f"L'utilisateur {value.email} n'a pas le rôle 'parent' "
                f"(rôle actuel: {value.role})."
            )
        if not self.instance:
            if Parent.objects.filter(user=value).exists():
                raise serializers.ValidationError(
                    f"Un profil parent existe déjà pour l'utilisateur {value.email}."
                )
        return value

    def create(self, validated_data):
        return Parent.objects.create(**validated_data)

    def update(self, instance, validated_data):
        validated_data.pop("user", None)
        return super().update(instance, validated_data)
