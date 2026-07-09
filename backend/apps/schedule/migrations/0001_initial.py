from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True
    dependencies = [
        ('classes', '0001_initial'),
        ('schools', '0001_initial'),
        ('subjects', '0001_initial'),
        ('teachers', '0001_initial'),
    ]
    operations = [
        migrations.CreateModel(
            name='ClassSchedule',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('day_of_week', models.PositiveSmallIntegerField(choices=[(0,'Lundi'),(1,'Mardi'),(2,'Mercredi'),(3,'Jeudi'),(4,'Vendredi'),(5,'Samedi')])),
                ('start_time', models.TimeField()),
                ('end_time', models.TimeField()),
                ('room', models.CharField(blank=True, max_length=50)),
                ('recurrent', models.BooleanField(default=True)),
                ('cls', models.ForeignKey(db_column='class_id', on_delete=django.db.models.deletion.CASCADE, related_name='schedules', to='classes.class')),
                ('school_year', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='schools.schoolyear')),
                ('subject', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='subjects.subject')),
                ('teacher', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='schedules', to='teachers.teacher')),
            ],
            options={'verbose_name': 'Emploi du temps', 'ordering': ['day_of_week','start_time']},
        ),
    ]
