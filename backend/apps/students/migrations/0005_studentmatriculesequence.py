"""
Ajoute le compteur séquentiel de matricules (FEBA-YY-NNNN).

Un enregistrement par (établissement, année système). Garantit des numéros
uniques et sans doublon même en création concurrente (verrou de ligne
`select_for_update` côté application), et un redémarrage automatique du
compteur à chaque nouvelle année.
"""
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("schools", "0006_school_tenant_fields"),
        ("students", "0004_tenant_and_exit_fields"),
    ]

    operations = [
        migrations.CreateModel(
            name="StudentMatriculeSequence",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("year", models.PositiveIntegerField(help_text="Année système (ex. 2026).")),
                ("last_number", models.PositiveIntegerField(default=0)),
                (
                    "school",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="matricule_sequences",
                        to="schools.school",
                    ),
                ),
            ],
            options={
                "verbose_name": "Séquence de matricules",
                "verbose_name_plural": "Séquences de matricules",
            },
        ),
        migrations.AddConstraint(
            model_name="studentmatriculesequence",
            constraint=models.UniqueConstraint(
                fields=("school", "year"),
                name="unique_matricule_sequence_per_school_year",
            ),
        ),
    ]
