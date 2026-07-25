"""V7 — l'établissement FEBA prend son nom officiel.

« Groupe Scolaire FEBA » (ancien nom de l'école dans l'ERP, affiché sur les
bulletins/reçus) devient « Faith & Excellence Bilingual Academy ». Le libellé
« GROUPE ÉDUCATIF FEBA » est désormais rendu séparément en tête des documents
(cf. pdf_generator). Migration de données sûre : ne renomme que les écoles
encore nommées avec l'ancien libellé exact.
"""
from django.db import migrations

OLD = "Groupe Scolaire FEBA"
NEW = "Faith & Excellence Bilingual Academy"


def forwards(apps, schema_editor):
    School = apps.get_model("schools", "School")
    School.objects.filter(name=OLD).update(name=NEW)


def backwards(apps, schema_editor):
    School = apps.get_model("schools", "School")
    School.objects.filter(name=NEW).update(name=OLD)


class Migration(migrations.Migration):
    dependencies = [
        ("schools", "0010_feba_matricule_prefix"),
    ]
    operations = [
        migrations.RunPython(forwards, backwards),
    ]
