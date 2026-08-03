"""
apps/documents/textfit.py — Composition du nom sur un document officiel

POURQUOI CE MODULE EXISTE
-------------------------
Le nom d'un élève ne rentre pas toujours sur une ligne. Un patronyme
composé de la diaspora — prénoms d'usage, nom du père, nom de la mère,
particule — dépasse couramment soixante-dix caractères. Trois réponses
sont possibles, et deux sont mauvaises :

  - le tronquer : le document circule avec un faux nom ;
  - refuser de produire : l'école ne peut pas remettre son diplôme ;
  - le replier sur deux lignes : la seule réponse acceptable.

Replier suppose de savoir, AVANT de dessiner, quelle place occupera le
bloc. Une version antérieure estimait cette hauteur à « taille × 0,75 ».
L'estimation était fausse d'environ 30 % sur une anglaise, et la première
ligne du nom venait se poser sur la phrase gravée dans le fond. Ce module
ne fait aucune estimation : il lit les tables du fichier de police.

CE QUE « MÉTRIQUES RÉELLES » VEUT DIRE ICI
------------------------------------------
Pour chaque caractère, le fichier TrueType donne :

  - `hmtx` — la chasse (largeur d'avance) ;
  - `glyf` — la boîte englobante du DESSIN : xMin, yMin, xMax, yMax.

Les deux diffèrent, et l'écart compte. Dans une italique, le « K » déborde
de 71 unités à droite de sa chasse et le « A » de 42 unités à gauche : un
nom calé sur la somme des chasses sort de sa zone par les extrémités. De
même, la hauteur d'une ligne n'est pas l'ascendante nominale de la police
(0,896 em) mais la hauteur RÉELLE de ses lettres : 0,766 em pour un « É »,
0,678 em pour un « d », 0,573 em pour un « K ». Mesurer le dessin plutôt
que la fonte rend près d'un quart de la hauteur — exactement ce qui
manquait pour tenir sur deux lignes sans toucher le texte du dessus.

L'ORIGINE ET LES UNITÉS
-----------------------
Tout est en POINTS PostScript, et l'origine d'une boîte de texte est la
LIGNE DE BASE, y vers le haut. `y_max` est donc positif (au-dessus de la
ligne de base) et `y_min` négatif (jambages descendants). C'est la
convention de ReportLab, à qui le résultat est transmis ; convertir deux
fois est la faute la plus prévisible de ce genre de code.

CE QUE CE MODULE NE FAIT PAS
----------------------------
Il ne dessine rien et n'ouvre aucun canevas. Il se teste donc sans PDF,
sans base de données et sans Django. C'est délibéré : le défaut corrigé
ici n'était visible qu'à l'œil, sur un rendu, et une mesure qu'on ne peut
pas éprouver isolément est une mesure qu'on ne corrige pas.
"""
import os
import re
import unicodedata
from dataclasses import dataclass, field as dataclass_field

from django.conf import settings

#: Point PostScript par millimètre. Redéfini ici plutôt qu'importé de
#: ReportLab : ce module doit rester mesurable sans moteur de rendu.
MM = 72.0 / 25.4

#: Racine des ressources livrées.
RESOURCES_DIR = os.path.join(settings.BASE_DIR, "feba_project", "static_files")

#: Polices embarquées. Une police résolue par le système produirait un
#: document différent selon le serveur, sans que personne ne s'en aperçoive
#: avant l'impression.
FONTS_DIR = os.path.join(RESOURCES_DIR, "fonts")
EMBEDDED_FONTS = {
    # Le placeholder d'origine est composé en anglaise calligraphique. Cette
    # fonte n'est pas fournie avec le projet : Crimson Pro Italic est un
    # choix COMPATIBLE — serif, italique, même or, même ligne de base — et
    # non identique. Le rapport de fidélité le dit.
    "FEBA-Script": "CrimsonPro-Italic.ttf",
    "FEBA-Text": "CrimsonPro-Regular.ttf",
    "FEBA-TextItalic": "CrimsonPro-Italic.ttf",
}


