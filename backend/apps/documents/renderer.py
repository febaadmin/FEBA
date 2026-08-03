"""
apps/documents/renderer.py — Rendu des diplômes et certificats

CE QUE FAIT LE MOTEUR
---------------------
Il pose le fond original, tel quel, sans le redessiner ni le reconstituer,
puis écrit UNIQUEMENT les champs déclarés dans le gabarit. Bordures,
ornements, médailles, rubans, sceaux, logo, texture, typographie fixe :
rien de tout cela n'est reproduit, donc rien ne peut en dériver.

LE RAPPORT D'ASPECT EST PRÉSERVÉ
--------------------------------
Le fond n'a pas exactement les proportions de l'A4 paysage — 1492/1054
contre 297/210, soit 0,09 % d'écart. L'étirer jusqu'aux bords serait
invisible à l'œil et déplacerait chaque élément d'environ 0,1 mm, la
moitié de la tolérance de calibrage. Le fond est donc inscrit dans la
page en conservant ses proportions, et centré ; le décentrage résiduel
est calculé, pas subi.

L'APERÇU ET LE DOCUMENT SONT LE MÊME RENDU
------------------------------------------
Une seule fonction produit les deux. Un aperçu calculé autrement finirait
par diverger du document remis à l'élève — et l'écart se découvrirait à
l'impression, une fois le diplôme signé.
"""
import os

from django.core.exceptions import ValidationError
from reportlab.lib.colors import HexColor
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfgen import canvas

from apps.documents.templates_registry import load_template
from apps.documents.textfit import (
    EMBEDDED_FONTS,
    FONTS_DIR,
    RESOURCES_DIR,
    CompositionRefused,
    MetricsError,
    compose,
    get_text_bbox,
)

__all__ = [
    "EMBEDDED_FONTS", "FONTS_DIR", "RESOURCES_DIR", "RenderError",
    "ensure_fonts", "render_document", "resolve_resource",
]

_fonts_loaded = False


def ensure_fonts():
    """
    Enregistre les polices du projet auprès de ReportLab.

    Idempotent : appelé à chaque rendu, il ne relit les fichiers qu'une
    fois. Une police manquante échoue ICI, avec son nom — pas plus tard,
    par une substitution silencieuse par Helvetica.
    """
    global _fonts_loaded
    if _fonts_loaded:
        return
    from reportlab.pdfbase.ttfonts import TTFont

    for name, filename in EMBEDDED_FONTS.items():
        path = os.path.join(FONTS_DIR, filename)
        if not os.path.exists(path):
            raise RenderError(
                f"Police « {name} » introuvable ({path}). Les documents "
                f"officiels ne peuvent pas être rendus avec une police de "
                f"substitution : la mise en page changerait sans prévenir."
            )
        try:
            pdfmetrics.registerFont(TTFont(name, path))
        except Exception as exc:  # pragma: no cover — fichier corrompu
            raise RenderError(f"Police « {name} » illisible : {exc}") from exc
    _fonts_loaded = True


class RenderError(ValidationError):
    """Le document ne peut pas être rendu tel que demandé."""


#: Ressource déclarée par un gabarit → champ de l'identité qui la fournit.
#:
#: P0 — LE MOTEUR NE CONNAÎT AUCUN NOM DE FICHIER. Un cachet appartient à
#: UNE académie ; tant que la résolution passait par une liste de noms
#: écrite ici, le diplôme d'une académie pouvait porter le sceau de
#: l'autre, sans qu'aucun contrôle ne le signale. Le moteur ne sait plus
#: que traduire un rôle (« le sceau officiel ») en un champ de l'identité
#: qu'on lui remet.
RESOURCE_BRANDING_FIELDS = {
    "seal_official": "stamp",
    "signature_director": "director_signature",
    "seal_secretariat": "secretary_stamp",
    "academy_logo": "document_logo",
}


