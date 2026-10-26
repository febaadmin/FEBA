"""
apps/documents/academy_templates.py — Gabarits officiels téléversés par académie

CE QUE CE MODULE GARANTIT
-------------------------
Un fond téléversé n'est utilisé qu'après avoir prouvé qu'il PEUT produire
un document : fichier lisible et du format annoncé, page choisie, champs
positionnés dans la page sans se chevaucher, et un rendu d'essai dont le
texte relu contient chaque valeur écrite. Un fichier simplement déposé
reste « téléversé, non validé ».

FORMATS
-------
  - PDF : la page choisie est reprise TELLE QUELLE (vectorielle) ; les
    champs sont dessinés dans un calque fusionné par-dessus. Couleurs,
    bordures, signatures préimprimées ne sont pas rééchantillonnées.
  - PNG / JPEG : l'image est inscrite dans la page en conservant ses
    proportions (jamais étirée), centrée.
  - DOCX : REFUSÉ. Le convertir exigerait LibreOffice dans l'image du
    serveur (plusieurs centaines de Mo) et sa mise en page varie d'une
    version à l'autre ; un document officiel ne peut pas en dépendre.
    Un DOCX s'exporte en PDF depuis Word, puis se téléverse.

ISOLATION
---------
Rien ici ne reçoit un identifiant d'académie du navigateur : l'académie
est celle de l'élève (génération) ou celle résolue côté serveur pour
l'utilisateur (gestion). Le chemin de stockage est aléatoire et rangé par
académie ; il n'est jamais exposé.
"""
import io
import os
import re
import uuid

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone
from reportlab.lib.colors import HexColor
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfgen import canvas

from apps.documents.models import (
    AcademyDocumentTemplate,
    AcademyTemplateEvent,
    academy_templates_root,
)

#: Taille maximale d'un gabarit. Un fond A4 en PDF ou en PNG 300 dpi tient
#: largement en dessous ; au-delà, c'est un fichier mal exporté.
MAX_TEMPLATE_BYTES = 10 * 1024 * 1024
#: Pixels maximaux d'une image (protection contre les « bombes » de
#: décompression : un PNG de 50 Ko peut déclarer 100 000 × 100 000 px).
MAX_IMAGE_PIXELS = 40_000_000
#: Côté minimal : en dessous, le document imprimé serait flou.
MIN_IMAGE_SIDE_PX = 600
MAX_PDF_PAGES = 10
#: Résolution en dessous de laquelle l'impression est signalée médiocre.
MIN_PRINT_DPI = 150

ACCEPTED_EXTENSIONS = {
    ".pdf": AcademyDocumentTemplate.FORMAT_PDF,
    ".png": AcademyDocumentTemplate.FORMAT_PNG,
    ".jpg": AcademyDocumentTemplate.FORMAT_JPEG,
    ".jpeg": AcademyDocumentTemplate.FORMAT_JPEG,
}
ACCEPTED_MIME = {
    AcademyDocumentTemplate.FORMAT_PDF: {"application/pdf", "application/x-pdf"},
    AcademyDocumentTemplate.FORMAT_PNG: {"image/png"},
    AcademyDocumentTemplate.FORMAT_JPEG: {"image/jpeg", "image/pjpeg"},
}
#: Types que le navigateur envoie quand il ne sait pas : on se fie alors
#: au CONTENU, vérifié de toute façon.
GENERIC_MIME = {"", "application/octet-stream", "binary/octet-stream"}

#: Formats de page proposés pour un fond image (mm, largeur × hauteur).
PAGE_FORMATS = {
    "a4_landscape": (297.0, 210.0),
    "a4_portrait": (210.0, 297.0),
    "a5_landscape": (210.0, 148.0),
    "a5_portrait": (148.0, 210.0),
    "letter_landscape": (279.4, 215.9),
    "letter_portrait": (215.9, 279.4),
}

#: Polices proposées → police ReportLab. Les deux premières sont
#: embarquées (Crimson Pro, accents et ligatures complets) ; les polices
#: standard du PDF ne couvrent que le jeu Windows-1252 — un caractère hors
#: de ce jeu est REFUSÉ au rendu, jamais remplacé par un carré.
FONTS = {
    "serif": "FEBA-Text",
    "serif_italic": "FEBA-TextItalic",
    "sans": "Helvetica",
    "sans_bold": "Helvetica-Bold",
    "times": "Times-Roman",
}
EMBEDDED_FONT_KEYS = {"serif", "serif_italic"}

#: Champs que FEBA sait remplir À PARTIR DE SES DONNÉES, par type.
#: `source` dit d'où vient la valeur — elle n'est jamais inventée.
FIELD_CATALOG = {
    "student_name": {
        "label": "Nom complet de l'élève", "label_en": "Student full name",
        "kinds": {"diploma", "certificate"}, "source": "student",
    },
    "student_matricule": {
        "label": "Matricule", "label_en": "Student ID",
        "kinds": {"diploma", "certificate"}, "source": "student",
    },
    "student_birth_date": {
        "label": "Date de naissance", "label_en": "Date of birth",
        "kinds": {"diploma", "certificate"}, "source": "student",
    },
    "academy_name": {
        "label": "Nom officiel de l'académie", "label_en": "Academy official name",
        "kinds": {"diploma", "certificate"}, "source": "academy",
    },
    "academy_city": {
        "label": "Ville de l'académie (« Fait à »)", "label_en": "Academy city",
        "kinds": {"diploma", "certificate"}, "source": "academy",
    },
    "document_title": {
        "label": "Intitulé du document", "label_en": "Document title",
        "kinds": {"diploma", "certificate"}, "source": "template",
    },
    "certificate_purpose": {
        "label": "Objet du certificat", "label_en": "Certificate purpose",
        "kinds": {"certificate"}, "source": "template",
    },
    "level_name": {
        "label": "Niveau", "label_en": "Level",
        "kinds": {"diploma", "certificate"}, "source": "schooling",
    },
    "class_name": {
        "label": "Classe", "label_en": "Class",
        "kinds": {"diploma", "certificate"}, "source": "schooling",
    },
    "school_year": {
        "label": "Année scolaire", "label_en": "School year",
        "kinds": {"diploma", "certificate"}, "source": "schooling",
    },
    "annual_average": {
        "label": "Moyenne annuelle", "label_en": "Annual average",
        "kinds": {"diploma", "certificate"}, "source": "grades",
    },
    "result_mention": {
        "label": "Mention (barème de l'académie)", "label_en": "Distinction",
        "kinds": {"diploma", "certificate"}, "source": "grades",
    },
    "award_date": {
        "label": "Date d'obtention (saisie à la production)", "label_en": "Award date",
        "kinds": {"diploma"}, "source": "input",
    },
    "issue_date": {
        "label": "Date de délivrance", "label_en": "Issue date",
        "kinds": {"diploma", "certificate"}, "source": "generation",
    },
    "document_number": {
        "label": "Numéro de référence (attribué à la délivrance)",
        "label_en": "Reference number",
        "kinds": {"diploma", "certificate"}, "source": "generation",
    },
    "signatory_name": {
        "label": "Nom du signataire", "label_en": "Signatory name",
        "kinds": {"diploma", "certificate"}, "source": "template",
    },
    "signatory_title": {
        "label": "Fonction du signataire", "label_en": "Signatory title",
        "kinds": {"diploma", "certificate"}, "source": "template",
    },
}

