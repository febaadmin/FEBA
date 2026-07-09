# Migration initiale du module Salles virtuelles (visioconférence Jitsi).

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('classes', '0001_initial'),
        ('schools', '0001_initial'),
        ('subjects', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='VirtualRoom',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=200)),
                ('description', models.TextField(blank=True)),
                ('room_code', models.CharField(blank=True, help_text='Identifiant Jitsi de la salle. Généré automatiquement (non devinable).', max_length=80, unique=True)),
                ('scheduled_at', models.DateTimeField(blank=True, help_text='Date/heure planifiée. Vide = salle permanente.', null=True)),
                ('duration_minutes', models.PositiveIntegerField(default=60)),
                ('status', models.CharField(choices=[('scheduled', 'Planifiée'), ('live', 'En cours'), ('ended', 'Terminée'), ('cancelled', 'Annulée')], default='scheduled', max_length=12)),
                ('is_active', models.BooleanField(default=True)),
                ('lobby_enabled', models.BooleanField(default=True, help_text="Salle d'attente Jitsi recommandée côté client (les invités attendent l'hôte).")),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('class_obj', models.ForeignKey(blank=True, db_column='class_id', help_text="Classe concernée. Vide = salle générale (tout l'établissement).", null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='virtual_rooms', to='classes.class')),
                ('created_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='virtual_rooms_created', to=settings.AUTH_USER_MODEL)),
                ('school', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='virtual_rooms', to='schools.school')),
                ('school_year', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='virtual_rooms', to='schools.schoolyear')),
                ('subject', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='virtual_rooms', to='subjects.subject')),
            ],
            options={
                'verbose_name': 'Salle virtuelle',
                'verbose_name_plural': 'Salles virtuelles',
                'ordering': ['-scheduled_at', '-created_at'],
            },
        ),
        migrations.CreateModel(
            name='VirtualRoomAttendance',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('joined_at', models.DateTimeField(auto_now_add=True)),
                ('room', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='attendances', to='virtualclass.virtualroom')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='virtual_room_attendances', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Participation salle virtuelle',
                'ordering': ['-joined_at'],
            },
        ),
    ]
