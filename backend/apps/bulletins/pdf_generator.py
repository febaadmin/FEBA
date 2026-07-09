"""
Bulletin PDF generator — v18 FEBA FINAL
Fonctionnalités :
  1. Logo FEBA dynamique (SchoolBranding → School.logo → static logo)
  2. Template Maternelle : notation en lettres + conduite
  3. Template Primaire/Collège/Lycée : numérique + bilingue (FR×40%+EN×60%)
  4. Calcul bilingue complet T1/T2/T3 + annuel
  5. Système de lettres A+/A/A-/B+/B/B-/C+/C/C-/D+/D/D-/F
  6. Classement dans la classe
  7. Régénération : supprime et recrée le PDF
"""
import os
import logging
from decimal import Decimal
from io import BytesIO

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable, Image
)
from django.core.files.base import ContentFile
from django.utils import timezone

from apps.grades.models import Grade, get_letter_grade, get_appreciation
from apps.bulletins.models import Bulletin

logger = logging.getLogger('apps')

# Static FEBA logo fallback path
STATIC_LOGO_PATH = os.path.join(
    os.path.dirname(__file__), '..', '..', 'feba_project', 'static_files', 'logo_feba.jpeg'
)


def _get_school_logo_path(student):
    """Return the active logo filesystem path for the student's school."""
    try:
        from apps.schools.models import SchoolBranding
        school = None
        if student.school_year and student.school_year.school_id:
            school = student.school_year.school
        elif student.current_class and student.current_class.school_year:
            school = student.current_class.school_year.school

        if school:
            path = SchoolBranding.get_active_logo_path(school)
            if path and os.path.exists(path):
                return path
    except Exception as e:
        logger.warning(f"Logo path error: {e}")

    # Fallback to static bundled logo
    static_path = os.path.normpath(STATIC_LOGO_PATH)
    if os.path.exists(static_path):
        return static_path
    return None


def _fmt(val):
    if val is None:
        return '—'
    return f'{float(val):.2f}'


def _period_label(period):
    labels = {
        'T1': '1ER TRIMESTRE', 'T2': '2ÈME TRIMESTRE',
        'T3': '3ÈME TRIMESTRE', 'annual': 'ANNUEL',
    }
    return labels.get(period, period.upper())


# ─── Entry Point ──────────────────────────────────────────────────────────────

