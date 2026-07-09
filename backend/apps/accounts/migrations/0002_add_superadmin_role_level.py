from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0001_initial'),
    ]

    operations = [
        # 1. Add role_level column with default 10
        migrations.AddField(
            model_name='customuser',
            name='role_level',
            field=models.PositiveSmallIntegerField(default=10),
        ),
        # 2. Extend max_length for role field (superadmin = 10 chars)
        migrations.AlterField(
            model_name='customuser',
            name='role',
            field=models.CharField(
                choices=[
                    ('superadmin', 'Super Administrateur'),
                    ('admin', 'Administrateur'),
                    ('teacher', 'Enseignant'),
                    ('parent', 'Parent'),
                    ('student', 'Élève'),
                ],
                default='student',
                max_length=12,
            ),
        ),
        # 3. Backfill role_level from existing roles
        migrations.RunSQL(
            sql="""
                UPDATE accounts_customuser SET role_level =
                    CASE role
                        WHEN 'superadmin' THEN 100
                        WHEN 'admin'      THEN 80
                        WHEN 'teacher'    THEN 50
                        WHEN 'parent'     THEN 30
                        ELSE 10
                    END
            """,
            reverse_sql="UPDATE accounts_customuser SET role_level = 10",
        ),
    ]
