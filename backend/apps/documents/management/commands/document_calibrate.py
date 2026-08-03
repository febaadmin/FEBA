"""
Produit la planche de calibrage d'un gabarit.

COMMENT ON CALIBRE
------------------
1. Cette commande génère un PDF : le fond original, recouvert d'une grille
   millimétrée et d'un rectangle rouge par zone déclarée.
2. On l'ouvre à 100 %, ou on l'imprime sans mise à l'échelle.
3. On lit l'écart entre chaque rectangle et l'emplacement réellement prévu
   par le graphiste sur le fond.
4. On corrige les coordonnées dans le fichier `*_template.json`.
5. On recommence jusqu'à ce que l'écart soit inférieur à la tolérance
   (0,2 mm), puis on passe `calibrated` à `true`.

L'étape 5 n'est pas décorative : tant que `calibrated` vaut `false`, le
moteur refuse d'émettre et filigrane tout ce qu'il produit.

POURQUOI PAS D'AUTOMATISME
--------------------------
Détecter automatiquement « l'endroit où le nom doit aller » supposerait de
reconnaître l'intention d'un graphiste dans une image. Un tel automatisme
se tromperait en silence, et son résultat aurait l'air aussi sûr qu'une
mesure. La grille, elle, ne décide rien : elle rend l'écart visible.
"""
import os

from django.core.management.base import BaseCommand, CommandError

from apps.documents.renderer import render_document
from apps.documents.templates_registry import (
    TemplateError, available_templates, load_template,
)


class Command(BaseCommand):
    help = "Génère la planche de calibrage (grille millimétrée) d'un gabarit."

    def add_arguments(self, parser):
        parser.add_argument("--template", required=True,
                            help=f"Gabarit ({', '.join(available_templates())}).")
        parser.add_argument("--output", help="Chemin du PDF produit.")
        parser.add_argument(
            "--sample-name", default="ABCDEFGHIJKLM NOPQRSTUVWXYZ",
            help="Texte témoin placé dans les champs — sert à voir les débordements.",
        )

    def handle(self, *args, **options):
        try:
            template = load_template(options["template"], use_cache=False)
        except TemplateError as exc:
            raise CommandError(exc.messages[0] if exc.messages else str(exc))

        if not template.background_installed:
            raise CommandError(
                f"Le fond « {template.background_file} » n'est pas installé : "
                f"il n'y a rien à calibrer. Une grille sur une page blanche "
                f"n'apprend rien.\n"
                f"Voir document_templates/originals/README.md."
            )
        template.verify_background()

        import datetime

        values = {
            field.name: (
                datetime.date.today() if field.type == "date"
                else options["sample_name"]
            )
            for field in template.fields
        }
        values["document_number"] = "XXXX-XXX-0000-0000"

        try:
            content = render_document(
                template.id, values, preview=True, calibration_grid=True,
            )
        except Exception as exc:
            raise CommandError(f"Rendu impossible : {exc}")

        output = options["output"] or os.path.join(
            os.getcwd(), f"calibrage_{template.id}_v{template.version}.pdf",
        )
        with open(output, "wb") as handle:
            handle.write(content)

        self.stdout.write(self.style.SUCCESS(f"\n  ✓ Planche de calibrage : {output}"))
        self.stdout.write(
            f"\n  Grille : trait tous les 10 mm, marqué tous les 50 mm.\n"
            f"  Rectangles rouges : zones déclarées dans "
            f"{os.path.basename(template.path)}.\n"
            f"  Tolérance à atteindre : {template.tolerance_mm} mm.\n"
            f"\n  Ouvrez ce PDF à 100 % (sans « ajuster à la page »), relevez "
            f"les écarts,\n  corrigez les coordonnées du gabarit, puis "
            f"relancez cette commande.\n"
            f"  Quand tout est en place, passez « calibrated » à true dans le "
            f"gabarit.\n"
        )
        if template.provisional_layout:
            self.stdout.write(self.style.WARNING(
                "  ⚠ Ce gabarit porte « provisional_layout: true » : ses "
                "coordonnées sont\n    des valeurs de départ, jamais "
                "confrontées à l'image. Attendez-vous à\n    des écarts "
                "importants au premier passage.\n"
            ))
