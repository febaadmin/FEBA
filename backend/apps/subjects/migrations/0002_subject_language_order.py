from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('subjects', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='subject',
            name='language',
            field=models.CharField(
                choices=[('fr', 'Français'), ('en', 'Anglais'), ('bilingual', 'Bilingue')],
                default='fr', max_length=10,
            ),
        ),
        migrations.AddField(
            model_name='subject',
            name='order',
            field=models.PositiveIntegerField(default=0),
        ),
    ]
