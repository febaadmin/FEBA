"""
P2 — La fiche PDF institutionnelle d'une demande de préinscription FEBA.

CE QUE CE FICHIER N'ÉCRIT PAS
-----------------------------
Aucun nom d'école, aucune couleur, aucune adresse, aucun logo n'est codé
ici. Tout vient de `get_branding(demande.entity)`. C'est la règle qui
empêche une fiche FEBA de sortir un jour à l'identité de FEBA French
Heritage Academy — et l'inverse. Une fiche de préinscription pour l'école
de Cotonou ne doit JAMAIS porter l'identité de l'académie en ligne : ce
sont deux établissements, deux directions, deux pays.

La mise en page délègue à `apps.core.pdf_longtext` : un message de
5 000 caractères, une adresse sur six lignes ou un mot de 300 caractères
s'impriment intégralement, sur autant de pages qu'il faut.
"""
import hashlib
import logging
import os
from io import BytesIO

from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.platypus import (
    HRFlowable, Image, SimpleDocTemplate, Spacer, TableStyle,
)

from apps.core.pdf_longtext import keep_with_next, long_text_table, pdf_paragraph
from apps.schools.branding import get_branding

logger = logging.getLogger("apps")

#: Marqueur d'absence de réponse. Une cellule vide se confond avec une
#: rubrique qu'on aurait oublié d'imprimer ; le tiret dit « la question a
#: été posée, la famille n'a pas répondu ».
EMPTY = "—"


def _date(value, fmt="%d/%m/%Y"):
    return value.strftime(fmt) if value else ""


def build_sections(demande):
    """
    Les rubriques de la fiche, dans l'ordre où le secrétariat les lit.

    Renvoie une liste de `(titre, [(libellé, valeur), …])`. Séparer la
    composition du contenu de sa mise en page permet de vérifier par un
    test que CHAQUE champ du modèle atteint bien la fiche — c'est ce qui
    manquait, et c'est ainsi que des champs collectés depuis des mois
    n'apparaissaient nulle part.
    """
    return [
        ("1. Dossier", [
            ("Numéro de dossier", demande.reference),
            ("Reçue le", _date(demande.created_at, "%d/%m/%Y à %H:%M")),
            ("Statut", demande.get_status_display()),
            ("Année scolaire souhaitée", demande.school_year),
        ]),
        ("2. Enfant", [
            ("Nom et prénoms", demande.child_name),
            ("Date de naissance", _date(demande.child_birth_date)),
            ("Âge déclaré", f"{demande.child_age} ans" if demande.child_age else ""),
            ("Niveau demandé", demande.get_desired_level_display()),
        ]),
        ("3. Parent ou tuteur", [
            ("Nom et prénoms", demande.parent_name),
            ("Téléphone principal", demande.phone),
            ("Téléphone secondaire", demande.phone_secondary),
            ("WhatsApp", demande.whatsapp),
            ("Adresse électronique", demande.email),
        ]),
        ("4. Domicile", [
            ("Adresse", demande.address),
        ]),
        ("5. Message de la famille", [
            ("Message", demande.message),
        ]),
    ]


def generate_prereg_sheet(demande):
    """
    Produit la fiche et renvoie ses octets. Ne range rien : l'appelant
    décide où le fichier va, ce qui permet de régénérer une fiche sans
    toucher au fichier déjà remis à la famille.
    """
    brand = get_branding(demande.entity)

    primary = colors.HexColor(brand.primary_color)
    secondary = colors.HexColor(brand.secondary_color)
    accent = colors.HexColor(brand.accent_color)
    light = colors.HexColor(brand.background_color)

    buffer = BytesIO()
    document = SimpleDocTemplate(
        buffer, pagesize=A4,
        leftMargin=1.6 * cm, rightMargin=1.6 * cm,
        topMargin=1.2 * cm, bottomMargin=1.4 * cm,
        title=f"Fiche de préinscription {demande.reference}",
        author=brand.display_name,
    )
    story = []

    # ── En-tête institutionnel ───────────────────────────────────────
    if brand.document_logo and os.path.exists(brand.document_logo):
        try:
            logo = Image(brand.document_logo, width=2.2 * cm, height=2.2 * cm)
            logo.hAlign = "CENTER"
            story.append(logo)
            story.append(Spacer(1, 0.15 * cm))
        except Exception as exc:
            # Un logo illisible ne doit pas empêcher la fiche d'exister :
            # le dossier de la famille passe avant l'ornement.
            logger.warning("Logo non apposé sur la fiche %s : %s",
                           demande.reference, exc)

    if brand.group_name:
        story.append(pdf_paragraph(brand.group_name, fontSize=9,
                                   fontName="Helvetica-Bold", alignment=1,
                                   textColor=accent, spaceAfter=1))
    story.append(pdf_paragraph(brand.display_name, fontSize=15,
                               fontName="Helvetica-Bold", alignment=1,
                               textColor=primary, spaceAfter=2))
    if brand.address_line:
        story.append(pdf_paragraph(brand.address_line, fontSize=8, alignment=1,
                                   textColor=colors.grey, spaceAfter=4))
    story.append(HRFlowable(width="100%", thickness=2.5, color=accent))
    story.append(pdf_paragraph("FICHE DE PRÉINSCRIPTION", fontSize=13,
                               fontName="Helvetica-Bold", alignment=1,
                               textColor=primary, spaceBefore=6, spaceAfter=2))
    story.append(pdf_paragraph(f"Dossier {demande.reference}", fontSize=11,
                               fontName="Helvetica-Bold", alignment=1,
                               textColor=secondary, spaceAfter=8))

    # ── Rubriques ────────────────────────────────────────────────────
    for title, rows in build_sections(demande):
        titre = pdf_paragraph(title.upper(), fontSize=9.5,
                              fontName="Helvetica-Bold",
                              textColor=primary, spaceAfter=3)
        data = [
            [pdf_paragraph(label, fontSize=8.5, fontName="Helvetica-Bold",
                           textColor=colors.HexColor("#475569")),
             pdf_paragraph(value if value not in (None, "", []) else EMPTY,
                           fontSize=8.5)]
            for label, value in rows
        ]
        table = long_text_table(data, colWidths=[6.2 * cm, 11.6 * cm])
        table.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.white, light]),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#E2E8F0")),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        story.extend(keep_with_next(titre, [table]))
        story.append(Spacer(1, 0.28 * cm))

    # ── Pied institutionnel ──────────────────────────────────────────
    story.append(Spacer(1, 0.2 * cm))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.lightgrey))
    footer = (
        f"Document interne — données personnelles d'un mineur. "
        f"Produit le {timezone.now():%d/%m/%Y à %H:%M} · Dossier "
        f"{demande.reference}"
    )
    if brand.footer_text:
        footer += f" · {brand.footer_text}"
    story.append(pdf_paragraph(footer, fontSize=7, alignment=1,
                               textColor=colors.grey))

    document.build(story)
    content = buffer.getvalue()
    buffer.close()
    return content


def sheet_filename(demande):
    return f"{demande.reference}-fiche-preinscription.pdf"


def sheet_sha256(content):
    return hashlib.sha256(content).hexdigest()
