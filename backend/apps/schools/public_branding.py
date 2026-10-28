"""
Identité PUBLIQUE d'une académie : logo effectif, favicons, titre de
visioconférence, couleurs. Lecture seule, sans authentification.

Pourquoi : le site public et la page de connexion n'ont pas de jeton ;
`/schools/branding/active/` leur répondait 401 et ils affichaient toujours
le logo statique du frontend, quel que soit le logo activé. Le client
plugNmeet (autre domaine, sans session FEBA) a besoin du même titre et du
même favicon que l'application.

Rien d'administratif n'est exposé : ni réglages, ni versions archivées, ni
fonction d'écriture. Le logo servi est exactement celui que
`branding.get_branding()` retient pour les documents.

Cache : chaque URL porte `?v=<version>` (empreinte du fichier effectif).
Une nouvelle activation change la version, donc l'URL : navigateurs et
proxys ne peuvent pas resservir l'ancienne image, sans désactiver le cache.
"""
import hashlib
import io
import os

from django.conf import settings

from .branding import get_branding

FAVICON_SIZES = (16, 32, 180)


def _file_digest(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def branding_version(academy):
    """Empreinte courte de l'identité visuelle effective (logo + favicons)."""
    brand = get_branding(academy)
    parts = [brand.academy_code, brand.meeting_title]
    for path in (brand.logo, brand.favicon_16, brand.favicon_32, brand.apple_touch_icon):
        parts.append(_file_digest(path) if path and os.path.exists(path) else "-")
    return hashlib.sha256("|".join(parts).encode()).hexdigest()[:12]


def logo_file(academy):
    """Chemin du logo effectif (téléversé et activé, sinon repli de l'académie), ou None."""
    path = get_branding(academy).logo
    return path if path and os.path.exists(path) else None


def favicon_png(academy, size):
    """
    Favicon `size`×`size` de l'académie, en PNG.

    Fichier livré pour l'académie (FEBA : favicons fournis) tant qu'aucun
    logo n'a été téléversé et activé ; sinon dérivé du logo actif, au carré,
    fond transparent. Le dérivé est mis en cache sur disque par version.
    """
    if size not in FAVICON_SIZES:
        raise ValueError("Taille de favicon non prise en charge.")
    brand = get_branding(academy)
    delivered = {16: brand.favicon_16, 32: brand.favicon_32, 180: brand.apple_touch_icon}[size]
    if delivered and os.path.exists(delivered):
        with open(delivered, "rb") as fh:
            return fh.read()
    source = logo_file(academy)
    if source is None:
        # Académie sans aucune image (créée depuis l'écran « Académies ») :
        # monogramme à SES couleurs. Sans cela l'URL annoncée répondait 404
        # et l'onglet gardait le favicon de la page précédente — celui de
        # FEBA, c'est-à-dire l'identité d'une autre académie.
        return _monogram_png(brand, size)
    version = branding_version(academy)
    cache_dir = os.path.join(settings.MEDIA_ROOT, "branding", "favicons")
    cached = os.path.join(cache_dir, f"{brand.academy_code or academy.pk}-{version}-{size}.png")
    if os.path.exists(cached):
        with open(cached, "rb") as fh:
            return fh.read()
    from PIL import Image
    with Image.open(source) as img:
        img = img.convert("RGBA")
        side = max(img.size)
        canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
        canvas.paste(img, ((side - img.width) // 2, (side - img.height) // 2))
        canvas = canvas.resize((size, size), Image.LANCZOS)
        buf = io.BytesIO()
        canvas.save(buf, format="PNG", optimize=True)
    data = buf.getvalue()
    try:
        os.makedirs(cache_dir, exist_ok=True)
        with open(cached, "wb") as fh:
            fh.write(data)
    except OSError:
        pass  # cache facultatif
    return data


def _initials(name):
    words = [w for w in str(name or "").replace("_", " ").replace("-", " ").split()
             if w.lower() not in {"de", "du", "des", "la", "le", "les", "d'", "l'"}]
    return "".join(w[0] for w in words[:2]).upper() or "?"


def _monogram_png(brand, size):
    """Carré à la couleur principale de l'académie, initiales en blanc."""
    from PIL import Image, ImageDraw, ImageFont

    color = brand.primary_color or "#334155"
    image = Image.new("RGBA", (size, size), color)
    draw = ImageDraw.Draw(image)
    text = _initials(brand.short_name or brand.display_name)
    font = ImageFont.load_default(size=max(8, int(size * (0.5 if len(text) > 1 else 0.62))))
    left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
    draw.text(((size - (right - left)) / 2 - left, (size - (bottom - top)) / 2 - top),
              text, font=font, fill="white")
    buf = io.BytesIO()
    image.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def public_payload(academy, build_url):
    """Données publiques ; `build_url(suffix)` construit l'URL d'un fichier de l'académie."""
    brand = get_branding(academy)
    v = branding_version(academy)
    return {
        "academy_code": brand.academy_code,
        "display_name": brand.display_name,
        "short_name": brand.short_name,
        "meeting_title": brand.meeting_title,
        "version": v,
        "logo_url": build_url(f"logo/?v={v}") if logo_file(academy) else None,
        "favicon_16_url": build_url(f"favicon-16.png?v={v}"),
        "favicon_32_url": build_url(f"favicon-32.png?v={v}"),
        "apple_touch_icon_url": build_url(f"favicon-180.png?v={v}"),
        "logo_is_uploaded": brand.logo_is_uploaded,
        "primary_color": brand.primary_color,
        "secondary_color": brand.secondary_color,
        "accent_color": brand.accent_color,
    }
