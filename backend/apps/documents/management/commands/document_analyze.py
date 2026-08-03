"""
P1 — Mesurer un fond officiel, au lieu de le calibrer à l'œil.

POURQUOI CETTE COMMANDE EXISTE
------------------------------
Chaque coordonnée d'un gabarit — la ligne où s'écrit le nom de l'élève,
les règles de signature, la zone de date — est une mesure prise sur
l'image réelle. Les estimer « à vue » produit un document décalé de
quelques millimètres : personne ne s'en aperçoit à l'écran, tout le monde
le voit sur le papier, et il est trop tard, le diplôme est signé.

Cette commande fait la mesure, et rend des nombres vérifiables :

  - dimensions, ratio, résolution déclarée, mode colorimétrique,
    transparence, empreinte SHA-256 ;
  - marges réelles du contenu ;
  - **règles horizontales** : les traits sur lesquels se posent le nom,
    les signatures et la date. Ce sont les ancres de calibrage ;
  - **bandes de texte** : les zones d'écriture, dont les mentions
    d'exemple à neutraliser.

CE QUI VALIDE CETTE COMMANDE
----------------------------
Elle est vérifiée contre les fonds FEBA déjà calibrés à la main lors
d'une itération précédente. Le test `test_document_analyze.py` lui
demande de retrouver, sans aide, les quatre ancres inscrites dans
`diploma_feba_template.json` — la règle du nom à y=692, celles du
directeur et de l'enseignant à y=886, celle de la date à y=920. Un outil
de mesure qu'on n'a pas confronté à une vérité connue ne mesure rien.
"""
import hashlib
import json
import os

from django.core.management.base import BaseCommand, CommandError

#: Un pixel est « sombre » en dessous de cette luminance. Les règles
#: dorées d'un diplôme ivoire sont nettement plus foncées que le fond
#: sans être noires : un seuil sur le noir pur ne les verrait pas.
DARK_THRESHOLD = 200

#: Une règle horizontale couvre une large part de sa zone. En dessous,
#: c'est un mot, une ornementation ou du bruit de compression.
RULE_MIN_COVERAGE = 0.10

#: Deux lignes sombres séparées par moins que cela appartiennent au même
#: objet (une règle épaisse, une ligne de texte).
MERGE_GAP_PX = 3

#: Écart horizontal au-delà duquel deux tronçons encrés sont deux traits
#: DISTINCTS. Les règles « DIRECTEUR » et « ENSEIGNANT » d'un diplôme
#: sont à la même hauteur, séparées par le sceau central : sans cette
#: séparation, elles se confondent en une seule ancre traversant le décor.
SEGMENT_GAP_PX = 12


def image_facts(path):
    """Les faits bruts du fichier, sans interprétation."""
    from PIL import Image

    with open(path, "rb") as handle:
        octets = handle.read()

    with Image.open(path) as image:
        largeur, hauteur = image.size
        mode = image.mode
        dpi = image.info.get("dpi")
        transparence = (mode in ("RGBA", "LA", "PA")
                        or "transparency" in image.info)
        format_ = image.format

    return {
        "fichier": os.path.basename(path),
        "chemin": path,
        "octets": len(octets),
        "sha256": hashlib.sha256(octets).hexdigest(),
        "format": format_,
        "largeur_px": largeur,
        "hauteur_px": hauteur,
        "ratio": round(largeur / hauteur, 5),
        "orientation": "paysage" if largeur > hauteur else "portrait",
        "mode_colorimetrique": mode,
        "resolution_dpi": list(dpi) if dpi else None,
        "transparence": transparence,
    }


def _dark_mask(path):
    import numpy as np
    from PIL import Image

    with Image.open(path) as image:
        gris = image.convert("L")
        return np.asarray(gris) < DARK_THRESHOLD


