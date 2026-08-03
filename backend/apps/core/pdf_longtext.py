"""
P0 — La règle unique de rendu d'un texte long dans un PDF.

LE DÉFAUT REPRODUIT
-------------------
La fiche d'inscription FEBA FHA se construit avec un `Table` de deux
colonnes, une ligne par champ. ReportLab ne coupe pas une ligne de tableau
en deux pages : si le contenu d'une seule cellule dépasse la hauteur utile
d'une page, la mise en page ne « déborde » pas, elle **échoue** :

    LayoutError: Flowable <Table 5 rows x 2 cols (tallest row 905)> with
    cell(0,0) ... tallest cell 905.1 points, too large on page 2

Autrement dit : un parent qui écrivait un message de 5 000 caractères
rendait la fiche PDF impossible à produire. L'appel était enveloppé dans
un `try/except`, donc rien ne remontait à l'écran — la demande était
enregistrée, et la fiche officielle n'existait simplement pas.

Ce module rassemble les trois décisions qui évitent cela, pour que la
fiche FHA, la fiche de préinscription FEBA et le rapport mensuel les
partagent au lieu de les redécouvrir chacun de son côté.

1. `long_text_table()` — un tableau autorisé à se couper AU MILIEU d'une
   ligne (`splitByRow`, `splitInRow`). Une réponse de dix pages s'étale
   sur dix pages au lieu de faire échouer le document.

2. `pdf_paragraph()` — l'échappement. ReportLab lit le contenu d'un
   `Paragraph` comme du mini-XML : « Coût & frais » ou « <plus de 3 ans> »
   provoquait une erreur d'analyse, ou pire, l'amputation silencieuse du
   fragment entre chevrons. On échappe donc `&`, `<` et `>`, puis on
   rétablit les seuls retours à la ligne sous forme de `<br/>`.

3. `keep_with_next()` — un titre de section ne reste solidaire que de sa
   PREMIÈRE ligne. `KeepTogether` sur une section entière rendait
   insécable un bloc parfois plus haut qu'une page : le même échec
   revenait par une autre porte.

Ce que ce module ne fait jamais : tronquer, réduire la police en dessous
du lisible, poser une hauteur fixe, ou remplacer une fin de texte par des
points de suspension. Une fiche officielle amputée est plus dangereuse
qu'une fiche longue, parce que rien n'y signale ce qui manque.
"""
from __future__ import annotations

import html

from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import CondPageBreak, KeepTogether, Paragraph, Table

#: Taille minimale acceptée dans un document officiel. En dessous, le texte
#: est présent mais illisible — ce qui revient à l'avoir supprimé, en pire :
#: on croit l'avoir imprimé.
MIN_READABLE_FONT_SIZE = 7.0

#: Caractères que certains claviers produisent et que les polices
#: embarquées ne couvrent pas toutes. On les remplace par un équivalent
#: présent dans la police plutôt que de laisser un carré noir.
SUBSTITUTIONS = {
    " ": " ",   # espace insécable
    " ": " ",   # espace fine insécable
    " ": "\n",  # séparateur de ligne
    " ": "\n",  # séparateur de paragraphe
    "﻿": "",    # marque d'ordre des octets
}

#: LA FAUSSE BONNE IDÉE, ÉCARTÉE APRÈS MESURE
#: -------------------------------------------
#: Le réflexe, pour replier un mot de 300 caractères, est d'y semer des
#: espaces de largeur nulle (U+200B). Mesuré sur le document réel, le
#: résultat est pire que le défaut : les polices de base d'un PDF n'ont
#: pas de glyphe pour U+200B, et ReportLab imprime alors le caractère de
#: remplacement. Le mot sortait :
#:
#:     MoooooooooooooooooooIooooooooooooooooooooIoooooooooooooo…
#:
#: Un « I » parasite tous les vingt caractères, dans une pièce officielle.
#: On s'était donné une solution qui abîmait le document sans rien dire.
#:
#: ReportLab sait déjà couper un mot plus large que sa colonne : c'est
#: `splitLongWords`, actif par défaut et réaffirmé ci-dessous parce qu'un
#: style hérité peut l'avoir éteint. La vérification n'est donc pas « le
#: mot a-t-il été découpé » mais « un mot dépasse-t-il la marge », mesurée
#: sur le PDF produit (voir `tests/test_long_text_rendering.py`).


def normalize(value) -> str:
    """Texte prêt à être mesuré : jamais `None`, sans caractères invisibles."""
    if value is None:
        return ""
    text = str(value)
    for source, target in SUBSTITUTIONS.items():
        text = text.replace(source, target)
    return text.replace("\r\n", "\n").replace("\r", "\n")


def pdf_paragraph(value, **style):
    """
    `Paragraph` ReportLab construit à partir d'un texte saisi par un humain.

    L'ordre des opérations compte : on échappe D'ABORD (`&` devient
    `&amp;`), et on n'introduit les balises `<br/>` qu'ENSUITE. Faire
    l'inverse transformerait les `<br/>` que l'on vient de poser en
    `&lt;br/&gt;` visibles à l'écran.
    """
    style.setdefault("fontSize", 9)
    if style["fontSize"] < MIN_READABLE_FONT_SIZE:
        raise ValueError(
            f"Police de {style['fontSize']} pt : en dessous de "
            f"{MIN_READABLE_FONT_SIZE} pt le texte n'est plus lisible à "
            f"l'impression. Faire tenir un texte long en le rapetissant "
            f"n'est pas de la mise en page, c'est de la dissimulation."
        )
    style.setdefault("leading", round(style["fontSize"] * 1.35, 1))
    # C'est CE réglage qui coupe une URL ou un mot de 300 caractères. Il
    # vaut 1 par défaut, mais un style hérité peut l'avoir éteint, et le
    # symptôme serait alors un mot qui sort de la page sans erreur.
    style.setdefault("splitLongWords", 1)
    style.setdefault("allowWidows", 0)
    style.setdefault("allowOrphans", 0)

    text = normalize(value)
    escaped = html.escape(text, quote=False).replace("\n", "<br/>")
    return Paragraph(escaped, ParagraphStyle("longtext", **style))


def long_text_table(data, **kwargs):
    """
    Tableau à deux colonnes autorisé à se couper au milieu d'une ligne.

    `splitByRow` seul ne suffit pas : il place les lignes entières sur la
    page suivante, ce qui laisse intact le cas d'UNE ligne plus haute
    qu'une page — précisément le cas qui faisait échouer la fiche.
    """
    kwargs.setdefault("splitByRow", 1)
    kwargs.setdefault("splitInRow", 1)
    kwargs.setdefault("repeatRows", 0)
    return Table(data, **kwargs)


def keep_with_next(title_flowable, body_flowables, min_space=2.4 * 28.3465):
    """
    Garde un titre solidaire du début de sa section, sans rendre la section
    entière insécable.

    `CondPageBreak` demande simplement : « s'il reste moins de `min_space`
    sur cette page, commence la suivante ». Un titre ne peut donc plus se
    retrouver seul en bas de page — sans pour autant interdire à la
    section de se poursuivre page suivante.
    """
    return [CondPageBreak(min_space), title_flowable, *body_flowables]


__all__ = [
    "MIN_READABLE_FONT_SIZE",
    "KeepTogether",
    "keep_with_next",
    "long_text_table",
    "normalize",
    "pdf_paragraph",
]