#: Répertoire de RÉFÉRENCE pour la hauteur d'un nom.
#:
#: Sert à obtenir un corps STABLE. Sans lui, « Élise Kponou » sortirait à
#: 31 pt et « Jean-Baptiste Dossou » à 34 pt sur le même certificat : le
#: premier porte un accent, qui monte plus haut que toute autre lettre du
#: second. Deux documents remis le même jour, au même diplôme, avec deux
#: tailles de nom différentes — l'écart se voit dès qu'on les pose côte à
#: côte, et rien dans le code ne l'expliquerait.
#:
#: Le corps est donc calculé sur la lettre la plus haute que la police
#: puisse avoir à dessiner dans un nom, quelle que soit celle qu'on lui
#: donne. Le répertoire couvre le latin étendu : une académie de la
#: diaspora reçoit des noms scandinaves, portugais et vietnamiens comme
#: elle reçoit des noms béninois.
NAME_REPERTOIRE = (
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    "ÀÁÂÃÄÅÆÇÈÉÊËÌÍÎÏÑÒÓÔÕÖØÙÚÛÜÝŸŒ"
    "abcdefghijklmnopqrstuvwxyz"
    "àáâãäåæçèéêëìíîïñòóôõöøùúûüýÿœ"
    "'’ʼ-‐&.0123456789"
)


class MetricsError(RuntimeError):
    """Les métriques demandées ne peuvent pas être lues."""


def font_path(family):
    """Chemin du fichier de police d'une famille déclarée par un gabarit."""
    filename = EMBEDDED_FONTS.get(family)
    if filename is None:
        raise MetricsError(
            f"La police « {family} » n'est pas embarquée. Les documents "
            f"officiels ne se composent pas avec une police résolue par le "
            f"système : la mise en page changerait d'un serveur à l'autre."
        )
    return os.path.join(FONTS_DIR, filename)


# ── Lecture du fichier de police ──────────────────────────────────────

@dataclass(frozen=True)
class GlyphMetrics:
    """Ce que le fichier de police dit d'un caractère, en unités em."""

    advance: float          #: chasse
    x_min: float
    y_min: float
    x_max: float
    y_max: float
    is_blank: bool          #: glyphe sans contour (espace)


class FontMetrics:
    """
    Les tables d'un fichier TrueType, lues une fois.

    Instanciée par `metrics_for()`, qui met en cache : ouvrir un TTF coûte
    quelques millisecondes, et un diplôme mesure une centaine de chaînes.
    """

    def __init__(self, path):
        from fontTools.ttLib import TTFont

        if not os.path.exists(path):
            raise MetricsError(
                f"Police introuvable ({path}). La composition s'arrête ici "
                f"plutôt que de mesurer avec une police de substitution."
            )
        self.path = path
        self._font = TTFont(path, lazy=True)
        self.units_per_em = float(self._font["head"].unitsPerEm)

        hhea = self._font["hhea"]
        #: Ascendante et descendante NOMINALES de la fonte, en em. Elles
        #: décrivent l'encombrement déclaré de la police, pas celui d'un
        #: texte donné : c'est `text_bbox()` qui mesure le second.
        self.ascent = hhea.ascent / self.units_per_em
        self.descent = hhea.descent / self.units_per_em      # négatif
        self.line_gap = hhea.lineGap / self.units_per_em

        self._cmap = self._font.getBestCmap()
        self._hmtx = self._font["hmtx"]
        self._glyf = self._font["glyf"]
        self._cache = {}

        #: Encre la plus haute et la plus basse que cette police puisse
        #: produire dans un nom, en em. Mesurées sur le répertoire, pas
        #: déclarées : pour Crimson Pro Italic, 0,815 em (le « Å ») et
        #: -0,226 em (le « j »), là où la fonte annonce 0,896 et -0,215.
        hauts = [self.glyph(c).y_max for c in NAME_REPERTOIRE
                 if self.glyph(c) is not None and not self.glyph(c).is_blank]
        bas = [self.glyph(c).y_min for c in NAME_REPERTOIRE
               if self.glyph(c) is not None and not self.glyph(c).is_blank]
        self.reference_ascent = max(hauts) if hauts else self.ascent
        self.reference_descent = min(bas) if bas else self.descent

    def glyph(self, char):
        """Métriques d'un caractère, en unités em, ou None s'il est absent."""
        if char in self._cache:
            return self._cache[char]
        name = self._cmap.get(ord(char))
        if name is None:
            self._cache[char] = None
            return None
        advance = self._hmtx[name][0] / self.units_per_em
        glyph = self._glyf[name]
        if glyph.numberOfContours == 0:
            metrics = GlyphMetrics(advance, 0.0, 0.0, 0.0, 0.0, True)
        else:
            metrics = GlyphMetrics(
                advance,
                glyph.xMin / self.units_per_em,
                glyph.yMin / self.units_per_em,
                glyph.xMax / self.units_per_em,
                glyph.yMax / self.units_per_em,
                False,
            )
        self._cache[char] = metrics
        return metrics

    def missing(self, text):
        """Caractères que cette police ne sait pas dessiner."""
        return sorted({c for c in text if self.glyph(c) is None})


