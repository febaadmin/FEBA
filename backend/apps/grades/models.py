"""
Grade model — v18 FEBA Bilingual
Corrections critiques :
  1. Système bilingue : Moy FR × 60% + Moy EN × 40% = Moy Bilingue
  2. Système de lettres : A+/A/A-/B+/B/B-/C+/C/C-/D+/D/D-/F
  3. Calcul annuel correct : (T1+T2+T3) / nb_trimestres
  4. Matières maternelle : notation en lettres uniquement
  5. Zéro régression sur logique existante
"""
from decimal import Decimal
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from apps.students.models import Student
from apps.subjects.models import Subject
from apps.schools.models import SchoolYear


# ─── Letter Grade System ──────────────────────────────────────────────────────

LETTER_GRADES = [
    (Decimal('19.5'), 'A+', 'Exceptionnel',  '⭐⭐⭐⭐⭐'),
    (Decimal('18.0'), 'A',  'Excellent',      '⭐⭐⭐⭐⭐'),
    (Decimal('16.0'), 'A-', 'Très bon',       '⭐⭐⭐⭐'),
    (Decimal('15.0'), 'B+', 'Bon',            '⭐⭐⭐⭐'),
    (Decimal('13.0'), 'B',  'Bon',            '⭐⭐⭐'),
    (Decimal('12.0'), 'B-', 'Assez bon',      '⭐⭐⭐'),
    (Decimal('11.0'), 'C+', 'Correct',        '⭐⭐'),
    (Decimal('10.0'), 'C',  'Moyen',          '⭐⭐'),
    (Decimal('9.0'),  'C-', 'Suffisant',      '⭐'),
    (Decimal('8.0'),  'D+', 'Faible',         '⭐'),
    (Decimal('6.0'),  'D',  'Faible',         '⚠️'),
    (Decimal('4.0'),  'D-', 'Très faible',    '⚠️'),
    (Decimal('0'),    'F',  'Échec',          '❌'),
]


def get_letter_grade(value):
    """Return (letter, meaning, stars) for a numeric grade /20."""
    if value is None:
        return None, None, None
    v = Decimal(str(value))
    for threshold, letter, meaning, stars in LETTER_GRADES:
        if v >= threshold:
            return letter, meaning, stars
    return 'F', 'Échec', '❌'


# ─── Barème officiel des appréciations (source unique de vérité) ─────────────
# Seuils inclusifs bas : une note n de [seuil, seuil_supérieur[ reçoit le
# libellé du seuil. 19 → EXCELLENT, 18,99 → TRÈS SATISFAISANT, etc.
# Toute autre logique (bulletins, exports, dashboards, API) DOIT passer par
# get_appreciation() — ne pas dupliquer ces seuils ailleurs.
APPRECIATION_SCALE = [
    (Decimal('19'), 'EXCELLENT'),
    (Decimal('17'), 'TRÈS SATISFAISANT'),
    (Decimal('15'), 'SATISFAISANT'),
    (Decimal('13'), 'ACCEPTABLE'),
    (Decimal('11'), 'PEUT MIEUX FAIRE'),
    (Decimal('9'),  'INSUFFISANT'),
    (Decimal('7'),  'TRÈS INSUFFISANT'),
    (Decimal('4'),  'FAIBLE'),
    (Decimal('0'),  'TRÈS FAIBLE'),
]


def get_appreciation(value, max_value=20):
    """
    Appréciation officielle d'une note.

    value      : note obtenue (None → '—', l'absence de note n'est pas une erreur)
    max_value  : barème de la note (20 par défaut) ; toute note sur un autre
                 barème est normalisée sur 20 avant classification :
                 note_normalisée = note / barème × 20 (ex. 45/50 → 18 → TRÈS SATISFAISANT)

    Une valeur non numérique, un barème nul/négatif ou une note hors
    [0, barème] lèvent ValueError : les données invalides doivent être
    rejetées par la validation, jamais converties en appréciation trompeuse.
    """
    if value is None:
        return '—'
    from decimal import InvalidOperation
    try:
        v = Decimal(str(value))
        m = Decimal(str(max_value))
    except (InvalidOperation, ValueError, TypeError):
        raise ValueError(f'Note ou barème non numérique : {value!r} / {max_value!r}')
    if m <= 0:
        raise ValueError(f'Barème invalide : {max_value!r} (doit être strictement positif)')
    if v < 0:
        raise ValueError(f'Note négative : {value!r}')
    if v > m:
        raise ValueError(f'Note {value!r} supérieure au barème {max_value!r}')
    normalized = v if m == 20 else v / m * Decimal('20')
    for threshold, label in APPRECIATION_SCALE:
        if normalized >= threshold:
            return label
    return 'TRÈS FAIBLE'


