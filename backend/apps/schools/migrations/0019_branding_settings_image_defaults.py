"""
Retire de `School.settings["branding"]` les images LIVRÉES qu'`init_academies`
y avait recopiées (logo de repli, favicons).

Pourquoi : recopiées dans les réglages, ces valeurs passaient pour un choix
administré. Pour FEBA, `document_logo = "logo_feba.jpeg"` (ancien logo) restait
donc le logo de repli au lieu du logo fourni le 26/10/2026.

Seules les valeurs ÉGALES à un fichier livré connu sont retirées ; un choix
réellement différent est conservé. Les valeurs retirées sont gardées dans
`settings["branding_before_0019"]` : la migration inverse les restaure.
"""
from django.db import migrations

IMAGE_KEYS = ("document_logo", "favicon_16", "favicon_32", "apple_touch_icon")
SHIPPED = {
    "logo_feba.jpeg", "logo_groupe_feba.png", "feba_logo_document.png",
    "favicon-16x16.png", "favicon-32x32.png", "apple-touch-icon.png",
}
BACKUP = "branding_before_0019"


def forwards(apps, schema_editor):
    School = apps.get_model("schools", "School")
    for school in School.objects.all():
        settings = dict(school.settings or {})
        branding = dict(settings.get("branding") or {})
        removed = {k: branding[k] for k in IMAGE_KEYS if branding.get(k) in SHIPPED}
        if not removed:
            continue
        for k in removed:
            branding.pop(k)
        settings["branding"] = branding
        settings[BACKUP] = removed
        school.settings = settings
        school.save(update_fields=["settings"])


def backwards(apps, schema_editor):
    School = apps.get_model("schools", "School")
    for school in School.objects.all():
        settings = dict(school.settings or {})
        removed = settings.pop(BACKUP, None)
        if not removed:
            continue
        branding = dict(settings.get("branding") or {})
        branding.update(removed)
        settings["branding"] = branding
        school.settings = settings
        school.save(update_fields=["settings"])


class Migration(migrations.Migration):
    dependencies = [("schools", "0018_branding_unique_active")]
    operations = [migrations.RunPython(forwards, backwards)]
