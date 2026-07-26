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
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable, Image
)
from django.core.files.base import ContentFile
from feba_project.branding import SCHOOL_GROUP_NAME
# V8 — barème d'affichage par niveau (1..11 → /10, au-delà → /20)
from apps.grades.grading import (
    convert_average_for_scale, get_grading_scale, scale_label,
)
from django.utils import timezone

from apps.grades.models import Grade, get_letter_grade, get_appreciation
from apps.bulletins.models import Bulletin

logger = logging.getLogger('apps')

# Static FEBA logo fallback path
STATIC_LOGO_PATH = os.path.join(
    os.path.dirname(__file__), '..', '..', 'feba_project', 'static_files', 'logo_feba.jpeg'
)
# Cachet officiel (V7) — extrait fidèlement du PDF fourni par la direction.
STATIC_CACHET_PATH = os.path.join(
    os.path.dirname(__file__), '..', '..', 'feba_project', 'static_files', 'cachet_feba.png'
)


def _get_cachet_path():
    """Chemin du cachet officiel à apposer, ou None si le fichier est absent
    (dégradation gracieuse : le document reste valide, sans cachet)."""
    return STATIC_CACHET_PATH if os.path.exists(STATIC_CACHET_PATH) else None

# Couleurs de la charte
PRIMARY = colors.HexColor('#1E3A6E')   # bleu institutionnel
GOLD    = colors.HexColor('#C9A227')   # or
LIGHT   = colors.HexColor('#EEF3FF')   # bleu très clair (partie française)
FR_HEAD = colors.HexColor('#1E3A6E')   # en-tête tableau FR
EN_HEAD = colors.HexColor('#166534')   # vert foncé (partie anglaise)
EN_BG   = colors.HexColor('#F0FFF4')   # vert très clair


def _get_school_logo_path(student):
    """Return the active logo filesystem path for the student's school."""
    try:
        from apps.schools.models import SchoolBranding
        school = None
        if student.school_id:
            school = student.school
        elif student.school_year and student.school_year.school_id:
            school = student.school_year.school
        elif student.current_class and student.current_class.school_year:
            school = student.current_class.school_year.school

        if school:
            path = SchoolBranding.get_active_logo_path(school)
            if path and os.path.exists(path):
                return path
    except Exception as e:
        logger.warning(f"Logo path error: {e}")

    static_path = os.path.normpath(STATIC_LOGO_PATH)
    if os.path.exists(static_path):
        return static_path
    return None


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
    """Cellule de tableau à retour à la ligne automatique."""
    style = dict(_CELL_BASE)
    style['fontName'] = 'Helvetica-Bold' if bold else 'Helvetica'
    style['fontSize'] = size
    style['leading'] = size + 1.5
    style['alignment'] = {'LEFT': 0, 'CENTER': 1, 'RIGHT': 2}[align]
    if color is not None:
        style['textColor'] = color
    return Paragraph('' if text is None else str(text), ParagraphStyle('_c', **style))


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
        logo_path = _get_school_logo_path(student)
        buffer = BytesIO()

        if is_maternelle:
            _build_maternelle_pdf(buffer, student, period, school_year,
                                  subject_data, average, bulletin, logo_path)
        else:
            _build_standard_pdf(buffer, student, period, school_year,
                                subject_data, bilingual_data, class_stats,
                                average, bulletin, logo_path)

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

def _school_display_names(student, school_year):
    """(nom principal, sous-titre) de l'établissement pour l'en-tête."""
    school = None
    if student.school_id:
        school = student.school
    elif school_year and getattr(school_year, 'school_id', None):
        school = school_year.school
    if school:
        subtitle = ", ".join(x for x in [school.address, school.city, school.country] if x)
        return school.name, subtitle or "—"
    return "FAITH & EXCELLENCE BILINGUAL ACADEMY", "École Bilingue Foi & Excellence — Cotonou, Bénin"


