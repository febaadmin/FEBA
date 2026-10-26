"""
apps/documents/models.py — Historique et immuabilité des documents officiels

CE QUE CE MODÈLE PROTÈGE
------------------------
Un diplôme n'est pas un fichier : c'est une affirmation de
l'établissement, opposable, qui circule hors de l'application. Trois
conséquences en découlent, et elles structurent tout ce fichier.

  1. **Un document émis ne se modifie pas.** On ne corrige pas un diplôme
     déjà remis ; on en émet un nouveau, et on marque le précédent comme
     remplacé. L'ancien reste dans l'historique — c'est lui que quelqu'un
     détient peut-être encore.

  2. **Un document émis se prouve.** L'empreinte SHA-256 du PDF et celle
     du gabarit utilisé sont conservées. Des années plus tard, elles
     permettent de dire si un fichier présenté est bien celui qui a été
     délivré, et avec quelle mise en page.

  3. **Un document ne se devine pas.** Le numéro est séquentiel par
     académie et par année, et l'accès est vérifié sur l'élève, jamais sur
     l'identifiant fourni dans l'URL.

STOCKAGE HORS DU RÉPERTOIRE PUBLIC
----------------------------------
Les fichiers vont dans `PRIVATE_MEDIA_ROOT`, qui n'est pas servi par le
serveur web. Un diplôme dans `/media/` est accessible à quiconque devine
son nom — et un nom de fichier n'est pas un secret.
"""
import hashlib
import os

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.utils import timezone


def private_documents_root():
    """Racine de stockage, hors du répertoire servi publiquement."""
    return getattr(
        settings, "PRIVATE_MEDIA_ROOT",
        os.path.join(settings.BASE_DIR, "private_media"),
    )


class DocumentNumberSequence(models.Model):
    """
    Compteur par académie, type de document et année.

    Une table dédiée plutôt qu'un `count() + 1` : deux émissions
    simultanées produiraient le même numéro, et deux diplômes portant le
    même numéro ne sont plus des preuves.
    """

    academy = models.ForeignKey(
        "schools.School", on_delete=models.CASCADE, related_name="document_sequences",
    )
    template_id = models.CharField(max_length=50)
    year = models.PositiveIntegerField()
    last_value = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = "Séquence de numérotation"
        constraints = [
            models.UniqueConstraint(
                fields=["academy", "template_id", "year"], name="uniq_document_sequence",
            ),
        ]

    @classmethod
    def next_number(cls, academy, template_id, year=None):
        year = year or timezone.now().year
        with transaction.atomic():
            # `select_for_update` : le verrou est pris en base, pas dans le
            # processus. Deux instances du serveur n'ont aucune mémoire
            # commune, un verrou applicatif ne les coordonnerait pas.
            sequence, _ = cls.objects.select_for_update().get_or_create(
                academy=academy, template_id=template_id, year=year,
            )
            sequence.last_value += 1
            sequence.save(update_fields=["last_value"])
        # P0 — le préfixe vient de l'identité de l'académie. « FEBA » en
        # repli numérotait les diplômes de FEBA French Heritage Academy
        # sous le préfixe de l'école de Cotonou.
        from apps.schools.branding import get_branding

        prefix = (get_branding(academy).document_prefix or "DOC").replace("_", "-")
        kind = "DIP" if "diploma" in template_id else "CER"
        return f"{prefix}-{kind}-{year}-{sequence.last_value:04d}"