_METRICS_CACHE = {}


def metrics_for(family):
    """`FontMetrics` d'une famille, mis en cache."""
    path = font_path(family)
    cached = _METRICS_CACHE.get(path)
    if cached is None:
        cached = FontMetrics(path)
        _METRICS_CACHE[path] = cached
    return cached


# ── Mesures ───────────────────────────────────────────────────────────

@dataclass(frozen=True)
class TextBox:
    """
    Encombrement RÉEL d'une chaîne, en points, origine à la ligne de base.

    `advance` est la somme des chasses — ce que ReportLab utilise pour
    centrer. `x_min`/`x_max` sont les bords de l'ENCRE, qui peuvent
    déborder de la chasse dans une italique. Les deux sont conservés :
    l'un sert au placement, l'autre au contrôle de débordement.
    """

    text: str
    font_family: str
    size_pt: float
    advance: float
    x_min: float
    y_min: float
    x_max: float
    y_max: float

    @property
    def ink_width(self):
        return max(0.0, self.x_max - self.x_min)

    @property
    def ink_height(self):
        return max(0.0, self.y_max - self.y_min)

    @property
    def is_empty(self):
        return self.x_max <= self.x_min and self.y_max <= self.y_min


def get_ascent_descent(font_family, size_pt):
    """
    Ascendante et descendante NOMINALES de la police, en points.

    Renvoyées telles que déclarées par la fonte : `descent` est négatif.
    Elles servent à poser la ligne de base d'un champ dans sa boîte, pas à
    décider si un bloc tient : pour cela, seule l'encre compte, et c'est
    `get_text_bbox()` qui la mesure.
    """
    metrics = metrics_for(font_family)
    return metrics.ascent * size_pt, metrics.descent * size_pt


def get_text_bbox(text, font_family, size_pt):
    """
    Boîte englobante réelle d'une chaîne composée sur une seule ligne.

    Le stylo part de (0, 0) — l'origine est la ligne de base, à gauche du
    premier caractère. Chaque glyphe est posé à sa position d'avance, et
    la boîte est l'union des dessins. Les espaces n'ont pas de contour et
    n'agrandissent donc pas l'encre, mais font avancer le stylo.

    Aucun crénage n'est appliqué : ReportLab n'en applique pas non plus
    dans `drawString`. Mesurer autrement que ce qui sera dessiné ferait
    exactement le genre d'écart qu'on cherche à éliminer.
    """
    metrics = metrics_for(font_family)
    manquants = metrics.missing(text)
    if manquants:
        raise MetricsError(
            f"La police « {font_family} » ne sait pas dessiner "
            f"{manquants}. Un document sortirait avec un rectangle vide à "
            f"la place d'une lettre du nom."
        )

    pen = 0.0
    x_min = y_min = None
    x_max = y_max = None
    for char in text:
        glyph = metrics.glyph(char)
        if not glyph.is_blank:
            left = pen + glyph.x_min
            right = pen + glyph.x_max
            x_min = left if x_min is None else min(x_min, left)
            x_max = right if x_max is None else max(x_max, right)
            y_min = glyph.y_min if y_min is None else min(y_min, glyph.y_min)
            y_max = glyph.y_max if y_max is None else max(y_max, glyph.y_max)
        pen += glyph.advance

    if x_min is None:            # chaîne vide, ou uniquement des espaces
        x_min = x_max = y_min = y_max = 0.0

    return TextBox(
        text=text, font_family=font_family, size_pt=size_pt,
        advance=pen * size_pt,
        x_min=x_min * size_pt, y_min=y_min * size_pt,
        x_max=x_max * size_pt, y_max=y_max * size_pt,
    )