#: Valeurs d'ESSAI de la validation — volontairement longues et
#: accentuées : un champ qui les accueille accueille un vrai nom. Elles ne
#: servent qu'au rendu filigrané « APERÇU », jamais à un document remis.
SAMPLE_VALUES = {
    "student_name": "Marie-Éléonore Abiodoun Kpossou-Gbénou",
    "student_matricule": "MAT-2026-00042",
    "student_birth_date": "29/02/2016",
    "academy_name": "Académie d'exemple",
    "academy_city": "Ville d'exemple",
    "document_title": "Intitulé du document",
    "certificate_purpose": "Objet du certificat",
    "level_name": "Niveau d'exemple",
    "class_name": "Classe d'exemple",
    "school_year": "2025-2026",
    "annual_average": "14,75 / 20",
    "result_mention": "Très bien",
    "award_date": "30/06/2026",
    "issue_date": "01/07/2026",
    "document_number": "EXE-DIP-2026-0001",
    "signatory_name": "Prénom Nom du signataire",
    "signatory_title": "Directeur / Directrice",
}

#: Champs que la requête de production peut fournir. Tout le reste vient
#: de la base : un navigateur ne choisit pas le nom écrit sur un diplôme.
INPUT_FIELDS = {"award_date", "certificate_purpose"}

#: Règles d'émission par type. Aucune n'est imposée par défaut à un
#: diplôme : FEBA n'en avait pas, et en inventer une changerait une règle
#: métier. L'administration la choisit explicitement.
ELIGIBILITY_RULES = {
    "diploma": ("admin_decision", "annual_average"),
    "certificate": ("enrolled", "admin_decision"),
}
DEFAULT_ELIGIBILITY = {"diploma": "admin_decision", "certificate": "enrolled"}

ALIGNMENTS = ("left", "center", "right")
HEX_COLOR = re.compile(r"^#[0-9A-Fa-f]{6}$")
LINE_LEADING = 1.15


class TemplateUploadError(ValidationError):
    """Fichier refusé à l'entrée — avec la raison exacte."""


# ── Téléversement ─────────────────────────────────────────────────────

def _clean_filename(name):
    """Nom d'origine, pour l'affichage uniquement. Jamais un chemin."""
    base = os.path.basename(str(name or "").replace("\\", "/"))
    base = "".join(ch for ch in base if ch.isprintable()).strip()
    return base[:120] or "gabarit"


def _detect_format(head):
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return AcademyDocumentTemplate.FORMAT_PNG
    if head.startswith(b"\xff\xd8\xff"):
        return AcademyDocumentTemplate.FORMAT_JPEG
    # La norme PDF tolère quelques octets avant l'en-tête.
    if b"%PDF-" in head[:1024]:
        return AcademyDocumentTemplate.FORMAT_PDF
    if head.startswith(b"PK\x03\x04"):
        return "zip"
    return None


#: Marqueurs PDF refusés : script, lancement de programme, fichiers joints,
#: formulaires dynamiques. Aucun n'a sa place dans un fond de diplôme.
_DANGEROUS_PDF = re.compile(
    rb"/(JavaScript|JS|Launch|EmbeddedFiles?|RichMedia|XFA|SubmitForm|ImportData)(?![A-Za-z])"
)


def _inspect_pdf(data):
    from pypdf import PdfReader
    from pypdf.errors import PdfReadError

    if _DANGEROUS_PDF.search(data):
        raise TemplateUploadError(
            "Ce PDF contient du contenu actif (script, lancement de programme, "
            "fichier joint ou formulaire dynamique). Il est refusé : un fond de "
            "diplôme n'en a pas besoin. Réexportez-le en « PDF pour impression »."
        )
    try:
        reader = PdfReader(io.BytesIO(data), strict=False)
        if reader.is_encrypted:
            raise TemplateUploadError(
                "Ce PDF est protégé par mot de passe ou chiffré : il ne peut pas "
                "servir de fond. Exportez une version non protégée."
            )
        count = len(reader.pages)
        sizes = []
        for page in reader.pages[:MAX_PDF_PAGES]:
            box = page.cropbox
            rotate = int(page.get("/Rotate", 0) or 0) % 360
            width_mm = float(box.width) / mm
            height_mm = float(box.height) / mm
            if rotate in (90, 270):
                width_mm, height_mm = height_mm, width_mm
            sizes.append((round(width_mm, 2), round(height_mm, 2)))
    except TemplateUploadError:
        raise
    except (PdfReadError, ValueError, KeyError, TypeError, AttributeError, OSError) as exc:
        raise TemplateUploadError(
            f"Ce fichier n'est pas un PDF lisible ({exc.__class__.__name__}). "
            f"Il est peut-être corrompu ou incomplet."
        ) from exc
    if count < 1:
        raise TemplateUploadError("Ce PDF ne contient aucune page.")
    if count > MAX_PDF_PAGES:
        raise TemplateUploadError(
            f"Ce PDF compte {count} pages. Un fond de diplôme ou de certificat en "
            f"compte une (au plus {MAX_PDF_PAGES} acceptées, dont une seule servira)."
        )
    for width_mm, height_mm in sizes:
        if not (50 <= width_mm <= 1200 and 50 <= height_mm <= 1200):
            raise TemplateUploadError(
                f"Format de page inattendu ({width_mm:.0f} × {height_mm:.0f} mm)."
            )
    _render_pdf_page_png(data, 0, 200)  # le moteur d'aperçu doit savoir l'ouvrir
    return {"page_count": count, "page_sizes": sizes}