def _add_header(story, student, period, school_year, logo_path, title):
    name, subtitle = _school_display_names(student, school_year)
    if logo_path and os.path.exists(logo_path):
        try:
            logo_img = Image(logo_path, width=2.0 * cm, height=2.0 * cm)
            logo_img.hAlign = 'CENTER'
            story.append(logo_img)
        except Exception as exc:
            logger.warning("Erreur non bloquante ignorée : %s", exc, exc_info=True)
    # V7 : ligne « groupe » (GROUPE ÉDUCATIF FEBA) au-dessus du nom officiel.
    story.append(P(SCHOOL_GROUP_NAME, fontSize=9, fontName='Helvetica-Bold',
                   alignment=1, textColor=GOLD, spaceAfter=1))
    story.append(P(name.upper(), fontSize=14, fontName='Helvetica-Bold',
                   alignment=1, textColor=PRIMARY, spaceAfter=2))
    story.append(P(subtitle, fontSize=9, alignment=1, spaceAfter=2))
    story.append(HRFlowable(width='100%', thickness=3, color=GOLD))
    story.append(P(f'{title} — {_period_label(period)}',
                   fontSize=13, fontName='Helvetica-Bold', alignment=1,
                   textColor=GOLD, spaceBefore=4))
    story.append(P(f'Année scolaire / School Year : {school_year.name}',
                   fontSize=10, alignment=1, spaceAfter=4))
    story.append(Spacer(1, 0.2 * cm))


def _add_student_info(story, student, period, school_year):
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
        ('BACKGROUND', (0, 0), (0, -1), LIGHT),
        ('BACKGROUND', (2, 0), (2, -1), LIGHT),
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
            details = '  '.join(
                f"{note_labels.get(n.note_type, 'N')}:{float(n.value):.1f}"
                for n in sorted(notes, key=lambda x: x.note_type)
            )
        else:
            details = 'Non noté'
        weighted = (float(avg) * info['coefficient']) if avg is not None else None
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

def _add_stats_section(story, bilingual_data, class_stats, average, bulletin, period, scale=20):
    story.append(HRFlowable(width='100%', thickness=1, color=GOLD))
    story.append(P('MOYENNES & STATISTIQUES DE LA CLASSE / AVERAGES & CLASS STATISTICS',
                   fontSize=11, fontName='Helvetica-Bold', textColor=PRIMARY,
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
    rows = [
        header,
        [C('Moyenne Française / French Average'),
         _fmt_scale_denom(fr_avg, scale), _fmt_scale(class_stats.get('fr_min'), scale), _fmt_scale(class_stats.get('fr_max'), scale),
         fr_letter or '—'],
        [C('Moyenne Anglaise / English Average'),
         _fmt_scale_denom(en_avg, scale), _fmt_scale(class_stats.get('en_min'), scale), _fmt_scale(class_stats.get('en_max'), scale),
         en_letter or '—'],
        [C('Moyenne Bilingue / Bilingual Average ★', bold=True),
         _fmt_scale_denom(bi_avg, scale), _fmt_scale(class_stats.get('bi_min'), scale), _fmt_scale(class_stats.get('bi_max'), scale),
         bi_letter or '—'],
    ]
    tbl = Table(rows, colWidths=[6.9 * cm, 2.9 * cm, 3.2 * cm, 3.2 * cm, 2.3 * cm])
    tbl.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), GOLD),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
        ('GRID', (0, 0), (-1, -1), 0.25, colors.lightgrey),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('BACKGROUND', (0, 1), (-1, 1), LIGHT),
        ('BACKGROUND', (0, 2), (-1, 2), EN_BG),
        ('BACKGROUND', (0, 3), (-1, 3), colors.HexColor('#FFF3CD')),
        ('FONTNAME', (0, 3), (-1, 3), 'Helvetica-Bold'),
    ]))
    story.append(tbl)

    story.append(Spacer(1, 0.15 * cm))
    story.append(P(
        '<font color="#1E3A6E"><b>Formule bilingue / Bilingual formula:</b></font> '
        'Moyenne Bilingue = (Moyenne Française × 60%) + (Moyenne Anglaise × 40%)',
        fontSize=8, spaceAfter=5,
    ))

    # Bande "moyenne générale" — sans rang (BUG N°2)
    letter, _, _ = get_letter_grade(average)
    summary_data = [[
        C('Moyenne Générale', align='CENTER', bold=True, size=9),
        C(_fmt_scale_denom(average, scale), align='CENTER', bold=True, size=9, color=PRIMARY),
        C('Lettre', align='CENTER', bold=True, size=9),
        C(f'{letter or "—"}', align='CENTER', bold=True, size=9),
        C('Appréciation', align='CENTER', bold=True, size=9),
        C(bulletin.appreciation or '—', align='CENTER', bold=True, size=9),
    ]]
    s_tbl = Table(summary_data, colWidths=[3.5 * cm, 2.7 * cm, 1.7 * cm, 1.6 * cm, 3.0 * cm, 6.0 * cm])
    s_tbl.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), LIGHT),
        ('GRID', (0, 0), (-1, -1), 0.5, PRIMARY),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    story.append(s_tbl)
    story.append(Spacer(1, 0.3 * cm))


