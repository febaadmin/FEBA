"""
Modèles du site vitrine public FEBA (P4 v4).

Tout le contenu affiché sur le site public est administrable :
- via l'admin Django (/django-admin/) — CRUD complet immédiat ;
- via l'API REST protégée (/api/website/admin/...) — utilisée par l'écran
  « Site vitrine » de l'ERP React.

Les images peuvent être soit un chemin statique packagé avec le frontend
(`/site/img/<slug>-1600.webp`, produits par scripts/optimize_site_media.py),
soit un fichier téléversé (`upload`). `image_src` fait foi côté API.

Règle « aucune donnée fictive » : les coordonnées, statistiques et contenus
sans valeur réelle restent VIDES en base — le frontend masque les blocs
vides au lieu d'afficher des valeurs inventées.
"""
from django.core.validators import MaxValueValidator
from django.db import models
from django.utils import timezone
from django.utils.text import slugify


class ImageSourceMixin(models.Model):
    """
    Champ image double : chemin statique packagé OU fichier téléversé,
    plus le POINT FOCAL (V5) — position du sujet principal en pourcentage,
    utilisée par le frontend comme object-position pour que le cadrage
    reste correct quel que soit le conteneur, sans modifier le code à
    chaque nouvelle image.
    """
    image_path = models.CharField(
        max_length=255, blank=True,
        help_text="Chemin statique packagé (ex: /site/img/hero-campus-1600.webp) ou URL absolue.",
    )
    upload = models.ImageField(
        upload_to='website/', null=True, blank=True,
        help_text="Image téléversée (prioritaire sur le chemin statique).",
    )
    focal_x = models.PositiveSmallIntegerField(
        default=50, validators=[MaxValueValidator(100)],
        help_text="Point focal horizontal en % (0 = gauche, 50 = centre, 100 = droite).",
    )
    focal_y = models.PositiveSmallIntegerField(
        default=50, validators=[MaxValueValidator(100)],
        help_text="Point focal vertical en % (0 = haut, 50 = centre, 100 = bas).",
    )

    class Meta:
        abstract = True

    @property
    def image_src(self):
        if self.upload:
            try:
                return self.upload.url
            except ValueError:
                pass
        return self.image_path or ''

    @property
    def focal(self):
        """Point focal au format CSS object-position (« 50% 50% »)."""
        return f"{self.focal_x}% {self.focal_y}%"


class SiteSettings(models.Model):
    """
    Paramètres globaux du site public (une seule ligne).
    Les champs vides ne sont PAS affichés par le frontend.
    """
    school_name = models.CharField(max_length=120, default="Faith Excellence Bilingual Academy")
    tagline = models.CharField(
        max_length=200, blank=True,
        default="Développer les talents, construire l'avenir.",
    )
    signature = models.CharField(
        max_length=200, blank=True,
        default="FEBA, l'école autrement avec vous.",
    )
    address = models.CharField(max_length=255, blank=True, default="Akpakpa, Cotonou, Bénin")
    phone = models.CharField(max_length=30, blank=True)
    whatsapp = models.CharField(
        max_length=30, blank=True,
        help_text="Numéro WhatsApp au format international (+229...). Vide = bouton masqué.",
    )
    email = models.EmailField(blank=True)
    opening_hours = models.CharField(max_length=255, blank=True)
    facebook_url = models.URLField(blank=True)
    instagram_url = models.URLField(blank=True)
    youtube_url = models.URLField(blank=True)
    # SEO par défaut
    meta_title = models.CharField(
        max_length=120, blank=True,
        default="FEBA — Faith Excellence Bilingual Academy | École bilingue à Cotonou",
    )
    meta_description = models.CharField(
        max_length=300, blank=True,
        default=(
            "École bilingue français-anglais à Akpakpa, Cotonou : garderie, "
            "maternelle et primaire. Encadrement de qualité, valeurs et excellence."
        ),
    )
    og_image = models.CharField(
        max_length=255, blank=True, default="/site/img/hero-campus-1600.webp",
    )
    # Statistiques : renseignées par l'administration, sinon masquées.
    stat_students = models.PositiveIntegerField(null=True, blank=True)
    stat_teachers = models.PositiveIntegerField(null=True, blank=True)
    stat_years = models.PositiveIntegerField(null=True, blank=True, verbose_name="Années d'expérience")
    stat_success_rate = models.PositiveIntegerField(
        null=True, blank=True, help_text="Taux de réussite en % (vide = masqué).",
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Paramètres du site'
        verbose_name_plural = 'Paramètres du site'

    def __str__(self):
        return f"Paramètres du site — {self.school_name}"

    @classmethod
    def load(cls):
        obj = cls.objects.order_by('id').first()
        return obj if obj else cls.objects.create()


class HeroSlide(ImageSourceMixin):
    title = models.CharField(max_length=120)
    subtitle = models.CharField(max_length=255, blank=True)
    cta_label = models.CharField(max_length=60, blank=True, verbose_name="Texte du bouton")
    cta_url = models.CharField(max_length=255, blank=True, verbose_name="Lien du bouton")
    order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Slide du carrousel'
        verbose_name_plural = 'Slides du carrousel'
        ordering = ['order', 'id']

    def __str__(self):
        return f"Slide {self.order} — {self.title}"


class NewsPost(ImageSourceMixin):
    KIND_CHOICES = [('news', 'Actualité'), ('event', 'Événement')]

    kind = models.CharField(max_length=10, choices=KIND_CHOICES, default='news')
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True, blank=True)
    excerpt = models.CharField(max_length=300, blank=True)
    body = models.TextField(blank=True)
    event_date = models.DateTimeField(
        null=True, blank=True, help_text="Date de l'événement (pour kind=event).",
    )
    location = models.CharField(max_length=200, blank=True)
    is_published = models.BooleanField(default=False)
    published_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Actualité / Événement'
        verbose_name_plural = 'Actualités / Événements'
        ordering = ['-published_at', '-created_at']

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.title)[:200] or 'article'
            slug = base
            n = 2
            while NewsPost.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base}-{n}"
                n += 1
            self.slug = slug
        if self.is_published and self.published_at is None:
            self.published_at = timezone.now()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"[{self.get_kind_display()}] {self.title}"


