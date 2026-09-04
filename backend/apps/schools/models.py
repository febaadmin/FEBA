import logging
logger = logging.getLogger("apps")
from django.db import models

from apps.core.currency import (
    CURRENCY_CHOICES, DEFAULT_CURRENCY, get_currency,
)
from django.utils.text import slugify


class School(models.Model):
    """
    Établissement scolaire — racine "tenant" de la plateforme SaaS.

    Chaque établissement est un client isolé : ses données (élèves,
    enseignants, classes, notes, paiements...) ne sont jamais visibles
    par un autre établissement. Voir apps/core/tenancy.py pour les
    règles d'isolation appliquées au niveau API.
    """
    PLAN_CHOICES = [
        ("trial", "Essai gratuit"),
        ("standard", "Standard"),
        ("premium", "Premium"),
    ]

    # Codes internes STABLES des entités. La logique métier s'appuie
    # exclusivement sur ces codes, jamais sur le nom affiché (qui peut être
    # renommé par l'administration sans casser les règles d'accès).
    CODE_FEBA = "FEBA"
    CODE_FEBA_FHA = "FEBA_FHA"

    ENTITY_TYPE_CHOICES = [
        ("campus", "École présentielle"),
        ("online", "Académie en ligne"),
    ]

    name = models.CharField(max_length=200)
    legal_name = models.CharField(
        max_length=250, blank=True,
        help_text="Dénomination légale complète (documents officiels, contrats, factures).",
    )
    code = models.CharField(
        max_length=32, unique=True, null=True, blank=True,
        help_text=(
            "Identifiant interne STABLE de l'entité (ex: FEBA, FEBA_FHA). "
            "Utilisé par la logique métier — ne jamais le dériver du nom affiché."
        ),
    )
    entity_type = models.CharField(
        max_length=20, choices=ENTITY_TYPE_CHOICES, default="campus",
        help_text="Détermine les fonctionnalités par défaut (présentiel vs académie en ligne).",
    )
    slug = models.SlugField(
        max_length=80, unique=True, blank=True,
        help_text="Identifiant court unique (sous-domaine / sélection tenant). Généré automatiquement si vide.",
    )
    address = models.TextField()
    city = models.CharField(max_length=100, default="Cotonou")
    country = models.CharField(max_length=100, default="Bénin")
    phone = models.CharField(max_length=20, blank=True)
    whatsapp = models.CharField(
        max_length=30, blank=True,
        help_text="Numéro WhatsApp au format international. Vide = bouton WhatsApp masqué.",
    )
    email = models.EmailField(blank=True)
    logo = models.ImageField(upload_to="school/", null=True, blank=True)
    description = models.TextField(blank=True)

    # --- Localisation / internationalisation de l'entité ------------------
    # FEBA FHA cible des familles aux États-Unis et au Canada : la devise, le
    # fuseau et la langue par défaut ne peuvent pas être ceux de FEBA Cotonou.
    timezone = models.CharField(
        max_length=64, default="Africa/Porto-Novo",
        help_text="Fuseau horaire de référence administrative (ex: America/New_York pour FEBA FHA).",
    )
    # ── Devise (P0) ───────────────────────────────────────────────────
    # `currency_code` est la SOURCE D'AUTORITÉ. Le symbole, le nom et le
    # nombre de décimales en découlent (voir apps/core/currency.py) et ne
    # sont volontairement PAS stockés : une colonne « symbole » pourrait
    # afficher « FCFA » sur une académie dont le code vaut « USD », ce qui
    # est exactement le défaut que ce champ existe pour empêcher.
    currency_code = models.CharField(
        max_length=3, default=DEFAULT_CURRENCY, choices=CURRENCY_CHOICES,
        verbose_name="Devise",
        help_text=(
            "Devise de TOUTES les opérations financières de cette académie : "
            "tarifs, factures, paiements, reçus, remboursements, statistiques "
            "et exports. FEBA facture en XOF, FEBA FHA en USD."
        ),
    )
    # Le format d'écriture des nombres peut se régler indépendamment de la
    # devise (une académie francophone payant en dollars écrit « 1 250,00 »).
    currency_locale = models.CharField(
        max_length=10, blank=True, default="",
        help_text="Format d'écriture des montants (ex. fr-BJ, en-US). Vide = celui de la devise.",
    )
    default_language = models.CharField(
        max_length=5, choices=[("fr", "Français"), ("en", "English")], default="fr",
        help_text="Langue par défaut des documents et notifications de l'entité.",
    )
    # Réglages libres administrables (tarifs non validés, dates de rentrée,
    # politique de remboursement...). Voir DEFAULT_FEATURES pour les
    # fonctionnalités, stockées sous la clé « features ».
    settings = models.JSONField(
        default=dict, blank=True,
        help_text="Réglages administrables de l'entité (features, textes, politiques).",
    )
    # Préfixe court des matricules (ex: FEBA → FEBA-26-0001).
    # Vide = dérivé automatiquement du slug de l'établissement.
    matricule_prefix = models.CharField(
        max_length=8, blank=True, default="",
        help_text="Préfixe court des matricules (ex: FEBA). Vide = dérivé du slug.",
    )

    # --- Champs "tenant" (gestion commerciale SaaS) -----------------------
    is_active = models.BooleanField(
        default=True,
        help_text="Un établissement désactivé ne peut plus se connecter (suspension d'abonnement, impayé...).",
    )
    plan = models.CharField(max_length=20, choices=PLAN_CHOICES, default="trial")
    max_students = models.PositiveIntegerField(
        default=0, help_text="0 = illimité. Quota contractuel selon le plan souscrit.",
    )
    trial_ends_at = models.DateField(null=True, blank=True)
    subscription_notes = models.TextField(
        blank=True, help_text="Notes internes (équipe commerciale/support), non visibles par l'établissement.",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)

    class Meta:
        verbose_name = "École"

    # ── Matrice de fonctionnalités par entité ────────────────────────────
    # Chaque drapeau est vérifié CÔTÉ SERVEUR (voir apps/core/features.py).
    # Masquer un menu React ne suffit jamais : l'API doit refuser.
    FEATURE_FLAGS = [
        "virtual_classrooms",
        "video_conferencing",
        "placement_tests",
        "online_lessons",
        "online_assignments",
        "learning_library",
        "skill_progress",
        "certificates",
        "payments",
        "messaging",
        "schedules",
        "support_tickets",
        # Autorise les classes monolingues (francophone / anglophone).
        # Faith & Excellence Bilingual Academy est bilingue par
        # construction : c'est son identité, pas un réglage. FEBA French
        # Heritage Academy accueille au contraire des enfants de la
        # diaspora dont certains ne suivent qu'une langue.
        #
        # Porté par l'académie et non par la classe : sans cela, un
        # `language_track` posté ou une donnée corrompue suffirait à
        # rendre monolingue une classe de FEBA.
        "monolingual_classes",
    ]

    # Valeurs par défaut selon le type d'entité.
    # « campus » (FEBA Cotonou) : école présentielle — pas de salle virtuelle,
    # pas de visioconférence, pas de test de placement en ligne.
    DEFAULT_FEATURES = {
        "campus": {
            "virtual_classrooms": False,
            "video_conferencing": False,
            "placement_tests": False,
            "online_lessons": False,
            "online_assignments": False,
            "learning_library": False,
            "skill_progress": False,
            "certificates": False,
            "payments": True,
            "messaging": True,
            "schedules": True,
            "support_tickets": False,
            "monolingual_classes": False,
        },
        "online": {
            "virtual_classrooms": True,
            "video_conferencing": True,
            "placement_tests": True,
            "online_lessons": True,
            "online_assignments": True,
            "learning_library": True,
            "skill_progress": True,
            "certificates": True,
            "payments": True,
            "messaging": True,
            "schedules": True,
            "support_tickets": True,
            "monolingual_classes": True,
        },
    }

    @property
    def features(self):
        """
        Matrice effective des fonctionnalités : valeurs par défaut du type
        d'entité, surchargées par `settings['features']` (administrable).
        """
        base = dict(self.DEFAULT_FEATURES.get(self.entity_type, self.DEFAULT_FEATURES["campus"]))
        overrides = (self.settings or {}).get("features") or {}
        for key, value in overrides.items():
            if key in self.FEATURE_FLAGS:
                base[key] = bool(value)
        return base

    def has_feature(self, flag):
        """True si l'entité a le droit d'utiliser cette fonctionnalité."""
        return bool(self.features.get(flag, False))

    @property
    def is_online_academy(self):
        return self.entity_type == "online"

    @property
    def display_name(self):
        """Nom complet à utiliser dans les documents et titres de page."""
        return self.legal_name or self.name

    @property
    def short_name(self):
        """
        Nom court affichable — badges, colonnes de tableau, exports.

        « FEBA French Heritage Academy » ne tient pas dans une cellule de
        tableau : en mode « Toutes les Académies », chaque ligne doit porter
        une étiquette lisible sans élargir la colonne au point de masquer
        les données. Le nom complet reste disponible via `name`.

        Ordre de résolution : valeur administrable, puis code interne
        rendu lisible (FEBA_FHA → « FEBA FHA »), puis nom complet.
        """
        override = (self.settings or {}).get("short_name")
        if override:
            return str(override)
        if self.code:
            return self.code.replace("_", " ")
        return self.name

    # ── Devise : tout est dérivé du code, rien n'est dupliqué ──────────
    @property
    def currency(self):
        """Objet devise complet (symbole, décimales, règles de formatage)."""
        return get_currency(self.currency_code)

    @property
    def currency_symbol(self):
        return self.currency.symbol

    @property
    def currency_name(self):
        return self.currency.name

    @property
    def currency_decimal_places(self):
        return self.currency.decimal_places

    @property
    def effective_currency_locale(self):
        return self.currency_locale or self.currency.locale

    def format_amount(self, amount_minor, with_symbol=True):
        """Rend un montant dans la devise de CETTE académie."""
        return self.currency.format(amount_minor, with_symbol=with_symbol)

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.name)[:70] or "ecole"
            slug = base
            i = 1
            while School.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                i += 1
                slug = f"{base}-{i}"
            self.slug = slug
        super().save(*args, **kwargs)

    def is_over_quota(self):
        """True si l'établissement a dépassé son quota d'élèves actifs."""
        if not self.max_students:
            return False
        return self.students.filter(is_active=True).count() > self.max_students

    def get_active_logo_url(self, request=None):
        # Absence de branding actif = état normal (repli sur School.logo),
        # pas une erreur à journaliser.
        branding = self.branding_versions.filter(is_active=True).order_by("-uploaded_at").first()
        if branding and branding.logo:
            return branding.logo.url
        if self.logo:
            return self.logo.url
        return None