def content_margins(mask):
    """Marges du contenu, en pixels, depuis chaque bord."""
    import numpy as np

    lignes = np.where(mask.any(axis=1))[0]
    colonnes = np.where(mask.any(axis=0))[0]
    if not len(lignes) or not len(colonnes):
        return None
    hauteur, largeur = mask.shape
    return {
        "haut_px": int(lignes[0]),
        "bas_px": int(hauteur - 1 - lignes[-1]),
        "gauche_px": int(colonnes[0]),
        "droite_px": int(largeur - 1 - colonnes[-1]),
    }


def _merge_runs(rows, gap=MERGE_GAP_PX):
    """Regroupe des numéros de ligne voisins en intervalles."""
    if not rows:
        return []
    groupes = [[rows[0], rows[0]]]
    for y in rows[1:]:
        if y - groupes[-1][1] <= gap:
            groupes[-1][1] = y
        else:
            groupes.append([y, y])
    return groupes


def _row_segments(row, min_length):
    """Tronçons d'encre continus d'une ligne, en (x_debut, x_fin)."""
    import numpy as np

    colonnes = np.where(row)[0]
    if not len(colonnes):
        return []
    segments = []
    for x_debut, x_fin in _merge_runs([int(c) for c in colonnes],
                                      gap=SEGMENT_GAP_PX):
        if x_fin - x_debut + 1 >= min_length:
            segments.append((x_debut, x_fin))
    return segments


def horizontal_rules(mask, band=None, min_length=40, max_thickness=12):
    """
    Les traits horizontaux : règles d'écriture, de signature, de date.

    ALGORITHME, ET POURQUOI CELUI-CI
    --------------------------------
    Une première version raisonnait LIGNE PAR LIGNE : elle retenait les
    lignes suffisamment encrées, les fusionnait, puis écartait les blocs
    trop épais. Confrontée aux ancres mesurées à la main, elle en
    manquait une sur quatre — la règle de DATE. La raison : à cette
    hauteur, la courbe décorative bleu marine des angles inférieurs
    encre déjà ~400 pixels par ligne. Une dizaine de lignes passaient
    donc le seuil, se fondaient en un bloc de plus de douze pixels
    d'épaisseur, et le trait disparaissait avec le bloc.

    On raisonne donc par TRONÇONS. Chaque ligne est découpée en segments
    d'encre continus ; les segments de lignes voisines qui se recouvrent
    horizontalement forment un même trait. Le décor et la règle
    cohabitent alors sans se confondre, parce qu'ils n'occupent pas les
    mêmes colonnes.

    `band` restreint la recherche à une plage de colonnes : la bordure
    décorative court sur toute la largeur et serait sinon prise pour une
    règle d'écriture.
    """
    hauteur, largeur = mask.shape
    x0, x1 = band if band else (0, largeur)
    zone = mask[:, x0:x1]

    #: Traits en cours de construction : {(x_debut, x_fin) : [y_debut, y_fin]}
    ouverts = []
    termines = []

    for y in range(zone.shape[0]):
        segments = _row_segments(zone[y], min_length)
        encore = []
        for trait in ouverts:
            correspondance = None
            for segment in segments:
                # Recouvrement horizontal d'au moins la moitié du plus
                # court des deux : deux traits distincts qui se frôlent
                # ne doivent pas fusionner.
                debut = max(trait["x_debut"], segment[0])
                fin = min(trait["x_fin"], segment[1])
                recouvrement = fin - debut + 1
                court = min(trait["x_fin"] - trait["x_debut"] + 1,
                            segment[1] - segment[0] + 1)
                if recouvrement > 0 and recouvrement >= 0.5 * court:
                    correspondance = segment
                    break
            if correspondance is not None:
                trait["y_fin"] = y
                trait["x_debut"] = min(trait["x_debut"], correspondance[0])
                trait["x_fin"] = max(trait["x_fin"], correspondance[1])
                segments.remove(correspondance)
                encore.append(trait)
            else:
                termines.append(trait)
        for segment in segments:
            encore.append({"y_debut": y, "y_fin": y,
                           "x_debut": segment[0], "x_fin": segment[1]})
        ouverts = encore
    termines.extend(ouverts)

    regles = []
    for trait in termines:
        epaisseur = trait["y_fin"] - trait["y_debut"] + 1
        # Un trait est PLAT. Un bloc de texte ou un ornement est haut.
        if epaisseur > max_thickness:
            continue
        longueur = trait["x_fin"] - trait["x_debut"] + 1
        if longueur < min_length:
            continue
        regles.append({
            "y_debut_px": trait["y_debut"],
            "y_fin_px": trait["y_fin"],
            "epaisseur_px": epaisseur,
            "x_debut_px": trait["x_debut"] + x0,
            "x_fin_px": trait["x_fin"] + x0,
            "longueur_px": longueur,
        })
    return sorted(regles, key=lambda r: (r["y_debut_px"], r["x_debut_px"]))


