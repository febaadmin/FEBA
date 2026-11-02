"""Cellule de CSV : un tableur exécuterait un texte commençant par un signe de formule."""
import re

NOMBRE = re.compile(r"^[+-]?[\d\s.,]+$")
SIGNES = ("=", "+", "-", "@", "\t", "\r")


def cellule(valeur):
    """Neutralise une formule. Les nombres et téléphones (-5, +229 97...) restent intacts."""
    if not isinstance(valeur, str) or not valeur.startswith(SIGNES) or NOMBRE.match(valeur):
        return valeur
    return f"'{valeur}"