def generate_bulletin(student, period, school_year):
    """
    Génère (ou régénère) le bulletin PDF d'un élève.
    Utilise le template maternelle si le niveau est maternelle,
    sinon le template standard bilingue.
    """
    logger.info(f"Generating bulletin: {student.matricule} {period} {school_year.name}")

    # ── Ensure student has a class for this year ──────────────────────────────
    # If student.current_class is None (multi-year scenario), try enrollment
    if not student.current_class:
        enrollment = student.get_enrollment_for_year(school_year)
        if enrollment and enrollment.class_obj:
            # Temporarily set for this generation (not saved to DB)
            student.current_class = enrollment.class_obj

    # FIX v32 : plus AUCUNE note à 0 n'est créée automatiquement.
    # Une matière sans note apparaît « — » sur le bulletin et est exclue
    # de la moyenne (voir Grade.get_subject_averages / calculate_average).

    # Detect template type
    is_maternelle = False
    if student.current_class and student.current_class.level:
        is_maternelle = student.current_class.level.is_maternelle()

    # Compute averages
    if period == 'annual':
        average = Grade.calculate_annual_average(student, school_year)
        subject_data = _build_annual_subject_data(student, school_year)
        bilingual_data = Grade.get_annual_bilingual(student, school_year)
    else:
        average = Grade.calculate_average(student, school_year, period)
        subject_data = Grade.get_subject_averages(student, school_year, period)
        bilingual_data = Grade.calculate_bilingual_averages(student, school_year, period)

    # Upsert bulletin — delete old PDF file if exists, then update fields
    bulletin, created = Bulletin.objects.get_or_create(
        student=student, school_year=school_year, period=period,
    )
    if not created and bulletin.pdf_file:
        # Supprime l'ancien fichier PDF avant régénération
        try:
            bulletin.pdf_file.delete(save=False)
        except Exception as exc:
            logger.warning("Erreur non bloquante ignorée : %s", exc, exc_info=True)
    bulletin.average = average
    from apps.grades.models import get_appreciation
    bulletin.appreciation = get_appreciation(average)

    # Rank in class
    if student.current_class:
        class_students = student.current_class.students.filter(is_active=True)
        averages_list = []
        for s in class_students:
            a = Grade.calculate_annual_average(s, school_year) if period == 'annual' else Grade.calculate_average(s, school_year, period)
            if a is not None:
                averages_list.append((s.id, float(a)))
        averages_list.sort(key=lambda x: -x[1])
        for rank, (sid, _) in enumerate(averages_list, 1):
            if sid == student.id:
                bulletin.rank_in_class = rank
                break

    # Generate PDF
    try:
        logo_path = _get_school_logo_path(student)
        buffer = BytesIO()

        if is_maternelle:
            _build_maternelle_pdf(buffer, student, period, school_year, subject_data, average, bulletin, logo_path)
        else:
            _build_standard_pdf(buffer, student, period, school_year, subject_data, bilingual_data, average, bulletin, logo_path)

        pdf_bytes = buffer.getvalue()
        buffer.close()

        # Delete old PDF
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
    from apps.subjects.models import Subject
    from apps.grades.models import Grade as _Grade
    subjects = []
    # 1. By level
    if student.current_class and student.current_class.level_id:
        subjects = list(Subject.objects.filter(level_id=student.current_class.level_id))
    # 2. By school
    if not subjects:
        school_id = None
        if school_year and hasattr(school_year, 'school_id') and school_year.school_id:
            school_id = school_year.school_id
        elif student.school_year and hasattr(student.school_year, 'school_id'):
            school_id = student.school_year.school_id
        if school_id:
            subjects = list(Subject.objects.filter(school_id=school_id))
    # 3. From actual grades
    if not subjects:
        sids = _Grade.objects.filter(
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
            # FIX v32 : un trimestre sans note n'entre pas dans la moyenne
            # annuelle de la matière (il n'est plus compté comme 0).
            if t_avg is not None:
                trim_avgs[t] = float(t_avg)
                valid_avgs.append(Decimal(str(t_avg)))
            else:
                trim_avgs[t] = None
        annual_avg = (sum(valid_avgs) / Decimal(len(valid_avgs))) if valid_avgs else None
        from apps.grades.models import get_letter_grade
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
            'has_notes':      any(v > 0 for v in trim_avgs.values()),
            'notes':          [],
        }
    return result


# ─── MATERNELLE PDF Template ──────────────────────────────────────────────────

