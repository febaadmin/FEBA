"""
apps/core/currency_conversion.py — Conversion explicite entre devises.

PROBLÈME RÉSOLU (P1 — juillet 2026)
------------------------------------
Sur /superadmin/payments, choisir « Toutes les Académies » (FEBA, en
francs CFA, ET FEBA FHA, en dollars) additionnait les deux montants tels
quels : 1 000 000 FCFA + 1 000 $ devenait « 1 001 000 ». `apps.core.currency`
empêche déjà cette addition directe au niveau de `Money.__add__` — mais
jusqu'ici, rien ne permettait de produire malgré tout le total consolidé
qu'un superadmin réclame légitimement pour piloter les deux académies à
la fois.

Ce module est CETTE brique manquante : il convertit explicitement un
montant d'une devise vers une autre, avec un taux daté et traçable, et
REND CETTE CONVERSION VISIBLE plutôt que de la cacher dans un total qui
semblerait juste.

RÈGLE ABSOLUE
-------------
Le frontend ne convertit jamais rien : il affiche ce que ce service a
calculé côté serveur. Une conversion refaite (même à l'identique) côté
navigateur créerait un deuxième calcul, donc un deuxième endroit où il
peut diverger du premier — exactement le problème que ce module existe
pour éliminer.
"""
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings
from django.utils import timezone

from apps.core.currency import Currency, Money, get_currency


class MissingExchangeRateError(Exception):
    """
    Levée quand aucun taux — enregistré ou de secours — ne permet de
    convertir entre deux devises.

    Volontairement UNE erreur explicite plutôt qu'un taux de 1:1 par
    défaut : un total consolidé silencieusement faux est pire qu'un
    écran qui dit clairement « impossible à consolider pour l'instant ».
    """

    def __init__(self, source_currency, target_currency):
        self.source_currency = source_currency
        self.target_currency = target_currency
        super().__init__(
            f"Aucun taux de change disponible pour convertir {source_currency} "
            f"vers {target_currency}. Ajoutez un taux dans "
            f"Paiements ▸ Taux de change, ou définissez "
            f"FALLBACK_EXCHANGE_RATES dans les réglages."
        )


@dataclass(frozen=True)
class RateInfo:
    """Un taux daté, avec sa provenance — ce que le spec appelle « le taux explicite »."""

    source_currency: str
    target_currency: str
    rate: Decimal          # combien d'unités cible pour 1 unité source
    rate_date: date
    is_fallback: bool      # True si issu du réglage de secours, pas d'un enregistrement daté
    is_inverted: bool = False  # True si dérivé d'un taux enregistré dans le sens inverse

    def as_dict(self):
        return {
            "source_currency": self.source_currency,
            "target_currency": self.target_currency,
            "rate": str(self.rate),
            "rate_date": self.rate_date.isoformat(),
            "is_fallback": self.is_fallback,
            "label": f"1 {self.source_currency} = {self.rate} {self.target_currency}",
        }


@dataclass(frozen=True)
class ConversionResult:
    """Le montant d'origine ET le montant converti — jamais l'un sans l'autre."""

    original: Money
    converted: Money
    rate_info: RateInfo | None  # None quand aucune conversion n'a été nécessaire (même devise)

    def as_dict(self):
        d = {
            "original_currency": self.original.currency.code,
            "original_amount": str(self.original.amount),
            "converted_currency": self.converted.currency.code,
            "converted_amount": str(self.converted.amount),
            "converted_formatted": self.converted.formatted(),
        }
        if self.rate_info is not None:
            d["conversion"] = self.rate_info.as_dict()
        return d


