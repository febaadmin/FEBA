"""
Migration de données : rattache les soumissions existantes à l'entité FEBA.

RÈGLE DE MIGRATION (sans perte)
-------------------------------
Les messages de contact et préinscriptions déjà en base ont été déposés
AVANT la séparation des entités, via les formulaires du site FEBA. Ils
appartiennent donc à FEBA.

Les demandes portant `desired_level = "feba_online"` sont un cas
particulier : elles concernent l'ancien module « FEBA Online », devenu
FEBA French Heritage Academy. Elles ne sont PAS déplacées silencieusement
— la donnée serait ambiguë (le formulaire FEBA ne collectait aucune des
informations nécessaires à FHA). Elles restent rattachées à FEBA et sont
MARQUÉES pour revue manuelle par l'administration, via le champ `message`
laissé intact et un compteur journalisé.

Aucune ligne n'est supprimée. La migration est idempotente : elle ne
touche que les lignes dont `entity` est encore NULL.
"""
import logging

from django.db import migrations

logger = logging.getLogger("apps")


def forwards(apps, schema_editor):
    School = apps.get_model("schools", "School")
    ContactMessage = apps.get_model("website", "ContactMessage")
    PreRegistration = apps.get_model("website", "PreRegistration")

    feba = School.objects.filter(code="FEBA").first()
    if feba is None:
        # Base sans entité FEBA identifiée (installation neuve, aucune
        # donnée à rattacher) : rien à faire.
        return

    contacts = ContactMessage.objects.filter(entity__isnull=True).update(entity=feba)
    preregs = PreRegistration.objects.filter(entity__isnull=True).update(entity=feba)

    # Comptage des demandes issues de l'ancien module « FEBA Online » :
    # signalées pour revue, jamais réaffectées automatiquement.
    to_review = PreRegistration.objects.filter(
        entity=feba, desired_level="feba_online",
    ).count()

    logger.info(
        "Migration entités formulaires : %s messages et %s préinscriptions "
        "rattachés à FEBA ; %s demandes « FEBA Online » à revoir manuellement "
        "pour un éventuel rattachement à FEBA FHA.",
        contacts, preregs, to_review,
    )


def backwards(apps, schema_editor):
    """Retour arrière non destructif : on ne fait que délier."""
    ContactMessage = apps.get_model("website", "ContactMessage")
    PreRegistration = apps.get_model("website", "PreRegistration")
    ContactMessage.objects.update(entity=None)
    PreRegistration.objects.update(entity=None)


class Migration(migrations.Migration):

    dependencies = [
        ("website", "0004_contactmessage_category_contactmessage_country_and_more"),
        ("schools", "0013_entity_codes_and_fha"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
