"""
P3 — Le rapport mensuel en PDF, à l'identité FEBA French Heritage Academy.

Aucun nom, aucune couleur, aucune adresse, aucun logo n'est écrit ici :
tout vient de `get_branding(report.academy)`. C'est la règle qui empêche
un rapport de l'académie en ligne de sortir à l'effigie de l'école de
Cotonou — deux établissements, deux directions, deux pays.

La mise en page passe par `apps.core.pdf_longtext` : un commentaire
d'enseignant de plusieurs milliers de caractères, un nom très long ou une
URL s'impriment intégralement, sur autant de pages qu'il faut, sans que
la génération échoue.
"""
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

from .aggregation import EMPTY_SECTION, NOT_WRITTEN

logger = logging.getLogger("apps")


def _rows_for_section(key, section):
    """
    Traduit une rubrique agrégée en lignes « libellé / valeur ».

    Une rubrique vide donne UNE ligne portant la phrase d'absence. Elle
    n'est jamais escamotée : une rubrique qui disparaît du sommaire fait
    croire qu'elle n'existe pas, alors qu'elle existe et n'a rien reçu.
    """
    if not section.get("has_data"):
        return [("État", EMPTY_SECTION)]

    if key == "attendance":
        rows = [
            ("Jours relevés", section["total_days"]),
            ("Présences", section["present"]),
            ("Absences", section["absent"]),
            ("Retards", section["late"]),
            ("Absences excusées", section["excused"]),
            ("Taux de présence", f"{section['presence_rate']} %"),
        ]
        for justification in section.get("justifications", []):
            rows.append((f"Motif du {justification['date']}",
                         justification["motif"]))
        return rows

    if key == "sessions":
        rows = [("Séances suivies", len(section.get("seances", [])))]
        if section.get("total_minutes"):
            rows.append(("Temps cumulé", f"{section['total_minutes']} minutes"))
        for seance in section.get("seances", []):
            rows.append((f"Séance du {seance['date']}",
                         f"{seance['salle']} — {seance['duree_minutes']} min"))
        for creneau in section.get("creneaux", []):
            rows.append(("Créneau hebdomadaire",
                         f"{creneau['jour']} {creneau['heure_utc']} UTC — "
                         f"{creneau['matiere']}"))
        return rows

    if key == "homework":
        rows = [("Devoirs sur la période", section["total"])]
        for devoir in section.get("devoirs", []):
            rows.append((f"{devoir['matiere']} — {devoir['echeance']}",
                         f"{devoir['titre']}\n{devoir['consigne']}"))
        return rows

    if key == "grades":
        rows = []
        if section.get("moyenne_sur_20") is not None:
            rows.append(("Moyenne pondérée", f"{section['moyenne_sur_20']} / 20"))
        for note in section.get("notes", []):
            valeur = ("non notée" if note["valeur"] is None
                      else f"{note['valeur']} / {note['bareme']}")
            rows.append((f"{note['matiere']} — {note['type']}",
                         f"{valeur} (coefficient {note['coefficient']})"))
            if note["commentaire"]:
                rows.append(("Appréciation", note["commentaire"]))
        return rows

    return [("État", EMPTY_SECTION)]


def build_sections(report):
    """
    Le rapport tel qu'il se lit, rubrique par rubrique.

    Séparé de la mise en page : un test peut vérifier que CHAQUE rubrique
    atteint le document, sans rasteriser un PDF.
    """
    data = report.generated_data or {}
    sections = []

    eleve = data.get("eleve", {})
    sections.append(("1. Élève et période", [
        ("Nom et prénoms", eleve.get("nom", "")),
        ("Matricule", eleve.get("matricule", "")),
        ("Groupe", eleve.get("groupe", "")),
        ("Période couverte", report.period_label()),
        ("Année scolaire", str(report.school_year or "")),
        ("Référence du rapport", report.reference or ""),
        ("Version", str(report.version)),
    ]))

    for index, (key, section) in enumerate(data.get("sections", {}).items(), 2):
        titre = f"{index}. {section.get('title', key)}"
        sections.append((titre, _rows_for_section(key, section)))

    # Ce que l'administration a écrit. Distinct des données agrégées :
    # une régénération ne doit jamais effacer un texte humain.
    #
    # DÉFAUT VU SUR LE DOCUMENT PRODUIT : ces lignes affichaient
    # « Aucune donnée enregistrée pour cette période » quand le champ
    # était vide. C'est faux, et de deux façons. Il n'y a rien à
    # « enregistrer » ici : ce sont des textes que quelqu'un écrit. Et
    # la phrase laissait croire à un défaut de saisie des enseignants
    # alors que c'est l'administration qui n'a pas encore rédigé.
    #
    # Deux absences différentes méritent deux phrases différentes.
    editable = report.editable_content or {}
    sections.append((f"{len(sections) + 1}. Appréciation de l'administration", [
        (label, editable.get(cle) or NOT_WRITTEN)
        for label, cle in (
            ("Synthèse du mois", "summary"),
            ("Progrès observés", "progress"),
            ("Difficultés rencontrées", "difficulties"),
            ("Recommandations", "recommendations"),
            ("Objectifs du mois suivant", "next_goals"),
            ("Message de l'administration", "admin_message"),
        )
    ]))
    return sections


