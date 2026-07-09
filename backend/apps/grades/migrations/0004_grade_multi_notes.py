"""
Migration 0004 — Multi-notes par matière/trimestre

Corrections :
  1. Suppression de la contrainte unique_together (student, subject, school_year, period)
  2. Ajout du champ note_type (type de note)
  3. Ajout du champ note_coefficient (poids de la note dans la moyenne matière)
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("grades", "0003_grade_soft_delete"),
    ]

    operations = [
        # 1. Supprimer la contrainte unique_together qui bloque les multi-notes
        migrations.AlterUniqueTogether(
            name="grade",
            unique_together=set(),
        ),

        # 2. Ajouter note_type
        migrations.AddField(
            model_name="grade",
            name="note_type",
            field=models.CharField(
                max_length=20,
                choices=[
                    ("devoir",        "Devoir"),
                    ("interrogation", "Interrogation"),
                    ("controle",      "Contrôle"),
                    ("examen",        "Examen"),
                    ("tp",            "Travaux Pratiques"),
                    ("autre",         "Autre"),
                ],
                default="devoir",
                verbose_name="Type de note",
            ),
        ),

        # 3. Ajouter note_coefficient
        migrations.AddField(
            model_name="grade",
            name="note_coefficient",
            field=models.PositiveSmallIntegerField(
                default=1,
                verbose_name="Coefficient de la note",
            ),
        ),
    ]