def text_bands(mask, band=None, min_coverage=0.008, max_coverage=RULE_MIN_COVERAGE):
    """
    Les bandes d'écriture : lignes assez encrées pour porter du texte,
    mais pas assez continues pour être un trait.
    """
    import numpy as np

    hauteur, largeur = mask.shape
    x0, x1 = band if band else (0, largeur)
    zone = mask[:, x0:x1]
    couverture = zone.sum(axis=1) / zone.shape[1]
    candidates = [int(y) for y in np.where(
        (couverture >= min_coverage) & (couverture < max_coverage))[0]]

    bandes = []
    for debut, fin in _merge_runs(candidates, gap=6):
        if fin - debut < 4:  # trop mince pour être une ligne de texte
            continue
        segment = zone[debut:fin + 1]
        colonnes = np.where(segment.any(axis=0))[0]
        if not len(colonnes):
            continue
        bandes.append({
            "y_debut_px": debut,
            "y_fin_px": fin,
            "hauteur_px": fin - debut + 1,
            "x_debut_px": int(colonnes[0]) + x0,
            "x_fin_px": int(colonnes[-1]) + x0,
        })
    return bandes


def px_to_mm(valeur_px, largeur_px, page_width_mm=297.0):
    """Conversion pixel → millimètre pour un fond ajusté en largeur."""
    return round(valeur_px * page_width_mm / largeur_px, 2)


def analyze(path, page_width_mm=297.0, inner_ratio=0.72):
    """
    Analyse complète d'un fond.

    `inner_ratio` délimite la zone centrale examinée pour les règles :
    les bordures décoratives courent sur toute la largeur et seraient
    sinon prises pour des règles d'écriture.

    Réglé à 0,90 après confrontation à la vérité connue : à 0,72, la
    règle de DATE — proche du bord droit — tombait hors de la zone
    examinée et n'était jamais trouvée. Un outil de mesure qui ignore
    silencieusement une ancre est pire qu'absent : on le croit complet.
    """
    faits = image_facts(path)
    mask = _dark_mask(path)
    largeur = faits["largeur_px"]

    # DEUX BANDES, ET LA RAISON.
    #
    # Une bande étroite (0,72) ignore la règle de DATE, proche du bord
    # droit. Une bande large (0,90) laisse entrer la courbe décorative
    # bleu marine des angles inférieurs : des dizaines de lignes
    # dépassent alors le seuil d'encrage, se fondent en un seul bloc
    # trop épais, et les règles de SIGNATURE disparaissent.
    #
    # Chaque bande voit ce que l'autre manque. On les cumule, puis on
    # dédoublonne. Choisir une seule valeur revenait à perdre
    # silencieusement une ancre sur quatre — et un outil de mesure qui
    # omet sans le dire est pire qu'absent : on le croit complet.
    faits["marges_contenu"] = content_margins(mask)

    brutes = []
    for ratio in (inner_ratio, 0.90):
        marge = int(largeur * (1 - ratio) / 2)
        brutes.extend(horizontal_rules(mask, band=(marge, largeur - marge)))

    # La bande étroite coupe les traits proches du bord : la règle de
    # DATE en ressort tronquée (x 1138–1283 au lieu de 1138–1314). Les
    # deux versions décrivent le MÊME trait ; on garde la plus longue,
    # c'est-à-dire celle qui n'a pas été rognée par la fenêtre d'analyse.
    retenues = []
    for regle in sorted(brutes, key=lambda r: -r["longueur_px"]):
        doublon = any(
            abs(regle["y_debut_px"] - autre["y_debut_px"]) <= 2
            and regle["x_debut_px"] <= autre["x_fin_px"]
            and autre["x_debut_px"] <= regle["x_fin_px"]
            for autre in retenues
        )
        if not doublon:
            retenues.append(regle)

    faits["regles_horizontales"] = [
        {**regle,
         "y_mm": px_to_mm(regle["y_debut_px"], largeur, page_width_mm),
         "x_debut_mm": px_to_mm(regle["x_debut_px"], largeur, page_width_mm),
         "x_fin_mm": px_to_mm(regle["x_fin_px"], largeur, page_width_mm)}
        for regle in sorted(retenues,
                            key=lambda r: (r["y_debut_px"], r["x_debut_px"]))
    ]
    faits["bandes_de_texte"] = [
        {**bande,
         "y_mm": px_to_mm(bande["y_debut_px"], largeur, page_width_mm),
         "hauteur_mm": px_to_mm(bande["hauteur_px"], largeur, page_width_mm)}
        for bande in text_bands(
            mask, band=(int(largeur * (1 - inner_ratio) / 2),
                        largeur - int(largeur * (1 - inner_ratio) / 2)))
    ]
    faits["mm_par_px"] = round(page_width_mm / largeur, 5)
    return faits