def resolve_resource(name, branding=None):
    """
    Chemin de la ressource officielle de CETTE académie, ou None.

    Sans identité — sondes de calibrage, mesures géométriques — rien n'est
    résolu et donc rien n'est apposé : ces outils travaillent la géométrie
    du gabarit, pas l'identité d'un établissement.
    """
    if branding is None:
        return None
    field = RESOURCE_BRANDING_FIELDS.get(name)
    if field is None:
        return None
    path = getattr(branding, field, None)
    return path if path and os.path.exists(path) else None


class Layout:
    """Placement du fond dans la page, proportions préservées."""

    def __init__(self, template):
        page_w, page_h = template.page_width_mm, template.page_height_mm
        ratio = template.background_width_px / template.background_height_px

        if template.fit == "stretch":
            width, height = page_w, page_h
        elif ratio >= page_w / page_h:
            width, height = page_w, page_w / ratio
        else:
            width, height = page_h * ratio, page_h

        self.width_mm = width
        self.height_mm = height
        self.offset_x_mm = (page_w - width) / 2
        self.offset_y_mm = (page_h - height) / 2
        self.page_width_mm = page_w
        self.page_height_mm = page_h

    def to_pdf(self, x_mm, y_mm):
        """
        Coordonnée gabarit (haut-gauche, mm) → coordonnée PDF (bas-gauche, pt).

        Les gabarits sont écrits comme on lit une maquette : origine en
        haut à gauche. ReportLab compte depuis le bas. Cette conversion
        est faite ICI, une fois — la refaire à chaque appel serait la
        source d'erreurs la plus prévisible du moteur.
        """
        return x_mm * mm, (self.page_height_mm - y_mm) * mm


def plan_text(field, text):
    """
    Décide, SANS DESSINER, comment un texte occupera son champ.

    Renvoie `(lignes, taille_pt, interligne_pt, baseline_y_mm)`. Séparer
    la décision du tracé n'est pas une élégance : c'est ce qui permet de
    vérifier une mise en page par le calcul, sans produire de PDF ni
    l'ouvrir, et donc de l'éprouver sur autant de noms qu'on veut.

    DEUX RÉGIMES, SELON CE QUE LE GABARIT A MESURÉ
    ----------------------------------------------
    Un champ qui déclare une `safe_zone` — les quatre champs de nom —
    passe par le moteur de composition : zone mesurée sur le fond, repli
    sur deux lignes, métriques réelles de la police.

    Un champ qui n'en déclare pas — date, signataire, numéro — garde le
    comportement d'origine : une ligne, réduite si nécessaire, calée dans
    sa boîte. Ces champs tiennent depuis le début et n'ont rien à gagner
    à changer de régime.
    """
    if field.safe_zone is not None:
        return _plan_in_safe_zone(field, text)
    return _plan_in_box(field, text)


def _plan_in_safe_zone(field, text):
    """Composition d'un nom dans une zone mesurée sur le fond."""
    zone = field.safe_zone
    try:
        composition = compose(
            text,
            font_family=field.font_family,
            size_pt=field.font_size,
            min_size_pt=field.min_font_size,
            max_lines=field.max_lines,
            available_width_pt=zone.width_mm * mm,
            zone_height_pt=zone.height_mm * mm,
            baseline_reserve_em=field.baseline_reserve_em,
            leading_ratio=field.line_spacing,
        )
    except CompositionRefused as exc:
        raise RenderError(
            f"Le champ « {field.label} » ne peut pas être composé : {exc} "
            f"Le document n'est pas produit — un nom tronqué ou débordant "
            f"sur un document officiel est une erreur qui circule sans se "
            f"voir."
        ) from exc

    # La dernière ligne de base, en millimètres, comptée depuis le BAS de
    # la zone sûre : elle remonte quand le corps grandit, exactement de la
    # profondeur du jambage descendant qu'il faut réserver.
    baseline_y_mm = zone.y_bottom_mm - composition.baseline_offset_pt / mm
    return (list(composition.lines), composition.size_pt,
            composition.leading_pt, baseline_y_mm)


