"""
Correction automatique des types objectifs. Renvoie None pour une question à
corriger par l'enseignant : aucune réponse ouverte n'est notée automatiquement.
Règles de points partiels : docs/EXAMENS_EN_LIGNE.md.
"""
import unicodedata
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

CENT = Decimal("0.01")


def _arrondi(valeur):
    return valeur.quantize(CENT, rounding=ROUND_HALF_UP)


def _texte(valeur, casse=False):
    if not isinstance(valeur, str):
        return None
    propre = " ".join(valeur.split())
    return unicodedata.normalize("NFC", propre if casse else propre.casefold())


def _nombre(valeur):
    if isinstance(valeur, bool) or valeur is None:
        return None
    try:
        return Decimal(str(valeur).replace(",", "."))
    except InvalidOperation:
        return None


def fraction(type_question, corrige, valeur):
    """Fraction de la note entre 0 et 1, ou None si la correction est manuelle."""
    if type_question in ("ouverte", "fichier"):
        return None
    if valeur is None:
        return Decimal(0)
    if type_question == "qcm_unique":
        return Decimal(1 if valeur == corrige.get("bonne") else 0)
    if type_question == "vrai_faux":
        return Decimal(1 if valeur is corrige.get("valeur") else 0)
    if type_question == "qcm_multiple":
        bonnes = set(corrige.get("bonnes", []))
        if not isinstance(valeur, list) or not bonnes:
            return Decimal(0)
        choisies = {v for v in valeur if isinstance(v, (str, int))}
        return max(Decimal(0), Decimal(len(choisies & bonnes) - len(choisies - bonnes)) / len(bonnes))
    if type_question == "courte":
        casse = bool(corrige.get("casse"))
        acceptees = {_texte(a, casse) for a in corrige.get("acceptees", [])}
        return Decimal(1 if _texte(valeur, casse) in acceptees else 0)
    if type_question == "numerique":
        attendu, saisi = _nombre(corrige.get("valeur")), _nombre(valeur)
        if attendu is None or saisi is None:
            return Decimal(0)
        return Decimal(1 if abs(attendu - saisi) <= (_nombre(corrige.get("tolerance")) or 0) else 0)
    if type_question == "trous":
        attendus = corrige.get("reponses", [])
        if not isinstance(valeur, list) or not attendus:
            return Decimal(0)
        bons = sum(1 for i, acceptees in enumerate(attendus)
                   if i < len(valeur) and _texte(valeur[i]) in {_texte(a) for a in acceptees})
        return Decimal(bons) / len(attendus)
    if type_question == "association":
        paires = corrige.get("paires", {})
        if not isinstance(valeur, dict) or not paires:
            return Decimal(0)
        return Decimal(sum(1 for k, v in paires.items() if valeur.get(k) == v)) / len(paires)
    if type_question == "classement":
        ordre = corrige.get("ordre", [])
        if not isinstance(valeur, list) or not ordre:
            return Decimal(0)
        return Decimal(sum(1 for i, e in enumerate(ordre) if i < len(valeur) and valeur[i] == e)) / len(ordre)
    return None


def points_auto(type_question, corrige, valeur, points):
    part = fraction(type_question, corrige, valeur)
    return None if part is None else _arrondi(part * Decimal(points))


def valider_question(type_question, contenu, corrige):
    """Erreurs de structure d'une question, avant enregistrement."""
    erreurs = []
    ids = [c.get("id") for c in contenu.get("choix", []) if isinstance(c, dict)]
    if type_question in ("qcm_unique", "qcm_multiple") and len(ids) < 2:
        erreurs.append("Il faut au moins deux choix.")
    if type_question == "qcm_unique" and corrige.get("bonne") not in ids:
        erreurs.append("Indiquez la bonne réponse parmi les choix.")
    if type_question == "qcm_multiple" and (not corrige.get("bonnes") or not set(corrige["bonnes"]) <= set(ids)):
        erreurs.append("Indiquez les bonnes réponses parmi les choix.")
    if type_question == "vrai_faux" and not isinstance(corrige.get("valeur"), bool):
        erreurs.append("Indiquez si l'affirmation est vraie ou fausse.")
    if type_question == "courte" and not corrige.get("acceptees"):
        erreurs.append("Indiquez au moins une réponse acceptée.")
    if type_question == "numerique" and _nombre(corrige.get("valeur")) is None:
        erreurs.append("Indiquez la valeur attendue.")
    if type_question == "trous" and not corrige.get("reponses"):
        erreurs.append("Indiquez les réponses de chaque trou.")
    if type_question == "association" and not corrige.get("paires"):
        erreurs.append("Indiquez les paires attendues.")
    if type_question == "classement" and not corrige.get("ordre"):
        erreurs.append("Indiquez l'ordre attendu.")
    return erreurs
