"""
bulletins/migrations/0003_bulletin_enrollment.py — VERSION IDEMPOTENTE (v29.1)
"""
from django.db import migrations, models
import django.db.models.deletion


def backfill_bulletin_enrollment(apps, schema_editor):
    """Idempotent : ne lie que les enregistrements sans enrollment."""
    Bulletin = apps.get_model('bulletins', 'Bulletin')
    StudentEnrollment = apps.get_model('students', 'StudentEnrollment')

    pairs = Bulletin.objects.exclude(school_year__isnull=True).filter(
        enrollment__isnull=True
    ).values_list('student_id', 'school_year_id').distinct()

    cache = {}
    for student_id, school_year_id in pairs:
        key = (student_id, school_year_id)
        if key not in cache:
            enrollment, _ = StudentEnrollment.objects.get_or_create(
                student_id=student_id,
                school_year_id=school_year_id,
            )
            cache[key] = enrollment.id
        Bulletin.objects.filter(
            student_id=student_id,
            school_year_id=school_year_id,
            enrollment__isnull=True,
        ).update(enrollment_id=cache[key])


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    atomic = False  # ADD COLUMN IF NOT EXISTS

    dependencies = [
        ('bulletins', '0002_remove_bulletin_unique_bulletin_alter_bulletin_id_and_more'),
        ('students', '0004_tenant_and_exit_fields'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql="""
                        ALTER TABLE bulletins_bulletin
                            ADD COLUMN IF NOT EXISTS enrollment_id INTEGER
                                REFERENCES students_studentenrollment(id)
                                ON DELETE SET NULL
                                DEFERRABLE INITIALLY DEFERRED;
                        CREATE INDEX IF NOT EXISTS bulletins_bulletin_enrollment_id_idx
                            ON bulletins_bulletin (enrollment_id);
                    """,
                    reverse_sql="""
                        ALTER TABLE bulletins_bulletin
                            DROP COLUMN IF EXISTS enrollment_id;
                    """,
                ),
            ],
            state_operations=[
                migrations.AddField(
                    model_name='bulletin',
                    name='enrollment',
                    field=models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='bulletins',
                        to='students.studentenrollment',
                        help_text=(
                            "Inscription annuelle de l'élève correspondant à "
                            "cet enregistrement (cohérence élève ↔ classe ↔ année)."
                        ),
                    ),
                ),
            ],
        ),
        migrations.RunPython(backfill_bulletin_enrollment, noop_reverse),
    ]
