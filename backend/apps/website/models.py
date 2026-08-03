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
import os

from django.core.validators import MaxValueValidator
from django.db import models

from apps.website.private_storage import private_storage
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
    school_name = models.CharField(max_length=120, default="Faith & Excellence Bilingual Academy")
    tagline = models.CharField(
        max_length=200, blank=True,
        default="Développer les talents, construire l'avenir.",
    )
    tagline_en = models.CharField(
        max_length=200, blank=True, verbose_name="Slogan (EN)",
        default="Developing talent, building the future.",
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
    opening_hours_en = models.CharField(max_length=255, blank=True, verbose_name="Horaires (EN)")
    facebook_url = models.URLField(blank=True)
    instagram_url = models.URLField(blank=True)
    youtube_url = models.URLField(blank=True)
    # SEO par défaut
    meta_title = models.CharField(
        max_length=120, blank=True,
        default="FEBA — Faith & Excellence Bilingual Academy | École bilingue à Cotonou",
    )
    meta_description = models.CharField(
        max_length=300, blank=True,
        default=(
            "École bilingue français-anglais à Akpakpa, Cotonou : garderie, "
            "maternelle et primaire. Encadrement de qualité, valeurs et excellence."
        ),
    )
    meta_description_en = models.CharField(
        max_length=300, blank=True, verbose_name="Méta-description (EN)",
        default=(
            "French-English bilingual school in Akpakpa, Cotonou: nursery, "
            "kindergarten and primary. Quality teaching, values and excellence."
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


# ── Contenu administré bilingue (P1) ────────────────────────────────────
# Le sélecteur EN/FR traduisait les libellés codés dans le frontend, mais
# PAS le contenu saisi par l'administration : le carrousel, les titres
# d'albums et les actualités restaient en français même en mode anglais.
# Or le carrousel est la toute première chose que voit un visiteur.
#
# Chaque champ éditorial reçoit donc son pendant `_en`, FACULTATIF : laissé
# vide, le frontend retombe sur le français plutôt que d'afficher un blanc.
# Traduire reste un choix éditorial, ce n'est pas une obligation technique.


class HeroSlide(ImageSourceMixin):
    title = models.CharField(max_length=120)
    title_en = models.CharField(max_length=120, blank=True, verbose_name="Titre (EN)")
    subtitle = models.CharField(max_length=255, blank=True)
    subtitle_en = models.CharField(max_length=255, blank=True, verbose_name="Sous-titre (EN)")
    cta_label = models.CharField(max_length=60, blank=True, verbose_name="Texte du bouton")
    cta_label_en = models.CharField(max_length=60, blank=True, verbose_name="Texte du bouton (EN)")
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
    title_en = models.CharField(max_length=200, blank=True, verbose_name="Titre (EN)")
    slug = models.SlugField(max_length=220, unique=True, blank=True)
    excerpt = models.CharField(max_length=300, blank=True)
    excerpt_en = models.CharField(max_length=300, blank=True, verbose_name="Résumé (EN)")
    body = models.TextField(blank=True)
    body_en = models.TextField(blank=True, verbose_name="Contenu (EN)")
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
    title_en = models.CharField(max_length=120, blank=True, verbose_name="Titre (EN)")
    description = models.CharField(max_length=300, blank=True)
    description_en = models.CharField(max_length=300, blank=True, verbose_name="Description (EN)")
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
    caption_en = models.CharField(max_length=200, blank=True, verbose_name="Légende (EN)")
    alt_text = models.CharField(
        max_length=200, blank=True,
        help_text="Texte alternatif (accessibilité). Repli sur la légende si vide.",
    )
    alt_text_en = models.CharField(
        max_length=200, blank=True, verbose_name="Texte alternatif (EN)",
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
    """
    Soumission d'un formulaire de contact public. Jamais exposée publiquement.

    MULTI-ENTITÉS : chaque message appartient à UNE entité, déterminée par la
    ROUTE utilisée (/contact → FEBA, /feba-fha/contact → FEBA FHA) et fixée
    CÔTÉ SERVEUR. Un `entity` envoyé par le navigateur est ignoré.
    Les boîtes de réception administratives sont séparées par entité.
    """
    # Catégories propres au programme FEBA FHA (académie en ligne).
    CATEGORY_CHOICES = [
        ('general', 'Informations générales'),
        ('enrollment', 'Inscription'),
        ('placement_test', 'Test de placement'),
        ('payment', 'Paiement'),
        ('zoom', 'Zoom / cours en direct'),
        ('technical', 'Support technique'),
        ('pedagogical', 'Question pédagogique'),
        ('absence', 'Absence'),
        ('document', 'Document'),
        ('other', 'Autre'),
    ]

    entity = models.ForeignKey(
        'schools.School', on_delete=models.PROTECT, null=True, blank=True,
        related_name='contact_messages',
        help_text="Entité destinataire. Déterminée par la route côté serveur.",
    )
    name = models.CharField(max_length=120)
    email = models.EmailField()
    phone = models.CharField(max_length=30, blank=True)
    subject = models.CharField(max_length=200)
    message = models.TextField()
    consent = models.BooleanField(default=False)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    # --- Champs propres au formulaire FEBA FHA (familles internationales) ---
    # Restent vides pour les messages FEBA : le formulaire FEBA ne les
    # collecte pas et le frontend ne les affiche pas.
    whatsapp = models.CharField(max_length=30, blank=True)
    country = models.CharField(max_length=100, blank=True)
    state_province = models.CharField(max_length=100, blank=True)
    timezone = models.CharField(
        max_length=64, blank=True,
        help_text="Fuseau horaire déclaré par la famille (affichage des créneaux).",
    )
    preferred_language = models.CharField(
        max_length=5, blank=True,
        choices=[('fr', 'Français'), ('en', 'English')],
    )
    category = models.CharField(
        max_length=20, choices=CATEGORY_CHOICES, blank=True,
    )

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
        # Libellé renommé : « FEBA Online » est devenu FEBA French
        # Heritage Academy. La CLÉ reste `feba_online` pour ne pas
        # invalider les demandes déjà enregistrées en base.
        ('feba_online', 'FEBA French Heritage Academy'),
    ]

    entity = models.ForeignKey(
        'schools.School', on_delete=models.PROTECT, null=True, blank=True,
        related_name='preregistrations',
        help_text="Entité de la demande. Fixée côté serveur (formulaire FEBA).",
    )
    #: Numéro de dossier institutionnel, attribué à l'enregistrement.
    #: Il figure sur la fiche PDF et sert de référence dans les échanges
    #: avec la famille : « votre dossier FEBA-2026-0042 ».
    #: `null=True` sur un CharField est en général une mauvaise idée — deux
    #: valeurs « vides » possibles. ICI C'EST LA SEULE FORME CORRECTE, et
    #: pour une raison précise.
    #:
    #: La référence contient l'identifiant de la ligne : elle ne peut donc
    #: être calculée qu'APRÈS l'insertion. Entre l'insertion et la mise à
    #: jour, la ligne porte une valeur transitoire. Avec `blank=True` et
    #: la valeur par défaut `""`, cette valeur transitoire est une chaîne
    #: vide — et deux insertions simultanées se retrouvent toutes deux à
    #: `""`, ce que la contrainte d'unicité refuse :
    #:
    #:     IntegrityError: duplicate key value violates unique constraint
    #:     "website_preregistration_reference_key"
    #:
    #: NULL, lui, n'est égal à rien, pas même à un autre NULL : autant
    #: d'insertions simultanées que l'on veut peuvent traverser la fenêtre
    #: sans se gêner. La valeur définitive est écrite juste après, dans la
    #: même transaction.
    reference = models.CharField(
        max_length=32, unique=True, null=True, blank=True,
        help_text="Numéro de dossier. Attribué automatiquement.",
    )

    parent_name = models.CharField(max_length=120)
    phone = models.CharField(max_length=30)
    #: P2 — Second numéro. Au Bénin, un parent joignable le jour n'est pas
    #: toujours joignable le soir, et la demande restait sans suite faute
    #: d'un deuxième contact.
    phone_secondary = models.CharField(max_length=30, blank=True)
    whatsapp = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)
    #: P2 — Adresse du domicile. Elle détermine le ramassage scolaire et
    #: la zone d'affectation ; la demander au téléphone, une par une, est
    #: une perte de temps pour le secrétariat comme pour la famille.
    address = models.TextField(blank=True)

    child_name = models.CharField(max_length=120)
    child_age = models.PositiveSmallIntegerField(null=True, blank=True)
    #: P2 — La date de naissance, pas seulement l'âge : un âge saisi en
    #: mars n'est plus vrai en septembre, et c'est la date qui décide de
    #: l'affectation au niveau réglementaire.
    child_birth_date = models.DateField(null=True, blank=True)
    desired_level = models.CharField(max_length=20, choices=LEVEL_CHOICES)
    school_year = models.CharField(max_length=20, blank=True)
    message = models.TextField(blank=True)
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default='new')
    created_at = models.DateTimeField(auto_now_add=True)

    # ── Fiche PDF institutionnelle ───────────────────────────────────
    #
    # P2 — Chaque demande produit une fiche PDF à l'en-tête FEBA. Les
    # trois champs ci-dessous existent pour que l'ÉCHEC de cette
    # production soit visible : sans eux, une fiche manquante ne se
    # remarque que le jour où quelqu'un la cherche.
    sheet_path = models.CharField(max_length=255, blank=True)
    sheet_sha256 = models.CharField(max_length=64, blank=True)
    sheet_generated_at = models.DateTimeField(null=True, blank=True)
    sheet_error = models.TextField(
        blank=True,
        help_text="Motif du dernier échec de production. Vide si la "
                  "dernière tentative a réussi.",
    )

    class Meta:
        verbose_name = 'Demande de préinscription'
        verbose_name_plural = 'Demandes de préinscription'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.child_name} ({self.get_desired_level_display()}) — {self.parent_name}"

    def save(self, *args, **kwargs):
        creating = self._state.adding
        super().save(*args, **kwargs)
        if creating and not self.reference:
            # Deuxième passage, limité à la seule colonne concernée : la
            # référence dérive de l'identifiant, qui n'existe qu'après
            # l'insertion.
            self.reference = self.build_reference()
            super().save(update_fields=["reference"])

    def build_reference(self):
        """
        Numéro de dossier : « FEBA-2026-0042 ».

        Il dérive de la CLÉ PRIMAIRE, jamais d'un `count() + 1`. Compter
        les lignes existantes donnerait le même numéro à deux demandes
        déposées dans la même seconde, et redonnerait un numéro déjà
        attribué dès qu'une demande est supprimée — deux dossiers
        différents portant la même référence dans les échanges avec deux
        familles. La séquence de la base, elle, ne revient jamais en
        arrière.
        """
        year = (self.created_at or timezone.now()).year
        return f"FEBA-{year}-{self.pk:04d}"

    @property
    def has_sheet(self):
        """Une fiche existe ET le fichier est encore là."""
        return bool(self.sheet_path) and os.path.exists(self.sheet_absolute_path)

    @property
    def sheet_absolute_path(self):
        from .private_storage import prereg_sheet_root

        if not self.sheet_path:
            return ""
        return os.path.join(prereg_sheet_root(), self.sheet_path)

    def store_sheet(self, content):
        """
        Écrit la fiche dans le stockage privé et enregistre son empreinte.

        Le fichier ne va JAMAIS dans `MEDIA_ROOT` : ce répertoire est servi
        statiquement, et une URL devinée suffirait à exposer l'adresse et
        le téléphone d'une famille. Il sort uniquement par une vue
        authentifiée qui vérifie l'académie du demandeur.
        """
        import hashlib

        from apps.website.private_storage import prereg_sheet_root

        relative = os.path.join(str(self.entity_id or 0), f"{self.reference}.pdf")
        absolute = os.path.join(prereg_sheet_root(), relative)
        os.makedirs(os.path.dirname(absolute), exist_ok=True)
        with open(absolute, "wb") as handle:
            handle.write(content)
        # 0600 : les permissions par défaut d'un serveur partagé sont
        # souvent lisibles par tous les comptes de la machine.
        try:
            os.chmod(absolute, 0o600)
        except OSError:  # pragma: no cover — dépend du système de fichiers
            pass

        self.sheet_path = relative
        self.sheet_sha256 = hashlib.sha256(content).hexdigest()
        self.sheet_generated_at = timezone.now()
        self.sheet_error = ""