def _build_maternelle_pdf(buffer, student, period, school_year, subject_data, average, bulletin, logo_path):
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        rightMargin=1.5*cm, leftMargin=1.5*cm,
        topMargin=1.5*cm, bottomMargin=1.5*cm,
    )
    story = []
    primary = colors.HexColor('#1E3A6E')
    gold    = colors.HexColor('#C9A227')
    light   = colors.HexColor('#EEF3FF')

    def P(text, **kw):
        return Paragraph(text, ParagraphStyle('_', **kw))

    # Header with logo
    header_items = []
    if logo_path and os.path.exists(logo_path):
        try:
            logo_img = Image(logo_path, width=3*cm, height=3*cm)
            logo_img.hAlign = 'CENTER'
            header_items.append(logo_img)
        except Exception as exc:
            logger.warning("Erreur non bloquante ignorée : %s", exc, exc_info=True)
    header_items.append(P('FAITH & EXCELLENCE BILINGUAL ACADEMY', fontSize=14,
                           fontName='Helvetica-Bold', alignment=1, textColor=primary, spaceAfter=2))
    header_items.append(P('École Bilingue Foi & Excellence — Cotonou, Bénin',
                           fontSize=10, fontName='Helvetica', alignment=1, spaceAfter=2))
    header_items.append(HRFlowable(width='100%', thickness=3, color=gold))
    header_items.append(P(f'BULLETIN DE NOTES — MATERNELLE — {_period_label(period)}',
                           fontSize=13, fontName='Helvetica-Bold', alignment=1, textColor=gold, spaceBefore=4))
    header_items.append(P(f'Année scolaire {school_year.name}',
                           fontSize=10, alignment=1, spaceAfter=4))
    story.extend(header_items)
    story.append(Spacer(1, 0.4*cm))

    # Student info
    class_name = student.current_class.name if student.current_class else '—'
    level_name = student.current_class.level.name if student.current_class and student.current_class.level else '—'
    info = [
        ['Élève / Student:', student.get_full_name(), 'Matricule:', student.matricule],
        ['Classe / Class:', class_name, 'Niveau / Level:', level_name],
        ['Effectif / Total:', str(bulletin.rank_in_class or '—'), 'Date de naissance:', str(student.date_of_birth) if student.date_of_birth else '—'],
    ]
    info_tbl = Table(info, colWidths=[4*cm, 6*cm, 4*cm, 4*cm])
    info_tbl.setStyle(TableStyle([
        ('FONTNAME', (0,0), (-1,-1), 'Helvetica'),
        ('FONTNAME', (0,0), (0,-1), 'Helvetica-Bold'),
        ('FONTNAME', (2,0), (2,-1), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,-1), 9),
        ('GRID', (0,0), (-1,-1), 0.25, colors.lightgrey),
        ('BACKGROUND', (0,0), (0,-1), light),
        ('BACKGROUND', (2,0), (2,-1), light),
        ('PADDING', (0,0), (-1,-1), 5),
    ]))
    story.append(info_tbl)
    story.append(Spacer(1, 0.5*cm))

    # Grading key
    story.append(P('Grading key / Clé de notation :', fontSize=9,
                   fontName='Helvetica-Bold', textColor=primary, spaceAfter=2))
    key_data = [['A+ (20-19.5)', 'A (19-18)', 'A- (17-16)', 'B+ (15)', 'B (14-13)', 'B- (12)', 'B (11)', 'C (10)', 'C- (9)', 'D+ (8)', 'D (7-6)', 'D- (5-4)', 'F (<4)']]
    key_tbl = Table(key_data, colWidths=[1.4*cm]*13)
    key_tbl.setStyle(TableStyle([
        ('FONTSIZE', (0,0), (-1,-1), 6),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('GRID', (0,0), (-1,-1), 0.25, colors.lightgrey),
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#F0F4FF')),
        ('PADDING', (0,0), (-1,-1), 3),
    ]))
    story.append(key_tbl)
    story.append(Spacer(1, 0.4*cm))

    # Results table — maternelle uses letters
    story.append(P('MATIÈRES / SUBJECTS', fontSize=11, fontName='Helvetica-Bold',
                   textColor=primary, spaceAfter=4))

    # Separate FR and EN subjects
    fr_rows = [(sid, info) for sid, info in subject_data.items() if info['language'] == 'fr']
    en_rows = [(sid, info) for sid, info in subject_data.items() if info['language'] == 'en']
    other_rows = [(sid, info) for sid, info in subject_data.items() if info['language'] not in ('fr','en')]

    def make_subject_rows(rows_list, lang_label):
        rows = []
        for sid, info in rows_list:
            letter, meaning, stars = get_letter_grade(info['average'])
            rows.append([
                info['subject_name'],
                letter or '—',
                meaning or '—',
                stars or '',
            ])
        return rows

    all_rows = []
    if fr_rows:
        all_rows.append(['FRANÇAIS / FRENCH — ACADÉMIQUES', '', '', ''])
        all_rows.extend(make_subject_rows(fr_rows, 'fr'))
    if en_rows:
        all_rows.append(['ENGLISH / ANGLAIS — ACADEMICS', '', '', ''])
        all_rows.extend(make_subject_rows(en_rows, 'en'))
    if other_rows:
        all_rows.append(['AUTRES MATIÈRES / OTHER SUBJECTS', '', '', ''])
        all_rows.extend(make_subject_rows(other_rows, ''))

    if not all_rows:
        all_rows = [['Aucune matière', '', '', '']]

    header_row = ['MATIÈRE / SUBJECT', 'NOTE / GRADE', 'APPRÉCIATION / COMMENT', 'NIVEAU / LEVEL']
    full_rows = [header_row] + all_rows

    col_widths = [8*cm, 2.5*cm, 5*cm, 2.5*cm]
    g_tbl = Table(full_rows, colWidths=col_widths)
    style_cmds = [
        ('BACKGROUND', (0, 0), (-1, 0), primary),
        ('TEXTCOLOR',  (0, 0), (-1, 0), colors.white),
        ('FONTNAME',   (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE',   (0, 0), (-1,-1), 8),
        ('ALIGN',      (1, 0), (-1,-1), 'CENTER'),
        ('GRID',       (0, 0), (-1,-1), 0.25, colors.lightgrey),
        ('PADDING',    (0, 0), (-1,-1), 4),
    ]
    for i, row in enumerate(full_rows[1:], 1):
        if row[1] == '' and row[2] == '' and row[3] == '':
            style_cmds.append(('BACKGROUND', (0, i), (-1, i), gold))
            style_cmds.append(('TEXTCOLOR',  (0, i), (-1, i), colors.white))
            style_cmds.append(('FONTNAME',   (0, i), (-1, i), 'Helvetica-Bold'))
            style_cmds.append(('SPAN',       (0, i), (-1, i)))
        else:
            bg = colors.white if i % 2 == 0 else colors.HexColor('#F8FAFF')
            style_cmds.append(('BACKGROUND', (0, i), (-1, i), bg))

    g_tbl.setStyle(TableStyle(style_cmds))
    story.append(g_tbl)
    story.append(Spacer(1, 0.4*cm))

    # Conduct section
    story.append(P('CONDUITE / CONDUCT', fontSize=11, fontName='Helvetica-Bold', textColor=primary, spaceAfter=4))
    conduct_items = [
        'Contrôle du langage / Controls talking',
        'Respect de l\'autorité / Respects authority',
        'Maîtrise de soi / Self-control',
        'Suit les consignes / Follows directions',
        'Attitude en classe / Class behavior',
        'Travail de groupe / Group work',
        'Retourne les devoirs / Returns homework',
    ]
    conduct_data = [['Critère / Criterion', 'Note / Grade', 'Commentaire']]
    for item in conduct_items:
        conduct_data.append([item, '—', ''])
    c_tbl = Table(conduct_data, colWidths=[8*cm, 3*cm, 7*cm])
    c_tbl.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), primary),
        ('TEXTCOLOR',  (0,0), (-1,0), colors.white),
        ('FONTNAME',   (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE',   (0,0), (-1,-1), 8),
        ('GRID',       (0,0), (-1,-1), 0.25, colors.lightgrey),
        ('PADDING',    (0,0), (-1,-1), 4),
    ]))
    story.append(c_tbl)
    story.append(Spacer(1, 0.4*cm))

    # Summary + signature
    _add_signatures(story, bulletin, primary, gold)
    _add_footer(story)
    doc.build(story)


