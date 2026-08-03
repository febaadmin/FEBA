"""
apps/payments/transaction_models.py — Tentatives de paiement par carte

POURQUOI UN MODÈLE SÉPARÉ DE `Payment`
--------------------------------------
`Payment` représente un encaissement CONSTATÉ : l'argent est arrivé, la
comptabilité peut s'y fier. Une tentative de paiement par carte, elle,
peut échouer, être abandonnée, expirer, ou aboutir vingt minutes plus tard
par un webhook. Confondre les deux reviendrait soit à créer des recettes
fantômes, soit à perdre la trace des échecs — et un parent qui a vu son
compte débité mérite qu'on retrouve sa tentative.

Un `PaymentTransaction` réussi CRÉE un `Payment` ; il ne le remplace pas.

CE QUI N'EST JAMAIS STOCKÉ ICI
------------------------------
Numéro de carte, date d'expiration, cryptogramme, jeton de moyen de
paiement brut. Ces données ne transitent même pas par le serveur : le
formulaire est celui du prestataire, et l'application ne voit que des
identifiants opaques. C'est ce qui permet de ne pas être soumis au champ
d'application complet de la norme PCI-DSS.

LA REDIRECTION N'EST PAS UNE PREUVE
-----------------------------------
Le retour du navigateur sur la page « succès » ne prouve rien : l'URL est
devinable, et un paiement peut être annulé après coup. Seul le webhook
signé fait foi. `mark_succeeded()` n'est appelé que depuis le traitement
d'un événement dont la signature a été vérifiée.
"""
import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.core.currency import DEFAULT_CURRENCY, Money


