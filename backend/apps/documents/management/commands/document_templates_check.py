"""
État réel des gabarits de documents officiels.

Répond à une seule question, sans détour : **peut-on délivrer un diplôme
sur cette instance, oui ou non, et si non pourquoi.**
"""
from django.core.management.base import BaseCommand

from apps.documents.templates_registry import (
    TemplateError, available_templates, load_template,
)


class Command(BaseCommand):
    help = "Vérifie la présence, l'empreinte et le calibrage des gabarits."

    def add_arguments(self, parser):
        parser.add_argument(
            "--strict", action="store_true",
            help="Code de sortie non nul si un gabarit ne peut pas émettre.",
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING(
            "\nGabarits de documents officiels\n"
        ))

        template_ids = available_templates()
        if not template_ids:
            self.stdout.write(self.style.ERROR("  Aucun gabarit trouvé."))
            if options["strict"]:
                raise SystemExit(1)
            return

        unusable = 0
        for template_id in template_ids:
            try:
                template = load_template(template_id, use_cache=False)
            except TemplateError as exc:
                unusable += 1
                self.stdout.write(self.style.ERROR(f"  ✗ {template_id} — gabarit invalide"))
                self.stdout.write(f"      {exc.messages[0] if exc.messages else exc}")
                continue

            blockers = template.issuance_blockers()
            marker = self.style.SUCCESS("✓") if not blockers else self.style.ERROR("✗")
            self.stdout.write(f"  {marker} {template.label} ({template.id} v{template.version})")
            self.stdout.write(
                f"      Fond        : {template.background_file} "
                f"({template.background_width_px}×{template.background_height_px} px)"
            )
            self.stdout.write(
                f"      Installé    : "
                f"{'oui' if template.background_installed else 'NON'}"
            )
            self.stdout.write(
                f"      Calibré     : {'oui' if template.calibrated else 'NON'} "
                f"(tolérance {template.tolerance_mm} mm)"
            )
            self.stdout.write(f"      Champs      : {len(template.fields)}")

            if blockers:
                unusable += 1
                self.stdout.write(self.style.WARNING("      Émission impossible :"))
                for blocker in blockers:
                    self.stdout.write(f"        - {blocker}")
            self.stdout.write("")

        if unusable:
            self.stdout.write(self.style.WARNING(
                f"  {unusable} gabarit(s) sur {len(template_ids)} ne peuvent pas "
                f"émettre de document.\n"
                f"  Un aperçu filigrané « NON CALIBRÉ » reste disponible pour "
                f"travailler la mise en page.\n"
            ))
            if options["strict"]:
                raise SystemExit(1)
        else:
            self.stdout.write(self.style.SUCCESS(
                "  Tous les gabarits peuvent émettre.\n"
            ))
