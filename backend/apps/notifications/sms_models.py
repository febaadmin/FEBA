"""
apps/notifications/sms_models.py — SMS envoyés (ou volontairement non envoyés).

UNE ligne par destinataire et par ÉVÉNEMENT métier : `event_key` est
unique. Un e-mail relancé, une tâche Celery rejouée, une relance publiée
à la fois par e-mail et en notification interne ne produisent donc jamais
deux SMS. Un événement DIFFÉRENT (nouvelle relance) a sa propre clé.

Le statut ne dit que ce qui a été constaté :
  pending   enregistré, en file ;
  sending   tentative en cours ;
  sent      ACCEPTÉ par le fournisseur (pas encore « reçu ») ;
  delivered remis au téléphone, selon l'accusé du fournisseur ;
  retry     échec temporaire, nouvel essai programmé ;
  failed    échec définitif (erreur du fournisseur ou message trop long) ;
  skipped   volontairement non envoyé, avec la raison (`skip_reason`) ;
  captured  transport de test : enregistré, JAMAIS envoyé.
"""
import uuid

from django.conf import settings
from django.db import models


class SmsMessage(models.Model):
    PENDING, SENDING, SENT, DELIVERED = "pending", "sending", "sent", "delivered"
    RETRY, FAILED, SKIPPED, CAPTURED = "retry", "failed", "skipped", "captured"
    STATUS_CHOICES = [
        (PENDING, "En file d'attente"),
        (SENDING, "Envoi en cours"),
        (SENT, "Accepté par le fournisseur SMS"),
        (DELIVERED, "Remis au téléphone (accusé du fournisseur)"),
        (RETRY, "Échec temporaire - nouvel essai programmé"),
        (FAILED, "Échec définitif"),
        (SKIPPED, "Non envoyé"),
        (CAPTURED, "Capturé (transport de test) - non envoyé"),
    ]
    FINAL = {SENT, DELIVERED, FAILED, SKIPPED, CAPTURED}

    # Raisons d'un SMS volontairement non envoyé — exploitables pour
    # corriger un dossier (numéro manquant, consentement à recueillir…).
    SKIP_DISABLED = "sms_disabled"
    SKIP_NO_USER = "no_matching_account"
    SKIP_NO_PHONE = "no_phone"
    SKIP_INVALID_PHONE = "invalid_phone"
    SKIP_NOT_MOBILE = "not_mobile"
    SKIP_NO_CONSENT = "no_consent"
    SKIP_REFUSED = "consent_refused"
    SKIP_SENSITIVE = "sensitive_content"
    SKIP_EMPTY = "empty_body"
    SKIP_NO_LONGER_DUE = "no_longer_due"
    SKIP_INACTIVE = "inactive_account"
    SKIP_CHOICES = [
        (SKIP_DISABLED, "SMS désactivés sur ce serveur"),
        (SKIP_NO_USER, "Aucun compte FEBA ne correspond à ce destinataire"),
        (SKIP_NO_PHONE, "Aucun numéro de téléphone enregistré"),
        (SKIP_INVALID_PHONE, "Numéro de téléphone invalide"),
        (SKIP_NOT_MOBILE, "Numéro fixe : ne reçoit pas de SMS"),
        (SKIP_NO_CONSENT, "Consentement aux SMS non recueilli"),
        (SKIP_REFUSED, "Le destinataire refuse les SMS"),
        (SKIP_SENSITIVE, "Message de sécurité : jamais copié par SMS"),
        (SKIP_EMPTY, "Message sans texte"),
        (SKIP_NO_LONGER_DUE, "Relance devenue sans objet (paiement reçu, relance annulée)"),
        (SKIP_INACTIVE, "Compte désactivé"),
    ]

    tracking_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    event_key = models.CharField(max_length=120, unique=True)
    purpose = models.CharField(max_length=60, db_index=True)
    entity = models.ForeignKey("schools.School", on_delete=models.SET_NULL, null=True, blank=True,
                               related_name="sms_messages")
    email_delivery = models.ForeignKey("notifications.EmailDelivery", on_delete=models.SET_NULL,
                                       null=True, blank=True, related_name="sms_messages")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                             related_name="sms_messages")
    # Numéro tel que SAISI dans le dossier (pour corriger une erreur) et
    # numéro normalisé E.164 réellement utilisé.
    raw_phone = models.CharField(max_length=40, blank=True)
    to_number = models.CharField(max_length=20, blank=True)
    from_number = models.CharField(max_length=20, blank=True)
    body = models.TextField(blank=True)
    encoding = models.CharField(max_length=8, blank=True)          # GSM-7 / UCS-2
    segments = models.PositiveIntegerField(default=0)
    parts = models.PositiveIntegerField(default=0)                  # nombre de SMS envoyés
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=PENDING, db_index=True)
    skip_reason = models.CharField(max_length=30, choices=SKIP_CHOICES, blank=True)
    provider = models.CharField(max_length=20, blank=True)
    provider_status = models.CharField(max_length=30, blank=True)
    # Vérification métier à refaire AU MOMENT de l'envoi (ex. relance :
    # le paiement a-t-il été reçu entre-temps ?).
    precheck = models.JSONField(default=dict, blank=True)
    attempts = models.PositiveIntegerField(default=0)
    next_retry_at = models.DateTimeField(null=True, blank=True, db_index=True)
    last_error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "SMS"
        verbose_name_plural = "SMS"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["status", "next_retry_at"]),
                   models.Index(fields=["entity", "created_at"])]

    def __str__(self):
        return f"SMS {self.purpose} → {self.masked_number} ({self.status})"

    @property
    def masked_number(self):
        n = self.to_number or self.raw_phone
        return f"{n[:4]}…{n[-2:]}" if len(n) > 6 else ("-" if not n else "…")


class SmsPart(models.Model):
    """
    Un message accepté par le fournisseur (un texte long en compte
    plusieurs, numérotés). Enregistré AUSSITÔT accepté : une reprise ne
    renvoie jamais une partie déjà partie.
    """
    sms = models.ForeignKey(SmsMessage, on_delete=models.CASCADE, related_name="part_records")
    index = models.PositiveIntegerField()
    provider_message_id = models.CharField(max_length=64, db_index=True)
    provider_status = models.CharField(max_length=30, blank=True)
    error_code = models.CharField(max_length=20, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["sms", "index"]
        constraints = [models.UniqueConstraint(fields=["sms", "index"], name="uniq_sms_part_index")]
