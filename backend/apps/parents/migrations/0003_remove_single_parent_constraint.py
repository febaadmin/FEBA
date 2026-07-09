"""
parents/migrations/0003_remove_single_parent_constraint.py — VERSION IDEMPOTENTE (v29.1)
"""
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):
    atomic = False  # IF NOT EXISTS / DO $$ pour idempotence

    dependencies = [
        ('parents', '0002_unique_student_has_one_parent'),
    ]

    operations = [
        # ── Suppression de la contrainte (idempotent) ────────────────────────
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql="""
                        DO $$
                        BEGIN
                            IF EXISTS (
                                SELECT 1 FROM pg_constraint
                                WHERE conname = 'unique_student_has_one_parent'
                            ) THEN
                                ALTER TABLE parents_parentstudent
                                    DROP CONSTRAINT unique_student_has_one_parent;
                            END IF;
                        END $$;
                    """,
                    reverse_sql=migrations.RunSQL.noop,
                ),
            ],
            state_operations=[
                migrations.RemoveConstraint(
                    model_name='parentstudent',
                    name='unique_student_has_one_parent',
                ),
            ],
        ),

        # ── Nouveaux champs (IF NOT EXISTS) ──────────────────────────────────
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql="""
                        ALTER TABLE parents_parentstudent
                            ADD COLUMN IF NOT EXISTS is_legal_guardian
                                BOOLEAN NOT NULL DEFAULT TRUE,
                            ADD COLUMN IF NOT EXISTS is_financial_responsible
                                BOOLEAN NOT NULL DEFAULT TRUE,
                            ADD COLUMN IF NOT EXISTS can_pickup
                                BOOLEAN NOT NULL DEFAULT TRUE,
                            ADD COLUMN IF NOT EXISTS created_at
                                TIMESTAMP WITH TIME ZONE DEFAULT NOW();
                        -- Remplir created_at pour les lignes existantes sans valeur
                        UPDATE parents_parentstudent
                            SET created_at = NOW()
                            WHERE created_at IS NULL;
                        -- Rendre NOT NULL après le backfill
                        ALTER TABLE parents_parentstudent
                            ALTER COLUMN created_at SET NOT NULL;
                    """,
                    reverse_sql="""
                        ALTER TABLE parents_parentstudent
                            DROP COLUMN IF EXISTS is_legal_guardian,
                            DROP COLUMN IF EXISTS is_financial_responsible,
                            DROP COLUMN IF EXISTS can_pickup,
                            DROP COLUMN IF EXISTS created_at;
                    """,
                ),
            ],
            state_operations=[
                migrations.AddField(
                    model_name='parentstudent',
                    name='is_legal_guardian',
                    field=models.BooleanField(
                        default=True,
                        help_text="Tuteur légal de l'élève (autorité parentale).",
                    ),
                ),
                migrations.AddField(
                    model_name='parentstudent',
                    name='is_financial_responsible',
                    field=models.BooleanField(
                        default=True,
                        help_text="Responsable des paiements de scolarité de cet élève.",
                    ),
                ),
                migrations.AddField(
                    model_name='parentstudent',
                    name='can_pickup',
                    field=models.BooleanField(
                        default=True,
                        help_text="Personne autorisée à récupérer l'élève à l'établissement.",
                    ),
                ),
                migrations.AddField(
                    model_name='parentstudent',
                    name='created_at',
                    field=models.DateTimeField(auto_now_add=True, null=True),
                ),
            ],
        ),

        migrations.AlterModelOptions(
            name='parentstudent',
            options={
                'verbose_name': 'Lien parent-élève',
                'verbose_name_plural': 'Liens parent-élève',
            },
        ),
    ]
