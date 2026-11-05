"""
apps/notifications/html_securise.py — HTML des e-mails composés dans FEBA.

Le navigateur envoie le HTML de l'éditeur : il n'est JAMAIS une autorité. Il est
nettoyé ici par nh3 (bibliothèque « ammonia », liste blanche) avant d'être
archivé et envoyé :

- balises permises : paragraphes, retours à la ligne, gras, italique, souligné,
  barré, listes, citations, titres simples, liens ;
- aucun attribut d'événement (onclick…), aucun style, aucun script, aucune image
  distante (pistage) ni iframe ;
- liens : http, https et mailto seulement, ouverts avec rel="noopener noreferrer".

La version texte est dérivée du HTML nettoyé : chaque destinataire peut lire le
message même si son client n'affiche pas le HTML.
"""
import html
import re

import nh3

BALISES = {"p", "br", "strong", "b", "em", "i", "u", "s", "ul", "ol", "li", "blockquote", "h3", "h4", "a", "div", "span"}
ATTRIBUTS = {"a": {"href", "title"}}
SCHEMAS = {"http", "https", "mailto"}
MAX_HTML = 200_000


class HtmlRefuse(ValueError):
    pass


def nettoyer(brut):
    """HTML sûr (liste blanche) ; lève HtmlRefuse si le message est trop long ou vide."""
    brut = brut or ""
    if len(brut) > MAX_HTML:
        raise HtmlRefuse("Le message mis en forme est trop long.")
    propre = nh3.clean(brut, tags=BALISES, attributes=ATTRIBUTS, url_schemes=SCHEMAS,
                       link_rel="noopener noreferrer", strip_comments=True).strip()
    if not en_texte(propre).strip():
        raise HtmlRefuse("Le contenu du message est obligatoire.")
    return propre


def en_texte(propre):
    """Version texte lisible du HTML nettoyé (paragraphes, listes, liens conservés)."""
    t = re.sub(r"<a\s[^>]*href=\"([^\"]+)\"[^>]*>(.*?)</a>",
               lambda m: m.group(2) if m.group(2).strip() == m.group(1) else f"{m.group(2)} ({m.group(1)})",
               propre, flags=re.S | re.I)
    t = re.sub(r"<br\s*/?>", "\n", t, flags=re.I)
    t = re.sub(r"<li[^>]*>", "\n- ", t, flags=re.I)
    t = re.sub(r"</(p|div|h3|h4|blockquote|ul|ol)>", "\n\n", t, flags=re.I)
    t = re.sub(r"<[^>]+>", "", t)
    t = html.unescape(t)
    t = re.sub(r"[ \t]+\n", "\n", t)
    return re.sub(r"\n{3,}", "\n\n", t).strip()