def _advance(text, family, size):
    """
    Largeur d'avance d'une chaîne, en points.

    Les polices embarquées sont mesurées dans leur fichier ; les
    quatorze polices de base de PostScript — utilisées par le filigrane,
    la grille de calibrage et les gabarits d'essai — n'ont pas de fichier
    et sont mesurées par ReportLab, qui en porte les tables.
    """
    try:
        return get_text_bbox(text, family, size).advance
    except MetricsError:
        return pdfmetrics.stringWidth(text, family, size)


def _plan_in_box(field, text):
    """
    Une ligne, réduite si nécessaire, calée dans la boîte du champ.

    OÙ SE POSE LA LIGNE DE BASE, ET POURQUOI ELLE NE BOUGE PAS
    ----------------------------------------------------------
    Ce chemin sert aux cinq champs courts — date, directeur, enseignant,
    signataire, numéro — dont les boîtes ont été calibrées contre le fond,
    au millimètre, par `manage.py document_calibrate`.

    La version d'origine écrivait, pour un alignement en bas :

        baseline = boîte.bas + getAscent(police, corps) / 1000 × corps

    `getAscent(police, corps)` rend DÉJÀ des points : la diviser par 1000
    puis la remultiplier par le corps la réduit d'un facteur ~30. À 11 pt,
    la correction de descendante valait 0,009 mm au lieu de 0,76 mm. Assez
    petit pour n'avoir jamais été remarqué — et c'est précisément contre
    ce placement que les cinq boîtes ont été calibrées : le BAS de la
    boîte est la ligne d'écriture imprimée sur le fond.

    Le placement est donc conservé tel quel, et écrit ici sans détour
    plutôt que par une expression qui prétend corriger quelque chose. La
    correction optique n'a pas disparu par négligence : elle n'a jamais
    été appliquée, et le calibrage a été fait sans elle. Y revenir
    déplacerait cinq champs déjà justes.
    """
    size = field.font_size
    max_width = field.box.width_mm * mm
    tient = False
    while size >= field.min_font_size:
        if _advance(text, field.font_family, size) <= max_width:
            tient = True
            break
        if not field.shrink_to_fit:
            break
        size -= 0.5

    if not tient:
        if not field.truncate:
            raise RenderError(
                f"« {text} » ne tient pas dans la zone « {field.label} » "
                f"({field.box.width_mm} mm), même à {field.min_font_size} pt. "
                f"Le document n'est pas produit : un nom tronqué sur un "
                f"document officiel est une erreur qui circule sans se voir."
            )
        size = field.min_font_size
        while text and _advance(
                text + "…", field.font_family, size) > max_width:
            text = text[:-1]
        text += "…"

    if field.vertical_align == "top":
        baseline_y_mm = field.box.y_mm
    elif field.vertical_align == "bottom":
        baseline_y_mm = field.box.y_mm + field.box.height_mm
    else:
        baseline_y_mm = field.box.y_mm + field.box.height_mm / 2

    return [text], size, size, baseline_y_mm


def _draw_text(pdf, layout, field, value):
    text = "" if value is None else str(value).strip()
    if not text:
        if field.required:
            raise RenderError(
                f"Le champ « {field.label} » est obligatoire et n'a pas de "
                f"valeur : le document sortirait avec un blanc à la place."
            )
        return

    lignes, size, interligne_pt, baseline_y_mm = plan_text(field, text)

    if field.align == "center":
        x_mm = field.box.x_mm + field.box.width_mm / 2
    elif field.align == "right":
        x_mm = field.box.x_mm + field.box.width_mm
    else:
        x_mm = field.box.x_mm

    pdf.setFont(field.font_family, size)
    pdf.setFillColor(HexColor(field.color))

    # La DERNIÈRE ligne se pose sur la ligne de base calculée ; les
    # précédentes montent au-dessus. L'inverse ferait flotter un nom long
    # au-dessus de la règle d'écriture et poserait un nom court dessus.
    interligne_mm = interligne_pt / mm
    depart_mm = baseline_y_mm - interligne_mm * (len(lignes) - 1)

    for index, ligne in enumerate(lignes):
        x_pt, y_pt = layout.to_pdf(x_mm, depart_mm + interligne_mm * index)
        if field.align == "center":
            pdf.drawCentredString(x_pt, y_pt, ligne)
        elif field.align == "right":
            pdf.drawRightString(x_pt, y_pt, ligne)
        else:
            pdf.drawString(x_pt, y_pt, ligne)


