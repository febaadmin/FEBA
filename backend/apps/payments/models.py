"""
Payments models — v7

PaymentHistory provides immutable audit trail for:
  - creation
  - cancellation (with mandatory justification)
  - any modification

The Payment itself is never deleted (soft-cancel via is_confirmed=False).
"""
from django.db import models
from django.utils import timezone
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
    amount = models.DecimalField(max_digits=12, decimal_places=2)
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

    def __str__(self):
        return f"{self.reference_number} — {self.student} — {self.amount} FCFA"

    def save(self, *args, **kwargs):
        # Auto-generate unique reference on first save
        if not self.reference_number:
            year = timezone.now().year
            suffix = uuid.uuid4().hex[:6].upper()
            self.reference_number = f"PAY-{year}-{suffix}"
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