# ─── STANDARD PDF Template (Primaire/Collège/Lycée) ──────────────────────────

def _build_standard_pdf(buffer, student, period, school_year, subject_data, bilingual_data, average, bulletin, logo_path):
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        rightMargin=1.5*cm, leftMargin=1.5*cm,
        topMargin=1.5*cm, bottomMargin=1.5*cm,
    )
    story = []
    primary = colors.HexColor('#1E3A6E')
    gold    = colors.HexColor('#C9A227')
    light   = colors.HexColor('#EEF3FF')
    en_bg   = colors.HexColor('#F0FFF4')

    def P(text, **kw):
        return Paragraph(text, ParagraphStyle('_', **kw))

    # Header
    if logo_path and os.path.exists(logo_path):
        try:
            logo_img = Image(logo_path, width=2.5*cm, height=2.5*cm)
            logo_img.hAlign = 'CENTER'
            story.append(logo_img)
        except Exception as exc:
            logger.warning("Erreur non bloquante ignorée : %s", exc, exc_info=True)
    story.append(P('FAITH & EXCELLENCE BILINGUAL ACADEMY', fontSize=14,
                   fontName='Helvetica-Bold', alignment=1, textColor=primary, spaceAfter=2))
    story.append(P('École Bilingue Foi & Excellence — Cotonou, Bénin',
                   fontSize=10, alignment=1, spaceAfter=2))
    story.append(HRFlowable(width='100%', thickness=3, color=gold))
    story.append(P(f'BULLETIN DE NOTES / PROGRESS REPORT — {_period_label(period)}',
                   fontSize=13, fontName='Helvetica-Bold', alignment=1, textColor=gold, spaceBefore=4))
    story.append(P(f'Année scolaire / School Year : {school_year.name}',
                   fontSize=10, alignment=1, spaceAfter=4))
    story.append(Spacer(1, 0.3*cm))

    # Student info
    class_name = student.current_class.name if student.current_class else '—'
    level_name = student.current_class.level.name if student.current_class and student.current_class.level else '—'
    rank_total = str(bulletin.rank_in_class or '—')
    info = [
        ['Nom / Name:', student.get_full_name(), 'Matricule:', student.matricule],
        ['Classe / Class:', class_name, 'Niveau / Level:', level_name],
        ['Rang / Rank:', rank_total, 'Période / Period:', _period_label(period)],
        ['Année / Year:', school_year.name, 'Date de naissance:', str(student.date_of_birth) if student.date_of_birth else '—'],
    ]
    info_tbl = Table(info, colWidths=[4*cm, 6*cm, 4*cm, 4*cm])
    info_tbl.setStyle(TableStyle([
        ('FONTNAME', (0,0), (-1,-1), 'Helvetica'),
        ('FONTNAME', (0,0), (0,-1), 'Helvetica-Bold'),
        ('FONTNAME', (2,0), (2,-1), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,-1), 9),
        ('GRID', (0,0), (-1,-1), 0.25, colors.lightgrey),
        ('BACKGROUND', (0,0), (0,-1), light),
        ('BACKGROUND', (2,0), (2,-1), light),
        ('PADDING', (0,0), (-1,-1), 5),
        ('ROWBACKGROUNDS', (0,0), (-1,-1), [colors.white, colors.HexColor('#F0F4FF')]),
    ]))
    story.append(info_tbl)
    story.append(Spacer(1, 0.4*cm))

    # Results table
    story.append(P('RÉSULTATS / ACADEMIC RESULTS', fontSize=11, fontName='Helvetica-Bold',
                   textColor=primary, spaceAfter=4))

    if period == 'annual':
        rows = _build_annual_rows(subject_data)
        col_widths = [5.5*cm, 1.5*cm, 1.5*cm, 2*cm, 2*cm, 2*cm, 2*cm, 2*cm]
        header = ['Matière', 'Coeff', 'Langue', 'T1', 'T2', 'T3', 'Moy. Ann.', 'Lettre']
    else:
        rows = _build_trimester_rows(subject_data)
        col_widths = [5*cm, 1.5*cm, 1.5*cm, 3.5*cm, 2.5*cm, 2*cm, 2*cm]
        header = ['Matière', 'Coeff', 'Langue', 'Notes', 'Moy. Matière', 'Moy. Pond.', 'Lettre']

    full_rows = [header] + rows

    # Total row
    if period == 'annual':
        full_rows.append(['MOYENNE GÉNÉRALE ANNUELLE', '', '', '', '', '',
                          f'{_fmt(average)}/20', get_letter_grade(average)[0] or '—'])
    else:
        full_rows.append(['MOYENNE GÉNÉRALE', '', '', '', f'{_fmt(average)}/20', '', get_letter_grade(average)[0] or '—'])

    g_tbl = Table(full_rows, colWidths=col_widths)
    style_cmds = [
        ('BACKGROUND', (0, 0), (-1, 0), primary),
        ('TEXTCOLOR',  (0, 0), (-1, 0), colors.white),
        ('FONTNAME',   (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE',   (0, 0), (-1,-1), 8),
        ('ALIGN',      (1, 0), (-1,-1), 'CENTER'),
        ('GRID',       (0, 0), (-1,-1), 0.25, colors.lightgrey),
        ('PADDING',    (0, 0), (-1,-1), 4),
        ('BACKGROUND', (0,-1), (-1,-1), colors.HexColor('#FEF3C7')),
        ('FONTNAME',   (0,-1), (-1,-1), 'Helvetica-Bold'),
    ]
    for i in range(1, len(full_rows) - 1):
        if i % 2 == 0:
            style_cmds.append(('BACKGROUND', (0, i), (-1, i), colors.white))
        else:
            style_cmds.append(('BACKGROUND', (0, i), (-1, i), light))
    g_tbl.setStyle(TableStyle(style_cmds))
    story.append(g_tbl)
    story.append(Spacer(1, 0.4*cm))

    # Bilingual averages section
    story.append(HRFlowable(width='100%', thickness=1, color=gold))
    story.append(P('MOYENNES BILINGUES / BILINGUAL AVERAGES', fontSize=11,
                   fontName='Helvetica-Bold', textColor=primary, spaceBefore=4, spaceAfter=4))

    if period == 'annual':
        bi_rows = _build_bilingual_annual_rows(bilingual_data)
    else:
        bi_rows = _build_bilingual_trimester_rows(bilingual_data, period)

    bi_full = [['Catégorie', 'Moyenne FR', 'Moyenne EN', 'Moyenne Bilingue', 'Lettre', 'Formule']] + bi_rows
    bi_tbl = Table(bi_full, colWidths=[4*cm, 3*cm, 3*cm, 3.5*cm, 2*cm, 2.5*cm])
    bi_tbl.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), gold),
        ('TEXTCOLOR',  (0, 0), (-1, 0), colors.white),
        ('FONTNAME',   (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE',   (0, 0), (-1,-1), 8),
        ('ALIGN',      (1, 0), (-1,-1), 'CENTER'),
        ('GRID',       (0, 0), (-1,-1), 0.25, colors.lightgrey),
        ('PADDING',    (0, 0), (-1,-1), 4),
        ('BACKGROUND', (0, 1), (-1,-2), en_bg),
        ('BACKGROUND', (0,-1), (-1,-1), colors.HexColor('#FFF3CD')),
        ('FONTNAME',   (0,-1), (-1,-1), 'Helvetica-Bold'),
    ]))
    story.append(bi_tbl)

    story.append(Spacer(1, 0.2*cm))
    story.append(P(
        '<font color="#1E3A6E"><b>Formule bilingue / Bilingual formula:</b></font> '
        'Moyenne Bilingue = (Moyenne Française × 40%) + (Moyenne Anglaise × 60%)',
        fontSize=8, spaceAfter=6,
    ))

    story.append(Spacer(1, 0.3*cm))

    # Summary box
    letter, meaning, stars = get_letter_grade(average)
    summary_data = [[
        'Moy. Générale', f'{_fmt(average)}/20',
        'Rang', f'{bulletin.rank_in_class or "—"}',
        'Lettre', f'{letter or "—"}',
        'Appréciation', bulletin.appreciation or '—',
    ]]
    s_tbl = Table(summary_data, colWidths=[3.5*cm, 2.5*cm, 2*cm, 1.5*cm, 2*cm, 1.5*cm, 3*cm, 2.5*cm])
    s_tbl.setStyle(TableStyle([
        ('FONTNAME',   (0, 0), (-1,-1), 'Helvetica-Bold'),
        ('FONTSIZE',   (0, 0), (-1,-1), 9),
        ('BACKGROUND', (0, 0), (-1,-1), light),
        ('GRID',       (0, 0), (-1,-1), 0.5, primary),
        ('TEXTCOLOR',  (1, 0), (1, 0),  primary),
        ('ALIGN',      (0, 0), (-1,-1), 'CENTER'),
        ('PADDING',    (0, 0), (-1,-1), 5),
    ]))
    story.append(s_tbl)
    story.append(Spacer(1, 0.4*cm))

    _add_signatures(story, bulletin, primary, gold)
    _add_footer(story)
    doc.build(story)


