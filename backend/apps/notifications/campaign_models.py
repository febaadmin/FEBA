"""
apps/notifications/campaign_models.py — Envois d'e-mails groupés par académie.

CE QUE CES MODÈLES GARANTISSENT
-------------------------------
- Un envoi groupé (« campagne ») appartient à UNE académie. Ses
  destinataires ont été recalculés par le serveur au moment de la création,
  à partir des règles d'audience — jamais repris tels quels du navigateur.
- Chaque destinataire a sa propre ligne et son propre statut. Un échec
  n'empêche pas les autres envois, et une relance ne touche que ce qui n'est
  pas parti : la contrainte (campagne, utilisateur) interdit les doublons,
  et le passage « en attente → en cours » est atomique.
- Les statuts ne mentent pas : « remis au serveur de messagerie » est le
  plus fort qu'un logiciel puisse constater. Personne ne peut savoir, sans
  accusé de lecture, qu'un message est arrivé dans une boîte.

CONFIDENTIALITÉ
---------------
Un message par destinataire, un seul destinataire par message : aucune
adresse n'est exposée aux autres. Le corps du message est conservé pour
pouvoir relancer les échecs ; il est visible des seuls administrateurs de
l'académie.
"""
from django.conf import settings
from django.db import models

from .email_models import email_attachment_storage


class EmailCampaign(models.Model):
    QUEUED = "queued"
    SENDING = "sending"
    DONE = "done"
    PARTIAL = "partial"
    FAILED = "failed"
    # « Terminé » = remis au serveur d'envoi (SMTP) pour chaque destinataire.
    # Ce n'est PAS une preuve de livraison dans la boîte du destinataire :
    # le fournisseur actuel ne renvoie aucun accusé de livraison.
    STATUS_CHOICES = [
        (QUEUED, "En attente"),
        (SENDING, "En cours d'envoi"),
        (DONE, "Envoyé au fournisseur"),
        (PARTIAL, "Envoyé avec des échecs"),
        (FAILED, "Échec"),
    ]
    TEXTE, HTML = "texte", "html"
    FORMAT_CHOICES = [(TEXTE, "Texte brut"), (HTML, "Mise en forme (HTML)")]
    INDIVIDUEL, COMMUN = "individuel", "commun"
    MODE_CHOICES = [
        (INDIVIDUEL, "Un message individuel par destinataire (aucune adresse visible des autres)"),
        (COMMUN, "Message commun : les destinataires « À » et « Cc » se voient, « Cci » reste invisible"),
    ]

    academy = models.ForeignKey(
        "schools.School", on_delete=models.CASCADE, related_name="email_campaigns",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
        related_name="email_campaigns",
    )
    #: Copie de l'adresse de l'auteur : la trace survit à la suppression du compte.
    created_by_email = models.EmailField(blank=True)
    subject = models.CharField(max_length=200)
    #: Texte du message (texte brut, ou version texte du HTML).
    body = models.TextField()
    body_format = models.CharField(max_length=8, choices=FORMAT_CHOICES, default=TEXTE)
    #: HTML NETTOYÉ (apps.notifications.html_securise) ; vide en texte brut.
    body_html = models.TextField(blank=True)
    mode = models.CharField(max_length=12, choices=MODE_CHOICES, default=INDIVIDUEL)
    #: Contenu archivé (texte, HTML, pièces jointes) partagé par tous les
    #: destinataires : un seul exemplaire des fichiers.
    content = models.ForeignKey(
        "notifications.EmailContent", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="campaigns",
    )
    #: Règles d'audience telles que soumises : rôles, « tous les profils »,
    #: inclusions et exclusions explicites. Sert d'audit, pas de source :
    #: les destinataires réels sont les lignes EmailCampaignRecipient.
    audience = models.JSONField(default=dict, blank=True)
    #: Jeton fourni par le navigateur pour chaque formulaire : un double
    #: clic ou un renvoi réseau ne crée pas une seconde campagne.
    client_token = models.CharField(max_length=64)

    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default=QUEUED)
    total_recipients = models.PositiveIntegerField(default=0)
    skipped_count = models.PositiveIntegerField(default=0)
    last_error = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Envoi groupé d'e-mails"
        verbose_name_plural = "Envois groupés d'e-mails"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["created_by", "client_token"], name="uniq_campaign_client_token",
            ),
        ]
        indexes = [models.Index(fields=["academy", "status"])]

    def __str__(self):
        return f"{self.academy_id} · {self.subject[:40]} [{self.status}]"

    def counts(self):
        rows = self.recipients.values("status").annotate(n=models.Count("id"))
        counts = {row["status"]: row["n"] for row in rows}
        return {key: counts.get(key, 0) for key, _ in EmailCampaignRecipient.STATUS_CHOICES}