# ─── STANDARD PDF Template (Primaire/Collège/Lycée) ──────────────────────────

def _build_standard_pdf(buffer, student, period, school_year, subject_data,
                        bilingual_data, class_stats, average, bulletin, logo_path):
    # Marges 1.2 cm : largeur utile = 21 - 2×1.2 = 18.6 cm. Toutes les tables
    # sont dimensionnées à ≤ 18.5 cm → marge de sécurité, aucun débordement.
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        rightMargin=1.2 * cm, leftMargin=1.2 * cm,
        topMargin=1.0 * cm, bottomMargin=1.0 * cm,
        title='Bulletin de notes', author='FEBA School Management System',
    )
    story = []
    # V8 — barème d'affichage du bulletin selon le niveau (1..11 → /10).
    scale = _student_scale(student)

    _add_header(story, student, period, school_year, logo_path,
                'BULLETIN DE NOTES / PROGRESS REPORT')
    _add_student_info(story, student, period, school_year)

    # BUG N°1 : séparation stricte des données françaises et anglaises.
    entries = list(subject_data.values())
    fr_entries = [e for e in entries if e.get('language') == 'fr']
    en_entries = [e for e in entries if e.get('language') == 'en']
    other_entries = [e for e in entries if e.get('language') not in ('fr', 'en')]

    _add_language_section(
        story, 'RÉSULTATS — PARTIE FRANÇAISE / FRENCH SECTION',
        fr_entries, period, FR_HEAD, LIGHT, scale,
    )
    _add_language_section(
        story, 'ACADEMIC RESULTS — ENGLISH SECTION / PARTIE ANGLAISE',
        en_entries, period, EN_HEAD, EN_BG, scale,
    )
    if other_entries:
        _add_language_section(
            story, 'AUTRES MATIÈRES / OTHER SUBJECTS',
            other_entries, period, colors.HexColor('#6B21A8'), colors.HexColor('#FAF5FF'), scale,
        )

    _add_stats_section(story, bilingual_data, class_stats, average, bulletin, period, scale)
    _add_signatures(story, bulletin)
    _add_footer(story, student, school_year)
    doc.build(story)


# ─── MATERNELLE PDF Template ──────────────────────────────────────────────────

