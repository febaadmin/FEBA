from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("announcements", "0001_initial")]
    operations = [
        migrations.AddField(
            model_name="announcement",
            name="attachment",
            field=models.FileField(blank=True, null=True, upload_to="announcements/"),
        ),
        migrations.AddField(
            model_name="announcement",
            name="attachment_name",
            field=models.CharField(blank=True, max_length=200),
        ),
    ]