def _inspect_image(data, expected_format):
    from PIL import Image, UnidentifiedImageError

    try:
        with Image.open(io.BytesIO(data)) as image:
            fmt = (image.format or "").upper()
            width, height = image.size
            if width * height > MAX_IMAGE_PIXELS:
                raise TemplateUploadError(
                    f"Image trop grande ({width} × {height} px). Au plus "
                    f"{MAX_IMAGE_PIXELS // 1_000_000} millions de pixels."
                )
            image.verify()
        with Image.open(io.BytesIO(data)) as image:
            image.load()  # décode réellement : un fichier tronqué échoue ici
            orientation = image.getexif().get(0x0112, 1) if fmt == "JPEG" else 1
    except TemplateUploadError:
        raise
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError,
            Image.DecompressionBombError) as exc:
        raise TemplateUploadError(
            f"Cette image est illisible ou corrompue ({exc.__class__.__name__})."
        ) from exc

    expected = "PNG" if expected_format == AcademyDocumentTemplate.FORMAT_PNG else "JPEG"
    if fmt != expected:
        raise TemplateUploadError(
            f"Le contenu du fichier ({fmt or 'inconnu'}) ne correspond pas à son "
            f"extension."
        )
    if orientation in (5, 6, 7, 8):
        width, height = height, width
    if max(width, height) < MIN_IMAGE_SIDE_PX:
        raise TemplateUploadError(
            f"Image trop petite ({width} × {height} px) : le document imprimé serait "
            f"flou. Au moins {MIN_IMAGE_SIDE_PX} px sur le plus grand côté."
        )
    return {"width": width, "height": height, "orientation": orientation}


def inspect_upload(uploaded_file):
    """
    Contrôle complet d'un fichier reçu. Renvoie `(octets, métadonnées)`.

    L'extension, le type annoncé par le navigateur ET le contenu réel
    doivent concorder : un `.png` qui est un PDF, ou un PDF annoncé
    `image/png`, est refusé.
    """
    if uploaded_file is None:
        raise TemplateUploadError("Aucun fichier reçu.")
    size = getattr(uploaded_file, "size", None)
    if size is not None and size > MAX_TEMPLATE_BYTES:
        raise TemplateUploadError(
            f"Fichier trop volumineux ({size / 1048576:.1f} Mo). "
            f"Taille maximale : {MAX_TEMPLATE_BYTES // 1048576} Mo."
        )
    data = uploaded_file.read(MAX_TEMPLATE_BYTES + 1)
    if len(data) > MAX_TEMPLATE_BYTES:
        raise TemplateUploadError(
            f"Fichier trop volumineux. Taille maximale : "
            f"{MAX_TEMPLATE_BYTES // 1048576} Mo."
        )
    if not data:
        raise TemplateUploadError("Le fichier est vide.")

    name = _clean_filename(getattr(uploaded_file, "name", ""))
    ext = os.path.splitext(name)[1].lower()
    if ext in (".docx", ".doc", ".odt"):
        raise TemplateUploadError(
            "Les documents Word (DOCX) ne sont pas pris en charge : leur conversion "
            "exigerait un traitement de texte sur le serveur et la mise en page "
            "changerait d'une version à l'autre. Exportez le modèle en PDF depuis "
            "Word (« Enregistrer sous » → PDF) puis téléversez ce PDF."
        )
    declared = ACCEPTED_EXTENSIONS.get(ext)
    if declared is None:
        raise TemplateUploadError(
            "Format non pris en charge. Formats acceptés : PDF, PNG, JPEG."
        )

    detected = _detect_format(data[:2048])
    if detected != declared:
        raise TemplateUploadError(
            f"L'extension « {ext} » ne correspond pas au contenu réel du fichier "
            f"({detected or 'format inconnu'}). Fichier refusé."
        )
    mime = (getattr(uploaded_file, "content_type", "") or "").split(";")[0].strip().lower()
    if mime not in GENERIC_MIME and mime not in ACCEPTED_MIME[declared]:
        raise TemplateUploadError(
            f"Type annoncé « {mime} » incompatible avec un fichier {ext}. Fichier refusé."
        )

    if declared == AcademyDocumentTemplate.FORMAT_PDF:
        meta = _inspect_pdf(data)
    else:
        meta = _inspect_image(data, declared)
    meta.update({"format": declared, "filename": name, "extension": ext})
    return data, meta


def _write_private(relative, content):
    absolute = os.path.join(academy_templates_root(), relative)
    os.makedirs(os.path.dirname(absolute), exist_ok=True)
    with open(absolute, "wb") as handle:
        handle.write(content)
    try:
        os.chmod(absolute, 0o600)
    except OSError:  # pragma: no cover — dépend du système de fichiers
        pass
    return absolute


def _normalized_image(data, orientation):
    """Image redressée selon l'EXIF — sinon un JPEG de téléphone sort couché."""
    from PIL import Image, ImageOps

    with Image.open(io.BytesIO(data)) as image:
        upright = ImageOps.exif_transpose(image)
        if upright.mode not in ("RGB", "RGBA", "L"):
            upright = upright.convert("RGB")
        out = io.BytesIO()
        upright.save(out, "PNG", optimize=True)
        return out.getvalue()


def create_version(*, academy, kind, uploaded_file, user=None, page_format="auto",
                   copy_from=None):
    """
    Enregistre un nouveau fichier comme NOUVELLE version, à l'état brouillon.

    Rien n'est activé ici : la version active, s'il y en a une, continue de
    servir tant que la nouvelle n'a pas été validée puis activée.
    """
    import hashlib

    if kind not in dict(AcademyDocumentTemplate.KIND_CHOICES):
        raise TemplateUploadError("Type de document inconnu.")
    if academy is None:
        raise TemplateUploadError("Sélectionnez d'abord une académie.")

    data, meta = inspect_upload(uploaded_file)
    fmt = meta["format"]

    if fmt == AcademyDocumentTemplate.FORMAT_PDF:
        width_mm, height_mm = meta["page_sizes"][0]
        image_w = image_h = 0
    else:
        image_w, image_h = meta["width"], meta["height"]
        if page_format in (None, "", "auto"):
            page_format = "a4_landscape" if image_w >= image_h else "a4_portrait"
        if page_format not in PAGE_FORMATS:
            raise TemplateUploadError(
                f"Format de page inconnu « {page_format} ». Formats : "
                f"{', '.join(PAGE_FORMATS)}."
            )
        width_mm, height_mm = PAGE_FORMATS[page_format]

    folder = os.path.join(str(academy.pk), kind)
    token = uuid.uuid4().hex
    relative = os.path.join(folder, f"{token}{'.pdf' if fmt == 'pdf' else meta['extension']}")
    render_relative = ""
    _write_private(relative, data)
    if fmt == AcademyDocumentTemplate.FORMAT_JPEG and meta.get("orientation", 1) != 1:
        render_relative = os.path.join(folder, f"{token}.upright.png")
        _write_private(render_relative, _normalized_image(data, meta["orientation"]))

    fields, options = [], {}
    if copy_from is not None:
        fields, options = list(copy_from.fields or []), dict(copy_from.options or {})
    options.setdefault("eligibility", {"rule": DEFAULT_ELIGIBILITY[kind]})
    options["page_format"] = page_format if fmt != "pdf" else "pdf"
    if fmt == "pdf":
        options["page_sizes"] = meta["page_sizes"]

    for _attempt in range(3):
        try:
            with transaction.atomic():
                last = (AcademyDocumentTemplate.objects.select_for_update()
                        .filter(academy=academy, kind=kind).order_by("-version").first())
                template = AcademyDocumentTemplate.objects.create(
                    academy=academy, kind=kind,
                    version=(last.version + 1) if last else 1,
                    original_filename=meta["filename"], file_format=fmt,
                    file_path=relative, render_path=render_relative,
                    file_sha256=hashlib.sha256(data).hexdigest(), file_size=len(data),
                    page_count=meta.get("page_count", 1), page_index=0,
                    page_width_mm=width_mm, page_height_mm=height_mm,
                    image_width_px=image_w, image_height_px=image_h,
                    fields=_drop_outside_page(fields, width_mm, height_mm),
                    options=options, uploaded_by=user,
                )
            break
        except IntegrityError:  # deux téléversements simultanés : on renumérote
            continue
    else:  # pragma: no cover — trois collisions de suite
        raise TemplateUploadError("Téléversement simultané : réessayez.")

    log(template, "uploaded", user,
        f"{template.original_filename} — {fmt.upper()}, {template.file_size} octets, "
        f"empreinte {template.file_sha256[:16]}…"
        + (f" (configuration reprise de la v{copy_from.version})" if copy_from else ""))
    return template


