from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):
    initial = True
    dependencies = [migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.CreateModel(
            name='Message',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('thread_id', models.UUIDField(default=uuid.uuid4)),
                ('subject', models.CharField(max_length=200)),
                ('body', models.TextField()),
                ('is_read', models.BooleanField(default=False)),
                ('sent_at', models.DateTimeField(auto_now_add=True)),
                ('read_at', models.DateTimeField(null=True, blank=True)),
                ('sender', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='sent_messages', to=settings.AUTH_USER_MODEL)),
                ('recipient', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='received_messages', to=settings.AUTH_USER_MODEL)),
                ('parent_message', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='replies', to='messaging.message')),
            ],
            options={'verbose_name': 'Message', 'ordering': ['-sent_at']},
        ),
    ]
