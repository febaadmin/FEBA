#!/usr/bin/env python3
"""
Construit les ressources d'identité FEBA à partir des fichiers FOURNIS.

Sources (jamais modifiées) : branding/source/
  - feba_logo_transparent.png  logo principal transparent (1280 × 1280)
  - favicon-16x16.png          favicon 16 × 16
  - favicon-32x32.png          favicon 32 × 32

Sorties (régénérables, versionnées pour que le dépôt fonctionne sans Pillow) :
  frontend/public/favicon-16x16.png, favicon-32x32.png   copies exactes
  frontend/public/apple-touch-icon.png                    180 × 180, dérivé du logo
  frontend/src/assets/feba_logo.png                       256 × 256, dérivé du logo
  backend/feba_project/static_files/feba_logo_document.png 400 × 400 (PDF : un logo
      de 2 Mo embarqué dans chaque bulletin alourdirait chaque document)
  backend/feba_project/static_files/favicon-16x16.png, favicon-32x32.png,
      apple-touch-icon.png                                favicons par défaut de FEBA

Usage : python3 scripts/build_branding_assets.py [--check]
  --check : vérifie que les sorties correspondent aux sources (CI), sans écrire.

Les réductions utilisent LANCZOS et un PNG sans métadonnées : la sortie est
identique d'une exécution à l'autre pour une même version de Pillow.
"""
import hashlib
import io
import shutil
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "branding" / "source"
LOGO = SRC / "feba_logo_transparent.png"
FRONT_PUBLIC = ROOT / "frontend" / "public"
FRONT_ASSETS = ROOT / "frontend" / "src" / "assets"
STATIC = ROOT / "backend" / "feba_project" / "static_files"


def resized(size):
    img = Image.open(LOGO).convert("RGBA")
    img = img.resize((size, size), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def outputs():
    copies = {
        FRONT_PUBLIC / "favicon-16x16.png": (SRC / "favicon-16x16.png").read_bytes(),
        FRONT_PUBLIC / "favicon-32x32.png": (SRC / "favicon-32x32.png").read_bytes(),
        STATIC / "favicon-16x16.png": (SRC / "favicon-16x16.png").read_bytes(),
        STATIC / "favicon-32x32.png": (SRC / "favicon-32x32.png").read_bytes(),
    }
    apple = resized(180)
    copies[FRONT_PUBLIC / "apple-touch-icon.png"] = apple
    copies[STATIC / "apple-touch-icon.png"] = apple
    copies[FRONT_ASSETS / "feba_logo.png"] = resized(256)
    copies[STATIC / "feba_logo_document.png"] = resized(400)
    return copies


def main():
    check = "--check" in sys.argv
    bad = []
    for path, data in outputs().items():
        if check:
            if not path.exists() or path.read_bytes() != data:
                bad.append(str(path.relative_to(ROOT)))
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        print(f"{hashlib.sha256(data).hexdigest()[:12]}  {path.relative_to(ROOT)}")
    if check:
        if bad:
            print("Ressources d'identité à régénérer :", *bad, sep="\n  ")
            sys.exit(1)
        print("Ressources d'identité conformes aux sources fournies.")


if __name__ == "__main__":
    main()
