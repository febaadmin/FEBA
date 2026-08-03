"""
P3 — Le rapport mensuel d'un élève de FEBA French Heritage Academy.

CE QUE CE MODÈLE PROTÈGE
------------------------
Un rapport mensuel part chez des parents, souvent à l'autre bout du
monde, et fait autorité sur le mois écoulé de leur enfant. Trois choses
peuvent mal tourner, et le modèle est construit pour qu'aucune ne puisse
passer inaperçue.

1. **Dire « envoyé » quand rien n'est parti.** Le statut `SENT` n'est
   atteignable que depuis `SENDING`, et uniquement quand le backend
   d'envoi a ACCEPTÉ le message. Produire le PDF ne suffit pas : un
   fichier écrit sur un disque n'est pas un courrier reçu. Le champ
   `provider_message_id` sépare les deux — vide, le message n'a été
   accepté par personne.

2. **Envoyer deux fois le même rapport.** La tâche mensuelle peut être
   relancée : par le planificateur, par un administrateur, par une
   reprise après incident. La contrainte d'unicité
   (académie, élève, année, mois, version) rend le doublon impossible au
   niveau de la BASE, pas seulement dans le code qui l'appelle.

3. **Effacer une version déjà remise.** Modifier un rapport envoyé crée
   une NOUVELLE version ; l'ancienne reste, avec son empreinte et ses
   destinataires. Un parent qui écrit « vous m'aviez dit autre chose »
   doit pouvoir être vérifié.
"""
import hashlib
import os

from django.conf import settings
from django.db import models
from django.utils import timezone


def reports_root():
    """
    Racine du stockage privé des rapports.

    Un rapport mensuel contient les notes, les absences et les
    appréciations d'un mineur. Il ne va JAMAIS dans `MEDIA_ROOT`, servi
    statiquement : une URL devinée suffirait à l'exposer.
    """
    base = getattr(settings, "PRIVATE_MEDIA_ROOT",
                   os.path.join(settings.BASE_DIR, "private_media"))
    return os.path.join(base, "monthly_reports")


class MonthlyReportStatus(models.TextChoices):
    """
    Les huit états, et les transitions qui ont un sens.

    L'ordre compte : `SENT` ne suit jamais directement `GENERATED`. Entre
    les deux il y a `READY` (un humain ou la configuration a autorisé
    l'envoi) puis `SENDING` (une tentative est en cours). Sauter ces
    étapes, c'est afficher « envoyé » pour un fichier qui n'a jamais
    quitté le serveur.
    """
    DRAFT = "draft", "Brouillon"
    GENERATED = "generated", "Généré"
    READY = "ready", "Prêt à envoyer"
    SENDING = "sending", "Envoi en cours"
    SENT = "sent", "Envoyé"
    FAILED = "failed", "Échec"
    CANCELLED = "cancelled", "Annulé"
    ARCHIVED = "archived", "Archivé"


#: Transitions autorisées. Un dictionnaire explicite plutôt qu'une suite
#: de `if` disséminés : la règle se lit d'un coup d'œil, et le test qui
#: la vérifie n'a qu'une seule source à comparer.
ALLOWED_TRANSITIONS = {
    MonthlyReportStatus.DRAFT: {MonthlyReportStatus.GENERATED,
                                MonthlyReportStatus.CANCELLED},
    MonthlyReportStatus.GENERATED: {MonthlyReportStatus.DRAFT,
                                    MonthlyReportStatus.READY,
                                    MonthlyReportStatus.GENERATED,
                                    MonthlyReportStatus.CANCELLED},
    MonthlyReportStatus.READY: {MonthlyReportStatus.SENDING,
                                MonthlyReportStatus.GENERATED,
                                MonthlyReportStatus.CANCELLED},
    MonthlyReportStatus.SENDING: {MonthlyReportStatus.SENT,
                                  MonthlyReportStatus.FAILED},
    MonthlyReportStatus.SENT: {MonthlyReportStatus.ARCHIVED,
                               MonthlyReportStatus.SENDING},
    MonthlyReportStatus.FAILED: {MonthlyReportStatus.READY,
                                 MonthlyReportStatus.SENDING,
                                 MonthlyReportStatus.CANCELLED},
    MonthlyReportStatus.CANCELLED: {MonthlyReportStatus.ARCHIVED,
                                    MonthlyReportStatus.DRAFT},
    MonthlyReportStatus.ARCHIVED: set(),
}

