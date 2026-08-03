"""
Relève la géométrie réelle d'un fond de document.

POURQUOI UNE COMMANDE, ET NON UN SCRIPT JETABLE
-----------------------------------------------
Le calibrage consiste à faire coïncider des coordonnées écrites dans un
gabarit avec ce que le graphiste a réellement dessiné. Tant que ces
coordonnées sont saisies « à l'œil », personne ne peut vérifier d'où elles
viennent, ni les refaire quand le visuel change.

Cette commande MESURE : elle repère les règles d'écriture, les zones de
texte doré et les médaillons, et exprime tout en millimètres dans le
repère du gabarit. Ce qu'elle imprime est reportable tel quel dans le
JSON, et reproductible.

CE QU'ELLE NE FAIT PAS
----------------------
Elle ne décide pas où va le nom de l'élève. Reconnaître l'intention d'un
graphiste dans une image se tromperait en silence, et son résultat aurait
l'air aussi sûr qu'une mesure. Elle donne des repères ; l'opérateur choisit.
"""
import os

from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Mesure la géométrie d'une image de fond (règles, textes, médaillons)."

    def add_arguments(self, parser):
        parser.add_argument("--file", required=True, help="Image à mesurer.")
        parser.add_argument("--page-width-mm", type=float, default=297.0)
        parser.add_argument("--page-height-mm", type=float, default=210.0)
        parser.add_argument("--min-rule-width", type=int, default=90,
                            help="Largeur minimale d'une règle, en pixels.")

    def handle(self, *args, **options):
        try:
            import numpy as np
            from PIL import Image
        except ImportError as exc:
            raise CommandError(f"Outillage de mesure absent : {exc}")

        path = options["file"]
        if not os.path.exists(path):
            raise CommandError(f"Fichier introuvable : {path}")

        with Image.open(path) as image:
            array = np.asarray(image.convert("RGB")).astype(int)
        height, width = array.shape[:2]
        page_w, page_h = options["page_width_mm"], options["page_height_mm"]

        # Le fond est inscrit dans la page en conservant ses proportions :
        # la conversion pixel → mm doit utiliser CE facteur, sinon toutes
        # les mesures sont décalées d'un demi-millimètre.
        ratio = width / height
        if ratio >= page_w / page_h:
            draw_w, draw_h = page_w, page_w / ratio
        else:
            draw_w, draw_h = page_h * ratio, page_h
        off_x, off_y = (page_w - draw_w) / 2, (page_h - draw_h) / 2

        def to_mm_x(px):
            return off_x + px * draw_w / width

        def to_mm_y(py):
            return off_y + py * draw_h / height

        red, green, blue = array[..., 0], array[..., 1], array[..., 2]
        gold = (red > 130) & (green > 95) & (blue < green - 25) & (red > blue + 55)
        navy = (blue > red + 25) & (blue < 150) & (red < 90)

        self.stdout.write(self.style.MIGRATE_HEADING(
            f"\nGéométrie de {os.path.basename(path)} — {width}×{height} px\n"
        ))
        self.stdout.write(
            f"  Page {page_w}×{page_h} mm · fond rendu {draw_w:.2f}×{draw_h:.2f} mm "
            f"· décalage ({off_x:.3f}, {off_y:.3f}) mm\n"
            f"  Échelle : 1 px = {draw_w / width:.4f} mm en largeur, "
            f"{draw_h / height:.4f} mm en hauteur\n"
        )

        # ── Règles d'écriture ────────────────────────────────────────
        # Un trait fin et long : c'est sur lui que se pose un nom, une
        # date ou une signature. Les repérer donne les seules ancres
        # objectives du document.
        self.stdout.write(self.style.MIGRATE_HEADING("  Règles horizontales dorées"))
        rules = []
        for y in range(height):
            cols = np.where(gold[y])[0]
            if len(cols) < options["min_rule_width"]:
                continue
            segments, start = [], cols[0]
            for i in range(1, len(cols)):
                if cols[i] - cols[i - 1] > 6:
                    segments.append((start, cols[i - 1]))
                    start = cols[i]
            segments.append((start, cols[-1]))
            for x0, x1 in segments:
                if x1 - x0 >= options["min_rule_width"]:
                    band = gold[max(0, y - 6):y + 7, x0:x1 + 1]
                    # Une règle est FINE : si la colonne est pleine sur
                    # douze pixels de haut, c'est un ornement, pas un trait.
                    if band.mean() < 0.55:
                        rules.append((y, int(x0), int(x1)))

        merged = []
        for y, x0, x1 in rules:
            if merged and y - merged[-1][1] <= 3 and abs(x0 - merged[-1][2]) < 25:
                merged[-1] = (merged[-1][0], y, min(merged[-1][2], x0),
                              max(merged[-1][3], x1))
            else:
                merged.append((y, y, x0, x1))

        for y0, y1, x0, x1 in merged:
            self.stdout.write(
                f"    y {y0:4}–{y1:<4} x {x0:4}–{x1:<4} "
                f"│ {to_mm_x(x0):7.2f} → {to_mm_x(x1):7.2f} mm  "
                f"y {to_mm_y(y0):6.2f} mm  largeur {to_mm_x(x1) - to_mm_x(x0):6.2f} mm"
            )

        # ── Blocs de texte doré ──────────────────────────────────────
        self.stdout.write(self.style.MIGRATE_HEADING("\n  Blocs dorés (hors bordures)"))
        inner = np.zeros_like(gold)
        m = int(width * 0.13)
        inner[:, m:width - m] = gold[:, m:width - m]
        profile = inner.sum(axis=1)
        threshold = max(8, profile.max() * 0.05)
        blocks, start = [], None
        for y in range(height):
            if profile[y] > threshold and start is None:
                start = y
            elif profile[y] <= threshold and start is not None:
                if y - start >= 6:
                    blocks.append((start, y - 1))
                start = None
        for y0, y1 in blocks:
            sub = inner[y0:y1 + 1]
            cols = np.where(sub.any(axis=0))[0]
            if not len(cols):
                continue
            x0, x1 = int(cols.min()), int(cols.max())
            self.stdout.write(
                f"    y {y0:4}–{y1:<4} x {x0:4}–{x1:<4} "
                f"│ {to_mm_x(x0):7.2f} → {to_mm_x(x1):7.2f} mm  "
                f"y {to_mm_y(y0):6.2f} → {to_mm_y(y1):6.2f} mm"
            )

        # ── Médaillons ───────────────────────────────────────────────
        # Un disque doré dense : c'est un sceau. Le repérer permet de
        # remplacer SON INTÉRIEUR sans toucher à la médaille elle-même.
        self.stdout.write(self.style.MIGRATE_HEADING("\n  Médaillons (disques dorés denses)"))
        step = 12
        seen = []
        for cy in range(step, height - step, step):
            for cx in range(step, width - step, step):
                win = gold[cy - step:cy + step, cx - step:cx + step]
                if win.mean() < 0.72:
                    continue
                if any(abs(cx - sx) < 90 and abs(cy - sy) < 90 for sx, sy in seen):
                    continue
                seen.append((cx, cy))
        for cx, cy in seen:
            r = step
            while r < 160:
                ring = gold[max(0, cy - r):cy + r, max(0, cx - r):cx + r]
                if ring.mean() < 0.42:
                    break
                r += 6
            self.stdout.write(
                f"    centre ({cx:4}, {cy:4}) rayon ≈{r:3} px "
                f"│ ({to_mm_x(cx):6.2f}, {to_mm_y(cy):6.2f}) mm  "
                f"⌀ {2 * r * draw_w / width:5.2f} mm"
            )

        self.stdout.write(
            "\n  Ces mesures sont des REPÈRES. Reportez-les dans le gabarit, "
            "puis\n  vérifiez avec « document_calibrate » et "
            "« document_compare ».\n"
        )
