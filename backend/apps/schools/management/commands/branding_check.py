"""
Vérifie l'identité visuelle de chaque académie.

Répond à une question simple : si un document était produit maintenant pour
cette académie, porterait-il la bonne identité ? La commande ne corrige
rien — elle constate, et sort en erreur si une académie produirait un
document sous une identité incomplète.

    python manage.py branding_check
    python manage.py branding_check --strict   # sort 1 au moindre défaut
"""
from django.core.management.base import BaseCommand

from apps.schools.branding import get_branding
from apps.schools.models import School

#: Champs sans lesquels un document officiel ne peut pas être considéré
#: comme correctement identifié.
ESSENTIAL = (
    ("legal_name", "dénomination légale"),
    ("display_name", "nom affiché"),
    ("short_name", "nom court"),
    ("postal_address", "adresse postale"),
    ("country", "pays"),
    ("currency_code", "devise"),
    ("document_prefix", "préfixe documentaire"),
)

#: Champs dont l'absence est signalée sans bloquer : ils dépendent de
#: fichiers que seul l'établissement peut fournir.
OPTIONAL_ASSETS = (
    ("document_logo", "logo documentaire"),
    ("stamp", "cachet"),
    ("director_signature", "signature de la direction"),
    ("secretary_stamp", "cachet du secrétariat"),
)


class Command(BaseCommand):
    help = "Contrôle l'identité visuelle (branding) de chaque académie."

    def add_arguments(self, parser):
        parser.add_argument(
            "--strict", action="store_true",
            help="Sortir en erreur si une ressource facultative manque aussi.",
        )

    def handle(self, *args, **options):
        academies = School.objects.order_by("id")
        if not academies:
            self.stdout.write(self.style.WARNING("Aucune académie en base."))
            return

        blocking = 0
        warnings = 0

        for academy in academies:
            branding = get_branding(academy)
            self.stdout.write("")
            self.stdout.write(self.style.MIGRATE_HEADING(
                f"{branding.display_name} [{branding.academy_code or 'sans code'}]"
            ))
            self.stdout.write(
                f"  devise {branding.currency_code} {branding.currency_symbol} · "
                f"langue {branding.language} · fuseau {branding.timezone or '—'}"
            )
            self.stdout.write(
                f"  couleurs {branding.primary_color} / {branding.secondary_color} / "
                f"{branding.accent_color}"
            )

            for field, label in ESSENTIAL:
                if not getattr(branding, field):
                    blocking += 1
                    self.stdout.write(self.style.ERROR(f"  ✗ {label} manquant"))

            if branding.palette_is_neutral:
                warnings += 1
                self.stdout.write(self.style.WARNING(
                    "  ! palette neutre — cette académie n'a pas encore ses "
                    "propres couleurs (settings['branding'])"
                ))

            for field, label in OPTIONAL_ASSETS:
                if not getattr(branding, field):
                    warnings += 1
                    self.stdout.write(self.style.WARNING(
                        f"  ! {label} absent — la zone restera vide "
                        f"(aucune image n'est inventée)"
                    ))

        self.stdout.write("")
        if blocking:
            self.stderr.write(self.style.ERROR(
                f"{blocking} information(s) essentielle(s) manquante(s) : "
                "des documents sortiraient sans identité complète."
            ))
            raise SystemExit(1)

        if warnings and options["strict"]:
            self.stderr.write(self.style.ERROR(
                f"{warnings} avertissement(s) en mode strict."
            ))
            raise SystemExit(1)

        self.stdout.write(self.style.SUCCESS(
            f"{academies.count()} académie(s) — identité essentielle complète"
            + (f", {warnings} avertissement(s)" if warnings else "")
        ))