@dataclass(frozen=True)
class BlockMetrics:
    """
    Encombrement réel d'un bloc de lignes, origine à la ligne de base de
    la DERNIÈRE ligne.

    Ce choix d'origine n'est pas arbitraire : sur un diplôme, c'est la
    dernière ligne qui est posée sur la règle d'écriture. Un bloc mesuré
    depuis le haut obligerait à recalculer sa position dès qu'une ligne
    s'ajoute, et le nom flotterait au-dessus du trait.
    """

    lines: tuple
    font_family: str
    size_pt: float
    leading_pt: float
    boxes: tuple = dataclass_field(repr=False)

    @property
    def line_count(self):
        return len(self.lines)

    @property
    def baselines(self):
        """Ordonnée de chaque ligne de base, la dernière valant 0."""
        n = len(self.lines)
        return tuple((n - 1 - i) * self.leading_pt for i in range(n))

    @property
    def top(self):
        """Bord supérieur de l'encre, au-dessus de la dernière ligne de base."""
        return max(base + box.y_max
                   for base, box in zip(self.baselines, self.boxes))

    @property
    def bottom(self):
        """Bord inférieur de l'encre. Négatif : les jambages descendent."""
        return min(base + box.y_min
                   for base, box in zip(self.baselines, self.boxes))

    @property
    def height(self):
        """Hauteur RÉELLE du bloc, encre comprise, sans aucune estimation."""
        return self.top - self.bottom

    @property
    def ink_width(self):
        return max(box.ink_width for box in self.boxes)

    @property
    def advance_width(self):
        return max(box.advance for box in self.boxes)

    @property
    def interline_gap(self):
        """
        Blanc réel entre le jambage le plus bas d'une ligne et la lettre la
        plus haute de la suivante. Négatif = les deux lignes se croisent.

        Sur une seule ligne, la notion n'a pas de sens : `None`.
        """
        if len(self.lines) < 2:
            return None
        ecarts = []
        for i in range(len(self.lines) - 1):
            bas_haut = self.baselines[i] + self.boxes[i].y_min
            haut_bas = self.baselines[i + 1] + self.boxes[i + 1].y_max
            ecarts.append(bas_haut - haut_bas)
        return min(ecarts)


def measure_multiline_block(lines, font_family, size_pt, leading_pt):
    """
    Mesure un bloc de lignes composé à taille et interligne donnés.

    Toutes les lignes ont la MÊME taille : deux tailles dans un nom se
    lisent comme deux personnes.
    """
    if not lines:
        raise MetricsError("Un bloc sans ligne n'a pas d'encombrement.")
    boxes = tuple(get_text_bbox(line, font_family, size_pt) for line in lines)
    return BlockMetrics(
        lines=tuple(lines), font_family=font_family, size_pt=float(size_pt),
        leading_pt=float(leading_pt), boxes=boxes,
    )


# ── Normalisation ─────────────────────────────────────────────────────

#: Espaces au sens Unicode, insécables compris. Un nom saisi depuis un
#: traitement de texte en contient sans que personne ne le voie.
_ESPACES = re.compile(r"[\s     ]+")