MONTH_NAMES_FR = [
    "", "janvier", "février", "mars", "avril", "mai", "juin",
    "juillet", "août", "septembre", "octobre", "novembre", "décembre",
]
MONTH_NAMES_EN = [
    "", "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]


class InvalidTransition(ValueError):
    """Refus explicite d'un changement d'état incohérent."""


class MonthlyStudentReport(models.Model):
    academy = models.ForeignKey(
        "schools.School", on_delete=models.PROTECT,
        related_name="monthly_reports",
        help_text="Académie propriétaire. Fixée d'après l'élève.",
    )
    student = models.ForeignKey(
        "students.Student", on_delete=models.CASCADE,
        related_name="monthly_reports",
    )
    school_year = models.ForeignKey(
        "schools.SchoolYear", on_delete=models.PROTECT,
        related_name="monthly_reports", null=True, blank=True,
    )
    year = models.PositiveSmallIntegerField()
    month = models.PositiveSmallIntegerField(help_text="1 à 12.")

    #: Version du rapport pour cette période. Modifier un rapport déjà
    #: envoyé n'écrase rien : une version de plus est créée.
    version = models.PositiveSmallIntegerField(default=1)

    reference = models.CharField(max_length=48, unique=True, null=True,
                                 blank=True)
    status = models.CharField(
        max_length=12, choices=MonthlyReportStatus.choices,
        default=MonthlyReportStatus.DRAFT, db_index=True,
    )

    #: Données AGRÉGÉES, telles que relevées au moment de la génération.
    #: Figées : un rapport doit rester lisible tel qu'il a été envoyé,
    #: même si une note est corrigée le mois suivant.
    generated_data = models.JSONField(default=dict, blank=True)
    #: Ce que l'administration ajoute : commentaires, recommandations,
    #: objectifs. Séparé des données agrégées, pour qu'une régénération
    #: ne perde jamais le texte écrit par un humain.
    editable_content = models.JSONField(default=dict, blank=True)

    pdf_path = models.CharField(max_length=255, blank=True)
    pdf_sha256 = models.CharField(max_length=64, blank=True)

    generated_at = models.DateTimeField(null=True, blank=True)
    scheduled_at = models.DateTimeField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    recipients = models.JSONField(
        default=list, blank=True,
        help_text="Adresses réellement visées par la dernière tentative.",
    )
    attempts_count = models.PositiveSmallIntegerField(default=0)
    last_attempt_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True)
    #: Identifiant rendu par le fournisseur d'envoi. VIDE tant qu'aucun
    #: fournisseur n'a accepté le message — c'est ce champ, et non le
    #: statut seul, qui distingue « écrit sur disque » de « remis ».
    provider_message_id = models.CharField(max_length=255, blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
        blank=True, related_name="monthly_reports_created",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
        blank=True, related_name="monthly_reports_updated",
    )
    archived_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Rapport mensuel"
        verbose_name_plural = "Rapports mensuels"
        ordering = ["-year", "-month", "student__last_name", "-version"]
        constraints = [
            # La protection contre les doublons vit dans la BASE. Un
            # verrou applicatif se contourne par un second processus, une
            # relance manuelle, un rejeu de tâche : la contrainte, non.
            models.UniqueConstraint(
                fields=["academy", "student", "year", "month", "version"],
                name="rapport_mensuel_unique_par_periode_et_version",
            ),
            models.CheckConstraint(
                check=models.Q(month__gte=1) & models.Q(month__lte=12),
                name="rapport_mensuel_mois_valide",
            ),
        ]
        indexes = [
            models.Index(fields=["academy", "year", "month"]),
            models.Index(fields=["status", "scheduled_at"]),
        ]

    def __str__(self):
        return f"{self.reference or '(sans référence)'} — {self.student}"

    # ── Identité ─────────────────────────────────────────────────────

    def save(self, *args, **kwargs):
        creating = self._state.adding
        super().save(*args, **kwargs)
        if creating and not self.reference:
            self.reference = self.build_reference()
            super().save(update_fields=["reference"])

    def build_reference(self):
        """
        « FHA-RM-2026-03-0042-v1 ».

        Dérivée de la clé primaire, jamais d'un comptage : compter les
        lignes existantes redonnerait un numéro déjà attribué dès qu'un
        rapport est supprimé, et deux rapports différents porteraient la
        même référence dans les échanges avec deux familles.
        """
        return (f"FHA-RM-{self.year:04d}-{self.month:02d}-"
                f"{self.pk:04d}-v{self.version}")

    def period_label(self, language="fr"):
        names = MONTH_NAMES_EN if language == "en" else MONTH_NAMES_FR
        return f"{names[self.month]} {self.year}"

    # ── Fichier ──────────────────────────────────────────────────────

    @property
    def pdf_absolute_path(self):
        if not self.pdf_path:
            return ""
        return os.path.join(reports_root(), self.pdf_path)

    @property
    def has_pdf(self):
        return bool(self.pdf_path) and os.path.exists(self.pdf_absolute_path)

    def store_pdf(self, content):
        """
        Écrit le PDF dans le stockage privé et enregistre son empreinte.

        L'ancienne version n'est pas supprimée : une copie a peut-être
        déjà été envoyée, et l'historique doit permettre de dire quel
        fichier la famille détient.
        """
        relative = os.path.join(str(self.academy_id),
                                f"{self.reference}.pdf")
        absolute = os.path.join(reports_root(), relative)
        os.makedirs(os.path.dirname(absolute), exist_ok=True)
        with open(absolute, "wb") as handle:
            handle.write(content)
        try:
            os.chmod(absolute, 0o600)
        except OSError:  # pragma: no cover — dépend du système de fichiers
            pass
        self.pdf_path = relative
        self.pdf_sha256 = hashlib.sha256(content).hexdigest()
        self.generated_at = timezone.now()

    # ── États ────────────────────────────────────────────────────────

    def can_transition_to(self, target):
        return MonthlyReportStatus(target) in ALLOWED_TRANSITIONS[
            MonthlyReportStatus(self.status)]

    def transition_to(self, target, *, user=None, save=True):
        """
        Change d'état, ou refuse en le disant.

        Un `status = "sent"` posé directement contournerait la règle sans
        bruit. Tout passage par cette méthode rend l'incohérence
        impossible à écrire par distraction.
        """
        target = MonthlyReportStatus(target)
        if not self.can_transition_to(target):
            raise InvalidTransition(
                f"Passage de « {self.get_status_display()} » à "
                f"« {target.label} » interdit."
            )
        self.status = target
        if user is not None:
            self.updated_by = user
        if target == MonthlyReportStatus.ARCHIVED:
            self.archived_at = timezone.now()
        if save:
            self.save(update_fields=["status", "updated_by", "archived_at",
                                     "updated_at"])
        return self

    @property
    def is_editable(self):
        """
        Un rapport envoyé ou archivé n'est plus modifiable EN PLACE.

        Le corriger créerait un document différent portant la même
        référence que celui déjà remis à la famille.
        """
        return self.status in {
            MonthlyReportStatus.DRAFT, MonthlyReportStatus.GENERATED,
            MonthlyReportStatus.READY, MonthlyReportStatus.FAILED,
        }

    @property
    def really_sent(self):
        """
        Le seul critère honnête : un fournisseur a accepté le message.

        Le statut peut dire « envoyé » ; ce booléen dit si quelqu'un
        d'autre que nous en a pris la responsabilité.
        """
        return bool(self.sent_at and self.provider_message_id)


