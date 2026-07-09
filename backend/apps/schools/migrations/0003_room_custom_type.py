from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('schools', '0002_room'),
    ]

    operations = [
        migrations.AddField(
            model_name='room',
            name='custom_type_label',
            field=models.CharField(
                blank=True,
                max_length=100,
                help_text="Utilisé uniquement si room_type='custom'",
            ),
        ),
        migrations.AlterField(
            model_name='room',
            name='room_type',
            field=models.CharField(
                choices=[
                    ('classroom', 'Salle de classe'),
                    ('computer', 'Salle informatique'),
                    ('canteen', 'Cantine'),
                    ('library', 'Bibliothèque'),
                    ('sports', 'Salle de sport'),
                    ('dance', 'Salle de danse'),
                    ('admin', 'Bureau administratif'),
                    ('custom', 'Type personnalisé'),
                    ('other', 'Autre'),
                ],
                default='classroom',
                max_length=20,
            ),
        ),
    ]
