from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('schools', '0001_initial'),
        ('students', '0001_initial'),
        ('subjects', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Attendance',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date', models.DateField()),
                ('status', models.CharField(
                    choices=[('present', 'Présent'), ('absent', 'Absent'), ('late', 'En retard'), ('excused', 'Excusé')],
                    default='present', max_length=10)),
                ('justification', models.TextField(blank=True)),
                ('notified_parent', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('created_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name='attendance_created', to=settings.AUTH_USER_MODEL)),
                ('school_year', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE,
                    to='schools.schoolyear')),
                ('student', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                    related_name='attendance_records', to='students.student')),
                ('subject', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                    to='subjects.subject')),
            ],
            options={'verbose_name': 'Présence', 'ordering': ['-date']},
        ),
    ]
