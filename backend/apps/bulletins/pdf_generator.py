"""
Bulletin PDF generator — refonte BUG N°1 / BUG N°2 / BUG N°6.

Présentation du bulletin (modèle de référence fourni par l'établissement) :
  1. En-tête établissement (logo dynamique : SchoolBranding → School.logo → statique)
  2. Identité de l'élève — SANS le rang (BUG N°2)
  3. RÉSULTATS — PARTIE FRANÇAISE : matières FR, notes, coefficients,
     moyennes, moyennes pondérées, lettres, appréciations
  4. ACADEMIC RESULTS — ENGLISH PART : idem pour les matières EN
  5. Statistiques de classe : moyennes MINIMALES et MAXIMALES de la classe
     (françaises, anglaises, bilingues) calculées dynamiquement à partir
     des résultats réels de tous les élèves de la classe (BUG N°2)
  6. Moyenne bilingue = (Moyenne FR × 60%) + (Moyenne EN × 40%)  (BUG N°6)
  7. Moyenne générale + lettre + appréciation
  8. Signatures (directeur, parent) + pied de page

Template Maternelle conservé (notation en lettres + conduite), sans rang.
"""
import os
import logging
from decimal import Decimal
from io import BytesIO

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable, Image,
    KeepTogether,
)
from django.core.files.base import ContentFile

from apps.schools.branding import branding_for
# V8 — barème d'affichage par niveau (1..11 → /10, au-delà → /20)
from apps.grades.grading import (
    convert_average_for_scale, get_grading_scale, scale_label,
)
from django.utils import timezone

from apps.core.pdf_longtext import pdf_paragraph
from apps.grades.models import Grade, get_letter_grade, get_appreciation
from apps.bulletins.models import Bulletin

logger = logging.getLogger('apps')

# P0 — L'IDENTITÉ N'EST PLUS ÉCRITE ICI.
#
# Le logo, le cachet et les trois couleurs institutionnelles étaient des
# constantes de module : tous les bulletins des deux académies sortaient
# donc avec le bleu, l'or et le cachet de l'école de Cotonou. Elles sont
# désormais résolues par `apps.schools.branding` à partir de l'académie de
# l'élève, et transportées dans un `Palette` le temps du rendu.
#
# Ne restent en dur que les couleurs SÉMANTIQUES, qui ne désignent aucune
# académie : le vert de la partie anglaise distingue une section du
# bulletin, exactement comme le rouge d'un solde négatif.
EN_HEAD = colors.HexColor('#166534')   # vert foncé (partie anglaise)
EN_BG   = colors.HexColor('#F0FFF4')   # vert très clair


class Palette:
    """Couleurs et ressources d'UNE académie, le temps d'un rendu."""

    __slots__ = ('brand', 'primary', 'gold', 'light', 'fr_head')

    def __init__(self, brand):
        self.brand = brand
        self.primary = colors.HexColor(brand.primary_color)
        self.gold = colors.HexColor(brand.accent_color)
        self.light = colors.HexColor(brand.background_color)
        # L'en-tête du tableau français reprend la couleur institutionnelle.
        self.fr_head = self.primary


def _fmt(val):
    if val is None:
        return '—'
    return f'{float(val):.2f}'


def _student_scale(student):
    """Barème d'AFFICHAGE du bulletin, déduit du niveau de l'élève."""
    level = None
    klass = getattr(student, 'current_class', None)
    if klass is not None:
        level = getattr(klass, 'level', None)
    return get_grading_scale(level)


def _fmt_scale(val, scale):
    """Moyenne interne /20 → valeur affichée dans le barème du niveau.

    La conversion n'a lieu QU'ICI (une seule fois) ; les lettres et
    appréciations restent calculées sur l'échelle interne /20.
    """
    if val is None:
        return '—'
    return f'{float(convert_average_for_scale(val, scale)):.2f}'


def _fmt_note(val, scale):
    """Note individuelle (stockée /20) exprimée dans le barème du bulletin.

    Une décimale sur 20 (format historique), deux sur 10 pour ne pas perdre
    de précision en divisant par deux (17,5/20 → 8,75/10).
    """
    if val is None:
        return '—'
    converted = convert_average_for_scale(val, scale)
    digits = 1 if Decimal(str(scale)) == Decimal('20') else 2
    return f'{float(converted):.{digits}f}'


def _fmt_scale_denom(val, scale):
    """Idem avec le dénominateur explicite : « 6.00/10 » ou « 12.00/20 »."""
    if val is None:
        return '—'
    return f'{_fmt_scale(val, scale)}/{int(scale)}'


def _period_label(period):
    labels = {
        'T1': '1ER TRIMESTRE', 'T2': '2ÈME TRIMESTRE',
        'T3': '3ÈME TRIMESTRE', 'annual': 'ANNUEL',
    }
    return labels.get(period, period.upper())


def P(text, **kw):
    return Paragraph(text, ParagraphStyle('_', **kw))


# ─── Cellules de tableau qui RETOURNENT À LA LIGNE (anti-débordement) ─────────
#
# BUG N°1 — Débordement latéral / colonnes coupées.
# Cause racine : les cellules de tableau étaient de simples chaînes. ReportLab
# ne coupe JAMAIS une chaîne : un intitulé long (« Éducation Civique, Morale et
# Instruction à la Citoyenneté Démocratique ») force donc sa colonne à s'élargir
# et déborde sur les colonnes voisines et hors du cadre. En enveloppant le texte
# dans un Paragraph, il se replie proprement dans la largeur de colonne fixée.