class GeneratedDocument(models.Model):
    """Un document officiel produit pour un élève."""

    DRAFT = "draft"
    TO_VALIDATE = "to_validate"
    VALIDATED = "validated"
    ISSUED = "issued"
    REVOKED = "revoked"
    REPLACED = "replaced"

    STATUS_CHOICES = [
        (DRAFT, "Brouillon"),
        (TO_VALIDATE, "À valider"),
        (VALIDATED, "Validé"),
        (ISSUED, "Émis"),
        (REVOKED, "Révoqué"),
        (REPLACED, "Remplacé"),
    ]

    #: États dans lesquels le document est figé. Toute modification de
    #: contenu y est refusée : le fichier est peut-être déjà imprimé.
    FROZEN_STATUSES = {ISSUED, REVOKED, REPLACED}

    #: Transitions autorisées. Un dictionnaire explicite plutôt qu'une
    #: suite de `if` : ce qui n'y figure pas est interdit, et se lit.
    ALLOWED_TRANSITIONS = {
        DRAFT: {TO_VALIDATE, VALIDATED},
        TO_VALIDATE: {DRAFT, VALIDATED},
        VALIDATED: {DRAFT, ISSUED},
        ISSUED: {REVOKED, REPLACED},
        REVOKED: set(),
        REPLACED: set(),
    }

    academy = models.ForeignKey(
        "schools.School", on_delete=models.PROTECT, related_name="generated_documents",
    )
    student = models.ForeignKey(
        "students.Student", on_delete=models.PROTECT, related_name="official_documents",
    )
    school_year = models.ForeignKey(
        "schools.SchoolYear", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="generated_documents",
    )

    template_id = models.CharField(max_length=50)
    template_version = models.PositiveIntegerField(default=1)
    template_fingerprint = models.CharField(
        max_length=64, blank=True,
        help_text="Empreinte du gabarit (coordonnées comprises) au moment du rendu.",
    )
    background_sha256 = models.CharField(
        max_length=64, blank=True,
        help_text="Empreinte du fond verrouillé réellement utilisé.",
    )

    number = models.CharField(
        max_length=40, blank=True, db_index=True,
        help_text="Numéro officiel, attribué à l'émission uniquement.",
    )
    values = models.JSONField(
        default=dict, blank=True,
        help_text="Champs variables rendus. Conservés pour pouvoir rejouer le document.",
    )

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=DRAFT)
    file_path = models.CharField(
        max_length=500, blank=True,
        help_text="Chemin RELATIF dans le stockage privé. Jamais une URL publique.",
    )
    file_sha256 = models.CharField(max_length=64, blank=True)
    file_size = models.PositiveIntegerField(default=0)

    #: Version du gabarit TÉLÉVERSÉ qui a produit ce document (vide pour
    #: un gabarit intégré). PROTECT : une version qui a servi ne peut pas
    #: disparaître, sinon le document ne dirait plus d'où il vient.
    academy_template = models.ForeignKey(
        "documents.AcademyDocumentTemplate", on_delete=models.PROTECT,
        null=True, blank=True, related_name="documents",
    )

    replaces = models.ForeignKey(
        "self", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="replaced_by",
        help_text="Document que celui-ci remplace. L'ancien reste consultable.",
    )
    revocation_reason = models.CharField(max_length=255, blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="documents_created",
    )
    validated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="documents_validated",
    )
    issued_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="documents_issued",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    validated_at = models.DateTimeField(null=True, blank=True)
    issued_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Document officiel"
        verbose_name_plural = "Documents officiels"
        ordering = ["-created_at"]
        constraints = [
            # Un numéro ne peut désigner qu'un document. Contrainte
            # partielle : les brouillons n'ont pas encore de numéro, et
            # plusieurs chaînes vides ne sont pas des doublons.
            models.UniqueConstraint(
                fields=["number"], name="uniq_document_number",
                condition=~models.Q(number=""),
            ),
        ]
        indexes = [
            models.Index(fields=["academy", "status"]),
            models.Index(fields=["student", "template_id"]),
        ]

    def __str__(self):
        return f"{self.number or '(sans numéro)'} — {self.student} — {self.get_status_display()}"

    # ── Fichier ───────────────────────────────────────────────────────

    @property
    def absolute_path(self):
        if not self.file_path:
            return None
        return os.path.join(private_documents_root(), self.file_path)

    @property
    def is_frozen(self):
        return self.status in self.FROZEN_STATUSES

    def store_pdf(self, content):
        """
        Écrit le PDF dans le stockage privé et enregistre son empreinte.

        Refusé sur un document figé : le fichier correspondant est
        peut-être déjà entre les mains d'un élève.
        """
        if self.is_frozen:
            raise ValidationError(
                f"Ce document est « {self.get_status_display()} » : son fichier "
                f"ne peut plus changer. Émettez un remplaçant — l'ancien reste "
                f"dans l'historique, car quelqu'un le détient peut-être encore."
            )

        relative = os.path.join(
            str(self.academy_id), self.template_id,
            f"{self.pk or 'draft'}-{timezone.now():%Y%m%d%H%M%S}.pdf",
        )
        absolute = os.path.join(private_documents_root(), relative)
        os.makedirs(os.path.dirname(absolute), exist_ok=True)
        with open(absolute, "wb") as handle:
            handle.write(content)
        # 0600 : le fichier ne concerne que le compte qui fait tourner le
        # service. Les permissions par défaut d'un serveur partagé sont
        # souvent lisibles par tous.
        try:
            os.chmod(absolute, 0o600)
        except OSError:  # pragma: no cover — dépend du système de fichiers
            pass

        self.file_path = relative
        self.file_sha256 = hashlib.sha256(content).hexdigest()
        self.file_size = len(content)
        return relative

    # ── Cycle de vie ──────────────────────────────────────────────────

    def transition_to(self, new_status, user=None, reason=""):
        """
        Change d'état, en refusant tout ce que la table n'autorise pas.

        Les transitions interdites ne sont pas des cas rares : « corriger »
        un document émis est le réflexe naturel de quelqu'un qui vient de
        repérer une faute de frappe. C'est précisément ce qu'il ne faut
        pas laisser faire silencieusement.
        """
        allowed = self.ALLOWED_TRANSITIONS.get(self.status, set())
        if new_status not in allowed:
            raise ValidationError(
                f"Passage de « {self.get_status_display()} » à "
                f"« {dict(self.STATUS_CHOICES).get(new_status, new_status)} » "
                f"impossible. Transitions permises : "
                f"{', '.join(sorted(allowed)) or 'aucune (état terminal)'}."
            )

        now = timezone.now()
        fields = ["status", "updated_at"]

        if new_status == self.VALIDATED:
            self.validated_by, self.validated_at = user, now
            fields += ["validated_by", "validated_at"]
        elif new_status == self.ISSUED:
            if not self.file_path:
                raise ValidationError(
                    "Aucun fichier n'a été produit : il n'y a rien à émettre."
                )
            if not self.number:
                self.number = DocumentNumberSequence.next_number(
                    self.academy, self.template_id,
                )
                fields.append("number")
            self.issued_by, self.issued_at = user, now
            fields += ["issued_by", "issued_at"]
        elif new_status == self.REVOKED:
            if not reason:
                raise ValidationError(
                    "Une révocation sans motif est inexploitable : le document "
                    "circule toujours, et personne ne saura pourquoi il ne "
                    "vaut plus."
                )
            self.revocation_reason, self.revoked_at = reason[:255], now
            fields += ["revocation_reason", "revoked_at"]

        self.status = new_status
        self.save(update_fields=fields)
        return self

    def clean(self):
        super().clean()
        # Un document ne peut pas concerner l'élève d'une autre académie :
        # ce serait un diplôme délivré par un établissement qui n'a pas
        # scolarisé l'élève.
        student_school_id = getattr(self.student, "school_id", None)
        if student_school_id and self.academy_id and student_school_id != self.academy_id:
            raise ValidationError({
                "student": (
                    "Cet élève n'appartient pas à l'académie émettrice. Un "
                    "document ne peut pas franchir la frontière entre FEBA et "
                    "FEBA French Heritage Academy."
                )
            })


