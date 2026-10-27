from rest_framework import serializers
from .models import School, SchoolYear, Level, Room, RoomType, SchoolBranding
from apps.core.academy_serializers import ACADEMY_FIELDS, AcademyMetadataMixin
from apps.core.tenancy import TenantRelationsMixin, get_request_school

#: Isolation des relations écrites (audit du 26/10/2026) : un PATCH
#: {"school": <autre académie>} déplaçait un niveau ou une salle physique
#: dans une autre académie. Le champ reste accepté s'il désigne l'académie
#: de la requête (super administrateur en vue « toutes les académies » :
#: choix libre, mais cohérent entre relations).
_SCHOOL_ONLY = {"school": ""}


class SchoolBrandingSerializer(TenantRelationsMixin, serializers.ModelSerializer):
    tenant_relations = _SCHOOL_ONLY

    logo_url = serializers.SerializerMethodField()
    uploaded_by_name = serializers.SerializerMethodField()

    class Meta:
        model = SchoolBranding
        fields = ['id', 'school', 'logo', 'logo_url', 'is_active', 'label',
                  'uploaded_at', 'updated_at', 'uploaded_by', 'uploaded_by_name']
        # `is_active` : l'activation passe par /activate/ (atomique). Un PATCH
        # direct pouvait laisser deux versions actives.
        read_only_fields = ['uploaded_at', 'updated_at', 'uploaded_by', 'is_active']
        extra_kwargs = {'school': {'required': False}}

    #: Formats acceptés, contrôlés sur le CONTENU décodé (pas l'extension).
    LOGO_FORMATS = {'PNG', 'JPEG', 'WEBP'}
    LOGO_MAX_BYTES = 5 * 1024 * 1024
    LOGO_MIN_SIDE, LOGO_MAX_SIDE = 64, 6000

    def validate_logo(self, value):
        if value is None:
            raise serializers.ValidationError("Fichier requis.")
        if value.size > self.LOGO_MAX_BYTES:
            raise serializers.ValidationError("Fichier trop volumineux (5 Mo au maximum).")
        from PIL import Image, UnidentifiedImageError
        try:
            value.seek(0)
            with Image.open(value) as img:
                fmt = img.format
                width, height = img.size
                img.verify()               # structure du fichier
            value.seek(0)
            with Image.open(value) as img:
                img.load()                 # décodage complet des pixels
        except (UnidentifiedImageError, OSError, SyntaxError, ValueError):
            raise serializers.ValidationError(
                "Ce fichier n'est pas une image lisible (PNG, JPEG ou WebP).")
        finally:
            value.seek(0)
        if fmt not in self.LOGO_FORMATS:
            raise serializers.ValidationError(f"Format {fmt} refusé : PNG, JPEG ou WebP uniquement.")
        if min(width, height) < self.LOGO_MIN_SIDE or max(width, height) > self.LOGO_MAX_SIDE:
            raise serializers.ValidationError(
                f"Dimensions {width}×{height} : entre {self.LOGO_MIN_SIDE} et {self.LOGO_MAX_SIDE} pixels.")
        return value

    def validate(self, attrs):
        attrs = super().validate(attrs)
        if self.instance is None and not attrs.get('logo'):
            raise serializers.ValidationError({'logo': "Fichier requis."})
        return attrs

    def get_logo_url(self, obj):
        request = self.context.get('request')
        if obj.logo and request:
            return obj.logo.url
        return None

    def get_uploaded_by_name(self, obj):
        if obj.uploaded_by:
            return obj.uploaded_by.get_full_name()
        return None


