from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("messaging", "0002_message_attachment"),
        ("accounts", "0002_add_superadmin_role_level"),
    ]

    operations = [
        migrations.CreateModel(
            name="Conversation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("subject", models.CharField(max_length=200)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("participants", models.ManyToManyField(blank=True, related_name="conversations", to="accounts.customuser")),
            ],
            options={"verbose_name": "Conversation", "ordering": ["-updated_at"]},
        ),
        migrations.AddField(
            model_name="message",
            name="conversation",
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.CASCADE,
                related_name="messages", to="messaging.conversation"
            ),
        ),
        # Make recipient nullable for conversation-based messages
        migrations.AlterField(
            model_name="message",
            name="recipient",
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.CASCADE,
                related_name="received_messages", to="accounts.customuser"
            ),
        ),
        migrations.AlterField(
            model_name="message",
            name="subject",
            field=models.CharField(blank=True, max_length=200),
        ),
    ]