def _build_maternelle_pdf(buffer, student, period, school_year, subject_data,
                          average, bulletin, logo_path):
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        rightMargin=1.2 * cm, leftMargin=1.2 * cm,
        topMargin=1.0 * cm, bottomMargin=1.0 * cm,
        title='Bulletin de notes — Maternelle', author='FEBA School Management System',
    )
    story = []

    _add_header(story, student, period, school_year, logo_path,
                'BULLETIN DE NOTES — MATERNELLE')
    _add_student_info(story, student, period, school_year)

    # Grading key — 13 colonnes égales sur la largeur utile (≤ 18.5 cm).
    story.append(P('Grading key / Clé de notation :', fontSize=9,
                   fontName='Helvetica-Bold', textColor=PRIMARY, spaceAfter=2))
    key_data = [['A+ (≥19.5)', 'A (18-19)', 'A- (16-17)', 'B+ (15)', 'B (13-14)', 'B- (12)',
                 'C+ (11)', 'C (10)', 'C- (9)', 'D+ (8)', 'D (6-7)', 'D- (4-5)', 'F (<4)']]
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
                   textColor=PRIMARY, spaceAfter=4))

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
        ('BACKGROUND', (0, 0), (-1, 0), PRIMARY),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
        ('GRID', (0, 0), (-1, -1), 0.25, colors.lightgrey),
        ('PADDING', (0, 0), (-1, -1), 4),
    ]
    for i, row in enumerate(full_rows[1:], 1):
        if row[1] == '' and row[2] == '' and row[3] == '':
            style_cmds.append(('BACKGROUND', (0, i), (-1, i), GOLD))
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
                   textColor=PRIMARY, spaceAfter=4))
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
        ('BACKGROUND', (0, 0), (-1, 0), PRIMARY),
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

    _add_signatures(story, bulletin)
    _add_footer(story, student, school_year)
    doc.build(story)


# ─── Signatures & pied de page ────────────────────────────────────────────────

def _add_signatures(story, bulletin):
    story.append(HRFlowable(width='100%', thickness=1, color=colors.lightgrey))
    story.append(Spacer(1, 0.2 * cm))
    comment = bulletin.general_comment or '(Aucun commentaire / No comment)'
    # V7 : cachet officiel de la direction apposé dans la case « Cachet ».
    cachet_path = _get_cachet_path()
    stamp_cell = ''
    if cachet_path:
        try:
            stamp = Image(cachet_path, width=2.6 * cm, height=2.6 * cm)
            stamp.hAlign = 'CENTER'
            stamp_cell = stamp
        except Exception as exc:
            logger.warning("Cachet non apposé (non bloquant) : %s", exc, exc_info=True)
    sig_data = [
        [C('Commentaire du Directeur / Principal\'s Comment', bold=True),
         '', C('Signature & Cachet / Stamp', bold=True)],
        [C(comment), '', stamp_cell],
        ['', '', C('________________________', align='CENTER')],
        ['', '', C(f'Cotonou, le {timezone.now().strftime("%d/%m/%Y")}', align='CENTER')],
    ]
    sig_tbl = Table(sig_data, colWidths=[9.4 * cm, 0.8 * cm, 8.3 * cm],
                    rowHeights=[0.55 * cm, 1.15 * cm, 0.55 * cm, 0.5 * cm])
    sig_tbl.setStyle(TableStyle([
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('VALIGN', (2, 2), (2, 3), 'MIDDLE'),
        ('GRID', (0, 0), (0, -1), 0.25, colors.lightgrey),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 5),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]))
    story.append(sig_tbl)
    story.append(Spacer(1, 0.25 * cm))
    parent_sig = Table(
        [[C('Signature du Parent / Parent\'s Signature:', bold=True), '',
          C('________________________', align='CENTER')]],
        colWidths=[7.5 * cm, 3.7 * cm, 7.3 * cm]
    )
    parent_sig.setStyle(TableStyle([
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    story.append(parent_sig)


def _add_footer(story, student=None, school_year=None):
    name = 'FEBA School Management System'
    if student is not None:
        school_name, _ = _school_display_names(student, school_year)
        name = f'FEBA School Management System | {school_name}'
    story.append(Spacer(1, 0.1 * cm))
    story.append(HRFlowable(width='100%', thickness=1, color=colors.lightgrey))
    story.append(P(
        f'{name} | Généré le {timezone.now().strftime("%d/%m/%Y à %H:%M")}',
        fontSize=6, alignment=1, textColor=colors.grey,
    ))
