"""
Comparaison pixel à pixel entre le PDF produit et le fond original.

CE QUE MESURE CETTE COMMANDE
----------------------------
Elle rend le document, le rastérise à la résolution exacte du fond
original, et compare les deux images point par point — en excluant les
ZONES VARIABLES.

La question posée n'est donc pas « le document est-il joli », mais :
**le moteur a-t-il déplacé ou altéré quelque chose du fond ?** Une
bordure, un logo, un sceau statique, un ornement : tout écart s'y voit et
s'y chiffre.

POURQUOI MASQUER LES ZONES VARIABLES
------------------------------------
Le nom de l'élève, la date, le numéro et le sceau appliqué SONT censés
différer du fond : c'est leur raison d'être. Les compter comme des écarts
noierait, sous des dizaines de milliers de pixels attendus, le décalage
d'un millimètre qu'on cherche à détecter.

Les zones masquées sont exactement celles que le gabarit déclare — champs,
assets, masques de placeholder. Rien n'est exclu « parce que ça diffère » :
tout ce qui est exclu est déclaré à l'avance.

CE QUE LA TOLÉRANCE COUVRE, ET CE QU'ELLE NE COUVRE PAS
--------------------------------------------------------
Un fond JPEG ou WebP ré-encodé, puis rastérisé depuis un PDF, ne redonne
jamais les octets de départ : la compression déplace les valeurs de
quelques niveaux. Le seuil `--tolerance` absorbe ce bruit. Il n'absorbe
PAS un décalage géométrique : déplacer une bordure d'un seul pixel change
brutalement des milliers de points, très au-delà du seuil.
"""
import json
import os

from django.core.management.base import BaseCommand, CommandError

from apps.documents.renderer import render_document
from apps.schools.branding import get_branding_by_code
from apps.documents.templates_registry import (
    TemplateError, available_templates, load_template,
)


