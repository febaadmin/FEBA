"""
Migration 0006 — Update Grade.period choices (add 'exam', reflects model state)
This migration exists only to silence Django's "Your models have changes" warning.
No schema change — choices are validators only.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('grades', '0005_grade_teacher_blank'),
    ]

    operations = [
        migrations.AlterField(
            model_name='grade',
            name='period',
            field=models.CharField(
                choices=[
                    ('T1',   'Trimestre 1'),
                    ('T2',   'Trimestre 2'),
                    ('T3',   'Trimestre 3'),
                    ('exam', 'Examen'),
                ],
                max_length=5,
            ),
        ),
    ]
