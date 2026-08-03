"""
Neutralise les mentions d'exemple d'un fond de document.

LE PROBLÈME
-----------
Le visuel du diplôme porte « Nom Prénom » en anglaise dorée. C'est un
échantillon de mise en page, pas un contenu. Écrire le vrai nom par-dessus
le laisserait visible en dessous : deux noms superposés sur un document
officiel.

POURQUOI UNE IMAGE DÉRIVÉE, ET NON UN RECTANGLE DANS LE PDF
------------------------------------------------------------
Le fond n'est pas uni : c'est un parchemin texturé, traversé d'un filigrane
de lauriers. Un rectangle de couleur unie posé dans le PDF se verrait
immédiatement comme une pièce rapportée.

La neutralisation est donc faite sur l'IMAGE : pour chaque colonne de la
zone, la texture est reconstruite par interpolation entre une bande saine
prise au-dessus et une autre prise au-dessous. Le filigrane et le dégradé
suivent, parce qu'ils sont continus verticalement à cet endroit.

L'ORIGINAL N'EST JAMAIS MODIFIÉ
-------------------------------
Le résultat est écrit dans `derived/`, à côté. L'original reste la
référence de la comparaison pixel à pixel : c'est contre LUI qu'on
vérifie qu'aucune bordure, aucun ornement n'a bougé.
"""
import os

from django.core.management.base import BaseCommand, CommandError

from apps.documents.templates_registry import (
    DERIVED_DIR, TemplateError, available_templates, load_template, sha256_of,
)