class Command(BaseCommand):
    help = ("Mesure un fond de document officiel : dimensions, empreinte, "
            "marges, règles d'écriture et bandes de texte.")

    def add_arguments(self, parser):
        parser.add_argument("images", nargs="+",
                            help="Chemins des PNG à analyser.")
        parser.add_argument("--json", action="store_true",
                            help="Sortie JSON, exploitable par un script.")
        parser.add_argument("--page-width-mm", type=float, default=297.0,
                            help="Largeur de la page cible (A4 paysage par défaut).")

    def handle(self, *args, **options):
        resultats = []
        for chemin in options["images"]:
            if not os.path.exists(chemin):
                raise CommandError(f"Fichier introuvable : {chemin}")
            resultats.append(analyze(chemin, options["page_width_mm"]))

        if options["json"]:
            self.stdout.write(json.dumps(resultats, ensure_ascii=False, indent=2))
            return

        for faits in resultats:
            self.stdout.write(self.style.MIGRATE_HEADING(f"\n{faits['fichier']}"))
            self.stdout.write(
                f"  {faits['largeur_px']} × {faits['hauteur_px']} px  "
                f"({faits['orientation']}, ratio {faits['ratio']})")
            self.stdout.write(
                f"  mode {faits['mode_colorimetrique']}  ·  "
                f"transparence : {'oui' if faits['transparence'] else 'non'}  ·  "
                f"résolution : {faits['resolution_dpi'] or 'non déclarée'}")
            self.stdout.write(f"  SHA-256 : {faits['sha256']}")
            self.stdout.write(f"  1 px = {faits['mm_par_px']} mm")
            if faits["marges_contenu"]:
                m = faits["marges_contenu"]
                self.stdout.write(
                    f"  marges du contenu : haut {m['haut_px']}  bas {m['bas_px']}"
                    f"  gauche {m['gauche_px']}  droite {m['droite_px']} px")

            self.stdout.write("  règles horizontales (ancres de calibrage) :")
            for regle in faits["regles_horizontales"]:
                self.stdout.write(
                    f"    y {regle['y_debut_px']}–{regle['y_fin_px']}  "
                    f"x {regle['x_debut_px']}–{regle['x_fin_px']}  "
                    f"({regle['longueur_px']} px, {regle['y_mm']} mm)")

            self.stdout.write("  bandes de texte :")
            for bande in faits["bandes_de_texte"]:
                self.stdout.write(
                    f"    y {bande['y_debut_px']}–{bande['y_fin_px']}  "
                    f"x {bande['x_debut_px']}–{bande['x_fin_px']}  "
                    f"({bande['hauteur_px']} px)")
