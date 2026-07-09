# FIX v32 — Contrainte d'unicité (school, name) sur les années scolaires.
# On dé-doublonne d'abord d'éventuelles années homonymes créées avant la
# contrainte (les inscriptions/notes sont réaffectées à l'année conservée).

from django.db import migrations, models


def dedupe_years(apps, schema_editor):
    SchoolYear = apps.get_model("schools", "SchoolYear")
    seen = {}
    for year in SchoolYear.objects.order_by("id"):
        key = (year.school_id, year.name)
        if key not in seen:
            seen[key] = year
            continue
        keeper = seen[key]
        # Réaffecte toutes les relations inverses connues vers l'année conservée
        for rel in year._meta.related_objects:
            accessor = rel.get_accessor_name()
            try:
                getattr(year, accessor).update(**{rel.field.name: keeper})
            except Exception:
                pass
        if year.is_current and not keeper.is_current:
            keeper.is_current = True
            keeper.save(update_fields=["is_current"])
        year.delete()


class Migration(migrations.Migration):

    dependencies = [
        ("schools", "0006_school_tenant_fields"),
    ]

    operations = [
        migrations.RunPython(dedupe_years, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name="schoolyear",
            constraint=models.UniqueConstraint(
                fields=["school", "name"], name="uniq_schoolyear_school_name",
            ),
        ),
    ]