def normalize_spaces(text):
    """
    Réduit les suites d'espaces à un seul et supprime ceux des extrémités.

    RIEN D'AUTRE N'EST TOUCHÉ. Les accents restent des accents, les
    apostrophes typographiques restent typographiques, les traits d'union
    restent des traits d'union et l'esperluette reste une esperluette :
    « Jean-Baptiste D'Almeida » ne devient pas « Jean Baptiste D Almeida ».
    Ce qu'un parent a écrit sur un acte de naissance n'est pas une donnée
    à normaliser — c'est le nom d'un enfant.

    La normalisation Unicode appliquée est NFC, qui recompose « e » + accent
    en « é » sans changer le texte visible. Sans elle, deux graphies du même
    nom mesureraient différemment.
    """
    if text is None:
        return ""
    return _ESPACES.sub(" ", unicodedata.normalize("NFC", str(text))).strip()


def split_points(text):
    """
    Coupes possibles d'un nom, uniquement sur les espaces.

    Jamais au milieu d'un mot, jamais sur un trait d'union : « Adjovi-Bokô »
    coupé après le tiret se lit comme deux noms distincts, et « Kponou »
    coupé en « Kpo- / nou » n'est plus un nom du tout.
    """
    mots = text.split(" ")
    return [(" ".join(mots[:i]), " ".join(mots[i:]))
            for i in range(1, len(mots))]


# ── Composition ───────────────────────────────────────────────────────

@dataclass(frozen=True)
class SafeZone:
    """
    Place réellement disponible pour l'encre du nom, en millimètres,
    repère du gabarit (origine en haut à gauche).

    Ces quatre nombres ne sont pas des préférences de mise en page : ils
    sont MESURÉS sur le fond livré — bord inférieur de la phrase gravée,
    bord supérieur de la règle d'écriture, bords des ornements latéraux —
    et consignés dans DOCUMENT_TEMPLATE_CALIBRATION.md avec la commande
    qui les a produits.
    """

    y_top_mm: float
    y_bottom_mm: float
    x_left_mm: float
    x_right_mm: float
    #: Les DEUX obstacles dont la zone est déduite, conservés en clair.
    #: Un commentaire ne se vérifie pas ; ces deux nombres, si. Le test de
    #: pixels s'en sert pour affirmer qu'aucune encre du nom ne se trouve
    #: entre la zone et l'obstacle — c'est-à-dire que le dégagement
    #: déclaré existe réellement sur le rendu.
    engraved_phrase_bottom_mm: float = None
    writing_rule_top_mm: float = None

    @classmethod
    def from_dict(cls, data):
        def facultatif(cle):
            valeur = data.get(cle)
            return None if valeur is None else float(valeur)

        return cls(
            y_top_mm=float(data["y_top_mm"]),
            y_bottom_mm=float(data["y_bottom_mm"]),
            x_left_mm=float(data["x_left_mm"]),
            x_right_mm=float(data["x_right_mm"]),
            engraved_phrase_bottom_mm=facultatif("engraved_phrase_bottom_mm"),
            writing_rule_top_mm=facultatif("writing_rule_top_mm"),
        )

    @property
    def height_mm(self):
        return self.y_bottom_mm - self.y_top_mm

    @property
    def width_mm(self):
        return self.x_right_mm - self.x_left_mm


@dataclass(frozen=True)
class Composition:
    """Résultat d'une composition réussie."""

    lines: tuple
    size_pt: float
    leading_pt: float
    block: BlockMetrics
    #: Distance, en points, entre le BAS de la zone sûre et la ligne de
    #: base de la DERNIÈRE ligne. Elle croît avec le corps : un nom écrit
    #: gros descend plus bas sous sa ligne de base, et doit donc être posé
    #: plus haut pour que ses jambages ne traversent pas la règle.
    baseline_offset_pt: float = 0.0
    #: Ce qui a été essayé avant d'aboutir. Sert au diagnostic et au
    #: dossier de calibrage : « pourquoi 21,5 pt et pas 34 » est une
    #: question qu'on se pose six mois plus tard.
    trials: tuple = ()


class CompositionRefused(Exception):
    """
    Aucune composition acceptable n'existe pour ce texte dans cette zone.

    Levée UNIQUEMENT après avoir prouvé que même la taille minimale sur le
    nombre maximal de lignes déborde. Le message porte les mesures qui
    l'établissent : un refus sans chiffres ne se corrige pas.
    """

    def __init__(self, message, *, trials=()):
        super().__init__(message)
        self.trials = tuple(trials)


