from rest_framework import serializers

from .models import (
    SiteSettings, HeroSlide, NewsPost, GalleryAlbum, GalleryItem,
    ContactMessage, PreRegistration,
)


# ── Lecture publique ───────────────────────────────────────────────────────────

class SiteSettingsPublicSerializer(serializers.ModelSerializer):
    class Meta:
        model = SiteSettings
        fields = [
            'school_name', 'tagline', 'tagline_en', 'signature', 'address', 'phone',
            'whatsapp', 'email', 'opening_hours', 'opening_hours_en',
            'facebook_url', 'instagram_url', 'youtube_url',
            'meta_title', 'meta_description', 'meta_description_en', 'og_image',
            'stat_students', 'stat_teachers', 'stat_years', 'stat_success_rate',
        ]


class HeroSlideSerializer(serializers.ModelSerializer):
    image_src = serializers.ReadOnlyField()
    focal = serializers.ReadOnlyField()

    class Meta:
        model = HeroSlide
        # Les variantes anglaises sont exposées TELLES QUELLES, vides
        # comprises : c'est le frontend qui décide du repli, en fonction de
        # la langue affichée. Choisir côté serveur imposerait une langue à
        # tous les visiteurs.
        fields = ['id', 'title', 'title_en', 'subtitle', 'subtitle_en',
                  'cta_label', 'cta_label_en', 'cta_url',
                  'image_src', 'image_path', 'focal', 'focal_x', 'focal_y',
                  'order', 'is_active']


class NewsPostListSerializer(serializers.ModelSerializer):
    image_src = serializers.ReadOnlyField()
    focal = serializers.ReadOnlyField()
    kind_display = serializers.CharField(source='get_kind_display', read_only=True)

    class Meta:
        model = NewsPost
        fields = ['id', 'kind', 'kind_display', 'title', 'title_en', 'slug',
                  'excerpt', 'excerpt_en',
                  'image_src', 'focal', 'event_date', 'location', 'published_at']


class NewsPostDetailSerializer(NewsPostListSerializer):
    class Meta(NewsPostListSerializer.Meta):
        fields = NewsPostListSerializer.Meta.fields + ['body', 'body_en']


class GalleryItemSerializer(serializers.ModelSerializer):
    image_src = serializers.ReadOnlyField()
    focal = serializers.ReadOnlyField()

    class Meta:
        model = GalleryItem
        fields = ['id', 'kind', 'caption', 'caption_en', 'alt_text', 'alt_text_en',
                  'image_src', 'focal', 'video_url', 'order']


class GalleryAlbumSerializer(serializers.ModelSerializer):
    items = serializers.SerializerMethodField()

    class Meta:
        model = GalleryAlbum
        fields = ['id', 'title', 'title_en', 'description', 'description_en',
                  'order', 'items']

    def get_items(self, obj):
        qs = obj.items.filter(is_active=True)
        return GalleryItemSerializer(qs, many=True).data


# ── Formulaires publics (écriture) ─────────────────────────────────────────────

class HoneypotMixin(serializers.Serializer):
    """
    Champ anti-spam invisible : les humains le laissent vide, les robots le
    remplissent. Toute valeur → rejet silencieux (validation générique).
    """
    website = serializers.CharField(
        required=False, allow_blank=True, write_only=True, max_length=100,
    )

    def validate_website(self, value):
        if value:
            raise serializers.ValidationError("Soumission invalide.")
        return value