class PaymentTransaction(models.Model):
    """Une tentative de paiement par carte, de sa création à son issue."""

    # ── Statuts ───────────────────────────────────────────────────────
    # Volontairement plus nombreux que « ok / pas ok » : « action requise »
    # (authentification bancaire) et « expiré » appellent des messages et
    # des relances différents d'un simple échec.
    CREATED = "created"
    PENDING = "pending"
    ACTION_REQUIRED = "action_required"
    PROCESSING = "processing"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    PARTIALLY_REFUNDED = "partially_refunded"
    REFUNDED = "refunded"
    DISPUTED = "disputed"

    STATUS_CHOICES = [
        (CREATED, "Créé"),
        (PENDING, "En attente"),
        (ACTION_REQUIRED, "Action requise (authentification bancaire)"),
        (PROCESSING, "Traitement en cours"),
        (SUCCEEDED, "Réussi"),
        (FAILED, "Échoué"),
        (CANCELLED, "Annulé"),
        (EXPIRED, "Expiré"),
        (PARTIALLY_REFUNDED, "Partiellement remboursé"),
        (REFUNDED, "Totalement remboursé"),
        (DISPUTED, "Contesté"),
    ]

    #: Statuts pour lesquels l'argent est considéré comme encaissé.
    SETTLED_STATUSES = {SUCCEEDED, PARTIALLY_REFUNDED, REFUNDED, DISPUTED}
    #: Statuts encore susceptibles d'évoluer — une nouvelle tentative sur
    #: la même facture serait un doublon.
    OPEN_STATUSES = {CREATED, PENDING, ACTION_REQUIRED, PROCESSING}

    academy = models.ForeignKey(
        "schools.School", on_delete=models.PROTECT, related_name="payment_transactions",
        help_text="Académie propriétaire — impose la devise.",
    )
    payer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="payment_attempts",
        help_text="Utilisateur qui a lancé le paiement (parent le plus souvent).",
    )
    student = models.ForeignKey(
        "students.Student", on_delete=models.PROTECT, related_name="payment_transactions",
    )
    school_year = models.ForeignKey(
        "schools.SchoolYear", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="payment_transactions",
    )
    payment_type = models.CharField(
        max_length=15, default="mensualite",
        help_text="Nature de la somme réglée — reprise sur le Payment créé.",
    )
    fee_schedule = models.ForeignKey(
        "payments.FeeSchedule", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="transactions",
        help_text=(
            "Ligne tarifaire réglée. Vide lorsqu'un membre de "
            "l'administration a saisi un montant hors grille."
        ),
    )
    amount_source = models.CharField(
        max_length=20, default="fee_schedule",
        help_text=(
            "Origine du montant : « fee_schedule » (grille publiée) ou "
            "« staff » (saisi par l'administration). Jamais « client » : "
            "un montant transmis par le navigateur n'est pas une autorité."
        ),
    )

    # ── Montant ───────────────────────────────────────────────────────
    # Recalculé côté serveur au moment de la création : un montant transmis
    # par le navigateur permettrait de payer 1 $ une facture de 1 250 $.
    amount_minor = models.BigIntegerField(
        help_text="Montant en unité mineure (cents pour USD).",
    )
    currency = models.CharField(max_length=3, default=DEFAULT_CURRENCY)
    amount_refunded_minor = models.BigIntegerField(default=0)

    # ── Prestataire ───────────────────────────────────────────────────
    provider = models.CharField(max_length=20, default="stripe")
    provider_session_id = models.CharField(
        max_length=255, blank=True, db_index=True,
        help_text="Identifiant de la session de paiement hébergée.",
    )
    provider_intent_id = models.CharField(
        max_length=255, blank=True, db_index=True,
        help_text="Identifiant du PaymentIntent — clé du rapprochement.",
    )
    provider_status = models.CharField(
        max_length=50, blank=True,
        help_text="Statut brut renvoyé par le prestataire, conservé tel quel pour l'audit.",
    )
    provider_metadata = models.JSONField(
        default=dict, blank=True,
        help_text="Métadonnées NON SENSIBLES (jamais de données de carte).",
    )

    # ── Idempotence ───────────────────────────────────────────────────
    # Une clé stable par tentative : un double clic, un rechargement ou un
    # rejeu réseau réutilisent la même clé et donc la même session côté
    # prestataire, au lieu de débiter deux fois.
    idempotency_key = models.CharField(max_length=64, unique=True, editable=False)

    status = models.CharField(max_length=25, choices=STATUS_CHOICES, default=CREATED)
    failure_reason = models.CharField(max_length=255, blank=True)

    payment = models.OneToOneField(
        "payments.Payment", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="card_transaction",
        help_text="Encaissement constaté, créé une seule fois à la réussite.",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    succeeded_at = models.DateTimeField(null=True, blank=True)
    failed_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Transaction carte"
        verbose_name_plural = "Transactions carte"
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                check=models.Q(amount_minor__gt=0),
                name="transaction_amount_positive",
            ),
            # Un remboursement ne peut pas dépasser ce qui a été encaissé.
            # Vérifié en base : une erreur applicative ne suffit pas à
            # protéger une écriture faite par un script d'exploitation.
            models.CheckConstraint(
                check=models.Q(amount_refunded_minor__lte=models.F("amount_minor")),
                name="transaction_refund_not_over_amount",
            ),
            models.CheckConstraint(
                check=models.Q(amount_refunded_minor__gte=0),
                name="transaction_refund_not_negative",
            ),
        ]
        indexes = [
            models.Index(fields=["academy", "status"]),
            models.Index(fields=["provider", "provider_intent_id"]),
        ]

    def __str__(self):
        return f"{self.provider} {self.reference} — {self.money.formatted()} — {self.status}"

    @property
    def reference(self):
        return self.provider_intent_id or self.provider_session_id or f"TX-{self.pk}"

    @property
    def money(self):
        return Money(self.amount_minor, self.currency)

    @property
    def refunded_money(self):
        return Money(self.amount_refunded_minor, self.currency)

    @property
    def refundable_minor(self):
        return max(self.amount_minor - self.amount_refunded_minor, 0)

    @property
    def is_settled(self):
        return self.status in self.SETTLED_STATUSES

    def save(self, *args, **kwargs):
        if not self.idempotency_key:
            self.idempotency_key = uuid.uuid4().hex
        # La devise vient de l'académie, jamais du client.
        self.currency = getattr(self.academy, "currency_code", None) or DEFAULT_CURRENCY
        super().save(*args, **kwargs)

    # ── Transitions ───────────────────────────────────────────────────

    def mark_succeeded(self, provider_status=""):
        """
        Constate l'encaissement et crée le `Payment` correspondant.

        Idempotent : rappelée par un webhook rejoué, elle ne crée pas un
        second encaissement. C'est la garantie qui empêche un parent d'être
        crédité deux fois pour un seul débit.
        """
        from apps.payments.models import Payment

        if self.payment_id and self.status in self.SETTLED_STATUSES:
            return self.payment

        payment = self.payment
        if payment is None:
            payment = Payment.objects.create(
                student=self.student,
                school_year=self.school_year,
                payment_type=self.payment_type,
                amount_minor=self.amount_minor,
                payment_method="card",
                payment_date=timezone.now().date(),
                received_by=None,
                notes=f"Paiement par carte — {self.provider} {self.reference}",
            )
            self.payment = payment

        self.status = self.SUCCEEDED
        self.provider_status = provider_status or self.provider_status
        self.succeeded_at = self.succeeded_at or timezone.now()
        self.save(update_fields=[
            "payment", "status", "provider_status", "succeeded_at", "updated_at",
        ])

        # Reçu généré automatiquement — mais JAMAIS bloquant. Un échec de
        # rendu PDF (police manquante, disque plein) ne doit pas faire
        # échouer le webhook : l'argent est encaissé, et un webhook en
        # erreur serait rejoué en boucle par le prestataire. Le reçu reste
        # regénérable à la demande.
        if not payment.receipt_file:
            try:
                from apps.payments.pdf_generator import generate_receipt

                generate_receipt(payment)
            except Exception as exc:  # pragma: no cover — dépend de l'environnement
                import logging

                logging.getLogger("apps").warning(
                    "Reçu non généré pour la transaction %s : %s", self.pk, exc,
                )

        return payment

    def mark_failed(self, reason="", provider_status="", status=None):
        self.status = status or self.FAILED
        self.failure_reason = (reason or "")[:255]
        self.provider_status = provider_status or self.provider_status
        self.failed_at = timezone.now()
        self.save(update_fields=[
            "status", "failure_reason", "provider_status", "failed_at", "updated_at",
        ])

    def register_refund(self, amount_minor):
        """
        Enregistre un remboursement, total ou partiel.

        Le plafond est vérifié ici ET par une contrainte de base : une
        erreur applicative seule ne protégerait pas d'une écriture faite
        par un script d'exploitation.
        """
        from django.core.exceptions import ValidationError

        amount_minor = int(amount_minor)
        if amount_minor <= 0:
            raise ValidationError("Le montant remboursé doit être positif.")
        if amount_minor > self.refundable_minor:
            raise ValidationError(
                f"Remboursement impossible : {Money(amount_minor, self.currency).formatted()} "
                f"dépasse le solde remboursable de "
                f"{Money(self.refundable_minor, self.currency).formatted()}."
            )

        self.amount_refunded_minor += amount_minor
        self.status = (
            self.REFUNDED if self.amount_refunded_minor >= self.amount_minor
            else self.PARTIALLY_REFUNDED
        )
        self.save(update_fields=["amount_refunded_minor", "status", "updated_at"])
        return self.refunded_money


