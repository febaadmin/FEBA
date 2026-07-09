"""
Migration 0005 — Correction champ teacher (blank=True) + GradeHistory verbose
"""
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('grades', '0004_grade_multi_notes'),
        ('teachers', '0001_initial'),
    ]

    operations = [
        # Fix teacher FK: add blank=True to match model
        migrations.AlterField(
            model_name='grade',
            name='teacher',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='grades_given',
                to='teachers.teacher',
            ),
        ),
    ]