class CurrencyConversionService:
    """
    Source unique de conversion entre devises.

    Utilisation typique (totaux consolidés multi-académies) :

        service = CurrencyConversionService()
        result = service.convert(Money(100000, "USD"), "XOF")
        result.converted.formatted()   # -> "60 000 000 FCFA"
        result.rate_info.as_dict()     # -> {"rate": "600", "rate_date": ..., ...}
    """

    def __init__(self, on_date=None):
        self.on_date = on_date or timezone.localdate()

    def get_rate(self, source_currency, target_currency):
        """
        Renvoie un `RateInfo` pour convertir source_currency -> target_currency.

        Ordre de résolution :
          1. Taux enregistré (ExchangeRate) dans le sens demandé, le plus
             récent dont la date d'effet est passée ;
          2. Taux enregistré dans le sens INVERSE, alors inversé (1/rate) ;
          3. Taux de secours (`settings.FALLBACK_EXCHANGE_RATES`), signalé
             comme tel ;
          4. `MissingExchangeRateError`.
        """
        source_currency = (source_currency or "").upper()
        target_currency = (target_currency or "").upper()

        # Import tardif : évite une dépendance circulaire (payments importe
        # apps.core.currency ; apps.core ne doit pas importer payments au
        # chargement du module).
        from apps.payments.models import ExchangeRate

        direct = ExchangeRate.objects.latest_for_pair(source_currency, target_currency, self.on_date)
        if direct is not None:
            return RateInfo(
                source_currency=source_currency, target_currency=target_currency,
                rate=direct.rate, rate_date=direct.effective_date, is_fallback=False,
            )

        inverse = ExchangeRate.objects.latest_for_pair(target_currency, source_currency, self.on_date)
        if inverse is not None:
            inverted_rate = (Decimal(1) / inverse.rate).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)
            return RateInfo(
                source_currency=source_currency, target_currency=target_currency,
                rate=inverted_rate, rate_date=inverse.effective_date, is_fallback=False, is_inverted=True,
            )

        fallback_rates = getattr(settings, "FALLBACK_EXCHANGE_RATES", {})
        fallback = fallback_rates.get((source_currency, target_currency))
        if fallback is not None:
            return RateInfo(
                source_currency=source_currency, target_currency=target_currency,
                rate=Decimal(str(fallback)), rate_date=self.on_date, is_fallback=True,
            )
        inverse_fallback = fallback_rates.get((target_currency, source_currency))
        if inverse_fallback is not None:
            inverted_rate = (Decimal(1) / Decimal(str(inverse_fallback))).quantize(
                Decimal("0.000001"), rounding=ROUND_HALF_UP
            )
            return RateInfo(
                source_currency=source_currency, target_currency=target_currency,
                rate=inverted_rate, rate_date=self.on_date, is_fallback=True, is_inverted=True,
            )

        raise MissingExchangeRateError(source_currency, target_currency)

    def convert(self, money, target_currency_code):
        """
        Convertit un `Money` vers `target_currency_code`.

        Si `money` est déjà dans la devise cible, renvoie le même montant
        sans conversion ni taux (évite un « 1 XOF = 1 XOF » qui n'a pas de
        sens et ne trompe personne en laissant croire à une conversion
        réelle).
        """
        target_currency_code = (target_currency_code or "").upper()
        if money.currency.code == target_currency_code:
            return ConversionResult(original=money, converted=money, rate_info=None)

        rate_info = self.get_rate(money.currency.code, target_currency_code)
        target_currency = get_currency(target_currency_code)

        # Le taux s'applique en UNITÉ MAJEURE (1 USD = 600 XOF, pas 1 cent
        # = 600 XOF) : on repasse donc par `Money.amount` (Decimal lisible)
        # avant de reconvertir vers l'entier d'unité mineure cible.
        converted_major = (money.amount * rate_info.rate).quantize(
            Decimal(1).scaleb(-target_currency.decimal_places), rounding=ROUND_HALF_UP
        )
        converted_money = Money.from_decimal(converted_major, target_currency)
        return ConversionResult(original=money, converted=converted_money, rate_info=rate_info)


def consolidate(money_list, target_currency_code, on_date=None):
    """
    Convertit et additionne une liste de `Money` (devises potentiellement
    différentes) en un unique `Money` dans `target_currency_code`.

    Renvoie `(total: Money, conversions: list[ConversionResult])` — la
    liste des conversions réellement effectuées, pour affichage du détail
    (« Taux utilisé : 1 USD = 600 FCFA »). Une entrée de `money_list` déjà
    dans la devise cible n'apparaît pas dans `conversions` : il n'y a rien
    à expliquer pour elle.
    """
    service = CurrencyConversionService(on_date=on_date)
    target_currency = get_currency(target_currency_code)
    total = Money(0, target_currency)
    conversions = []
    for money in money_list:
        result = service.convert(money, target_currency_code)
        total = total + result.converted
        if result.rate_info is not None:
            conversions.append(result)
    return total, conversions