_CELL_BASE = dict(fontName='Helvetica', fontSize=8, leading=9.5,
                  wordWrap='CJK')  # 'CJK' coupe même les très longs mots/URL


def C(text, *, align='LEFT', bold=False, size=8, color=None):
    """
    Cellule de tableau à retour à la ligne automatique.

    P0 — BUG N°2, TROUVÉ EN AUDITANT LE RENDU DES TEXTES LONGS.
    Cette fonction reçoit des textes SAISIS PAR UN ENSEIGNANT — nom de
    matière, appréciation, commentaire général du directeur — et les
    passait tels quels à `Paragraph`, qui les lit comme du mini-XML.

    Mesuré sur le bulletin produit : une appréciation « progrès <très
    nets> en lecture » ressortait imprimée « progrès  en lecture ». Le
    fragment entre chevrons — celui qui portait l'appréciation — était
    avalé sans erreur ni avertissement. Le bulletin sortait complet en
    apparence, amputé en réalité, et signé.

    (ReportLab 4.2 tolère en revanche une esperluette isolée : « Bon élève
    & travailleur » passait. C'est précisément ce qui rendait le défaut
    difficile à voir — il ne se manifestait que sur certains caractères.)

    `pdf_paragraph` échappe le texte et convertit les retours à la ligne.
    `P()` reste volontairement non échappée : elle ne sert qu'à des
    libellés fixes écrits dans ce fichier, dont la mise en forme (`<b>`,
    `<font>`) est intentionnelle.
    """
    style = dict(_CELL_BASE)
    style['fontName'] = 'Helvetica-Bold' if bold else 'Helvetica'
    style['fontSize'] = size
    style['leading'] = size + 1.5
    style['alignment'] = {'LEFT': 0, 'CENTER': 1, 'RIGHT': 2}[align]
    if color is not None:
        style['textColor'] = color
    return pdf_paragraph(text, **style)


# ─── Entry Point ──────────────────────────────────────────────────────────────

def generate_bulletin(student, period, school_year):
    """
    Génère (ou régénère) le bulletin PDF d'un élève.
    Template maternelle si le niveau est maternelle, sinon template
    bilingue standard (parties FR et EN séparées).
    """
    logger.info(f"Generating bulletin: {student.matricule} {period} {school_year.name}")

    # Classe de l'élève POUR L'ANNÉE DEMANDÉE (inscription annuelle),
    # repli sur current_class.
    student_class = Grade._class_for_year(student, school_year)
    if not student.current_class and student_class:
        # Utilisé seulement pour cette génération (non sauvegardé)
        student.current_class = student_class

    is_maternelle = bool(
        student_class and student_class.level and student_class.level.is_maternelle()
    )

    # Moyennes de l'élève
    if period == 'annual':
        average = Grade.calculate_annual_average(student, school_year)
        subject_data = _build_annual_subject_data(student, school_year)
        bilingual_data = Grade.get_annual_bilingual(student, school_year)['annual']
    else:
        average = Grade.calculate_average(student, school_year, period)
        subject_data = Grade.get_subject_averages(student, school_year, period)
        bilingual_data = Grade.calculate_bilingual_averages(student, school_year, period)

    # Statistiques de classe : min/max FR, EN, bilingue (BUG N°2) —
    # calculées automatiquement à partir des résultats de tous les élèves.
    class_stats = Grade.get_class_bilingual_stats(student_class, school_year, period)

    # Upsert bulletin
    bulletin, created = Bulletin.objects.get_or_create(
        student=student, school_year=school_year, period=period,
    )
    if not created and bulletin.pdf_file:
        try:
            bulletin.pdf_file.delete(save=False)
        except Exception as exc:
            logger.warning("Erreur non bloquante ignorée : %s", exc, exc_info=True)
    bulletin.average = average
    bulletin.appreciation = get_appreciation(average)
    # BUG N°2 : le rang n'apparaît plus sur le bulletin et n'est plus calculé.
    bulletin.rank_in_class = None

    try:
        # P0 — l'identité vient de l'académie DE L'ÉLÈVE, résolue une fois
        # et transportée jusqu'au dernier trait de couleur du document.
        palette = Palette(branding_for(student))
        buffer = BytesIO()

        if is_maternelle:
            _build_maternelle_pdf(buffer, student, period, school_year,
                                  subject_data, average, bulletin, palette)
        else:
            _build_standard_pdf(buffer, student, period, school_year,
                                subject_data, bilingual_data, class_stats,
                                average, bulletin, palette,
                                expected_languages=_expected_languages(student_class))

        pdf_bytes = buffer.getvalue()
        buffer.close()

        if bulletin.pdf_file:
            try:
                bulletin.pdf_file.delete(save=False)
            except Exception as exc:
                logger.warning("Erreur non bloquante ignorée : %s", exc, exc_info=True)
        filename = f"bulletin_{student.matricule}_{period}_{school_year.name}.pdf"
        bulletin.pdf_file.save(filename, ContentFile(pdf_bytes), save=False)
        bulletin.save()
        logger.info(f"Bulletin saved: {filename} ({len(pdf_bytes)} bytes)")
    except Exception as e:
        logger.error(f"PDF build failed {student.matricule}/{period}: {e}", exc_info=True)
        bulletin.save()
        raise

    return bulletin


# ─── Annual Subject Data ──────────────────────────────────────────────────────

