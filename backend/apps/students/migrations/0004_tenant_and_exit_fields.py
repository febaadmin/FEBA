"""
students/migrations/0004_tenant_and_exit_fields.py — VERSION IDEMPOTENTE (v29.1)

Réécriture idempotente (atomic=False + IF NOT EXISTS) pour éviter les
DuplicateColumn / DuplicateTable sur un relancement après interruption.
"""
from apps.core.migration_utils import portable_schema_change
from django.db import migrations, models
import django.db.models.deletion


def backfill_student_school(apps, schema_editor):
    """
    Idempotent : ne touche que les étudiants sans école.
    """
    Student = apps.get_model('students', 'Student')
    School = apps.get_model('schools', 'School')
    fallback_school = School.objects.first()

    qs = Student.objects.select_related('school_year').filter(school__isnull=True)
    for student in qs:
        if student.school_year_id and student.school_year.school_id:
            student.school_id = student.school_year.school_id
        elif fallback_school is not None:
            student.school_id = fallback_school.id
        student.save(update_fields=['school'])


def noop_reverse(apps, schema_editor):
    pass


PROMOTION_CHOICES = [
    ('normal', 'Passage normal'),
    ('honor', 'Passage avec mention'),
    ('repeat', 'Redoublement'),
    ('transfer', 'Transfert (changement de filière/classe)'),
    ('new', 'Nouvelle inscription'),
    ('graduated', 'Diplômé / fin de cycle'),
    ('excluded', 'Exclu'),
    ('withdrawn', 'Retiré (départ établissement)'),
]

EXIT_REASON_CHOICES = [
    ('', '—'),
    ('graduated', 'Diplômé / fin de cycle'),
    ('transferred_out', 'Transféré vers un autre établissement'),
    ('excluded', 'Exclu'),
    ('withdrawn', 'Retiré par la famille / déménagement'),
]


class Migration(migrations.Migration):
    atomic = False  # IF NOT EXISTS

    dependencies = [
        ('students', '0003_enrollment_note_helptext'),
        ('schools', '0006_school_tenant_fields'),
    ]

    operations = [
        # ── 1. Retirer l'unicité globale du matricule ───────────────────────
        portable_schema_change(
            # DROP CONSTRAINT IF EXISTS est idempotent
                    sql="""
                        DO $$
                        BEGIN
                            IF EXISTS (
                                SELECT 1 FROM pg_constraint
                                WHERE conname = 'students_student_matricule_key'
                                  AND conrelid = 'students_student'::regclass
                            ) THEN
                                ALTER TABLE students_student
                                    DROP CONSTRAINT students_student_matricule_key;
                            END IF;
                        END $$;
                    """,
                    reverse_sql=migrations.RunSQL.noop,
            state_operations=[
                migrations.AlterField(
                    model_name='student',
                    name='matricule',
                    field=models.CharField(max_length=20, blank=True),
                ),
            ],
        ),

        # ── 2. Colonnes nouvelles (IF NOT EXISTS) ───────────────────────────
        portable_schema_change(
            sql="""
                        ALTER TABLE students_student
                            ADD COLUMN IF NOT EXISTS school_id INTEGER
                                REFERENCES schools_school(id)
                                ON DELETE RESTRICT
                                DEFERRABLE INITIALLY DEFERRED,
                            ADD COLUMN IF NOT EXISTS exit_reason VARCHAR(20) NOT NULL DEFAULT '',
                            ADD COLUMN IF NOT EXISTS exit_date   DATE DEFAULT NULL,
                            ADD COLUMN IF NOT EXISTS exit_notes  TEXT NOT NULL DEFAULT '';
                        CREATE INDEX IF NOT EXISTS students_student_school_id_idx
                            ON students_student (school_id);
                    """,
                    reverse_sql="""
                        ALTER TABLE students_student
                            DROP COLUMN IF EXISTS school_id,
                            DROP COLUMN IF EXISTS exit_reason,
                            DROP COLUMN IF EXISTS exit_date,
                            DROP COLUMN IF EXISTS exit_notes;
                    """,
            state_operations=[
                migrations.AddField(
                    model_name='student',
                    name='school',
                    field=models.ForeignKey(
                        blank=True, null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name='students', to='schools.school',
                    ),
                ),
                migrations.AddField(
                    model_name='student',
                    name='exit_reason',
                    field=models.CharField(
                        max_length=20, blank=True, default='',
                        choices=EXIT_REASON_CHOICES,
                    ),
                ),
                migrations.AddField(
                    model_name='student',
                    name='exit_date',
                    field=models.DateField(null=True, blank=True),
                ),
                migrations.AddField(
                    model_name='student',
                    name='exit_notes',
                    field=models.TextField(blank=True, default=''),
                ),
            ],
        ),

        # ── 3. Backfill tenant (idempotent) ─────────────────────────────────
        migrations.RunPython(backfill_student_school, noop_reverse),

        # ── 4. Contrainte unique (school, matricule) ─────────────────────────
        portable_schema_change(
            sql="""
                        DO $$
                        BEGIN
                            IF NOT EXISTS (
                                SELECT 1 FROM pg_constraint
                                WHERE conname = 'unique_matricule_per_school'
                            ) THEN
                                ALTER TABLE students_student
                                    ADD CONSTRAINT unique_matricule_per_school
                                    UNIQUE (school_id, matricule);
                            END IF;
                        END $$;
                    """,
                    reverse_sql="""
                        ALTER TABLE students_student
                            DROP CONSTRAINT IF EXISTS unique_matricule_per_school;
                    """,
            state_operations=[
                migrations.AddConstraint(
                    model_name='student',
                    constraint=models.UniqueConstraint(
                        fields=['school', 'matricule'],
                        name='unique_matricule_per_school',
                    ),
                ),
            ],
        ),

        # ── 5. Nouveaux statuts sur StudentEnrollment ────────────────────────
        migrations.AlterField(
            model_name='studentenrollment',
            name='promotion_status',
            field=models.CharField(
                max_length=20,
                default='new',
                choices=PROMOTION_CHOICES,
            ),
        ),
    ]
