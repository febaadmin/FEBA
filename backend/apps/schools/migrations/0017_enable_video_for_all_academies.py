"""
Visioconférence et salles virtuelles pour TOUTES les académies (FEBA comprise).

Les valeurs par défaut du type « campus » ont changé dans le code
(School.DEFAULT_FEATURES) ; cette migration traite les DONNÉES : une
académie dont `settings["features"]` désactivait explicitement
`virtual_classrooms` ou `video_conferencing` les voit réactivées.

Non destructive : seules ces deux clés changent ; les autres drapeaux et
réglages, les salles et les réunions existantes ne sont pas touchés. Les
valeurs d'origine sont conservées dans `settings["features_before_0017"]`,
ce qui rend la migration réversible à l'identique.
"""
from django.db import migrations

FLAGS = ("virtual_classrooms", "video_conferencing")
BACKUP_KEY = "features_before_0017"


def enable(apps, schema_editor):
    School = apps.get_model("schools", "School")
    for school in School.objects.all():
        settings = dict(school.settings or {})
        features = dict(settings.get("features") or {})
        disabled = {flag: features[flag] for flag in FLAGS if flag in features and not features[flag]}
        if not disabled:
            continue
        settings[BACKUP_KEY] = disabled
        features.update({flag: True for flag in disabled})
        settings["features"] = features
        school.settings = settings
        school.save(update_fields=["settings"])


def restore(apps, schema_editor):
    School = apps.get_model("schools", "School")
    for school in School.objects.all():
        settings = dict(school.settings or {})
        backup = settings.pop(BACKUP_KEY, None)
        if not backup:
            continue
        features = dict(settings.get("features") or {})
        features.update(backup)
        settings["features"] = features
        school.settings = settings
        school.save(update_fields=["settings"])


class Migration(migrations.Migration):
    dependencies = [("schools", "0016_activate_orphan_school_years")]
    operations = [migrations.RunPython(enable, restore)]