def _build_annual_subject_data(student, school_year):
    """Moyennes annuelles par matière (T1/T2/T3 + moyenne des trimestres notés)."""
    from apps.subjects.models import Subject

    student_class = Grade._class_for_year(student, school_year)
    subjects = []
    # 1. Matières assignées à la classe (source de vérité bilingue)
    if student_class:
        class_subjects = student_class.subjects.all()
        if class_subjects.exists():
            subjects = list(class_subjects)
    # 2. Repli : matières du niveau
    if not subjects and student_class and student_class.level_id:
        subjects = list(Subject.objects.filter(level_id=student_class.level_id))
    # 3. Repli : matières de l'établissement
    if not subjects:
        school_id = None
        if school_year and getattr(school_year, 'school_id', None):
            school_id = school_year.school_id
        elif student.school_id:
            school_id = student.school_id
        if school_id:
            subjects = list(Subject.objects.filter(school_id=school_id))
    # 4. Dernier recours : matières réellement notées
    if not subjects:
        sids = Grade.objects.filter(
            student=student, school_year=school_year, is_deleted=False
        ).values_list('subject_id', flat=True).distinct()
        subjects = list(Subject.objects.filter(id__in=sids))

    result = {}
    for subj in subjects:
        sid = subj.id
        trim_avgs = {}
        valid_avgs = []
        for t in ['T1', 'T2', 'T3']:
            t_data = Grade.get_subject_averages(student, school_year, t)
            t_avg = t_data.get(sid, {}).get('average') if sid in t_data else None
            if t_avg is not None:
                trim_avgs[t] = float(t_avg)
                valid_avgs.append(Decimal(str(t_avg)))
            else:
                trim_avgs[t] = None
        annual_avg = (sum(valid_avgs) / Decimal(len(valid_avgs))) if valid_avgs else None
        letter, meaning, stars = get_letter_grade(annual_avg)
        result[sid] = {
            'subject_id':     sid,
            'subject_name':   subj.name,
            'coefficient':    subj.coefficient,
            'language':       subj.language,
            'average':        round(annual_avg, 2) if annual_avg is not None else None,
            'letter':         letter,
            'meaning':        meaning,
            'trimester_avgs': trim_avgs,
            # FIX BUG N°9 : None > 0 levait TypeError et cassait la
            # génération du bulletin annuel dès qu'un trimestre était vide.
            'has_notes':      any(v is not None for v in trim_avgs.values()),
            'notes':          [],
        }
    return result


# ─── Header / identité élève (partagés) ──────────────────────────────────────

def _add_header(story, student, period, school_year, palette, title):
    brand = palette.brand
    name = brand.display_name
    # P1 — Le bulletin recomposait son en-tête à partir de l'adresse seule.
    # Il sortait donc SANS numéro de téléphone : la pièce qu'un parent a le
    # plus souvent en main pour appeler l'établissement (une note contestée,
    # une appréciation à discuter) était la seule à ne pas porter le
    # numéro. `address_line` est la ligne d'identité commune à tous les
    # documents — même adresse, même numéro institutionnel, même e-mail.
    subtitle = brand.address_line or "—"
    logo_path = brand.document_logo
    if logo_path and os.path.exists(logo_path):
        try:
            logo_img = Image(logo_path, width=2.0 * cm, height=2.0 * cm)
            logo_img.hAlign = 'CENTER'
            story.append(logo_img)
        except Exception as exc:
            logger.warning("Erreur non bloquante ignorée : %s", exc, exc_info=True)
    # V7 : ligne « groupe » au-dessus du nom officiel — libellé administrable
    # par académie ; absente, la ligne disparaît.
    if brand.group_name:
        story.append(P(brand.group_name, fontSize=9, fontName='Helvetica-Bold',
                       alignment=1, textColor=palette.gold, spaceAfter=1))
    story.append(P(name.upper(), fontSize=14, fontName='Helvetica-Bold',
                   alignment=1, textColor=palette.primary, spaceAfter=2))
    story.append(P(subtitle, fontSize=9, alignment=1, spaceAfter=2))
    story.append(HRFlowable(width='100%', thickness=3, color=palette.gold))
    story.append(P(f'{title} — {_period_label(period)}',
                   fontSize=13, fontName='Helvetica-Bold', alignment=1,
                   textColor=palette.gold, spaceBefore=4))
    story.append(P(f'Année scolaire / School Year : {school_year.name}',
                   fontSize=10, alignment=1, spaceAfter=4))
    story.append(Spacer(1, 0.2 * cm))


def _add_student_info(story, student, period, school_year, palette):
    """Bloc identité — SANS le rang (BUG N°2)."""
    class_name = student.current_class.name if student.current_class else '—'
    level_name = (student.current_class.level.name
                  if student.current_class and student.current_class.level else '—')
    def lbl(t):
        return C(t, bold=True, size=8.5)

    def val(t):
        return C(t, size=8.5)

    info = [
        [lbl('Nom / Name:'), val(student.get_full_name()), lbl('Matricule:'), val(student.matricule)],
        [lbl('Classe / Class:'), val(class_name), lbl('Niveau / Level:'), val(level_name)],
        [lbl('Période / Period:'), val(_period_label(period)), lbl('Année / Year:'), val(school_year.name)],
        [lbl('Date de naissance:'), val(str(student.date_of_birth) if student.date_of_birth else '—'),
         lbl('Sexe / Gender:'), val(student.get_gender_display() if student.gender else '—')],
    ]
    info_tbl = Table(info, colWidths=[3.5 * cm, 5.8 * cm, 3.5 * cm, 5.7 * cm])
    info_tbl.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.25, colors.lightgrey),
        ('BACKGROUND', (0, 0), (0, -1), palette.light),
        ('BACKGROUND', (2, 0), (2, -1), palette.light),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 5),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]))
    story.append(info_tbl)
    story.append(Spacer(1, 0.3 * cm))


