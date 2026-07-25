"""V7 — nom officiel : « Faith Excellence… » → « Faith & Excellence Bilingual Academy ».

Met à jour le défaut des champs ET les lignes existantes (migration de données
sûre : ne touche qu'aux valeurs encore égales à l'ancien libellé).
"""
from django.db import migrations, models

OLD_NAME = "Faith Excellence Bilingual Academy"
NEW_NAME = "Faith & Excellence Bilingual Academy"
OLD_META = "FEBA — Faith Excellence Bilingual Academy | École bilingue à Cotonou"
NEW_META = "FEBA — Faith & Excellence Bilingual Academy | École bilingue à Cotonou"


def forwards(apps, schema_editor):
    SiteSettings = apps.get_model("website", "SiteSettings")
    SiteSettings.objects.filter(school_name=OLD_NAME).update(school_name=NEW_NAME)
    SiteSettings.objects.filter(meta_title=OLD_META).update(meta_title=NEW_META)


def backwards(apps, schema_editor):
    SiteSettings = apps.get_model("website", "SiteSettings")
    SiteSettings.objects.filter(school_name=NEW_NAME).update(school_name=OLD_NAME)
    SiteSettings.objects.filter(meta_title=NEW_META).update(meta_title=OLD_META)


class Migration(migrations.Migration):
    dependencies = [
        ("website", "0002_galleryitem_focal_x_galleryitem_focal_y_and_more"),
    ]
    operations = [
        migrations.AlterField(
            model_name="sitesettings",
            name="school_name",
            field=models.CharField(default=NEW_NAME, max_length=120),
        ),
        migrations.AlterField(
            model_name="sitesettings",
            name="meta_title",
            field=models.CharField(blank=True, default=NEW_META, max_length=120),
        ),
        migrations.RunPython(forwards, backwards),
    ]