def generate_report_pdf(report):
    """Produit le PDF et renvoie ses octets. Ne range rien."""
    brand = get_branding(report.academy)

    primary = colors.HexColor(brand.primary_color)
    secondary = colors.HexColor(brand.secondary_color)
    accent = colors.HexColor(brand.accent_color)
    light = colors.HexColor(brand.background_color)

    buffer = BytesIO()
    document = SimpleDocTemplate(
        buffer, pagesize=A4,
        leftMargin=1.6 * cm, rightMargin=1.6 * cm,
        topMargin=1.2 * cm, bottomMargin=1.4 * cm,
        title=f"Rapport mensuel {report.reference}",
        author=brand.display_name,
    )
    story = []

    if brand.document_logo and os.path.exists(brand.document_logo):
        try:
            logo = Image(brand.document_logo, width=2.2 * cm, height=2.2 * cm)
            logo.hAlign = "CENTER"
            story.append(logo)
            story.append(Spacer(1, 0.15 * cm))
        except Exception as exc:
            # Un logo illisible ne doit pas empêcher le rapport d'exister.
            logger.warning("Logo non apposé sur le rapport %s : %s",
                           report.reference, exc)

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
    story.append(pdf_paragraph("RAPPORT MENSUEL DE SUIVI", fontSize=13,
                               fontName="Helvetica-Bold", alignment=1,
                               textColor=primary, spaceBefore=6, spaceAfter=2))
    eleve = (report.generated_data or {}).get("eleve", {}).get("nom", "")
    story.append(pdf_paragraph(f"{eleve} — {report.period_label()}", fontSize=11,
                               fontName="Helvetica-Bold", alignment=1,
                               textColor=secondary, spaceAfter=8))

    resume = (report.generated_data or {}).get("resume", {})
    if resume.get("mois_sans_donnee"):
        # Le dire en tête plutôt que de laisser le lecteur parcourir six
        # rubriques vides pour le découvrir.
        story.append(pdf_paragraph(
            "Aucune activité n'a été enregistrée pour cette période. "
            "Ce rapport est émis pour information.",
            fontSize=9, alignment=1, textColor=colors.HexColor("#B45309"),
            spaceAfter=8))

    for title, rows in build_sections(report):
        titre = pdf_paragraph(title.upper(), fontSize=9.5,
                              fontName="Helvetica-Bold",
                              textColor=primary, spaceAfter=3)
        data = [
            [pdf_paragraph(label, fontSize=8.5, fontName="Helvetica-Bold",
                           textColor=colors.HexColor("#475569")),
             pdf_paragraph(value if value not in (None, "", [])
                           else EMPTY_SECTION, fontSize=8.5)]
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

    story.append(Spacer(1, 0.2 * cm))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.lightgrey))
    footer = (
        f"Document confidentiel — suivi scolaire d'un mineur. "
        f"Produit le {timezone.now():%d/%m/%Y à %H:%M} · "
        f"Rapport {report.reference}"
    )
    if brand.footer_text:
        footer += f" · {brand.footer_text}"
    story.append(pdf_paragraph(footer, fontSize=7, alignment=1,
                               textColor=colors.grey))

    document.build(story)
    content = buffer.getvalue()
    buffer.close()
    return content


def report_filename(report):
    return f"{report.reference}-rapport-mensuel.pdf"