class DocumentEvent(models.Model):
    """
    Journal immuable des opérations sur un document.

    Sans ce journal, un document révoqué est un document dont personne ne
    sait qui l'a révoqué ni quand — ce qui revient à ne pas pouvoir le
    justifier devant celui qui le détient.
    """

    document = models.ForeignKey(
        GeneratedDocument, on_delete=models.CASCADE, related_name="events",
    )
    action = models.CharField(max_length=30)
    from_status = models.CharField(max_length=20, blank=True)
    to_status = models.CharField(max_length=20, blank=True)
    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
    )
    detail = models.TextField(blank=True)
    performed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Événement document"
        ordering = ["-performed_at"]

    def __str__(self):
        return f"{self.document_id} — {self.action} — {self.performed_at:%d/%m/%Y %H:%M}"


def academy_templates_root():
    """Gabarits téléversés : stockage privé, jamais `/media/`."""
    return os.path.join(private_documents_root(), "academy_templates")


class AcademyDocumentTemplate(models.Model):
    """
    Gabarit officiel TÉLÉVERSÉ par une académie : une version d'un fond.

    POURQUOI DES VERSIONS ET NON UN FICHIER REMPLACÉ
    ------------------------------------------------
    Chaque document émis désigne la version qui l'a produit. Écraser le
    fichier ferait mentir cette référence : l'empreinte conservée ne
    correspondrait plus à rien. Un remplacement crée donc une NOUVELLE
    version ; l'ancienne passe à « remplacé » et reste lisible.

    UNE SEULE VERSION ACTIVE PAR ACADÉMIE ET PAR TYPE
    -------------------------------------------------
    Garanti par une contrainte en base, pas par l'interface : deux
    activations simultanées ne peuvent pas laisser deux diplômes actifs.
    Tant qu'une version active existe, elle prime sur le gabarit intégré
    livré avec l'application pour ce type — la règle est unique et écrite
    (`documents.academy_templates.resolve_template`).
    """

    DIPLOMA = "diploma"
    CERTIFICATE = "certificate"
    KIND_CHOICES = [(DIPLOMA, "Diplôme"), (CERTIFICATE, "Certificat")]

    FORMAT_PDF = "pdf"
    FORMAT_PNG = "png"
    FORMAT_JPEG = "jpeg"
    FORMAT_CHOICES = [
        (FORMAT_PDF, "PDF (fond vectoriel)"),
        (FORMAT_PNG, "Image PNG"),
        (FORMAT_JPEG, "Image JPEG"),
    ]

    DRAFT = "draft"
    VALIDATED = "validated"
    ACTIVE = "active"
    DISABLED = "disabled"
    ARCHIVED = "archived"
    INVALID = "invalid"
    STATUS_CHOICES = [
        (DRAFT, "Téléversé, non validé"),
        (VALIDATED, "Valide, prêt à être activé"),
        (ACTIVE, "Actif — utilisé pour les documents"),
        (DISABLED, "Désactivé"),
        (ARCHIVED, "Remplacé par une version plus récente"),
        (INVALID, "Invalide ou incompatible"),
    ]
    #: Versions dont la configuration peut encore changer. Une version
    #: active ou ayant servi se duplique : son rendu doit rester rejouable.
    EDITABLE_STATUSES = {DRAFT, VALIDATED, INVALID}

    academy = models.ForeignKey(
        "schools.School", on_delete=models.CASCADE, related_name="document_templates",
    )
    kind = models.CharField(max_length=20, choices=KIND_CHOICES)
    version = models.PositiveIntegerField()

    original_filename = models.CharField(max_length=255)
    #: Format du fond NORMALISÉ, celui que le moteur de rendu exploite.
    file_format = models.CharField(max_length=10, choices=FORMAT_CHOICES)
    #: Format RÉEL du fichier téléversé (lu dans son contenu) : docx, odt,
    #: tiff… Identique à `file_format` quand aucune conversion n'a eu lieu.
    source_format = models.CharField(max_length=10, blank=True, default="")
    #: Empreinte du fond normalisé (PDF converti, image redressée) : vérifiée
    #: avant chaque usage, comme celle de l'original.
    normalized_sha256 = models.CharField(max_length=64, blank=True, default="")
    #: Rapport de conversion : moteur, durée, marqueurs effacés.
    conversion = models.JSONField(default=dict, blank=True)
    file_path = models.CharField(
        max_length=500,
        help_text="Chemin RELATIF dans le stockage privé ; nom aléatoire.",
    )
    render_path = models.CharField(
        max_length=500, blank=True,
        help_text="Fond normalisé (PDF converti, image redressée), si différent de l'original.",
    )
    file_sha256 = models.CharField(max_length=64)
    file_size = models.PositiveIntegerField()

    page_count = models.PositiveIntegerField(default=1)
    page_index = models.PositiveIntegerField(
        default=0, help_text="Page du PDF utilisée comme fond (0 = première).",
    )
    page_width_mm = models.FloatField()
    page_height_mm = models.FloatField()
    image_width_px = models.PositiveIntegerField(default=0)
    image_height_px = models.PositiveIntegerField(default=0)

    #: Champs positionnés, en MILLIMÈTRES depuis le coin haut-gauche de la
    #: page : un repère documentaire, indépendant de l'écran qui l'a saisi.
    fields = models.JSONField(default=list, blank=True)
    #: Textes fixes propres à ce gabarit (intitulé, signataire, objet…) et
    #: règle d'émission.
    options = models.JSONField(default=dict, blank=True)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=DRAFT)
    validation_report = models.JSONField(default=dict, blank=True)
    validated_at = models.DateTimeField(null=True, blank=True)
    activated_at = models.DateTimeField(null=True, blank=True)

    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="document_templates_uploaded",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Gabarit d'académie"
        verbose_name_plural = "Gabarits d'académie"
        ordering = ["academy", "kind", "-version"]
        constraints = [
            models.UniqueConstraint(
                fields=["academy", "kind", "version"], name="uniq_academy_template_version",
            ),
            models.UniqueConstraint(
                fields=["academy", "kind"], condition=models.Q(status="active"),
                name="uniq_active_academy_template",
            ),
        ]

    def __str__(self):
        return f"{self.academy} — {self.get_kind_display()} v{self.version} ({self.status})"

    @property
    def absolute_path(self):
        return os.path.join(academy_templates_root(), self.file_path)

    @property
    def render_absolute_path(self):
        return os.path.join(academy_templates_root(), self.render_path or self.file_path)

    @property
    def is_editable(self):
        return self.status in self.EDITABLE_STATUSES

    @property
    def template_id(self):
        """Identifiant porté par les documents produits sur ce gabarit."""
        return f"{self.kind}_upload"

    @property
    def sequence_key(self):
        """
        Clé du compteur de numéros.

        Celle du gabarit intégré de la même académie (« diploma_feba »,
        « certificate_feba_fha »…) : passer du gabarit livré au gabarit
        téléversé ne doit pas remettre la numérotation à 1 — deux diplômes
        « FEBA-DIP-2026-0001 » seraient refusés par la base, ou pire,
        confondus sur papier.
        """
        return f"{self.kind}_{self.academy.code.lower()}"

    def fingerprint(self):
        """Empreinte de la version : fichier + configuration rendue."""
        import json

        payload = json.dumps({
            "file": self.file_sha256, "normalized": self.normalized_sha256,
            "page": self.page_index,
            "size": [self.page_width_mm, self.page_height_mm],
            "fields": self.fields, "options": self.options,
        }, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class AcademyTemplateEvent(models.Model):
    """Journal des opérations sur un gabarit — qui, quoi, quand."""

    template = models.ForeignKey(
        AcademyDocumentTemplate, on_delete=models.CASCADE, related_name="events",
    )
    action = models.CharField(max_length=30)
    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
    )
    detail = models.TextField(blank=True)
    performed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Événement de gabarit"
        ordering = ["-performed_at"]
