"""
Payment Receipt PDF Generator — v20 FEBA
Corrections:
  - Logo dynamique via SchoolBranding (fix branding 401 résolu)
  - Infos école dynamiques depuis le modèle School
  - Année scolaire incluse dans le reçu
  - Statut paiement clair (confirmé / en attente)
  - Fallback logo statique si aucun logo configuré
"""
import logging
logger = logging.getLogger("apps")
import os
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, Image
)
from reportlab.lib.units import cm
from reportlab.lib import colors
from django.core.files.base import ContentFile
from django.utils import timezone
from feba_project.branding import SCHOOL_GROUP_NAME

# V8 — cachet officiel du SECRÉTARIAT, réservé aux REÇUS.
# (Le cachet « LA DIRECTION » est réservé aux bulletins — ne pas les
# intervertir : ce sont deux autorités distinctes de l'établissement.)
SECRETARIAT_STAMP_PATH = os.path.normpath(os.path.join(
    os.path.dirname(__file__), "..", "..",
    "feba_project", "static_files", "cachet_secretariat.png",
))

STATIC_LOGO_PATH = os.path.join(
    os.path.dirname(__file__), '..', '..', 'feba_project', 'static_files', 'logo_feba.jpeg'
)


def _get_logo_and_school(payment):
    try:
        from apps.schools.models import SchoolBranding, School
        school = None
        if payment.school_year and payment.school_year.school_id:
            school = payment.school_year.school
        if not school:
            school = School.objects.first()
        if school:
            path = SchoolBranding.get_active_logo_path(school)
            if path and os.path.exists(path):
                return path, school
        return None, school
    except Exception as exc:
        logger.warning("Erreur non bloquante ignorée : %s", exc, exc_info=True)
    return None, None


def _school_info(school):
    if not school:
        return "FAITH & EXCELLENCE BILINGUAL ACADEMY", "Cotonou, Bénin"
    name = school.name or "FAITH & EXCELLENCE BILINGUAL ACADEMY"
    parts = []
    if school.address: parts.append(school.address)
    if school.city:    parts.append(school.city)
    if school.country: parts.append(school.country)
    if school.phone:   parts.append(f"Tél: {school.phone}")
    if school.email:   parts.append(school.email)
    return name, " | ".join(parts) if parts else "Cotonou, Bénin"


def amount_in_words(amount):
    try:
        from num2words import num2words
        return num2words(int(amount), lang="fr").upper() + " FRANCS CFA"
    except Exception:
        return f"{int(amount)} FRANCS CFA"