class Command(BaseCommand):
    help = "Compare pixel à pixel le rendu PDF et le fond original."

    def add_arguments(self, parser):
        parser.add_argument("--template", required=True,
                            help=f"Gabarit ({', '.join(available_templates())}).")
        parser.add_argument("--output-dir", default="comparaison")
        # P0 — la comparaison porte sur le document RÉELLEMENT produit, donc
        # sur celui d'une académie précise (son cachet, sa signature).
        parser.add_argument("--academy", default="FEBA",
                            help="Code interne de l'académie émettrice.")
        parser.add_argument("--tolerance", type=int, default=16,
                            help="Écart par canal en deçà duquel deux pixels sont "
                                 "réputés identiques (0-255, défaut 16).")
        parser.add_argument("--max-diff-ratio", type=float, default=1.0,
                            help="Pourcentage de pixels différents au-delà duquel "
                                 "la commande échoue (défaut 1,0 %%).")
        parser.add_argument("--margin-mm", type=float, default=1.0,
                            help="Marge ajoutée autour de chaque zone variable, "
                                 "pour absorber l'antialiasing de ses bords.")

    def handle(self, *args, **options):
        try:
            template = load_template(options["template"], use_cache=False)
        except TemplateError as exc:
            raise CommandError(exc.messages[0] if exc.messages else str(exc))

        if not template.background_installed:
            raise CommandError(
                f"Le fond « {template.background_file} » n'est pas installé : "
                f"il n'y a rien à comparer. Une comparaison sans référence "
                f"produirait un score inventé."
            )
        template.verify_background()

        try:
            import fitz  # PyMuPDF
            from PIL import Image, ImageChops, ImageDraw
        except ImportError as exc:
            raise CommandError(
                f"Outillage de comparaison absent ({exc}). "
                f"Installez : pip install -r requirements/dev.txt"
            )

        out = options["output_dir"]
        os.makedirs(out, exist_ok=True)
        width = template.background_width_px
        height = template.background_height_px

        # ── Rendu avec des valeurs réalistes ──────────────────────────
        # Un document VIDE ne prouverait rien sur les zones variables ;
        # elles sont de toute façon masquées. Le remplir garantit en
        # revanche que le rendu comparé est bien celui qu'on livre.
        values = {}
        for field in template.fields:
            if field.type == "date":
                values[field.name] = "01/01/2026"
            elif field.name == "student_name":
                values[field.name] = "Exemple Comparaison"
            else:
                values[field.name] = "—"
        content = render_document(template.id, values,
                                  branding=get_branding_by_code(options["academy"]))

        pdf_path = os.path.join(out, f"rendu_{template.id}.pdf")
        with open(pdf_path, "wb") as handle:
            handle.write(content)

        document = fitz.open(pdf_path)
        page = document[0]
        pixmap = page.get_pixmap(
            matrix=fitz.Matrix(width / page.rect.width, height / page.rect.height),
            alpha=False,
        )
        rendered_path = os.path.join(out, f"rendu_{template.id}.png")
        pixmap.save(rendered_path)
        document.close()

        rendered = Image.open(rendered_path).convert("RGB")
        original = Image.open(template.background_path).convert("RGB")
        if rendered.size != original.size:
            rendered = rendered.resize(original.size, Image.LANCZOS)

        # ── Masque des zones variables ────────────────────────────────
        page_w, page_h = template.page_width_mm, template.page_height_mm
        ratio = width / height
        if ratio >= page_w / page_h:
            draw_w, draw_h = page_w, page_w / ratio
        else:
            draw_w, draw_h = page_h * ratio, page_h
        off_x, off_y = (page_w - draw_w) / 2, (page_h - draw_h) / 2
        margin = options["margin_mm"]

        variable = Image.new("L", original.size, 0)
        painter = ImageDraw.Draw(variable)
        zones = []
        for item in template.all_boxes:
            box = item.box
            # Marge globale + débord propre au champ : un nom avec jambages
            # descend sous sa ligne de base, et cette descente appartient
            # à la zone variable, pas au fond.
            pad = margin + getattr(item, "bleed_mm", 0.0)
            x0 = int((box.x_mm - pad - off_x) * width / draw_w)
            y0 = int((box.y_mm - pad - off_y) * height / draw_h)
            x1 = int((box.x_mm + box.width_mm + pad - off_x) * width / draw_w)
            y1 = int((box.y_mm + box.height_mm + pad - off_y) * height / draw_h)
            painter.rectangle([x0, y0, x1, y1], fill=255)
            zones.append({
                "nom": item.name,
                "px": [max(0, x0), max(0, y0), min(width, x1), min(height, y1)],
                "mm": [round(box.x_mm, 2), round(box.y_mm, 2),
                       round(box.width_mm, 2), round(box.height_mm, 2)],
                "debord_mm": round(getattr(item, "bleed_mm", 0.0), 2),
            })
        mask_path = os.path.join(out, f"masque_variables_{template.id}.png")
        variable.save(mask_path)

        # ── Différence sur les zones STATIQUES ────────────────────────
        difference = ImageChops.difference(rendered, original)
        tolerance = options["tolerance"]
        diff_data = difference.getdata()
        mask_data = variable.getdata()

        total_static = 0
        differing = 0
        max_delta = 0
        worst = None
        for index, pixel in enumerate(diff_data):
            if mask_data[index]:
                continue
            total_static += 1
            delta = max(pixel)
            if delta > max_delta:
                max_delta = delta
                worst = index
            if delta > tolerance:
                differing += 1

        ratio_pct = differing * 100.0 / max(1, total_static)

        # Image de différence : zones variables grisées, écarts amplifiés.
        amplified = difference.point(lambda value: min(255, value * 8)).convert("RGB")
        overlay = Image.new("RGB", original.size, (40, 40, 60))
        amplified.paste(overlay, (0, 0), variable.point(lambda v: 90 if v else 0))
        diff_path = os.path.join(out, f"difference_{template.id}.png")
        amplified.save(diff_path)

        report = {
            "gabarit": template.id,
            "version": template.version,
            "fond": os.path.basename(template.background_path),
            "fond_est_original": template.is_original,
            "fond_variante": (template.installed_variant.as_dict()
                              if template.installed_variant else None),
            "resolution_px": [width, height],
            "tolerance_par_canal": tolerance,
            "marge_zones_variables_mm": margin,
            "pixels_statiques": total_static,
            "pixels_statiques_differents": differing,
            "pourcentage_different": round(ratio_pct, 4),
            "score_fidelite": round(100 - ratio_pct, 4),
            "ecart_maximal_canal": max_delta,
            "ecart_maximal_position_px": (
                [worst % width, worst // width] if worst is not None else None
            ),
            "zones_variables_exclues": zones,
        }
        report_path = os.path.join(out, f"comparaison_{template.id}.json")
        with open(report_path, "w", encoding="utf-8") as handle:
            json.dump(report, handle, ensure_ascii=False, indent=2)
            handle.write("\n")

        self.stdout.write(self.style.MIGRATE_HEADING(
            f"\nComparaison — {template.label}\n"
        ))
        self.stdout.write(
            f"  Fond original    : {template.background_path}\n"
            f"  Rendu            : {rendered_path}\n"
            f"  Masque variables : {mask_path}\n"
            f"  Différence       : {diff_path}\n"
            f"  Rapport          : {report_path}\n"
            f"  Résolution       : {width}×{height} px\n"
        )
        if not template.is_original:
            self.stdout.write(self.style.WARNING(
                "  ⚠ Le fond installé est une VARIANTE acceptée, pas le PNG "
                "d'origine.\n    Le score porte donc sur la fidélité au fichier "
                "réellement installé.\n"
            ))
        self.stdout.write(
            f"  Zones variables exclues : {len(zones)} "
            f"({100 - total_static * 100.0 / (width * height):.1f} % de la page)\n"
            f"  Pixels statiques comparés : {total_static}\n"
            f"  Au-delà de la tolérance ({tolerance}) : {differing} "
            f"= {ratio_pct:.4f} %\n"
            f"  Écart maximal : {max_delta}/255\n"
        )
        self.stdout.write(self.style.MIGRATE_HEADING(
            f"  Score de fidélité des zones statiques : {100 - ratio_pct:.4f} %\n"
        ))

        if ratio_pct > options["max_diff_ratio"]:
            self.stdout.write(self.style.ERROR(
                f"  ✗ Écart supérieur au seuil ({options['max_diff_ratio']} %).\n"
                f"    Ouvrez l'image de différence : les zones claires montrent "
                f"où le fond\n    a été altéré. Un décalage géométrique s'y voit "
                f"comme un contour double.\n"
            ))
            raise SystemExit(1)

        self.stdout.write(self.style.SUCCESS(
            "  ✓ Aucune zone statique déplacée ni altérée au-delà du bruit "
            "de compression.\n"
        ))
