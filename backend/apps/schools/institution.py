"""
apps/schools/institution.py — Coordonnées INSTITUTIONNELLES du groupe FEBA.

POURQUOI CE MODULE EXISTE
-------------------------
Un reçu d'inscription émis pour un élève portait en en-tête
« Tél: 0196697363 ». Ce numéro n'était écrit nulle part dans le code : il
venait de la base, du champ `School.phone`, saisi un jour par un
administrateur depuis l'écran « Paramètres ». Le générateur de PDF le
recopiait fidèlement — il faisait exactement ce qu'on lui demandait.

C'est la nature du défaut qui compte ici. Le numéro affiché sur un document
officiel n'est pas une préférence d'affichage : c'est la coordonnée par
laquelle une famille rappelle l'établissement au sujet d'un paiement, d'un
bulletin ou d'un certificat. Tant qu'il est stocké dans une colonne
administrable par entité, il a autant de valeurs qu'il y a d'entités, de
profils et d'écrans de saisie — et il dérive silencieusement. Aucun test ne
peut le rattraper, parce qu'aucune valeur n'est techniquement fausse.

LA RÈGLE
--------
Le groupe éducatif FEBA a UN SEUL numéro institutionnel. Il est déclaré
ici, une fois, et TOUS les documents générés le lisent depuis ce module —
quel que soit l'utilisateur connecté, son rôle, son profil, l'académie
émettrice ou le chemin de génération.

CE QUE CE MODULE N'EST PAS
--------------------------
Ce n'est pas un « remplacement de chaîne ». `School.phone` continue
d'exister et reste administrable : c'est une donnée de gestion interne
légitime (joindre un campus). Ce qu'elle ne peut plus faire, c'est décider
de ce qui s'imprime sur une pièce officielle. La séparation est explicite :

    School.phone          → donnée de gestion, écran d'administration
    official_phone()      → identité institutionnelle, documents officiels

ROTATION
--------
Le numéro reste surchargeable par `FEBA_OFFICIAL_PHONE` (settings/env) pour
qu'un changement de ligne téléphonique ne demande pas une modification de
code. Une valeur retirée du service ne peut PAS être réintroduite : elle
figure dans `RETIRED_INSTITUTIONAL_PHONES` et le module refuse de la servir.
"""
from __future__ import annotations

import re

from django.conf import settings

#: Numéro institutionnel officiel du groupe éducatif FEBA.
#:
#: Valeur de référence, utilisée par tous les générateurs de documents.
#: Surchargeable par le réglage `FEBA_OFFICIAL_PHONE` (voir settings/base.py)
#: pour permettre une rotation sans modification de code.
OFFICIAL_PHONE = "0160011717"

#: Numéros institutionnels RETIRÉS DU SERVICE.
#:
#: Ils ont réellement figuré sur des documents émis ; ils ne doivent plus
#: jamais y apparaître. Cette liste n'est pas décorative : elle est
#: appliquée à l'exécution (`official_phone()` refuse de les servir),
#: utilisée pour nettoyer les champs libres hérités
#: (`strip_retired_phones()`) et vérifiée par les tests de non-régression.
RETIRED_INSTITUTIONAL_PHONES = (
    "0196697363",
)

#: Tout ce qui n'est pas un chiffre dans un numéro écrit à la main.
_NON_DIGITS = re.compile(r"\D+")

#: Un numéro tel qu'il peut apparaître dans un champ de texte libre :
#: chiffres séparés par des espaces, points, tirets ou barres obliques,
#: éventuellement précédé d'un indicatif international.
_LOOSE_PHONE = re.compile(r"(?:\+\s*\d{1,4}[\s.\-/]*)?(?:\d[\s.\-/]*){8,15}")


def digits(value) -> str:
    """
    Chiffres d'un numéro, sans mise en forme.

    « 01 96 69 73 63 », « 01.96.69.73.63 » et « 0196697363 » désignent le
    même numéro. Comparer les chaînes brutes laissait passer les deux
    premières écritures : un audit qui ne cherche que « 0196697363 »
    déclare propre un document où le numéro retiré est simplement espacé.
    """
    return _NON_DIGITS.sub("", str(value or ""))


def _significant(value) -> str:
    """
    Chiffres significatifs, indicatif pays et zéro initial retirés.

    « +229 01 96 69 73 63 », « 0196697363 » et « 196697363 » sont la même
    ligne téléphonique écrite de trois façons. Sans cette normalisation, un
    numéro retiré réapparaît simplement en le préfixant de son indicatif.
    """
    raw = digits(value)
    for prefix in ("00229", "229"):
        if raw.startswith(prefix) and len(raw) > len(prefix) + 6:
            raw = raw[len(prefix):]
            break
    return raw.lstrip("0")


#: Empreintes des numéros retirés, calculées une fois.
_RETIRED_SIGNATURES = frozenset(
    _significant(number) for number in RETIRED_INSTITUTIONAL_PHONES
)


def is_retired_phone(value) -> bool:
    """Vrai si `value` est un numéro institutionnel retiré du service."""
    signature = _significant(value)
    return bool(signature) and signature in _RETIRED_SIGNATURES


def official_phone() -> str:
    """
    Numéro institutionnel à imprimer sur TOUS les documents officiels.

    Un réglage `FEBA_OFFICIAL_PHONE` qui vaudrait un numéro retiré est
    ignoré au profit de la constante : une erreur de configuration ne doit
    pas remettre en circulation un numéro qui ne répond plus.
    """
    configured = str(getattr(settings, "FEBA_OFFICIAL_PHONE", "") or "").strip()
    if configured and not is_retired_phone(configured):
        return configured
    return OFFICIAL_PHONE


def strip_retired_phones(text) -> str:
    """
    Retire d'un texte libre tout numéro institutionnel hors service.

    `School.address` et `footer_text` sont des champs libres : ils
    contiennent parfois « Akpakpa, Cotonou — Tél 01 96 69 73 63 ». Le
    numéro y échappe à `official_phone()` puisqu'il ne passe pas par la
    colonne `phone`. On le retire du rendu, avec l'étiquette « Tél: » qui
    le précède éventuellement, plutôt que de le laisser contredire le
    numéro officiel imprimé deux centimètres plus loin.

    Les séparateurs orphelins laissés par la coupe sont recousus : une
    adresse ne doit pas sortir avec « Cotonou —  | contact@… ».
    """
    original = str(text or "")
    if not original:
        return ""

    def _replace(match):
        return "" if is_retired_phone(match.group(0)) else match.group(0)

    cleaned = _LOOSE_PHONE.sub(_replace, original)
    if cleaned == original:
        return original

    # Étiquette « Tél: » / « Tel. » / « Téléphone » restée sans numéro.
    cleaned = re.sub(
        r"(?i)\bt[ée]l[ée]?(?:phone)?\s*\.?\s*:?\s*(?=$|[|,;•\-–—])",
        "", cleaned,
    )
    # Séparateurs devenus orphelins, puis espaces et ponctuation en trop.
    cleaned = re.sub(r"\s*([|•])\s*(?=[|•]|$)", "", cleaned)
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    cleaned = re.sub(r"\s+([,;.])", r"\1", cleaned)
    cleaned = re.sub(r"[,;\-–—]\s*$", "", cleaned.strip())
    return cleaned.strip(" |•\t\n").strip()
