"""
apps/documents/templates_registry.py — Chargement et vérification des gabarits

CE QUE CE MODULE GARANTIT
-------------------------
Un gabarit décrit un fond verrouillé et des zones variables, en
millimètres. Avant qu'une seule ligne ne soit imprimée dessus, trois
choses sont vérifiées :

  1. le fichier de fond existe ;
  2. ses dimensions en pixels sont exactement celles déclarées ;
  3. son empreinte SHA-256 est exactement celle déclarée.

Les trois sont nécessaires, et la troisième n'est pas redondante. Un
ré-export du même visuel — même logiciel, même taille — produit un fichier
différent au bit près : compression, profil colorimétrique, arrondi des
teintes. Les éléments peuvent s'y trouver décalés d'un ou deux pixels.
Sur un document officiel, ce décalage ne se voit pas et ne se corrige
jamais, parce que personne ne sait qu'il existe.

POURQUOI DES MILLIMÈTRES
------------------------
Le rendu final est un PDF destiné à l'impression ; les tolérances
s'expriment en millimètres, pas en pixels. Convertir une fois, au
chargement, évite de traîner deux unités dans tout le moteur — et évite
surtout les conversions approximatives faites à la volée.
"""
import hashlib
import json
import os

from django.conf import settings
from django.core.exceptions import ValidationError

from apps.documents.textfit import SafeZone

#: Racine des gabarits. Contient les fichiers JSON et le dossier
#: `originals/` où sont installés les fonds.
TEMPLATES_ROOT = getattr(
    settings, "DOCUMENT_TEMPLATES_ROOT",
    os.path.join(settings.BASE_DIR, "document_templates"),
)
ORIGINALS_DIR = os.path.join(TEMPLATES_ROOT, "originals")
#: Fonds dérivés — mentions d'exemple neutralisées. Régénérables, jamais
#: la référence : la comparaison pixel à pixel se fait contre l'ORIGINAL.
DERIVED_DIR = os.path.join(TEMPLATES_ROOT, "derived")

#: Tolérance de calibrage, en millimètres.
CALIBRATION_TOLERANCE_MM = 0.2


class TemplateError(ValidationError):
    """Gabarit absent, incomplet ou incohérent."""


class BackgroundMissing(TemplateError):
    """Le fond verrouillé n'est pas installé sur cette instance."""


class BackgroundMismatch(TemplateError):
    """Le fond installé n'est pas celui que le gabarit décrit."""


class BackgroundVariant:
    """
    Un fond qui n'est PAS l'original, explicitement accepté.

    POURQUOI CETTE NOTION EXISTE
    ----------------------------
    L'empreinte du fichier d'origine reste l'autorité. Mais un visuel peut
    parvenir à l'établissement par un canal qui le ré-encode — une
    messagerie, un outil de conversation, un export. Les pixels changent
    alors sans que la géométrie bouge d'un iota.

    Refuser sans recours immobiliserait le projet ; accepter en silence
    ferait passer un dérivé pour l'original. La variante est donc acceptée
    NOMMÉMENT, avec sa propre empreinte, sa provenance et le motif — et
    chaque document produit dessus porte cette information.
    """

    def __init__(self, data):
        self.sha256 = (data.get("sha256") or "").lower()
        self.source = data.get("source") or "inconnue"
        self.reason = data.get("reason") or ""
        self.accepted_by = data.get("accepted_by") or ""
        self.accepted_at = data.get("accepted_at") or ""
        self.lossy = bool(data.get("lossy", False))
        if len(self.sha256) != 64:
            raise TemplateError(
                "Une variante de fond doit déclarer une empreinte SHA-256 "
                "complète : sans elle, elle n'est pas identifiable."
            )

    def as_dict(self):
        return {
            "sha256": self.sha256, "source": self.source, "reason": self.reason,
            "accepted_by": self.accepted_by, "accepted_at": self.accepted_at,
            "lossy": self.lossy,
        }


