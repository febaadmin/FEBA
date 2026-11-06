"""
apps/payments/remise_models.py — Remises, exonérations, échéanciers personnels, journal.

    RegleRemise        une remise OU une exonération : valeur (pourcentage ou
                       montant), périmètre (année, nature, niveau, classe,
                       élève, famille), période, conditions, cumul, motif.
    EcheanceEleve      échéancier propre à un élève pour un tarif et une année :
                       remplace, pour CET élève seulement, les échéances
                       standard (délai, répartition différente).
    JournalFinancier   trace inaltérable (ajout seul) de toute création,
                       modification ou annulation : auteur, date, avant, après, motif.

Une seule règle de calcul : `reminders.compute_dues` (voir `ajustements.py`).
Ces modèles ne portent AUCUN montant calculé : ils décrivent des décisions,
le moteur en déduit les sommes dues. Rien n'est jamais supprimé : une règle
est annulée (motif obligatoire), une échéance personnelle désactivée.
"""
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class RegleRemise(models.Model):
    REMISE = "remise"
    EXONERATION = "exoneration"
    GENRES = [(REMISE, "Remise"), (EXONERATION, "Exonération")]

    POURCENTAGE = "pourcentage"
    MONTANT = "montant"
    MODES = [(POURCENTAGE, "Pourcentage"), (MONTANT, "Montant fixe")]

    EXCEPTIONNELLE = "exceptionnelle"
    FRATRIE = "fratrie"
    ANTICIPE = "paiement_anticipe"
    INTEGRAL = "paiement_integral"
    SOCIALE = "sociale"
    SITUATION = "situation_particuliere"
    ADMINISTRATIVE = "decision_administrative"
    AUTRE = "autre"
    CATEGORIES = [
        (EXCEPTIONNELLE, "Remise exceptionnelle"),
        (FRATRIE, "Plusieurs enfants d'une même famille"),
        (ANTICIPE, "Paiement anticipé"),
        (INTEGRAL, "Paiement intégral"),
        (SOCIALE, "Remise sociale"),
        (SITUATION, "Situation particulière"),
        (ADMINISTRATIVE, "Décision administrative"),
        (AUTRE, "Autre"),
    ]
    # Catégories qui exigent une justification écrite (décision individuelle).
    JUSTIFICATION_REQUISE = {EXCEPTIONNELLE, SOCIALE, SITUATION, ADMINISTRATIVE}

    academy = models.ForeignKey("schools.School", on_delete=models.CASCADE, related_name="regles_remise")
    nom = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    genre = models.CharField(max_length=12, choices=GENRES, default=REMISE)
    categorie = models.CharField(max_length=24, choices=CATEGORIES, default=AUTRE)
    mode = models.CharField(max_length=12, choices=MODES, default=POURCENTAGE)
    pourcentage = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(Decimal("0.01")), MaxValueValidator(Decimal("100"))],
    )
    montant_minor = models.BigIntegerField(null=True, blank=True, help_text="Montant fixe, en unité mineure.")
    devise = models.CharField(max_length=3, editable=False, blank=True)

    # Périmètre : un champ vide = « tous ».
    school_year = models.ForeignKey("schools.SchoolYear", on_delete=models.PROTECT, null=True, blank=True, related_name="+")
    payment_type = models.CharField(max_length=15, blank=True, help_text="Nature de frais (vide : toutes).")
    level = models.ForeignKey("schools.Level", on_delete=models.PROTECT, null=True, blank=True, related_name="+")
    class_obj = models.ForeignKey("classes.Class", on_delete=models.PROTECT, null=True, blank=True, related_name="+")
    student = models.ForeignKey("students.Student", on_delete=models.PROTECT, null=True, blank=True, related_name="regles_remise")
    famille = models.ForeignKey("parents.Parent", on_delete=models.PROTECT, null=True, blank=True, related_name="+",
                                help_text="Remise propre à une famille : tous les enfants de ce responsable.")

    # Période : seules les échéances dont la date est dans l'intervalle sont concernées.
    debut = models.DateField(null=True, blank=True)
    fin = models.DateField(null=True, blank=True)

    # Conditions.
    rang_enfant_min = models.PositiveSmallIntegerField(
        null=True, blank=True, validators=[MinValueValidator(2)],
        help_text="Fratrie : à partir du N-ième enfant (rang par date de naissance, l'aîné en premier).",
    )
    date_limite_paiement = models.DateField(
        null=True, blank=True, help_text="Paiement anticipé : solde entièrement réglé au plus tard à cette date.",
    )

    cumulable = models.BooleanField(
        default=True, help_text="Non cumulable : ne se combine avec aucune autre remise.",
    )
    priorite = models.SmallIntegerField(default=0, help_text="Départage deux remises non cumulables d'égale valeur.")

    actif = models.BooleanField(default=True)
    justification = models.TextField(blank=True)
    autorise_par = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    cree_par = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    cree_le = models.DateTimeField(auto_now_add=True)
    modifie_le = models.DateTimeField(auto_now=True)
    annulee_le = models.DateTimeField(null=True, blank=True)
    annulee_par = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    motif_annulation = models.CharField(max_length=255, blank=True)

    class Meta:
        verbose_name = "Remise ou exonération"
        verbose_name_plural = "Remises et exonérations"
        ordering = ["academy", "genre", "-actif", "nom"]
        constraints = [
            models.CheckConstraint(condition=models.Q(montant_minor__isnull=True) | models.Q(montant_minor__gt=0),
                                   name="regle_montant_positif"),
        ]

    def __str__(self):
        return f"{self.academy_id} · {self.genre} · {self.nom}"

    @property
    def en_vigueur(self):
        return self.actif and self.annulee_le is None

    def clean(self):
        super().clean()
        erreurs = {}
        if self.mode == self.POURCENTAGE:
            if self.pourcentage is None:
                erreurs["pourcentage"] = "Indiquez un pourcentage (entre 0,01 et 100)."
            if self.montant_minor is not None:
                erreurs["montant_minor"] = "Une remise en pourcentage ne porte pas de montant."
        else:
            if not self.montant_minor:
                erreurs["montant_minor"] = "Indiquez un montant positif."
            if self.pourcentage is not None:
                erreurs["pourcentage"] = "Une remise en montant fixe ne porte pas de pourcentage."
        if self.debut and self.fin and self.debut > self.fin:
            erreurs["fin"] = "La fin précède le début."
        if self.categorie == self.FRATRIE and not self.rang_enfant_min:
            erreurs["rang_enfant_min"] = "Indiquez à partir de quel enfant la remise s'applique (2 au minimum)."
        if self.categorie != self.FRATRIE and self.rang_enfant_min:
            erreurs["rang_enfant_min"] = "Le rang d'enfant ne concerne que la remise « fratrie »."
        if self.categorie == self.ANTICIPE and not self.date_limite_paiement:
            erreurs["date_limite_paiement"] = "Indiquez la date limite du paiement anticipé."
        if self.categorie != self.ANTICIPE and self.date_limite_paiement:
            erreurs["date_limite_paiement"] = "La date limite ne concerne que le paiement anticipé."
        if self.genre == self.EXONERATION and self.categorie in (self.FRATRIE, self.ANTICIPE, self.INTEGRAL):
            erreurs["categorie"] = "Une exonération n'est pas une remise commerciale : choisissez un motif d'exonération."
        if (self.genre == self.EXONERATION or self.categorie in self.JUSTIFICATION_REQUISE) and not (self.justification or "").strip():
            erreurs["justification"] = "Une exonération ou une décision individuelle doit être justifiée."
        if self.student_id and self.famille_id:
            erreurs["famille"] = "Choisissez un élève OU une famille, pas les deux."
        for champ in ("school_year", "level", "class_obj", "student"):
            objet = getattr(self, champ, None)
            if objet is not None and getattr(objet, "school_id", self.academy_id) != self.academy_id:
                erreurs[champ] = "Cet élément appartient à une autre académie."
        if erreurs:
            raise ValidationError(erreurs)

    def save(self, *args, **kwargs):
        self.devise = getattr(self.academy, "currency_code", "") or self.devise
        self.full_clean()
        super().save(*args, **kwargs)


