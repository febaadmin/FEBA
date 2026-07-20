"""
Recalcule les appréciations stockées des bulletins existants avec le
barème officiel v4 (EXCELLENT … TRÈS FAIBLE), à partir de la moyenne
enregistrée. Les anciennes valeurs (« Excellent travail », « Assez Bien »,
etc.) ne subsistent plus dans les données actives.

Réversible : la migration inverse recalcule les libellés de l'ancien
barème à partir des mêmes moyennes (aucune donnée n'est détruite — la
moyenne source reste intacte dans les deux sens).
"""
from decimal import Decimal
from django.db import migrations

# Barème v4 — copie figée volontairement dans la migration (une migration ne
# doit pas dépendre du code applicatif qui, lui, continuera d'évoluer).
NEW_SCALE = [
    (Decimal('19'), 'EXCELLENT'),
    (Decimal('17'), 'TRÈS SATISFAISANT'),
    (Decimal('15'), 'SATISFAISANT'),
    (Decimal('13'), 'ACCEPTABLE'),
    (Decimal('11'), 'PEUT MIEUX FAIRE'),
    (Decimal('9'),  'INSUFFISANT'),
    (Decimal('7'),  'TRÈS INSUFFISANT'),
    (Decimal('4'),  'FAIBLE'),
    (Decimal('0'),  'TRÈS FAIBLE'),
]

OLD_SCALE = [
    (Decimal('16'), 'Excellent'),
    (Decimal('14'), 'Très Bien'),
    (Decimal('12'), 'Bien'),
    (Decimal('10'), 'Assez Bien'),
    (Decimal('8'),  'Passable'),
    (Decimal('0'),  'Insuffisant'),
]


def _classify(value, scale):
    for threshold, label in scale:
        if value >= threshold:
            return label
    return scale[-1][1]


def _recompute(apps, scale):
    Bulletin = apps.get_model('bulletins', 'Bulletin')
    to_update = []
    for bulletin in Bulletin.objects.exclude(average__isnull=True).iterator():
        new_label = _classify(bulletin.average, scale)
        if bulletin.appreciation != new_label:
            bulletin.appreciation = new_label
            to_update.append(bulletin)
    Bulletin.objects.bulk_update(to_update, ['appreciation'], batch_size=500)


def forwards(apps, schema_editor):
    _recompute(apps, NEW_SCALE)


def backwards(apps, schema_editor):
    _recompute(apps, OLD_SCALE)


class Migration(migrations.Migration):

    dependencies = [
        ('bulletins', '0004_alter_bulletin_enrollment'),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