def natural_leading(boxes, size_pt, leading_ratio, min_gap_pt):
    """
    Interligne réellement nécessaire pour que deux lignes ne se croisent pas.

    L'interligne nominal — un multiple du corps — suffit presque toujours.
    « Presque » ne convient pas ici : un prénom finissant par « j » suivi
    d'un nom commençant par « É » demande 0,99 em à lui seul, et un
    gabarit qui serrerait l'interligne pour gagner de la place ferait
    coïncider le jambage de l'un avec l'accent de l'autre. L'interligne
    retenu est donc le PLUS GRAND des deux : le nominal, et celui que
    l'encre réelle de CES lignes-là exige.

    Il est uniforme pour tout le bloc : deux interlignes différents dans
    un nom se voient immédiatement.
    """
    besoin = leading_ratio * size_pt
    for haut, bas in zip(boxes, boxes[1:]):
        besoin = max(besoin, (-haut.y_min) + bas.y_max + min_gap_pt)
    return besoin


def compose(text, *, font_family, size_pt, min_size_pt, max_lines,
            available_width_pt, zone_height_pt, baseline_reserve_em=0.23,
            leading_ratio=1.0, size_step_pt=0.25, min_interline_gap_pt=0.0):
    """
    Compose un nom dans la place mesurée, ou refuse en le prouvant.

    LA ZONE ET L'ANCRAGE
    --------------------
    `zone_height_pt` est la hauteur MESURÉE entre le bas de la phrase
    gravée dans le fond et le haut de la règle d'écriture, moins les
    dégagements consignés au calibrage. La dernière ligne de base est
    posée à `baseline_reserve_em × corps` au-dessus du bas de cette zone :
    la réserve couvre le jambage descendant le plus profond de la police
    (0,228 em pour le « y »), de sorte qu'aucune lettre ne touche la
    règle, quel que soit le corps retenu.

    L'ALGORITHME, DANS L'ORDRE
    --------------------------
     1. Normaliser les espaces, et rien d'autre.
     2. Essayer UNE ligne à la taille nominale.
     3. Réduire progressivement, par pas de `size_step_pt`, tant que la
        taille minimale n'est pas atteinte.
     4. Si une ligne ne suffit pas et que le gabarit autorise deux lignes,
        chercher les coupes possibles — sur les espaces seulement.
     5. Reprendre la même taille : un nom qui ne tient pas sur une ligne à
        24 pt peut tenir sur deux à 24 pt.
     6. À chaque taille, mesurer les DEUX lignes de chaque coupe.
     7. Écarter les coupes dont une ligne déborde en largeur.
     8. Écarter les tailles dont le bloc déborde en hauteur — hauteur
        RÉELLE, mesurée sur l'encre.
     9. Écarter les tailles où les deux lignes se croisent verticalement.
    10. Parmi les coupes restantes, retenir la plus ÉQUILIBRÉE : quatre
        mots suivis d'un mot isolé se lit comme une erreur de composition,
        pas comme un nom.
    11. La taille retenue vaut pour les deux lignes.
    12. Ne refuser qu'après avoir constaté l'échec à la taille minimale.

    UNE ET DEUX LIGNES SONT ESSAYÉES À CHAQUE TAILLE, PAS L'UNE APRÈS
    L'AUTRE. La première écriture épuisait toutes les tailles sur une
    ligne avant d'envisager la seconde ; un nom de 73 caractères sortait
    alors sur UNE ligne à 14,75 pt, alors que deux lignes tenaient à
    20,5 pt. Techniquement conforme, typographiquement mauvais : à taille
    égale on préfère une ligne, mais on ne rapetisse pas un nom de 30 %
    pour éviter d'en faire deux.

    Le retour porte la mesure du bloc : l'appelant place, il ne remesure
    pas.
    """
    texte = normalize_spaces(text)
    if not texte:
        raise CompositionRefused("Texte vide : il n'y a rien à composer.")

    metrics = metrics_for(font_family)
    essais = []

    def tenter(lignes, taille):
        """Mesure une hypothèse et dit si elle tient. Aucune estimation."""
        boxes = tuple(get_text_bbox(ligne, font_family, taille)
                      for ligne in lignes)
        interligne = natural_leading(boxes, taille, leading_ratio,
                                     min_interline_gap_pt)
        bloc = BlockMetrics(lines=tuple(lignes), font_family=font_family,
                            size_pt=taille, leading_pt=interligne, boxes=boxes)

        # La ligne de base de la dernière ligne, comptée depuis le BAS de
        # la zone. Elle monte quand le corps grandit.
        reserve = baseline_reserve_em * taille
        plafond = zone_height_pt - reserve       # place au-dessus
        plancher = reserve                       # place en dessous

        # La montée retenue est la PLUS GRANDE des deux : celle de l'encre
        # réelle de ces lignes-là — qui garantit l'absence de collision —
        # et celle du répertoire — qui rend le corps indépendant des
        # lettres du nom, donc identique d'un élève à l'autre.
        montee_reelle = bloc.top
        montee_reference = (interligne * (len(lignes) - 1)
                            + metrics.reference_ascent * taille)
        montee = max(montee_reelle, montee_reference)
        descente = max(-bloc.bottom, -metrics.reference_descent * taille)

        trop_large = bloc.ink_width > available_width_pt + 1e-6
        depasse_haut = montee > plafond + 1e-6
        depasse_bas = descente > plancher + 1e-6
        essais.append({
            "lignes": len(lignes), "taille_pt": round(taille, 2),
            "largeur_encre_pt": round(bloc.ink_width, 2),
            "hauteur_encre_pt": round(bloc.height, 2),
            "montee_reelle_pt": round(montee_reelle, 2),
            "montee_reference_pt": round(montee_reference, 2),
            "plafond_pt": round(plafond, 2),
            "descente_pt": round(descente, 2),
            "plancher_pt": round(plancher, 2),
            "interligne_pt": round(interligne, 2),
            "blanc_interligne_pt": (None if bloc.interline_gap is None
                                    else round(bloc.interline_gap, 2)),
            "accepte": not (trop_large or depasse_haut or depasse_bas),
        })
        if trop_large or depasse_haut or depasse_bas:
            return None
        return bloc

    def aboutir(bloc, taille):
        return Composition(
            lines=bloc.lines, size_pt=taille, leading_pt=bloc.leading_pt,
            block=bloc, baseline_offset_pt=baseline_reserve_em * taille,
            trials=tuple(essais))

    coupes = split_points(texte) if max_lines >= 2 else []

    taille = float(size_pt)
    while taille >= min_size_pt - 1e-9:
        # 2, 3 — une ligne d'abord : à taille égale, elle est préférable.
        bloc = tenter([texte], taille)
        if bloc is not None:
            return aboutir(bloc, taille)

        # 4 à 11 — puis deux lignes, à LA MÊME taille.
        meilleur = None
        for haut, bas in coupes:
            bloc = tenter([haut, bas], taille)
            if bloc is None:
                continue
            # 10 — la coupe la plus équilibrée, mesurée sur l'encre.
            desequilibre = abs(bloc.boxes[0].ink_width
                               - bloc.boxes[1].ink_width)
            if meilleur is None or desequilibre < meilleur[0]:
                meilleur = (desequilibre, bloc)
        if meilleur is not None:
            return aboutir(meilleur[1], taille)

        taille -= size_step_pt

    # 12 — refus prouvé, avec les chiffres qui l'établissent.
    dernier = essais[-1] if essais else {}
    raise CompositionRefused(
        f"« {texte} » ({len(texte)} caractères) ne peut pas être composé "
        f"dans une zone de {available_width_pt:.1f} pt de large et "
        f"{zone_height_pt:.1f} pt de haut, même à {min_size_pt} pt sur "
        f"{max(1, max_lines)} ligne(s). Dernière mesure : encre "
        f"{dernier.get('largeur_encre_pt')} pt de large, montée "
        f"{dernier.get('montee_pt')} pt pour un plafond de "
        f"{dernier.get('plafond_pt')} pt.",
        trials=essais,
    )
