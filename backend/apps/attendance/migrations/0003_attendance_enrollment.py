"""
attendance/migrations/0003_attendance_enrollment.py — VERSION IDEMPOTENTE (v29.1)
"""
from django.db import migrations, models
import django.db.models.deletion


def backfill_attendance_enrollment(apps, schema_editor):
    """Idempotent : ne lie que les enregistrements sans enrollment."""
    Attendance = apps.get_model('attendance', 'Attendance')
    StudentEnrollment = apps.get_model('students', 'StudentEnrollment')

    pairs = Attendance.objects.exclude(school_year__isnull=True).filter(
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
        Attendance.objects.filter(
            student_id=student_id,
            school_year_id=school_year_id,
            enrollment__isnull=True,
        ).update(enrollment_id=cache[key])


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    atomic = False  # ADD COLUMN IF NOT EXISTS

    dependencies = [
        ('attendance', '0002_attendance_justification_file'),
        ('students', '0004_tenant_and_exit_fields'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql="""
                        ALTER TABLE attendance_attendance
                            ADD COLUMN IF NOT EXISTS enrollment_id INTEGER
                                REFERENCES students_studentenrollment(id)
                                ON DELETE SET NULL
                                DEFERRABLE INITIALLY DEFERRED;
                        CREATE INDEX IF NOT EXISTS attendance_attendance_enrollment_id_idx
                            ON attendance_attendance (enrollment_id);
                    """,
                    reverse_sql="""
                        ALTER TABLE attendance_attendance
                            DROP COLUMN IF EXISTS enrollment_id;
                    """,
                ),
            ],
            state_operations=[
                migrations.AddField(
                    model_name='attendance',
                    name='enrollment',
                    field=models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='attendance_records',
                        to='students.studentenrollment',
                        help_text=(
                            "Inscription annuelle de l'élève correspondant à "
                            "cet enregistrement (cohérence élève ↔ classe ↔ année)."
                        ),
                    ),
                ),
            ],
        ),
        migrations.RunPython(backfill_attendance_enrollment, noop_reverse),
    ]