def _drop_outside_page(fields, width_mm, height_mm):
    """Champs repris d'une version précédente qui tiennent dans la nouvelle page."""
    kept = []
    for item in fields:
        try:
            if (float(item["x_mm"]) + float(item["width_mm"]) <= width_mm + 0.01
                    and float(item["y_mm"]) + float(item["height_mm"]) <= height_mm + 0.01):
                kept.append(item)
        except (KeyError, TypeError, ValueError):
            continue
    return kept


def log(template, action, user=None, detail=""):
    AcademyTemplateEvent.objects.create(
        template=template, action=action, performed_by=user, detail=detail[:2000],
    )


# ── Configuration des champs ──────────────────────────────────────────

def _number(value, label, lo, hi):
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValidationError(f"{label} : valeur numérique attendue.")
    if number != number or not (lo <= number <= hi):  # NaN compris
        raise ValidationError(f"{label} : doit être entre {lo} et {hi}.")
    return round(number, 2)


def normalize_fields(template, items):
    """
    Contrôle et normalise la liste des champs positionnés.

    Coordonnées en mm, repère haut-gauche de la PAGE. Un champ hors de la
    page, deux champs qui se chevauchent, une taille absurde ou un champ
    étranger au type de document sont refusés — chacun nommément.
    """
    if not isinstance(items, list):
        raise ValidationError("La configuration des champs doit être une liste.")
    errors, cleaned, seen = [], [], set()
    page_w, page_h = template.page_width_mm, template.page_height_mm
    for index, raw in enumerate(items):
        if not isinstance(raw, dict):
            errors.append(f"Champ n° {index + 1} : format invalide.")
            continue
        name = raw.get("name")
        spec = FIELD_CATALOG.get(name)
        if spec is None or template.kind not in spec["kinds"]:
            errors.append(f"« {name} » n'est pas un champ disponible pour ce type de document.")
            continue
        if name in seen:
            errors.append(f"« {spec['label']} » est placé deux fois.")
            continue
        seen.add(name)
        label = spec["label"]
        try:
            x = _number(raw.get("x_mm"), f"{label} — position horizontale", 0, page_w)
            y = _number(raw.get("y_mm"), f"{label} — position verticale", 0, page_h)
            w = _number(raw.get("width_mm"), f"{label} — largeur", 5, page_w)
            h = _number(raw.get("height_mm"), f"{label} — hauteur", 3, page_h)
            size = _number(raw.get("font_size_pt", 14), f"{label} — taille du texte", 6, 72)
            min_size = _number(raw.get("min_font_size_pt", min(size, 8)),
                               f"{label} — taille minimale", 5, 72)
        except ValidationError as exc:
            errors.extend(exc.messages)
            continue
        if x + w > page_w + 0.01 or y + h > page_h + 0.01:
            errors.append(f"« {label} » dépasse de la page ({page_w:g} × {page_h:g} mm).")
            continue
        font = raw.get("font", "serif")
        if font not in FONTS:
            errors.append(f"« {label} » : police inconnue « {font} ».")
            continue
        align = raw.get("align", "center")
        if align not in ALIGNMENTS:
            errors.append(f"« {label} » : alignement inconnu « {align} ».")
            continue
        color = raw.get("color", "#000000")
        if not isinstance(color, str) or not HEX_COLOR.match(color):
            errors.append(f"« {label} » : couleur invalide (format #RRGGBB attendu).")
            continue
        try:
            max_lines = int(raw.get("max_lines", 1))
        except (TypeError, ValueError):
            max_lines = 0
        if max_lines not in (1, 2):
            errors.append(f"« {label} » : 1 ou 2 lignes au plus.")
            continue
        if min_size > size:
            min_size = size
        cleaned.append({
            "name": name, "x_mm": x, "y_mm": y, "width_mm": w, "height_mm": h,
            "font": font, "font_size_pt": size, "min_font_size_pt": min_size,
            "align": align, "color": color.upper(), "max_lines": max_lines,
            "required": bool(raw.get("required", name == "student_name")),
        })

    for i, first in enumerate(cleaned):
        for second in cleaned[i + 1:]:
            if _overlap(first, second):
                errors.append(
                    f"« {FIELD_CATALOG[first['name']]['label']} » et "
                    f"« {FIELD_CATALOG[second['name']]['label']} » se chevauchent : "
                    f"leurs textes se superposeraient."
                )
    if errors:
        raise ValidationError(errors)
    return cleaned


def _overlap(a, b):
    return (a["x_mm"] < b["x_mm"] + b["width_mm"] - 0.01
            and b["x_mm"] < a["x_mm"] + a["width_mm"] - 0.01
            and a["y_mm"] < b["y_mm"] + b["height_mm"] - 0.01
            and b["y_mm"] < a["y_mm"] + a["height_mm"] - 0.01)