class FHAEnrollmentApplication(models.Model):
    """
    Fiche de renseignements FEBA French Heritage Academy.

    Formulaire DISTINCT de la préinscription FEBA (`PreRegistration`) : le
    programme FHA est une académie en ligne pour la diaspora, et les
    informations nécessaires (origines, niveau de français, fuseau horaire,
    équipement, consentements) n'ont aucun équivalent dans le formulaire
    présentiel de Cotonou.

    L'ENTITÉ EST TOUJOURS FIXÉE CÔTÉ SERVEUR à partir de la route
    `/api/website/public/fha/enroll/`. Aucun `entity` transmis par le
    navigateur n'est lu.

    Les blocs suivent le cahier de structure du site (document de cadrage) :
      1. enfant — 2. origines/langues — 3. niveau de français —
      4. expérience — 5. objectifs — 6. parent 1 — 7. parent 2 —
      8. contact d'urgence — 9. disponibilités — 10. équipement —
      11. besoins particuliers — 12. consentements.
    """

    # États du dossier, repris tels quels du cahier de structure.
    STATUS_NEW_CONTACT = 'new_contact'
    STATUS_FORM_RECEIVED = 'form_received'
    STATUS_CHOICES = [
        (STATUS_NEW_CONTACT, 'Nouveau contact'),
        (STATUS_FORM_RECEIVED, 'Fiche reçue'),
        ('test_booked', 'Test réservé'),
        ('test_done', 'Test effectué'),
        ('admission_offered', 'Admission proposée'),
        ('documents_pending', 'Documents en attente'),
        ('payment_pending', 'Paiement en attente'),
        ('enrollment_confirmed', 'Inscription confirmée'),
        ('account_activated', 'Compte activé'),
        ('student_active', 'Élève actif'),
        ('suspended', 'Suspendu'),
        ('cancelled', 'Annulé'),
    ]

    # Niveau de français : cases à cocher cumulables (un enfant peut
    # « comprendre quelques mots » ET « répondre en anglais »).
    FRENCH_LEVEL_CHOICES = [
        ('no_understanding', "Ne comprend pas le français"),
        ('few_words', "Comprend quelques mots"),
        ('understands_replies_english', "Comprend mais répond en anglais"),
        ('speaks_with_difficulty', "Parle difficilement"),
        ('speaks_well', "Parle correctement"),
        ('reads', "Lit le français"),
        ('writes', "Écrit le français"),
    ]

    PARENT_GOAL_CHOICES = [
        ('family_conversation', "Conversation familiale"),
        ('grandparents', "Communication avec les grands-parents"),
        ('reading', "Lecture"),
        ('writing', "Écriture"),
        ('african_culture', "Culture africaine"),
        ('travel', "Voyage"),
        ('return_home', "Retour au pays"),
        ('studies', "Études"),
        ('certification', "Certification"),
        ('oral_confidence', "Confiance à l'oral"),
        ('other', "Autre objectif"),
    ]

    # Groupes de lancement (âges issus du document de cadrage).
    GROUP_JUNIOR_ROOTS = 'junior_roots'
    GROUP_FRENCH_EXPLORERS = 'french_explorers'
    GROUP_FRENCH_AMBASSADORS = 'french_ambassadors'
    GROUP_CHOICES = [
        (GROUP_JUNIOR_ROOTS, 'Junior Roots (6-9 ans)'),
        (GROUP_FRENCH_EXPLORERS, 'French Explorers (10-15 ans)'),
        (GROUP_FRENCH_AMBASSADORS, 'French Ambassadors (16-17 ans)'),
    ]

    entity = models.ForeignKey(
        'schools.School', on_delete=models.PROTECT,
        related_name='fha_applications',
        help_text="Toujours FEBA_FHA. Déterminé par la route, jamais par le client.",
    )
    reference = models.CharField(
        max_length=24, unique=True, blank=True,
        help_text="Numéro de dossier unique communiqué à la famille (ex: FHA-2026-0001).",
    )
    status = models.CharField(
        max_length=24, choices=STATUS_CHOICES, default=STATUS_FORM_RECEIVED,
    )

    # ── Étape 1 : informations sur l'enfant ─────────────────────────────
    child_last_name = models.CharField(max_length=120)
    child_first_name = models.CharField(max_length=120)
    child_birth_date = models.DateField()
    child_city = models.CharField(max_length=120, blank=True)
    child_state_province = models.CharField(max_length=120, blank=True)
    child_country = models.CharField(max_length=100, blank=True)
    child_current_school = models.CharField(max_length=200, blank=True)
    child_grade = models.CharField(max_length=60, blank=True)
    child_photo = models.ImageField(
        upload_to='fha/children/', null=True, blank=True,
        # P11 — STOCKAGE PRIVÉ. La photo partait dans MEDIA_ROOT, que nginx
        # publie sous /media/ : la photo d'un mineur était atteignable par
        # une URL, sans authentification, pour qui la devinait ou se la
        # faisait transmettre. Elle vit désormais hors du répertoire servi
        # et ne sort que par la vue `…/photo/`, qui vérifie l'académie du
        # demandeur.
        storage=private_storage,
        help_text="Photo facultative. Donnée de mineur : stockage privé, accès restreint.",
    )

    # ── Étape 2 : origines et langues ───────────────────────────────────
    family_origin_country = models.CharField(max_length=120, blank=True)
    home_main_language = models.CharField(max_length=120, blank=True)
    other_languages = models.CharField(max_length=255, blank=True)
    french_speakers_with_child = models.CharField(
        max_length=255, blank=True,
        help_text="Personnes parlant français avec l'enfant.",
    )
    french_speakers_relation = models.CharField(max_length=255, blank=True)

    # ── Étape 3 : niveau actuel de français ─────────────────────────────
    french_levels = models.JSONField(
        default=list, blank=True,
        help_text="Liste de valeurs FRENCH_LEVEL_CHOICES (sélections cumulables).",
    )
    french_level_notes = models.TextField(blank=True)

    # ── Étape 4 : expérience antérieure ─────────────────────────────────
    previous_courses = models.BooleanField(default=False)
    bilingual_school = models.BooleanField(default=False)
    stay_in_francophone_country = models.BooleanField(default=False)
    certifications_obtained = models.CharField(max_length=255, blank=True)
    experience_duration = models.CharField(max_length=120, blank=True)
    experience_comments = models.TextField(blank=True)

    # ── Étape 5 : objectifs des parents ─────────────────────────────────
    parent_goals = models.JSONField(
        default=list, blank=True,
        help_text="Liste de valeurs PARENT_GOAL_CHOICES.",
    )
    parent_goals_other = models.CharField(max_length=255, blank=True)

    # ── Étape 6 : parent / responsable 1 (obligatoire) ──────────────────
    parent1_last_name = models.CharField(max_length=120)
    parent1_first_name = models.CharField(max_length=120)
    parent1_relation = models.CharField(max_length=80, blank=True)
    parent1_phone = models.CharField(max_length=30)
    parent1_whatsapp = models.CharField(max_length=30, blank=True)
    parent1_email = models.EmailField()
    parent1_address = models.CharField(max_length=255, blank=True)
    parent1_city = models.CharField(max_length=120, blank=True)
    parent1_state_province = models.CharField(max_length=120, blank=True)
    parent1_country = models.CharField(max_length=100, blank=True)
    parent1_postal_code = models.CharField(max_length=20, blank=True)
    parent1_preferred_language = models.CharField(
        max_length=5, choices=[('fr', 'Français'), ('en', 'English')], default='en',
    )
    parent1_timezone = models.CharField(max_length=64, blank=True)

    # ── Étape 7 : parent / responsable 2 (facultatif) ───────────────────
    parent2_last_name = models.CharField(max_length=120, blank=True)
    parent2_first_name = models.CharField(max_length=120, blank=True)
    parent2_relation = models.CharField(max_length=80, blank=True)
    parent2_phone = models.CharField(max_length=30, blank=True)
    parent2_whatsapp = models.CharField(max_length=30, blank=True)
    parent2_email = models.EmailField(blank=True)
    parent2_address = models.CharField(max_length=255, blank=True)
    parent2_city = models.CharField(max_length=120, blank=True)
    parent2_state_province = models.CharField(max_length=120, blank=True)
    parent2_country = models.CharField(max_length=100, blank=True)
    parent2_postal_code = models.CharField(max_length=20, blank=True)
    parent2_preferred_language = models.CharField(
        max_length=5, choices=[('fr', 'Français'), ('en', 'English')], blank=True,
    )
    parent2_timezone = models.CharField(max_length=64, blank=True)

    # ── Étape 8 : contact d'urgence ─────────────────────────────────────
    emergency_name = models.CharField(max_length=160, blank=True)
    emergency_relation = models.CharField(max_length=80, blank=True)
    emergency_phone = models.CharField(max_length=30, blank=True)
    emergency_email = models.EmailField(blank=True)
    emergency_contact_authorized = models.BooleanField(default=False)

    # ── Étape 9 : disponibilités ────────────────────────────────────────
    # Stockage NORMALISÉ : jours ISO (1=lundi … 7=dimanche) et créneaux en
    # heure locale déclarée + fuseau, pour pouvoir recalculer l'affichage
    # dans le fuseau de chaque utilisateur.
    available_days = models.JSONField(
        default=list, blank=True, help_text="Jours ISO disponibles (1=lundi … 7=dimanche).",
    )
    available_time_slots = models.JSONField(
        default=list, blank=True,
        help_text="Créneaux [{'start': 'HH:MM', 'end': 'HH:MM'}] en heure locale famille.",
    )
    family_timezone = models.CharField(
        max_length=64, blank=True,
        help_text="Fuseau de référence des créneaux ci-dessus (IANA, ex: America/New_York).",
    )
    weekday_or_weekend = models.CharField(
        max_length=20, blank=True,
        choices=[('weekday', 'Semaine'), ('weekend', 'Week-end'), ('both', 'Les deux')],
    )
    availability_notes = models.TextField(blank=True)

    # ── Étape 10 : équipement ───────────────────────────────────────────
    has_computer = models.BooleanField(default=False)
    has_tablet = models.BooleanField(default=False)
    has_camera = models.BooleanField(default=False)
    has_microphone = models.BooleanField(default=False)
    has_headset = models.BooleanField(default=False)
    has_internet = models.BooleanField(default=False)
    can_print = models.BooleanField(default=False)
    equipment_notes = models.TextField(blank=True)

    # ── Étape 11 : besoins particuliers (CONFIDENTIEL) ──────────────────
    # Donnée sensible de mineur : exposée uniquement aux profils habilités
    # (voir FHAApplicationAdminSerializer / permissions renforcées).
    special_needs = models.TextField(
        blank=True,
        help_text="CONFIDENTIEL — adaptations pédagogiques, difficultés, besoins de soutien.",
    )

    # ── Étape 12 : consentements (datés et versionnés) ──────────────────
    consent_rules = models.BooleanField(default=False)
    consent_zoom = models.BooleanField(default=False)
    consent_privacy = models.BooleanField(default=False)
    consent_data_processing = models.BooleanField(default=False)
    consent_photo_video = models.BooleanField(default=False)
    consent_communications = models.BooleanField(default=False)
    consent_payment_policy = models.BooleanField(default=False)
    consent_annual_commitment = models.BooleanField(default=False)
    consent_parental_authorization = models.BooleanField(default=False)
    consents_version = models.CharField(
        max_length=20, default='1.0',
        help_text="Version des textes de consentement acceptés (traçabilité).",
    )
    consents_accepted_at = models.DateTimeField(null=True, blank=True)

    # ── Suivi ───────────────────────────────────────────────────────────
    recommended_group = models.CharField(
        max_length=24, choices=GROUP_CHOICES, blank=True,
        help_text="Groupe recommandé après test de placement.",
    )
    submitted_ip = models.GenericIPAddressField(null=True, blank=True)

    # ── P1 : fiche PDF produite à la soumission ──────────────────────────
    # Chemin RELATIF dans le stockage privé. Jamais dans MEDIA_ROOT : ce
    # document contient l'adresse, le téléphone et les besoins particuliers
    # d'un mineur. Servi uniquement par une vue authentifiée.
    sheet_path = models.CharField(max_length=255, blank=True)
    sheet_sha256 = models.CharField(max_length=64, blank=True)
    sheet_size = models.PositiveIntegerField(default=0)
    sheet_generated_at = models.DateTimeField(null=True, blank=True)
    #: Numéro de version de la fiche. Une régénération après correction ne
    #: doit pas laisser croire que la famille a reçu CE fichier-là.
    sheet_version = models.PositiveSmallIntegerField(default=0)
    sheet_error = models.TextField(
        blank=True,
        help_text="Cause EXACTE d'un échec de production de la fiche.",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Fiche d'inscription FEBA FHA"
        verbose_name_plural = "Fiches d'inscription FEBA FHA"
        ordering = ['-created_at']
        constraints = [
            # Prévention des doublons, telle que spécifiée : un même enfant
            # ne peut pas être soumis deux fois par le même parent DANS LA
            # MÊME ENTITÉ. L'entité fait partie de la clé pour ne jamais
            # provoquer de collision entre FEBA et FEBA FHA.
            models.UniqueConstraint(
                fields=[
                    'entity', 'parent1_email', 'child_first_name',
                    'child_last_name', 'child_birth_date',
                ],
                name='uniq_fha_application_child_per_parent',
            ),
        ]

    def __str__(self):
        return f"{self.reference or '(sans réf.)'} — {self.child_first_name} {self.child_last_name}"

    @property
    def child_age(self):
        """Âge calculé à partir de la date de naissance (jamais saisi)."""
        if not self.child_birth_date:
            return None
        today = timezone.localdate()
        years = today.year - self.child_birth_date.year
        if (today.month, today.day) < (self.child_birth_date.month, self.child_birth_date.day):
            years -= 1
        return years

    @property
    def suggested_group(self):
        """
        Groupe suggéré d'après l'âge seul. Le placement DÉFINITIF dépend
        aussi du test de placement — ce n'est qu'une indication.
        """
        age = self.child_age
        if age is None:
            return ''
        if 6 <= age <= 9:
            return self.GROUP_JUNIOR_ROOTS
        if 10 <= age <= 15:
            return self.GROUP_FRENCH_EXPLORERS
        if 16 <= age <= 17:
            return self.GROUP_FRENCH_AMBASSADORS
        return ''

    def generate_reference(self):
        """
        Numéro de dossier unique par entité et par année civile :
        « FHA-2026-0001 ». Calculé à partir du compteur de l'entité pour ne
        jamais entrer en collision avec la numérotation FEBA.
        """
        year = timezone.localdate().year
        prefix = (self.entity.matricule_prefix or 'FHA').upper()
        base = f"{prefix}-{year}-"
        last = (
            FHAEnrollmentApplication.objects
            .filter(entity=self.entity, reference__startswith=base)
            .order_by('-reference').values_list('reference', flat=True).first()
        )
        seq = 1
        if last:
            try:
                seq = int(last.rsplit('-', 1)[1]) + 1
            except (IndexError, ValueError):
                seq = FHAEnrollmentApplication.objects.filter(entity=self.entity).count() + 1
        return f"{base}{seq:04d}"

    def save(self, *args, **kwargs):
        if not self.reference:
            self.reference = self.generate_reference()
        super().save(*args, **kwargs)

    # ── Fiche PDF ────────────────────────────────────────────────────────

    @property
    def has_sheet(self):
        import os

        from apps.website.private_storage import fha_sheet_root

        return bool(self.sheet_path) and os.path.exists(
            os.path.join(fha_sheet_root(), self.sheet_path)
        )

    @property
    def sheet_absolute_path(self):
        import os

        from apps.website.private_storage import fha_sheet_root

        if not self.sheet_path:
            return None
        return os.path.join(fha_sheet_root(), self.sheet_path)

    def store_sheet(self, content):
        """
        Écrit la fiche dans le stockage privé et enregistre son empreinte.

        L'ancienne version n'est PAS supprimée : une copie a peut-être déjà
        été envoyée par e-mail, et l'historique doit permettre de dire quel
        fichier la famille détient.
        """
        import hashlib
        import os

        from apps.website.private_storage import fha_sheet_root

        self.sheet_version += 1
        relative = os.path.join(
            str(self.entity_id),
            f"{self.reference}-v{self.sheet_version}.pdf",
        )
        absolute = os.path.join(fha_sheet_root(), relative)
        os.makedirs(os.path.dirname(absolute), exist_ok=True)
        with open(absolute, "wb") as handle:
            handle.write(content)
        # 0600 : les permissions par défaut d'un serveur partagé sont
        # souvent lisibles par tous les comptes de la machine.
        try:
            os.chmod(absolute, 0o600)
        except OSError:  # pragma: no cover — dépend du système de fichiers
            pass

        self.sheet_path = relative
        self.sheet_sha256 = hashlib.sha256(content).hexdigest()
        self.sheet_size = len(content)
        self.sheet_generated_at = timezone.now()
        self.sheet_error = ""
        return relative


class FHAApplicationStatusHistory(models.Model):
    """
    Historique des changements d'état d'un dossier FHA.

    Exigence de traçabilité du parcours d'admission : qui a changé quoi,
    quand, pourquoi. Aucune ligne n'est modifiée ni supprimée.
    """
    application = models.ForeignKey(
        FHAEnrollmentApplication, on_delete=models.CASCADE, related_name='status_history',
    )
    from_status = models.CharField(max_length=24, blank=True)
    to_status = models.CharField(max_length=24)
    changed_by = models.ForeignKey(
        'accounts.CustomUser', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='fha_status_changes',
    )
    reason = models.CharField(max_length=255, blank=True)
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Changement d'état de dossier FHA"
        verbose_name_plural = "Changements d'état de dossier FHA"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.application_id} : {self.from_status or '—'} → {self.to_status}"


