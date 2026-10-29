"""
Au plus une version de logo active par académie, et noms de fichiers uniques.

Données existantes : si une académie avait PLUSIEURS versions actives
(activation concurrente, ancien code non atomique), seule la plus récente
le reste — c'est celle que l'application affichait déjà (tri par date
décroissante). Aucun fichier ni aucune version n'est supprimé ; le retour
arrière retire seulement la contrainte.
"""

import apps.schools.models
from django.conf import settings
from django.db import migrations, models


def keep_latest_active(apps, schema_editor):
    SchoolBranding = apps.get_model("schools", "SchoolBranding")
    seen = set()
    for b in SchoolBranding.objects.filter(is_active=True).order_by("school_id", "-uploaded_at", "-pk"):
        if b.school_id in seen:
            SchoolBranding.objects.filter(pk=b.pk).update(is_active=False)
        else:
            seen.add(b.school_id)


class Migration(migrations.Migration):

    dependencies = [
        ('schools', '0017_enable_video_for_all_academies'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RunPython(keep_latest_active, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='schoolbranding',
            name='logo',
            field=models.ImageField(blank=True, null=True, upload_to=apps.schools.models.branding_logo_path),
        ),
        migrations.AddConstraint(
            model_name='schoolbranding',
            constraint=models.UniqueConstraint(condition=models.Q(('is_active', True)), fields=('school',), name='uniq_active_branding_per_school'),
        ),
    ]