def normalize_options(template, raw):
    """Textes fixes et règle d'émission de la version."""
    raw = raw if isinstance(raw, dict) else {}
    options = dict(template.options or {})
    for key in ("document_title", "certificate_purpose", "signatory_name", "signatory_title"):
        if key in raw:
            value = str(raw.get(key) or "").strip()
            if len(value) > 200:
                raise ValidationError(f"« {FIELD_CATALOG[key]['label']} » : 200 caractères au plus.")
            options[key] = value
    if "page_index" in raw:
        try:
            page_index = int(raw["page_index"])
        except (TypeError, ValueError):
            raise ValidationError("Page du fond : numéro invalide.")
        if not (0 <= page_index < template.page_count):
            raise ValidationError(
                f"Page du fond : ce PDF compte {template.page_count} page(s)."
            )
        options["page_index"] = page_index
    if "eligibility" in raw:
        rule = raw.get("eligibility") or {}
        name = rule.get("rule") if isinstance(rule, dict) else None
        if name not in ELIGIBILITY_RULES[template.kind]:
            raise ValidationError(
                f"Règle d'émission inconnue pour ce type : « {name} ». Règles : "
                f"{', '.join(ELIGIBILITY_RULES[template.kind])}."
            )
        clean = {"rule": name}
        if name == "annual_average":
            clean["min_average"] = _number(
                rule.get("min_average", 10), "Moyenne annuelle minimale (sur 20)", 0, 20,
            )
        options["eligibility"] = clean
    return options


def save_configuration(template, *, fields=None, options=None, user=None):
    """
    Enregistre champs et options d'une version MODIFIABLE.

    Une version validée qu'on modifie redevient un brouillon : sa
    validation portait sur l'ancienne configuration. Une version active ou
    ayant servi n'est jamais modifiée — on en crée une nouvelle.
    """
    if not template.is_editable:
        raise ValidationError(
            "Cette version est « " + template.get_status_display() + " » : sa "
            "configuration ne change plus, des documents en dépendent ou peuvent en "
            "dépendre. Créez une nouvelle version à partir de celle-ci."
        )
    if template.documents.exists():
        raise ValidationError(
            "Des documents ont été produits avec cette version : créez une nouvelle "
            "version pour changer sa configuration."
        )
    update = ["updated_at", "status", "validation_report", "validated_at"]
    if options is not None:
        template.options = normalize_options(template, options)
        if "page_index" in (options or {}):
            template.page_index = template.options.pop("page_index")
            sizes = template.options.get("page_sizes") or []
            if template.page_index < len(sizes):
                template.page_width_mm, template.page_height_mm = sizes[template.page_index]
            update += ["page_index", "page_width_mm", "page_height_mm"]
        update.append("options")
    if fields is not None:
        template.fields = normalize_fields(template, fields)
        update.append("fields")
    elif "page_width_mm" in update:
        template.fields = normalize_fields(template, template.fields)
        update.append("fields")
    template.status = AcademyDocumentTemplate.DRAFT
    template.validation_report = {}
    template.validated_at = None
    template.save(update_fields=update)
    log(template, "configured", user,
        f"{len(template.fields)} champ(s) positionné(s) ; règle "
        f"{(template.options.get('eligibility') or {}).get('rule')}")
    return template


# ── Rendu ─────────────────────────────────────────────────────────────

def _font_supports(font_name, text):
    if font_name.startswith("FEBA-"):
        return True
    try:
        text.encode("cp1252")
        return True
    except UnicodeEncodeError:
        return False


def fit_text(text, font_name, size_pt, min_size_pt, width_pt, height_pt, max_lines, label):
    """
    Lignes et corps qui font tenir `text` dans la boîte, ou RenderError.

    Réduit la police par demi-points ; sur deux lignes au plus si le champ
    le permet, coupées à l'espace qui équilibre le mieux. Jamais tronqué :
    un nom amputé sur un diplôme est une erreur qui circule.
    """
    from apps.documents.renderer import RenderError, _advance

    words = text.split()
    splits = [(" ".join(words[:i]), " ".join(words[i:])) for i in range(1, len(words))]
    size = size_pt
    while size >= min_size_pt - 1e-6:
        if size <= height_pt and _advance(text, font_name, size) <= width_pt:
            return [text], size
        if max_lines >= 2 and splits and 2 * size * LINE_LEADING <= height_pt:
            best = min(splits, key=lambda pair: max(_advance(pair[0], font_name, size),
                                                    _advance(pair[1], font_name, size)))
            if max(_advance(best[0], font_name, size),
                   _advance(best[1], font_name, size)) <= width_pt:
                return list(best), size
        size -= 0.5
    raise RenderError(
        f"« {text} » ne tient pas dans la zone « {label} » "
        f"({width_pt / mm:.1f} × {height_pt / mm:.1f} mm), même en {min_size_pt:g} pt"
        f"{' sur deux lignes' if max_lines >= 2 else ''}. Agrandissez la zone dans "
        f"l'éditeur du gabarit : le texte n'est jamais tronqué."
    )


def _draw_fields(pdf, template, values, page_h_pt, offset=(0.0, 0.0)):
    from apps.documents.renderer import RenderError, ensure_fonts

    ensure_fonts()
    ox, oy = offset
    for field in template.fields:
        spec = FIELD_CATALOG[field["name"]]
        value = values.get(field["name"])
        if hasattr(value, "strftime"):
            value = value.strftime("%d/%m/%Y")
        text = " ".join(str(value or "").split())
        if not text:
            if field.get("required"):
                raise RenderError(
                    f"Le champ « {spec['label']} » est obligatoire et n'a pas de valeur."
                )
            continue
        font_name = FONTS[field["font"]]
        if not _font_supports(font_name, text):
            raise RenderError(
                f"« {text} » contient des caractères que la police « {field['font']} » "
                f"ne sait pas écrire. Choisissez la police « serif » (Crimson Pro) pour "
                f"ce champ."
            )
        width_pt, height_pt = field["width_mm"] * mm, field["height_mm"] * mm
        lines, size = fit_text(
            text, font_name, field["font_size_pt"], field["min_font_size_pt"],
            width_pt, height_pt, field["max_lines"], spec["label"],
        )
        ascent, descent = pdfmetrics.getAscentDescent(font_name, size)
        leading = size * LINE_LEADING
        block = leading * (len(lines) - 1)
        # Bloc centré verticalement dans la zone, sur la hauteur réelle de
        # l'encre (ascendantes et descendantes), pas sur le corps nominal.
        top_pt = page_h_pt - field["y_mm"] * mm
        centre = top_pt - height_pt / 2
        first_baseline = centre + block / 2 - (ascent + descent) / 2
        pdf.setFont(font_name, size)
        pdf.setFillColor(HexColor(field["color"]))
        for index, line in enumerate(lines):
            y = first_baseline - index * leading + oy
            if field["align"] == "center":
                pdf.drawCentredString(ox + (field["x_mm"] + field["width_mm"] / 2) * mm, y, line)
            elif field["align"] == "right":
                pdf.drawRightString(ox + (field["x_mm"] + field["width_mm"]) * mm, y, line)
            else:
                pdf.drawString(ox + field["x_mm"] * mm, y, line)