class Command(BaseCommand):
    help = "Reconstruit la texture du fond sous les mentions d'exemple."

    def add_arguments(self, parser):
        parser.add_argument("--template", required=True,
                            help=f"Gabarit ({', '.join(available_templates())}).")
        parser.add_argument("--force", action="store_true",
                            help="Régénère même si le dérivé existe déjà.")

    def handle(self, *args, **options):
        try:
            template = load_template(options["template"], use_cache=False)
        except TemplateError as exc:
            raise CommandError(exc.messages[0] if exc.messages else str(exc))

        if not template.masks:
            self.stdout.write(
                f"  Le gabarit « {template.id} » ne déclare aucune mention "
                f"d'exemple à neutraliser. Rien à faire — le rendu utilisera "
                f"l'original."
            )
            return

        if not template.background_installed:
            raise CommandError(
                f"Le fond « {template.background_file} » n'est pas installé : "
                f"il n'y a rien à neutraliser."
            )
        template.verify_background()

        if os.path.exists(template.derived_path) and not options["force"]:
            self.stdout.write(self.style.SUCCESS(
                f"  ✓ Dérivé déjà présent : {template.derived_path}\n"
                f"    Utilisez --force pour le régénérer."
            ))
            return

        try:
            from PIL import Image
        except ImportError as exc:
            raise CommandError(f"Pillow requis : {exc}")

        image = Image.open(template.background_path).convert("RGB")
        width, height = image.size
        pixels = image.load()

        # Conversion mm → pixel : la même que celle du rendu, sinon le
        # masque ne tomberait pas où le moteur écrit.
        page_w, page_h = template.page_width_mm, template.page_height_mm
        ratio = width / height
        if ratio >= page_w / page_h:
            draw_w, draw_h = page_w, page_w / ratio
        else:
            draw_w, draw_h = page_h * ratio, page_h
        off_x, off_y = (page_w - draw_w) / 2, (page_h - draw_h) / 2

        def to_px_x(mm_value):
            return int(round((mm_value - off_x) * width / draw_w))

        def to_px_y(mm_value):
            return int(round((mm_value - off_y) * height / draw_h))

        self.stdout.write(self.style.MIGRATE_HEADING(
            f"\nNeutralisation — {template.label}\n"
        ))

        def band_median(y_center_mm, x0, x1):
            """
            Médiane par colonne d'une bande horizontale saine.

            La médiane, et non la moyenne : une poussière ou un reste
            d'antialiasing tirerait la moyenne, pas la médiane.
            """
            half = max(1, int(round(mask.sample_band_mm * height / draw_h / 2)))
            yc = to_px_y(y_center_mm)
            rows = range(max(0, yc - half), min(height, yc + half + 1))
            out = []
            for x in range(x0, x1):
                samples = [pixels[x, y] for y in rows]
                out.append(tuple(
                    sorted(s[c] for s in samples)[len(samples) // 2] for c in range(3)
                ))
            return out

        def neutraliser_medaillon(mask):
            """
            Repeint l'encre d'un médaillon sans toucher à son anneau.

            PREMIÈRE VERSION, ÉCARTÉE APRÈS INSPECTION DU RÉSULTAT
            ------------------------------------------------------
            Elle repérait l'encre par sa couleur : « rouge nettement
            supérieur au bleu », ce qui décrit le doré. Le rendu montrait
            « YOUR SEAL » toujours lisible en creux. Les lettres ne sont
            pas seulement dorées : elles sont gravées, avec une ombre
            portée PLUS SOMBRE que le fond marine. La règle de couleur
            attrapait le cœur doré et laissait tout le relief.

            VERSION RETENUE
            ---------------
            On ne cherche plus une couleur, on cherche un ÉCART. Pour
            chaque distance au centre, la couleur médiane du disque est
            calculée, puis tout pixel qui s'en écarte de plus de la
            tolérance est repeint avec cette médiane. Le doré comme
            l'ombre sont des écarts ; une structure radiale légitime — un
            liseré, un dégradé — EST la médiane à son rayon et se trouve
            donc préservée par construction.

            La médiane est recalculée trois fois en excluant les pixels
            déjà jugés aberrants : sur les anneaux que le texte couvre
            largement, la première médiane est encore tirée par l'encre.
            """
            import math

            cx, cy = to_px_x(mask.center_x_mm), to_px_y(mask.center_y_mm)
            rayon = int(round(mask.radius_mm * width / draw_w))
            tolerance = mask.ink_tolerance

            # Recensement par anneau d'un pixel de large.
            anneaux = {r: [] for r in range(rayon + 1)}
            for y in range(max(0, cy - rayon), min(height, cy + rayon + 1)):
                for x in range(max(0, cx - rayon), min(width, cx + rayon + 1)):
                    d = int(round(math.hypot(x - cx, y - cy)))
                    if d <= rayon:
                        anneaux[d].append((x, y))

            def mediane(echantillons):
                return tuple(
                    sorted(p[c] for p in echantillons)[len(echantillons) // 2]
                    for c in range(3)
                )

            def ecart(pixel, reference):
                return math.sqrt(sum((pixel[c] - reference[c]) ** 2
                                     for c in range(3)))

            # Couleur de référence de chaque anneau, et repérage de l'encre.
            reference_de = {}
            encre = set()
            for r, points in anneaux.items():
                if not points:
                    continue
                sains = [pixels[x, y] for x, y in points]
                reference = mediane(sains)
                for _ in range(6):
                    retenus = [p for p in sains if ecart(p, reference) <= tolerance]
                    if len(retenus) < 8:
                        break
                    nouvelle = mediane(retenus)
                    if nouvelle == reference:
                        break
                    reference = nouvelle
                reference_de[r] = reference
                for x, y in points:
                    if ecart(pixels[x, y], reference) > tolerance:
                        encre.add((x, y))

            # DILATATION — le détail qui décide du résultat.
            #
            # Repeindre les seuls pixels hors tolérance laisse le halo
            # d'antialiasing qui entoure chaque lettre : chaque pixel du
            # halo est individuellement « presque » la couleur du fond,
            # mais ensemble ils dessinent encore « YOUR SEAL », parfaitement
            # lisible. Mesuré sur le rendu : contraste résiduel de 46
            # niveaux sans dilatation, 33 avec trois passes.
            dans_le_disque = set()
            for points in anneaux.values():
                dans_le_disque.update(points)
            for _ in range(mask.ink_dilation):
                voisins = set()
                for x, y in encre:
                    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        candidat = (x + dx, y + dy)
                        if candidat in dans_le_disque:
                            voisins.add(candidat)
                encre |= voisins

            repeints = 0
            for x, y in encre:
                r = int(round(math.hypot(x - cx, y - cy)))
                reference = reference_de.get(r)
                if reference is not None:
                    pixels[x, y] = reference
                    repeints += 1

            self.stdout.write(
                f"  · {mask.name:26} médaillon centre ({cx},{cy}) "
                f"rayon {rayon} px  ·  tolérance {tolerance}"
                f"  ·  dilatation {mask.ink_dilation}"
                f"  ·  {repeints} pixel(s) repeint(s)"
            )
            if mask.note:
                self.stdout.write(f"    {mask.note}")

        for mask in template.masks:
            if mask.kind == "medaillon":
                neutraliser_medaillon(mask)
                continue
            x0, x1 = to_px_x(mask.box.x_mm), to_px_x(mask.box.x_mm + mask.box.width_mm)
            y0, y1 = to_px_y(mask.box.y_mm), to_px_y(mask.box.y_mm + mask.box.height_mm)
            x0, x1 = max(0, x0), min(width, x1)
            y0, y1 = max(0, y0), min(height, y1)
            if x1 <= x0 or y1 <= y0:
                continue

            top = (band_median(mask.sample_above_y_mm, x0, x1)
                   if mask.sample_above_y_mm is not None else None)
            bottom = (band_median(mask.sample_below_y_mm, x0, x1)
                      if mask.sample_below_y_mm is not None else None)

            # Lignes à ne pas toucher : la règle d'écriture.
            preserved = set()
            for zone in mask.preserve:
                for y in range(to_px_y(zone.y_mm),
                               to_px_y(zone.y_mm + zone.height_mm)):
                    preserved.add(y)

            span = max(1, y1 - y0)
            for index, x in enumerate(range(x0, x1)):
                a = top[index] if top else None
                b = bottom[index] if bottom else None
                for y in range(y0, y1):
                    if y in preserved:
                        continue
                    if a is not None and b is not None:
                        t = (y - y0) / span
                        pixels[x, y] = tuple(
                            int(round(a[c] * (1 - t) + b[c] * t)) for c in range(3)
                        )
                    else:
                        pixels[x, y] = a or b

            self.stdout.write(
                f"  · {mask.name:26} px x {x0}–{x1}  y {y0}–{y1}"
                f"  ({x1 - x0}×{y1 - y0})"
                + (f"  · {len(preserved)} ligne(s) préservée(s)" if preserved else "")
            )
            if mask.note:
                self.stdout.write(f"    {mask.note}")

        os.makedirs(DERIVED_DIR, exist_ok=True)
        # PNG sans perte : le dérivé sert au rendu, pas au stockage.
        image.save(template.derived_path, "PNG", optimize=True)
        digest = sha256_of(template.derived_path)

        self.stdout.write(self.style.SUCCESS(
            f"\n  ✓ Fond neutralisé : {template.derived_path}"
        ))
        self.stdout.write(
            f"    Empreinte : {digest}\n"
            f"    L'original reste intact et demeure la référence de la "
            f"comparaison pixel à pixel.\n"
        )
