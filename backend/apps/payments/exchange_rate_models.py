"""
apps/payments/exchange_rate_models.py — Taux de change : autorité unique.

PROBLÈME RÉSOLU (P1 — juillet 2026)
------------------------------------
Sur /superadmin/payments, sélectionner « Toutes les Académies » additionnait
directement les montants FEBA (francs CFA) et FEBA FHA (dollars) :
2 850 000 FCFA + 601,50 $ devenait « 2 850 601,5 », un nombre qui n'a
aucun sens — ni en francs, ni en dollars, ni dans aucune unité.

`apps.core.currency.totals_by_currency` empêche déjà l'addition directe de
deux devises (elle lève une erreur). C'était juste pour un total détaillé
par devise, mais insuffisant pour la vue consolidée demandée : un
superadmin qui pilote deux académies dans deux monnaies a aussi besoin
d'UN chiffre unique, converti, pour son tableau de bord global.

Ce module ajoute donc la brique manquante : un taux de change EXPLICITE,
daté et traçable, qui sert de base à `apps.core.currency_conversion`.

RÈGLES
------
1. Le taux est un enregistrement, pas une constante codée en dur : il a
   une date d'effet, une source, et une histoire. On peut toujours
   répondre à « quel taux a servi pour ce total du 12 mars ? ».
2. On ne stocke qu'un sens (base → quote) : le sens inverse se déduit par
   division, jamais par une seconde saisie qui pourrait diverger.
3. En l'absence de taux enregistré, le service de conversion retombe sur
   `settings.FALLBACK_EXCHANGE_RATES` — mais le signale explicitement
   (`is_fallback=True`) partout où le taux est restitué à l'écran. Un taux
   par défaut silencieux serait aussi trompeur que l'addition qu'il
   remplace.
"""
from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from apps.accounts.models import CustomUser


class ExchangeRateQuerySet(models.QuerySet):
    def effective_on(self, on_date):
        return self.filter(effective_date__lte=on_date).order_by("-effective_date", "-created_at")

    def latest_for_pair(self, base_currency, quote_currency, on_date=None):
        on_date = on_date or timezone.localdate()
        return self.filter(
            base_currency=base_currency.upper(), quote_currency=quote_currency.upper(),
        ).effective_on(on_date).first()


class ExchangeRate(models.Model):
    """
    Taux de conversion `1 base_currency = rate quote_currency`, daté.

    Exemple : base_currency="USD", quote_currency="XOF", rate=600 signifie
    1 USD = 600 XOF — exactement l'exemple donné dans la demande initiale.
    """

    base_currency = models.CharField(max_length=3, help_text="Devise source, ex. USD.")
    quote_currency = models.CharField(max_length=3, help_text="Devise cible, ex. XOF.")
    rate = models.DecimalField(
        max_digits=18, decimal_places=6,
        help_text="Combien d'unités de quote_currency pour 1 unité de base_currency.",
    )
    effective_date = models.DateField(
        default=timezone.localdate,
        help_text="Date à partir de laquelle ce taux s'applique.",
    )
    source = models.CharField(
        max_length=100, blank=True,
        help_text="D'où vient ce taux (ex. « BCEAO », « saisie manuelle »).",
    )
    note = models.CharField(max_length=255, blank=True)
    created_by = models.ForeignKey(
        CustomUser, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="exchange_rates_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    objects = ExchangeRateQuerySet.as_manager()

    class Meta:
        verbose_name = "Taux de change"
        verbose_name_plural = "Taux de change"
        ordering = ["-effective_date", "-created_at"]
        constraints = [
            models.CheckConstraint(check=models.Q(rate__gt=0), name="exchange_rate_positive"),
        ]
        indexes = [
            models.Index(fields=["base_currency", "quote_currency", "effective_date"]),
        ]

    def __str__(self):
        return f"1 {self.base_currency} = {self.rate} {self.quote_currency} (au {self.effective_date})"

    def clean(self):
        super().clean()
        if self.base_currency and self.quote_currency and self.base_currency.upper() == self.quote_currency.upper():
            raise ValidationError("La devise source et la devise cible doivent être différentes.")
        try:
            if self.rate is not None and Decimal(self.rate) <= 0:
                raise ValidationError({"rate": "Le taux doit être strictement positif."})
        except InvalidOperation:
            raise ValidationError({"rate": "Taux invalide."})

    def save(self, *args, **kwargs):
        self.base_currency = (self.base_currency or "").upper()
        self.quote_currency = (self.quote_currency or "").upper()
        self.full_clean()
        super().save(*args, **kwargs)