class EcheanceEleve(models.Model):
    """Échéance personnelle : remplace les échéances standard d'un tarif pour un élève et une année."""

    academy = models.ForeignKey("schools.School", on_delete=models.CASCADE, related_name="+")
    student = models.ForeignKey("students.Student", on_delete=models.PROTECT, related_name="echeances_personnelles")
    fee_schedule = models.ForeignKey("payments.FeeSchedule", on_delete=models.PROTECT, related_name="echeances_personnelles")
    school_year = models.ForeignKey("schools.SchoolYear", on_delete=models.PROTECT, related_name="+")
    label = models.CharField(max_length=80)
    due_date = models.DateField()
    amount_minor = models.BigIntegerField()
    order = models.PositiveSmallIntegerField(default=0)
    actif = models.BooleanField(default=True)
    motif = models.CharField(max_length=255, blank=True)
    cree_par = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    cree_le = models.DateTimeField(auto_now_add=True)
    modifie_le = models.DateTimeField(auto_now=True)

    # Lu par le moteur : une échéance personnelle est reconnaissable partout.
    est_personnelle = True

    class Meta:
        verbose_name = "Échéance personnelle"
        verbose_name_plural = "Échéanciers personnels"
        ordering = ["student", "fee_schedule", "due_date", "order"]
        constraints = [
            models.CheckConstraint(condition=models.Q(amount_minor__gt=0), name="echeance_eleve_montant_positif"),
            models.UniqueConstraint(fields=["student", "fee_schedule", "school_year", "due_date"],
                                    condition=models.Q(actif=True), name="uniq_echeance_eleve_active"),
        ]

    def __str__(self):
        return f"{self.student_id} · {self.fee_schedule_id} · {self.label} · {self.due_date}"

    def clean(self):
        super().clean()
        if self.student_id and self.student.school_id != self.academy_id:
            raise ValidationError({"student": "Élève d'une autre académie."})
        if self.fee_schedule_id and self.fee_schedule.academy_id != self.academy_id:
            raise ValidationError({"fee_schedule": "Tarif d'une autre académie."})
        if self.school_year_id and self.school_year.school_id != self.academy_id:
            raise ValidationError({"school_year": "Année d'une autre académie."})

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class JournalFinancier(models.Model):
    """Historique inaltérable des décisions financières (ajout seul)."""

    TARIF, REGLE, ECHEANCIER, DISPOSITION = "tarif", "regle", "echeancier", "disposition"
    OBJETS = [(TARIF, "Tarif"), (REGLE, "Remise ou exonération"), (ECHEANCIER, "Échéancier personnel"),
              (DISPOSITION, "Disposition d'élève")]
    ACTIONS = [("creation", "Création"), ("modification", "Modification"), ("annulation", "Annulation"),
               ("reactivation", "Réactivation"), ("desactivation", "Désactivation"), ("suppression", "Suppression")]

    academy = models.ForeignKey("schools.School", on_delete=models.CASCADE, related_name="journal_financier")
    objet = models.CharField(max_length=12, choices=OBJETS)
    objet_id = models.PositiveIntegerField(null=True, blank=True)
    student = models.ForeignKey("students.Student", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    action = models.CharField(max_length=14, choices=ACTIONS)
    description = models.CharField(max_length=255)
    avant = models.JSONField(default=dict, blank=True)
    apres = models.JSONField(default=dict, blank=True)
    motif = models.CharField(max_length=255, blank=True)
    auteur = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    auteur_email = models.EmailField(blank=True)
    le = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Entrée du journal financier"
        verbose_name_plural = "Journal financier"
        ordering = ["-le", "-pk"]
        indexes = [models.Index(fields=["academy", "objet", "objet_id"]), models.Index(fields=["student", "le"])]

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError("Le journal financier ne se modifie pas.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Le journal financier ne se supprime pas.")