class FHAPlacementTestRequest(models.Model):
    """
    Demande de réservation d'un test de placement FEBA FHA.

    PARCOURS DISTINCT DE L'INSCRIPTION (P3)
    ---------------------------------------
    « Réserver un test de placement » et « Inscrire mon enfant » ouvraient
    le même formulaire. Ce sont pourtant deux moments différents du
    parcours : le test précède l'admission, il ne l'engage pas.

    Une demande de test NE CRÉE PAS d'inscription confirmée. Elle peut
    être rattachée à une fiche d'inscription (`application`) lorsque la
    famille poursuit le parcours.

    Formulaire volontairement COURT : le document de cadrage demande une
    réservation en quelques champs, pas une fiche complète.
    """
    STATUS_CHOICES = [
        ('requested', 'Demande reçue'),
        ('scheduled', 'Créneau confirmé'),
        ('reminded', 'Rappel envoyé'),
        ('completed', 'Test effectué'),
        ('no_show', 'Absence'),
        ('rescheduled', 'Reprogrammé'),
        ('cancelled', 'Annulé'),
    ]

    # Niveau estimé PAR LE PARENT (le niveau réel sort du test).
    ESTIMATED_LEVEL_CHOICES = [
        ('none', "Ne comprend pas le français"),
        ('few_words', "Comprend quelques mots"),
        ('understands', "Comprend mais répond en anglais"),
        ('speaks_a_little', "Parle un peu"),
        ('speaks_well', "Parle bien"),
        ('unknown', "Je ne sais pas"),
    ]

    entity = models.ForeignKey(
        'schools.School', on_delete=models.PROTECT,
        related_name='fha_placement_requests',
        help_text="Toujours FEBA_FHA. Déterminé par la route, jamais par le client.",
    )
    reference = models.CharField(
        max_length=24, unique=True, blank=True,
        help_text="Numéro de dossier de test (ex: FHA-TEST-2026-0001).",
    )
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default='requested')

    # ── Enfant ──────────────────────────────────────────────────────────
    child_first_name = models.CharField(max_length=120)
    child_last_name = models.CharField(max_length=120)
    child_birth_date = models.DateField()
    child_country = models.CharField(max_length=100, blank=True)
    child_state_province = models.CharField(max_length=120, blank=True)

    # ── Parent ──────────────────────────────────────────────────────────
    parent_first_name = models.CharField(max_length=120)
    parent_last_name = models.CharField(max_length=120)
    parent_email = models.EmailField()
    parent_phone = models.CharField(max_length=30)
    parent_whatsapp = models.CharField(max_length=30, blank=True)
    parent_timezone = models.CharField(
        max_length=64, blank=True,
        help_text="Fuseau IANA de la famille : les créneaux lui sont affichés dans cette heure locale.",
    )
    preferred_language = models.CharField(
        max_length=5, choices=[('fr', 'Français'), ('en', 'English')], default='en',
    )

    # ── Niveau et expérience estimés ────────────────────────────────────
    estimated_level = models.CharField(
        max_length=20, choices=ESTIMATED_LEVEL_CHOICES, default='unknown',
    )
    previous_experience = models.TextField(blank=True)

    # ── Créneau souhaité ────────────────────────────────────────────────
    # Stockage NORMALISÉ : date + heure locale déclarée + fuseau, pour
    # pouvoir recalculer l'affichage dans le fuseau de chaque utilisateur.
    preferred_date = models.DateField(null=True, blank=True)
    preferred_time = models.TimeField(null=True, blank=True)
    alternate_date = models.DateField(null=True, blank=True)
    alternate_time = models.TimeField(null=True, blank=True)

    # Créneau réellement confirmé par l'administration (UTC).
    scheduled_at = models.DateTimeField(
        null=True, blank=True,
        help_text="Créneau confirmé, stocké en UTC.",
    )
    meeting_room = models.ForeignKey(
        'virtualclass.VirtualRoom', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='placement_tests',
        help_text="Salle de visioconférence privée du test.",
    )

    special_needs = models.TextField(
        blank=True, help_text="CONFIDENTIEL — besoin particulier signalé par la famille.",
    )
    consent_video = models.BooleanField(
        default=False, help_text="Consentement à la participation en visioconférence.",
    )
    comment = models.TextField(blank=True)

    # Rattachement éventuel à une fiche d'inscription complète.
    application = models.ForeignKey(
        FHAEnrollmentApplication, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='placement_tests',
        help_text="Fiche d'inscription associée, si la famille a poursuivi le parcours.",
    )

    submitted_ip = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Demande de test de placement FEBA FHA"
        verbose_name_plural = "Demandes de test de placement FEBA FHA"
        ordering = ['-created_at']
        constraints = [
            # Un même enfant ne peut pas être réservé deux fois par le même
            # parent DANS LA MÊME ENTITÉ tant qu'aucun test n'a eu lieu.
            models.UniqueConstraint(
                fields=['entity', 'parent_email', 'child_first_name',
                        'child_last_name', 'child_birth_date'],
                condition=models.Q(status__in=['requested', 'scheduled', 'reminded']),
                name='uniq_active_placement_request_per_child',
            ),
        ]

    def __str__(self):
        return f"{self.reference or '(sans réf.)'} — {self.child_first_name} {self.child_last_name}"

    @property
    def child_age(self):
        if not self.child_birth_date:
            return None
        today = timezone.localdate()
        years = today.year - self.child_birth_date.year
        if (today.month, today.day) < (self.child_birth_date.month, self.child_birth_date.day):
            years -= 1
        return years

    @property
    def suggested_group(self):
        """Groupe suggéré d'après l'âge. Le test affine le placement réel."""
        age = self.child_age
        if age is None:
            return ''
        if 6 <= age <= 9:
            return FHAEnrollmentApplication.GROUP_JUNIOR_ROOTS
        if 10 <= age <= 15:
            return FHAEnrollmentApplication.GROUP_FRENCH_EXPLORERS
        if 16 <= age <= 17:
            return FHAEnrollmentApplication.GROUP_FRENCH_AMBASSADORS
        return ''

    def generate_reference(self):
        """Numérotation SÉPARÉE de celle des inscriptions : FHA-TEST-AAAA-NNNN."""
        year = timezone.localdate().year
        prefix = (self.entity.matricule_prefix or 'FHA').upper()
        base = f"{prefix}-TEST-{year}-"
        last = (
            FHAPlacementTestRequest.objects
            .filter(entity=self.entity, reference__startswith=base)
            .order_by('-reference').values_list('reference', flat=True).first()
        )
        seq = 1
        if last:
            try:
                seq = int(last.rsplit('-', 1)[1]) + 1
            except (IndexError, ValueError):
                seq = FHAPlacementTestRequest.objects.filter(entity=self.entity).count() + 1
        return f"{base}{seq:04d}"

    def save(self, *args, **kwargs):
        if not self.reference:
            self.reference = self.generate_reference()
        super().save(*args, **kwargs)


