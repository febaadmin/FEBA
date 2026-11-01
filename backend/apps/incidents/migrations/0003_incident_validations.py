from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("incidents", "0002_statut_corrige_historique")]

    operations = [
        migrations.AddField(
            model_name="technicalincident",
            name="validations",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