class ContactMessageCreateSerializer(HoneypotMixin, serializers.ModelSerializer):
    class Meta:
        model = ContactMessage
        # P5 — « whatsapp » manquait ici. Le champ existait en base, le
        # formulaire pouvait l'envoyer : DRF ignore silencieusement une clé
        # non déclarée, et le numéro disparaissait entre le navigateur et
        # la base sans la moindre erreur.
        fields = ['name', 'email', 'phone', 'whatsapp', 'subject', 'message',
                  'consent', 'website']
        extra_kwargs = {
            'name':    {'error_messages': {'required': 'Le nom est obligatoire.', 'blank': 'Le nom est obligatoire.'}},
            'email':   {'error_messages': {'required': "L'email est obligatoire.", 'blank': "L'email est obligatoire.", 'invalid': "Format d'email invalide."}},
            'subject': {'error_messages': {'required': 'Le sujet est obligatoire.', 'blank': 'Le sujet est obligatoire.'}},
            # `trim_whitespace` vaut True par défaut dans DRF : les blancs
            # de début et de fin — retours à la ligne compris — étaient
            # retirés du message. Un texte de 7 014 caractères arrivait à
            # 7 012 en base, sans erreur et sans que personne ne le sache.
            # Sur les champs d'une ligne le nettoyage est utile ; sur un
            # message, la mise en forme appartient à celui qui l'écrit.
            'message': {'trim_whitespace': False,
                        'error_messages': {'required': 'Le message est obligatoire.', 'blank': 'Le message est obligatoire.'}},
        }

    def create(self, validated_data):
        validated_data.pop('website', None)
        # MULTI-ENTITÉS : ce formulaire est celui de FEBA. L'entité est
        # imposée par le serveur d'après le code interne stable — un
        # « entity » envoyé par le navigateur n'est pas déclaré ici et
        # serait donc ignoré.
        from .fha_serializers import get_feba_entity
        validated_data['entity'] = get_feba_entity()
        return super().create(validated_data)


class PreRegistrationCreateSerializer(HoneypotMixin, serializers.ModelSerializer):
    class Meta:
        model = PreRegistration
        # P2 — Les trois champs ajoutés (téléphone secondaire, adresse,
        # date de naissance) sont ACCEPTÉS ICI. Un champ présent dans le
        # formulaire React mais absent de cette liste est silencieusement
        # jeté par DRF : la famille croit l'avoir renseigné, la base ne le
        # reçoit jamais, et personne ne s'en aperçoit. C'est exactement ce
        # que vérifie `test_field_mapping_audit.py`.
        fields = ['parent_name', 'phone', 'phone_secondary', 'whatsapp',
                  'email', 'address', 'child_name', 'child_age',
                  'child_birth_date', 'desired_level', 'school_year',
                  'message', 'website']
        extra_kwargs = {
            # `trim_whitespace=False` : DRF retire par défaut les espaces
            # de début et de fin. Sur un message qui commence par un saut
            # de ligne, deux caractères disparaissaient sans trace.
            'message': {'trim_whitespace': False},
            'address': {'trim_whitespace': False},
            'parent_name':   {'error_messages': {'required': 'Le nom du parent est obligatoire.', 'blank': 'Le nom du parent est obligatoire.'}},
            'phone':         {'error_messages': {'required': 'Le téléphone est obligatoire.', 'blank': 'Le téléphone est obligatoire.'}},
            'child_name':    {'error_messages': {'required': "Le nom de l'enfant est obligatoire.", 'blank': "Le nom de l'enfant est obligatoire."}},
            'desired_level': {'error_messages': {'required': 'Le niveau souhaité est obligatoire.', 'invalid_choice': 'Niveau invalide.'}},
        }

    def validate_child_age(self, value):
        if value is not None and (value < 1 or value > 18):
            raise serializers.ValidationError("Âge de l'enfant invalide (1 à 18 ans).")
        return value

    def validate_child_birth_date(self, value):
        """
        Une date de naissance dans le futur n'est pas une faute de frappe
        anodine : elle fausse le calcul du niveau réglementaire.
        """
        from django.utils import timezone

        if value is None:
            return value
        today = timezone.localdate()
        if value > today:
            raise serializers.ValidationError(
                "La date de naissance ne peut pas être dans le futur.")
        if (today.year - value.year) > 25:
            raise serializers.ValidationError(
                "Date de naissance invalide pour une préinscription.")
        return value

    def create(self, validated_data):
        validated_data.pop('website', None)
        # Préinscription FEBA : entité FEBA, fixée côté serveur. Le
        # formulaire FEBA FHA est un endpoint distinct
        # (/api/website/public/fha/enroll/) avec son propre modèle.
        from .fha_serializers import get_feba_entity
        validated_data['entity'] = get_feba_entity()
        return super().create(validated_data)