def _draw_asset(pdf, layout, asset, branding=None):
    """
    Appose une image officielle, si et seulement si elle existe.

    Rien n'est dessiné à la place d'une ressource absente. Une signature
    approchée ou un cachet ressemblant ne sont pas des solutions de repli :
    ce sont des faux.
    """
    path = resolve_resource(asset.resource, branding)
    if path is None:
        if asset.required:
            raise RenderError(
                f"L'élément officiel « {asset.label} » est déclaré "
                f"obligatoire mais absent des ressources du projet. Il n'est "
                f"pas remplacé : un cachet inventé ferait de ce document un faux."
            )
        return False

    box = asset.box

    # Certains sceaux officiels sont un tracé foncé sur fond blanc : posés
    # tels quels sur un médaillon marine, ils seraient illisibles. Le
    # gabarit peut donc déclarer un disque clair, dessiné À L'INTÉRIEUR du
    # médaillon — la couronne dorée et les rubans du fond restent intacts.
    backdrop = getattr(asset, "backdrop", None)
    if backdrop:
        from reportlab.lib.colors import HexColor as _Hex

        diameter = float(getattr(asset, "backdrop_diameter_mm", 0)
                         or max(box.width_mm, box.height_mm))
        cx_mm = box.x_mm + box.width_mm / 2
        cy_mm = box.y_mm + box.height_mm / 2
        cx_pt, cy_pt = layout.to_pdf(cx_mm, cy_mm)
        pdf.saveState()
        pdf.setFillColor(_Hex(backdrop))
        pdf.setStrokeColor(_Hex(backdrop))
        pdf.circle(cx_pt, cy_pt, diameter * mm / 2, stroke=0, fill=1)
        pdf.restoreState()

    x_pt, y_pt = layout.to_pdf(box.x_mm, box.y_mm + box.height_mm)
    pdf.drawImage(
        path, x_pt, y_pt, width=box.width_mm * mm, height=box.height_mm * mm,
        mask="auto", preserveAspectRatio=(asset.fit == "contain"), anchor="c",
    )
    return True


def _draw_watermark(pdf, layout, text):
    """Filigrane d'un aperçu — il doit être impossible à confondre."""
    pdf.saveState()
    pdf.setFont("Helvetica-Bold", 46)
    pdf.setFillColorRGB(0.85, 0.10, 0.10, alpha=0.28)
    pdf.translate(layout.page_width_mm * mm / 2, layout.page_height_mm * mm / 2)
    pdf.rotate(28)
    pdf.drawCentredString(0, 0, text)
    pdf.setFont("Helvetica-Bold", 13)
    pdf.drawCentredString(0, -22, "APERÇU — NE PAS REMETTRE À UN ÉLÈVE")
    pdf.restoreState()


