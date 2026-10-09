"""
apps/core/age.py — Âge des élèves : UNE règle, UN endroit.

POURQUOI CE MODULE
------------------
L'âge n'était affiché nulle part dans les listes d'élèves. L'ajouter écran
par écran aurait produit autant de calculs que d'écrans — et des calculs
qui divergent (différence d'années sans tenir compte de l'anniversaire,
« aujourd'hui » pris dans le fuseau du navigateur plutôt que dans celui
de l'académie…). Tous les serializers passent donc par ce module, et le
frontend se contente d'AFFICHER la valeur reçue.

CONVENTION
----------
- L'âge est exprimé en **années révolues** : on n'a 8 ans qu'à partir du
  jour de son 8e anniversaire.
- « Aujourd'hui » est la date locale **de l'académie** (`School.timezone`) :
  à 21 h à New York, FEBA FHA est encore la veille alors que le serveur
  (UTC) est déjà le lendemain. Un élève qui fête son anniversaire ce
  jour-là ne doit pas « vieillir » quelques heures trop tôt.
- Né un **29 février** : les années non bissextiles, l'anniversaire est
  considéré comme atteint le **1er mars** (on compare (mois, jour) ; le
  28 février, (2, 28) < (2, 29) donc l'anniversaire n'est pas encore
  passé). C'est la convention retenue par la plupart des états civils
  pour la majorité légale ; elle est documentée ici pour qu'elle reste la
  même partout.

DONNÉES ABSENTES OU INCOHÉRENTES
--------------------------------
Aucune valeur n'est inventée :

    status = "ok"        âge calculé
    status = "missing"   date de naissance non renseignée → « Non renseigné »
    status = "invalid"   date de naissance dans le futur → anomalie signalée,
                         jamais un âge négatif

Aucun champ « âge » n'est stocké en base : il se périmerait chaque jour.
"""
from datetime import date, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.utils import timezone

AGE_OK = "ok"
AGE_MISSING = "missing"
AGE_INVALID = "invalid"

#: Plus ancienne date de naissance plausible pour un élève. En deçà, il
#: s'agit d'une erreur de saisie (« 0201 » au lieu de « 2015 »), pas d'un
#: élève de 1 800 ans.
MIN_BIRTH_DATE = date(1900, 1, 1)


def academy_today(academy=None, now=None):
    """
    Date du jour dans le fuseau de l'académie (sinon celui du projet).

    `now` permet aux tests de fixer l'instant de référence.
    """
    now = now or timezone.now()
    tz_name = getattr(academy, "timezone", None) or None
    if tz_name:
        try:
            return timezone.localtime(now, ZoneInfo(tz_name)).date()
        except (ZoneInfoNotFoundError, ValueError):
            pass
    return timezone.localtime(now).date()


def _as_date(value):
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def compute_age(birth_date, on):
    """
    Âge en années révolues au jour `on`, ou None si non calculable.

    Ne renvoie JAMAIS un âge négatif : une naissance postérieure à `on`
    est une anomalie de données, signalée par `age_info`.
    """
    birth_date = _as_date(birth_date)
    on = _as_date(on)
    if birth_date is None or on is None or birth_date > on:
        return None
    years = on.year - birth_date.year
    if (on.month, on.day) < (birth_date.month, birth_date.day):
        years -= 1
    return years


def age_info(birth_date, academy=None, on=None):
    """
    `{"age": int | None, "age_status": "ok" | "missing" | "invalid"}`.

    `on` : date de référence (par défaut : aujourd'hui dans le fuseau de
    l'académie).
    """
    birth = _as_date(birth_date)
    if birth is None:
        return {"age": None, "age_status": AGE_MISSING}
    reference = _as_date(on) or academy_today(academy)
    if birth > reference or birth < MIN_BIRTH_DATE:
        return {"age": None, "age_status": AGE_INVALID}
    return {"age": compute_age(birth, reference), "age_status": AGE_OK}


def age_label(info):
    """Libellé français unique pour les exports et les PDF."""
    if info["age_status"] == AGE_OK:
        age = info["age"]
        return f"{age} an" if age in (0, 1) else f"{age} ans"
    if info["age_status"] == AGE_INVALID:
        return "Date de naissance invalide"
    return "Non renseigné"


def validate_birth_date(value, academy=None):
    """
    Message d'erreur si `value` n'est pas une date de naissance acceptable,
    sinon None. Partagé par les serializers et les imports.
    """
    value = _as_date(value)
    if value is None:
        return None
    if value > academy_today(academy):
        return "La date de naissance ne peut pas être dans le futur."
    if value < MIN_BIRTH_DATE:
        return "Date de naissance invraisemblable : vérifiez l'année saisie."
    return None
