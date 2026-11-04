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
    # Bornes d'une clé BigAutoField : au-delà, PostgreSQL refuse la requête (erreur 500).
    if isinstance(valeur, int):
        return valeur if 0 < valeur < 2 ** 63 else None
    if isinstance(valeur, str) and valeur.strip().isdigit():
        return identifiant(int(valeur))
    return None


def liste_identifiants(valeurs):
    """Liste d'identifiants reçue du client : les entiers valides, ou None si la forme est fausse."""
    if not isinstance(valeurs, list):
        return None
    ids = [identifiant(v) for v in valeurs]
    return None if None in ids else ids


def date_field(value, name):
    """Date AAAA-MM-JJ venue du client : None si absente, 400 si invalide.

    `parse_date` lève ValueError pour une date bien formée mais impossible
    (« 2026-02-30 ») et TypeError pour une valeur qui n'est pas un texte :
    sans ce contrôle, l'une et l'autre donnaient une erreur 500.
    """
    from django.utils.dateparse import parse_date
    if value is None or value == "":
        return None
    parsed = None
    if isinstance(value, str):
        try:
            parsed = parse_date(value.strip())
        except ValueError:
            parsed = None
    if parsed is None:
        raise ValidationError({name: "Date invalide : format attendu AAAA-MM-JJ."})
    return parsed


def datetime_field(value, name):
    """Date et heure ISO 8601 venue du client : None si absente, 400 si invalide."""
    from django.utils.dateparse import parse_datetime
    if value is None or value == "":
        return None
    parsed = None
    if isinstance(value, str):
        try:
            parsed = parse_datetime(value.strip())
        except ValueError:
            parsed = None
    if parsed is None:
        raise ValidationError({name: "Date et heure invalides : format ISO 8601 attendu."})
    return parsed