class FHAPlacementTestResult(models.Model):
    """
    Grille d'évaluation interne du test de placement.

    Les six compétences sont celles du cahier de structure. Les notes sont
    volontairement sur une échelle courte (0-4) : il s'agit d'un
    positionnement, pas d'une note scolaire — la logique de moyennes FEBA
    ne s'applique pas ici.
    """
    SCALE = [(0, "Non évalué"), (1, "Débutant"), (2, "En cours"),
             (3, "Acquis"), (4, "Avancé")]

    LEVEL_CHOICES = [
        ('beginner', 'Débutant'),
        ('intermediate', 'Intermédiaire'),
        ('advanced', 'Avancé'),
    ]

    request = models.OneToOneField(
        FHAPlacementTestRequest, on_delete=models.CASCADE, related_name='result',
    )
    listening = models.PositiveSmallIntegerField(choices=SCALE, default=0)
    speaking = models.PositiveSmallIntegerField(choices=SCALE, default=0)
    vocabulary = models.PositiveSmallIntegerField(choices=SCALE, default=0)
    reading = models.PositiveSmallIntegerField(choices=SCALE, default=0)
    writing = models.PositiveSmallIntegerField(choices=SCALE, default=0)
    confidence = models.PositiveSmallIntegerField(choices=SCALE, default=0)

    recommended_group = models.CharField(
        max_length=24, choices=FHAEnrollmentApplication.GROUP_CHOICES, blank=True,
    )
    starting_level = models.CharField(max_length=16, choices=LEVEL_CHOICES, blank=True)
    priority_objectives = models.TextField(blank=True)
    assessor_notes = models.TextField(blank=True)

    assessed_by = models.ForeignKey(
        'accounts.CustomUser', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='fha_assessments',
    )
    assessed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Résultat de test de placement FHA"
        verbose_name_plural = "Résultats de test de placement FHA"

    def __str__(self):
        return f"Résultat {self.request.reference} — {self.get_starting_level_display() or 'niveau à définir'}"