# ─── Tableaux de résultats FR / EN (BUG N°1) ─────────────────────────────────

def _weighted_section_average(rows):
    """Moyenne pondérée (coefficients matières) d'une liste d'entrées matières."""
    graded = [r for r in rows if r['average'] is not None]
    if not graded:
        return None
    total_w = sum(Decimal(str(r['average'])) * Decimal(r['coefficient']) for r in graded)
    total_c = sum(Decimal(r['coefficient']) for r in graded)
    return round(total_w / total_c, 2) if total_c else None


def _subject_rows_trimester(entries, scale=20):
    """Lignes matières pour une période trimestre : notes détaillées."""
    note_labels = {'devoir': 'D', 'interrogation': 'I', 'controle': 'C',
                   'examen': 'E', 'tp': 'TP', 'autre': 'A'}
    rows = []
    for info in entries:
        notes = info.get('notes') or []
        avg = info['average']
        if notes:
            # V8 : le DÉTAIL des notes suit le barème du bulletin. Sur un
            # bulletin sur 10, imprimer « E:17.5 » à côté de « 8.26/10 » était
            # incompréhensible (et affichait des notes supérieures au barème
            # annoncé). Les notes restent stockées sur 20 ; la conversion a
            # lieu ici seulement, à l'affichage.
            details = '  '.join(
                f"{note_labels.get(n.note_type, 'N')}:{_fmt_note(n.value, scale)}"
                for n in sorted(notes, key=lambda x: x.note_type)
            )
        else:
            details = 'Non noté'
        # V8 : la moyenne pondérée s'exprime dans le MÊME barème que la colonne
        # « Moy. » affichée (sinon on lisait « 6.00/10 » en face de « 48.00 »,
        # calculé sur l'échelle interne /20 — incohérent pour le lecteur).
        weighted = (float(convert_average_for_scale(avg, scale)) * info['coefficient']
                    if avg is not None else None)
        letter, _, _ = get_letter_grade(avg)
        rows.append([
            C(info['subject_name'], bold=True),
            str(info['coefficient']),
            C(details, align='CENTER', size=7.5),
            _fmt_scale_denom(avg, scale),
            f'{weighted:.2f}' if weighted is not None else '—',
            letter or '—',
            C(get_appreciation(avg) if avg is not None else '—', align='CENTER'),
        ])
    return rows


def _subject_rows_annual(entries, scale=20):
    """Lignes matières pour le bulletin annuel : T1 / T2 / T3 / moyenne."""
    rows = []
    for info in entries:
        t_avgs = info.get('trimester_avgs', {})
        avg = info['average']
        letter, _, _ = get_letter_grade(avg)
        rows.append([
            C(info['subject_name'], bold=True),
            str(info['coefficient']),
            _fmt_scale(t_avgs.get('T1'), scale),
            _fmt_scale(t_avgs.get('T2'), scale),
            _fmt_scale(t_avgs.get('T3'), scale),
            _fmt_scale_denom(avg, scale),
            letter or '—',
            C(get_appreciation(avg) if avg is not None else '—', align='CENTER'),
        ])
    return rows


def _add_language_section(story, title, entries, period, head_color, zebra_color, scale=20):
    """
    Une section de résultats par langue (BUG N°1) : tableau des matières
    de cette langue avec notes, coefficients, moyennes et appréciations,
    puis ligne de moyenne de la partie.
    """
    story.append(P(title, fontSize=11, fontName='Helvetica-Bold',
                   textColor=head_color, spaceAfter=4))

    if not entries:
        story.append(P('Aucune matière dans cette catégorie / No subject in this category.',
                       fontSize=9, textColor=colors.grey, spaceAfter=8))
        return None

    def hcell(t, align='CENTER'):
        return C(t, align=align, bold=True, size=8, color=colors.white)

    if period == 'annual':
        header = [hcell('Matière / Subject', 'LEFT'), hcell('Coeff'), hcell('T1'),
                  hcell('T2'), hcell('T3'), hcell('Moy. Ann.'), hcell('Lettre'),
                  hcell('Appréciation')]
        col_widths = [4.7 * cm, 1.2 * cm, 1.3 * cm, 1.3 * cm, 1.3 * cm, 2.0 * cm,
                      1.3 * cm, 5.4 * cm]
        rows = _subject_rows_annual(entries, scale)
    else:
        header = [hcell('Matière / Subject', 'LEFT'), hcell('Coeff'), hcell('Notes'),
                  hcell(scale_label(scale)), hcell('Moy. Pond.'), hcell('Lettre'),
                  hcell('Appréciation')]
        col_widths = [4.6 * cm, 1.2 * cm, 3.6 * cm, 1.9 * cm, 1.9 * cm, 1.3 * cm, 4.0 * cm]
        rows = _subject_rows_trimester(entries, scale)

    section_avg = _weighted_section_average(entries)
    letter, _, _ = get_letter_grade(section_avg)
    total_label = C('MOYENNE DE LA PARTIE', bold=True)
    total_row = ([total_label, '', '', '', '',
                  _fmt_scale_denom(section_avg, scale), letter or '—',
                  C(get_appreciation(section_avg), align='CENTER', bold=True)]
                 if period == 'annual' else
                 [total_label, '', '', _fmt_scale_denom(section_avg, scale), '',
                  letter or '—', C(get_appreciation(section_avg), align='CENTER', bold=True)])

    full_rows = [header] + rows + [total_row]
    tbl = Table(full_rows, colWidths=col_widths, repeatRows=1)
    style_cmds = [
        ('BACKGROUND', (0, 0), (-1, 0), head_color),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
        ('GRID', (0, 0), (-1, -1), 0.25, colors.lightgrey),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 2.5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2.5),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#FEF3C7')),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
    ]
    for i in range(1, len(full_rows) - 1):
        style_cmds.append(('BACKGROUND', (0, i), (-1, i),
                           colors.white if i % 2 == 0 else zebra_color))
    tbl.setStyle(TableStyle(style_cmds))
    story.append(tbl)
    story.append(Spacer(1, 0.25 * cm))
    return section_avg


