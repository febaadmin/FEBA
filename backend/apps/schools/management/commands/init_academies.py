"""
Initialise les deux académies FEBA et garantit leur cohérence.

Idempotent : peut être relancé sans effet de bord. Utilisé par
`make install` (scripts/bootstrap.sh) et sûr en production.

Ne crée AUCUNE donnée commerciale non validée (tarifs, dates de rentrée,
horaires, enseignants) : ces champs restent nuls et administrables.
"""
from django.core.management.base import BaseCommand

from apps.schools.branding import ACADEMY_DEFAULTS
from apps.schools.models import School


class Command(BaseCommand):
    help = "Crée / met à jour les académies FEBA et FEBA French Heritage Academy."

    def _apply_branding(self, academy):
        """
        Installe l'identité visuelle de l'académie, sans jamais écraser une
        valeur déjà administrée par l'établissement.
        """
        wanted = ACADEMY_DEFAULTS.get(academy.code or "")
        if not wanted:
            return False
        settings_data = dict(academy.settings or {})
        current = dict(settings_data.get("branding") or {})
        added = {k: v for k, v in wanted.items() if not current.get(k)}
        if not added:
            return False
        current.update(added)
        settings_data["branding"] = current
        academy.settings = settings_data
        academy.save(update_fields=["settings"])
        self.stdout.write(
            f"  Identité visuelle complétée : {', '.join(sorted(added))}"
        )
        return True

    def handle(self, *args, **options):
        created_any = False

        feba, created = School.objects.get_or_create(
            code=School.CODE_FEBA,
            defaults={
                "name": "Faith & Excellence Bilingual Academy",
                "legal_name": "Faith & Excellence Bilingual Academy",
                "slug": "feba",
                "entity_type": "campus",
                "address": "Akpakpa, Cotonou, Bénin",
                "city": "Cotonou",
                "country": "Bénin",
                "timezone": "Africa/Porto-Novo",
                "currency_code": "XOF",
                "default_language": "fr",
                "matricule_prefix": "FEBA",
                "is_active": True,
            },
        )
        created_any |= created
        self.stdout.write(
            self.style.SUCCESS(f"{'Créée' if created else 'Présente'} : {feba.name} [{feba.code}]")
        )
        created_any |= self._apply_branding(feba)

        fha, created = School.objects.get_or_create(
            code=School.CODE_FEBA_FHA,
            defaults={
                "name": "FEBA French Heritage Academy",
                "legal_name": "FEBA French Heritage Academy",
                "slug": "feba-fha",
                "entity_type": "online",
                "address": "Programme 100 % en ligne — cours dispensés depuis FEBA, Cotonou, Bénin.",
                "city": "Cotonou",
                "country": "Bénin",
                "whatsapp": "+1 (215) 715-5406",
                "timezone": "America/New_York",
                "currency_code": "USD",
                "default_language": "en",
                "matricule_prefix": "FHA",
                "is_active": True,
                "settings": {
                    "tagline": "From English Speakers to Confident French Speakers",
                    # Informations NON validées par la direction : elles
                    # restent nulles et administrables. Ne jamais inventer.
                    "pending_direction_validation": {
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
                    },
                },
            },
        )
        created_any |= created
        self.stdout.write(
            self.style.SUCCESS(f"{'Créée' if created else 'Présente'} : {fha.name} [{fha.code}]")
        )
        created_any |= self._apply_branding(fha)

        if not created_any:
            self.stdout.write("Aucune modification — les deux académies existaient déjà.")
