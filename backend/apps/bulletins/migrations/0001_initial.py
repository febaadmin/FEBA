from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True
    dependencies = [
        ('schools', '0001_initial'),
        ('students', '0001_initial'),
    ]
    operations = [
        migrations.CreateModel(
            name='Bulletin',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('period', models.CharField(max_length=7, choices=[('T1','Trimestre 1'),('T2','Trimestre 2'),('T3','Trimestre 3'),('annual','Annuel')])),
                ('pdf_file', models.FileField(null=True, blank=True, upload_to='bulletins/')),
                ('generated_at', models.DateTimeField(auto_now_add=True)),
                ('general_comment', models.TextField(blank=True)),
                ('average', models.DecimalField(decimal_places=2, max_digits=4, null=True, blank=True)),
                ('rank_in_class', models.PositiveIntegerField(null=True, blank=True)),
                ('appreciation', models.CharField(blank=True, max_length=100)),
                ('student', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='bulletins', to='students.student')),
                ('school_year', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='schools.schoolyear')),
            ],
            options={'verbose_name': 'Bulletin', 'ordering': ['-generated_at']},
        ),
        migrations.AddConstraint(
            model_name='bulletin',
            constraint=models.UniqueConstraint(fields=['student','school_year','period'], name='unique_bulletin'),
        ),
    ]
