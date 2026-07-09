from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('schools', '0004_roomtype_room_type_obj'),
    ]

    operations = [
        migrations.AddField(
            model_name='level',
            name='cycle',
            field=models.CharField(
                choices=[('maternelle', 'Maternelle'), ('primaire', 'Primaire'), ('college', 'Collège'), ('lycee', 'Lycée')],
                default='primaire', max_length=20,
            ),
        ),
        migrations.CreateModel(
            name='SchoolBranding',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('logo', models.ImageField(blank=True, null=True, upload_to='branding/')),
                ('is_active', models.BooleanField(default=False)),
                ('label', models.CharField(blank=True, max_length=100)),
                ('uploaded_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('school', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='branding_versions', to='schools.school')),
                ('uploaded_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='uploaded_brandings', to=settings.AUTH_USER_MODEL)),
            ],
            options={'verbose_name': 'Version branding', 'ordering': ['-uploaded_at']},
        ),
    ]
