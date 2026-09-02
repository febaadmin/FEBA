"""
apps/schools/branding.py — Source unique de l'identité visuelle des académies.

POURQUOI CE MODULE EXISTE
-------------------------
Chaque générateur de document portait sa propre idée de l'établissement :
« FAITH & EXCELLENCE BILINGUAL ACADEMY » écrit en dur dans le repli du reçu,
« Cotonou » en dur au-dessus de la date, « #1E3A6E » recopié dans quatre
fichiers, « FCFA » supposé par le formateur de montants. Tant qu'il n'y
avait qu'une école, l'erreur ne se voyait pas. Avec deux académies, chaque
constante en dur devient un document faux : un reçu de FEBA French Heritage
Academy signé du nom et de l'adresse d'une école de Cotonou n'est pas une
imperfection graphique, c'est un document qui désigne la mauvaise personne
morale.

RÈGLE
-----
Aucun générateur de PDF, d'e-mail ou d'export ne lit School directement pour
composer un en-tête. Tous appellent `get_branding(academy)` et n'utilisent
que les champs de l'objet retourné. Un contrôle automatisé
(`tests/test_branding.py`) refuse la réapparition d'une chaîne en dur.

CE QUE CE MODULE N'INVENTE JAMAIS
--------------------------------
Un logo, un cachet ou une signature absents du disque restent à None. Le
document sort sans, plutôt qu'avec l'emblème d'une autre académie. Une
signature approchée sur un diplôme n'est pas une approximation graphique :
c'est un faux.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass, replace
from typing import Optional

from .institution import official_phone, strip_retired_phones

logger = logging.getLogger("apps")

#: Racine des ressources graphiques livrées avec le projet.
STATIC_FILES_DIR = os.path.normpath(os.path.join(
    os.path.dirname(__file__), "..", "..", "feba_project", "static_files",
))


class BrandingUnavailable(RuntimeError):
    """
    Levée quand un document est demandé sans académie identifiable.

    Volontairement bloquant. L'ancien comportement — retomber sur
    `School.objects.first()` — produisait un document complet, plausible et
    faux : personne ne peut voir à l'œil nu qu'un reçu porte l'en-tête de
    l'autre académie. Mieux vaut une erreur qu'un document erroné en
    circulation.
    """


#: Palette institutionnelle NEUTRE.
#:
#: Elle ne sert qu'aux académies dont l'identité n'a pas encore été
#: administrée — une école créée hier par un administrateur, avant qu'il
#: n'ait déposé ses couleurs. Ce n'est pas « le branding par défaut de
#: FEBA » : FEBA et FEBA FHA ont chacune leurs propres valeurs en base
#: (voir `init_academies`). La commande `branding_check` signale toute
#: académie encore sur ces valeurs neutres.
NEUTRAL_PALETTE = {
    "primary_color": "#1F2937",
    "secondary_color": "#4B5563",
    "accent_color": "#9CA3AF",
    "background_color": "#FFFFFF",
}

#: Clés reconnues dans `School.settings['branding']`.
BRANDING_SETTING_KEYS = (
    "primary_color", "secondary_color", "accent_color", "background_color",
    "website", "footer_text", "group_name", "document_prefix",
    "document_logo", "stamp", "director_signature", "secretary_stamp",
)

#: Images dont le DESSIN porte le nom d'un établissement, et lequel.
#:
#: Ces fichiers ne sont pas des ressources neutres du groupe : leur visuel
#: nomme une académie. Les poser sur un document d'une autre y estampille
#: le nom d'une école qui n'a pas délivré la pièce.
#:
#: Trois fuites de cette famille ont été trouvées, l'une après l'autre, et
#: toujours de la même manière : en OUVRANT l'image, jamais en lisant le
#: code. Aucune extraction de texte ne les voyait — le nom est dans une
#: matrice de pixels. Cette table transforme trois découvertes ponctuelles
#: en une règle : `test_academy_identity_separation.py` échoue si une
#: académie déclare une image rattachée à une autre, y compris pour une
#: image ajoutée demain.
ACADEMY_BOUND_ASSETS = {
    "logo_feba.jpeg": (
        "FEBA",
        "« Faith & Excellence Bilingual Academy » incrusté sous le bouclier."),
    "cachet_feba.png": (
        "FEBA",
        "« COMPLEXE SCOLAIRE FAITH & EXCELLENCE BILINGUAL ACADEMY » en "
        "couronne, autour de « LA DIRECTION »."),
    "cachet_feba_hd.png": (
        "FEBA", "Même couronne, version haute définition."),
    "cachet_secretariat.png": (
        "FEBA",
        "« COMPLEXE SCOLAIRE FAITH & EXCELLENCE BILINGUAL ACADEMY » en "
        "couronne, autour de « LE SECRÉTARIAT »."),
    "cachet_secretariat_hd.png": (
        "FEBA", "Même couronne, version haute définition."),
}

#: Images du GROUPE, communes aux deux académies parce qu'elles ne nomment
#: aucune école. `logo_groupe_feba.png` est `logo_feba.jpeg` coupée dans la
#: bande blanche mesurée sous le bouclier : le blason et son ruban « Faith
#: & Excellence » — la devise du groupe, pas le nom d'une école — sont
#: conservés au pixel près.
GROUP_ASSETS = ("logo_groupe_feba.png",)

#: Identité livrée de chaque académie, indexée par son CODE INTERNE STABLE.
#:
#: Ce n'est PAS un branding générique appliqué à toutes les académies :
#: chaque entrée décrit UNE académie précise, exactement comme
#: `School.DEFAULT_FEATURES` décrit un type d'entité. Une académie créée par
#: un administrateur — donc sans code connu ici — n'hérite de rien : palette
#: neutre, aucune image, et `branding_check` le signale.
#:
#: `School.settings['branding']` reste prioritaire : ces valeurs sont un
#: point de départ administrable, pas une contrainte.
#:
#: Les couleurs viennent de la charte du site (frontend/tailwind.config.js).
#: Les deux académies partagent le bleu du groupe — elles appartiennent
#: réellement au même groupe éducatif. Ce qui les distingue est la couleur
#: secondaire : l'or de l'école de Cotonou, le vert de l'académie en ligne.
ACADEMY_DEFAULTS = {
    "FEBA": {
        "primary_color": "#071D49",
        "secondary_color": "#0E2A63",
        "accent_color": "#D89B16",
        "background_color": "#F7F2E8",
        "group_name": "GROUPE ÉDUCATIF FEBA",
        "document_prefix": "FEBA",
        "document_logo": "logo_feba.jpeg",
        "stamp": "cachet_feba.png",
        "secretary_stamp": "cachet_secretariat.png",
        "director_signature": "signature_direction.png",
        "footer_text": "Faith & Excellence Bilingual Academy — Akpakpa, Cotonou, Bénin",
    },
    "FEBA_FHA": {
        "primary_color": "#071D49",
        "secondary_color": "#1F6B36",
        "accent_color": "#D89B16",
        "background_color": "#FFFFFF",
        "group_name": "GROUPE ÉDUCATIF FEBA",
        "document_prefix": "FHA",
        # DÉFAUT TROUVÉ EN REGARDANT UN RAPPORT MENSUEL PRODUIT, PAS EN
        # LISANT LE CODE.
        #
        # Les deux académies partageaient `logo_feba.jpeg`. Or cette
        # image ne contient pas seulement le blason du groupe : le
        # libellé « Faith & Excellence Bilingual Academy » y est
        # incrusté, sous le bouclier. Chaque document de l'académie en
        # ligne — fiche d'inscription, reçu, rapport mensuel — portait
        # donc en tête le nom de l'école de Cotonou, en toutes lettres.
        #
        # Aucun test textuel ne pouvait l'attraper : le nom était dans
        # une image matricielle, invisible à l'extraction de texte.
        #
        # `logo_groupe_feba.png` est la MÊME image, coupée dans la bande
        # blanche mesurée entre le bouclier (fin y=392) et le libellé
        # (début y=412). Le blason et son ruban « Faith & Excellence »
        # sont intacts au pixel près ; seul le nom de l'autre académie
        # est retiré. Le nom correct est déjà imprimé juste en dessous,
        # en texte, par le générateur.
        "document_logo": "logo_groupe_feba.png",
        # MEME DEFAUT QUE LE LOGO, TROUVE SUR LE CERTIFICAT PRODUIT.
        #
        # `cachet_feba.png` porte en couronne « COMPLEXE SCOLAIRE FAITH &
        # EXCELLENCE BILINGUAL ACADEMY ». Appose sur un certificat de
        # l'academie en ligne, il y estampille le nom de l'ecole de
        # Cotonou — sur la piece qui fait foi.
        #
        # Aucun cachet propre a FEBA French Heritage Academy n'a ete
        # fourni. On n'en appose donc AUCUN : un document sans cachet se
        # voit et se corrige, un document au cachet d'un autre
        # etablissement circule et fait autorite. Le medaillon du fond
        # reste net, sa mention d'exemple ayant ete neutralisee.
        #
        # Deposer le cachet officiel FHA dans `static_files/` et
        # remplacer None par son nom suffira a le retablir.
        "stamp": None,
        # TROISIÈME FUITE DE LA MÊME FAMILLE, TROUVÉE EN REGARDANT L'IMAGE.
        #
        # `cachet_secretariat.png` porte la même couronne que le cachet de
        # la direction : « COMPLEXE SCOLAIRE FAITH & EXCELLENCE BILINGUAL
        # ACADEMY ». Il n'était pas apposé sur les diplômes, ce qui l'avait
        # laissé passer — mais `payments/pdf_generator.py` l'appose sur
        # CHAQUE REÇU DE PAIEMENT. Une famille de la diaspora recevait donc
        # un reçu tamponné au nom de l'école de Cotonou.
        #
        # Même règle que pour le cachet de direction : rien n'est apposé.
        # La zone « Le Secrétariat » du reçu reste en place, avec sa
        # mention légale et sa ligne de lieu et date — un reçu sans cachet
        # se voit et se corrige ; un reçu au cachet d'un autre
        # établissement circule et fait autorité.
        "secretary_stamp": None,
        "director_signature": "signature_direction.png",
        "footer_text": "FEBA French Heritage Academy — programme en ligne pour la diaspora",
    },
}


def resolved_branding_settings(academy) -> dict:
    """
    Réglages d'identité effectifs : ceux livrés pour cette académie,
    surchargés par ce que l'établissement a administré.
    """
    base = dict(ACADEMY_DEFAULTS.get(academy.code or "", {}))
    administered = ((academy.settings or {}).get("branding")) or {}
    base.update({k: v for k, v in administered.items() if v})
    return base


@dataclass(frozen=True)
class AcademyBranding:
    """
    Identité complète d'une académie, telle qu'elle doit apparaître sur
    TOUS ses documents. Immuable : un générateur ne peut pas modifier
    l'identité d'une académie en cours de rendu.
    """

    # ── Identité ────────────────────────────────────────────────────────
    academy_id: int
    academy_code: str
    legal_name: str
    display_name: str
    short_name: str
    group_name: str

    # ── Images (chemins absolus vérifiés, ou None) ──────────────────────
    logo: Optional[str]
    document_logo: Optional[str]
    stamp: Optional[str]
    director_signature: Optional[str]
    secretary_stamp: Optional[str]

    # ── Couleurs ────────────────────────────────────────────────────────
    primary_color: str
    secondary_color: str
    accent_color: str
    background_color: str

    # ── Coordonnées ─────────────────────────────────────────────────────
    postal_address: str
    city: str
    country: str
    #: Numéro INSTITUTIONNEL du groupe, identique pour toutes les académies.
    #:
    #: Ce champ ne recopie plus `School.phone`. Un reçu est sorti avec
    #: « Tél: 0196697363 » — une valeur saisie en base, propre à une entité,
    #: qu'aucun test ne pouvait déclarer fausse. Le numéro imprimé sur une
    #: pièce officielle est celui par lequel une famille rappelle le groupe :
    #: il n'a pas à dépendre de l'entité émettrice ni de qui a rempli
    #: l'écran « Paramètres ». Il vient de `institution.official_phone()`.
    phone: str
    whatsapp: str
    email: str
    website: str

    # ── Localisation ────────────────────────────────────────────────────
    currency_code: str
    currency_symbol: str
    locale: str
    language: str
    timezone: str

    # ── Documents ───────────────────────────────────────────────────────
    footer_text: str
    document_prefix: str

    #: Vrai tant que les couleurs de cette académie n'ont pas été
    #: administrées. Consommé par `branding_check`, jamais par un rendu.
    palette_is_neutral: bool = False

    # ── Confort de rendu ────────────────────────────────────────────────

    @property
    def address_line(self) -> str:
        """
        Une ligne d'adresse lisible : « Akpakpa, Cotonou, Bénin | Tél: … ».

        Chaque partie manquante disparaît au lieu d'être remplacée par une
        valeur d'une autre académie.

        LA VILLE ET LE PAYS NE SONT AJOUTÉS QUE S'ILS MANQUENT.
        `School.address` est un champ libre, et il contient le plus souvent
        déjà la ville et le pays. Les recoller sans regarder imprimait
        « Akpakpa, Cotonou, Bénin, Cotonou, Bénin » en tête de chaque reçu
        — et, pour l'académie en ligne, faisait apparaître deux fois une
        ville qui n'est pas la sienne.
        """
        # `School.address` est un champ libre : il contient parfois un
        # numéro de téléphone, saisi à la main, hors service depuis. Le
        # laisser passer imprimerait deux numéros contradictoires sur la
        # même ligne — l'ancien dans l'adresse, l'officiel après « Tél: ».
        place = strip_retired_phones(self.postal_address or "")
        lowered = place.lower()
        for part in (self.city, self.country):
            if part and part.lower() not in lowered:
                place = f"{place}, {part}" if place else part
                lowered = place.lower()

        # Une adresse libre se termine parfois par un point : « …, Bénin. »
        # suivi de « | Tél: » se lit mal.
        place = place.strip().rstrip(".").strip()

        parts = [place] if place else []
        if self.phone:
            parts.append(f"Tél: {self.phone}")
        if self.email:
            parts.append(self.email)
        return " | ".join(parts)

    @property
    def location_line(self) -> str:
        """« Cotonou » pour une mention « fait à … le … ». Vide si inconnu."""
        return self.city or self.country or ""

    def money(self, amount_minor, with_symbol=True) -> str:
        """Formate un montant dans la devise de CETTE académie."""
        from apps.core.currency import get_currency
        return get_currency(self.currency_code).format(
            amount_minor, with_symbol=with_symbol,
        )

    def as_dict(self) -> dict:
        """Représentation sérialisable (API, exports, rapports d'audit)."""
        return {
            "academy_id": self.academy_id,
            "academy_code": self.academy_code,
            "legal_name": self.legal_name,
            "display_name": self.display_name,
            "short_name": self.short_name,
            "group_name": self.group_name,
            "logo": bool(self.logo),
            "document_logo": bool(self.document_logo),
            "stamp": bool(self.stamp),
            "director_signature": bool(self.director_signature),
            "secretary_stamp": bool(self.secretary_stamp),
            "primary_color": self.primary_color,
            "secondary_color": self.secondary_color,
            "accent_color": self.accent_color,
            "background_color": self.background_color,
            "postal_address": self.postal_address,
            "city": self.city,
            "country": self.country,
            "phone": self.phone,
            "whatsapp": self.whatsapp,
            "email": self.email,
            "website": self.website,
            "currency_code": self.currency_code,
            "currency_symbol": self.currency_symbol,
            "locale": self.locale,
            "language": self.language,
            "timezone": self.timezone,
            "footer_text": self.footer_text,
            "document_prefix": self.document_prefix,
            "palette_is_neutral": self.palette_is_neutral,
        }


# ── Résolution des ressources ────────────────────────────────────────────


def _static_asset(filename) -> Optional[str]:
    """
    Chemin absolu d'une ressource livrée, ou None si le fichier n'existe pas.

    Le nom est confiné à `static_files/` : un `settings['branding']` mal
    rempli — ou malveillant — ne peut pas faire lire `/etc/passwd` par un
    générateur de PDF.
    """
    if not filename:
        return None
    name = os.path.basename(str(filename))
    path = os.path.join(STATIC_FILES_DIR, name)
    return path if os.path.exists(path) else None


def _academy_logo(academy) -> Optional[str]:
    """Logo actif de l'académie. Jamais celui d'une autre."""
    try:
        from .models import SchoolBranding
        path = SchoolBranding.get_active_logo_path(academy)
        if path and os.path.exists(path):
            return path
    except Exception as exc:
        # Un stockage indisponible ne doit pas empêcher d'émettre un
        # document : il sortira sans logo, jamais avec celui d'une autre.
        logger.warning("Logo d'académie illisible (%s) : %s", academy, exc)
    return None


# ── Point d'entrée unique ────────────────────────────────────────────────


def get_branding(academy) -> AcademyBranding:
    """
    Identité complète de `academy` (instance de `schools.School`).

    Lève `BrandingUnavailable` si l'académie est inconnue : produire un
    document sans savoir à quelle personne morale il appartient n'a pas de
    solution par défaut acceptable.
    """
    if academy is None:
        raise BrandingUnavailable(
            "Aucune académie n'a pu être déterminée pour ce document. "
            "Un document officiel engage une personne morale précise : il "
            "ne peut pas être produit sous une identité par défaut."
        )

    brand = resolved_branding_settings(academy)

    palette = {key: brand.get(key) or NEUTRAL_PALETTE[key] for key in NEUTRAL_PALETTE}
    palette_is_neutral = not any(brand.get(key) for key in NEUTRAL_PALETTE)

    currency = academy.currency

    return AcademyBranding(
        academy_id=academy.pk,
        academy_code=academy.code or "",
        legal_name=academy.legal_name or academy.name,
        display_name=academy.name,
        short_name=academy.short_name,
        group_name=str(brand.get("group_name") or ""),
        logo=_academy_logo(academy),
        document_logo=_static_asset(brand.get("document_logo")) or _academy_logo(academy),
        stamp=_static_asset(brand.get("stamp")),
        director_signature=_static_asset(brand.get("director_signature")),
        secretary_stamp=_static_asset(brand.get("secretary_stamp")),
        primary_color=palette["primary_color"],
        secondary_color=palette["secondary_color"],
        accent_color=palette["accent_color"],
        background_color=palette["background_color"],
        postal_address=academy.address or "",
        city=academy.city or "",
        country=academy.country or "",
        # `academy.phone` n'est PAS lu ici. Voir `institution.py` : la
        # colonne reste une donnée de gestion administrable, elle n'est
        # plus l'autorité sur ce qui s'imprime.
        phone=official_phone(),
        whatsapp=academy.whatsapp or "",
        email=academy.email or "",
        website=str(brand.get("website") or ""),
        currency_code=academy.currency_code,
        currency_symbol=currency.symbol,
        locale=academy.effective_currency_locale,
        language=academy.default_language,
        timezone=academy.timezone or "",
        footer_text=strip_retired_phones(brand.get("footer_text") or ""),
        document_prefix=str(
            brand.get("document_prefix") or academy.matricule_prefix or academy.code or ""
        ).upper(),
        palette_is_neutral=palette_is_neutral,
    )


def get_branding_by_code(code) -> AcademyBranding:
    """Identité d'une académie désignée par son CODE INTERNE STABLE."""
    from .models import School
    return get_branding(School.objects.filter(code=code).first())


# ── Résolution de l'académie portée par un objet métier ──────────────────


def resolve_academy(obj) -> Optional[object]:
    """
    Académie d'un objet métier, par ordre de fiabilité décroissante.

    Un élève n'appartient qu'à une académie : c'est la source la plus sûre.
    Vient ensuite l'académie portée par l'objet lui-même, puis celle de
    l'année scolaire. Il n'y a volontairement AUCUN repli vers « la
    première académie de la base » : c'est ce repli qui faisait sortir des
    reçus FHA sous l'en-tête de Cotonou.
    """
    if obj is None:
        return None

    for attr in ("academy", "entity", "school"):
        value = getattr(obj, attr, None)
        if value is not None and hasattr(value, "currency_code"):
            return value

    student = getattr(obj, "student", None)
    if student is not None and getattr(student, "school_id", None):
        return student.school

    year = getattr(obj, "school_year", None)
    if year is not None and getattr(year, "school_id", None):
        return year.school

    return None


def branding_for(obj) -> AcademyBranding:
    """Identité de l'académie à laquelle appartient `obj`."""
    return get_branding(resolve_academy(obj))


def with_overrides(branding: AcademyBranding, **fields) -> AcademyBranding:
    """Copie d'une identité avec quelques champs remplacés (tests, aperçus)."""
    return replace(branding, **fields)