# ─── Statistiques de classe + moyennes bilingues (BUG N°2 / N°6) ─────────────

def _expected_languages(student_class):
    """
    Langues que le bulletin de cette classe doit PRÉSENTER.

    POURQUOI CE N'EST PAS TOUJOURS « FR ET EN »
    -------------------------------------------
    Le bulletin standard imprimait les deux parties quoi qu'il arrive.
    Pour une classe francophone de FEBA FHA, la partie anglaise sortait
    donc à chaque trimestre avec « Aucune matière dans cette catégorie »,
    suivie d'une « Moyenne Anglaise » à « — » et d'une moyenne bilingue
    calculée sur une langue absente. Le document annonçait un manque là
    où il n'y avait rien à manquer.

    Le parcours DÉCLARÉ de la classe dit ce qui est attendu. En son
    absence — classe inconnue, modèle plus ancien — on retombe sur le
    bilingue : c'est le fonctionnement historique de FEBA, et un bulletin
    ne doit jamais perdre une section par accident.
    """
    if student_class is None:
        return ("fr", "en")
    getter = getattr(student_class, "expected_subject_languages", None)
    if not callable(getter):
        return ("fr", "en")
    langues = tuple(getter() or ())
    return langues or ("fr", "en")


def _add_stats_section(story, bilingual_data, class_stats, average, bulletin, period, palette,
                       scale=20, expected_languages=("fr", "en")):
    story.append(HRFlowable(width='100%', thickness=1, color=palette.gold))
    story.append(P('MOYENNES & STATISTIQUES DE LA CLASSE / AVERAGES & CLASS STATISTICS',
                   fontSize=11, fontName='Helvetica-Bold', textColor=palette.primary,
                   spaceBefore=4, spaceAfter=4))

    fr_avg = bilingual_data.get('fr_average')
    en_avg = bilingual_data.get('en_average')
    bi_avg = bilingual_data.get('bilingual_average')
    fr_letter, _, _ = get_letter_grade(fr_avg)
    en_letter, _, _ = get_letter_grade(en_avg)
    bi_letter, _, _ = get_letter_grade(bi_avg)

    def hc(t, align='CENTER'):
        return C(t, align=align, bold=True, size=8, color=colors.white)

    header = [hc('Catégorie', 'LEFT'), hc('Moyenne élève'), hc('Moy. min. classe'),
              hc('Moy. max. classe'), hc('Lettre')]

    # UNE LIGNE PAR LANGUE RÉELLEMENT CONCERNÉE.
    #
    # Une langue est présentée si le parcours de la classe l'attend, ou si
    # une moyenne existe malgré tout — on n'affiche pas une ligne vide qui
    # ne sera jamais remplie, et on ne cache jamais un résultat réel.
    attendues = tuple(expected_languages or ("fr", "en"))
    montrer_fr = 'fr' in attendues or fr_avg is not None
    montrer_en = 'en' in attendues or en_avg is not None
    # La moyenne bilingue est une pondération 60/40 de DEUX langues. Sur un
    # parcours monolingue elle n'a pas d'objet : l'afficher reviendrait à
    # présenter une note pondérée par une matière que la classe n'enseigne
    # pas.
    montrer_bi = montrer_fr and montrer_en

    rows = [header]
    fonds = []  # (index de ligne, couleur de fond)
    if montrer_fr:
        fonds.append((len(rows), palette.light))
        rows.append([C('Moyenne Française / French Average'),
                     _fmt_scale_denom(fr_avg, scale), _fmt_scale(class_stats.get('fr_min'), scale),
                     _fmt_scale(class_stats.get('fr_max'), scale), fr_letter or '—'])
    if montrer_en:
        fonds.append((len(rows), EN_BG))
        rows.append([C('Moyenne Anglaise / English Average'),
                     _fmt_scale_denom(en_avg, scale), _fmt_scale(class_stats.get('en_min'), scale),
                     _fmt_scale(class_stats.get('en_max'), scale), en_letter or '—'])
    ligne_bi = None
    if montrer_bi:
        ligne_bi = len(rows)
        fonds.append((ligne_bi, colors.HexColor('#FFF3CD')))
        rows.append([C('Moyenne Bilingue / Bilingual Average ★', bold=True),
                     _fmt_scale_denom(bi_avg, scale), _fmt_scale(class_stats.get('bi_min'), scale),
                     _fmt_scale(class_stats.get('bi_max'), scale), bi_letter or '—'])

    tbl = Table(rows, colWidths=[6.9 * cm, 2.9 * cm, 3.2 * cm, 3.2 * cm, 2.3 * cm])
    style = [
        ('BACKGROUND', (0, 0), (-1, 0), palette.gold),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
        ('GRID', (0, 0), (-1, -1), 0.25, colors.lightgrey),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]
    # Les index de fond étaient écrits en dur (1, 2, 3). Ils suivent
    # désormais les lignes réellement produites.
    style += [('BACKGROUND', (0, i), (-1, i), couleur) for i, couleur in fonds]
    if ligne_bi is not None:
        style.append(('FONTNAME', (0, ligne_bi), (-1, ligne_bi), 'Helvetica-Bold'))
    tbl.setStyle(TableStyle(style))
    story.append(tbl)

    story.append(Spacer(1, 0.15 * cm))
    if montrer_bi:
        story.append(P(
            f'<font color="{palette.brand.primary_color}"><b>Formule bilingue / '
            'Bilingual formula:</b></font> Moyenne Bilingue = '
            '(Moyenne Française × 60%) + (Moyenne Anglaise × 40%)',
            fontSize=8, spaceAfter=5,
        ))

    # Bande "moyenne générale" — sans rang (BUG N°2)
    letter, _, _ = get_letter_grade(average)
    summary_data = [[
        C('Moyenne Générale', align='CENTER', bold=True, size=9),
        C(_fmt_scale_denom(average, scale), align='CENTER', bold=True, size=9,
          color=palette.primary),
        C('Lettre', align='CENTER', bold=True, size=9),
        C(f'{letter or "—"}', align='CENTER', bold=True, size=9),
        C('Appréciation', align='CENTER', bold=True, size=9),
        C(bulletin.appreciation or '—', align='CENTER', bold=True, size=9),
    ]]
    s_tbl = Table(summary_data, colWidths=[3.5 * cm, 2.7 * cm, 1.7 * cm, 1.6 * cm, 3.0 * cm, 6.0 * cm])
    s_tbl.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), palette.light),
        ('GRID', (0, 0), (-1, -1), 0.5, palette.primary),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    story.append(s_tbl)
    story.append(Spacer(1, 0.3 * cm))