# ─── Row Builders ─────────────────────────────────────────────────────────────

def _build_trimester_rows(subject_data):
    note_labels = {'devoir':'D','interrogation':'I','controle':'C','examen':'E','tp':'TP','autre':'A'}
    lang_labels = {'fr':'FR','en':'EN','bilingual':'BI'}
    rows = []
    for info in subject_data.values():
        notes = info['notes']
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
            info['subject_name'],
            str(info['coefficient']),
            lang_labels.get(info.get('language','fr'), 'FR'),
            details,
            f'{_fmt(avg)}/20' if avg is not None else '—',
            f'{weighted:.2f}' if weighted is not None else '—',
            letter or '—',
        ])
    return rows


def _build_annual_rows(subject_data):
    lang_labels = {'fr':'FR','en':'EN','bilingual':'BI'}
    rows = []
    for info in subject_data.values():
        t_avgs = info.get('trimester_avgs', {})
        avg = info['average']
        letter, _, _ = get_letter_grade(avg)
        rows.append([
            info['subject_name'],
            str(info['coefficient']),
            lang_labels.get(info.get('language','fr'), 'FR'),
            _fmt(t_avgs.get('T1')),
            _fmt(t_avgs.get('T2')),
            _fmt(t_avgs.get('T3')),
            f'{_fmt(avg)}/20',
            letter or '—',
        ])
    return rows