class SchoolBranding(models.Model):
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="branding_versions")
    logo = models.ImageField(upload_to="branding/", null=True, blank=True)
    is_active = models.BooleanField(default=False)
    label = models.CharField(max_length=100, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    uploaded_by = models.ForeignKey(
        "accounts.CustomUser", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="uploaded_brandings",
    )

    class Meta:
        verbose_name = "Version branding"
        ordering = ["-uploaded_at"]

    def __str__(self):
        status = "Active" if self.is_active else "Archive"
        return f"{self.school.name} [{status}]"

    def activate(self):
        SchoolBranding.objects.filter(school=self.school, is_active=True).update(is_active=False)
        self.is_active = True
        self.save(update_fields=["is_active"])

    @classmethod
    def get_active_logo_path(cls, school):
        # Absence de branding actif = état normal (repli sur School.logo puis
        # logo statique), pas une erreur à journaliser.
        b = cls.objects.filter(school=school, is_active=True).order_by("-uploaded_at").first()
        if b and b.logo:
            return b.logo.path
        if school.logo:
            return school.logo.path
        return None


class SchoolYear(models.Model):
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="years")
    name = models.CharField(max_length=20)
    start_date = models.DateField()
    end_date = models.DateField()
    is_current = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Année scolaire"
        ordering = ["-start_date"]
        # FIX v32 : pas deux années du même nom dans un établissement.
        # FIX v39 : au plus UNE année active (is_current=True) par
        # établissement — garantit au niveau base que la puce « Année active »
        # et le contenu filtré désignent toujours la même année.
        constraints = [
            models.UniqueConstraint(fields=["school", "name"], name="uniq_schoolyear_school_name"),
            models.UniqueConstraint(
                fields=["school"], condition=models.Q(is_current=True),
                name="uniq_current_year_per_school",
            ),
        ]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if self.is_current:
            SchoolYear.objects.filter(school=self.school, is_current=True).update(is_current=False)
        else:
            # FIX v41 — LA PREMIÈRE ANNÉE D'UNE ACADÉMIE EST ACTIVE.
            #
            # Sans cela, une académie pouvait avoir une année et AUCUNE
            # année active : l'administrateur crée l'entité, ajoute
            # « 2026-2027 », crée ses classes, et ne clique jamais sur
            # « Activer » — rien ne le lui demande. Toutes les listes
            # déroulantes de classes tombaient alors à zéro, en silence.
            #
            # DEUX GARDES, chacune indispensable :
            #
            #  1. `_state.adding` — uniquement à la CRÉATION. Une année qui
            #     existe déjà et qu'on enregistre à is_current=False est
            #     une année qu'on ferme DÉLIBÉRÉMENT (bouton « Clôturer »).
            #     La réactiver ici rendait la clôture impossible : on la
            #     fermait, elle se rouvrait dans le même appel.
            #  2. aucune autre année active — créer une seconde année ne
            #     doit pas déplacer l'année de travail sous les pieds de
            #     l'établissement.
            #
            # Une académie dont toutes les années sont closes n'est PAS
            # rattrapée ici, et c'est voulu : `academic_year.active_year()`
            # se replie alors sur l'année la plus récente pour l'affichage,
            # sans jamais rouvrir ce qu'un administrateur a fermé.
            if self._state.adding and not SchoolYear.objects.filter(
                school=self.school, is_current=True
            ).exists():
                self.is_current = True
        super().save(*args, **kwargs)


