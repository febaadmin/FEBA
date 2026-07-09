# FIX v35 — Présence aux cours virtuels liée à l'inscription annuelle
# (+ heure de sortie et durée), conformément au modèle métier multi-années.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('virtualclass', '0001_initial'),
        ('students', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='virtualroomattendance',
            name='enrollment',
            field=models.ForeignKey(
                blank=True, null=True,
                help_text="Inscription annuelle de l'élève (null pour enseignants/admins).",
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='virtual_attendances',
                to='students.studentenrollment',
            ),
        ),
        migrations.AddField(
            model_name='virtualroomattendance',
            name='left_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='virtualroomattendance',
            name='duration_seconds',
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
    ]