# ─── STANDARD PDF Template (Primaire/Collège/Lycée) ──────────────────────────

def _build_standard_pdf(buffer, student, period, school_year, subject_data,
                        bilingual_data, class_stats, average, bulletin, palette,
                        expected_languages=("fr", "en")):
    # Marges 1.2 cm : largeur utile = 21 - 2×1.2 = 18.6 cm. Toutes les tables
    # sont dimensionnées à ≤ 18.5 cm → marge de sécurité, aucun débordement.
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        rightMargin=1.2 * cm, leftMargin=1.2 * cm,
        topMargin=1.0 * cm, bottomMargin=1.0 * cm,
        title='Bulletin de notes', author=palette.brand.display_name,
    )
    story = []
    # V8 — barème d'affichage du bulletin selon le niveau (1..11 → /10).
    scale = _student_scale(student)

    _add_header(story, student, period, school_year, palette,
                'BULLETIN DE NOTES / PROGRESS REPORT')
    _add_student_info(story, student, period, school_year, palette)

    # BUG N°1 : séparation stricte des données françaises et anglaises.
    entries = list(subject_data.values())
    fr_entries = [e for e in entries if e.get('language') == 'fr']
    en_entries = [e for e in entries if e.get('language') == 'en']
    other_entries = [e for e in entries if e.get('language') not in ('fr', 'en')]

    # Une section n'est imprimée que si le parcours de la classe l'attend,
    # ou si des résultats existent malgré tout. Une classe francophone
    # n'affiche donc plus une partie anglaise vide à chaque trimestre ;
    # une classe bilingue à qui il manque une langue continue, elle, de
    # montrer la section vide — c'est une anomalie de configuration, et
    # la masquer reviendrait à la taire.
    attendues = tuple(expected_languages or ("fr", "en"))
    if 'fr' in attendues or fr_entries:
        _add_language_section(
            story, 'RÉSULTATS — PARTIE FRANÇAISE / FRENCH SECTION',
            fr_entries, period, palette.fr_head, palette.light, scale,
        )
    if 'en' in attendues or en_entries:
        _add_language_section(
            story, 'ACADEMIC RESULTS — ENGLISH SECTION / PARTIE ANGLAISE',
            en_entries, period, EN_HEAD, EN_BG, scale,
        )
    if other_entries:
        _add_language_section(
            story, 'AUTRES MATIÈRES / OTHER SUBJECTS',
            other_entries, period, colors.HexColor('#6B21A8'), colors.HexColor('#FAF5FF'), scale,
        )

    _add_stats_section(story, bilingual_data, class_stats, average, bulletin,
                       period, palette, scale, expected_languages=attendues)
    _add_signatures(story, bulletin, palette)
    _add_footer(story, palette)
    doc.build(story)


# ─── MATERNELLE PDF Template ──────────────────────────────────────────────────

# Seuils officiels des lettres, exprimés sur l'échelle interne /20.
# (borne basse, borne haute incluse ; None = pas de borne de ce côté)
_GRADING_KEY = [
    ('A+', Decimal('19.5'), None), ('A', Decimal('18'), Decimal('19')),
    ('A-', Decimal('16'), Decimal('17')), ('B+', Decimal('15'), Decimal('15')),
    ('B', Decimal('13'), Decimal('14')), ('B-', Decimal('12'), Decimal('12')),
    ('C+', Decimal('11'), Decimal('11')), ('C', Decimal('10'), Decimal('10')),
    ('C-', Decimal('9'), Decimal('9')), ('D+', Decimal('8'), Decimal('8')),
    ('D', Decimal('6'), Decimal('7')), ('D-', Decimal('4'), Decimal('5')),
    ('F', None, Decimal('4')),
]


