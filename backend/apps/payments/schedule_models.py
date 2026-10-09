"""
apps/payments/schedule_models.py — Échéanciers, dispositions par élève et
relances de paiement.

POURQUOI CES MODÈLES
--------------------
La grille tarifaire (`FeeSchedule`) répondait à « combien coûte ceci » ; rien
ne disait QUAND c'était dû. Sans échéance, impossible de savoir qu'un
paiement est en retard — donc impossible de relancer sans inventer une
règle. Les modalités de paiement par tranche (« 150 000 en septembre,
100 000 en novembre, le solde en janvier ») sont désormais des DONNÉES,
saisies par l'académie, et non des montants cachés dans le code.

    FeeInstallment          une tranche : montant et date limite
    StudentFeeArrangement   abonnement (cantine, transport…), exonération
                            ou réduction propre à un élève
    PaymentReminderPolicy   règles de relance d'une académie (désactivées
                            par défaut)
    ReminderRun             trace de chaque exécution du moteur
    PaymentReminder         une relance : élève × tranche × destinataire ×
                            niveau de rappel, avec sa clé d'idempotence
"""
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class FeeInstallment(models.Model):
    """Une échéance d'un tarif : montant attendu et date limite."""

    fee_schedule = models.ForeignKey(
        "payments.FeeSchedule", on_delete=models.CASCADE, related_name="installments",
    )
    label = models.CharField(max_length=80, help_text="Ex. « 1re tranche », « Octobre 2026 ».")
    due_date = models.DateField(help_text="Date limite de paiement (incluse).")
    amount_minor = models.BigIntegerField(help_text="Montant attendu, en unité mineure.")
    order = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Échéance"
        verbose_name_plural = "Échéances"
        ordering = ["fee_schedule", "due_date", "order"]
        constraints = [
            models.CheckConstraint(check=models.Q(amount_minor__gt=0), name="installment_amount_positive"),
            models.UniqueConstraint(fields=["fee_schedule", "due_date"], name="uniq_installment_due_date"),
        ]

    def __str__(self):
        return f"{self.fee_schedule_id} · {self.label} · {self.due_date}"

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class StudentFeeArrangement(models.Model):
    """
    Disposition propre à un élève pour un tarif.

    - subscription : l'élève est inscrit à un service optionnel (cantine,
      transport, garderie). Un tarif « non obligatoire » ne concerne QUE
      les élèves abonnés : sans cette ligne, aucun montant n'est dû et
      aucune relance n'est envoyée.
    - exemption   : exonération totale — rien n'est dû.
    - discount    : réduction d'un montant fixe sur le total du tarif.
    """

    SUBSCRIPTION = "subscription"
    EXEMPTION = "exemption"
    DISCOUNT = "discount"
    KIND_CHOICES = [
        (SUBSCRIPTION, "Abonnement au service"),
        (EXEMPTION, "Exonération totale"),
        (DISCOUNT, "Réduction / bourse (montant fixe)"),
    ]

    student = models.ForeignKey(
        "students.Student", on_delete=models.CASCADE, related_name="fee_arrangements",
    )
    fee_schedule = models.ForeignKey(
        "payments.FeeSchedule", on_delete=models.CASCADE, related_name="arrangements",
    )
    kind = models.CharField(max_length=14, choices=KIND_CHOICES)
    discount_minor = models.BigIntegerField(
        default=0, help_text="Réduction en unité mineure (réduction uniquement).",
    )
    start_date = models.DateField(
        null=True, blank=True, help_text="Abonnement : premières échéances concernées.",
    )
    end_date = models.DateField(
        null=True, blank=True, help_text="Abonnement : dernières échéances concernées.",
    )
    reason = models.CharField(max_length=255, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="+",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Disposition tarifaire d'un élève"
        verbose_name_plural = "Dispositions tarifaires des élèves"
        constraints = [
            models.UniqueConstraint(
                fields=["student", "fee_schedule", "kind"], name="uniq_student_fee_arrangement",
            ),
            models.CheckConstraint(check=models.Q(discount_minor__gte=0), name="arrangement_discount_not_negative"),
        ]

    def __str__(self):
        return f"{self.student_id} · {self.fee_schedule_id} · {self.kind}"

    def clean(self):
        super().clean()
        if self.student_id and self.fee_schedule_id:
            if self.student.school_id != self.fee_schedule.academy_id:
                raise ValidationError(
                    "Cet élève et ce tarif n'appartiennent pas à la même académie."
                )
        if self.kind == self.DISCOUNT and self.discount_minor <= 0:
            raise ValidationError({"discount_minor": "Une réduction doit avoir un montant positif."})
        if self.kind != self.DISCOUNT and self.discount_minor:
            raise ValidationError({"discount_minor": "Seule une réduction porte un montant."})
        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValidationError({"end_date": "La fin précède le début."})

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class PaymentReminderPolicy(models.Model):
    """
    Règles de relance d'UNE académie.

    Désactivée par défaut : l'envoi automatique d'un message parlant
    d'argent à des familles ne doit jamais s'allumer par surprise. Il faut
    en plus `PAYMENT_REMINDERS_ENABLED=True` dans la configuration du
    serveur (interrupteur global, faux en développement et en test).
    """

    academy = models.OneToOneField(
        "schools.School", on_delete=models.CASCADE, related_name="reminder_policy",
    )
    enabled = models.BooleanField(
        default=False, help_text="Relances AUTOMATIQUES actives pour cette académie.",
    )
    grace_days = models.PositiveSmallIntegerField(
        default=7, help_text="Jours de tolérance après la date limite avant la 1re relance.",
    )
    interval_days = models.PositiveSmallIntegerField(
        default=14, help_text="Jours minimum entre deux relances d'une même échéance.",
    )
    max_reminders = models.PositiveSmallIntegerField(
        default=3, help_text="Nombre maximum de relances par échéance et par destinataire.",
    )
    min_amount_minor = models.BigIntegerField(
        default=1, help_text="Solde minimum (unité mineure) en deçà duquel on ne relance pas.",
    )
    send_email = models.BooleanField(default=True)
    send_notification = models.BooleanField(default=True)
    payment_instructions = models.TextField(
        blank=True, help_text="Modalités de paiement rappelées dans le message.",
    )
    contact_text = models.TextField(
        blank=True, help_text="Coordonnées du secrétariat / service comptable.",
    )
    paused_reason = models.CharField(max_length=255, blank=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="+",
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Politique de relance"
        verbose_name_plural = "Politiques de relance"

    def __str__(self):
        return f"Relances {self.academy_id} ({'actives' if self.enabled else 'inactives'})"

    def clean(self):
        super().clean()
        if self.max_reminders < 1:
            raise ValidationError({"max_reminders": "Au moins une relance."})
        if self.interval_days < 1:
            raise ValidationError({"interval_days": "Au moins un jour entre deux relances."})


class ReminderRun(models.Model):
    """Une exécution du moteur de relance (automatique, manuelle ou simulation)."""

    TRIGGER_BEAT = "beat"
    TRIGGER_MANUAL = "manual"
    TRIGGER_DRY_RUN = "dry_run"
    TRIGGER_CHOICES = [
        (TRIGGER_BEAT, "Planification automatique"),
        (TRIGGER_MANUAL, "Lancement manuel"),
        (TRIGGER_DRY_RUN, "Simulation sans envoi"),
    ]
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    SKIPPED = "skipped"
    STATUS_CHOICES = [
        (RUNNING, "En cours"), (DONE, "Terminée"), (FAILED, "Échec"),
        (SKIPPED, "Non exécutée (désactivée)"),
    ]

    academy = models.ForeignKey(
        "schools.School", on_delete=models.CASCADE, null=True, blank=True,
        related_name="reminder_runs",
    )
    trigger = models.CharField(max_length=10, choices=TRIGGER_CHOICES)
    triggered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="+",
    )
    reference_date = models.DateField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=RUNNING)
    stats = models.JSONField(default=dict, blank=True)
    error = models.TextField(blank=True)
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Exécution des relances"
        verbose_name_plural = "Exécutions des relances"
        ordering = ["-started_at"]