class Level(models.Model):
    CYCLE_CHOICES = [
        ("maternelle", "Maternelle"),
        ("primaire", "Primaire"),
        ("college", "Collège"),
        ("lycee", "Lycée"),
    ]
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="levels")
    name = models.CharField(max_length=50)
    order = models.PositiveIntegerField(default=0)
    cycle = models.CharField(max_length=20, choices=CYCLE_CHOICES, default="primaire")

    class Meta:
        verbose_name = "Niveau"
        ordering = ["order"]

    def __str__(self):
        return self.name

    def is_maternelle(self):
        return self.cycle == "maternelle"


class RoomType(models.Model):
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="room_types")
    name = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Type de salle"
        ordering = ["name"]
        unique_together = [["school", "name"]]

    def __str__(self):
        return self.name


class Room(models.Model):
    ROOM_TYPES = [
        ("classroom", "Salle de classe"),
        ("computer", "Salle informatique"),
        ("canteen", "Cantine"),
        ("library", "Bibliothèque"),
        ("sports", "Salle de sport"),
        ("dance", "Salle de danse"),
        ("admin", "Bureau administratif"),
        ("custom", "Type personnalisé"),
        ("other", "Autre"),
    ]
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="rooms")
    name = models.CharField(max_length=100)
    room_type = models.CharField(max_length=20, choices=ROOM_TYPES, default="classroom")
    custom_type_label = models.CharField(max_length=100, blank=True)
    room_type_obj = models.ForeignKey(
        RoomType, on_delete=models.SET_NULL, null=True, blank=True, related_name="rooms"
    )
    capacity = models.PositiveIntegerField(default=30)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Salle"
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.get_room_type_display()})"

    def get_display_type(self):
        if self.room_type_obj:
            return self.room_type_obj.name
        if self.room_type == "custom" and self.custom_type_label:
            return self.custom_type_label
        return self.get_room_type_display()


