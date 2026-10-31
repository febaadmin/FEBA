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
