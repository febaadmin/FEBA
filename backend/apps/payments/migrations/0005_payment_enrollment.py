"""
payments/migrations/0005_payment_enrollment.py — VERSION IDEMPOTENTE (v29.1)
"""
from apps.core.migration_utils import portable_schema_change
from django.db import migrations, models
import django.db.models.deletion


def backfill_payment_enrollment(apps, schema_editor):
    """Idempotent : ne lie que les enregistrements sans enrollment."""
    Payment = apps.get_model('payments', 'Payment')
    StudentEnrollment = apps.get_model('students', 'StudentEnrollment')

    pairs = Payment.objects.exclude(school_year__isnull=True).filter(
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
        Payment.objects.filter(
            student_id=student_id,
            school_year_id=school_year_id,
            enrollment__isnull=True,
        ).update(enrollment_id=cache[key])


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    atomic = False  # ADD COLUMN IF NOT EXISTS

    dependencies = [
        ('payments', '0004_alter_payment_options_alter_payment_school_year'),
        ('students', '0004_tenant_and_exit_fields'),
    ]

    operations = [
        portable_schema_change(
            sql="""
                        ALTER TABLE payments_payment
                            ADD COLUMN IF NOT EXISTS enrollment_id INTEGER
                                REFERENCES students_studentenrollment(id)
                                ON DELETE SET NULL
                                DEFERRABLE INITIALLY DEFERRED;
                        CREATE INDEX IF NOT EXISTS payments_payment_enrollment_id_idx
                            ON payments_payment (enrollment_id);
                    """,
                    reverse_sql="""
                        ALTER TABLE payments_payment
                            DROP COLUMN IF EXISTS enrollment_id;
                    """,
            state_operations=[
                migrations.AddField(
                    model_name='payment',
                    name='enrollment',
                    field=models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='payments',
                        to='students.studentenrollment',
                        help_text=(
                            "Inscription annuelle de l'élève correspondant à "
                            "cet enregistrement (cohérence élève ↔ classe ↔ année)."
                        ),
                    ),
                ),
            ],
        ),
        migrations.RunPython(backfill_payment_enrollment, noop_reverse),
    ]