class OrganizationMembership(models.Model):
    """
    Appartenance d'un utilisateur à une entité (organisation).

    POURQUOI CE MODÈLE EN PLUS DE `CustomUser.school`
    --------------------------------------------------
    `CustomUser.school` reste la SOURCE DE VÉRITÉ du rattachement principal
    d'un utilisateur normal (admin, enseignant, parent, élève) : c'est ce
    champ que lit le filtrage de queryset, et le conserver évite de casser
    les règles d'isolation déjà éprouvées.

    `OrganizationMembership` ajoute ce que le champ simple ne peut pas
    exprimer :
      - le Super Administrateur, rattaché à PLUSIEURS entités ;
      - l'historique des affectations (qui a affecté qui, quand) ;
      - un statut (active / suspended / revoked) sans supprimer la ligne ;
      - un rôle porté par l'appartenance elle-même.

    Les deux restent cohérents : `sync_primary_membership()` est appelé à la
    sauvegarde de l'utilisateur pour refléter `user.school` dans une
    appartenance principale.
    """
    STATUS_CHOICES = [
        ("active", "Active"),
        ("suspended", "Suspendue"),
        ("revoked", "Révoquée"),
    ]

    user = models.ForeignKey(
        "accounts.CustomUser", on_delete=models.CASCADE, related_name="memberships",
    )
    organization = models.ForeignKey(
        School, on_delete=models.CASCADE, related_name="memberships",
    )
    role = models.CharField(
        max_length=12,
        help_text="Rôle porté par cette appartenance (mêmes valeurs que CustomUser.role).",
    )
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default="active")
    is_primary = models.BooleanField(
        default=False,
        help_text="Appartenance principale : entité par défaut à la connexion.",
    )
    created_by = models.ForeignKey(
        "accounts.CustomUser", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="memberships_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Appartenance à une entité"
        verbose_name_plural = "Appartenances aux entités"
        ordering = ["-is_primary", "-created_at"]
        constraints = [
            # Une seule appartenance par couple (utilisateur, entité) :
            # empêche les affectations en double / incohérentes.
            models.UniqueConstraint(
                fields=["user", "organization"], name="uniq_membership_user_org",
            ),
            # Au plus UNE appartenance principale par utilisateur.
            models.UniqueConstraint(
                fields=["user"], condition=models.Q(is_primary=True),
                name="uniq_primary_membership_per_user",
            ),
        ]

    def __str__(self):
        flag = " (principale)" if self.is_primary else ""
        return f"{self.user_id} → {self.organization.name} [{self.role}]{flag}"

    @property
    def is_usable(self):
        return self.status == "active" and self.organization.is_active


class EntitySwitchLog(models.Model):
    """
    Journal d'audit des changements d'entité active du Super Administrateur.

    Exigence de traçabilité : tout basculement entre FEBA et FEBA FHA est
    enregistré (qui, depuis quelle entité, vers laquelle, quand, depuis
    quelle IP).
    """
    user = models.ForeignKey(
        "accounts.CustomUser", on_delete=models.CASCADE, related_name="entity_switches",
    )
    from_organization = models.ForeignKey(
        School, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="switches_from",
    )
    to_organization = models.ForeignKey(
        School, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="switches_to",
        help_text="NULL = bascule vers le mode « Toutes les entités ».",
    )
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Changement d'entité active"
        verbose_name_plural = "Changements d'entité active"
        ordering = ["-created_at"]

    def __str__(self):
        src = self.from_organization.name if self.from_organization else "toutes"
        dst = self.to_organization.name if self.to_organization else "toutes"
        return f"{self.user_id} : {src} → {dst} ({self.created_at:%Y-%m-%d %H:%M})"
