from django.db import migrations, models


def backfill_source_format(apps, schema_editor):
    """Versions existantes : aucune conversion, le format réel est celui du moteur."""
    Template = apps.get_model("documents", "AcademyDocumentTemplate")
    Template.objects.filter(source_format="").update(source_format=models.F("file_format"))


class Migration(migrations.Migration):

    dependencies = [
        ("documents", "0002_academy_document_templates"),
    ]

    operations = [
        migrations.AddField(
            model_name="academydocumenttemplate", name="source_format",
            field=models.CharField(blank=True, default="", max_length=10),
        ),
        migrations.AddField(
            model_name="academydocumenttemplate", name="normalized_sha256",
            field=models.CharField(blank=True, default="", max_length=64),
        ),
        migrations.AddField(
            model_name="academydocumenttemplate", name="conversion",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AlterField(
            model_name="academydocumenttemplate", name="render_path",
            field=models.CharField(
                blank=True, max_length=500,
                help_text="Fond normalisé (PDF converti, image redressée), si différent de l'original."),
        ),
        migrations.RunPython(backfill_source_format, migrations.RunPython.noop),
    ]