# ─── Grade Model ─────────────────────────────────────────────────────────────

class Grade(models.Model):
    PERIOD_CHOICES = [
        ('T1',   'Trimestre 1'),
        ('T2',   'Trimestre 2'),
        ('T3',   'Trimestre 3'),
        ('exam', 'Examen'),
    ]
    # Les valeurs internes ('interrogation', 'examen', …) sont des identifiants
    # métier STABLES stockés en base — ne jamais les renommer, seuls les
    # libellés affichés changent (compatibilité des données existantes).
    NOTE_TYPE_CHOICES = [
        ('devoir',        'Devoir'),
        ('interrogation', 'Interrogation / Devoir de classe'),
        ('controle',      'Contrôle'),
        ('examen',        'Examen / Évaluation'),
        ('tp',            'Travaux Pratiques'),
        ('autre',         'Autre'),
    ]

    student     = models.ForeignKey(Student,    on_delete=models.CASCADE, related_name='grades')
    subject     = models.ForeignKey(Subject,    on_delete=models.CASCADE, related_name='grades')
    teacher     = models.ForeignKey(
        'teachers.Teacher', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='grades_given',
    )
    school_year = models.ForeignKey(SchoolYear, on_delete=models.CASCADE, related_name='grades')
    # Rattachement à l'inscription annuelle de l'élève (StudentEnrollment).
    # Nullable pour compatibilité avec les notes déjà existantes avant la
    # migration de backfill ; toute nouvelle note créée via l'API passe
    # désormais systématiquement par get_or_create_enrollment().
    enrollment = models.ForeignKey(
        'students.StudentEnrollment', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='grades',
        help_text="Inscription annuelle de l'élève correspondant à cette note (cohérence élève ↔ classe ↔ année).",
    )
    period      = models.CharField(max_length=5, choices=PERIOD_CHOICES)
    value       = models.DecimalField(
        max_digits=4, decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(20)],
    )
    note_type = models.CharField(max_length=20, choices=NOTE_TYPE_CHOICES, default='devoir')
    note_coefficient = models.PositiveSmallIntegerField(
        default=1, validators=[MinValueValidator(1)],
    )
    comment    = models.TextField(blank=True)
    graded_at  = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)
    deleted_by = models.ForeignKey(
        'accounts.CustomUser', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='deleted_grades',
    )

    class Meta:
        verbose_name = 'Note'
        ordering = ['-created_at']

    def __str__(self):
        return (
            f'{self.student} - {self.subject} - {self.period} '
            f'[{self.get_note_type_display()}] : {self.value}/20'
        )

    @property
    def letter(self):
        letter, _, _ = get_letter_grade(self.value)
        return letter

    # ──────────────────────────────────────────────────────────────────────────
    # Core Calculation Methods
    # ──────────────────────────────────────────────────────────────────────────

    @classmethod
    def _class_for_year(cls, student, school_year):
        """
        FIX v33 : classe de l'élève POUR L'ANNÉE DEMANDÉE.
        Priorité : classe de l'inscription de cette année → repli sur
        current_class. Avant, tout reposait sur current_class : consulter
        une année passée, ou un élève promu « sans classe », cassait le
        Résumé par élève et le calcul Bilingue (« Vérifiez que cet élève
        a une classe... »).
        """
        if school_year is not None and getattr(student, 'pk', None):
            enrollment = student.get_enrollment_for_year(school_year)
            if enrollment and enrollment.class_obj_id:
                return enrollment.class_obj
        return student.current_class

    @classmethod
    def get_subject_averages(cls, student, school_year, period):
        """
        Returns {subject_id: {...}} for all subjects of the student's class.
        Priority: class.subjects (M2M) > level subjects > school subjects > grades fallback.
        FIX v28: uses Class.subjects M2M for bilingual correctness.
        FIX v33: the class is resolved for the REQUESTED year (enrollment).
        """
        subjects = []
        student_class = cls._class_for_year(student, school_year)

        # 1. BEST: matières directement assignées à la classe (M2M)
        if student_class:
            class_subjects = student_class.subjects.all()
            if class_subjects.exists():
                subjects = list(class_subjects)

        # 2. Fallback: subjects for the student's class level
        if not subjects and student_class and student_class.level_id:
            subjects = list(Subject.objects.filter(level_id=student_class.level_id))

        # 3. Fallback: subjects for the school
        if not subjects:
            school_id = None
            if school_year and hasattr(school_year, 'school_id') and school_year.school_id:
                school_id = school_year.school_id
            elif student.school_year and hasattr(student.school_year, 'school_id'):
                school_id = student.school_year.school_id
            if school_id:
                subjects = list(Subject.objects.filter(school_id=school_id))

        # 4. Last resort: any subject that actually has a grade for this student/year/period
        if not subjects:
            subject_ids = cls.objects.filter(
                student=student, school_year=school_year,
                period=period, is_deleted=False
            ).values_list('subject_id', flat=True).distinct()
            subjects = list(Subject.objects.filter(id__in=subject_ids))

        if not subjects:
            return {}

        notes_qs = cls.objects.filter(
            student=student, school_year=school_year,
            period=period, is_deleted=False,
        ).select_related('subject')

        notes_by_subject = {}
        for note in notes_qs:
            notes_by_subject.setdefault(note.subject_id, []).append(note)

        result = {}
        for subj in subjects:
            sid   = subj.id
            notes = notes_by_subject.get(sid, [])

            # FIX v32 (règle métier) : une matière SANS note n'a pas de
            # moyenne — elle vaut None et est EXCLUE de la moyenne générale.
            # L'ancien comportement (0 d'office) écrasait injustement la
            # moyenne des élèves dès qu'une matière n'était pas encore notée.
            if notes:
                total_w = sum(note.value * Decimal(note.note_coefficient) for note in notes)
                total_c = sum(Decimal(note.note_coefficient) for note in notes)
                avg = total_w / total_c if total_c else None
            else:
                avg = None

            if avg is not None:
                letter, meaning, stars = get_letter_grade(avg)
            else:
                letter, meaning, stars = '—', 'Non noté', 0
            result[sid] = {
                'subject_id':   sid,
                'subject_name': subj.name,
                'coefficient':  subj.coefficient,
                'language':     subj.language,
                'average':      round(avg, 2) if avg is not None else None,
                'letter':       letter,
                'meaning':      meaning,
                'stars':        stars,
                'notes':        notes,
                'has_notes':    bool(notes),
            }
        return result

    @classmethod
    def get_annual_subject_averages(cls, student, school_year):
        """
        Moyenne annuelle PAR MATIÈRE = moyenne des moyennes trimestrielles de
        cette matière (même convention que calculate_annual_average() et
        get_annual_bilingual() : moyenne des trimestres effectivement notés,
        pas un recalcul pondéré sur l'ensemble des notes brutes).

        NE PAS appeler get_subject_averages(student, school_year, period=None) :
        les notes ont toujours un period='T1'/'T2'/'T3' réel, jamais None —
        period=None ne retourne donc jamais aucune note.
        """
        per_period = {t: cls.get_subject_averages(student, school_year, t) for t in ('T1', 'T2', 'T3')}

        # Union des matières apparues dans au moins un trimestre.
        all_subjects = {}
        for t, subj_map in per_period.items():
            for sid, info in subj_map.items():
                all_subjects.setdefault(sid, info)

        result = {}
        for sid, base_info in all_subjects.items():
            period_avgs = [
                per_period[t][sid]['average']
                for t in ('T1', 'T2', 'T3')
                if sid in per_period[t] and per_period[t][sid]['average'] is not None
            ]
            avg = round(sum(period_avgs) / len(period_avgs), 2) if period_avgs else None
            result[sid] = {
                'subject_id':   base_info['subject_id'],
                'subject_name': base_info['subject_name'],
                'coefficient':  base_info['coefficient'],
                'language':     base_info['language'],
                'average':      avg,
                'has_notes':    bool(period_avgs),
            }
        return result

    @classmethod
    def calculate_average(cls, student, school_year, period=None):
        """
        Moyenne générale pondérée par coefficient matière.
        period='annual' → délégué à calculate_annual_average().

        FIX (moyennes Parent absentes) : le champ Grade.period n'est JAMAIS
        NULL en base (CharField à choix obligatoire : 'T1'/'T2'/'T3'). Un
        appel avec period=None ou period='' déléguait donc à
        get_subject_averages(..., period=None), qui filtrait sur
        period=None et ne correspondait à AUCUNE note réelle → la moyenne
        renvoyée était toujours None. C'est exactement le cas de la page
        Parent (filtre par défaut « Toutes périodes » → period='' côté
        frontend → aucun paramètre `period` envoyé à l'API).
        « Aucune période précisée » doit avoir le même sens que « Annuel »
        (déjà le comportement de get_annual_bilingual/bilingual_averages_view
        pour la moyenne bilingue) : on délègue donc aussi à
        calculate_annual_average() dans ce cas, pour que les 4 cartes
        (générale, française, anglaise, bilingue) restent cohérentes entre
        elles quelle que soit la période sélectionnée.
        """
        if not period or period == 'annual':
            return cls.calculate_annual_average(student, school_year)

        subject_avgs = cls.get_subject_averages(student, school_year, period)
        # FIX v32 : seules les matières effectivement notées entrent dans la
        # moyenne générale (les matières sans note ont average=None).
        graded = [info for info in subject_avgs.values() if info['average'] is not None]
        if not graded:
            return None

        total_w = sum(
            info['average'] * Decimal(info['coefficient'])
            for info in graded
        )
        total_c = sum(Decimal(info['coefficient']) for info in graded)
        if not total_c:
            return None
        return round(total_w / total_c, 2)

    @classmethod
    def calculate_annual_average(cls, student, school_year):
        """Moyenne annuelle = (moy_T1 + moy_T2 + moy_T3) / nb_trimestres_avec_données."""
        trimesters = ['T1', 'T2', 'T3']
        avgs = []
        for t in trimesters:
            avg = cls.calculate_average(student, school_year, t)
            if avg is not None:
                avgs.append(avg)
        if not avgs:
            return None
        return round(sum(avgs) / Decimal(len(avgs)), 2)

    # ──────────────────────────────────────────────────────────────────────────
    # Bilingual Calculation — FR × 60% + EN × 40%
    # ──────────────────────────────────────────────────────────────────────────

    # Pondérations OFFICIELLES de la moyenne bilingue (BUG N°6) :
    # Moyenne Bilingue = (Moyenne Française × 60%) + (Moyenne Anglaise × 40%)
    BILINGUAL_FR_WEIGHT = Decimal('0.6')
    BILINGUAL_EN_WEIGHT = Decimal('0.4')
    BILINGUAL_FORMULA = 'Bilingue = (Moyenne FR × 60%) + (Moyenne EN × 40%)'

    @classmethod
    def calculate_bilingual_averages(cls, student, school_year, period):
        """
        Retourne {
            'fr_average': ...,
            'en_average': ...,
            'bilingual_average': fr*0.6 + en*0.4,
            'fr_subjects': [...],
            'en_subjects': [...],
            'has_fr_subjects': bool,
            'has_en_subjects': bool,
        }
        FIX v28: filtre strictement sur les matières de la classe.
        Ne génère plus de faux message d'erreur quand une catégorie est absente.
        """
        subject_avgs = cls.get_subject_averages(student, school_year, period)

        # Filtre strict: uniquement les matières de la classe, par langue
        fr_subjects = {sid: info for sid, info in subject_avgs.items() if info['language'] == 'fr'}
        en_subjects = {sid: info for sid, info in subject_avgs.items() if info['language'] == 'en'}

        def weighted_avg(subjects_dict):
            # FIX v32 : ignore les matières sans note (average=None)
            graded = [info for info in subjects_dict.values() if info['average'] is not None]
            if not graded:
                return None
            total_w = sum(info['average'] * Decimal(info['coefficient']) for info in graded)
            total_c = sum(Decimal(info['coefficient']) for info in graded)
            return round(total_w / total_c, 2) if total_c else None

        fr_avg = weighted_avg(fr_subjects)
        en_avg = weighted_avg(en_subjects)

        if fr_avg is not None and en_avg is not None:
            bilingual = round(
                fr_avg * cls.BILINGUAL_FR_WEIGHT + en_avg * cls.BILINGUAL_EN_WEIGHT, 2
            )
        elif fr_avg is not None:
            bilingual = fr_avg
        elif en_avg is not None:
            bilingual = en_avg
        else:
            bilingual = None

        return {
            'fr_average': fr_avg,
            'en_average': en_avg,
            'bilingual_average': bilingual,
            'fr_subjects': list(fr_subjects.values()),
            'en_subjects': list(en_subjects.values()),
            'has_fr_subjects': bool(fr_subjects),
            'has_en_subjects': bool(en_subjects),
            'formula': cls.BILINGUAL_FORMULA,
        }

    @classmethod
    def get_annual_bilingual(cls, student, school_year):
        """Calcul bilingue annuel : moyenne des trimestres par groupe de langue."""
        result = {'T1': {}, 'T2': {}, 'T3': {}, 'annual': {}}
        for t in ['T1', 'T2', 'T3']:
            result[t] = cls.calculate_bilingual_averages(student, school_year, t)

        # Annual bilingual
        fr_avgs = [result[t]['fr_average'] for t in ['T1','T2','T3'] if result[t]['fr_average'] is not None]
        en_avgs = [result[t]['en_average'] for t in ['T1','T2','T3'] if result[t]['en_average'] is not None]
        bi_avgs = [result[t]['bilingual_average'] for t in ['T1','T2','T3'] if result[t]['bilingual_average'] is not None]

        fr_annual = round(sum(fr_avgs) / len(fr_avgs), 2) if fr_avgs else None
        en_annual = round(sum(en_avgs) / len(en_avgs), 2) if en_avgs else None
        bi_annual = round(sum(bi_avgs) / len(bi_avgs), 2) if bi_avgs else None

        result['annual'] = {
            'fr_average': fr_annual,
            'en_average': en_annual,
            'bilingual_average': bi_annual,
            'formula': 'Bilingue Annuelle = Moyenne des moyennes bilingues trimestrielles',
        }
        return result

    @classmethod
    def get_class_bilingual_stats(cls, student_class, school_year, period):
        """
        Statistiques de classe pour le bulletin (BUG N°2) : moyennes
        minimales et maximales de la classe — FR, EN, bilingue et générale.
        Calculées dynamiquement à partir des résultats réels de TOUS les
        élèves actifs de la classe (aucune valeur codée en dur).
        period='annual' agrège les trimestres comme get_annual_bilingual().
        """
        from apps.students.models import Student

        if student_class is None or school_year is None:
            return {
                'students_count': 0, 'graded_count': 0,
                'fr_min': None, 'fr_max': None,
                'en_min': None, 'en_max': None,
                'bi_min': None, 'bi_max': None,
                'general_min': None, 'general_max': None,
            }

        # Élèves de la classe POUR CETTE ANNÉE (inscriptions annuelles),
        # avec repli sur le pointeur current_class.
        students = list(Student.objects.filter(
            enrollments__school_year=school_year,
            enrollments__class_obj=student_class,
            is_active=True,
        ).distinct()) or list(student_class.students.filter(is_active=True))

        fr_list, en_list, bi_list, gen_list = [], [], [], []
        for s in students:
            if period == 'annual':
                data = cls.get_annual_bilingual(s, school_year)['annual']
                gen = cls.calculate_annual_average(s, school_year)
            else:
                data = cls.calculate_bilingual_averages(s, school_year, period)
                gen = cls.calculate_average(s, school_year, period)
            if data['fr_average'] is not None:
                fr_list.append(data['fr_average'])
            if data['en_average'] is not None:
                en_list.append(data['en_average'])
            if data['bilingual_average'] is not None:
                bi_list.append(data['bilingual_average'])
            if gen is not None:
                gen_list.append(gen)

        def _min_max(values):
            return (min(values), max(values)) if values else (None, None)

        fr_min, fr_max = _min_max(fr_list)
        en_min, en_max = _min_max(en_list)
        bi_min, bi_max = _min_max(bi_list)
        gen_min, gen_max = _min_max(gen_list)

        return {
            'students_count': len(students),
            'graded_count': len(gen_list),
            'fr_min': fr_min, 'fr_max': fr_max,
            'en_min': en_min, 'en_max': en_max,
            'bi_min': bi_min, 'bi_max': bi_max,
            'general_min': gen_min, 'general_max': gen_max,
        }


class GradeHistory(models.Model):
    grade         = models.ForeignKey(Grade, on_delete=models.CASCADE, related_name='history')
    changed_by    = models.ForeignKey('accounts.CustomUser', on_delete=models.SET_NULL, null=True)
    old_value     = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)
    new_value     = models.DecimalField(max_digits=4, decimal_places=2)
    old_comment   = models.TextField(blank=True)
    new_comment   = models.TextField(blank=True)
    justification = models.TextField(blank=True)
    action        = models.CharField(
        max_length=10,
        choices=[('create', 'Création'), ('update', 'Modification')],
        default='create',
    )
    changed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Historique note'
        ordering = ['-changed_at']

    def __str__(self):
        return f'{self.grade} — {self.action} par {self.changed_by} le {self.changed_at}'