def _draw_preview_marks(pdf, width_pt, height_pt, label):
    pdf.saveState()
    pdf.setFont("Helvetica-Bold", 46)
    pdf.setFillColorRGB(0.85, 0.10, 0.10, alpha=0.28)
    pdf.translate(width_pt / 2, height_pt / 2)
    pdf.rotate(28)
    pdf.drawCentredString(0, 0, label)
    pdf.setFont("Helvetica-Bold", 13)
    pdf.drawCentredString(0, -22, "APERÇU — NE PAS REMETTRE À UN ÉLÈVE")
    pdf.restoreState()


def _draw_field_frames(pdf, template, page_h_pt):
    """Cadres des zones, pour l'aperçu de configuration uniquement."""
    pdf.saveState()
    pdf.setStrokeColorRGB(0.1, 0.35, 0.85, alpha=0.7)
    pdf.setLineWidth(0.5)
    pdf.setDash(2, 2)
    for field in template.fields:
        pdf.rect(field["x_mm"] * mm, page_h_pt - (field["y_mm"] + field["height_mm"]) * mm,
                 field["width_mm"] * mm, field["height_mm"] * mm, stroke=1, fill=0)
    pdf.restoreState()


def render(template, values, *, preview=False, frames=False, preview_label="APERÇU"):
    """
    Produit le PDF final sur le fond de CETTE version.

    Aperçu et document remis passent par cette même fonction : seule la
    surimpression « APERÇU » les distingue.
    """
    from apps.documents.renderer import RenderError

    page_w_pt, page_h_pt = template.page_width_mm * mm, template.page_height_mm * mm
    source = template.render_absolute_path
    if not os.path.exists(source):
        raise RenderError(
            "Le fichier de ce gabarit est absent du stockage. Téléversez-le de nouveau "
            "(voir la sauvegarde du volume des fichiers privés)."
        )

    if template.file_format == AcademyDocumentTemplate.FORMAT_PDF:
        return _render_on_pdf(template, values, source, preview, frames, preview_label)

    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=(page_w_pt, page_h_pt))
    pdf.setTitle(_title(template, values))
    width_px = template.image_width_px or 1
    height_px = template.image_height_px or 1
    ratio = width_px / height_px
    if ratio >= page_w_pt / page_h_pt:
        draw_w, draw_h = page_w_pt, page_w_pt / ratio
    else:
        draw_w, draw_h = page_h_pt * ratio, page_h_pt
    pdf.drawImage(source, (page_w_pt - draw_w) / 2, (page_h_pt - draw_h) / 2,
                  width=draw_w, height=draw_h, preserveAspectRatio=True, anchor="c",
                  mask="auto")
    _draw_fields(pdf, template, values, page_h_pt)
    if frames:
        _draw_field_frames(pdf, template, page_h_pt)
    if preview:
        _draw_preview_marks(pdf, page_w_pt, page_h_pt, preview_label)
    pdf.showPage()
    pdf.save()
    return buffer.getvalue()


def _title(template, values):
    return (template.options.get("document_title")
            or dict(AcademyDocumentTemplate.KIND_CHOICES)[template.kind])


def _render_on_pdf(template, values, source, preview, frames, preview_label):
    from pypdf import PdfReader, PdfWriter, Transformation
    from pypdf.generic import NameObject

    from apps.documents.renderer import RenderError

    try:
        reader = PdfReader(source, strict=False)
        page = reader.pages[template.page_index]
        page.transfer_rotation_to_content()
    except Exception as exc:  # fichier altéré depuis la validation
        raise RenderError(f"Le PDF du gabarit ne peut plus être lu : {exc}") from exc
    box = page.cropbox
    left, bottom = float(box.left), float(box.bottom)
    page_w_pt, page_h_pt = float(box.width), float(box.height)

    overlay_buffer = io.BytesIO()
    pdf = canvas.Canvas(overlay_buffer, pagesize=(page_w_pt, page_h_pt))
    _draw_fields(pdf, template, values, page_h_pt)
    if frames:
        _draw_field_frames(pdf, template, page_h_pt)
    if preview:
        _draw_preview_marks(pdf, page_w_pt, page_h_pt, preview_label)
    pdf.showPage()
    pdf.save()
    overlay = PdfReader(io.BytesIO(overlay_buffer.getvalue())).pages[0]

    page.merge_transformed_page(overlay, Transformation().translate(left, bottom))
    # Le document remis n'emporte ni annotations ni actions du fichier
    # d'origine : seulement son dessin et nos champs.
    for key in ("/Annots", "/AA"):
        if NameObject(key) in page:
            del page[NameObject(key)]
    writer = PdfWriter()
    writer.add_page(page)
    writer.add_metadata({"/Title": _title(template, values), "/Producer": "FEBA"})
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def _render_pdf_page_png(data_or_path, page_index, target_px):
    import pypdfium2 as pdfium

    document = pdfium.PdfDocument(data_or_path)
    try:
        page = document[page_index]
        width_pt, height_pt = page.get_size()
        scale = max(0.2, min(6.0, target_px / max(width_pt, height_pt)))
        image = page.render(scale=scale).to_pil()
        out = io.BytesIO()
        image.convert("RGB").save(out, "PNG", optimize=True)
        return out.getvalue()
    finally:
        document.close()


def background_png(template, target_px=1600):
    """Image du fond pour l'éditeur (jamais le fichier original lui-même)."""
    from PIL import Image

    if template.file_format == AcademyDocumentTemplate.FORMAT_PDF:
        return _render_pdf_page_png(template.absolute_path, template.page_index, target_px)
    with Image.open(template.render_absolute_path) as image:
        image = image.convert("RGB")
        image.thumbnail((target_px, target_px))
        out = io.BytesIO()
        image.save(out, "PNG", optimize=True)
        return out.getvalue()


def pdf_to_png(content, target_px=1600):
    return _render_pdf_page_png(content, 0, target_px)


# ── Validation ────────────────────────────────────────────────────────

def _sample_values(template):
    values = dict(SAMPLE_VALUES)
    for key in ("document_title", "certificate_purpose", "signatory_name", "signatory_title"):
        if template.options.get(key):
            values[key] = template.options[key]
    return values


