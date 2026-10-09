"""
Reprise de l'heure des paiements existants — SANS rien inventer.

Avant cette version, seule la DATE d'un paiement était enregistrée
(`payment_date`). La seule trace horaire existante est `created_at`,
l'instant où la ligne a été saisie dans FEBA.

Règle appliquée :
  - si la saisie a eu lieu LE JOUR MÊME du paiement (comparaison faite dans
    le fuseau de l'académie de l'élève), l'encaissement a été enregistré
    au guichet au moment où il a eu lieu : `paid_at` reprend `created_at`
    et la provenance est marquée `backfill_created_at` ;
  - sinon (paiement antidaté, import, saisie de rattrapage), l'heure réelle
    est INCONNUE : `paid_at` reste vide et l'écran l'indique.

Aucune date existante n'est modifiée (`payment_date` n'est pas touché).
La migration inverse vide simplement les valeurs reprises.
"""
from zoneinfo import ZoneInfo

from django.conf import settings
from django.db import migrations

BATCH = 500


def _zone(name):
    try:
        return ZoneInfo(name or settings.TIME_ZONE)
    except Exception:
        return ZoneInfo(settings.TIME_ZONE)


def backfill(apps, schema_editor):
    Payment = apps.get_model("payments", "Payment")
    zones = {}
    pending = []
    qs = (
        Payment.objects.filter(paid_at__isnull=True)
        .select_related("student__school")
        .only("id", "payment_date", "created_at", "student__school__timezone")
        .order_by("pk")
    )
    for payment in qs.iterator(chunk_size=BATCH):
        if payment.created_at is None or payment.payment_date is None:
            continue
        school = getattr(payment.student, "school", None)
        tz_name = getattr(school, "timezone", None) or settings.TIME_ZONE
        zone = zones.setdefault(tz_name, _zone(tz_name))
        if payment.created_at.astimezone(zone).date() != payment.payment_date:
            continue
        payment.paid_at = payment.created_at
        payment.paid_at_source = "backfill_created_at"
        pending.append(payment)
        if len(pending) >= BATCH:
            Payment.objects.bulk_update(pending, ["paid_at", "paid_at_source"])
            pending = []
    if pending:
        Payment.objects.bulk_update(pending, ["paid_at", "paid_at_source"])


def unfill(apps, schema_editor):
    Payment = apps.get_model("payments", "Payment")
    Payment.objects.filter(paid_at_source="backfill_created_at").update(
        paid_at=None, paid_at_source="",
    )


class Migration(migrations.Migration):

    dependencies = [
        ("payments", "0010_payment_paid_at_period_month"),
    ]

    operations = [
        migrations.RunPython(backfill, unfill),
    ]