def _build_bilingual_trimester_rows(bilingual_data, period):
    fr_avg = bilingual_data.get('fr_average')
    en_avg = bilingual_data.get('en_average')
    bi_avg = bilingual_data.get('bilingual_average')
    fr_letter, _, _ = get_letter_grade(fr_avg)
    en_letter, _, _ = get_letter_grade(en_avg)
    bi_letter, _, _ = get_letter_grade(bi_avg)
    rows = [
        [f'Français ({period})', _fmt(fr_avg), '—', '—', fr_letter or '—', ''],
        [f'Anglais ({period})', '—', _fmt(en_avg), '—', en_letter or '—', ''],
        [f'Bilingue ({period}) ★', _fmt(fr_avg), _fmt(en_avg), _fmt(bi_avg), bi_letter or '—', 'FR×40%+EN×60%'],
    ]
    return rows


def _build_bilingual_annual_rows(bilingual_data):
    rows = []
    for t in ['T1', 'T2', 'T3']:
        td = bilingual_data.get(t, {})
        fr = td.get('fr_average')
        en = td.get('en_average')
        bi = td.get('bilingual_average')
        bi_letter, _, _ = get_letter_grade(bi)
        rows.append([f'Bilingue {t}', _fmt(fr), _fmt(en), _fmt(bi), bi_letter or '—', 'FR×40%+EN×60%'])
    # Annual
    ann = bilingual_data.get('annual', {})
    fr_a = ann.get('fr_average')
    en_a = ann.get('en_average')
    bi_a = ann.get('bilingual_average')
    bi_letter_a, _, _ = get_letter_grade(bi_a)
    rows.append(['Bilingue ANNUELLE ★', _fmt(fr_a), _fmt(en_a), _fmt(bi_a), bi_letter_a or '—', 'Moy. Trimestrielles'])
    return rows