def sha256_of(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


class Box:
    """Zone rectangulaire en millimètres, repère haut-gauche."""

    __slots__ = ("x_mm", "y_mm", "width_mm", "height_mm")

    def __init__(self, x_mm, y_mm, width_mm, height_mm):
        self.x_mm = float(x_mm)
        self.y_mm = float(y_mm)
        self.width_mm = float(width_mm)
        self.height_mm = float(height_mm)

    def __repr__(self):
        return (f"Box({self.x_mm}, {self.y_mm}, "
                f"{self.width_mm}×{self.height_mm} mm)")

    @classmethod
    def from_dict(cls, data, context=""):
        missing = {"x_mm", "y_mm", "width_mm", "height_mm"} - set(data or {})
        if missing:
            raise TemplateError(
                f"{context} : coordonnées incomplètes, manque {sorted(missing)}."
            )
        box = cls(data["x_mm"], data["y_mm"], data["width_mm"], data["height_mm"])
        if box.width_mm <= 0 or box.height_mm <= 0:
            raise TemplateError(f"{context} : zone de dimension nulle ou négative.")
        return box


class Field:
    """Un champ variable : ce que le moteur a le droit d'écrire."""

    def __init__(self, data):
        self.name = data.get("name")
        if not self.name:
            raise TemplateError("Un champ est déclaré sans nom.")
        self.label = data.get("label") or self.name
        self.type = data.get("type", "text")
        self.required = bool(data.get("required", False))
        self.box = Box.from_dict(data.get("box"), f"Champ « {self.name} »")
        self.align = data.get("align", "left")
        self.vertical_align = data.get("vertical_align", "middle")
        font = data.get("font") or {}
        self.font_family = font.get("family", "Helvetica")
        self.font_size = float(font.get("size_pt", 12))
        self.min_font_size = float(font.get("min_size_pt", self.font_size))
        self.color = data.get("color", "#000000")
        self.shrink_to_fit = bool(data.get("shrink_to_fit", True))
        self.max_lines = int(data.get("max_lines", 1))
        # Interligne NOMINAL, en multiples de la taille de police. Le
        # moteur de composition ne descend jamais en dessous de ce que
        # l'encre réelle des deux lignes exige : c'est un plancher, pas
        # une valeur imposée.
        self.line_spacing = float(data.get("line_spacing", 1.0))
        # Zone SÛRE, mesurée sur le fond livré (voir
        # DOCUMENT_TEMPLATE_CALIBRATION.md). Elle est distincte de la
        # boîte : la boîte dit où l'on écrit d'ordinaire, la zone sûre dit
        # jusqu'où l'encre a le droit d'aller sans toucher la phrase
        # gravée au-dessus ni la règle d'écriture en dessous. Sans elle,
        # un repli sur deux lignes n'a aucun repère et vient se poser sur
        # le texte du fond — ce qui est arrivé.
        zone = data.get("safe_zone")
        self.safe_zone = SafeZone.from_dict(zone) if zone else None
        # Profondeur réservée sous la dernière ligne de base, en em. Elle
        # doit couvrir le jambage le plus profond de la police (0,228 em
        # pour le « y » de Crimson Pro Italic), sans quoi un nom se
        # terminant par « Ahouangonou Gbenyon » traverserait la règle.
        self.baseline_reserve_em = float(data.get("baseline_reserve_em", 0.23))
        # `truncate` par défaut à False : couper le nom d'un élève sur son
        # propre diplôme n'est pas une dégradation acceptable. Le moteur
        # réduit la police, puis échoue franchement.
        self.truncate = bool(data.get("truncate", False))
        self.date_format = data.get("format", "%d/%m/%Y")
        # Débord : un champ occupe PLUS que sa boîte de texte. Les jambages
        # descendants (« p », « g », « j ») passent sous la ligne de base,
        # les accents montent au-dessus. Cette marge ne déplace rien au
        # rendu ; elle sert à la comparaison, pour ne pas compter les
        # jambages d'un nom comme une altération du fond.
        self.bleed_mm = float(data.get("bleed_mm", 0.0))


class PlaceholderMask:
    """
    Zone du fond à neutraliser avant d'écrire dessus.

    Le visuel d'origine contient des mentions d'exemple — « Nom Prénom »
    sur le diplôme — destinées à montrer la mise en page, pas à figurer
    sur un document remis à un élève. Écrire par-dessus les laisserait
    visibles en dessous.

    La neutralisation est faite sur l'IMAGE, une fois, et non à chaque
    rendu : un rectangle de couleur unie posé dans le PDF se verrait comme
    une pièce rapportée sur un fond texturé.
    """

    def __init__(self, data):
        self.name = data.get("name")
        if not self.name:
            raise TemplateError("Un masque est déclaré sans nom.")
        # Deux formes de masque, pour deux formes de support.
        #
        # `bande` (défaut) — une zone rectangulaire sur du papier texturé.
        #   La texture est reconstruite par interpolation entre une bande
        #   saine au-dessus et une bande saine en dessous.
        #
        # `medaillon` — une mention d'exemple posée sur un disque en
        #   dégradé, cerné d'un anneau doré. Un rectangle inscrit dans ce
        #   disque ne couvrirait pas tout le texte ; un rectangle qui le
        #   couvre mord sur l'anneau. On repeint donc UNIQUEMENT les
        #   pixels de l'encre, à l'intérieur d'un rayon donné, avec la
        #   médiane du fond à la même distance du centre. Le dégradé est
        #   respecté et l'anneau n'est jamais touché.
        self.kind = data.get("kind", "bande")
        if self.kind not in ("bande", "medaillon"):
            raise TemplateError(
                f"Le masque « {self.name} » déclare une forme inconnue : "
                f"« {self.kind} ». Formes acceptées : bande, medaillon."
            )

        if self.kind == "medaillon":
            for cle in ("center_x_mm", "center_y_mm", "radius_mm"):
                if data.get(cle) is None:
                    raise TemplateError(
                        f"Le masque « {self.name} » est un médaillon mais ne "
                        f"déclare pas « {cle} » : sans centre ni rayon, il n'y "
                        f"a pas de disque à reconstruire."
                    )
            self.center_x_mm = float(data["center_x_mm"])
            self.center_y_mm = float(data["center_y_mm"])
            self.radius_mm = float(data["radius_mm"])
            # Écart maximal toléré à la couleur médiane du disque, en
            # distance euclidienne RGB. Au-delà, le pixel est considéré
            # comme de l'encre d'exemple et repeint.
            #
            # On raisonne en ÉCART et non en couleur : les lettres du
            # médaillon sont gravées, avec un cœur doré ET une ombre plus
            # sombre que le fond. Une règle de couleur n'attrape que le
            # cœur et laisse le relief parfaitement lisible.
            self.ink_tolerance = float(data.get("ink_tolerance", 10))
            # Passes de dilatation du masque d'encre. Sans elles, le halo
            # d'antialiasing autour de chaque lettre reste et la mention
            # demeure lisible bien qu'aucun pixel ne dépasse la tolérance.
            self.ink_dilation = int(data.get("ink_dilation", 3))
            self.box = None
            self.sample_above_y_mm = None
            self.sample_below_y_mm = None
            self.sample_band_mm = 0.0
            self.bleed_mm = 0.0
            self.preserve = []
            self.note = data.get("note", "")
            return

        self.box = Box.from_dict(data.get("box"), f"Masque « {self.name} »")

        # Bandes de référence, en position ABSOLUE : d'où la texture de
        # remplacement est prélevée. Absolue et non relative à la zone,
        # parce que « cinq millimètres plus bas » peut tomber sur le
        # paragraphe suivant — ce qui reproduit son antialiasing en
        # stries verticales.
        self.sample_above_y_mm = data.get("sample_above_y_mm")
        self.sample_below_y_mm = data.get("sample_below_y_mm")
        if self.sample_above_y_mm is None and self.sample_below_y_mm is None:
            raise TemplateError(
                f"Le masque « {self.name} » ne déclare aucune bande de "
                f"prélèvement : il n'y a pas de texture à reconstruire."
            )
        self.sample_above_y_mm = (float(self.sample_above_y_mm)
                                  if self.sample_above_y_mm is not None else None)
        self.sample_below_y_mm = (float(self.sample_below_y_mm)
                                  if self.sample_below_y_mm is not None else None)
        # Hauteur de la bande prélevée. Une seule ligne suffirait si le
        # papier était uni ; il est texturé, donc on prend la MÉDIANE de
        # plusieurs lignes pour ne pas recopier son grain à l'identique.
        self.sample_band_mm = float(data.get("sample_band_mm", 1.4))

        # Sous-bandes à NE PAS toucher : la règle d'écriture traverse la
        # zone du placeholder et doit rester pixel pour pixel.
        self.bleed_mm = float(data.get("bleed_mm", 0.0))
        self.preserve = [
            Box.from_dict(
                {"x_mm": item.get("x_mm", self.box.x_mm),
                 "y_mm": item["y_mm"],
                 "width_mm": item.get("width_mm", self.box.width_mm),
                 "height_mm": item["height_mm"]},
                f"Zone préservée de « {self.name} »",
            )
            for item in (data.get("preserve") or [])
        ]
        self.note = data.get("note", "")


class Asset:
    """Une image officielle — signature, cachet — jamais inventée."""

    def __init__(self, data):
        self.name = data.get("name")
        if not self.name:
            raise TemplateError("Un asset est déclaré sans nom.")
        self.label = data.get("label") or self.name
        self.required = bool(data.get("required", False))
        self.resource = data.get("resource")
        self.box = Box.from_dict(data.get("box"), f"Asset « {self.name} »")
        self.fit = data.get("fit", "contain")
        # Disque clair optionnel, dessiné sous l'image : voir le rendu.
        self.backdrop = data.get("backdrop")
        self.backdrop_shape = data.get("backdrop_shape", "circle")
        self.backdrop_diameter_mm = float(data.get("backdrop_diameter_mm", 0) or 0)
        self.bleed_mm = float(data.get("bleed_mm", 0.0))


class DocumentTemplate:
    """Gabarit chargé, validé et prêt à rendre."""

    def __init__(self, data, path):
        self.path = path
        self.raw = data
        self.id = data.get("id")
        if not self.id:
            raise TemplateError(f"{path} : gabarit sans identifiant.")
        self.version = int(data.get("version", 1))
        self.label = data.get("label") or self.id

        # P8 — Académies autorisées à émettre ce document, par CODE INTERNE.
        #
        # Un fond porte l'identité visuelle d'UNE académie. Le proposer aux
        # autres produirait un document au nom d'une académie et à
        # l'effigie d'une autre — une erreur invisible pour celui qui le
        # reçoit. Liste vide = aucune restriction.
        self.academies = [
            str(code).upper() for code in (data.get("academies") or [])
        ]

        background = data.get("background") or {}
        self.background_file = background.get("file")
        # Répertoire du fond, relatif à TEMPLATES_ROOT. Vide = originals/.
        self.background_directory = (background.get("directory") or "").strip("/")
        self.background_sha256 = (background.get("sha256") or "").lower()
        # P7 — Empreinte du fond NEUTRALISÉ, versionné avec le projet.
        # Déclarée, elle rend le dérivé vérifiable ; absente, le gabarit
        # n'a pas de mention d'exemple à neutraliser.
        self.derived_sha256 = (background.get("derived_sha256") or "").lower()
        self.background_width_px = int(background.get("width_px") or 0)
        self.background_height_px = int(background.get("height_px") or 0)
        if not (self.background_file and self.background_sha256
                and self.background_width_px and self.background_height_px):
            raise TemplateError(
                f"{path} : le fond doit déclarer un fichier, une empreinte "
                f"SHA-256 et ses dimensions en pixels. Sans les trois, rien "
                f"ne distingue l'original d'un ré-export."
            )

        page = data.get("page") or {}
        self.page_width_mm = float(page.get("width_mm", 297.0))
        self.page_height_mm = float(page.get("height_mm", 210.0))
        self.fit = page.get("fit", "contain")

        self.origin = data.get("origin", "top-left")
        if self.origin != "top-left":
            raise TemplateError(
                f"{path} : seul le repère « top-left » est pris en charge."
            )

        calibration = data.get("calibration") or {}
        self.calibrated = bool(data.get("calibrated", False))
        self.tolerance_mm = float(
            calibration.get("tolerance_mm", CALIBRATION_TOLERANCE_MM)
        )
        self.calibration = calibration
        self.provisional_layout = bool(data.get("provisional_layout", False))

        self.fields = [Field(item) for item in data.get("fields", [])]
        self.assets = [Asset(item) for item in data.get("assets", [])]
        self.masks = [PlaceholderMask(item) for item in data.get("placeholder_masks", [])]
        self.variants = [BackgroundVariant(item)
                         for item in (background.get("accepted_variants") or [])]
        if not self.fields:
            raise TemplateError(f"{path} : aucun champ variable déclaré.")

        names = [field.name for field in self.fields]
        if len(names) != len(set(names)):
            raise TemplateError(f"{path} : deux champs portent le même nom.")

        self._check_boxes_inside_page()
        self._check_safe_zones()

    def _check_safe_zones(self):
        """
        Une zone sûre incohérente vaut moins que pas de zone sûre du tout :
        elle donne au moteur un repère faux et l'autorise à écrire là où il
        ne faut pas, en toute confiance.
        """
        for field in self.fields:
            zone = field.safe_zone
            if zone is None:
                continue
            contexte = f"Zone sûre du champ « {field.name} »"
            if zone.height_mm <= 0 or zone.width_mm <= 0:
                raise TemplateError(
                    f"{contexte} : hauteur ou largeur nulle ou négative "
                    f"({zone.width_mm:.2f} × {zone.height_mm:.2f} mm)."
                )
            if (zone.y_top_mm < 0 or zone.x_left_mm < 0
                    or zone.y_bottom_mm > self.page_height_mm + 0.01
                    or zone.x_right_mm > self.page_width_mm + 0.01):
                raise TemplateError(f"{contexte} : sort de la page.")
            # La boîte reste le repère du rendu sur une ligne ; si elle
            # sort de la zone sûre, l'un des deux calibrages est faux.
            if (field.box.x_mm < zone.x_left_mm - 0.01
                    or field.box.x_mm + field.box.width_mm
                    > zone.x_right_mm + 0.01):
                raise TemplateError(
                    f"{contexte} : la boîte du champ ({field.box.x_mm}–"
                    f"{field.box.x_mm + field.box.width_mm} mm) déborde "
                    f"latéralement de la zone sûre ({zone.x_left_mm}–"
                    f"{zone.x_right_mm} mm)."
                )

    @property
    def all_boxes(self):
        return list(self.fields) + list(self.assets) + list(self.masks)

    def _check_boxes_inside_page(self):
        """
        Une zone qui dépasse la page produit un texte invisible, sans la
        moindre erreur au moment du rendu : le document sort « réussi »,
        amputé de son contenu.
        """
        for item in self.all_boxes:
            box = item.box
            if box is None:
                # Masque radial : décrit par un centre et un rayon, pas par
                # un rectangle. On vérifie son disque, pas sa boîte.
                gauche = item.center_x_mm - item.radius_mm
                haut = item.center_y_mm - item.radius_mm
                droite = item.center_x_mm + item.radius_mm
                bas = item.center_y_mm + item.radius_mm
                if (gauche < 0 or haut < 0
                        or droite > self.page_width_mm + 0.01
                        or bas > self.page_height_mm + 0.01):
                    raise TemplateError(
                        f"Le médaillon « {item.name} » sort de la page "
                        f"({self.page_width_mm}×{self.page_height_mm} mm)."
                    )
                continue
            if (box.x_mm < 0 or box.y_mm < 0
                    or box.x_mm + box.width_mm > self.page_width_mm + 0.01
                    or box.y_mm + box.height_mm > self.page_height_mm + 0.01):
                raise TemplateError(
                    f"« {item.name} » sort de la page "
                    f"({self.page_width_mm}×{self.page_height_mm} mm) : "
                    f"son contenu serait rendu hors du document, sans erreur."
                )

    # ── Fond verrouillé ───────────────────────────────────────────────

    @property
    def background_path(self):
        """
        Emplacement du fond d'origine.

        Le répertoire est déclarable par gabarit (`background.directory`).
        Les visuels de l'école de Cotonou vivent dans `originals/`, ceux de
        l'académie en ligne dans `sources/feba_fha/` : deux établissements,
        deux jeux de sources, et une erreur de rangement se voit sur le
        disque plutôt que de dépendre d'un nom de fichier bien choisi.
        """
        if self.background_directory:
            return os.path.join(TEMPLATES_ROOT, self.background_directory,
                                self.background_file)
        return os.path.join(ORIGINALS_DIR, self.background_file)

    @property
    def derived_path(self):
        """
        Fond dont les mentions d'exemple ont été neutralisées.

        Séparé de l'original, jamais à sa place : l'original reste la
        référence de la comparaison pixel à pixel, le dérivé sert au rendu.
        """
        base, ext = os.path.splitext(self.background_file)
        return os.path.join(DERIVED_DIR, f"{base}.neutralise{ext}")

    @property
    def has_derived(self):
        return bool(self.masks) and os.path.exists(self.derived_path)

    @property
    def derived_digest(self):
        """Empreinte du dérivé réellement présent sur le disque, ou None."""
        if not os.path.exists(self.derived_path):
            return None
        return sha256_of(self.derived_path)

    def derived_problem(self):
        """
        Ce qui empêche d'utiliser le fond neutralisé, ou None si tout va bien.

        P7 — Le dérivé est VERSIONNÉ : il arrive avec l'application. Il n'y
        a donc plus de commande à lancer, et l'absence du fichier n'est plus
        un état de travail normal mais une installation abîmée. Son
        empreinte est vérifiée : un dérivé altéré ne doit pas plus servir
        qu'un dérivé absent.
        """
        if not self.masks:
            return None

        if not os.path.exists(self.derived_path):
            return (
                f"Le fond neutralisé du gabarit « {self.id} » est absent de "
                f"l'installation ({os.path.basename(self.derived_path)}). Il "
                f"est livré avec le projet ; son absence signale une archive "
                f"incomplète ou un fichier supprimé. Sans lui, le document "
                f"sortirait avec la mention d'exemple visible sous le vrai "
                f"contenu. Réparation : « make documents-install »."
            )

        if not self.derived_sha256:
            return (
                f"Le gabarit « {self.id} » déclare des mentions à neutraliser "
                f"mais aucune empreinte pour son fond neutralisé : rien ne "
                f"distinguerait un dérivé correct d'un fichier altéré."
            )

        digest = self.derived_digest
        if digest != self.derived_sha256:
            return (
                f"Le fond neutralisé du gabarit « {self.id} » ne correspond "
                f"pas à son empreinte (installée {digest[:16]}…, attendue "
                f"{self.derived_sha256[:16]}…). Il a été modifié ou "
                f"régénéré depuis un autre original. Il n'est pas utilisé : "
                f"un fond altéré déplacerait ou révélerait des éléments sans "
                f"que rien ne le signale à l'écran."
            )
        return None

    @property
    def derived_is_valid(self):
        return self.derived_problem() is None

    @property
    def render_background_path(self):
        """
        Image réellement dessinée.

        Le dérivé N'EST utilisé QUE s'il est conforme à son empreinte. Le
        repli silencieux vers l'original est exclu : c'est précisément lui
        qui faisait sortir un diplôme avec « Nom Prénom » sous le vrai nom.
        Un dérivé absent ou altéré bloque l'émission (voir
        `issuance_blockers`), il ne dégrade pas le rendu.
        """
        if self.masks:
            return self.derived_path
        return self.background_path

    @property
    def background_installed(self):
        return os.path.exists(self.background_path)

    def verify_background(self):
        """
        Vérifie que le fond installé est bien l'original.

        Lève une exception plutôt que de renvoyer False : un appelant qui
        oublie de tester un booléen imprimerait sur le mauvais fond.
        """
        path = self.background_path
        if not os.path.exists(path):
            raise BackgroundMissing(
                f"Le fond « {self.background_file} » n'est pas installé "
                f"({ORIGINALS_DIR}). Voir originals/README.md : il s'installe "
                f"avec « manage.py install_document_template »."
            )

        try:
            from PIL import Image

            with Image.open(path) as image:
                width, height = image.size
        except Exception as exc:
            raise BackgroundMismatch(
                f"Le fond « {self.background_file} » n'est pas une image "
                f"lisible : {exc}"
            ) from exc

        if (width, height) != (self.background_width_px, self.background_height_px):
            raise BackgroundMismatch(
                f"Le fond « {self.background_file} » mesure {width}×{height} px "
                f"au lieu de {self.background_width_px}×"
                f"{self.background_height_px}. Un recadrage de quelques pixels "
                f"déplace tous les éléments : le calibrage serait faux sans "
                f"que rien ne le signale."
            )

        digest = sha256_of(path)
        if digest == self.background_sha256:
            return digest

        # Variante explicitement acceptée : elle n'est pas l'original, et
        # c'est écrit. Le document produit dessus le mentionnera.
        variant = self.variant_for(digest)
        if variant is not None:
            return digest

        raise BackgroundMismatch(
            f"Le fond « {self.background_file} » a l'empreinte {digest}, "
            f"attendue {self.background_sha256}. Même visuel ne veut pas "
            f"dire même fichier : un ré-export change la compression et "
            f"peut décaler les ornements.\n"
            f"Si ce fichier provient d'un canal qui le ré-encode, il peut "
            f"être accepté nommément :\n"
            f"  manage.py install_document_template --template {self.id} "
            f"--file … --accept-variant --reason « … »"
        )

    def variant_for(self, digest):
        """Variante acceptée correspondant à cette empreinte, ou None."""
        for variant in self.variants:
            if variant.sha256 == digest:
                return variant
        return None

    @property
    def installed_digest(self):
        if not self.background_installed:
            return None
        return sha256_of(self.background_path)

    @property
    def is_original(self):
        """Vrai si le fond installé est bien le fichier d'origine."""
        return self.installed_digest == self.background_sha256

    @property
    def installed_variant(self):
        digest = self.installed_digest
        return self.variant_for(digest) if digest else None

    # ── Aptitude à l'émission ─────────────────────────────────────────

    def issuance_blockers(self):
        """
        Raisons — factuelles — pour lesquelles ce gabarit ne peut pas
        produire un document officiel. Liste vide = émission possible.
        """
        blockers = []
        try:
            self.verify_background()
        except TemplateError as exc:
            blockers.append(exc.messages[0] if exc.messages else str(exc))

        if not self.calibrated:
            blockers.append(
                "Le gabarit n'est pas calibré : les positions n'ont jamais été "
                "confrontées à l'image réelle. Un nom décalé de trois "
                "millimètres reste un diplôme aux yeux de celui qui le reçoit."
            )

        # P7 — Le fond neutralisé est livré et vérifié. Ce n'est plus une
        # étape que l'utilisateur doit accomplir : c'est une intégrité que
        # l'application contrôle.
        problem = self.derived_problem()
        if problem:
            blockers.append(problem)
        return blockers

    def allows_academy(self, academy):
        """Cette académie peut-elle émettre ce document ?"""
        if not self.academies:
            return True
        code = (getattr(academy, "code", None) or "").upper()
        return code in self.academies

    def academy_blocker(self, academy):
        """Raison — factuelle — pour laquelle cette académie ne peut pas."""
        if self.allows_academy(academy):
            return None
        return (
            f"Ce gabarit est réservé à : {', '.join(self.academies)}. Son "
            f"fond porte l'identité visuelle de cette académie ; l'utiliser "
            f"pour « {getattr(academy, 'name', 'cette académie')} » "
            f"produirait un document au nom d'une académie et à l'effigie "
            f"d'une autre."
        )

    @property
    def can_issue(self):
        return not self.issuance_blockers()

    def fingerprint(self):
        """
        Empreinte du gabarit lui-même — coordonnées comprises.

        Conservée sur chaque document émis : elle permet de dire, des
        années plus tard, avec quelle version de la mise en page un
        document a été produit.
        """
        payload = json.dumps(self.raw, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


# ── Chargement ────────────────────────────────────────────────────────

_CACHE = {}


def template_path(template_id):
    return os.path.join(TEMPLATES_ROOT, f"{template_id}_template.json")


def load_template(template_id, use_cache=True):
    if use_cache and template_id in _CACHE:
        return _CACHE[template_id]

    path = template_path(template_id)
    if not os.path.exists(path):
        # LE CHEMIN DU SERVEUR NE SORT PAS.
        #
        # Ce message remonte tel quel au navigateur : un gabarit inconnu
        # est une erreur de saisie (400), pas un incident, et le
        # gestionnaire d'exceptions le laisse donc passer. Il affichait
        # « /home/…/backend/document_templates/None_template.json » —
        # l'arborescence du serveur, offerte à qui poste un identifiant
        # au hasard. Trouvé en produisant un document depuis le
        # navigateur, pas en lisant le code.
        #
        # La liste des gabarits disponibles reste : elle est déjà
        # publiée par `/api/documents/templates/` et aide à corriger.
        raise TemplateError(
            f"Gabarit « {template_id} » introuvable. "
            f"Gabarits disponibles : {', '.join(available_templates()) or 'aucun'}."
        )
    with open(path, encoding="utf-8") as handle:
        try:
            data = json.load(handle)
        except json.JSONDecodeError as exc:
            raise TemplateError(f"{path} : JSON invalide — {exc}") from exc

    template = DocumentTemplate(data, path)
    if use_cache:
        _CACHE[template_id] = template
    return template


def available_templates():
    if not os.path.isdir(TEMPLATES_ROOT):
        return []
    return sorted(
        name[: -len("_template.json")]
        for name in os.listdir(TEMPLATES_ROOT)
        if name.endswith("_template.json")
    )


def clear_cache():
    _CACHE.clear()
