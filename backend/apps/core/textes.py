"""Textes déjà enregistrés : le tiret cadratin n'est pas réécrit en base, seulement à l'affichage."""


def sans_tiret(texte):
    return texte.replace(chr(0x2014), "-") if isinstance(texte, str) else texte
