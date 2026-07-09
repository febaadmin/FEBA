"""
Migration 0003 — Ajout help_text sur StudentEnrollment.note
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('students', '0002_studentenrollment'),
    ]

    operations = [
        migrations.AlterField(
            model_name='studentenrollment',
            name='note',
            field=models.TextField(
                blank=True,
                help_text="Notes sur l'inscription (redoublement, transfert, etc.)",
            ),
        ),
    ]