def generate_receipt(payment):
    logo_path, school = _get_logo_and_school(payment)
    school_name, school_address = _school_info(school)
    if not logo_path:
        static = os.path.normpath(STATIC_LOGO_PATH)
        if os.path.exists(static):
            logo_path = static

    primary = colors.HexColor("#1E3A6E")
    gold    = colors.HexColor("#C9A227")
    green   = colors.HexColor("#10B981")
    light   = colors.HexColor("#EEF3FF")

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4,
        rightMargin=2*cm, leftMargin=2*cm, topMargin=1.5*cm, bottomMargin=1.5*cm)
    story = []

    def P(text, **kw):
        # V8 — CORRECTION D'UN CHEVAUCHEMENT : ParagraphStyle utilise par défaut
        # leading=12. Un texte en 16 pt (nom de l'établissement) débordait donc
        # de sa ligne et se superposait à l'adresse juste en dessous. On calcule
        # un interligne proportionnel dès qu'il n'est pas fourni explicitement.
        kw.setdefault("leading", round(kw.get("fontSize", 10) * 1.25, 1))
        return Paragraph(text, ParagraphStyle("_", **kw))

    # Logo
    if logo_path and os.path.exists(logo_path):
        try:
            img = Image(logo_path, width=2.5*cm, height=2.5*cm)
            img.hAlign = "CENTER"
            story.append(img)
            story.append(Spacer(1, 0.2*cm))
        except Exception as exc:
            logger.warning("Erreur non bloquante ignorée : %s", exc, exc_info=True)
    # V7 : ligne « groupe » (GROUPE ÉDUCATIF FEBA) au-dessus du nom officiel.
    story.append(P(SCHOOL_GROUP_NAME, fontSize=10, fontName="Helvetica-Bold",
                   alignment=1, textColor=gold, spaceAfter=1))
    story.append(P(school_name, fontSize=16, fontName="Helvetica-Bold",
                   alignment=1, textColor=primary, spaceAfter=2))
    story.append(P(school_address, fontSize=10, alignment=1,
                   textColor=colors.grey, spaceAfter=4))
    story.append(HRFlowable(width="100%", thickness=3, color=gold))
    story.append(P("REÇU DE PAIEMENT / PAYMENT RECEIPT",
                   fontSize=15, fontName="Helvetica-Bold",
                   alignment=1, textColor=primary, spaceBefore=6, spaceAfter=4))

    # Statut
    confirmed = getattr(payment, 'is_confirmed', True)
    statut_color = green if confirmed else colors.HexColor("#F59E0B")
    statut_text = "✓ PAIEMENT CONFIRMÉ" if confirmed else "⏳ EN ATTENTE DE CONFIRMATION"
    story.append(P(statut_text, fontSize=11, fontName="Helvetica-Bold",
                   alignment=1, textColor=statut_color, spaceAfter=6))

    # Référence
    year_name = payment.school_year.name if payment.school_year else "—"
    ref_tbl = Table([
        ["N° Référence:", payment.reference_number, "Date:", payment.payment_date.strftime("%d/%m/%Y")],
        ["Année scolaire:", year_name, "Généré le:", timezone.now().strftime("%d/%m/%Y %H:%M")],
    ], colWidths=[4*cm, 6*cm, 3*cm, 4*cm])
    ref_tbl.setStyle(TableStyle([
        ("FONTNAME",  (0,0), (-1,-1), "Helvetica"),
        ("FONTNAME",  (0,0), (0,-1), "Helvetica-Bold"),
        ("FONTNAME",  (2,0), (2,-1), "Helvetica-Bold"),
        ("FONTSIZE",  (0,0), (-1,-1), 9),
        ("BACKGROUND",(0,0), (-1,-1), light),
        ("BOX",       (0,0), (-1,-1), 0.5, primary),
        ("INNERGRID", (0,0), (-1,-1), 0.25, colors.grey),
        ("PADDING",   (0,0), (-1,-1), 6),
    ]))
    story.append(ref_tbl)
    story.append(Spacer(1, 0.5*cm))

    # Élève
    story.append(P("INFORMATIONS ÉLÈVE / STUDENT INFORMATION",
                   fontSize=10, fontName="Helvetica-Bold", textColor=primary, spaceAfter=4))
    student = payment.student
    # V8 : valeurs enveloppées dans des Paragraph → repli automatique (les
    # identités très longues étaient tronquées au bord droit du reçu).
    student_data = [
        ["Nom complet / Full Name:", P(student.get_full_name(), fontSize=9, leading=11, wordWrap="CJK")],
        ["Matricule / Student ID:", student.matricule],
        ["Classe / Class:", student.current_class.name if student.current_class else "—"],
        ["Niveau / Level:", (student.current_class.level.name
                             if student.current_class and student.current_class.level else "—")],
    ]
    try:
        link = student.parents.select_related("parent__user").first()
        if link:
            student_data.append(["Parent / Guardian:",
                                 P(link.parent.user.get_full_name(), fontSize=9, leading=11, wordWrap="CJK")])
    except Exception as exc:
        logger.warning("Erreur non bloquante ignorée : %s", exc, exc_info=True)
    st_tbl = Table(student_data, colWidths=[5.5*cm, 11.5*cm])
    st_tbl.setStyle(TableStyle([
        ("FONTNAME",       (0,0), (0,-1), "Helvetica-Bold"),
        ("FONTSIZE",       (0,0), (-1,-1), 9),
        ("ROWBACKGROUNDS", (0,0), (-1,-1), [colors.white, light]),
        ("PADDING",        (0,0), (-1,-1), 5),
        ("GRID",           (0,0), (-1,-1), 0.25, colors.lightgrey),
    ]))
    story.append(st_tbl)
    story.append(Spacer(1, 0.5*cm))

    # Détail paiement
    story.append(P("DÉTAIL DU PAIEMENT / PAYMENT DETAILS",
                   fontSize=10, fontName="Helvetica-Bold", textColor=primary, spaceAfter=4))
    pay_data = [
        ["Type de paiement / Payment Type:", payment.get_payment_type_display()],
        ["Montant (chiffres) / Amount:", f"{payment.amount:,.0f} FCFA"],
        ["Montant (lettres) / In Words:",
         P(amount_in_words(payment.amount), fontSize=9, leading=11, wordWrap="CJK")],
        ["Mode de paiement / Method:", payment.get_payment_method_display()],
        ["Reçu par / Received by:", payment.received_by.get_full_name() if payment.received_by else "—"],
        ["Statut / Status:", "Confirmé ✓" if confirmed else "En attente"],
    ]
    if getattr(payment, 'notes', None):
        # V8 — les observations peuvent être longues : ReportLab ne coupe JAMAIS
        # une simple chaîne, le texte était donc TRONQUÉ au bord droit du reçu.
        # Enveloppé dans un Paragraph, il se replie dans la largeur de colonne.
        pay_data.append([
            "Observations:",
            P(str(payment.notes), fontSize=9, leading=11, wordWrap="CJK"),
        ])

    pay_tbl = Table(pay_data, colWidths=[6*cm, 11*cm])
    pay_tbl.setStyle(TableStyle([
        ("FONTNAME",       (0,0), (0,-1), "Helvetica-Bold"),
        ("FONTSIZE",       (0,0), (-1,-1), 9),
        ("ROWBACKGROUNDS", (0,0), (-1,-1), [colors.white, light]),
        ("PADDING",        (0,0), (-1,-1), 5),
        ("GRID",           (0,0), (-1,-1), 0.25, colors.lightgrey),
        ("TEXTCOLOR",      (1,1), (1,1), green),
        ("FONTNAME",       (1,1), (1,1), "Helvetica-Bold"),
        ("FONTSIZE",       (1,1), (1,1), 12),
    ]))
    story.append(pay_tbl)
    story.append(Spacer(1, 1*cm))

    # ── Zone de validation UNIQUE : « Le Secrétariat » (V8) ─────────────────
    # Les anciennes mentions « Signature du Caissier » et « Cachet de l'École /
    # School Stamp » sont SUPPRIMÉES : le reçu ne comporte plus qu'une seule
    # zone de validation, avec le cachet officiel du SECRÉTARIAT (le cachet de
    # la Direction est réservé aux bulletins).
    story.append(HRFlowable(width="100%", thickness=1, color=colors.lightgrey))
    story.append(Spacer(1, 0.35*cm))

    stamp_cell = ""
    if os.path.exists(SECRETARIAT_STAMP_PATH):
        try:
            stamp = Image(SECRETARIAT_STAMP_PATH, width=3.0*cm, height=3.0*cm)  # ratio 1:1 préservé
            stamp.hAlign = "CENTER"
            stamp_cell = stamp
        except Exception as exc:
            logger.warning("Cachet du secrétariat non apposé (non bloquant) : %s",
                           exc, exc_info=True)

    # Colonne gauche : mention légale ; colonne droite : validation + cachet.
    # Une grille (et non un positionnement absolu) garantit que le bloc reste
    # solidaire même si le contenu au-dessus varie.
    mention = P(
        "Ce reçu atteste du paiement mentionné ci-dessus. "
        "Il est délivré pour servir et valoir ce que de droit.",
        fontSize=8, textColor=colors.grey, leading=11,
    )
    validation_tbl = Table(
        [[P("Le Secrétariat", fontSize=10, fontName="Helvetica-Bold",
            alignment=1, textColor=primary)],
         [stamp_cell],
         [P(f"Cotonou, le {timezone.now().strftime('%d/%m/%Y')}",
            fontSize=8, alignment=1, textColor=colors.grey)]],
        colWidths=[6.2*cm], rowHeights=[0.6*cm, 3.3*cm, 0.6*cm],
    )
    validation_tbl.setStyle(TableStyle([
        ("ALIGN",  (0,0), (-1,-1), "CENTER"),
        ("VALIGN", (0,1), (0,1), "MIDDLE"),
        ("TOPPADDING",    (0,0), (-1,-1), 2),
        ("BOTTOMPADDING", (0,0), (-1,-1), 2),
    ]))

    bottom_tbl = Table([[mention, validation_tbl]], colWidths=[10.6*cm, 6.4*cm])
    bottom_tbl.setStyle(TableStyle([
        ("VALIGN", (0,0), (0,0), "TOP"),
        ("VALIGN", (1,0), (1,0), "TOP"),
        ("LEFTPADDING",  (0,0), (-1,-1), 0),
        ("RIGHTPADDING", (0,0), (-1,-1), 0),
    ]))
    story.append(bottom_tbl)
    story.append(Spacer(1, 0.4*cm))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.lightgrey))
    story.append(P(
        f"Généré le {timezone.now().strftime('%d/%m/%Y à %H:%M')} | "
        f"Réf: {payment.reference_number} | Système FEBA School Management",
        fontSize=7, alignment=1, textColor=colors.grey, spaceBefore=3,
    ))

    doc.build(story)
    pdf_content = buffer.getvalue()
    buffer.close()

    if payment.receipt_file:
        try:
            payment.receipt_file.delete(save=False)
        except Exception as exc:
            logger.warning("Erreur non bloquante ignorée : %s", exc, exc_info=True)
    payment.receipt_file.save(
        f"receipt_{payment.reference_number}.pdf",
        ContentFile(pdf_content),
        save=True,
    )
    return payment