class EmailCampaignRecipient(models.Model):
    PENDING = "pending"
    SENDING = "sending"
    SENT = "sent"
    RETRY = "retry"
    FAILED = "failed"
    SKIPPED_NO_EMAIL = "skipped_no_email"
    SKIPPED_INVALID = "skipped_invalid_email"
    SKIPPED_INACTIVE = "skipped_inactive"
    SKIPPED_DUPLICATE = "skipped_duplicate"
    #: Adresse refusée définitivement par le serveur d'envoi (SMTP 5xx) : aucune nouvelle tentative.
    REJECTED = "rejected"
    STATUS_CHOICES = [
        (PENDING, "En attente"),
        (SENDING, "En cours"),
        (SENT, "Remis au serveur de messagerie"),
        (RETRY, "Nouvel essai programmé"),
        (FAILED, "Échec"),
        (SKIPPED_NO_EMAIL, "Ignoré - aucune adresse"),
        (SKIPPED_INVALID, "Ignoré - adresse invalide"),
        (SKIPPED_INACTIVE, "Ignoré - compte inactif"),
        (SKIPPED_DUPLICATE, "Ignoré - adresse en double"),
        (REJECTED, "Rejeté par le serveur d'envoi"),
    ]
    GROUPE, A, CC, CCI = "groupe", "a", "cc", "cci"
    CHAMP_CHOICES = [(GROUPE, "Profil ou liste (message individuel)"), (A, "À"), (CC, "Cc"), (CCI, "Cci")]
    SKIPPED = {SKIPPED_NO_EMAIL, SKIPPED_INVALID, SKIPPED_INACTIVE, SKIPPED_DUPLICATE}
    RETRYABLE = {FAILED, RETRY, REJECTED}

    campaign = models.ForeignKey(EmailCampaign, on_delete=models.CASCADE, related_name="recipients")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="campaign_receipts",
    )
    email = models.CharField(max_length=254, blank=True)
    full_name = models.CharField(max_length=200, blank=True)
    role = models.CharField(max_length=12, blank=True)
    #: Champ de destination : profil/liste (individuel), À, Cc ou Cci.
    champ = models.CharField(max_length=8, choices=CHAMP_CHOICES, default=GROUPE)
    status = models.CharField(max_length=24, choices=STATUS_CHOICES, default=PENDING)
    delivery = models.ForeignKey(
        "notifications.EmailDelivery", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="campaign_recipients",
    )
    attempts = models.PositiveSmallIntegerField(default=0)
    error = models.TextField(blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Destinataire d'un envoi groupé"
        verbose_name_plural = "Destinataires d'envois groupés"
        ordering = ["campaign", "full_name"]
        constraints = [
            # Un même compte n'est jamais deux fois destinataire d'une
            # campagne, quoi qu'il arrive aux tâches de fond.
            models.UniqueConstraint(
                fields=["campaign", "user"], name="uniq_campaign_recipient_user",
            ),
        ]
        indexes = [models.Index(fields=["campaign", "status"])]

    def __str__(self):
        return f"{self.campaign_id} → {self.email or '-'} [{self.status}]"

    @property
    def tracking_reference(self):
        """Référence portée par l'EmailDelivery : relie le journal à cette ligne."""
        return f"CAMP-{self.campaign_id}-R{self.pk}"


def _piece_brouillon_path(instance, filename):
    import uuid
    return f"brouillons/{instance.brouillon_id}/{uuid.uuid4().hex}"


class BrouillonEmail(models.Model):
    """Brouillon d'e-mail : repris et envoyé plus tard par son auteur (et lui seul)."""

    academy = models.ForeignKey("schools.School", on_delete=models.CASCADE, related_name="brouillons_email")
    auteur = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="brouillons_email")
    objet = models.CharField(max_length=200, blank=True)
    corps = models.TextField(blank=True)
    corps_html = models.TextField(blank=True)
    format = models.CharField(max_length=8, choices=EmailCampaign.FORMAT_CHOICES, default=EmailCampaign.TEXTE)
    mode = models.CharField(max_length=12, choices=EmailCampaign.MODE_CHOICES, default=EmailCampaign.INDIVIDUEL)
    #: Règles d'audience et champs À / Cc / Cci tels que saisis (revalidés à l'envoi).
    audience = models.JSONField(default=dict, blank=True)
    cree_le = models.DateTimeField(auto_now_add=True)
    modifie_le = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Brouillon d'e-mail"
        verbose_name_plural = "Brouillons d'e-mails"
        ordering = ["-modifie_le"]
        indexes = [models.Index(fields=["auteur", "academy"])]

    def __str__(self):
        return f"Brouillon {self.pk} · {self.objet[:40]}"


class PieceJointeBrouillon(models.Model):
    """Pièce jointe d'un brouillon : stockage privé, jamais servi publiquement."""

    brouillon = models.ForeignKey(BrouillonEmail, on_delete=models.CASCADE, related_name="pieces")
    fichier = models.FileField(storage=email_attachment_storage, upload_to=_piece_brouillon_path, max_length=255)
    nom = models.CharField(max_length=255)
    type_mime = models.CharField(max_length=127)
    taille = models.PositiveBigIntegerField()
    cree_le = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Pièce jointe de brouillon"
        verbose_name_plural = "Pièces jointes de brouillons"
        ordering = ["cree_le", "pk"]

    def lire(self):
        with self.fichier.open("rb") as f:
            return f.read()


class SignatureEmail(models.Model):
    """Signature personnelle insérée à la demande dans les e-mails."""

    utilisateur = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                       related_name="signature_email")
    texte = models.TextField(blank=True, max_length=2000)
    modifie_le = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Signature d'e-mail"
        verbose_name_plural = "Signatures d'e-mails"
