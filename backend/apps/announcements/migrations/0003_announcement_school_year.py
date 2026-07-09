from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('announcements', '0002_announcement_attachment'),
        ('schools', '0005_schoolbranding_level_cycle'),
    ]

    operations = [
        migrations.AddField(
            model_name='announcement',
            name='school_year',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='announcements',
                to='schools.schoolyear',
            ),
        ),
    ]