def validate(template, user=None):
    """
    Éprouve la version et enregistre le rapport. Renvoie le rapport.

    Prête = fichier présent et à l'empreinte enregistrée, nom de l'élève
    placé, configuration conforme, rendu d'essai réussi et RELU : le texte
    extrait du PDF produit contient chaque valeur écrite, et aucun marqueur.
    """
    import hashlib

    from pypdf import PdfReader

    from apps.documents.renderer import RenderError

    errors, warnings = [], []
    path = template.absolute_path
    if not os.path.exists(path):
        errors.append("Le fichier du gabarit est absent du stockage.")
    else:
        with open(path, "rb") as handle:
            if hashlib.sha256(handle.read()).hexdigest() != template.file_sha256:
                errors.append("Le fichier stocké ne correspond plus à son empreinte : "
                              "il a été modifié hors de l'application.")
    names = {field["name"] for field in template.fields}
    if "student_name" not in names:
        errors.append("Le nom de l'élève n'est pas placé sur le gabarit.")
    try:
        normalize_fields(template, template.fields)
    except ValidationError as exc:
        errors.extend(exc.messages)
    for key in ("document_title", "signatory_name", "signatory_title", "certificate_purpose"):
        if key in names and not template.options.get(key):
            errors.append(f"« {FIELD_CATALOG[key]['label']} » est placé mais son texte "
                          f"n'est pas renseigné dans les paramètres du gabarit.")
    rule = (template.options.get("eligibility") or {}).get("rule")
    if rule not in ELIGIBILITY_RULES[template.kind]:
        errors.append("Aucune règle d'émission valide n'est choisie.")
    if template.file_format != AcademyDocumentTemplate.FORMAT_PDF and template.image_width_px:
        dpi = template.image_width_px / (template.page_width_mm / 25.4)
        dpi = min(dpi, template.image_height_px / (template.page_height_mm / 25.4))
        if dpi < MIN_PRINT_DPI:
            warnings.append(
                f"Résolution d'impression faible (≈ {dpi:.0f} dpi pour ce format de page) : "
                f"le document imprimé peut paraître flou. Idéalement 300 dpi."
            )

    pages = None
    if not errors:
        values = _sample_values(template)
        try:
            content = render(template, values, preview=False)
            reader = PdfReader(io.BytesIO(content))
            pages = len(reader.pages)
            text = " ".join((reader.pages[0].extract_text() or "").split())
            squeezed = text.replace(" ", "")
            for field in template.fields:
                value = str(values.get(field["name"], ""))
                if value and value.replace(" ", "") not in squeezed:
                    errors.append(f"Rendu d'essai : « {FIELD_CATALOG[field['name']]['label']} » "
                                  f"n'a pas été retrouvé dans le PDF produit.")
            if "{{" in text or "}}" in text:
                errors.append("Rendu d'essai : un marqueur non remplacé subsiste.")
            if pages != 1:
                errors.append(f"Rendu d'essai : {pages} pages produites au lieu d'une.")
        except (RenderError, ValidationError) as exc:
            errors.extend(exc.messages)
        except Exception as exc:  # moteur ou fichier : jamais « prêt » par défaut
            errors.append(f"Rendu d'essai impossible : {exc.__class__.__name__}.")

    report = {
        "ok": not errors, "errors": errors, "warnings": warnings,
        "checked_at": timezone.now().isoformat(), "pages": pages,
        "fields": len(template.fields), "fingerprint": template.fingerprint(),
    }
    if template.is_editable:
        template.status = (AcademyDocumentTemplate.VALIDATED if not errors
                           else AcademyDocumentTemplate.INVALID)
        template.validated_at = timezone.now() if not errors else None
    template.validation_report = report
    template.save(update_fields=["status", "validated_at", "validation_report", "updated_at"])
    log(template, "validated" if not errors else "validation_failed", user,
        "; ".join(errors)[:1500] or "Rendu d'essai relu : conforme.")
    return report


def activate(template, user=None):
    """
    Met la version en service ; l'ancienne active passe à « remplacée ».

    Refusé si la version n'est pas validée OU si sa configuration a changé
    depuis la validation (empreinte différente).
    """
    if template.status != AcademyDocumentTemplate.VALIDATED:
        raise ValidationError(
            "Seule une version validée peut être activée. Lancez d'abord la vérification."
        )
    if (template.validation_report or {}).get("fingerprint") != template.fingerprint():
        raise ValidationError("La configuration a changé depuis la vérification : "
                              "vérifiez de nouveau avant d'activer.")
    with transaction.atomic():
        previous = list(AcademyDocumentTemplate.objects.select_for_update().filter(
            academy=template.academy, kind=template.kind,
            status=AcademyDocumentTemplate.ACTIVE,
        ).exclude(pk=template.pk))
        for old in previous:
            old.status = AcademyDocumentTemplate.ARCHIVED
            old.save(update_fields=["status", "updated_at"])
            log(old, "archived", user, f"Remplacée par la v{template.version}.")
        template.status = AcademyDocumentTemplate.ACTIVE
        template.activated_at = timezone.now()
        template.save(update_fields=["status", "activated_at", "updated_at"])
    log(template, "activated", user,
        f"Version {template.version} en service"
        + (f" (remplace la v{previous[0].version})" if previous else ""))
    return template


def disable(template, user=None):
    if template.status != AcademyDocumentTemplate.ACTIVE:
        raise ValidationError("Seule la version active peut être désactivée.")
    template.status = AcademyDocumentTemplate.DISABLED
    template.save(update_fields=["status", "updated_at"])
    log(template, "disabled", user, "Plus utilisée pour produire des documents.")
    return template


def reactivate(template, user=None):
    """Remet en service une version désactivée ou remplacée — revérifiée d'abord."""
    if template.status not in (AcademyDocumentTemplate.DISABLED, AcademyDocumentTemplate.ARCHIVED):
        raise ValidationError("Seule une version désactivée ou remplacée peut être réactivée.")
    report = validate(template, user)
    if not report["ok"]:
        raise ValidationError(["La vérification a échoué :"] + report["errors"])
    template.status = AcademyDocumentTemplate.VALIDATED
    template.save(update_fields=["status", "updated_at"])
    return activate(template, user)


def delete_version(template, user=None, confirm=False):
    """
    Supprime une version JAMAIS utilisée. Une version qui a servi à des
    documents se désactive : la supprimer rendrait ces documents orphelins.
    """
    if template.documents.exists():
        raise ValidationError(
            f"{template.documents.count()} document(s) ont été produits avec cette "
            f"version : elle ne peut pas être supprimée. Désactivez-la."
        )
    if template.status == AcademyDocumentTemplate.ACTIVE and not confirm:
        raise ValidationError(
            "C'est la version ACTIVE : après suppression, aucun document de ce type ne "
            "pourra plus être produit avec un gabarit téléversé. Confirmez la suppression."
        )
    paths = [template.absolute_path]
    if template.render_path:
        paths.append(template.render_absolute_path)
    label = f"{template.get_kind_display()} v{template.version} ({template.original_filename})"
    template.delete()
    for path in paths:
        try:
            os.remove(path)
        except OSError:
            pass
    return label