def render_document(template_id, values, *, branding=None, preview=False,
                    calibration_grid=False):
    """
    Rend un document et renvoie ses octets PDF.

    `branding` porte l'identité de l'académie émettrice : c'est elle qui
    fournit cachet et signature. Sans elle, seuls les outils de calibrage
    rendent un document — jamais une émission.

    `preview=True` autorise le rendu même sans calibrage, en le filigranant.
    `preview=False` refuse tout ce que le gabarit ne permet pas d'émettre —
    c'est le seul mode dont sort un document remis à un élève.
    """
    from io import BytesIO

    template = load_template(template_id)
    ensure_fonts()

    blockers = template.issuance_blockers()
    if blockers and not preview:
        raise RenderError(
            "Ce document ne peut pas être émis :\n  - " + "\n  - ".join(blockers)
        )
    # Sans le fond, il n'y a rien à prévisualiser : produire une page
    # blanche avec un nom dessus donnerait une idée fausse du résultat.
    if not template.background_installed:
        template.verify_background()

    layout = Layout(template)
    buffer = BytesIO()
    pdf = canvas.Canvas(
        buffer,
        pagesize=(template.page_width_mm * mm, template.page_height_mm * mm),
    )
    pdf.setTitle(template.label)

    background_x, background_y = layout.to_pdf(
        layout.offset_x_mm, layout.offset_y_mm + layout.height_mm,
    )
    pdf.drawImage(
        template.render_background_path, background_x, background_y,
        width=layout.width_mm * mm, height=layout.height_mm * mm,
        preserveAspectRatio=True, anchor="c",
    )

    for asset in template.assets:
        _draw_asset(pdf, layout, asset, branding)

    for field in template.fields:
        value = values.get(field.name)
        if field.type == "date" and hasattr(value, "strftime"):
            value = value.strftime(field.date_format)
        _draw_text(pdf, layout, field, value)

    if calibration_grid:
        _draw_calibration_grid(pdf, layout, template)

    if blockers:
        _draw_watermark(pdf, layout, "NON CALIBRÉ")

    pdf.showPage()
    pdf.save()
    return buffer.getvalue()


def _draw_calibration_grid(pdf, layout, template):
    """
    Grille millimétrée et zones du gabarit, superposées au fond.

    C'est l'outil qui rend le calibrage possible : imprimé ou affiché à
    100 %, ce PDF montre exactement où le moteur écrira, et de combien il
    faut corriger. Sans lui, calibrer revient à deviner.
    """
    pdf.saveState()

    # Grille : trait fin tous les 10 mm, plus marqué tous les 50 mm.
    for x in range(0, int(layout.page_width_mm) + 1, 10):
        major = x % 50 == 0
        pdf.setStrokeColorRGB(0, 0, 0.8, alpha=0.35 if major else 0.15)
        pdf.setLineWidth(0.6 if major else 0.25)
        pdf.line(x * mm, 0, x * mm, layout.page_height_mm * mm)
        if major:
            pdf.setFont("Helvetica", 5)
            pdf.setFillColorRGB(0, 0, 0.8, alpha=0.7)
            pdf.drawString(x * mm + 1, layout.page_height_mm * mm - 5, f"{x}")

    for y in range(0, int(layout.page_height_mm) + 1, 10):
        major = y % 50 == 0
        pdf.setStrokeColorRGB(0, 0, 0.8, alpha=0.35 if major else 0.15)
        pdf.setLineWidth(0.6 if major else 0.25)
        y_pt = (layout.page_height_mm - y) * mm
        pdf.line(0, y_pt, layout.page_width_mm * mm, y_pt)
        if major:
            pdf.setFont("Helvetica", 5)
            pdf.setFillColorRGB(0, 0, 0.8, alpha=0.7)
            pdf.drawString(1, y_pt + 1, f"{y}")

    # Zones déclarées : un rectangle par champ, nommé.
    for item in list(template.fields) + list(template.assets):
        box = item.box
        x_pt, y_pt = layout.to_pdf(box.x_mm, box.y_mm + box.height_mm)
        pdf.setStrokeColorRGB(0.85, 0.1, 0.1, alpha=0.8)
        pdf.setLineWidth(0.4)
        pdf.rect(x_pt, y_pt, box.width_mm * mm, box.height_mm * mm, stroke=1, fill=0)
        pdf.setFont("Helvetica", 5)
        pdf.setFillColorRGB(0.85, 0.1, 0.1, alpha=0.9)
        pdf.drawString(x_pt + 0.5, y_pt + box.height_mm * mm + 1, item.name)

    pdf.restoreState()
