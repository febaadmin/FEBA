"""
Les services optionnels ne sont dus que par les élèves abonnés.

Le nouveau champ `FeeSchedule.is_mandatory` vaut vrai par défaut. Pour les
tarifs DÉJÀ publiés de cantine, transport, garderie et « autre », ce défaut
signifierait « dû par tous les élèves » — et donc, dès qu'un échéancier
serait ajouté, des relances à des familles qui n'ont jamais souscrit le
service. On les marque ici comme optionnels et récurrents. Aucun montant,
aucune date et aucun paiement ne sont modifiés.
"""
from django.db import migrations

OPTIONAL_TYPES = ("cantine", "transport", "garderie", "other")


def mark_optional(apps, schema_editor):
    FeeSchedule = apps.get_model("payments", "FeeSchedule")
    FeeSchedule.objects.filter(payment_type__in=OPTIONAL_TYPES).update(
        is_mandatory=False, installment_mode="recurring",
    )


def unmark(apps, schema_editor):
    FeeSchedule = apps.get_model("payments", "FeeSchedule")
    FeeSchedule.objects.filter(payment_type__in=OPTIONAL_TYPES).update(
        is_mandatory=True, installment_mode="split",
    )


class Migration(migrations.Migration):

    dependencies = [
        ("payments", "0012_fee_installments_and_reminders"),
    ]

    operations = [
        migrations.RunPython(mark_optional, unmark),
    ]
