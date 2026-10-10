"""
apps/notifications/attachments.py — Validation des pièces jointes (serveur).

Le navigateur n'a AUCUNE autorité : extension, type annoncé et taille sont
revérifiés ici, et le CONTENU du fichier doit correspondre à son extension
(signature binaire). Un `.pdf` qui n'est pas un PDF, un `.docx` qui n'est
pas une archive Office, un exécutable renommé : refusés.

Formats par défaut (configurables par EMAIL_ATTACHMENT_ALLOWED_EXTENSIONS) :
images courantes, PDF, Word, Excel, PowerPoint, OpenDocument, texte, CSV.
Jamais : exécutables, scripts, archives, HTML/SVG (contenu actif).

Aucune analyse antivirus n'est disponible dans cet environnement : elle
n'est donc PAS annoncée. Voir EMAIL_CONFIGURATION_GUIDE.md.
"""
import os
import re
import unicodedata

from django.conf import settings

#: extension → (type MIME envoyé, signatures acceptées)
FORMATS = {
    "pdf": ("application/pdf", [b"%PDF-"]),
    "png": ("image/png", [b"\x89PNG\r\n\x1a\n"]),
    "jpg": ("image/jpeg", [b"\xff\xd8\xff"]),
    "jpeg": ("image/jpeg", [b"\xff\xd8\xff"]),
    "gif": ("image/gif", [b"GIF87a", b"GIF89a"]),
    "webp": ("image/webp", [b"RIFF"]),
    "doc": ("application/msword", [b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"]),
    "xls": ("application/vnd.ms-excel", [b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"]),
    "ppt": ("application/vnd.ms-powerpoint", [b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"]),
    "docx": ("application/vnd.openxmlformats-officedocument.wordprocessingml.document", [b"PK\x03\x04"]),
    "xlsx": ("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", [b"PK\x03\x04"]),
    "pptx": ("application/vnd.openxmlformats-officedocument.presentationml.presentation", [b"PK\x03\x04"]),
    "odt": ("application/vnd.oasis.opendocument.text", [b"PK\x03\x04"]),
    "ods": ("application/vnd.oasis.opendocument.spreadsheet", [b"PK\x03\x04"]),
    "txt": ("text/plain", None),
    "csv": ("text/csv", None),
}
DEFAULT_ALLOWED = sorted(FORMATS)

#: Formats affichables dans le navigateur sans risque (aperçu en ligne).
INLINE_TYPES = {"application/pdf", "image/png", "image/jpeg", "image/gif", "image/webp"}


class AttachmentError(Exception):
    pass


def allowed_extensions():
    configured = getattr(settings, "EMAIL_ATTACHMENT_ALLOWED_EXTENSIONS", None)
    if isinstance(configured, str):
        configured = [e.strip().lower().lstrip(".") for e in configured.split(",") if e.strip()]
    # On ne peut autoriser qu'un format dont on sait vérifier la nature.
    return sorted(set(configured or DEFAULT_ALLOWED) & set(FORMATS))


def max_file_bytes():
    return int(getattr(settings, "EMAIL_ATTACHMENT_MAX_FILE_MB", 10)) * 1024 * 1024


def max_total_bytes():
    return int(getattr(settings, "EMAIL_ATTACHMENT_MAX_TOTAL_MB", 20)) * 1024 * 1024


def max_files():
    return int(getattr(settings, "EMAIL_ATTACHMENT_MAX_FILES", 10))


def safe_filename(name):
    """Nom affichable et sûr : pas de chemin, pas de caractère de contrôle."""
    name = os.path.basename(str(name or "").replace("\\", "/"))
    name = unicodedata.normalize("NFC", name)
    name = re.sub(r"[\x00-\x1f\x7f<>:\"/\\|?*]", "_", name).strip(" .")
    if not name:
        name = "piece-jointe"
    stem, ext = os.path.splitext(name)
    return f"{stem[:120]}{ext[:10]}"


def _sniff(ext, head, data):
    _mime, signatures = FORMATS[ext]
    if signatures is None:
        # Texte : doit être décodable et sans octet nul.
        if b"\x00" in data:
            return False
        try:
            data.decode("utf-8")
        except UnicodeDecodeError:
            try:
                data.decode("latin-1")
            except UnicodeDecodeError:  # pragma: no cover
                return False
        return True
    if not any(head.startswith(sig) for sig in signatures):
        return False
    if ext == "webp":
        return head[8:12] == b"WEBP"
    return True


def validate_uploads(files):
    """
    Valide une liste de fichiers téléversés (UploadedFile).

    Renvoie [(nom_sûr, octets, type MIME)] ou lève AttachmentError avec un
    message destiné à l'utilisateur.
    """
    files = list(files or [])
    if len(files) > max_files():
        raise AttachmentError(f"{len(files)} fichiers : au plus {max_files()} pièces jointes par message.")
    allowed = allowed_extensions()
    total, result = 0, []
    for upload in files:
        name = safe_filename(getattr(upload, "name", ""))
        ext = os.path.splitext(name)[1].lower().lstrip(".")
        if ext not in allowed:
            raise AttachmentError(
                f"« {name} » : format non autorisé. Formats acceptés : {', '.join(allowed)}."
            )
        size = getattr(upload, "size", None)
        if size is not None and size > max_file_bytes():
            raise AttachmentError(
                f"« {name} » dépasse {max_file_bytes() // (1024 * 1024)} Mo."
            )
        data = upload.read()
        if len(data) > max_file_bytes():
            raise AttachmentError(f"« {name} » dépasse {max_file_bytes() // (1024 * 1024)} Mo.")
        if not data:
            raise AttachmentError(f"« {name} » est vide.")
        if not _sniff(ext, data[:16], data):
            raise AttachmentError(
                f"« {name} » : le contenu du fichier ne correspond pas à un fichier .{ext}."
            )
        total += len(data)
        if total > max_total_bytes():
            raise AttachmentError(
                f"Taille totale des pièces jointes supérieure à {max_total_bytes() // (1024 * 1024)} Mo."
            )
        result.append((name, data, FORMATS[ext][0]))
    return result


def limits_payload():
    return {
        "allowed_extensions": allowed_extensions(),
        "max_file_mb": max_file_bytes() // (1024 * 1024),
        "max_total_mb": max_total_bytes() // (1024 * 1024),
        "max_files": max_files(),
    }
