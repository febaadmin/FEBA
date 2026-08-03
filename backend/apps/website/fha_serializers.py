"""
apps/website/fha_serializers.py — Formulaires publics FEBA French Heritage Academy

RÈGLE CENTRALE : l'entité n'est JAMAIS lue depuis la requête. Elle est
résolue côté serveur à partir du code interne stable `FEBA_FHA`. Un
navigateur qui envoie `{"entity": 1}` ou `{"entity_id": 1}` voit ce champ
ignoré — il n'est pas déclaré dans les serializers.
"""
from datetime import date

from django.utils import timezone
from rest_framework import serializers

from .models import (
    ContactMessage, FHAApplicationStatusHistory, FHAEnrollmentApplication,
    FHAPlacementTestRequest,
)
from .serializers import HoneypotMixin


#: Champs où la mise en forme saisie par la famille doit être conservée
#: telle quelle : ce sont des textes libres, souvent multi-paragraphes.
FREEFORM_TEXT_FIELDS = (
    "special_needs",
    "availability_notes",
    "equipment_notes",
    "experience_comments",
    "french_level_notes",
    "parent_goals_other",
    "comment",
)


def get_fha_entity():
    """
    Entité FEBA French Heritage Academy, résolue par son CODE INTERNE
    STABLE. Ne jamais rechercher par nom affiché : l'administration peut
    renommer l'entité sans que la logique métier ne doive changer.
    """
    from apps.schools.models import School
    return School.objects.filter(code=School.CODE_FEBA_FHA).first()


def get_feba_entity():
    """
    Entité FEBA (école présentielle de Cotonou), destinataire des
    formulaires publics du site FEBA.

    Repli indispensable : sur une installation neuve — ou sur une base dont
    l'établissement historique n'a pas encore reçu le code « FEBA » — une
    recherche stricte par code renverrait None, et les soumissions
    publiques seraient enregistrées SANS entité, donc invisibles dans
    toutes les boîtes de réception. On retombe donc sur la première entité
    présentielle active, en excluant explicitement FEBA FHA pour ne jamais
    router un message FEBA vers l'académie en ligne.
    """
    from apps.schools.models import School

    entity = School.objects.filter(code=School.CODE_FEBA).first()
    if entity is not None:
        return entity
    return (
        School.objects
        .filter(is_active=True)
        .exclude(code=School.CODE_FEBA_FHA)
        .exclude(entity_type="online")
        .order_by("id")
        .first()
    )


# ── Contact FEBA FHA ──────────────────────────────────────────────────────────

class FHAContactMessageCreateSerializer(HoneypotMixin, serializers.ModelSerializer):
    """
    Formulaire de contact FEBA FHA — distinct de celui de FEBA.

    Champs supplémentaires adaptés à des familles internationales (pays,
    État/province, fuseau, langue préférée, WhatsApp) et catégories propres
    au programme en ligne.
    """

    class Meta:
        model = ContactMessage
        fields = [
            'name', 'email', 'phone', 'whatsapp', 'country', 'state_province',
            'timezone', 'preferred_language', 'subject', 'category', 'message',
            'consent', 'website',
        ]
        extra_kwargs = {
            'name': {'error_messages': {
                'required': 'Le nom complet est obligatoire.',
                'blank': 'Le nom complet est obligatoire.',
            }},
            'email': {'error_messages': {
                'required': "L'adresse e-mail est obligatoire.",
                'blank': "L'adresse e-mail est obligatoire.",
                'invalid': "Format d'adresse e-mail invalide.",
            }},
            'subject': {'error_messages': {
                'required': 'Le sujet est obligatoire.',
                'blank': 'Le sujet est obligatoire.',
            }},
            # Voir serializers.py : DRF retire les blancs de fin par
            # défaut, et ampute silencieusement un message long.
            'message': {'trim_whitespace': False, 'error_messages': {
                'required': 'Le message est obligatoire.',
                'blank': 'Le message est obligatoire.',
            }},
        }

    def validate_consent(self, value):
        if not value:
            raise serializers.ValidationError(
                "Le consentement au traitement de vos données est obligatoire."
            )
        return value

    def validate_category(self, value):
        if not value:
            return 'general'
        return value

    def create(self, validated_data):
        validated_data.pop('website', None)
        # Entité fixée par le serveur — jamais par le client.
        entity = get_fha_entity()
        if entity is None:
            raise serializers.ValidationError(
                "L'entité FEBA French Heritage Academy n'est pas configurée."
            )
        validated_data['entity'] = entity
        return super().create(validated_data)


