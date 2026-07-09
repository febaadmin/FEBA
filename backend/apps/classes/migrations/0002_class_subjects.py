from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('classes', '0001_initial'),
        ('subjects', '0004_subject_language_helptext'),
    ]

    operations = [
        migrations.AddField(
            model_name='class',
            name='subjects',
            field=models.ManyToManyField(
                blank=True,
                help_text='Matières françaises ET anglaises assignées à cette classe',
                related_name='classes',
                to='subjects.subject',
                verbose_name='Matières',
            ),
        ),
    ]