class WebhookEvent(models.Model):
    """
    Journal des événements reçus du prestataire.

    Sert à deux choses, toutes deux indispensables :

    1. **Empêcher le double traitement.** Les prestataires garantissent une
       livraison « au moins une fois » : le même événement arrive parfois
       deux fois. Sans ce journal, un paiement serait rapproché deux fois.

    2. **Rendre l'incident analysable.** Quand un parent affirme avoir payé
       et que rien n'apparaît, la question est de savoir si l'événement est
       arrivé. Sans trace, la réponse est un haussement d'épaules.
    """

    RECEIVED = "received"
    PROCESSED = "processed"
    IGNORED = "ignored"
    FAILED = "failed"

    STATUS_CHOICES = [
        (RECEIVED, "Reçu"),
        (PROCESSED, "Traité"),
        (IGNORED, "Ignoré (doublon ou type non géré)"),
        (FAILED, "Échec de traitement"),
    ]

    provider = models.CharField(max_length=20, default="stripe")
    event_id = models.CharField(
        max_length=255,
        help_text="Identifiant unique de l'événement chez le prestataire.",
    )
    event_type = models.CharField(max_length=100)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=RECEIVED)
    transaction = models.ForeignKey(
        PaymentTransaction, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="webhook_events",
    )
    detail = models.TextField(blank=True)
    received_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Événement webhook"
        ordering = ["-received_at"]
        constraints = [
            # L'unicité est la protection anti-double-traitement. Elle est
            # en base, pas seulement dans le code : deux instances du
            # serveur peuvent traiter le même événement au même instant.
            models.UniqueConstraint(
                fields=["provider", "event_id"], name="uniq_webhook_event_per_provider",
            ),
        ]

    def __str__(self):
        return f"{self.provider}:{self.event_type} ({self.status})"