class MonthlyReportAttempt(models.Model):
    """
    Une tentative d'envoi — réussie ou non.

    Le rapport porte l'état COURANT ; cette table porte l'histoire. Sans
    elle, un rapport passé de `failed` à `sent` après trois essais ne
    garderait aucune trace des trois premiers, et la question « depuis
    quand ce parent ne reçoit-il rien ? » resterait sans réponse.
    """
    report = models.ForeignKey(
        MonthlyStudentReport, on_delete=models.CASCADE,
        related_name="attempts",
    )
    attempted_at = models.DateTimeField(auto_now_add=True)
    recipients = models.JSONField(default=list, blank=True)
    succeeded = models.BooleanField(default=False)
    #: Renseigné uniquement quand un fournisseur externe a répondu.
    provider_message_id = models.CharField(max_length=255, blank=True)
    used_real_provider = models.BooleanField(
        default=False,
        help_text="Faux quand le message a seulement été écrit dans la "
                  "console ou capturé localement.",
    )
    error = models.TextField(blank=True)
    triggered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
        blank=True, related_name="monthly_report_attempts",
    )

    class Meta:
        verbose_name = "Tentative d'envoi"
        verbose_name_plural = "Tentatives d'envoi"
        ordering = ["-attempted_at"]

    def __str__(self):
        etat = "réussie" if self.succeeded else "échouée"
        return f"{self.report_id} — tentative {etat} le {self.attempted_at:%d/%m/%Y %H:%M}"
