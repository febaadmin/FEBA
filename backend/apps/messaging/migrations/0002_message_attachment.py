from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [
        ('messaging', '0001_initial'),
    ]
    operations = [
        migrations.AddField(
            model_name='message',
            name='attachment',
            field=models.FileField(blank=True, null=True, upload_to='messages/attachments/'),
        ),
        migrations.AddField(
            model_name='message',
            name='attachment_name',
            field=models.CharField(blank=True, max_length=200),
        ),
    ]