class PaymentReminder(models.Model):
    """
    Une relance adressée à UN responsable, pour UNE échéance d'UN élève, à
    UN niveau de rappel. La clé d'idempotence est unique en base : rejouer
    la tâche, ou l'exécuter deux fois en parallèle, ne peut pas produire
    deux fois la même relance.
    """

    PENDING = "pending"
    SENT = "sent"
    NOTIFIED = "notified"
    RETRY = "retry"
    FAILED = "failed"
    NO_CHANNEL = "no_channel"
    STATUS_CHOICES = [
        (PENDING, "En cours de traitement"),
        (SENT, "E-mail remis au serveur de messagerie"),
        (NOTIFIED, "Notification interne uniquement (pas d'e-mail)"),
        (RETRY, "E-mail : nouvel essai programmé"),
        (FAILED, "Échec de l'e-mail"),
        (NO_CHANNEL, "Aucun canal disponible"),
    ]

    academy = models.ForeignKey("schools.School", on_delete=models.CASCADE, related_name="payment_reminders")
    student = models.ForeignKey("students.Student", on_delete=models.CASCADE, related_name="payment_reminders")
    # SET_NULL et non CASCADE : modifier ou supprimer un échéancier après
    # coup ne doit pas effacer la trace des relances déjà envoyées. Les
    # montants et la date sont conservés ci-dessous en instantané.
    fee_schedule = models.ForeignKey(
        "payments.FeeSchedule", on_delete=models.SET_NULL, null=True, related_name="reminders",
    )
    installment = models.ForeignKey(
        FeeInstallment, on_delete=models.SET_NULL, null=True, related_name="reminders",
    )
    fee_label = models.CharField(max_length=160, blank=True)
    installment_label = models.CharField(max_length=80, blank=True)
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="payment_reminders",
    )
    level = models.PositiveSmallIntegerField()
    idempotency_key = models.CharField(max_length=80, unique=True)
    run = models.ForeignKey(ReminderRun, on_delete=models.SET_NULL, null=True, blank=True, related_name="reminders")

    # Instantané des montants AU MOMENT de la relance : si l'échéancier ou
    # les paiements changent ensuite, on sait ce qui a été écrit au parent.
    currency = models.CharField(max_length=3)
    due_date = models.DateField()
    amount_expected_minor = models.BigIntegerField()
    amount_paid_minor = models.BigIntegerField()
    amount_due_minor = models.BigIntegerField()

    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default=PENDING)
    notification = models.ForeignKey(
        "notifications.Notification", on_delete=models.SET_NULL, null=True, blank=True, related_name="+",
    )
    email_delivery = models.ForeignKey(
        "notifications.EmailDelivery", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="payment_reminders",
    )
    email_to = models.CharField(max_length=254, blank=True)
    error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Relance de paiement"
        verbose_name_plural = "Relances de paiement"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["academy", "status"]),
            models.Index(fields=["installment", "student", "recipient"]),
        ]

    def __str__(self):
        return self.idempotency_key

    @staticmethod
    def make_key(installment_id, student_id, recipient_id, level):
        return f"inst{installment_id}:stu{student_id}:usr{recipient_id}:L{level}"
