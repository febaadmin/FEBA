from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('classes', '0001_initial'),
        ('schools', '0005_schoolbranding_level_cycle'),
        ('students', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='StudentEnrollment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('enrolled_at', models.DateField(auto_now_add=True)),
                ('is_active', models.BooleanField(default=True)),
                ('note', models.TextField(blank=True)),
                ('promotion_status', models.CharField(
                    choices=[('normal','Passage normal'),('honor','Passage avec mention'),('repeat','Redoublement'),('transfer','Transfert'),('new','Nouvelle inscription')],
                    default='new', max_length=20,
                )),
                ('class_obj', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='enrollments', to='classes.class')),
                ('school_year', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='enrollments', to='schools.schoolyear')),
                ('student', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='enrollments', to='students.student')),
            ],
            options={'verbose_name': 'Inscription annuelle', 'ordering': ['-school_year__start_date'], 'unique_together': {('student', 'school_year')}},
        ),
    ]
