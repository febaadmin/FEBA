"""
accounts/migrations/0003_customuser_school.py — VERSION IDEMPOTENTE (v29.1)
"""
from django.db import migrations, models
import django.db.models.deletion


def backfill_user_school(apps, schema_editor):
    """
    Idempotent : ne touche que les CustomUser sans école assignée.
    Les utilisateurs déjà associés à une école (d'un run précédent
    de cette migration) sont ignorés.
    """
    CustomUser = apps.get_model('accounts', 'CustomUser')
    School = apps.get_model('schools', 'School')
    school = School.objects.first()
    if school is not None:
        CustomUser.objects.filter(
            school__isnull=True
        ).exclude(role='superadmin').update(school=school)


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    atomic = False  # IF NOT EXISTS

    dependencies = [
        ('accounts', '0002_add_superadmin_role_level'),
        ('schools', '0006_school_tenant_fields'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql="""
                        ALTER TABLE accounts_customuser
                            ADD COLUMN IF NOT EXISTS school_id INTEGER
                                REFERENCES schools_school(id)
                                ON DELETE RESTRICT
                                DEFERRABLE INITIALLY DEFERRED;
                        CREATE INDEX IF NOT EXISTS accounts_customuser_school_id_idx
                            ON accounts_customuser (school_id);
                    """,
                    reverse_sql="""
                        ALTER TABLE accounts_customuser
                            DROP COLUMN IF EXISTS school_id;
                    """,
                ),
            ],
            state_operations=[
                migrations.AddField(
                    model_name='customuser',
                    name='school',
                    field=models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name='users',
                        to='schools.school',
                        help_text=(
                            "Établissement de rattachement. "
                            "Obligatoire sauf pour le rôle superadmin."
                        ),
                    ),
                ),
            ],
        ),
        migrations.RunPython(backfill_user_school, noop_reverse),
    ]