class GalleryAlbum(models.Model):
    title = models.CharField(max_length=120)
    description = models.CharField(max_length=300, blank=True)
    order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Album galerie'
        verbose_name_plural = 'Albums galerie'
        ordering = ['order', 'id']

    def __str__(self):
        return self.title


class GalleryItem(ImageSourceMixin):
    KIND_CHOICES = [('image', 'Image'), ('video', 'Vidéo')]

    album = models.ForeignKey(GalleryAlbum, on_delete=models.CASCADE, related_name='items')
    kind = models.CharField(max_length=10, choices=KIND_CHOICES, default='image')
    caption = models.CharField(max_length=200, blank=True)
    alt_text = models.CharField(
        max_length=200, blank=True,
        help_text="Texte alternatif (accessibilité). Repli sur la légende si vide.",
    )
    video_url = models.CharField(
        max_length=255, blank=True,
        help_text="Chemin du MP4 packagé (/site/video/...) ou URL (pour kind=video).",
    )
    order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Média galerie'
        verbose_name_plural = 'Médias galerie'
        ordering = ['album', 'order', 'id']

    def __str__(self):
        return f"{self.album} — {self.caption or self.image_src or self.video_url}"


class ContactMessage(models.Model):
    """Soumission du formulaire de contact public. Jamais exposée publiquement."""
    name = models.CharField(max_length=120)
    email = models.EmailField()
    phone = models.CharField(max_length=30, blank=True)
    subject = models.CharField(max_length=200)
    message = models.TextField()
    consent = models.BooleanField(default=False)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Message de contact'
        verbose_name_plural = 'Messages de contact'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} — {self.subject} ({self.created_at:%d/%m/%Y})"


class PreRegistration(models.Model):
    """Demande de préinscription publique. Jamais exposée publiquement."""
    STATUS_CHOICES = [
        ('new', 'Nouvelle'),
        ('processing', 'En traitement'),
        ('closed', 'Clôturée'),
    ]
    LEVEL_CHOICES = [
        ('garderie', 'Garderie'),
        ('maternelle1', 'Maternelle 1'),
        ('maternelle2', 'Maternelle 2'),
        ('ci', 'CI'),
        ('cp', 'CP'),
        ('ce1', 'CE1'),
        ('ce2', 'CE2'),
        ('cm1', 'CM1'),
        ('cm2', 'CM2'),
        ('feba_online', 'FEBA Online'),
    ]

    parent_name = models.CharField(max_length=120)
    phone = models.CharField(max_length=30)
    whatsapp = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)
    child_name = models.CharField(max_length=120)
    child_age = models.PositiveSmallIntegerField(null=True, blank=True)
    desired_level = models.CharField(max_length=20, choices=LEVEL_CHOICES)
    school_year = models.CharField(max_length=20, blank=True)
    message = models.TextField(blank=True)
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default='new')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Demande de préinscription'
        verbose_name_plural = 'Demandes de préinscription'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.child_name} ({self.get_desired_level_display()}) — {self.parent_name}"
