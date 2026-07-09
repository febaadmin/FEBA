"""
Migration 0003 — Ajout help_text sur Subject.order
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('subjects', '0002_subject_language_order'),
    ]

    operations = [
        migrations.AlterField(
            model_name='subject',
            name='order',
            field=models.PositiveIntegerField(
                default=0,
                help_text="Ordre d'affichage dans le bulletin",
            ),
        ),
    ]
