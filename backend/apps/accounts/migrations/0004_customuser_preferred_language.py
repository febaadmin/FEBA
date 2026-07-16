from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0003_customuser_school'),
    ]

    operations = [
        migrations.AddField(
            model_name='customuser',
            name='preferred_language',
            field=models.CharField(
                choices=[('fr', 'Français'), ('en', 'English')],
                default='fr',
                help_text="Langue préférée de l'interface / Preferred interface language.",
                max_length=5,
            ),
        ),
    ]
