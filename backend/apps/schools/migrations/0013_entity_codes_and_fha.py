"""
Migration de données multi-entités (V4).

OBJECTIFS
---------
1. Donner un CODE INTERNE STABLE aux entités existantes : l'établissement
   FEBA historique reçoit `code = "FEBA"`. La logique métier s'appuiera sur
   ce code, jamais sur le nom affiché.
2. Créer l'entité « FEBA French Heritage Academy » (`code = "FEBA_FHA"`),
   académie en ligne ciblant la diaspora aux États-Unis / Canada.
3. Rétro-remplir `OrganizationMembership` depuis `CustomUser.school`, sans
   perte : chaque utilisateur déjà rattaché à un établissement obtient une
   appartenance principale correspondante.

AUCUNE DONNÉE N'EST SUPPRIMÉE NI DÉPLACÉE. Les données scolaires existantes
restent rattachées à leur établissement d'origine (FEBA).

IDEMPOTENCE
-----------
Toutes les opérations utilisent `filter(...)` / `get_or_create(...)` : la
migration peut être rejouée sur une base déjà migrée sans créer de doublon
ni écraser une valeur saisie par l'administration.

VALEURS NON INVENTÉES
---------------------
Seules les données confirmées par les documents de cadrage FEBA FHA sont
écrites (nom, slogan, WhatsApp +1 215 715-5406, pays/fuseau cible, devise
USD, langue par défaut EN). Les tarifs, dates de rentrée, horaires
définitifs, noms d'enseignants et prestataire de paiement ne sont PAS
renseignés : ils restent vides et administrables.
"""
from django.db import migrations

FHA_CODE = "FEBA_FHA"
FHA_SLUG = "feba-fha"
FHA_NAME = "FEBA French Heritage Academy"
FHA_LEGAL = "FEBA French Heritage Academy"
FHA_WHATSAPP = "+1 (215) 715-5406"


def forwards(apps, schema_editor):
    School = apps.get_model("schools", "School")
    User = apps.get_model("accounts", "CustomUser")
    Membership = apps.get_model("schools", "OrganizationMembership")

    # ── 1. Code stable pour l'entité FEBA historique ────────────────────
    # On ne touche qu'aux établissements sans code, pour rester idempotent
    # et ne jamais réécrire un code déjà attribué par l'administration.
    feba = (
        School.objects.filter(code__isnull=True)
        .filter(slug__icontains="feba")
        .exclude(slug=FHA_SLUG)
        .order_by("id")
        .first()
    )
    if feba is None:
        # Base sans école « feba » identifiable : on prend le plus ancien
        # établissement existant comme entité principale, plutôt que de
        # laisser la plateforme sans entité de référence.
        feba = School.objects.filter(code__isnull=True).order_by("id").first()

    if feba is not None:
        feba.code = "FEBA"
        feba.entity_type = "campus"
        if not feba.legal_name:
            feba.legal_name = "Faith & Excellence Bilingual Academy"
        if not feba.timezone:
            feba.timezone = "Africa/Porto-Novo"
        if not feba.currency:
            feba.currency = "XOF"
        feba.default_language = feba.default_language or "fr"
        feba.save()

    # ── 2. Création de l'entité FEBA French Heritage Academy ────────────
    fha = School.objects.filter(code=FHA_CODE).first()
    if fha is None:
        # Un établissement portant déjà ce slug (import antérieur) est
        # réutilisé plutôt que dupliqué.
        fha = School.objects.filter(slug=FHA_SLUG).first()

    if fha is None:
        fha = School(slug=FHA_SLUG)

    fha.code = FHA_CODE
    fha.name = FHA_NAME
    fha.legal_name = FHA_LEGAL
    fha.entity_type = "online"
    fha.slug = FHA_SLUG
    # Académie 100 % en ligne : pas d'adresse de campus propre, les cours
    # sont dispensés depuis FEBA au Bénin.
    if not fha.address:
        fha.address = "Programme 100 % en ligne — cours dispensés depuis FEBA, Cotonou, Bénin."
    fha.city = fha.city or "Cotonou"
    fha.country = fha.country or "Bénin"
    if not fha.whatsapp:
        fha.whatsapp = FHA_WHATSAPP
    # Le public cible vit aux États-Unis / Canada : fuseau, devise et langue
    # par défaut de l'entité sont ceux des familles, pas ceux de Cotonou.
    fha.timezone = fha.timezone if fha.timezone not in ("", "Africa/Porto-Novo") else "America/New_York"
    fha.currency = fha.currency if fha.currency not in ("", "XOF") else "USD"
    fha.default_language = "en"
    fha.matricule_prefix = fha.matricule_prefix or "FHA"
    fha.is_active = True
    if not fha.description:
        fha.description = (
            "Programme d'apprentissage du français entièrement en ligne destiné aux "
            "enfants de la diaspora africaine vivant aux États-Unis, au Canada et "
            "dans d'autres pays anglophones."
        )
    # Réglages administrables. Les valeurs non validées par la direction
    # (tarifs, rentrée, horaires, remboursement, prestataire de paiement)
    # restent VIDES : le frontend masque les blocs vides au lieu
    # d'afficher des informations inventées.
    settings = dict(fha.settings or {})
    settings.setdefault("tagline", "From English Speakers to Confident French Speakers")
    settings.setdefault("pending_direction_validation", {
        "annual_fee": None,
        "installments_allowed": None,
        "school_year_start_date": None,
        "group_schedules": None,
        "sibling_discount": None,
        "early_bird_discount": None,
        "refund_policy": None,
        "teacher_names": None,
        "payment_provider": None,
        "zoom_recording_policy": None,
    })
    fha.settings = settings
    fha.save()

    # ── 3. Rétro-remplissage des appartenances ──────────────────────────
    # Chaque utilisateur déjà rattaché à un établissement reçoit une
    # appartenance principale. Aucun utilisateur n'est déplacé d'entité.
    for user in User.objects.filter(school__isnull=False).iterator():
        Membership.objects.get_or_create(
            user_id=user.id,
            organization_id=user.school_id,
            defaults={
                "role": user.role,
                "status": "active",
                "is_primary": True,
            },
        )

    # Le Super Administrateur est un rôle plateforme : il reçoit une
    # appartenance NON principale à chaque entité, afin de pouvoir basculer
    # entre FEBA et FEBA FHA. Sans appartenance principale, sa connexion le
    # laisse en mode « toutes les entités ».
    for su in User.objects.filter(role="superadmin").iterator():
        for org in School.objects.all().iterator():
            Membership.objects.get_or_create(
                user_id=su.id,
                organization_id=org.id,
                defaults={
                    "role": "superadmin",
                    "status": "active",
                    "is_primary": False,
                },
            )


def backwards(apps, schema_editor):
    """
    Retour arrière NON DESTRUCTIF : on retire les codes et les
    appartenances générées, mais on ne supprime PAS l'entité FEBA FHA ni
    aucune donnée métier qui aurait pu lui être rattachée entre-temps.
    """
    School = apps.get_model("schools", "School")
    Membership = apps.get_model("schools", "OrganizationMembership")

    Membership.objects.all().delete()
    School.objects.filter(code__in=["FEBA", FHA_CODE]).update(code=None)


class Migration(migrations.Migration):

    dependencies = [
        ("schools", "0012_school_code_school_currency_school_default_language_and_more"),
        # `CustomUser.school` doit exister pour le rétro-remplissage des
        # appartenances : on dépend de la migration qui l'ajoute, pas de
        # 0001_initial (dont le modèle historique n'a pas encore ce champ).
        ("accounts", "0003_customuser_school"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
