from rest_framework import serializers
from .models import School, SchoolYear, Level, Room, RoomType, SchoolBranding
from apps.core.academy_serializers import ACADEMY_FIELDS, AcademyMetadataMixin


class SchoolBrandingSerializer(serializers.ModelSerializer):
    logo_url = serializers.SerializerMethodField()
    uploaded_by_name = serializers.SerializerMethodField()

    class Meta:
        model = SchoolBranding
        fields = ['id', 'school', 'logo', 'logo_url', 'is_active', 'label',
                  'uploaded_at', 'updated_at', 'uploaded_by', 'uploaded_by_name']
        read_only_fields = ['uploaded_at', 'updated_at']

    def get_logo_url(self, obj):
        request = self.context.get('request')
        if obj.logo and request:
            return obj.logo.url
        return None

    def get_uploaded_by_name(self, obj):
        if obj.uploaded_by:
            return obj.uploaded_by.get_full_name()
        return None


class LevelSerializer(AcademyMetadataMixin, serializers.ModelSerializer):
    # P3 : chaque objet expose son académie, sans quoi la vue
    # « Toutes les Académies » ne peut pas étiqueter ses lignes.
    academy_source = "school"
    school_name = serializers.CharField(source='school.name', read_only=True, default='—')

    class Meta:
        model = Level
        fields = ['id', 'school', 'school_name', 'name', 'order', 'cycle'] + ACADEMY_FIELDS


class SchoolSerializer(serializers.ModelSerializer):
    """
    Vue "établissement" standard — utilisée par l'admin de l'école pour
    consulter/modifier son propre profil. Les champs commerciaux
    (plan, quota, statut, notes internes) sont en lecture seule ici :
    seul un superadmin (SchoolPlatformSerializer) peut les modifier.
    """
    logo_url = serializers.SerializerMethodField()
    active_logo_url = serializers.SerializerMethodField()
    # Dérivés de `currency_code` — jamais stockés, donc jamais
    # contradictoires avec lui (voir apps/core/currency.py).
    currency_symbol = serializers.CharField(read_only=True)
    currency_name = serializers.CharField(read_only=True)
    short_name = serializers.CharField(read_only=True)
    branding = serializers.SerializerMethodField()

    class Meta:
        model = School
        # P11 — Ces champs existaient en base et n'étaient exposés par AUCUN
        # serializer : un administrateur ne pouvait ni voir ni corriger la
        # dénomination légale, le numéro WhatsApp, la devise, le fuseau ou
        # le préfixe des matricules de son académie. Ce sont pourtant ceux
        # qui déterminent l'en-tête de chaque reçu, de chaque bulletin et de
        # chaque diplôme qu'elle émet.
        fields = ['id', 'name', 'legal_name', 'short_name', 'slug', 'code',
                  'entity_type', 'address', 'city', 'country', 'phone',
                  'whatsapp', 'email',
                  'logo', 'logo_url', 'active_logo_url', 'description',
                  'timezone', 'currency_code', 'currency_symbol',
                  'currency_name', 'currency_locale', 'default_language',
                  'matricule_prefix', 'branding', 'created_at', 'updated_at',
                  'is_active', 'plan', 'max_students', 'trial_ends_at']
        # `code` reste EN LECTURE SEULE : c'est l'identifiant interne stable
        # sur lequel s'appuient l'isolation, la devise et l'identité
        # visuelle. Le renommer depuis un écran ferait basculer une académie
        # dans l'identité d'une autre.
        read_only_fields = ['slug', 'code', 'is_active', 'plan', 'max_students',
                            'trial_ends_at', 'created_at', 'updated_at']

    def get_branding(self, obj):
        """Identité effective de l'académie, telle que les documents la voient."""
        from apps.schools.branding import get_branding

        return get_branding(obj).as_dict()

    def get_logo_url(self, obj):
        request = self.context.get('request')
        if obj.logo and request:
            return obj.logo.url
        return None

    def get_active_logo_url(self, obj):
        request = self.context.get('request')
        return obj.get_active_logo_url(request)