# ── Fiche d'inscription FEBA FHA (12 étapes) ──────────────────────────────────

class FHAEnrollmentCreateSerializer(HoneypotMixin, serializers.ModelSerializer):
    """
    Soumission de la fiche de renseignements FHA.

    `entity`, `reference` et `status` ne sont PAS exposés en écriture : ils
    sont calculés par le serveur.
    """
    child_age = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = FHAEnrollmentApplication
        fields = [
            # étape 1
            'child_last_name', 'child_first_name', 'child_birth_date', 'child_age',
            'child_city', 'child_state_province', 'child_country',
            'child_current_school', 'child_grade', 'child_photo',
            # étape 2
            'family_origin_country', 'home_main_language', 'other_languages',
            'french_speakers_with_child', 'french_speakers_relation',
            # étape 3
            'french_levels', 'french_level_notes',
            # étape 4
            'previous_courses', 'bilingual_school', 'stay_in_francophone_country',
            'certifications_obtained', 'experience_duration', 'experience_comments',
            # étape 5
            'parent_goals', 'parent_goals_other',
            # étape 6
            'parent1_last_name', 'parent1_first_name', 'parent1_relation',
            'parent1_phone', 'parent1_whatsapp', 'parent1_email',
            'parent1_address', 'parent1_city', 'parent1_state_province',
            'parent1_country', 'parent1_postal_code',
            'parent1_preferred_language', 'parent1_timezone',
            # étape 7
            'parent2_last_name', 'parent2_first_name', 'parent2_relation',
            'parent2_phone', 'parent2_whatsapp', 'parent2_email',
            'parent2_address', 'parent2_city', 'parent2_state_province',
            'parent2_country', 'parent2_postal_code',
            'parent2_preferred_language', 'parent2_timezone',
            # étape 8
            'emergency_name', 'emergency_relation', 'emergency_phone',
            'emergency_email', 'emergency_contact_authorized',
            # étape 9
            'available_days', 'available_time_slots', 'family_timezone',
            'weekday_or_weekend', 'availability_notes',
            # étape 10
            'has_computer', 'has_tablet', 'has_camera', 'has_microphone',
            'has_headset', 'has_internet', 'can_print', 'equipment_notes',
            # étape 11
            'special_needs',
            # étape 12
            'consent_rules', 'consent_zoom', 'consent_privacy',
            'consent_data_processing', 'consent_photo_video',
            'consent_communications', 'consent_payment_policy',
            'consent_annual_commitment', 'consent_parental_authorization',
            # anti-spam
            'website',
        ]
        extra_kwargs = {
            'child_last_name': {'error_messages': {
                'required': "Le nom de l'enfant est obligatoire.",
                'blank': "Le nom de l'enfant est obligatoire.",
            }},
            'child_first_name': {'error_messages': {
                'required': "Le prénom de l'enfant est obligatoire.",
                'blank': "Le prénom de l'enfant est obligatoire.",
            }},
            'child_birth_date': {'error_messages': {
                'required': "La date de naissance est obligatoire.",
                'invalid': "Date de naissance invalide (format attendu : AAAA-MM-JJ).",
            }},
            'parent1_last_name': {'error_messages': {
                'required': "Le nom du parent est obligatoire.",
                'blank': "Le nom du parent est obligatoire.",
            }},
            'parent1_first_name': {'error_messages': {
                'required': "Le prénom du parent est obligatoire.",
                'blank': "Le prénom du parent est obligatoire.",
            }},
            'parent1_phone': {'error_messages': {
                'required': "Le téléphone du parent est obligatoire.",
                'blank': "Le téléphone du parent est obligatoire.",
            }},
            'parent1_email': {'error_messages': {
                'required': "L'adresse e-mail du parent est obligatoire.",
                'blank': "L'adresse e-mail du parent est obligatoire.",
                'invalid': "Format d'adresse e-mail invalide.",
            }},
        }

    def get_child_age(self, obj):
        return obj.child_age

    def get_fields(self):
        """
        Les champs de TEXTE LIBRE conservent leur mise en forme.

        DRF retire par défaut les blancs de début et de fin. Sur un nom ou
        un numéro, c'est un nettoyage utile. Sur des besoins particuliers
        ou des précisions de disponibilité, c'est une amputation
        silencieuse — et c'est justement là que la famille écrit ce qui
        compte, en plusieurs paragraphes.
        """
        fields = super().get_fields()
        for name in FREEFORM_TEXT_FIELDS:
            field = fields.get(name)
            if field is not None:
                field.trim_whitespace = False
        return fields

    # ── Validations ──────────────────────────────────────────────────────

    def validate_child_birth_date(self, value):
        today = timezone.localdate()
        if value > today:
            raise serializers.ValidationError(
                "La date de naissance ne peut pas être dans le futur."
            )
        age = today.year - value.year - (
            (today.month, today.day) < (value.month, value.day)
        )
        # Le programme s'adresse aux 6-17 ans. On borne largement pour
        # rejeter les saisies aberrantes sans bloquer un cas limite légitime
        # que l'administration traitera manuellement.
        if age > 25:
            raise serializers.ValidationError(
                "Date de naissance invalide pour un programme destiné aux enfants."
            )
        return value

    def _validate_phone(self, value, field_label):
        if not value:
            return value
        digits = [c for c in value if c.isdigit()]
        if len(digits) < 7:
            raise serializers.ValidationError(
                f"{field_label} : numéro de téléphone invalide."
            )
        return value

    def validate_parent1_phone(self, value):
        return self._validate_phone(value, "Parent 1")

    def validate_parent2_phone(self, value):
        return self._validate_phone(value, "Parent 2")

    def validate_french_levels(self, value):
        valid = {c[0] for c in FHAEnrollmentApplication.FRENCH_LEVEL_CHOICES}
        if not isinstance(value, list):
            raise serializers.ValidationError("Format attendu : liste de valeurs.")
        unknown = [v for v in value if v not in valid]
        if unknown:
            raise serializers.ValidationError(
                f"Niveau(x) de français inconnu(s) : {', '.join(map(str, unknown))}."
            )
        return value

    def validate_parent_goals(self, value):
        valid = {c[0] for c in FHAEnrollmentApplication.PARENT_GOAL_CHOICES}
        if not isinstance(value, list):
            raise serializers.ValidationError("Format attendu : liste de valeurs.")
        unknown = [v for v in value if v not in valid]
        if unknown:
            raise serializers.ValidationError(
                f"Objectif(s) inconnu(s) : {', '.join(map(str, unknown))}."
            )
        return value

    def validate_available_days(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError("Format attendu : liste de jours ISO.")
        for day in value:
            if not isinstance(day, int) or not 1 <= day <= 7:
                raise serializers.ValidationError(
                    "Jour invalide : utiliser 1 (lundi) à 7 (dimanche)."
                )
        return value

    def validate_available_time_slots(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError("Format attendu : liste de créneaux.")
        for slot in value:
            if not isinstance(slot, dict) or 'start' not in slot or 'end' not in slot:
                raise serializers.ValidationError(
                    "Chaque créneau doit contenir « start » et « end » (HH:MM)."
                )
        return value

    def validate_child_photo(self, value):
        """
        Téléversement sécurisé : type MIME réel vérifié (et non l'extension
        annoncée), taille bornée, nom de fichier neutralisé par Django.
        """
        if value is None:
            return value

        max_bytes = 5 * 1024 * 1024
        if value.size > max_bytes:
            raise serializers.ValidationError(
                "La photo ne doit pas dépasser 5 Mo."
            )

        # Vérification du contenu réel via Pillow : un fichier .jpg qui
        # n'est pas une image est rejeté.
        try:
            from PIL import Image
            value.seek(0)
            image = Image.open(value)
            image.verify()
            fmt = (image.format or '').upper()
        except Exception:
            raise serializers.ValidationError(
                "Fichier image invalide ou corrompu."
            )
        finally:
            try:
                value.seek(0)
            except Exception:
                pass

        if fmt not in {'JPEG', 'PNG', 'WEBP'}:
            raise serializers.ValidationError(
                "Formats acceptés : JPEG, PNG ou WEBP."
            )
        return value

    def validate(self, attrs):
        # Consentements strictement obligatoires pour un programme
        # accueillant des mineurs.
        required_consents = {
            'consent_rules': "le règlement",
            'consent_privacy': "la politique de confidentialité",
            'consent_data_processing': "le traitement des données",
            'consent_parental_authorization': "l'autorisation parentale",
        }
        missing = [
            label for field, label in required_consents.items()
            if not attrs.get(field)
        ]
        if missing:
            raise serializers.ValidationError({
                'consents': (
                    "Vous devez accepter : " + ", ".join(missing) + "."
                )
            })

        # Prévention des doublons — vérifiée AVANT l'insertion pour renvoyer
        # un message clair plutôt qu'une erreur d'intégrité brute. La
        # contrainte en base reste la garantie ultime contre les
        # soumissions concurrentes.
        entity = get_fha_entity()
        if entity is not None:
            duplicate = FHAEnrollmentApplication.objects.filter(
                entity=entity,
                parent1_email__iexact=attrs.get('parent1_email', ''),
                child_first_name__iexact=attrs.get('child_first_name', ''),
                child_last_name__iexact=attrs.get('child_last_name', ''),
                child_birth_date=attrs.get('child_birth_date'),
            ).first()
            if duplicate is not None:
                raise serializers.ValidationError({
                    'duplicate': (
                        "Une fiche existe déjà pour cet enfant avec cette adresse "
                        f"e-mail (dossier {duplicate.reference}). Contactez-nous "
                        "si vous souhaitez la modifier."
                    )
                })
        return attrs

    def create(self, validated_data):
        validated_data.pop('website', None)

        entity = get_fha_entity()
        if entity is None:
            raise serializers.ValidationError(
                "L'entité FEBA French Heritage Academy n'est pas configurée."
            )
        # Entité imposée par le serveur, jamais par la requête.
        validated_data['entity'] = entity
        validated_data['status'] = FHAEnrollmentApplication.STATUS_FORM_RECEIVED
        validated_data['consents_accepted_at'] = timezone.now()

        request = self.context.get('request')
        if request is not None:
            forwarded = request.META.get('HTTP_X_FORWARDED_FOR', '')
            validated_data['submitted_ip'] = (
                forwarded.split(',')[0].strip() if forwarded
                else request.META.get('REMOTE_ADDR')
            )

        application = super().create(validated_data)

        # État initial « Fiche reçue » consigné dans l'historique.
        FHAApplicationStatusHistory.objects.create(
            application=application,
            from_status='',
            to_status=application.status,
            reason="Soumission du formulaire public",
        )
        return application


# ── Lecture administrative ────────────────────────────────────────────────────

def _latest_email_state(application, purpose):
    """
    État du dernier envoi de ce type pour ce dossier.

    Exposé jusque dans la LISTE : c'est là que l'administration voit qu'un
    accusé de réception n'est jamais parti. Le reléguer au détail
    reviendrait à ne le montrer qu'à qui le cherche déjà.
    """
    from apps.notifications.email_models import EmailDelivery

    delivery = (
        EmailDelivery.objects
        .filter(purpose=purpose, subject_reference=application.reference)
        .order_by('-created_at').first()
    )
    if delivery is None:
        return {
            'status': 'none', 'status_display': 'Aucun envoi enregistré',
            'accepted': False, 'error': '', 'tracking_id': None,
            'used_real_provider': False, 'sent_at': None,
            'attempts': 0, 'next_retry_at': None,
        }
    return {
        'status': delivery.status,
        'status_display': delivery.get_status_display(),
        'accepted': delivery.is_delivered_to_provider,
        'error': delivery.last_error,
        'tracking_id': str(delivery.tracking_id),
        # Sans ce drapeau, un écran pourrait afficher « envoyé » alors que
        # le message a été écrit dans la console du serveur.
        'used_real_provider': delivery.used_real_provider,
        'sent_at': delivery.sent_at,
        'attempts': delivery.attempts,
        'next_retry_at': delivery.next_retry_at,
    }


class FHAApplicationListSerializer(serializers.ModelSerializer):
    """
    Liste des dossiers pour l'administration FHA.

    N'EXPOSE PAS les besoins particuliers (donnée confidentielle de mineur) :
    ils ne sont lisibles que sur le détail, par un profil habilité.
    """
    child_age = serializers.IntegerField(read_only=True)
    suggested_group = serializers.CharField(read_only=True)
    entity_code = serializers.CharField(source='entity.code', read_only=True)
    entity_short_name = serializers.CharField(source='entity.short_name',
                                              read_only=True)
    status_display = serializers.CharField(source='get_status_display',
                                           read_only=True)
    has_sheet = serializers.BooleanField(read_only=True)
    sheet_generated_at = serializers.DateTimeField(read_only=True)
    confirmation_email = serializers.SerializerMethodField()

    class Meta:
        model = FHAEnrollmentApplication
        fields = [
            'id', 'reference', 'status', 'status_display', 'entity_code',
            'entity_short_name',
            'child_first_name', 'child_last_name', 'child_age',
            'child_country', 'suggested_group', 'recommended_group',
            'parent1_first_name', 'parent1_last_name', 'parent1_email',
            'parent1_phone', 'parent1_whatsapp', 'family_timezone',
            'has_sheet', 'sheet_generated_at', 'confirmation_email',
            'created_at',
        ]

    def get_confirmation_email(self, obj):
        from .fha_enrollment import PURPOSE_PARENT_ACK
        return _latest_email_state(obj, PURPOSE_PARENT_ACK)


class FHAApplicationDetailSerializer(serializers.ModelSerializer):
    """Détail complet d'un dossier (profils habilités uniquement)."""
    child_age = serializers.IntegerField(read_only=True)
    suggested_group = serializers.CharField(read_only=True)
    entity_code = serializers.CharField(source='entity.code', read_only=True)
    entity_name = serializers.CharField(source='entity.name', read_only=True)
    entity_short_name = serializers.CharField(source='entity.short_name',
                                              read_only=True)
    status_display = serializers.CharField(source='get_status_display',
                                           read_only=True)
    status_history = serializers.SerializerMethodField()
    has_sheet = serializers.BooleanField(read_only=True)
    confirmation_email = serializers.SerializerMethodField()
    admin_alert_email = serializers.SerializerMethodField()
    #: Libellés lisibles des champs à choix multiples. Sans eux, l'écran
    #: afficherait « french_explorers » ou « understands_replies_english ».
    labels = serializers.SerializerMethodField()

    class Meta:
        model = FHAEnrollmentApplication
        fields = '__all__'

    def get_confirmation_email(self, obj):
        from .fha_enrollment import PURPOSE_PARENT_ACK
        return _latest_email_state(obj, PURPOSE_PARENT_ACK)

    def get_admin_alert_email(self, obj):
        from .fha_enrollment import PURPOSE_ADMIN_ALERT
        return _latest_email_state(obj, PURPOSE_ADMIN_ALERT)

    def get_labels(self, obj):
        levels = dict(obj.FRENCH_LEVEL_CHOICES)
        goals = dict(obj.PARENT_GOAL_CHOICES)
        days = {1: 'Lundi', 2: 'Mardi', 3: 'Mercredi', 4: 'Jeudi',
                5: 'Vendredi', 6: 'Samedi', 7: 'Dimanche'}
        return {
            'french_levels': [levels.get(v, v) for v in (obj.french_levels or [])],
            'parent_goals': [goals.get(v, v) for v in (obj.parent_goals or [])],
            'available_days': [days.get(v, str(v)) for v in (obj.available_days or [])],
            'weekday_or_weekend': obj.get_weekday_or_weekend_display() or '',
            'recommended_group': obj.get_recommended_group_display() or '',
            'suggested_group': dict(obj.GROUP_CHOICES).get(obj.suggested_group, ''),
            'parent1_preferred_language': obj.get_parent1_preferred_language_display(),
            'parent2_preferred_language': obj.get_parent2_preferred_language_display() or '',
        }

    def get_status_history(self, obj):
        return [
            {
                'from_status': h.from_status,
                'to_status': h.to_status,
                'changed_by': h.changed_by.email if h.changed_by else None,
                'reason': h.reason,
                'comment': h.comment,
                'created_at': h.created_at,
            }
            for h in obj.status_history.select_related('changed_by')
        ]

    def to_representation(self, instance):
        """
        Les besoins particuliers sont une donnée de santé/scolarité d'un
        mineur : masqués pour tout profil non habilité, même en détail.
        """
        data = super().to_representation(instance)
        request = self.context.get('request')
        user = getattr(request, 'user', None) if request else None
        # Habilités : administration (admin/superadmin) uniquement.
        allowed = bool(user and user.is_authenticated and user.is_admin_or_above())
        if not allowed:
            data['special_needs'] = ''
            data['child_photo'] = None
        return data


# ── Test de placement FEBA FHA (parcours DISTINCT de l'inscription) ──────────

class FHAPlacementTestCreateSerializer(HoneypotMixin, serializers.ModelSerializer):
    """
    Réservation d'un test de placement.

    Formulaire COURT et distinct de la fiche d'inscription : réserver un
    test n'engage pas une inscription. `entity`, `reference` et `status`
    sont imposés par le serveur.
    """
    child_age = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = FHAPlacementTestRequest
        fields = [
            'child_first_name', 'child_last_name', 'child_birth_date', 'child_age',
            'child_country', 'child_state_province',
            'parent_first_name', 'parent_last_name', 'parent_email',
            'parent_phone', 'parent_whatsapp', 'parent_timezone',
            'preferred_language', 'estimated_level', 'previous_experience',
            'preferred_date', 'preferred_time', 'alternate_date', 'alternate_time',
            'special_needs', 'consent_video', 'comment', 'website',
        ]
        extra_kwargs = {
            'child_first_name': {'error_messages': {
                'required': "Le prénom de l'enfant est obligatoire.",
                'blank': "Le prénom de l'enfant est obligatoire.",
            }},
            'child_last_name': {'error_messages': {
                'required': "Le nom de l'enfant est obligatoire.",
                'blank': "Le nom de l'enfant est obligatoire.",
            }},
            'child_birth_date': {'error_messages': {
                'required': "La date de naissance est obligatoire.",
                'invalid': "Date de naissance invalide (format attendu : AAAA-MM-JJ).",
            }},
            'parent_email': {'error_messages': {
                'required': "L'adresse e-mail du parent est obligatoire.",
                'blank': "L'adresse e-mail du parent est obligatoire.",
                'invalid': "Format d'adresse e-mail invalide.",
            }},
            'parent_phone': {'error_messages': {
                'required': "Le téléphone du parent est obligatoire.",
                'blank': "Le téléphone du parent est obligatoire.",
            }},
        }

    def get_child_age(self, obj):
        return obj.child_age

    def get_fields(self):
        """Mêmes champs libres, même règle : rien n'est amputé."""
        fields = super().get_fields()
        for name in FREEFORM_TEXT_FIELDS:
            field = fields.get(name)
            if field is not None:
                field.trim_whitespace = False
        return fields

    def validate_child_birth_date(self, value):
        today = timezone.localdate()
        if value > today:
            raise serializers.ValidationError(
                "La date de naissance ne peut pas être dans le futur."
            )
        return value

    def validate_parent_phone(self, value):
        if len([c for c in value if c.isdigit()]) < 7:
            raise serializers.ValidationError("Numéro de téléphone invalide.")
        return value

    def validate_preferred_date(self, value):
        if value and value < timezone.localdate():
            raise serializers.ValidationError(
                "La date souhaitée ne peut pas être dans le passé."
            )
        return value

    def validate_consent_video(self, value):
        if not value:
            raise serializers.ValidationError(
                "Le consentement à la participation en visioconférence est "
                "obligatoire pour passer le test."
            )
        return value

    def validate(self, attrs):
        entity = get_fha_entity()
        if entity is not None:
            existing = FHAPlacementTestRequest.objects.filter(
                entity=entity,
                parent_email__iexact=attrs.get('parent_email', ''),
                child_first_name__iexact=attrs.get('child_first_name', ''),
                child_last_name__iexact=attrs.get('child_last_name', ''),
                child_birth_date=attrs.get('child_birth_date'),
                status__in=['requested', 'scheduled', 'reminded'],
            ).first()
            if existing is not None:
                raise serializers.ValidationError({
                    'duplicate': (
                        "Une demande de test est déjà en cours pour cet enfant "
                        f"(dossier {existing.reference})."
                    )
                })
        return attrs

    def create(self, validated_data):
        validated_data.pop('website', None)
        entity = get_fha_entity()
        if entity is None:
            raise serializers.ValidationError(
                "L'entité FEBA French Heritage Academy n'est pas configurée."
            )
        validated_data['entity'] = entity
        validated_data['status'] = 'requested'

        request = self.context.get('request')
        if request is not None:
            forwarded = request.META.get('HTTP_X_FORWARDED_FOR', '')
            validated_data['submitted_ip'] = (
                forwarded.split(',')[0].strip() if forwarded
                else request.META.get('REMOTE_ADDR')
            )
        return super().create(validated_data)


class FHAPlacementTestListSerializer(serializers.ModelSerializer):
    """Liste administrative. N'expose pas les besoins particuliers."""
    child_age = serializers.IntegerField(read_only=True)
    suggested_group = serializers.CharField(read_only=True)
    entity_code = serializers.CharField(source='entity.code', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = FHAPlacementTestRequest
        fields = [
            'id', 'reference', 'status', 'status_display', 'entity_code',
            'child_first_name', 'child_last_name', 'child_age', 'child_country',
            'suggested_group', 'parent_first_name', 'parent_last_name',
            'parent_email', 'parent_phone', 'parent_timezone',
            'estimated_level', 'preferred_date', 'preferred_time',
            'scheduled_at', 'created_at',
        ]


class FHAPlacementTestDetailSerializer(serializers.ModelSerializer):
    """Détail complet — besoins particuliers réservés aux habilités."""
    child_age = serializers.IntegerField(read_only=True)
    suggested_group = serializers.CharField(read_only=True)
    entity_code = serializers.CharField(source='entity.code', read_only=True)
    result = serializers.SerializerMethodField()

    class Meta:
        model = FHAPlacementTestRequest
        fields = '__all__'

    def get_result(self, obj):
        result = getattr(obj, 'result', None)
        if result is None:
            return None
        return {
            'listening': result.listening,
            'speaking': result.speaking,
            'vocabulary': result.vocabulary,
            'reading': result.reading,
            'writing': result.writing,
            'confidence': result.confidence,
            'recommended_group': result.recommended_group,
            'starting_level': result.starting_level,
            'priority_objectives': result.priority_objectives,
            'assessor_notes': result.assessor_notes,
            'assessed_by': result.assessed_by.email if result.assessed_by else None,
            'assessed_at': result.assessed_at,
        }

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get('request')
        user = getattr(request, 'user', None) if request else None
        allowed = bool(user and user.is_authenticated and user.is_admin_or_above())
        if not allowed:
            data['special_needs'] = ''
        return data