def _grading_key_cells(scale):
    """Clé de notation exprimée dans le barème du bulletin.

    Les lettres restent calculées sur l'échelle interne /20 ; seuls les seuils
    AFFICHÉS suivent le barème du document (÷ 2 pour un bulletin sur 10).
    """
    def n(value):
        converted = convert_average_for_scale(value, scale)
        texte = f'{converted:.2f}'.rstrip('0').rstrip('.')
        return texte or '0'

    cells = []
    for letter, low, high in _GRADING_KEY:
        if low is None:
            cells.append(f'{letter} (<{n(high)})')
        elif high is None:
            cells.append(f'{letter} (≥{n(low)})')
        elif low == high:
            cells.append(f'{letter} ({n(low)})')
        else:
            cells.append(f'{letter} ({n(low)}-{n(high)})')
    return cells


def _build_maternelle_pdf(buffer, student, period, school_year, subject_data,
                          average, bulletin, palette):
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        rightMargin=1.2 * cm, leftMargin=1.2 * cm,
        topMargin=1.0 * cm, bottomMargin=1.0 * cm,
        title='Bulletin de notes — Maternelle', author=palette.brand.display_name,
    )
    story = []

    _add_header(story, student, period, school_year, palette,
                'BULLETIN DE NOTES — MATERNELLE')
    _add_student_info(story, student, period, school_year, palette)

    # Grading key — 13 colonnes égales sur la largeur utile (≤ 18.5 cm).
    # V8 : les seuils suivent le barème du bulletin. Sur un bulletin de
    # maternelle (sur 10), afficher « A+ (≥19.5) » revenait à donner la seule
    # référence chiffrée du document dans une échelle qui n'est pas la sienne.
    story.append(P('Grading key / Clé de notation :', fontSize=9,
                   fontName='Helvetica-Bold', textColor=palette.primary, spaceAfter=2))
    key_data = [_grading_key_cells(_student_scale(student))]
    key_tbl = Table(key_data, colWidths=[18.5 / 13 * cm] * 13)
    key_tbl.setStyle(TableStyle([
        ('FONTSIZE', (0, 0), (-1, -1), 6),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('GRID', (0, 0), (-1, -1), 0.25, colors.lightgrey),
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F0F4FF')),
        ('LEFTPADDING', (0, 0), (-1, -1), 2),
        ('RIGHTPADDING', (0, 0), (-1, -1), 2),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]))
    story.append(key_tbl)
    story.append(Spacer(1, 0.35 * cm))

    # Résultats en lettres, séparés FR / EN (BUG N°1)
    story.append(P('MATIÈRES / SUBJECTS', fontSize=11, fontName='Helvetica-Bold',
                   textColor=palette.primary, spaceAfter=4))

    entries = list(subject_data.values())
    fr_rows = [e for e in entries if e.get('language') == 'fr']
    en_rows = [e for e in entries if e.get('language') == 'en']
    other_rows = [e for e in entries if e.get('language') not in ('fr', 'en')]

    def make_subject_rows(rows_list):
        rows = []
        for info in rows_list:
            letter, meaning, stars = get_letter_grade(info['average'])
            rows.append([
                C(info['subject_name'], bold=True),
                letter or '—',
                C(meaning or '—', align='CENTER'),
                stars or '',
            ])
        return rows

    all_rows = []
    if fr_rows:
        all_rows.append([C('PARTIE FRANÇAISE / FRENCH SECTION', bold=True, color=colors.white), '', '', ''])
        all_rows.extend(make_subject_rows(fr_rows))
    if en_rows:
        all_rows.append([C('ENGLISH SECTION / PARTIE ANGLAISE', bold=True, color=colors.white), '', '', ''])
        all_rows.extend(make_subject_rows(en_rows))
    if other_rows:
        all_rows.append([C('AUTRES MATIÈRES / OTHER SUBJECTS', bold=True, color=colors.white), '', '', ''])
        all_rows.extend(make_subject_rows(other_rows))
    if not all_rows:
        all_rows = [[C('Aucune matière'), '', '', '']]

    def mhcell(t):
        return C(t, align='CENTER', bold=True, size=8, color=colors.white)

    header_row = [mhcell('MATIÈRE / SUBJECT'), mhcell('NOTE / GRADE'),
                  mhcell('APPRÉCIATION / COMMENT'), mhcell('NIVEAU / LEVEL')]
    full_rows = [header_row] + all_rows

    g_tbl = Table(full_rows, colWidths=[8.0 * cm, 2.5 * cm, 5.5 * cm, 2.5 * cm])
    style_cmds = [
        ('BACKGROUND', (0, 0), (-1, 0), palette.primary),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
        ('GRID', (0, 0), (-1, -1), 0.25, colors.lightgrey),
        ('PADDING', (0, 0), (-1, -1), 4),
    ]
    for i, row in enumerate(full_rows[1:], 1):
        if row[1] == '' and row[2] == '' and row[3] == '':
            style_cmds.append(('BACKGROUND', (0, i), (-1, i), palette.gold))
            style_cmds.append(('TEXTCOLOR', (0, i), (-1, i), colors.white))
            style_cmds.append(('FONTNAME', (0, i), (-1, i), 'Helvetica-Bold'))
            style_cmds.append(('SPAN', (0, i), (-1, i)))
        else:
            bg = colors.white if i % 2 == 0 else colors.HexColor('#F8FAFF')
            style_cmds.append(('BACKGROUND', (0, i), (-1, i), bg))
    g_tbl.setStyle(TableStyle(style_cmds))
    story.append(g_tbl)
    story.append(Spacer(1, 0.4 * cm))

    # Conduite
    story.append(P('CONDUITE / CONDUCT', fontSize=11, fontName='Helvetica-Bold',
                   textColor=palette.primary, spaceAfter=4))
    conduct_items = [
        'Contrôle du langage / Controls talking',
        'Respect de l\'autorité / Respects authority',
        'Maîtrise de soi / Self-control',
        'Suit les consignes / Follows directions',
        'Attitude en classe / Class behavior',
        'Travail de groupe / Group work',
        'Retourne les devoirs / Returns homework',
    ]
    conduct_data = [[C('Critère / Criterion', bold=True, color=colors.white),
                     C('Note / Grade', align='CENTER', bold=True, color=colors.white),
                     C('Commentaire', bold=True, color=colors.white)]]
    for item in conduct_items:
        conduct_data.append([C(item), C('—', align='CENTER'), ''])
    c_tbl = Table(conduct_data, colWidths=[8.0 * cm, 3.0 * cm, 7.5 * cm])
    c_tbl.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), palette.primary),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 0.25, colors.lightgrey),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]))
    story.append(c_tbl)
    story.append(Spacer(1, 0.3 * cm))

    _add_signatures(story, bulletin, palette)
    _add_footer(story, palette)
    doc.build(story)