def _add_signatures(story, bulletin, primary, gold):
    def P(text, **kw):
        return Paragraph(text, ParagraphStyle('_', **kw))

    story.append(HRFlowable(width='100%', thickness=1, color=colors.lightgrey))
    story.append(Spacer(1, 0.3*cm))
    sig_data = [
        ['Commentaire du Directeur / Principal\'s Comment', '', 'Signature & Cachet / Stamp'],
        [bulletin.general_comment or '(Aucun commentaire / No comment)', '', ''],
        ['', '', ''],
        ['', '', '________________________'],
        ['', '', f'Cotonou, le {timezone.now().strftime("%d/%m/%Y")}'],
    ]
    sig_tbl = Table(sig_data, colWidths=[9*cm, 1*cm, 8*cm])
    sig_tbl.setStyle(TableStyle([
        ('FONTNAME',    (0, 0), (-1,  0), 'Helvetica-Bold'),
        ('FONTSIZE',    (0, 0), (-1, -1), 8),
        ('VALIGN',      (0, 0), (-1, -1), 'TOP'),
        ('GRID',        (0, 0), (0, -1),  0.25, colors.lightgrey),
        ('ALIGN',       (2, 0), (2, -1),  'CENTER'),
        ('TOPPADDING',  (2, 3), (2,  3),  10),
    ]))
    story.append(sig_tbl)
    # Parent signature
    story.append(Spacer(1, 0.3*cm))
    parent_sig = Table(
        [['Signature du Parent / Parent\'s Signature:', '', '________________________']],
        colWidths=[7*cm, 4*cm, 7*cm]
    )
    parent_sig.setStyle(TableStyle([
        ('FONTNAME', (0,0), (-1,-1), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,-1), 8),
        ('ALIGN',    (2,0), (2,0),   'CENTER'),
    ]))
    story.append(parent_sig)


def _add_footer(story):
    def P(text, **kw):
        return Paragraph(text, ParagraphStyle('_', **kw))
    story.append(Spacer(1, 0.2*cm))
    story.append(HRFlowable(width='100%', thickness=1, color=colors.lightgrey))
    story.append(P(
        f'FEBA School Management System | Faith & Excellence Bilingual Academy | '
        f'Généré le {timezone.now().strftime("%d/%m/%Y à %H:%M")}',
        fontSize=6, alignment=1, textColor=colors.grey,
    ))
