from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    dependencies = [
        ('grades', '0001_initial'),
        ('accounts', '0002_add_superadmin_role_level'),
    ]
    operations = [
        migrations.AddField(
            model_name='grade',
            name='updated_at',
            field=models.DateTimeField(auto_now=True),
        ),
        migrations.CreateModel(
            name='GradeHistory',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('old_value', models.DecimalField(blank=True, decimal_places=2, max_digits=4, null=True)),
                ('new_value', models.DecimalField(decimal_places=2, max_digits=4)),
                ('old_comment', models.TextField(blank=True)),
                ('new_comment', models.TextField(blank=True)),
                ('justification', models.TextField(blank=True)),
                ('action', models.CharField(choices=[('create', 'Création'), ('update', 'Modification')], default='create', max_length=10)),
                ('changed_at', models.DateTimeField(auto_now_add=True)),
                ('changed_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to='accounts.customuser')),
                ('grade', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='history', to='grades.grade')),
            ],
            options={'verbose_name': 'Historique note', 'ordering': ['-changed_at']},
        ),
    ]
