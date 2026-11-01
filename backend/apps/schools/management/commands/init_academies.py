"""
Initialise les deux académies FEBA et garantit leur cohérence.

Idempotent : peut être relancé sans effet de bord. Utilisé par
`make install` (scripts/bootstrap.sh) et sûr en production.

Ne crée AUCUNE donnée commerciale non validée (tarifs, dates de rentrée,
horaires, enseignants) : ces champs restent nuls et administrables.
"""
from django.core.management.base import BaseCommand

from apps.schools.branding import ACADEMY_DEFAULTS, IMAGE_DEFAULT_KEYS
from apps.schools.institution import is_retired_phone, official_phone
from apps.schools.models import School


class Command(BaseCommand):
    help = "Crée / met à jour les académies FEBA et FEBA French Heritage Academy."

    def _apply_branding(self, academy):
        """
        Installe l'identité visuelle de l'académie, sans jamais écraser une
        valeur déjà administrée par l'établissement.
        """
        # Les images livrées (logo de repli, favicons) restent des valeurs du
        # CODE : recopiées ici, elles passaient pour un choix administré et
        # empêchaient tout nouveau logo livré de s'appliquer.
        wanted = {k: v for k, v in (ACADEMY_DEFAULTS.get(academy.code or "") or {}).items()
                  if k not in IMAGE_DEFAULT_KEYS}
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

    def _align_management_phones(self):
        """
        Aligne la colonne de gestion sur le numéro institutionnel.

        Deux cas, une seule raison. Les documents ne lisent plus cette
        colonne (voir `apps/schools/institution.py`) : rien d'imprimé n'en
        dépend, et le défaut d'origine est corrigé sans y toucher. Mais
        l'écran « Paramètres » l'affiche toujours, et un administrateur
        s'y fie.

          * un numéro RETIRÉ y ferait croire que le groupe est encore
            joignable par une ligne qui ne répond plus ;
          * une colonne VIDE laisse penser qu'aucun numéro n'est publié,
            alors que tous les documents en portent un.

        Un numéro déjà renseigné et non retiré n'est JAMAIS écrasé : c'est
        une donnée de gestion légitime (la ligne directe d'un campus), et
        la faire disparaître serait une perte d'information.
        """
        changed = False
        for academy in School.objects.all():
            if is_retired_phone(academy.phone):
                previous = academy.phone
                academy.phone = official_phone()
                academy.save(update_fields=["phone"])
                changed = True
                self.stdout.write(self.style.WARNING(
                    f"  Numéro hors service remplacé sur {academy.name} : "
                    f"{previous} → {academy.phone}"
                ))
            elif not (academy.phone or "").strip() and academy.code in ACADEMY_DEFAULTS:
                # Seules les académies du GROUPE reçoivent le numéro
                # institutionnel : une académie indépendante garde une
                # colonne vide plutôt que le numéro d'une autre institution.
                academy.phone = official_phone()
                academy.save(update_fields=["phone"])
                changed = True
                self.stdout.write(
                    f"  Numéro institutionnel renseigné sur {academy.name} : "
                    f"{academy.phone}"
                )
        return changed

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
                "phone": official_phone(),
                "timezone": "Africa/Porto-Novo",
                "currency_code": "XOF",
                "default_language": "fr",
                "matricule_prefix": "FEBA",
                "curriculum_language_mode": School.CURRICULUM_BILINGUAL,
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
                "address": "Programme 100 % en ligne - cours dispensés depuis FEBA, Cotonou, Bénin.",
                "city": "Cotonou",
                "country": "Bénin",
                "phone": official_phone(),
                "whatsapp": "+1 (215) 715-5406",
                "timezone": "America/New_York",
                "currency_code": "USD",
                "default_language": "en",
                "matricule_prefix": "FHA",
                "curriculum_language_mode": School.CURRICULUM_BILINGUAL,
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

        # Barème d'appréciations de chaque académie : une COPIE du barème par
        # défaut, modifiable dans « Appréciations ». Sans elle, une académie
        # créée ici (installation neuve) n'avait aucun palier à modifier.
        from apps.grades.appreciations import install_default_rules
        for academy in (feba, fha):
            if install_default_rules(academy):
                created_any = True
                self.stdout.write(f"  Barème d'appréciations installé : {academy.name}")

        # Programme linguistique : les deux académies du groupe enseignent en
        # français ET en anglais (bulletin à deux sections, moyenne 60/40) ;
        # FEBA FHA garde ses classes monolingues (fonctionnalité de l'entité).
        # Jamais écrasé : seule une valeur VIDE est complétée.
        for academy in (feba, fha):
            if not academy.curriculum_language_mode:
                academy.curriculum_language_mode = School.CURRICULUM_BILINGUAL
                academy.save(update_fields=["curriculum_language_mode"])
                created_any = True
                self.stdout.write(f"  Programme linguistique : bilingue - {academy.name}")

        created_any |= self._align_management_phones()

        if not created_any:
            self.stdout.write("Aucune modification - les deux académies existaient déjà.")