# ── Administration (CRUD complet, permission admin) ────────────────────────────

class SiteSettingsAdminSerializer(serializers.ModelSerializer):
    class Meta:
        model = SiteSettings
        fields = '__all__'


class NewsPostAdminSerializer(serializers.ModelSerializer):
    image_src = serializers.ReadOnlyField()

    class Meta:
        model = NewsPost
        fields = '__all__'
        read_only_fields = ['slug', 'created_at', 'updated_at']


class GalleryAlbumAdminSerializer(serializers.ModelSerializer):
    class Meta:
        model = GalleryAlbum
        fields = '__all__'


class GalleryItemAdminSerializer(serializers.ModelSerializer):
    image_src = serializers.ReadOnlyField()

    class Meta:
        model = GalleryItem
        fields = '__all__'


class ContactMessageAdminSerializer(serializers.ModelSerializer):
    """
    Message reçu, vu par l'administration.

    P5 — `fields = '__all__'` exposait déjà toutes les colonnes, mais rien
    n'identifiait l'ACADÉMIE destinataire autrement que par une clé
    étrangère numérique. En mode « Toutes les Académies », deux messages
    voisins pouvaient venir d'établissements différents sans que la ligne
    le dise.
    """
    entity_code = serializers.CharField(source='entity.code', read_only=True,
                                        default='')
    entity_name = serializers.CharField(source='entity.name', read_only=True,
                                        default='')
    entity_short_name = serializers.CharField(source='entity.short_name',
                                              read_only=True, default='')
    category_display = serializers.CharField(source='get_category_display',
                                             read_only=True, default='')
    preferred_language_display = serializers.CharField(
        source='get_preferred_language_display', read_only=True, default='',
    )

    class Meta:
        model = ContactMessage
        fields = '__all__'
        # Tout ce que le visiteur a saisi est en lecture seule : un message
        # reçu est une pièce, pas un brouillon. Seul `is_read` change.
        read_only_fields = [
            'name', 'email', 'phone', 'whatsapp', 'subject', 'message',
            'consent', 'created_at', 'entity', 'country', 'state_province',
            'timezone', 'preferred_language', 'category',
        ]


class PreRegistrationAdminSerializer(serializers.ModelSerializer):
    """
    P2 — La demande TELLE QU'ELLE A ÉTÉ DÉPOSÉE, en entier.

    `fields = '__all__'` est délibéré : une liste explicite se désynchronise
    du modèle à la première colonne ajoutée, et le symptôme est
    précisément celui qu'on corrige — un champ collecté depuis des mois
    qui n'apparaît sur aucun écran.
    """
    desired_level_display = serializers.CharField(
        source='get_desired_level_display', read_only=True,
    )
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    academy_code = serializers.CharField(source='entity.code', read_only=True,
                                         default='')
    academy_name = serializers.CharField(source='entity.name', read_only=True,
                                         default='')
    #: État réel de la fiche PDF — jamais déduit côté écran. Un booléen
    #: calculé dans le navigateur à partir de `sheet_path` dirait « oui »
    #: pour un fichier effacé du disque.
    sheet_available = serializers.SerializerMethodField()

    class Meta:
        model = PreRegistration
        fields = '__all__'
        read_only_fields = ['reference', 'parent_name', 'phone',
                            'phone_secondary', 'whatsapp', 'email', 'address',
                            'child_name', 'child_age', 'child_birth_date',
                            'desired_level', 'school_year', 'message',
                            'created_at', 'sheet_path', 'sheet_sha256',
                            'sheet_generated_at', 'sheet_error']

    def get_sheet_available(self, obj):
        return obj.has_sheet
