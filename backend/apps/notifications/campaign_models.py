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


class EmailCampaign(models.Model):
    QUEUED = "queued"
    SENDING = "sending"
    DONE = "done"
    PARTIAL = "partial"
    FAILED = "failed"
    STATUS_CHOICES = [
        (QUEUED, "En file d'attente"),
        (SENDING, "Envoi en cours"),
        (DONE, "Terminé"),
        (PARTIAL, "Terminé avec des échecs"),
        (FAILED, "Échec"),
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
    body = models.TextField()
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
    STATUS_CHOICES = [
        (PENDING, "En attente"),
        (SENDING, "En cours"),
        (SENT, "Remis au serveur de messagerie"),
        (RETRY, "Nouvel essai programmé"),
        (FAILED, "Échec"),
        (SKIPPED_NO_EMAIL, "Ignoré — aucune adresse"),
        (SKIPPED_INVALID, "Ignoré — adresse invalide"),
        (SKIPPED_INACTIVE, "Ignoré — compte inactif"),
        (SKIPPED_DUPLICATE, "Ignoré — adresse en double"),
    ]
    SKIPPED = {SKIPPED_NO_EMAIL, SKIPPED_INVALID, SKIPPED_INACTIVE, SKIPPED_DUPLICATE}
    RETRYABLE = {FAILED, RETRY}

    campaign = models.ForeignKey(EmailCampaign, on_delete=models.CASCADE, related_name="recipients")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="campaign_receipts",
    )
    email = models.CharField(max_length=254, blank=True)
    full_name = models.CharField(max_length=200, blank=True)
    role = models.CharField(max_length=12, blank=True)
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
        return f"{self.campaign_id} → {self.email or '—'} [{self.status}]"

    @property
    def tracking_reference(self):
        """Référence portée par l'EmailDelivery : relie le journal à cette ligne."""
        return f"CAMP-{self.campaign_id}-R{self.pk}"
