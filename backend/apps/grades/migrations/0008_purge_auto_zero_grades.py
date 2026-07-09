# FIX v32 — Nettoyage des données : les « notes automatiques » à 0 créées par
# l'ancien mécanisme _ensure_zeros_for_period faussaient toutes les moyennes
# (une matière non notée comptait 0 avec son coefficient). Le mécanisme a été
# supprimé ; cette migration marque les notes polluantes existantes comme
# supprimées (soft-delete → exclues des calculs, historique d'audit conservé).

from django.db import migrations
from django.utils import timezone


AUTO_COMMENT = "Note automatique (aucune note saisie)"


def soft_delete_auto_zeros(apps, schema_editor):
    Grade = apps.get_model("grades", "Grade")
    Grade.objects.filter(
        comment=AUTO_COMMENT, value=0, is_deleted=False,
    ).update(is_deleted=True, deleted_at=timezone.now())


def restore_auto_zeros(apps, schema_editor):
    Grade = apps.get_model("grades", "Grade")
    Grade.objects.filter(comment=AUTO_COMMENT, value=0).update(
        is_deleted=False, deleted_at=None,
    )


class Migration(migrations.Migration):

    dependencies = [
        ("grades", "0007_grade_enrollment"),
    ]

    operations = [
        migrations.RunPython(soft_delete_auto_zeros, restore_auto_zeros),
    ]
