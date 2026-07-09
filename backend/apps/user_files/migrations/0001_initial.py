from django.db import migrations, models
import apps.user_files.models
import django.core.validators
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('accounts', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='UserFile',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255, help_text='Nom affiché du fichier')),
                ('description', models.TextField(blank=True)),
                ('file', models.FileField(
                    upload_to=apps.user_files.models.user_upload_path,
                    validators=[django.core.validators.FileExtensionValidator(
                        allowed_extensions=['jpg','jpeg','png','gif','webp','pdf','doc','docx','odt',
                                            'xls','xlsx','ods','ppt','pptx','txt','csv','zip','rar','mp4','mp3']
                    )]
                )),
                ('file_size', models.PositiveBigIntegerField(default=0)),
                ('mime_type', models.CharField(blank=True, max_length=100)),
                ('original_filename', models.CharField(blank=True, max_length=255)),
                ('uploaded_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='files',
                    to='accounts.customuser',
                )),
            ],
            options={'verbose_name': 'Fichier utilisateur', 'ordering': ['-uploaded_at']},
        ),
    ]