# ─── Signatures & pied de page ────────────────────────────────────────────────

def _add_signatures(story, bulletin, palette):
    story.append(HRFlowable(width='100%', thickness=1, color=colors.lightgrey))
    story.append(Spacer(1, 0.2 * cm))
    comment = bulletin.general_comment or '(Aucun commentaire / No comment)'
    # V7 : cachet officiel de la direction apposé dans la case « Cachet ».
    # P0 — le cachet est celui de CETTE académie ; absent, la case reste vide.
    cachet_path = palette.brand.stamp
    stamp_cell = ''
    if cachet_path:
        try:
            # 2,5 cm : lisible à l'impression sans gonfler la hauteur du bulletin.
            stamp = Image(cachet_path, width=2.5 * cm, height=2.5 * cm)  # ratio 1:1 conservé
            stamp.hAlign = 'CENTER'
            stamp_cell = stamp
        except Exception as exc:
            logger.warning("Cachet non apposé (non bloquant) : %s", exc, exc_info=True)
    # V8 — Zone de validation de la Direction repensée.
    #
    # Avant : le cachet flottait dans une cellule partagée avec la ligne de
    # signature et la date, sans marge ni alignement — il paraissait posé au
    # hasard et frôlait le bord droit.
    #
    # Maintenant : un bloc dédié, empilé et centré — intitulé, cachet centré,
    # puis lieu/date — assemblé dans sa PROPRE table (donc insécable) et placé
    # à droite du commentaire du directeur. Aucune coordonnée absolue : la
    # grille s'adapte si le commentaire s'allonge.
    validation_tbl = Table(
        [[C('La Direction / The Principal', bold=True, align='CENTER')],
         [stamp_cell],
         [C((f'{palette.brand.location_line}, le '
             if palette.brand.location_line else 'Le ')
            + timezone.now().strftime("%d/%m/%Y"), align='CENTER')]],
        colWidths=[8.3 * cm],
    )
    validation_tbl.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 1), (0, 1), 'MIDDLE'),   # cachet centré dans sa case
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
    ]))

    # Colonne de gauche : commentaire du directeur PUIS signature du parent
    # (empilés). Le bloc « signature du parent » qui occupait auparavant une
    # ligne pleine largeur est ainsi absorbé : la zone de validation gagne la
    # hauteur nécessaire à un cachet correctement rendu, SANS allonger le
    # bulletin (un bulletin chargé tient toujours sur une seule page A4).
    comment_box = Table(
        [[C('Commentaire du Directeur / Principal\'s Comment', bold=True)],
         [C(comment)]],
        colWidths=[9.4 * cm], rowHeights=[0.5 * cm, 2.4 * cm],
    )
    comment_box.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 0.25, colors.lightgrey),
        ('LINEBELOW', (0, 0), (0, 0), 0.25, colors.lightgrey),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 5),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]))
    parent_sig = Table(
        [[C('Signature du Parent / Parent\'s Signature:', bold=True),
          C('________________________', align='CENTER')]],
        colWidths=[5.2 * cm, 4.2 * cm], rowHeights=[0.7 * cm],
    )
    parent_sig.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
    ]))
    left_column = Table([[comment_box], [parent_sig]], colWidths=[9.4 * cm])
    left_column.setStyle(TableStyle([
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))

    sig_tbl = Table([[left_column, '', validation_tbl]],
                    colWidths=[9.4 * cm, 0.8 * cm, 8.3 * cm])
    sig_tbl.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))
    # Le bloc « commentaire + validation » ne doit jamais être coupé en deux
    # pages : le cachet reste solidaire de sa zone de validation.
    story.append(KeepTogether(sig_tbl))


def _add_footer(story, palette):
    brand = palette.brand
    name = brand.footer_text or brand.display_name
    story.append(Spacer(1, 0.1 * cm))
    story.append(HRFlowable(width='100%', thickness=1, color=colors.lightgrey))
    story.append(P(
        f'{name} | Généré le {timezone.now().strftime("%d/%m/%Y à %H:%M")}',
        fontSize=6, alignment=1, textColor=colors.grey,
    ))
