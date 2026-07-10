# BUG N°8 — matricules FEBA_26_0001 : configure le préfixe « FEBA » pour
# l'établissement FEBA existant. Les autres établissements gardent la
# dérivation automatique depuis leur slug (modifiable dans School.matricule_prefix).
from django.db import migrations


def set_feba_prefix(apps, schema_editor):
    School = apps.get_model("schools", "School")
    School.objects.filter(slug__icontains="feba").update(matricule_prefix="FEBA")


def unset_feba_prefix(apps, schema_editor):
    School = apps.get_model("schools", "School")
    School.objects.filter(matricule_prefix="FEBA").update(matricule_prefix="")


class Migration(migrations.Migration):

    dependencies = [
        ("schools", "0009_school_matricule_prefix_alter_room_custom_type_label_and_more"),
    ]

    operations = [
        migrations.RunPython(set_feba_prefix, unset_feba_prefix),
    ]
