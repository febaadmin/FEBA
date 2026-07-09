# FIX v39 — Invariant : une seule année active par établissement.
# Des états historiques (tests successifs, activations partielles) ont pu
# laisser PLUSIEURS années avec is_current=True dans le même établissement,
# ce qui désynchronisait la puce sélectionnée et le contenu affiché
# (puce 2026-2027 active, tableau 2023-2024). On ne conserve comme active
# que l'année la plus récente (start_date max) de chaque établissement.

from django.db import migrations, models


def enforce_single_current(apps, schema_editor):
    SchoolYear = apps.get_model("schools", "SchoolYear")
    School = apps.get_model("schools", "School")
    for school in School.objects.all():
        current = list(
            SchoolYear.objects.filter(school=school, is_current=True).order_by("-start_date")
        )
        if len(current) <= 1:
            continue
        keeper = current[0]  # la plus récente reste active
        SchoolYear.objects.filter(school=school, is_current=True).exclude(
            pk=keeper.pk
        ).update(is_current=False)


class Migration(migrations.Migration):

    dependencies = [
        ("schools", "0007_schoolyear_unique_name"),
    ]

    operations = [
        # 1. Dédoublonnage des états historiques
        migrations.RunPython(enforce_single_current, migrations.RunPython.noop),
        # 2. Contrainte : au plus une année active par établissement
        migrations.AddConstraint(
            model_name="schoolyear",
            constraint=models.UniqueConstraint(
                fields=["school"], condition=models.Q(is_current=True),
                name="uniq_current_year_per_school",
            ),
        ),
    ]
