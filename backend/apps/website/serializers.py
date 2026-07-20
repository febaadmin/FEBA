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
            'school_name', 'tagline', 'signature', 'address', 'phone',
            'whatsapp', 'email', 'opening_hours',
            'facebook_url', 'instagram_url', 'youtube_url',
            'meta_title', 'meta_description', 'og_image',
            'stat_students', 'stat_teachers', 'stat_years', 'stat_success_rate',
        ]


class HeroSlideSerializer(serializers.ModelSerializer):
    image_src = serializers.ReadOnlyField()
    focal = serializers.ReadOnlyField()

    class Meta:
        model = HeroSlide
        fields = ['id', 'title', 'subtitle', 'cta_label', 'cta_url',
                  'image_src', 'image_path', 'focal', 'focal_x', 'focal_y',
                  'order', 'is_active']


class NewsPostListSerializer(serializers.ModelSerializer):
    image_src = serializers.ReadOnlyField()
    focal = serializers.ReadOnlyField()
    kind_display = serializers.CharField(source='get_kind_display', read_only=True)

    class Meta:
        model = NewsPost
        fields = ['id', 'kind', 'kind_display', 'title', 'slug', 'excerpt',
                  'image_src', 'focal', 'event_date', 'location', 'published_at']


class NewsPostDetailSerializer(NewsPostListSerializer):
    class Meta(NewsPostListSerializer.Meta):
        fields = NewsPostListSerializer.Meta.fields + ['body']


class GalleryItemSerializer(serializers.ModelSerializer):
    image_src = serializers.ReadOnlyField()
    focal = serializers.ReadOnlyField()

    class Meta:
        model = GalleryItem
        fields = ['id', 'kind', 'caption', 'alt_text', 'image_src', 'focal',
                  'video_url', 'order']


class GalleryAlbumSerializer(serializers.ModelSerializer):
    items = serializers.SerializerMethodField()

    class Meta:
        model = GalleryAlbum
        fields = ['id', 'title', 'description', 'order', 'items']

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
        fields = ['name', 'email', 'phone', 'subject', 'message', 'consent', 'website']
        extra_kwargs = {
            'name':    {'error_messages': {'required': 'Le nom est obligatoire.', 'blank': 'Le nom est obligatoire.'}},
            'email':   {'error_messages': {'required': "L'email est obligatoire.", 'blank': "L'email est obligatoire.", 'invalid': "Format d'email invalide."}},
            'subject': {'error_messages': {'required': 'Le sujet est obligatoire.', 'blank': 'Le sujet est obligatoire.'}},
            'message': {'error_messages': {'required': 'Le message est obligatoire.', 'blank': 'Le message est obligatoire.'}},
        }

    def create(self, validated_data):
        validated_data.pop('website', None)
        return super().create(validated_data)


class PreRegistrationCreateSerializer(HoneypotMixin, serializers.ModelSerializer):
    class Meta:
        model = PreRegistration
        fields = ['parent_name', 'phone', 'whatsapp', 'email', 'child_name',
                  'child_age', 'desired_level', 'school_year', 'message', 'website']
        extra_kwargs = {
            'parent_name':   {'error_messages': {'required': 'Le nom du parent est obligatoire.', 'blank': 'Le nom du parent est obligatoire.'}},
            'phone':         {'error_messages': {'required': 'Le téléphone est obligatoire.', 'blank': 'Le téléphone est obligatoire.'}},
            'child_name':    {'error_messages': {'required': "Le nom de l'enfant est obligatoire.", 'blank': "Le nom de l'enfant est obligatoire."}},
            'desired_level': {'error_messages': {'required': 'Le niveau souhaité est obligatoire.', 'invalid_choice': 'Niveau invalide.'}},
        }

    def validate_child_age(self, value):
        if value is not None and (value < 1 or value > 18):
            raise serializers.ValidationError("Âge de l'enfant invalide (1 à 18 ans).")
        return value

    def create(self, validated_data):
        validated_data.pop('website', None)
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
    class Meta:
        model = ContactMessage
        fields = '__all__'
        read_only_fields = ['name', 'email', 'phone', 'subject', 'message',
                            'consent', 'created_at']


class PreRegistrationAdminSerializer(serializers.ModelSerializer):
    desired_level_display = serializers.CharField(
        source='get_desired_level_display', read_only=True,
    )
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = PreRegistration
        fields = '__all__'
        read_only_fields = ['parent_name', 'phone', 'whatsapp', 'email',
                            'child_name', 'child_age', 'desired_level',
                            'school_year', 'message', 'created_at']
