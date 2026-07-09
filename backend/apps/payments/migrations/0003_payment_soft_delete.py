from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [("payments", "0002_paymenthistory")]
    operations = [
        migrations.AddField(
            model_name="payment",
            name="is_deleted",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="payment",
            name="deleted_at",
            field=models.DateTimeField(null=True, blank=True),
        ),
        migrations.AddField(
            model_name="payment",
            name="deleted_by",
            field=models.ForeignKey(
                "accounts.CustomUser", null=True, blank=True,
                on_delete=models.SET_NULL, related_name="deleted_payments"
            ),
        ),
    ]
