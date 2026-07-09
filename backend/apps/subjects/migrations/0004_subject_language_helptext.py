"""
Migration 0004 — Add help_text to Subject.language field
Silences Django's "models have changes not reflected in migration" warning.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('subjects', '0003_subject_order_helptext'),
    ]

    operations = [
        migrations.AlterField(
            model_name='subject',
            name='language',
            field=models.CharField(
                choices=[('fr', 'Français'), ('en', 'Anglais'), ('bilingual', 'Bilingue')],
                default='fr',
                help_text='Langue de la matière — utilisé pour le calcul de la moyenne bilingue',
                max_length=10,
            ),
        ),
    ]