class SchoolPlatformSerializer(SchoolSerializer):
    """
    Vue "plateforme" — réservée au superadmin (rôle transverse de
    gestion commerciale des établissements clients). Permet de créer
    un nouveau tenant, suspendre un abonnement, ajuster le quota/plan,
    et consulter les notes internes (non visibles par l'établissement).
    """
    students_count = serializers.SerializerMethodField()
    users_count = serializers.SerializerMethodField()

    class Meta(SchoolSerializer.Meta):
        fields = SchoolSerializer.Meta.fields + ['subscription_notes', 'students_count', 'users_count']
        read_only_fields = ['slug', 'created_at']  # tout le reste devient modifiable

    def get_students_count(self, obj):
        return obj.students.filter(is_active=True).count()

    def get_users_count(self, obj):
        return obj.users.count()


class SchoolYearSerializer(AcademyMetadataMixin, serializers.ModelSerializer):
    # P3 : chaque objet expose son académie, sans quoi la vue
    # « Toutes les Académies » ne peut pas étiqueter ses lignes.
    academy_source = "school"
    school_name = serializers.CharField(source='school.name', read_only=True, default='—')

    class Meta:
        model = SchoolYear
        fields = ['id', 'school', 'school_name', 'name', 'start_date', 'end_date', 'is_current', 'created_at'] + ACADEMY_FIELDS
        # DRF génère automatiquement un UniqueTogetherValidator depuis la
        # contrainte (school, name) qui rend `school` OBLIGATOIRE dans le
        # payload — alors que le tenant est résolu côté vue (admin → son
        # établissement). L'unicité du nom est déjà contrôlée dans validate()
        # avec un message clair, et la contrainte base reste le garde-fou final.
        validators = []
        extra_kwargs = {
            'school': {'required': False, 'allow_null': True},
            'name': {'error_messages': {'required': "Le nom de l'année est obligatoire (ex: 2026-2027)."}},
            'start_date': {'error_messages': {'required': 'La date de début est obligatoire.', 'invalid': 'Date de début invalide.'}},
            'end_date': {'error_messages': {'required': 'La date de fin est obligatoire.', 'invalid': 'Date de fin invalide.'}},
        }

    def validate(self, attrs):
        # FIX v32 — validations métier explicites (avant : IntegrityError 500 brute)
        start = attrs.get('start_date') or getattr(self.instance, 'start_date', None)
        end = attrs.get('end_date') or getattr(self.instance, 'end_date', None)
        if start and end and end <= start:
            raise serializers.ValidationError(
                {'end_date': 'La date de fin doit être postérieure à la date de début.'}
            )

        name = attrs.get('name') or getattr(self.instance, 'name', None)
        school = attrs.get('school') or getattr(self.instance, 'school', None)
        if school is None:
            request = self.context.get('request')
            if request is not None:
                from apps.core.tenancy import get_request_school
                school = get_request_school(request)
        if name and school is not None:
            dup = SchoolYear.objects.filter(school=school, name=name)
            if self.instance:
                dup = dup.exclude(pk=self.instance.pk)
            if dup.exists():
                raise serializers.ValidationError(
                    {'name': f"L'année scolaire « {name} » existe déjà pour cet établissement."}
                )
        return attrs


class RoomTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = RoomType
        fields = ['id', 'school', 'name', 'created_at']


class RoomSerializer(AcademyMetadataMixin, serializers.ModelSerializer):
    # P3 : chaque objet expose son académie, sans quoi la vue
    # « Toutes les Académies » ne peut pas étiqueter ses lignes.
    academy_source = "school"
    display_type = serializers.SerializerMethodField()

    class Meta:
        model = Room
        fields = ['id', 'school', 'name', 'room_type', 'custom_type_label',
                  'room_type_obj', 'display_type', 'capacity', 'description', 'is_active', 'created_at'] + ACADEMY_FIELDS

    def get_display_type(self, obj):
        return obj.get_display_type()
