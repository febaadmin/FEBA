"""
HTML des e-mails reçus : nettoyé par liste blanche (nh3) avant tout affichage.

Aucun script, aucun gestionnaire d'événement, aucun style actif, aucun formulaire ni
cadre. Les images distantes (souvent des pixels de pistage) sont retirées de la version
affichée par défaut ; une seconde version, avec images, n'est servie qu'à la demande.
"""
import re

import nh3

BALISES = {"a", "b", "blockquote", "br", "caption", "center", "code", "div", "em", "font", "h1", "h2", "h3", "h4",
           "h5", "h6", "hr", "i", "img", "li", "ol", "p", "pre", "s", "small", "span", "strong", "sub", "sup",
           "table", "tbody", "td", "tfoot", "th", "thead", "tr", "u", "ul"}
ATTRIBUTS = {"a": {"href", "title"}, "img": {"src", "alt", "width", "height"}, "td": {"colspan", "rowspan", "align"},
             "th": {"colspan", "rowspan", "align"}, "table": {"width"}, "p": {"align"}, "div": {"align"}}
SCHEMAS = {"http", "https", "mailto", "data", "cid"}
_IMG_DISTANTE = re.compile(r"<img\b[^>]*\bsrc=\"https?://[^\"]*\"[^>]*>", re.I)


def nettoyer_mail(brut):
    """→ (html sans images distantes, html avec images, présence d'images distantes)."""
    avec = nh3.clean(brut or "", tags=BALISES, attributes=ATTRIBUTS, url_schemes=SCHEMAS,
                     link_rel="noopener noreferrer nofollow", strip_comments=True)
    # Images en ligne (cid:) non résolues : retirées (affichées comme pièces jointes).
    avec = re.sub(r"<img\b[^>]*\bsrc=\"cid:[^\"]*\"[^>]*>", "", avec, flags=re.I)
    distantes = bool(_IMG_DISTANTE.search(avec))
    sans = _IMG_DISTANTE.sub("", avec)
    return sans, avec, distantes
