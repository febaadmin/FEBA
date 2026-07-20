#!/usr/bin/env python3
"""
Optimisation des médias du site vitrine FEBA (P4 v4).

Source   : archive fournie IMG_vid (57 PNG ~2 Mo chacun + video1.mov 73 Mo).
           Les ORIGINAUX ne sont JAMAIS modifiés ni supprimés.
Sortie   : frontend/public/site/  — copies optimisées pour le web :
           - <slug>-1600.webp (hero, pleine largeur, lightbox)
           - <slug>-800.webp  (cartes, grilles, mosaïque galerie)
           - video/feba-presentation.mp4 (H.264 compressé, ~10 Mo)
           - video/feba-presentation-poster.webp (affiche cliquable)

Usage :
    python3 scripts/optimize_site_media.py [--src /chemin/vers/IMG_vid]

Nécessite Pillow ; ffmpeg pour la vidéo (sinon étape vidéo sautée).
Le mapping UUID → slug sémantique est documenté dans MEDIA_INVENTORY.md.
"""
import argparse
import shutil
import subprocess
import sys
from pathlib import Path

try:
    from PIL import Image
except ImportError:  # pragma: no cover
    sys.exit("Pillow requis : pip install Pillow")

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "frontend" / "public" / "site"

# ── Mapping : fichier source (préfixe UUID) → slug sémantique ────────────────
# Sélection éditoriale : chaque slug correspond à un emplacement du site
# vitrine (voir MEDIA_INVENTORY.md pour la description de chaque visuel).
MAPPING = {
    # Carrousel / heros
    "ad9e0dc6": "hero-campus",            # grand bâtiment académie, ciel bleu
    "03240d6b": "hero-bilingue",          # enseignante, livres Français/English
    "f08d185a": "hero-vie-scolaire",      # ronde d'enfants dans la cour (espace négatif)
    "182bfd8a": "hero-excellence",        # élèves collaborant sur un projet
    "15fdd070": "hero-admissions",        # famille accueillie par une responsable
    # Campus
    "028e7d0c": "campus-garderie-maternelle",  # façade rouge/crème garderie-maternelle
    "6302672d": "campus-facade",               # façade FEBA vue rapprochée
    "652399ec": "campus-batiment",             # bâtiment principal, palmiers
    "0fb2b2d8": "campus-cour",                 # enfants jouant dans la cour
    # Niveaux
    "b924bb36": "niveau-garderie",        # petits, blocs éducatifs
    "ff3dd775": "niveau-garderie-jeux",   # jeux de construction colorés
    "0ef89dcf": "niveau-maternelle",      # activités couleurs et formes
    "de6007a2": "niveau-maternelle-cour", # marelle, fresque murale
    "385db627": "niveau-primaire",        # élèves écrivant en classe
    "858d64f0": "niveau-primaire-lecture",# lecture en classe
    # Académique
    "2c4fc8fa": "academique-classe",      # enseignante au tableau
    "4efe3f20": "academique-carte",       # cours avec carte du monde
    "2c1e8a46": "academique-lecture",     # deux élèves lisant
    "5fdac19c": "academique-bibliotheque",# lecture en bibliothèque
    "d8fd92d7": "academique-sciences",    # expérience scientifique
    "a0166b9d": "academique-numerique",   # robotique et ordinateur
    "c5808504": "academique-participation", # élèves levant la main
    # Bilinguisme
    "2e76e906": "bilingue-accompagnement",  # enseignante avec deux élèves
    # Accompagnement / valeurs
    "20f1d147": "accompagnement-individuel",
    "49e1fa47": "accompagnement-duo",
    "2c75f2fe": "valeurs-equipe",
    "ab35c86f": "valeurs-projet",
    # Vie scolaire / activités
    "00d302b8": "activite-musique-atelier",   # atelier musique avec enseignant
    "aa3cb9e6": "activite-musique-groupe",    # groupe guitare/batterie/chant
    "adbaf9bb": "activite-musique-scene",
    "c58f0b8c": "activite-percussions",       # djembé, héritage culturel
    "5e15c55b": "activite-arts",              # peinture
    "21b12b06": "activite-football-cour",
    "facbe521": "activite-football",          # gazon, maillots sport
    "c9177c7d": "activite-expression",        # élève au micro
    "ffd2ee74": "activite-ronde",             # ronde d'enfants
    # FEBA Online
    "1576cf4c": "online-visio",           # visioconférence
    "3e6f75cb": "online-cours-francais",  # laptop cours de français
    "ff8bfa27": "online-lecon",           # casque + leçon en ligne
    # Admissions / contact
    "478e3767": "admissions-famille",     # famille dans le couloir
    "a27417c7": "admissions-visite",      # famille visite guidée
    "9e3b46c3": "admissions-accueil",     # échange avec l'accueil
    "ee230580": "admissions-bienvenue",
    "4e835291": "contact-accueil",        # réceptionniste FEBA
    "f872c720": "contact-administration", # bureau administration
    # À propos
    "6dd81966": "apropos-direction",      # bureau de direction
    "c06e94c1": "apropos-direction-2",
    "ba066112": "apropos-encadrement",    # portrait professionnel
    "cc8af6c0": "apropos-equipe",         # équipe pédagogique
    # Galerie (compléments + variantes + collages)
    "35302c29": "galerie-projet",
    "3e3ecff2": "galerie-ecriture",
    "59510f62": "galerie-etude",
    "ccb2c1bd": "galerie-devoirs",
    "5010d5ea": "galerie-soutien",
    "2ec00d74": "galerie-mosaique-1",     # collage multi-scènes
    "ba9a5133": "galerie-mosaique-2",
    "49619860": "galerie-mosaique-3",
}

