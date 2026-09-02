"""
Retire de la base les numéros institutionnels hors service.

POURQUOI UNE MIGRATION EN PLUS DU CORRECTIF DE CODE
---------------------------------------------------
`apps/schools/institution.py` garantit que les DOCUMENTS n'impriment plus
que le numéro officiel : ils ne lisent plus `School.phone`. Cela suffit à
faire cesser l'émission de pièces erronées, et cela suffit seul.

Mais la colonne, elle, contient toujours l'ancien numéro dans les bases
déjà en service — celle de production comprise, d'où provenait le reçu
signalé. Elle reste affichée dans l'écran « Paramètres », reprise dans les
exports d'administration, et lue par tout code futur qui croirait bien
faire en l'utilisant. Corriger le rendu sans corriger la donnée laisse la
cause en place et compte sur le fait que personne n'y touchera.

CE QUE CETTE MIGRATION NE FAIT PAS
----------------------------------
Elle ne touche AUCUN numéro de parent, d'élève, d'enseignant ou de
demande d'inscription : ce sont des coordonnées personnelles, et rien ne
permet de supposer qu'un parent a saisi par erreur le numéro de l'école.
Seules les entités (`School`) sont concernées, et seulement lorsque leur
numéro est exactement l'un des numéros institutionnels retirés.

RÉVERSIBILITÉ
-------------
Volontairement irréversible dans le sens « restaurer l'ancien numéro » :
remettre en base un numéro hors service n'a pas de sens métier. La
migration inverse existe et ne fait rien, pour ne pas bloquer un
`migrate` descendant.
"""
from django.db import migrations


def retire_legacy_phone(apps, schema_editor):
    School = apps.get_model("schools", "School")
    # Import local : le module applicatif n'est pas un modèle historique,
    # mais il ne contient que des constantes et des fonctions pures — il
    # est stable pour une migration de données.
    from apps.schools.institution import (
        is_retired_phone, official_phone, strip_retired_phones,
    )

    replacement = official_phone()
    for academy in School.objects.all():
        updates = []
        if is_retired_phone(academy.phone):
            academy.phone = replacement
            updates.append("phone")
        # `address` est un champ libre : le numéro y a parfois été recopié
        # (« Akpakpa, Cotonou — Tél 01 96 69 73 63 »).
        cleaned_address = strip_retired_phones(academy.address)
        if cleaned_address != (academy.address or ""):
            academy.address = cleaned_address
            updates.append("address")
        if is_retired_phone(academy.whatsapp):
            academy.whatsapp = ""
            updates.append("whatsapp")
        if updates:
            academy.save(update_fields=updates)


def noop(apps, schema_editor):
    """Rien à défaire : un numéro hors service n'est pas à restaurer."""


class Migration(migrations.Migration):

    dependencies = [
        ("schools", "0014_remove_school_currency_school_currency_code_and_more"),
    ]

    operations = [
        migrations.RunPython(retire_legacy_phone, noop),
    ]