class LevelSerializer(TenantRelationsMixin, AcademyMetadataMixin, serializers.ModelSerializer):
    tenant_relations = _SCHOOL_ONLY

    # P3 : chaque objet expose son académie, sans quoi la vue
    # « Toutes les Académies » ne peut pas étiqueter ses lignes.
    academy_source = "school"
    school_name = serializers.CharField(source='school.name', read_only=True, default='—')

    class Meta:
        model = Level
        fields = ['id', 'school', 'school_name', 'name', 'order', 'cycle'] + ACADEMY_FIELDS
        # L'académie vient de la REQUÊTE (perform_create) : la demander au
        # formulaire poussait l'écran à proposer « la première école de la
        # liste » — pour un super administrateur, souvent pas la bonne.
        extra_kwargs = {'school': {'required': False}}

    def _target_school(self, attrs):
        if self.instance is not None:
            return self.instance.school
        request = self.context.get('request')
        school = get_request_school(request) if request is not None else None
        return school or attrs.get('school')

    def validate(self, attrs):
        """
        Le cycle décide du barème (/10 ou /20, voir apps.grades.grading) : il
        doit être compatible avec le TYPE de l'académie. Sans cette règle, un
        niveau créé sans préciser le cycle dans un lycée prenait le défaut du
        modèle, « primaire », et ses bulletins sortaient notés sur 10.
        """
        attrs = super().validate(attrs)
        school = self._target_school(attrs)
        if school is None:
            raise serializers.ValidationError({'school': (
                "Sélectionnez d'abord l'académie à laquelle ce niveau appartient.")})
        if 'cycle' not in attrs and self.instance is None:
            attrs['cycle'] = school.default_level_cycle()
        cycle = attrs.get('cycle', getattr(self.instance, 'cycle', None))
        allowed = school.allowed_cycles()
        if cycle not in allowed:
            labels = dict(Level.CYCLE_CHOICES)
            raise serializers.ValidationError({'cycle': (
                f"Le cycle « {labels.get(cycle, cycle)} » n'est pas admis dans "
                f"« {school.name} » ({school.get_academy_type_display()}). "
                f"Cycles admis : {', '.join(labels[c] for c in allowed)}."
            )})
        return attrs


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
    curriculum_language_mode_display = serializers.CharField(
        source='get_curriculum_language_mode_display', read_only=True, default=None)

    class Meta:
        model = School
        # P11 — Ces champs existaient en base et n'étaient exposés par AUCUN
        # serializer : un administrateur ne pouvait ni voir ni corriger la
        # dénomination légale, le numéro WhatsApp, la devise, le fuseau ou
        # le préfixe des matricules de son académie. Ce sont pourtant ceux
        # qui déterminent l'en-tête de chaque reçu, de chaque bulletin et de
        # chaque diplôme qu'elle émet.
        fields = ['id', 'name', 'legal_name', 'short_name', 'slug', 'code',
                  'entity_type', 'academy_type', 'curriculum_language_mode',
                  'curriculum_language_mode_display', 'address', 'city', 'country', 'phone',
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
        # `entity_type` aussi : il fixe la matrice des fonctionnalités
        # (cours en ligne, tests de placement, classes monolingues…). Un
        # administrateur d'académie le passait de « campus » à « online »
        # par un simple PATCH et s'ouvrait toutes ces fonctions. Seul le
        # super administrateur (SchoolPlatformSerializer) le modifie.
        # `curriculum_language_mode` aussi : il décide des matières, des
        # parcours et des bulletins de toute l'académie (super admin seul).
        read_only_fields = ['slug', 'code', 'entity_type', 'academy_type',
                            'curriculum_language_mode', 'is_active', 'plan',
                            'max_students', 'trial_ends_at', 'created_at', 'updated_at']

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

    academy_type_display = serializers.CharField(source='get_academy_type_display', read_only=True)
    classification = serializers.SerializerMethodField()

    class Meta(SchoolSerializer.Meta):
        fields = SchoolSerializer.Meta.fields + [
            'subscription_notes', 'students_count', 'users_count',
            'academy_type_display', 'classification',
        ]
        # `code` : identifiant interne STABLE (isolation, identité visuelle,
        # devise). Fixé à la création ; le modifier ensuite ferait basculer
        # une académie dans l'identité d'une autre — y compris pour le
        # super administrateur.
        read_only_fields = ['slug', 'code', 'created_at']

    def get_classification(self, obj):
        """Pour une académie non classée : proposition déduite de ses niveaux, et motif."""
        if obj.academy_type:
            return None
        from apps.schools.academy_types import classify

        suggested, reason = classify(obj.entity_type, set(obj.levels.values_list('cycle', flat=True)))
        return {'suggested_type': suggested, 'reason': reason}

    def validate(self, attrs):
        attrs = super().validate(attrs)
        instance = self.instance
        academy_type = attrs.get('academy_type', getattr(instance, 'academy_type', None))
        if instance is not None and instance.academy_type and 'academy_type' in attrs \
                and attrs['academy_type'] is None:
            raise serializers.ValidationError({'academy_type': (
                "Une académie classée ne peut pas redevenir « non classée ».")})
        if instance is not None and 'academy_type' in attrs and attrs['academy_type']:
            conflicts = instance.incompatible_levels(attrs['academy_type'])
            if conflicts:
                labels = dict(Level.CYCLE_CHOICES)
                raise serializers.ValidationError({'academy_type': (
                    f"Type refusé : {len(conflicts)} niveau(x) portent un cycle qu'il n'admet pas ("
                    + ", ".join(f"{lvl.name} — {labels.get(lvl.cycle, lvl.cycle)}" for lvl in conflicts[:6])
                    + "). Corrigez ou déplacez ces niveaux d'abord : sinon leurs bulletins "
                      "seraient notés sur le mauvais barème.")})
        if instance is not None and 'curriculum_language_mode' in attrs:
            self._check_curriculum_change(instance, attrs['curriculum_language_mode'])
        derived = School.entity_type_for(academy_type)
        if derived and 'entity_type' in attrs and attrs['entity_type'] != derived:
            raise serializers.ValidationError({'entity_type': (
                f"Incohérent avec le type d'académie : une académie "
                f"« {dict(School.ACADEMY_TYPE_CHOICES)[academy_type]} » est "
                f"{'en ligne' if derived == 'online' else 'présentielle'}.")})
        return attrs

    def update(self, instance, validated_data):
        previous = instance.curriculum_language_mode
        instance = super().update(instance, validated_data)
        if instance.curriculum_language_mode != previous:
            from apps.classes.subject_rules import align_class_tracks

            align_class_tracks(instance)
        return instance

    def _check_curriculum_change(self, instance, mode):
        """
        Changer le programme linguistique ne SUPPRIME ni ne convertit rien.
        Si des matières, classes ou notes existantes ne le respecteraient
        plus, le changement est refusé avec le diagnostic détaillé, sauf
        confirmation explicite (`confirm_curriculum_change`) : les données
        restent alors en place, consultables, et ne peuvent plus recevoir
        de nouvelles notes ni de nouveaux créneaux tant qu'elles ne sont
        pas corrigées.
        """
        if mode is None:
            if instance.curriculum_language_mode:
                raise serializers.ValidationError({'curriculum_language_mode': (
                    "Le programme linguistique est obligatoire : il ne peut pas redevenir vide.")})
            return
        if mode == instance.curriculum_language_mode:
            return
        from apps.classes.subject_rules import curriculum_diagnostic

        diagnostic = curriculum_diagnostic(instance, mode)
        request = self.context.get('request')
        confirmed = str((request.data if request is not None else {}).get(
            'confirm_curriculum_change', '')).lower() in ('1', 'true', 'yes')
        if not diagnostic['ok'] and not confirmed:
            raise serializers.ValidationError({
                'curriculum_language_mode': [(
                    f"{len(diagnostic['subjects'])} matière(s) et {len(diagnostic['classes'])} "
                    f"classe(s) ne respecteraient pas ce programme ({diagnostic['grades']} note(s) "
                    f"rattachée(s)). Rien n'a été modifié. Corrigez-les, ou confirmez : aucune "
                    f"donnée n'est supprimée.")],
                # Sans `ok` (toujours faux ici) : DRF convertit le détail
                # d'erreur en chaînes, et « False » deviendrait vrai côté
                # navigateur. Le diagnostic complet est servi par
                # GET …/language-diagnostic/.
                'diagnostic': {k: v for k, v in diagnostic.items() if k != 'ok'},
            })

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


class RoomTypeSerializer(TenantRelationsMixin, serializers.ModelSerializer):
    tenant_relations = _SCHOOL_ONLY

    class Meta:
        model = RoomType
        fields = ['id', 'school', 'name', 'created_at']


class RoomSerializer(TenantRelationsMixin, AcademyMetadataMixin, serializers.ModelSerializer):
    tenant_relations = {"school": "", "room_type_obj": "school"}

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


class AcademyCreateSerializer(serializers.ModelSerializer):
    """
    Création d'une académie par le super administrateur (écran « Académies »).

    Le TYPE est obligatoire : c'est lui qui fixe les niveaux initiaux, leurs
    cycles (donc les barèmes /10 ou /20) et la matrice des fonctionnalités.
    L'initialisation elle-même est faite par `academy_setup.create_academy`.
    """
    CODE_PATTERN = r'^[A-Z0-9][A-Z0-9_-]{1,31}$'

    academy_type = serializers.ChoiceField(
        choices=School.ACADEMY_TYPE_CHOICES,
        error_messages={'required': "Le type d'académie est obligatoire.",
                        'invalid_choice': "Type d'académie inconnu."})
    curriculum_language_mode = serializers.ChoiceField(
        choices=School.CURRICULUM_CHOICES,
        error_messages={'required': "Le programme linguistique est obligatoire "
                                    "(français uniquement, anglais uniquement ou bilingue).",
                        'invalid_choice': "Programme linguistique inconnu.",
                        'null': "Le programme linguistique est obligatoire."})
    school_year_name = serializers.CharField(required=False, allow_blank=True, max_length=20)
    school_year_start = serializers.DateField(required=False, allow_null=True)
    school_year_end = serializers.DateField(required=False, allow_null=True)

    class Meta:
        model = School
        fields = ['name', 'legal_name', 'code', 'academy_type', 'curriculum_language_mode',
                  'address', 'city', 'country',
                  'phone', 'whatsapp', 'email', 'description', 'timezone', 'currency_code',
                  'currency_locale', 'default_language', 'matricule_prefix',
                  'school_year_name', 'school_year_start', 'school_year_end']
        extra_kwargs = {
            'name': {'error_messages': {'required': "Le nom de l'académie est obligatoire.",
                                        'blank': "Le nom de l'académie est obligatoire."}},
            'code': {'required': True, 'allow_blank': False, 'allow_null': False,
                     'validators': [],
                     'error_messages': {'required': "Le code interne est obligatoire.",
                                        'blank': "Le code interne est obligatoire."}},
            'address': {'error_messages': {'required': "L'adresse est obligatoire.",
                                           'blank': "L'adresse est obligatoire."}},
            # Ville et pays s'impriment en tête de chaque document : sans
            # eux, le défaut du modèle (« Cotonou », « Bénin ») apparaissait
            # sur les bulletins d'une académie installée ailleurs.
            'city': {'required': True, 'allow_blank': False, 'error_messages': {
                'required': "La ville est obligatoire.", 'blank': "La ville est obligatoire."}},
            'country': {'required': True, 'allow_blank': False, 'error_messages': {
                'required': "Le pays est obligatoire.", 'blank': "Le pays est obligatoire."}},
        }

    def validate_code(self, value):
        import re

        code = (value or '').strip().upper()
        if not re.match(self.CODE_PATTERN, code):
            raise serializers.ValidationError(
                "Code invalide : 2 à 32 caractères, lettres majuscules, chiffres, « _ » ou « - » "
                "(ex. ECOLE_PARAKOU).")
        if School.objects.filter(code__iexact=code).exists():
            raise serializers.ValidationError(f"Le code « {code} » est déjà utilisé par une autre académie.")
        return code

    def validate_name(self, value):
        name = (value or '').strip()
        if School.objects.filter(name__iexact=name).exists():
            raise serializers.ValidationError("Une académie porte déjà ce nom.")
        return name

    def validate_timezone(self, value):
        from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError):
            raise serializers.ValidationError(f"Fuseau horaire inconnu : {value!r} (ex. Africa/Porto-Novo).")
        return value

    def validate(self, attrs):
        name = attrs.get('school_year_name') or ''
        start, end = attrs.get('school_year_start'), attrs.get('school_year_end')
        if any([name, start, end]):
            missing = [label for key, label in (('school_year_name', 'nom'), ('school_year_start', 'début'),
                                                ('school_year_end', 'fin')) if not attrs.get(key)]
            if missing:
                raise serializers.ValidationError({'school_year': (
                    "Première année scolaire : renseigner le nom, la date de début et la date de fin "
                    f"(manquant : {', '.join(missing)}), ou aucun des trois.")})
            if end <= start:
                raise serializers.ValidationError({'school_year_end': (
                    "La date de fin doit être postérieure à la date de début.")})
        return attrs
