"""
Payments models — v7

PaymentHistory provides immutable audit trail for:
  - creation
  - cancellation (with mandatory justification)
  - any modification

The Payment itself is never deleted (soft-cancel via is_confirmed=False).
"""
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from apps.core.currency import DEFAULT_CURRENCY, Money, get_currency
from apps.students.models import Student
from apps.accounts.models import CustomUser
from apps.schools.models import SchoolYear
import uuid


class Payment(models.Model):
    PAYMENT_TYPES = [
        ("inscription", "Inscription"),
        ("mensualite", "Mensualité"),
        ("cantine", "Cantine"),
        ("transport", "Transport"),
        ("other", "Autre"),
    ]
    PAYMENT_METHODS = [
        ("cash", "Espèces"),
        ("mtn_momo", "MTN MoMo"),
        ("moov_money", "Moov Money"),
        ("card", "Carte bancaire"),
    ]

    student = models.ForeignKey(
        Student, on_delete=models.CASCADE, related_name="payments"
    )
    school_year = models.ForeignKey(
        SchoolYear, on_delete=models.SET_NULL, null=True, blank=True
    )
    enrollment = models.ForeignKey(
        "students.StudentEnrollment", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="payments",
        help_text="Inscription annuelle de l'élève correspondant à ce paiement.",
    )
    payment_type = models.CharField(max_length=15, choices=PAYMENT_TYPES)
    # ── Montant et devise (P0) ────────────────────────────────────────
    # `amount_minor` est la valeur DE RÉFÉRENCE : un entier en plus petite
    # unité de la devise (cents pour USD, franc pour XOF, qui n'a pas de
    # subdivision). `amount` reste exposé pour la lisibilité et la
    # compatibilité, mais il est recalculé depuis l'entier à chaque
    # enregistrement — deux sources de vérité finiraient par diverger.
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    amount_minor = models.BigIntegerField(
        default=0,
        help_text="Montant en unité mineure (cents pour USD, franc pour XOF). Valeur de référence.",
    )
    currency = models.CharField(
        max_length=3, default=DEFAULT_CURRENCY,
        help_text=(
            "Devise du paiement. Imposée par l'académie de l'élève : elle "
            "n'est jamais lue depuis le formulaire."
        ),
    )
    payment_date = models.DateField(default=timezone.now)
    received_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        related_name="payments_received",
    )
    payment_method = models.CharField(
        max_length=15, choices=PAYMENT_METHODS, default="cash"
    )
    reference_number = models.CharField(max_length=20, unique=True, blank=True)
    notes = models.TextField(blank=True)
    receipt_file = models.FileField(upload_to="receipts/", null=True, blank=True)
    # is_confirmed=False means soft-cancelled
    is_confirmed = models.BooleanField(default=True)
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)
    deleted_by = models.ForeignKey(
        CustomUser, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="deleted_payments"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Paiement"
        ordering = ["-payment_date", "-created_at"]
        constraints = [
            # Garde-fou au niveau de la base : même un import direct en SQL
            # ne peut pas créer un encaissement négatif.
            models.CheckConstraint(
                check=models.Q(amount_minor__gte=0),
                name="payment_amount_minor_not_negative",
            ),
        ]

    def __str__(self):
        return f"{self.reference_number} — {self.student} — {self.formatted_amount}"

    # ── Devise : imposée par l'académie, jamais par le client ─────────
    @property
    def academy(self):
        """Académie propriétaire — celle de l'élève, seule autorité."""
        student = getattr(self, "student", None)
        return getattr(student, "school", None) if student is not None else None

    @property
    def expected_currency_code(self):
        academy = self.academy
        return getattr(academy, "currency_code", None) or DEFAULT_CURRENCY

    @property
    def money(self):
        return Money(self.amount_minor, self.currency or DEFAULT_CURRENCY)

    @property
    def formatted_amount(self):
        """Montant rendu dans SA devise — jamais un symbole codé en dur."""
        return self.money.formatted()

    def clean(self):
        super().clean()
        expected = self.expected_currency_code
        if self.currency and self.currency.upper() != expected:
            raise ValidationError({
                "currency": (
                    f"Ce paiement appartient à une académie qui facture en "
                    f"{expected} : il ne peut pas être enregistré en "
                    f"{self.currency.upper()}. Changer la devise d'une "
                    f"opération ne change pas la somme réellement encaissée."
                )
            })
        if self.amount_minor is not None and self.amount_minor < 0:
            raise ValidationError({"amount_minor": "Un paiement ne peut pas être négatif."})

    def save(self, *args, **kwargs):
        # Auto-generate unique reference on first save
        if not self.reference_number:
            year = timezone.now().year
            suffix = uuid.uuid4().hex[:6].upper()
            self.reference_number = f"PAY-{year}-{suffix}"

        # La devise vient de l'académie de l'élève. Un `currency` transmis
        # par un formulaire ou une API est ignoré : l'utilisateur ne choisit
        # pas la monnaie dans laquelle son école facture.
        self.currency = self.expected_currency_code
        currency = get_currency(self.currency)

        # Un seul des deux champs est renseigné par l'appelant selon le
        # chemin d'écriture (API existante → `amount` ; paiement carte →
        # `amount_minor`). On dérive l'autre plutôt que d'exiger les deux.
        if self.amount_minor:
            self.amount = currency.to_decimal(self.amount_minor)
        elif self.amount is not None:
            self.amount_minor = currency.to_minor(self.amount)

        self.full_clean(exclude=[f.name for f in self._meta.fields
                                 if f.name not in {"currency", "amount_minor"}])
        super().save(*args, **kwargs)


class PaymentHistory(models.Model):
    """
    Immutable audit log for every action on a Payment.
    Records: create, cancel, update, receipt_generated.
    """
    ACTION_CHOICES = [
        ("create", "Création"),
        ("cancel", "Annulation"),
        ("update", "Modification"),
        ("receipt", "Reçu généré"),
    ]

    payment = models.ForeignKey(
        Payment, on_delete=models.CASCADE, related_name="history"
    )
    action = models.CharField(max_length=10, choices=ACTION_CHOICES)
    performed_by = models.ForeignKey(
        CustomUser, on_delete=models.SET_NULL, null=True, related_name="payment_actions"
    )
    # Snapshot of key fields at time of action
    amount_snapshot = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )
    is_confirmed_before = models.BooleanField(null=True, blank=True)
    is_confirmed_after = models.BooleanField(null=True, blank=True)
    justification = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    performed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Historique paiement"
        ordering = ["-performed_at"]

    def __str__(self):
        return f"{self.payment.reference_number} — {self.action} — {self.performed_at:%d/%m/%Y %H:%M}"


# ── Paiement par carte (P1) ───────────────────────────────────────────
# Les modèles de tentative et de journal d'événements vivent dans un module
# séparé pour ne pas alourdir celui-ci, mais doivent être importés ICI :
# Django ne découvre les modèles que via `models.py`.
from apps.payments.fee_models import FeeSchedule  # noqa: E402,F401
from apps.payments.transaction_models import (  # noqa: E402,F401  (import tardif volontaire)
    PaymentTransaction, WebhookEvent,
)
