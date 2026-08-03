"""
apps/website/fha_pdf.py — Fiche d'inscription FEBA FHA au format PDF.

CE QUE CETTE FICHE DOIT ÊTRE
----------------------------
Le document que l'administration ouvre, imprime et classe. Il porte
l'identité de l'académie destinataire — jamais celle de l'autre — et
reprend TOUT ce que la famille a saisi.

POURQUOI « TOUT » N'EST PAS NÉGOCIABLE
--------------------------------------
Une fiche partielle est pire qu'aucune fiche. Elle a l'air complète : rien
n'y signale qu'un champ manque. Un numéro WhatsApp absent, un besoin
particulier omis, une disponibilité tronquée — et la décision se prend sur
une information incomplète que personne ne sait incomplète.

Un champ vide est donc écrit « — », et non supprimé : l'absence de réponse
est elle-même une information.

L'IDENTITÉ VIENT D'UNE SOURCE UNIQUE
------------------------------------
Aucun nom, logo, couleur, adresse ni devise n'est écrit dans ce fichier :
tout vient de `apps.schools.branding.get_branding(entity)`.
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

from apps.core.pdf_longtext import (
    keep_with_next, long_text_table, pdf_paragraph,
)
from apps.schools.branding import get_branding

logger = logging.getLogger("apps")

#: Caractères absents des polices Type1 standard de ReportLab. Sans cette
#: substitution, ils sortent en rectangle plein — la fiche part à
#: l'impression avec un numéro illisible et rien ne l'a signalé.
PDF_SUBSTITUTIONS = {
    " ": " ",
    " ": " ",
    "‑": "-",
}

EMPTY = "—"


def _safe(value):
    if value is None:
        return ""
    text = str(value)
    for source, target in PDF_SUBSTITUTIONS.items():
        text = text.replace(source, target)
    return text


def _para(text, **kwargs):
    """
    Paragraphe ReportLab à partir d'un texte SAISI PAR UN UTILISATEUR.

    P0 — Délégué au module partagé `apps.core.pdf_longtext` : l'échappement
    XML, la coupure des mots trop longs et le plancher de lisibilité sont
    désormais les mêmes pour la fiche FHA, la fiche de préinscription FEBA
    et le rapport mensuel. Une règle appliquée dans un seul fichier n'est
    pas une règle, c'est une habitude que le fichier suivant ignorera.
    """
    return pdf_paragraph(_safe(text), **kwargs)


def _yes_no(value, language="fr"):
    if value is None:
        return EMPTY
    if language == "en":
        return "Yes" if value else "No"
    return "Oui" if value else "Non"


def _joined(values, labels=None):
    """Liste de codes → libellés lisibles, séparés par des virgules."""
    if not values:
        return EMPTY
    mapping = dict(labels or [])
    return ", ".join(mapping.get(v, str(v)) for v in values)


def _days(values):
    names = {1: "Lundi", 2: "Mardi", 3: "Mercredi", 4: "Jeudi",
             5: "Vendredi", 6: "Samedi", 7: "Dimanche"}
    if not values:
        return EMPTY
    return ", ".join(names.get(d, str(d)) for d in values)


def _slots(values):
    if not values:
        return EMPTY
    return ", ".join(
        f"{slot.get('start', '?')}–{slot.get('end', '?')}"
        for slot in values if isinstance(slot, dict)
    )


def build_sections(application):
    """
    Les dix-huit blocs de la fiche, dans l'ordre du cahier de structure.

    Renvoyés séparément du rendu pour être vérifiables par un test : c'est
    cette liste qui garantit qu'aucune section n'a été oubliée, et le test
    de complétude la compare aux champs du modèle.
    """
    a = application
    levels = dict(a.FRENCH_LEVEL_CHOICES)
    goals = dict(a.PARENT_GOAL_CHOICES)

    return [
        ("1. Dossier", [
            ("Numéro de dossier", a.reference),
            ("État du dossier", a.get_status_display()),
            ("Reçue le", timezone.localtime(a.created_at).strftime("%d/%m/%Y à %H:%M")),
            ("Dernière mise à jour",
             timezone.localtime(a.updated_at).strftime("%d/%m/%Y à %H:%M")),
        ]),
        ("2. Enfant", [
            ("Nom", a.child_last_name),
            ("Prénom", a.child_first_name),
            ("Date de naissance",
             a.child_birth_date.strftime("%d/%m/%Y") if a.child_birth_date else EMPTY),
            ("Âge", f"{a.child_age} ans" if a.child_age is not None else EMPTY),
            ("Ville", a.child_city),
            ("État / Province", a.child_state_province),
            ("Pays", a.child_country),
        ]),
        ("3. Scolarité actuelle", [
            ("École actuelle", a.child_current_school),
            ("Niveau / Grade", a.child_grade),
            ("Photo fournie", _yes_no(bool(a.child_photo))),
        ]),
        ("4. Origines et langues", [
            ("Pays d'origine de la famille", a.family_origin_country),
            ("Langue principale à la maison", a.home_main_language),
            ("Autres langues parlées", a.other_languages),
            ("Personnes parlant français avec l'enfant", a.french_speakers_with_child),
            ("Lien avec ces personnes", a.french_speakers_relation),
        ]),
        ("5. Niveau de français", [
            ("Niveaux déclarés", _joined(a.french_levels, levels.items())),
            ("Précisions", a.french_level_notes),
        ]),
        ("6. Expérience antérieure", [
            ("Cours de français déjà suivis", _yes_no(a.previous_courses)),
            ("École bilingue", _yes_no(a.bilingual_school)),
            ("Séjour en pays francophone", _yes_no(a.stay_in_francophone_country)),
            ("Certifications obtenues", a.certifications_obtained),
            ("Durée de l'expérience", a.experience_duration),
            ("Commentaires", a.experience_comments),
        ]),
        ("7. Objectifs des parents", [
            ("Objectifs", _joined(a.parent_goals, goals.items())),
            ("Autre objectif", a.parent_goals_other),
        ]),
        ("8. Responsable 1", [
            ("Nom", a.parent1_last_name),
            ("Prénom", a.parent1_first_name),
            ("Lien avec l'enfant", a.parent1_relation),
            ("Téléphone", a.parent1_phone),
            ("WhatsApp", a.parent1_whatsapp),
            ("E-mail", a.parent1_email),
            ("Langue préférée", a.get_parent1_preferred_language_display()),
            ("Fuseau horaire", a.parent1_timezone),
        ]),
        ("9. Adresse du responsable 1", [
            ("Adresse", a.parent1_address),
            ("Ville", a.parent1_city),
            ("État / Province", a.parent1_state_province),
            ("Code postal", a.parent1_postal_code),
            ("Pays", a.parent1_country),
        ]),
        ("10. Responsable 2", [
            ("Nom", a.parent2_last_name),
            ("Prénom", a.parent2_first_name),
            ("Lien avec l'enfant", a.parent2_relation),
            ("Téléphone", a.parent2_phone),
            ("WhatsApp", a.parent2_whatsapp),
            ("E-mail", a.parent2_email),
            ("Langue préférée", a.get_parent2_preferred_language_display() or EMPTY),
            ("Fuseau horaire", a.parent2_timezone),
        ]),
        ("11. Adresse du responsable 2", [
            ("Adresse", a.parent2_address),
            ("Ville", a.parent2_city),
            ("État / Province", a.parent2_state_province),
            ("Code postal", a.parent2_postal_code),
            ("Pays", a.parent2_country),
        ]),
        ("12. Contact d'urgence", [
            ("Nom", a.emergency_name),
            ("Lien avec l'enfant", a.emergency_relation),
            ("Téléphone", a.emergency_phone),
            ("E-mail", a.emergency_email),
            ("Autorisé à être contacté", _yes_no(a.emergency_contact_authorized)),
        ]),
        ("13. Disponibilités", [
            ("Jours disponibles", _days(a.available_days)),
            ("Créneaux horaires", _slots(a.available_time_slots)),
            ("Fuseau horaire de la famille", a.family_timezone),
            ("Semaine / week-end", a.get_weekday_or_weekend_display() or EMPTY),
            ("Précisions", a.availability_notes),
        ]),
        ("14. Équipement", [
            ("Ordinateur", _yes_no(a.has_computer)),
            ("Tablette", _yes_no(a.has_tablet)),
            ("Caméra", _yes_no(a.has_camera)),
            ("Micro", _yes_no(a.has_microphone)),
            ("Casque", _yes_no(a.has_headset)),
            ("Connexion Internet", _yes_no(a.has_internet)),
            ("Peut imprimer", _yes_no(a.can_print)),
            ("Précisions", a.equipment_notes),
        ]),
        ("15. Besoins particuliers (confidentiel)", [
            ("Adaptations, difficultés, soutien", a.special_needs),
        ]),
        ("16. Consentements", [
            ("Règlement intérieur", _yes_no(a.consent_rules)),
            ("Visioconférence", _yes_no(a.consent_zoom)),
            ("Politique de confidentialité", _yes_no(a.consent_privacy)),
            ("Traitement des données", _yes_no(a.consent_data_processing)),
            ("Photos et vidéos", _yes_no(a.consent_photo_video)),
            ("Communications", _yes_no(a.consent_communications)),
            ("Politique de paiement", _yes_no(a.consent_payment_policy)),
            ("Engagement annuel", _yes_no(a.consent_annual_commitment)),
            ("Autorisation parentale", _yes_no(a.consent_parental_authorization)),
        ]),
        ("17. Traçabilité des consentements", [
            ("Version des textes acceptés", a.consents_version),
            ("Acceptés le",
             timezone.localtime(a.consents_accepted_at).strftime("%d/%m/%Y à %H:%M")
             if a.consents_accepted_at else EMPTY),
        ]),
        ("18. Orientation", [
            ("Groupe suggéré par l'âge",
             dict(a.GROUP_CHOICES).get(a.suggested_group, EMPTY)),
            ("Groupe recommandé après test",
             a.get_recommended_group_display() or EMPTY),
        ]),
    ]


def generate_enrollment_sheet(application):
    """
    Produit la fiche PDF et renvoie ses octets.

    Ne stocke rien : l'appelant décide où le fichier va. Séparer la
    production du rangement permet de régénérer une fiche sans toucher au
    fichier déjà remis.
    """
    brand = get_branding(application.entity)

    primary = colors.HexColor(brand.primary_color)
    secondary = colors.HexColor(brand.secondary_color)
    accent = colors.HexColor(brand.accent_color)
    light = colors.HexColor(brand.background_color)

    buffer = BytesIO()
    document = SimpleDocTemplate(
        buffer, pagesize=A4,
        leftMargin=1.6 * cm, rightMargin=1.6 * cm,
        topMargin=1.2 * cm, bottomMargin=1.4 * cm,
        title=f"Fiche d'inscription {application.reference}",
        author=brand.display_name,
    )
    story = []

    # ── En-tête ──────────────────────────────────────────────────────
    if brand.document_logo and os.path.exists(brand.document_logo):
        try:
            logo = Image(brand.document_logo, width=2.2 * cm, height=2.2 * cm)
            logo.hAlign = "CENTER"
            story.append(logo)
            story.append(Spacer(1, 0.15 * cm))
        except Exception as exc:
            logger.warning("Logo non apposé sur la fiche %s : %s",
                           application.reference, exc)

    if brand.group_name:
        story.append(_para(brand.group_name, fontSize=9,
                           fontName="Helvetica-Bold", alignment=1,
                           textColor=accent, spaceAfter=1))
    story.append(_para(brand.display_name, fontSize=15,
                       fontName="Helvetica-Bold", alignment=1,
                       textColor=primary, spaceAfter=2))
    if brand.address_line:
        story.append(_para(brand.address_line, fontSize=8, alignment=1,
                           textColor=colors.grey, spaceAfter=4))
    story.append(HRFlowable(width="100%", thickness=2.5, color=accent))
    story.append(_para("FICHE D'INSCRIPTION / ENROLLMENT FORM", fontSize=13,
                       fontName="Helvetica-Bold", alignment=1,
                       textColor=primary, spaceBefore=6, spaceAfter=2))
    story.append(_para(f"Dossier {application.reference}", fontSize=11,
                       fontName="Helvetica-Bold", alignment=1,
                       textColor=secondary, spaceAfter=8))

    # ── Sections ─────────────────────────────────────────────────────
    for title, rows in build_sections(application):
        block = [
            _para(title.upper(), fontSize=9.5, fontName="Helvetica-Bold",
                  textColor=primary, spaceAfter=3),
        ]
        data = [
            [_para(label, fontSize=8.5, fontName="Helvetica-Bold",
                   textColor=colors.HexColor("#475569")),
             # Un champ vide devient « — » : l'absence de réponse est
             # elle-même une information, et une cellule vide se confond
             # avec une section qu'on aurait oublié d'imprimer.
             _para(value if (value not in (None, "", [])) else EMPTY, fontSize=8.5)]
            for label, value in rows
        ]
        # P0 — `splitInRow` : une réponse de dix pages s'étale sur dix
        # pages. Sans lui, ReportLab lève LayoutError et AUCUNE fiche
        # n'est produite (reproduit avec un message de 5 000 caractères).
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
        # P0 — On ne rend PAS la section insécable : une section de dix
        # pages enfermée dans un KeepTogether reproduit exactement l'échec
        # qu'on vient de corriger. On garantit seulement qu'un titre ne
        # reste jamais seul en bas de page.
        story.extend(keep_with_next(block[0], [table]))
        story.append(Spacer(1, 0.28 * cm))

    # ── Pied ─────────────────────────────────────────────────────────
    story.append(Spacer(1, 0.2 * cm))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.lightgrey))
    footer = (
        f"Document interne — données personnelles d'un mineur. "
        f"Produit le {timezone.now():%d/%m/%Y à %H:%M} · Dossier "
        f"{application.reference}"
    )
    if brand.footer_text:
        footer += f" · {brand.footer_text}"
    story.append(_para(footer, fontSize=7, alignment=1, textColor=colors.grey))

    document.build(story)
    content = buffer.getvalue()
    buffer.close()
    return content


def sheet_filename(application):
    """
    Nom de fichier STABLE : « FHA-2026-0002-fiche-inscription.pdf ».

    Stable et déductible du numéro de dossier : une pièce jointe qu'on
    retrouve six mois plus tard dans un dossier de messagerie, sans avoir à
    l'ouvrir pour savoir ce qu'elle est.
    """
    reference = (application.reference or "sans-reference").replace("/", "-")
    return f"{reference}-fiche-inscription.pdf"
