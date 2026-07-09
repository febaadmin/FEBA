from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ("payments", "0001_initial"),
        ("accounts", "0002_add_superadmin_role_level"),
    ]

    operations = [
        migrations.AddField(
            model_name="payment",
            name="updated_at",
            field=models.DateTimeField(auto_now=True),
        ),
        migrations.CreateModel(
            name="PaymentHistory",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("action", models.CharField(choices=[("create","Création"),("cancel","Annulation"),("update","Modification"),("receipt","Reçu généré")], max_length=10)),
                ("amount_snapshot", models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True)),
                ("is_confirmed_before", models.BooleanField(blank=True, null=True)),
                ("is_confirmed_after", models.BooleanField(blank=True, null=True)),
                ("justification", models.TextField(blank=True)),
                ("notes", models.TextField(blank=True)),
                ("performed_at", models.DateTimeField(auto_now_add=True)),
                ("payment", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="history", to="payments.payment")),
                ("performed_by", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="payment_actions", to="accounts.customuser")),
            ],
            options={"verbose_name": "Historique paiement", "ordering": ["-performed_at"]},
        ),
    ]
