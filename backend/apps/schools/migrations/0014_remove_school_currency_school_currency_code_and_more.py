"""
schools/0014 — `currency` devient `currency_code`, sans perte de donnée.

L'autodétection de Django proposait un `RemoveField` suivi d'un `AddField` :
appliquée telle quelle, cette paire aurait effacé la devise déjà
renseignée sur chaque académie et remis tout le monde en XOF — y compris
FEBA French Heritage Academy, qui facture en dollars. Le renommage est
donc explicitement scindé en trois temps : créer, recopier, supprimer.
"""
from django.db import migrations, models


def copy_currency_to_code(apps, schema_editor):
    """Reporte la devise existante dans le nouveau champ."""
    School = apps.get_model("schools", "School")
    for school in School.objects.all():
        code = (getattr(school, "currency", None) or "XOF").upper()[:3]
        # Une valeur hors registre (saisie libre historique) retombe sur le
        # franc CFA plutôt que de casser la migration : le rapport d'audit
        # la signalera, mais la base doit rester exploitable.
        school.currency_code = code if code in {"XOF", "USD"} else "XOF"
        school.save(update_fields=["currency_code"])


def copy_code_to_currency(apps, schema_editor):
    School = apps.get_model("schools", "School")
    for school in School.objects.all():
        school.currency = school.currency_code
        school.save(update_fields=["currency"])


class Migration(migrations.Migration):

    dependencies = [
        ("schools", "0013_entity_codes_and_fha"),
    ]

    operations = [
        migrations.AddField(
            model_name="school",
            name="currency_code",
            field=models.CharField(
                choices=[
                    ("XOF", "XOF — Franc CFA BCEAO"),
                    ("USD", "USD — Dollar des États-Unis"),
                ],
                default="XOF",
                help_text=(
                    "Devise de TOUTES les opérations financières de cette académie : "
                    "tarifs, factures, paiements, reçus, remboursements, statistiques "
                    "et exports. FEBA facture en XOF, FEBA FHA en USD."
                ),
                max_length=3,
                verbose_name="Devise",
            ),
        ),
        migrations.AddField(
            model_name="school",
            name="currency_locale",
            field=models.CharField(
                blank=True,
                default="",
                help_text="Format d'écriture des montants (ex. fr-BJ, en-US). Vide = celui de la devise.",
                max_length=10,
            ),
        ),
        migrations.RunPython(copy_currency_to_code, copy_code_to_currency),
        migrations.RemoveField(
            model_name="school",
            name="currency",
        ),
    ]
