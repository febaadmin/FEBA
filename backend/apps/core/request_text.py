"""
Lecture d'un champ TEXTE dans le corps d'une requête.

`request.data.get("x", "").strip()` suppose une chaîne. Un client qui envoie
un objet, un nombre ou une liste provoquait AttributeError, donc une erreur 500
et un incident, au lieu d'un refus. Le contrat est : absent ou null = vide,
chaîne = chaîne nettoyée, autre type = 400.
"""
from rest_framework.exceptions import ValidationError


def text_field(data, name):
    value = data.get(name)
    if value is None:
        return ""
    if not isinstance(value, str):
        raise ValidationError({name: "Ce champ doit être un texte."})
    return value.strip()


def checked_upload(upload):
    """Pièce jointe : format réel et taille contrôlés, 400 sinon."""
    from apps.notifications.attachments import AttachmentError, validate_uploads
    if upload is None:
        return None
    try:
        validate_uploads([upload])
    except AttachmentError as exc:
        raise ValidationError({"attachment": str(exc)})
    upload.seek(0)
    return upload


def identifiant(valeur):
    """Identifiant reçu du client : un entier, sinon None (aucun objet ne correspond)."""
    if isinstance(valeur, bool):
        return None
    if isinstance(valeur, int):
        return valeur
    if isinstance(valeur, str) and valeur.strip().isdigit():
        return int(valeur)
    return None


def liste_identifiants(valeurs):
    """Liste d'identifiants reçue du client : les entiers valides, ou None si la forme est fausse."""
    if not isinstance(valeurs, list):
        return None
    ids = [identifiant(v) for v in valeurs]
    return None if None in ids else ids
