#!/usr/bin/env python3
"""
Fabrique le PDF téléchargeable du flyer FEBA French Heritage Academy.

POURQUOI UN PDF ALORS QUE LE FLYER EXISTE DÉJÀ EN JPEG
------------------------------------------------------
Le lien « Voir le détail des formules » doit TÉLÉCHARGER le flyer. Sur un
`<a download>` pointant une image, les navigateurs mobiles (Safari iOS en
particulier) ouvrent le plus souvent l'image dans l'onglet au lieu de
l'enregistrer : l'attribut `download` y est diversement honoré. Un PDF, lui,
est traité comme un document à enregistrer, s'ouvre partout et s'imprime à
l'échelle — ce qu'une famille fait d'un flyer de tarifs.

Le JPEG reste servi tel quel pour l'APERÇU affiché dans la page ; le PDF est
la cible du téléchargement. Les deux montrent le même visuel.

FIDÉLITÉ
--------
Le contenu marketing n'est pas retouché : aucun texte, aucune couleur,
aucun recadrage. Le seul traitement est un ré-encodage du JPEG source, qui
est PROGRESSIF, vers du JPEG BASELINE — le filtre `DCTDecode` de PDF ne
couvre que le baseline, et un flux progressif produit un PDF que certains
lecteurs affichent en noir. Le ré-encodage est fait en qualité 97, sans
sous-échantillonnage de la chrominance (4:4:4), ce qui préserve la netteté
des textes fins du flyer (les tarifs « 1 299 $ »).

La page a exactement le ratio de l'image, à 150 ppp : aucune bande blanche,
aucune déformation.

USAGE
-----
    python3 scripts/build_fha_flyer_pdf.py

Le fichier produit est VERSIONNÉ dans le dépôt : un utilisateur qui installe
le projet n'a aucune commande à lancer pour que le téléchargement marche.
Ce script ne sert qu'à le régénérer si le visuel officiel change.
"""
from __future__ import annotations

import hashlib
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOURCE = os.path.join(
    REPO, "frontend", "public", "images", "feba-fha", "feba-fha-flyer.jpeg")
TARGET = os.path.join(
    REPO, "frontend", "public", "images", "feba-fha", "feba-fha-flyer.pdf")

#: Résolution d'impression du visuel. 150 ppp donne une page d'environ
#: 19 x 23,7 cm pour un flyer de 1122 x 1402 px : proche d'un A4 sans en
#: forcer le ratio, donc sans bande blanche ni recadrage.
DPI = 150


def build(source=SOURCE, target=TARGET):
    import tempfile

    from PIL import Image

    with Image.open(source) as image:
        image.load()
        if image.mode != "RGB":
            image = image.convert("RGB")
        width_px, height_px = image.size

        # Page au ratio exact de l'image (en points PostScript : 1/72 pouce).
        width_pt = width_px * 72.0 / DPI
        height_pt = height_px * 72.0 / DPI

        # Ré-encodage BASELINE sur disque, puis remise du CHEMIN à ReportLab.
        #
        # Ce détour n'est pas cosmétique. ReportLab n'embarque le flux JPEG
        # tel quel (filtre DCTDecode, ~300 Ko) que si on lui passe un
        # CHEMIN de fichier JPEG. Passé un objet PIL, il ré-encode en Flate
        # sans perte : visuellement identique, mais 3 Mo — trois secondes de
        # téléchargement sur une connexion mobile, pour un flyer d'une page.
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
            baseline = tmp.name
        try:
            image.save(baseline, format="JPEG", quality=97,
                       optimize=True, progressive=False, subsampling=0)

            from reportlab.pdfgen import canvas

            pdf = canvas.Canvas(target, pagesize=(width_pt, height_pt))
            pdf.setTitle("FEBA French Heritage Academy — flyer officiel")
            pdf.setAuthor("Groupe éducatif FEBA")
            pdf.setSubject(
                "Programme de français en ligne pour la diaspora — formules "
                "annuelles et informations pratiques")
            # `preserveAspectRatio` est redondant avec une page au bon ratio :
            # il est passé pour qu'une modification future des dimensions ne
            # déforme pas le visuel silencieusement.
            pdf.drawImage(
                baseline, 0, 0, width=width_pt, height=height_pt,
                preserveAspectRatio=True, anchor="c",
            )
            pdf.showPage()
            pdf.save()
        finally:
            os.unlink(baseline)

    digest = hashlib.sha256(open(target, "rb").read()).hexdigest()
    print(f"source  : {source}")
    print(f"          {width_px}x{height_px} px")
    print(f"cible   : {target}")
    print(f"page    : {width_pt:.1f} x {height_pt:.1f} pt "
          f"({width_pt / 72 * 25.4:.0f} x {height_pt / 72 * 25.4:.0f} mm)")
    print(f"taille  : {os.path.getsize(target)} octets")
    print(f"sha256  : {digest}")
    return target


if __name__ == "__main__":
    if not os.path.exists(SOURCE):
        sys.exit(f"Visuel source introuvable : {SOURCE}")
    build()