SIZES = {1600: 82, 800: 80}  # largeur max → qualité WebP


def optimize_images(src: Path) -> int:
    (OUT / "img").mkdir(parents=True, exist_ok=True)
    done = 0
    for png in sorted(src.glob("*.png")):
        slug = MAPPING.get(png.name[:8])
        if not slug:
            continue
        with Image.open(png) as im:
            im = im.convert("RGB")
            for width, quality in SIZES.items():
                target = OUT / "img" / f"{slug}-{width}.webp"
                copy = im.copy()
                if copy.width > width:
                    ratio = width / copy.width
                    copy = copy.resize((width, round(copy.height * ratio)), Image.LANCZOS)
                copy.save(target, "WEBP", quality=quality, method=6)
        done += 1
    return done


def optimize_video(src: Path):
    mov = src / "video1.mov"
    if not mov.exists():
        print("⚠️  video1.mov absente — étape vidéo sautée")
        return
    if not shutil.which("ffmpeg"):
        print("⚠️  ffmpeg introuvable — étape vidéo sautée")
        return
    vdir = OUT / "video"
    vdir.mkdir(parents=True, exist_ok=True)
    mp4 = vdir / "feba-presentation.mp4"
    # H.264 + AAC, 1280 de large, CRF 27 : ~10 Mo pour 52 s, compatible partout.
    subprocess.run([
        "ffmpeg", "-y", "-i", str(mov),
        "-vf", "scale=1280:-2", "-c:v", "libx264", "-crf", "27",
        "-preset", "medium", "-movflags", "+faststart",
        "-c:a", "aac", "-b:a", "96k", str(mp4),
    ], check=True, capture_output=True)
    # Affiche (poster) à ~3 s, convertie en WebP.
    poster_png = vdir / "_poster_tmp.png"
    subprocess.run([
        "ffmpeg", "-y", "-ss", "3", "-i", str(mov), "-frames:v", "1", str(poster_png),
    ], check=True, capture_output=True)
    with Image.open(poster_png) as im:
        im = im.convert("RGB")
        if im.width > 1280:
            im = im.resize((1280, round(im.height * 1280 / im.width)), Image.LANCZOS)
        im.save(vdir / "feba-presentation-poster.webp", "WEBP", quality=80, method=6)
    poster_png.unlink()
    print(f"🎬 vidéo : {mp4.stat().st_size // 1048576} Mo (originale conservée : {mov})")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--src", default="/Users/m.chris/Desktop/FEBA/Medias/IMG_vid")
    args = parser.parse_args()
    src = Path(args.src)
    if not src.is_dir():
        sys.exit(f"Source introuvable : {src}")
    n = optimize_images(src)
    total = sum(f.stat().st_size for f in (OUT / "img").glob("*.webp")) // 1048576
    print(f"🖼  {n} images optimisées → {OUT/'img'} ({total} Mo au total)")
    optimize_video(src)


if __name__ == "__main__":
    main()
