"""
apps/core/currency.py — Devise, montants et formatage. Source unique.

PROBLÈME RÉSOLU (P0)
--------------------
Les montants étaient stockés sans devise et affichés avec « FCFA » codé en
dur, à onze endroits du frontend et quatre du backend. FEBA French Heritage
Academy facture en dollars des États-Unis : chaque reçu, chaque statistique
et chaque export de cette académie annonçait donc une devise qui n'est pas
la sienne. Le montant était juste, l'unité fausse — le pire des deux
mondes, parce que rien ne le signale.

TROIS PRINCIPES
---------------

1. **La devise est imposée par l'académie propriétaire, jamais par le
   client.** Ni la langue du navigateur, ni un symbole envoyé par React, ni
   un champ de formulaire ne peuvent la changer. `School.currency_code` est
   la seule autorité.

2. **Le montant de référence est un ENTIER en unité mineure.** Un dollar
   vaut 100 cents ; un franc CFA n'a pas de subdivision et vaut 1. Stocker
   un flottant introduirait des erreurs d'arrondi invisibles jusqu'au jour
   où un solde tombe à 0,004 au lieu de 0. `Decimal` reste exposé pour la
   lisibilité, mais l'entier fait foi.

3. **On n'additionne jamais deux devises.** 1 000 FCFA + 10 USD n'a aucun
   sens. Les totaux consolidés sont donc rendus PAR DEVISE, et toute
   tentative d'agrégation mixte lève une erreur explicite plutôt que de
   produire un nombre convaincant et faux.
"""
from decimal import Decimal, ROUND_HALF_UP

from django.core.exceptions import ValidationError


class Currency:
    """
    Une devise et ses règles de rendu.

    `decimal_places` n'est pas cosmétique : c'est lui qui définit l'unité
    mineure. USD a 2 décimales, donc 100 cents pour un dollar ; XOF en a 0,
    donc l'unité mineure EST le franc. Se tromper de facteur multiplierait
    ou diviserait tous les montants par cent.
    """

    def __init__(self, code, symbol, name, decimal_places, locale,
                 symbol_before=True, group_separator=",", decimal_separator="."):
        self.code = code
        self.symbol = symbol
        self.name = name
        self.decimal_places = decimal_places
        self.locale = locale
        self.symbol_before = symbol_before
        self.group_separator = group_separator
        self.decimal_separator = decimal_separator

    @property
    def minor_units_per_unit(self):
        return 10 ** self.decimal_places

    def to_minor(self, amount):
        """
        Convertit un montant lisible en entier d'unité mineure.

        L'arrondi est explicitement `ROUND_HALF_UP` : c'est la règle
        comptable attendue par les familles et les auditeurs, alors que
        l'arrondi par défaut de Python (au pair le plus proche) transforme
        2,5 en 2 — surprenant sur une facture.
        """
        if amount is None:
            return None
        value = Decimal(str(amount))
        return int((value * self.minor_units_per_unit).quantize(Decimal("1"), rounding=ROUND_HALF_UP))

    def to_decimal(self, amount_minor):
        """Convertit un entier d'unité mineure en montant lisible."""
        if amount_minor is None:
            return None
        quantum = Decimal(1).scaleb(-self.decimal_places)
        return (Decimal(amount_minor) / self.minor_units_per_unit).quantize(quantum)

    def format(self, amount_minor, with_symbol=True):
        """
        Rendu humain d'un montant, à partir de l'entier d'unité mineure.

        Le symbole se place AVANT en dollars (`$1,250.00`) et APRÈS en
        francs CFA (`1 250 FCFA`) : c'est l'usage de chaque zone, et
        l'inverser suffit à faire douter un parent de la facture qu'il lit.
        """
        if amount_minor is None:
            return ""
        value = self.to_decimal(amount_minor)
        negative = value < 0
        digits = f"{abs(value):,.{self.decimal_places}f}"
        digits = digits.replace(",", "\x00").replace(".", self.decimal_separator)
        digits = digits.replace("\x00", self.group_separator)
        if not with_symbol:
            return f"-{digits}" if negative else digits
        rendered = f"{self.symbol}{digits}" if self.symbol_before else f"{digits} {self.symbol}"
        return f"-{rendered}" if negative else rendered

    def __repr__(self):  # pragma: no cover — confort de débogage
        return f"<Currency {self.code}>"


