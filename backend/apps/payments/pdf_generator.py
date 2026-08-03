"""
Payment Receipt PDF Generator — v20 FEBA
Corrections:
  - Logo dynamique via SchoolBranding (fix branding 401 résolu)
  - Infos école dynamiques depuis le modèle School
  - Année scolaire incluse dans le reçu
  - Statut paiement clair (confirmé / en attente)
  - Fallback logo statique si aucun logo configuré
"""
import html
import logging
logger = logging.getLogger("apps")
import os
from decimal import Decimal
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

from apps.schools.branding import branding_for


#: Libellés en toutes lettres, par devise. Ils ne sont PAS déduits du
#: symbole : « $ » sert à une dizaine de monnaies, et écrire « DOLLARS »
#: sur un reçu libellé en une autre serait une erreur comptable.
CURRENCY_WORDS = {
    "XOF": {"lang": "fr", "unit": "FRANCS CFA", "sub": ""},
    "USD": {"lang": "en", "unit": "DOLLARS", "sub": "CENTS"},
}


def amount_in_words(amount, currency_code="XOF"):
    """
    Montant en toutes lettres, dans la devise réellement encaissée.

    Le montant en lettres est ce qui fait foi en cas de litige sur un reçu :
    écrire « CENT VINGT-SIX FRANCS CFA » sous un paiement de 125,50 $ n'est
    pas un défaut d'affichage, c'est un faux document. Les décimales sont
    donc énoncées quand la devise en a.
    """
    words = CURRENCY_WORDS.get((currency_code or "").upper())
    if words is None:
        # Devise inconnue : on n'invente pas de libellé. Le code ISO est
        # exact, là où « FRANCS CFA » par défaut serait faux.
        return f"{amount} {(currency_code or '').upper()}".strip()

    # `Decimal(str(...))` et non `int(amount)` : le montant arrive parfois
    # sous forme de chaîne (« 125.50 »), et `int("125.50")` échoue.
    value = Decimal(str(amount))
    whole = int(value)
    cents = int((abs(value) - abs(Decimal(whole))).quantize(Decimal("0.01")) * 100)

    try:
        from num2words import num2words
        text = num2words(whole, lang=words["lang"]).upper()
        if cents and words["sub"]:
            joiner = " ET " if words["lang"] == "fr" else " AND "
            return (f"{text} {words['unit']}{joiner}"
                    f"{num2words(cents, lang=words['lang']).upper()} {words['sub']}")
        return f"{text} {words['unit']}"
    except Exception:
        if cents and words["sub"]:
            return f"{whole} {words['unit']} {cents} {words['sub']}"
        return f"{whole} {words['unit']}"


#: Caractères que les polices Type1 standard de ReportLab (Helvetica &
#: consorts) n'ont pas, et leur équivalent le plus proche qu'elles ont.
#:
#: L'espace fine insécable U+202F est la bonne typographie française pour
#: séparer les milliers — et c'est ce que le formateur de devise produit.
#: Helvetica ne la connaît pas : elle sortait en carré noir, « 35■000 FCFA ».
#: L'espace insécable U+00A0 garde la propriété qui compte (le nombre ne se
#: coupe pas en fin de ligne) et existe, elle, dans la police.
PDF_FONT_SUBSTITUTIONS = {
    "\u202f": "\u00a0",   # espace fine insécable → espace insécable
    "\u2009": "\u00a0",   # espace fine            → espace insécable
    "\u2011": "-",        # trait d'union insécable → trait d'union
}


def _pdf_safe(text):
    """
    Remplace les caractères absents des polices standard du PDF.

    Sans ce passage, un caractère manquant ne provoque aucune erreur : il
    est dessiné en rectangle plein. Le reçu part à l'impression avec un
    montant illisible, et rien ne l'a signalé.
    """
    if text is None:
        return ""
    result = str(text)
    for source, target in PDF_FONT_SUBSTITUTIONS.items():
        result = result.replace(source, target)
    return result


def _para_text(text):
    """Prépare un texte SAISI par un utilisateur pour un Paragraph ReportLab.

    ReportLab interprète les paragraphes comme du mini-XML : une observation
    contenant « & » ou « <trimestre 2> » était soit refusée, soit SILENCIEUSEMENT
    amputée (le fragment entre chevrons disparaissait du reçu). On échappe donc
    le texte, et on convertit les retours à la ligne en <br/> pour préserver la
    mise en forme voulue par le secrétariat.
    """
    if text is None:
        return ""
    escaped = html.escape(_pdf_safe(text), quote=False)
    return escaped.replace("\r\n", "\n").replace("\r", "\n").replace("\n", "<br/>")


def generate_receipt(payment):
    # P0 — TOUTE l'identité vient de l'académie du paiement, par une source
    # unique. Aucun nom, logo, couleur, adresse ni cachet n'est écrit ici :
    # un reçu de FEBA French Heritage Academy portait l'en-tête, la ville et
    # les couleurs de l'école de Cotonou dès que l'un de ces éléments était
    # codé en dur.
    brand = branding_for(payment)
    logo_path = brand.document_logo
    school_name = brand.display_name
    school_address = brand.address_line

    primary = colors.HexColor(brand.primary_color)
    gold    = colors.HexColor(brand.accent_color)
    green   = colors.HexColor("#10B981")   # sémantique (validé), pas identitaire
    light   = colors.HexColor(brand.background_color)

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
        return Paragraph(_para_text(text), ParagraphStyle("_", **kw))

    # Logo
    if logo_path and os.path.exists(logo_path):
        try:
            img = Image(logo_path, width=2.5*cm, height=2.5*cm)
            img.hAlign = "CENTER"
            story.append(img)
            story.append(Spacer(1, 0.2*cm))
        except Exception as exc:
            logger.warning("Erreur non bloquante ignorée : %s", exc, exc_info=True)
    # V7 : ligne « groupe » au-dessus du nom officiel. P0 — le libellé
    # vient de l'identité de l'académie ; vide, la ligne disparaît au lieu
    # d'afficher le groupe d'une autre académie.
    if brand.group_name:
        story.append(P(brand.group_name, fontSize=10, fontName="Helvetica-Bold",
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
        # V8 — Le montant est rendu par la devise de l'académie. L'ancien
        # « f"{payment.amount:,.0f} FCFA" » écrivait « 126 FCFA » sur un reçu
        # de 125,50 $ : mauvaise monnaie ET décimales perdues.
        ["Montant (chiffres) / Amount:", _pdf_safe(payment.formatted_amount)],
        ["Montant (lettres) / In Words:",
         P(amount_in_words(payment.amount, payment.currency),
           fontSize=9, leading=11, wordWrap="CJK")],
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
    if brand.secretary_stamp:
        try:
            stamp = Image(brand.secretary_stamp, width=3.0*cm, height=3.0*cm)  # ratio 1:1 préservé
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
         # V8 — La ville vient de l'académie : « Cotonou » codé en dur
         # apparaissait sur les reçus de FEBA French Heritage Academy, qui
         # n'a pas de campus à Cotonou. P0 — plus aucun repli textuel : une
         # académie sans ville affiche la date seule.
         [P((f"{brand.location_line}, le " if brand.location_line else "Le ")
            + timezone.now().strftime('%d/%m/%Y'),
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
    footer = (f"Généré le {timezone.now().strftime('%d/%m/%Y à %H:%M')} | "
              f"Réf: {payment.reference_number}")
    if brand.footer_text:
        footer += f" | {brand.footer_text}"
    story.append(P(footer, fontSize=7, alignment=1,
                   textColor=colors.grey, spaceBefore=3))

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
