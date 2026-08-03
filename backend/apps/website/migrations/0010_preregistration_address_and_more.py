"""
P2 — La demande de préinscription porte enfin tout ce qu'elle collecte.

Trois champs manquaient au modèle alors que le secrétariat en avait
besoin pour traiter le dossier : la date de naissance (un âge saisi en
mars n'est plus vrai en septembre, et c'est la date qui décide du niveau
réglementaire), l'adresse du domicile (ramassage scolaire, zone
d'affectation) et un second numéro de téléphone.

Quatre autres champs suivent la production de la fiche PDF officielle,
pour qu'un échec de génération SE VOIE au lieu d'être découvert le jour
où quelqu'un cherche la fiche.

LES DEUX PIÈGES DE CETTE MIGRATION, TROUVÉS EN LA REJOUANT
----------------------------------------------------------
1. `reference` est unique. Ajouter d'un seul coup une colonne unique
   avec une valeur par défaut vide fait échouer la migration dès qu'il
   existe plus d'une demande en base : deux chaînes vides violent la
   contrainte. La colonne est donc ajoutée SANS contrainte, remplie pour
   chaque ligne existante, puis seulement rendue unique.

2. Une première version ajoutait la colonne avec `db_index=True` avant
   de l'altérer en `unique=True`. Sur PostgreSQL, les deux options
   créent le MÊME index auxiliaire de comparaison — son nom dérive de la
   table et de la colonne, pas de l'option. La migration échouait donc
   sur une base neuve :

       ProgrammingError: relation
       "website_preregistration_reference_04b57e49_like" already exists

   La colonne est donc ajoutée nue. L'unicité, posée à l'étape 3, fournit
   déjà l'index : `db_index=True` en plus serait redondant.
"""
from django.db import migrations, models


def attribuer_les_references(apps, schema_editor):
    """Donne un numéro de dossier aux demandes déjà enregistrées."""
    PreRegistration = apps.get_model("website", "PreRegistration")
    anciennes = PreRegistration.objects.filter(
        models.Q(reference="") | models.Q(reference=None)).order_by("pk")
    for demande in anciennes:
        annee = demande.created_at.year if demande.created_at else 2026
        demande.reference = f"FEBA-{annee}-{demande.pk:04d}"
        demande.save(update_fields=["reference"])


def effacer_les_references(apps, schema_editor):
    apps.get_model("website", "PreRegistration").objects.update(reference=None)


class Migration(migrations.Migration):

    dependencies = [
        ("website", "0009_alter_fhaenrollmentapplication_child_photo"),
    ]

    operations = [
        migrations.AddField(
            model_name="preregistration",
            name="address",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="preregistration",
            name="child_birth_date",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="preregistration",
            name="phone_secondary",
            field=models.CharField(blank=True, max_length=30),
        ),
        # Étape 1 — la colonne nue : ni index, ni unicité.
        migrations.AddField(
            model_name="preregistration",
            name="reference",
            field=models.CharField(blank=True, max_length=32, null=True),
        ),
        migrations.AddField(
            model_name="preregistration",
            name="sheet_error",
            field=models.TextField(
                blank=True,
                help_text="Motif du dernier échec de production. Vide si la dernière tentative a réussi.",
            ),
        ),
        migrations.AddField(
            model_name="preregistration",
            name="sheet_generated_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="preregistration",
            name="sheet_path",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name="preregistration",
            name="sheet_sha256",
            field=models.CharField(blank=True, max_length=64),
        ),
        # Étape 2 — les demandes déjà en base reçoivent leur numéro.
        migrations.RunPython(attribuer_les_references, effacer_les_references),
        # Étape 3 — l'unicité, maintenant qu'aucune valeur n'est vide.
        # `null=True` laisse passer la fenêtre entre l'insertion d'une
        # ligne et l'écriture de sa référence : NULL n'est égal à rien,
        # donc deux insertions simultanées ne se gênent pas.
        migrations.AlterField(
            model_name="preregistration",
            name="reference",
            field=models.CharField(
                blank=True,
                null=True,
                help_text="Numéro de dossier. Attribué automatiquement.",
                max_length=32,
                unique=True,
            ),
        ),
    ]