#: Devises prises en charge. Ajouter une académie dans une nouvelle zone
#: monétaire se fait ICI, pas en dispersant des symboles dans les écrans.
CURRENCIES = {
    "XOF": Currency(
        code="XOF", symbol="FCFA", name="Franc CFA BCEAO",
        decimal_places=0, locale="fr-BJ",
        # Le séparateur de milliers français est une ESPACE FINE INSÉCABLE
        # (U+202F), pas une espace ordinaire : elle empêche « 50 » et « 000 »
        # d'être coupés en fin de ligne sur un reçu ou dans un tableau.
        symbol_before=False, group_separator="\u202f", decimal_separator=",",
    ),
    "USD": Currency(
        code="USD", symbol="$", name="Dollar des États-Unis",
        decimal_places=2, locale="en-US",
        symbol_before=True, group_separator=",", decimal_separator=".",
    ),
}

DEFAULT_CURRENCY = "XOF"

#: Choix proposés à l'administration. Une académie ne peut pas se voir
#: attribuer une devise absente du registre : le formatage n'existerait pas.
CURRENCY_CHOICES = [(code, f"{c.code} — {c.name}") for code, c in CURRENCIES.items()]


def get_currency(code):
    """
    Devise correspondant au code, ou erreur explicite.

    On préfère échouer bruyamment plutôt que retomber sur une devise par
    défaut : un montant affiché dans la mauvaise unité est indétectable à
    l'œil, alors qu'une exception se voit tout de suite.
    """
    currency = CURRENCIES.get((code or "").upper())
    if currency is None:
        raise ValidationError(
            f"Devise inconnue : « {code} ». Devises prises en charge : "
            f"{', '.join(sorted(CURRENCIES))}."
        )
    return currency


def currency_for(academy):
    """Devise de l'académie propriétaire — la seule autorité qui compte."""
    if academy is None:
        return get_currency(DEFAULT_CURRENCY)
    return get_currency(getattr(academy, "currency_code", None) or DEFAULT_CURRENCY)


class Money:
    """
    Un montant ET sa devise, indissociables.

    C'est le point du module : un nombre seul ne veut rien dire. Tant que
    les deux voyagent ensemble, il devient impossible d'additionner par
    inadvertance des dollars et des francs — l'opération lève une erreur au
    lieu de produire un total plausible.
    """

    __slots__ = ("amount_minor", "currency")

    def __init__(self, amount_minor, currency):
        self.amount_minor = int(amount_minor or 0)
        self.currency = currency if isinstance(currency, Currency) else get_currency(currency)

    @classmethod
    def from_decimal(cls, amount, currency):
        currency = currency if isinstance(currency, Currency) else get_currency(currency)
        return cls(currency.to_minor(amount), currency)

    @property
    def amount(self):
        return self.currency.to_decimal(self.amount_minor)

    def formatted(self, with_symbol=True):
        return self.currency.format(self.amount_minor, with_symbol=with_symbol)

    def _assert_same_currency(self, other):
        if self.currency.code != other.currency.code:
            raise ValidationError(
                f"Addition impossible entre {self.currency.code} et "
                f"{other.currency.code} : ces deux devises n'ont pas de taux "
                f"de conversion défini dans l'application. Présentez les "
                f"totaux séparément."
            )

    def __add__(self, other):
        self._assert_same_currency(other)
        return Money(self.amount_minor + other.amount_minor, self.currency)

    def __sub__(self, other):
        self._assert_same_currency(other)
        return Money(self.amount_minor - other.amount_minor, self.currency)

    def __eq__(self, other):
        return (
            isinstance(other, Money)
            and self.currency.code == other.currency.code
            and self.amount_minor == other.amount_minor
        )

    def __hash__(self):
        return hash((self.currency.code, self.amount_minor))

    def __repr__(self):  # pragma: no cover
        return f"<Money {self.formatted()}>"


def totals_by_currency(rows, amount_attr="amount_minor", currency_attr="currency"):
    """
    Totaux ventilés PAR DEVISE.

    Renvoie un dictionnaire `{code: Money}` plutôt qu'un nombre unique.
    C'est délibérément moins pratique à afficher : un total consolidé
    « toutes académies » ne DOIT pas se réduire à un seul chiffre quand les
    académies ne facturent pas dans la même monnaie.
    """
    totals = {}
    for row in rows:
        code = (getattr(row, currency_attr, None) or DEFAULT_CURRENCY).upper()
        amount = getattr(row, amount_attr, 0) or 0
        current = totals.get(code)
        totals[code] = Money((current.amount_minor if current else 0) + amount, code)
    return totals


def format_totals(totals):
    """Rendu lisible d'un dictionnaire de totaux : `['$12,450.00', '1 500 000 FCFA']`."""
    return [money.formatted() for _, money in sorted(totals.items())]