# ── Choix du gabarit et données d'un élève ────────────────────────────

def active_template(academy, kind):
    if academy is None:
        return None
    return AcademyDocumentTemplate.objects.filter(
        academy=academy, kind=kind, status=AcademyDocumentTemplate.ACTIVE,
    ).first()


def builtin_template(academy, kind):
    """Gabarit intégré (livré avec l'application) prévu pour cette académie."""
    from apps.documents.templates_registry import (
        TemplateError, available_templates, load_template,
    )

    for template_id in available_templates():
        if not template_id.startswith(f"{kind}_"):
            continue
        try:
            template = load_template(template_id)
        except TemplateError:
            continue
        if template.academies and template.allows_academy(academy):
            return template
    return None


def resolve_template(academy, kind):
    """
    LA règle de choix, unique : version téléversée active de l'académie,
    sinon gabarit intégré prévu pour elle, sinon rien. Jamais le gabarit
    d'une autre académie.
    """
    uploaded = active_template(academy, kind)
    if uploaded is not None:
        return "uploaded", uploaded
    builtin = builtin_template(academy, kind)
    if builtin is not None:
        return "builtin", builtin
    return None, None


def _school_year_for(student, school_year=None):
    if school_year is not None:
        return school_year
    return (student.school.years.filter(is_current=True).first()
            if student.school_id else None)


def _class_for(student, school_year):
    from apps.grades.models import Grade

    return Grade._class_for_year(student, school_year)


def schooling_facts(student, school_year):
    """Classe, niveau, moyenne et mention — lus dans la base, ou None."""
    from apps.grades.appreciations import appreciation_for, cycle_of_class
    from apps.grades.grading import format_average, get_grading_scale
    from apps.grades.models import Grade

    klass = _class_for(student, school_year) if school_year else None
    facts = {"class": klass, "level": getattr(klass, "level", None),
             "average": None, "average_text": "", "mention": "", "scale": None}
    if school_year is None:
        return facts
    average = Grade.calculate_annual_average(student, school_year)
    facts["average"] = average
    if average is not None and klass is not None:
        scale = get_grading_scale(klass.level)
        facts["scale"] = scale
        facts["average_text"] = format_average(average, scale)
        facts["mention"] = appreciation_for(
            average, 20, academy=student.school, cycle=cycle_of_class(klass),
        ) or ""
    return facts


def _parse_date(value):
    if hasattr(value, "strftime"):
        return value
    text = str(value or "").strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return timezone.datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    raise ValidationError(f"Date invalide : « {text} » (format JJ/MM/AAAA attendu).")


def build_values(template, student, *, school_year=None, extra=None, number=""):
    """
    Valeurs de CHAQUE champ du catalogue pour cet élève, et ce qui manque.

    Renvoie `(values, missing, warnings)`. `missing` = champs PLACÉS et
    obligatoires sans valeur ; `warnings` = champs placés facultatifs qui
    resteront vides. Rien n'est complété par une valeur plausible.
    """
    from apps.schools.branding import get_branding

    extra = extra if isinstance(extra, dict) else {}
    academy = student.school
    year = _school_year_for(student, school_year)
    facts = schooling_facts(student, year)
    branding = get_branding(academy)
    options = template.options or {}
    award = _parse_date(extra.get("award_date")) if "award_date" in extra else None
    purpose = str(extra.get("certificate_purpose") or "").strip()[:200] \
        or options.get("certificate_purpose", "")

    values = {
        "student_name": student.get_full_name().strip(),
        "student_matricule": student.matricule or "",
        "student_birth_date": student.date_of_birth.strftime("%d/%m/%Y")
        if student.date_of_birth else "",
        "academy_name": branding.legal_name or academy.name,
        "academy_city": academy.city or "",
        "document_title": options.get("document_title", ""),
        "certificate_purpose": purpose,
        "level_name": facts["level"].name if facts["level"] else "",
        "class_name": facts["class"].name if facts["class"] else "",
        "school_year": year.name if year else "",
        "annual_average": facts["average_text"],
        "result_mention": facts["mention"],
        "award_date": award.strftime("%d/%m/%Y") if award else "",
        "issue_date": timezone.localdate().strftime("%d/%m/%Y"),
        "document_number": number,
        "signatory_name": options.get("signatory_name", ""),
        "signatory_title": options.get("signatory_title", ""),
    }
    missing, warnings = [], []
    for field in template.fields:
        name = field["name"]
        if name == "document_number" or values.get(name):
            continue
        label = FIELD_CATALOG[name]["label"]
        if field.get("required"):
            missing.append(label)
        else:
            warnings.append(f"« {label} » sera laissé vide : aucune donnée enregistrée.")
    return values, missing, warnings, year, facts


def eligibility_blockers(template, student, year, facts):
    """
    Raisons — factuelles — qui interdisent de délivrer ce document à cet
    élève selon la règle choisie pour la version. Liste vide = permis.
    """
    from apps.grades.grading import format_average

    rule = (template.options.get("eligibility") or {}).get("rule")
    reasons = []
    if student.school_id != template.academy_id:
        return ["Cet élève n'appartient pas à l'académie de ce gabarit."]
    if rule == "admin_decision":
        return []
    if rule == "enrolled":
        if not student.is_active:
            reasons.append("L'élève n'est plus inscrit (fiche inactive) : un certificat "
                           "d'inscription ne peut pas lui être délivré.")
        if year is None:
            reasons.append("Aucune année scolaire en cours pour cette académie.")
        elif facts["class"] is None:
            reasons.append(f"L'élève n'est inscrit dans aucune classe pour l'année {year.name}.")
        return reasons
    if rule == "annual_average":
        threshold = float((template.options.get("eligibility") or {}).get("min_average", 10))
        if year is None:
            return ["Aucune année scolaire en cours : la moyenne annuelle ne peut pas être "
                    "calculée."]
        if facts["class"] is None:
            return [f"L'élève n'a pas de classe pour l'année {year.name} : son barème "
                    f"(sur 10 ou sur 20) et sa moyenne ne peuvent pas être établis."]
        if facts["average"] is None:
            return [f"Aucune note enregistrée pour l'année {year.name} : la réussite ne peut "
                    f"pas être établie."]
        if float(facts["average"]) < threshold:
            scale = facts["scale"] or 20
            return [f"Moyenne annuelle {facts['average_text']} inférieure au seuil requis "
                    f"({format_average(threshold, scale)})."]
        return []
    return ["Aucune règle d'émission valide n'est configurée pour ce gabarit."]

