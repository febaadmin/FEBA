"""
apps/documents/conversion.py — Point d'entrée UNIQUE du traitement des fichiers de gabarit

Tout fichier téléversé comme gabarit passe ici, et seulement ici :

  1. le FORMAT RÉEL est lu dans le contenu (signature, structure du conteneur
     ZIP ou OLE), jamais déduit de l'extension ni du type annoncé ;
  2. extension, type annoncé et contenu doivent concorder ;
  3. le fichier est contrôlé : intégrité, taille décompressée des archives,
     macros, contenu actif ;
  4. il est NORMALISÉ vers ce que le moteur de rendu sait exploiter :
       - PDF, PNG, JPEG : tels quels (JPEG redressé selon l'EXIF) ;
       - TIFF, WEBP : image PNG (ou PDF pour un TIFF de plusieurs pages) ;
       - DOCX, DOC, ODT, RTF, PPTX, PPT, ODP : PDF produit par LibreOffice
         sans interface, dans un environnement jetable.
     Le résultat est rouvert et vérifié avant d'être accepté.

POURQUOI UN SEUL CONVERTISSEUR BUREAUTIQUE
------------------------------------------
Deux moteurs (LibreOffice ici, une bibliothèque Python là) produiraient
deux mises en page différentes du même fichier : les champs placés sur l'un
tomberaient à côté sur l'autre. LibreOffice est le seul à lire tous ces
formats ; il sert donc pour tous.

ISOLATION D'UNE CONVERSION
--------------------------
Chaque conversion a son répertoire temporaire, son PROFIL LibreOffice
(deux conversions simultanées ne partagent ni verrou ni configuration), son
délai maximal (le groupe de processus entier est tué au-delà), un
environnement minimal (aucune variable du serveur, donc aucun secret) et un
profil qui interdit les macros et le chargement de liens externes. Le
répertoire est supprimé dans tous les cas, succès ou échec. Aucune commande
n'est construite par concaténation : les arguments sont passés en liste,
et le nom de fichier transmis est fixe (« source.ext »).

MARQUEURS {{ champ }}
---------------------
Un gabarit bureautique peut contenir des marqueurs explicites, par exemple
« {{ student_name }} ». Ils sont REPÉRÉS (position exacte sur la page) puis
RETIRÉS du fond sans rien déplacer d'autre (voir plus bas) : FEBA crée à
leur emplacement des champs pré-positionnés, que l'éditeur permet
d'ajuster. Le fichier d'origine n'est jamais modifié ; c'est une copie de
travail qui est traitée. Les deux méthodes (marqueurs
et placement manuel) aboutissent à la même chose — des champs positionnés
sur un fond — et ne peuvent donc pas entrer en conflit.
"""
import io
import os
import re
import shutil
import signal
import subprocess
import tempfile
import time
import zipfile

from django.conf import settings
from django.core.exceptions import ValidationError
from reportlab.lib.units import mm


class TemplateUploadError(ValidationError):
    """Fichier refusé à l'entrée — avec la raison exacte."""


class ConversionError(TemplateUploadError):
    """Le fichier est valide mais n'a pas pu être converti en PDF exploitable."""


# ── Formats ───────────────────────────────────────────────────────────

#: Format réel → famille et libellé. `engine` : ce que le moteur de rendu
#: reçoit après normalisation.
FORMATS = {
    "pdf": {"label": "PDF", "family": "pdf", "mime": {"application/pdf", "application/x-pdf"}},
    "png": {"label": "Image PNG", "family": "image", "mime": {"image/png"}},
    "jpeg": {"label": "Image JPEG", "family": "image", "mime": {"image/jpeg", "image/pjpeg"}},
    "tiff": {"label": "Image TIFF", "family": "image", "mime": {"image/tiff", "image/tif"}},
    "webp": {"label": "Image WEBP", "family": "image", "mime": {"image/webp"}},
    "docx": {"label": "Word (DOCX)", "family": "office", "odf": "odt", "mime": {
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"}},
    "doc": {"label": "Word 97-2003 (DOC)", "family": "office", "odf": "odt", "mime": {
        "application/msword", "application/vnd.ms-word"}},
    "odt": {"label": "OpenDocument texte (ODT)", "family": "office", "odf": "odt", "mime": {
        "application/vnd.oasis.opendocument.text"}},
    "rtf": {"label": "Texte enrichi (RTF)", "family": "office", "odf": "odt", "mime": {
        "application/rtf", "text/rtf", "application/x-rtf", "text/richtext"}},
    "pptx": {"label": "PowerPoint (PPTX)", "family": "office", "odf": "odp", "mime": {
        "application/vnd.openxmlformats-officedocument.presentationml.presentation"}},
    "ppt": {"label": "PowerPoint 97-2003 (PPT)", "family": "office", "odf": "odp", "mime": {
        "application/vnd.ms-powerpoint", "application/mspowerpoint"}},
    "odp": {"label": "OpenDocument présentation (ODP)", "family": "office", "odf": "odp", "mime": {
        "application/vnd.oasis.opendocument.presentation"}},
}

#: Type MIME servi au téléchargement de l'original.
CONTENT_TYPES = {
    "pdf": "application/pdf", "png": "image/png", "jpeg": "image/jpeg", "tiff": "image/tiff",
    "webp": "image/webp", "rtf": "application/rtf", "doc": "application/msword",
    "ppt": "application/vnd.ms-powerpoint",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "odt": "application/vnd.oasis.opendocument.text",
    "odp": "application/vnd.oasis.opendocument.presentation",
}

EXTENSIONS = {
    ".pdf": "pdf", ".png": "png", ".jpg": "jpeg", ".jpeg": "jpeg", ".tif": "tiff",
    ".tiff": "tiff", ".webp": "webp", ".docx": "docx", ".doc": "doc", ".odt": "odt",
    ".rtf": "rtf", ".pptx": "pptx", ".ppt": "ppt", ".odp": "odp",
}

#: Extensions connues et REFUSÉES, avec la raison. Un refus expliqué vaut
#: mieux qu'un « format non pris en charge » qui laisse l'utilisateur deviner.
REFUSED_EXTENSIONS = {
    ".docm": "Les documents Word avec macros (DOCM) sont refusés : une macro est un programme. "
             "Enregistrez le document en DOCX (sans macros).",
    ".dotm": "Les modèles Word avec macros (DOTM) sont refusés. Enregistrez le document en DOCX.",
    ".pptm": "Les présentations avec macros (PPTM) sont refusées. Enregistrez-la en PPTX.",
    ".dot": "Les modèles Word (DOT) ne sont pas des documents : enregistrez-le en DOC ou DOCX.",
    ".dotx": "Les modèles Word (DOTX) ne sont pas des documents : enregistrez-le en DOCX.",
    ".xls": "Les classeurs Excel ne sont pas des fonds de document : exportez la page en PDF.",
    ".xlsx": "Les classeurs Excel ne sont pas des fonds de document : exportez la page en PDF.",
    ".ods": "Les classeurs ne sont pas des fonds de document : exportez la page en PDF.",
    ".gif": "Le GIF (256 couleurs) donnerait un fond de mauvaise qualité : utilisez PNG ou JPEG.",
    ".bmp": "Le BMP n'est pas accepté : enregistrez l'image en PNG.",
    ".svg": "Le SVG peut contenir du script et des références externes : exportez-le en PDF ou PNG.",
    ".heic": "Le HEIC n'est pas lu par le serveur : exportez la photo en JPEG.",
    ".pages": "Les fichiers Apple Pages ne sont pas lisibles : exportez-les en PDF ou DOCX.",
    ".key": "Les fichiers Apple Keynote ne sont pas lisibles : exportez-les en PDF ou PPTX.",
}

#: Types que le navigateur envoie quand il ne sait pas : seul le contenu,
#: vérifié de toute façon, fait foi.
GENERIC_MIME = {"", "application/octet-stream", "binary/octet-stream",
                "application/zip", "application/x-zip-compressed",
                "application/x-ole-storage", "application/cdfv2"}

#: Limites des conteneurs ZIP (DOCX, PPTX, ODT, ODP) : une « bombe » de
#: quelques Ko peut se décompresser en plusieurs Go.
ZIP_MAX_ENTRIES = 3000
ZIP_MAX_UNCOMPRESSED = 250 * 1024 * 1024
ZIP_MAX_RATIO = 200

#: Délai maximal d'une conversion bureautique, en secondes.
DEFAULT_TIMEOUT = 90

MARKER = re.compile(r"\{\{\s*([A-Za-z_][A-Za-z0-9_]*)\s*\}\}")
#: Débris de marqueur restés visibles (accolades doubles) : un marqueur que
#: la mise en page aurait coupé ne doit pas passer inaperçu.
MARKER_DEBRIS = re.compile(r"\{\{|\}\}")


def accepted_formats():
    """Formats acceptés pour l'écran — calculé, jamais recopié à la main."""
    office_ok = office_available()
    return [
        {"format": key, "label": spec["label"], "family": spec["family"],
         "extensions": sorted(ext for ext, fmt in EXTENSIONS.items() if fmt == key),
         "available": spec["family"] != "office" or office_ok}
        for key, spec in FORMATS.items()
    ]


# ── Détection du format réel ──────────────────────────────────────────

def _zip_kind(data):
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
        infos = archive.infolist()
    except (zipfile.BadZipFile, ValueError, OSError):
        return "zip-corrompu", None
    names = {info.filename for info in infos}
    if "mimetype" in names:
        try:
            mimetype = archive.read("mimetype").decode("ascii", "replace").strip()
        except (KeyError, zipfile.BadZipFile, RuntimeError, OSError):
            return "zip-corrompu", None
        return {
            "application/vnd.oasis.opendocument.text": "odt",
            "application/vnd.oasis.opendocument.presentation": "odp",
            "application/vnd.oasis.opendocument.spreadsheet": "ods",
            "application/vnd.oasis.opendocument.graphics": "odg",
        }.get(mimetype, "zip"), archive
    if "[Content_Types].xml" in names:
        if "word/document.xml" in names:
            return "docx", archive
        if "ppt/presentation.xml" in names:
            return "pptx", archive
        if "xl/workbook.xml" in names:
            return "xlsx", archive
    return "zip", archive


def _ole_kind(data):
    import olefile

    try:
        ole = olefile.OleFileIO(io.BytesIO(data))
    except Exception:  # olefile lève des exceptions variées sur un fichier abîmé
        return "ole-corrompu", None
    streams = {"/".join(entry) for entry in ole.listdir(streams=True, storages=True)}
    if "WordDocument" in streams:
        return "doc", ole
    if "PowerPoint Document" in streams:
        return "ppt", ole
    if "Workbook" in streams or "Book" in streams:
        return "xls", ole
    return "ole", ole


def detect_format(data):
    """Format RÉEL d'après le contenu : (format, conteneur ouvert ou None)."""
    head = data[:2048]
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png", None
    if head.startswith(b"\xff\xd8\xff"):
        return "jpeg", None
    if head.startswith(b"II*\x00") or head.startswith(b"MM\x00*"):
        return "tiff", None
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "webp", None
    if head.lstrip()[:5] == b"{\\rtf":
        return "rtf", None
    if b"%PDF-" in head[:1024]:
        return "pdf", None
    if head.startswith(b"PK\x03\x04"):
        return _zip_kind(data)
    if head.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"):
        return _ole_kind(data)
    return None, None


# ── Contrôles de sécurité par famille ─────────────────────────────────

def _check_zip(archive, fmt):
    infos = archive.infolist()
    if len(infos) > ZIP_MAX_ENTRIES:
        raise TemplateUploadError(
            f"Ce fichier contient {len(infos)} éléments internes : structure anormale, refusé."
        )
    total = 0
    for info in infos:
        name = info.filename.replace("\\", "/")
        if name.startswith("/") or ".." in name.split("/"):
            raise TemplateUploadError("Ce fichier contient des chemins internes anormaux : refusé.")
        total += info.file_size
        if info.compress_size and info.file_size / max(info.compress_size, 1) > ZIP_MAX_RATIO \
                and info.file_size > 10 * 1024 * 1024:
            raise TemplateUploadError(
                "Ce fichier se décompresse en un volume démesuré (archive piégée) : refusé."
            )
        lowered = name.lower()
        if "vbaproject" in lowered or "vbadata" in lowered or lowered.startswith(("basic/", "scripts/")):
            raise TemplateUploadError(
                "Ce document contient des MACROS (programmes intégrés). Il est refusé : la "
                "plateforme n'exécute jamais de macro. Enregistrez-le sans macros (DOCX, PPTX, ODT ou ODP)."
            )
    if total > ZIP_MAX_UNCOMPRESSED:
        raise TemplateUploadError(
            f"Ce fichier se décompresse en {total / 1048576:.0f} Mo : trop volumineux pour un "
            f"gabarit (au plus {ZIP_MAX_UNCOMPRESSED // 1048576} Mo)."
        )
    try:
        bad = archive.testzip()
    except (zipfile.BadZipFile, RuntimeError, OSError, EOFError, ValueError):
        bad = "?"
    if bad is not None:
        raise TemplateUploadError("Ce fichier est corrompu : une partie de son contenu est illisible.")
    if fmt in ("docx", "pptx"):
        try:
            types = archive.read("[Content_Types].xml").decode("utf-8", "replace")
        except KeyError:
            types = ""
        if "macroEnabled" in types:
            raise TemplateUploadError(
                "Ce document est enregistré « avec macros » : il est refusé. "
                "Enregistrez-le en DOCX ou PPTX standard."
            )


def _check_ole(ole):
    entries = {"/".join(entry).lower() for entry in ole.listdir(streams=True, storages=True)}
    if any(name.startswith(("macros", "_vba_project_cur", "vba")) or "/vba" in name
           for name in entries):
        raise TemplateUploadError(
            "Ce document contient des MACROS (programmes intégrés). Il est refusé : la "
            "plateforme n'exécute jamais de macro. Enregistrez-le sans macros (DOCX ou PPTX)."
        )
    if any("encryptedpackage" in name or "encryptioninfo" in name for name in entries):
        raise TemplateUploadError(
            "Ce document est protégé par mot de passe : il ne peut pas être converti. "
            "Retirez la protection puis téléversez-le."
        )


def _check_rtf(data):
    if b"\\object" in data or b"\\objdata" in data:
        raise TemplateUploadError(
            "Ce fichier RTF contient des objets incorporés (OLE), vecteur connu de code "
            "malveillant : il est refusé. Insérez les images comme images, ou enregistrez-le en DOCX."
        )
    if not data.rstrip().endswith(b"}"):
        raise TemplateUploadError("Ce fichier RTF est incomplet ou corrompu.")


# ── Inspection complète ───────────────────────────────────────────────

def _clean_filename(name):
    """Nom d'origine, pour l'affichage uniquement. Jamais un chemin."""
    base = os.path.basename(str(name or "").replace("\\", "/"))
    base = "".join(ch for ch in base if ch.isprintable() and ch not in '<>:"|?*').strip(" .")
    return base[:120] or "gabarit"


def inspect(data, filename, declared_mime=""):
    """
    Contrôle un fichier reçu. Renvoie le format réel et le nom nettoyé.

    L'extension, le type annoncé par le navigateur ET le contenu réel
    doivent concorder : un `.docx` qui est un PDF, ou un DOC annoncé
    `image/png`, est refusé — avec la raison.
    """
    name = _clean_filename(filename)
    ext = os.path.splitext(name)[1].lower()
    if ext in REFUSED_EXTENSIONS:
        raise TemplateUploadError(REFUSED_EXTENSIONS[ext])
    declared = EXTENSIONS.get(ext)
    if declared is None:
        raise TemplateUploadError(
            f"Format « {ext or 'sans extension'} » non pris en charge. Formats acceptés : "
            + ", ".join(spec["label"] for spec in FORMATS.values()) + "."
        )
    if not data:
        raise TemplateUploadError("Le fichier est vide.")

    real, container = detect_format(data)
    if real in ("zip-corrompu", "ole-corrompu"):
        raise TemplateUploadError(
            f"Ce fichier {FORMATS[declared]['label']} est corrompu : sa structure interne est illisible."
        )
    if real != declared:
        found = FORMATS.get(real, {}).get("label") or {
            "xlsx": "classeur Excel", "xls": "classeur Excel", "ods": "classeur",
            "odg": "dessin OpenDocument", "zip": "archive ZIP", "ole": "document OLE inconnu",
        }.get(real, "format inconnu")
        raise TemplateUploadError(
            f"L'extension « {ext} » ne correspond pas au contenu réel du fichier ({found}). "
            f"Fichier refusé."
        )

    mime = (declared_mime or "").split(";")[0].strip().lower()
    if mime not in GENERIC_MIME and mime not in FORMATS[real]["mime"]:
        raise TemplateUploadError(
            f"Type annoncé « {mime} » incompatible avec un fichier {ext}. Fichier refusé."
        )

    family = FORMATS[real]["family"]
    if real in ("docx", "pptx", "odt", "odp"):
        _check_zip(container, real)
    elif real in ("doc", "ppt"):
        _check_ole(container)
        container.close()
    elif real == "rtf":
        _check_rtf(data)
    if family == "office" and not office_available():
        raise ConversionError(
            "Le convertisseur bureautique (LibreOffice) n'est pas installé sur ce serveur : "
            f"le format {FORMATS[real]['label']} ne peut pas être traité ici. Il est fourni par "
            "l'image Docker de FEBA (backend/Dockerfile.prod)."
        )
    return {"format": real, "family": family, "filename": name, "extension": ext}


# ── Conversion bureautique ────────────────────────────────────────────

def soffice_path():
    configured = getattr(settings, "LIBREOFFICE_BINARY", "") or ""
    for candidate in (configured, shutil.which("soffice"), shutil.which("libreoffice"),
                      "/usr/bin/soffice", "/usr/lib/libreoffice/program/soffice"):
        if candidate and os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate
    return None


def office_available():
    return soffice_path() is not None


def conversion_timeout():
    return int(getattr(settings, "DOCUMENT_CONVERSION_TIMEOUT", DEFAULT_TIMEOUT))


def _timeout_error(timeout):
    return ConversionError(
        f"La conversion a dépassé le délai maximal ({timeout} s) et a été interrompue. "
        f"Le document est peut-être trop lourd (images très volumineuses) : allégez-le "
        f"ou exportez-le en PDF."
    )


class Deadline:
    """
    Échéance GLOBALE d'une conversion.

    CONTRAT : `DOCUMENT_CONVERSION_TIMEOUT` borne la conversion d'UN
    téléversement, toutes étapes comprises (conversion directe, passage par
    OpenDocument, rendu avec marqueurs isolés, relevé et retrait des
    marqueurs) — c'est ce qu'annoncent le réglage et le message d'erreur.

    DÉFAUT CORRIGÉ : chaque appel à LibreOffice recevait le délai ENTIER. Un
    document à marqueurs en enchaîne trois : avec un délai de 1 s, une
    conversion de 2,43 s était acceptée (mesuré lors de l'audit).
    """

    def __init__(self, timeout):
        self.timeout = timeout
        self.end = time.monotonic() + timeout

    def remaining(self):
        """Secondes restantes ; lève l'erreur de délai si l'échéance est passée."""
        left = self.end - time.monotonic()
        if left <= 0:
            raise _timeout_error(self.timeout)
        return left


#: Profil imposé à chaque conversion : macros interdites (niveau de sécurité
#: maximal, exécution désactivée), liens externes jamais mis à jour.
_PROFILE_XCU = """<?xml version="1.0" encoding="UTF-8"?>
<oor:items xmlns:oor="http://openoffice.org/2001/registry" xmlns:xs="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
<item oor:path="/org.openoffice.Office.Common/Security/Scripting"><prop oor:name="MacroSecurityLevel" oor:op="fuse"><value>3</value></prop></item>
<item oor:path="/org.openoffice.Office.Common/Security/Scripting"><prop oor:name="DisableMacrosExecution" oor:op="fuse"><value>true</value></prop></item>
<item oor:path="/org.openoffice.Office.Common/Security/Scripting"><prop oor:name="BlockUntrustedRefererLinks" oor:op="fuse"><value>true</value></prop></item>
<item oor:path="/org.openoffice.Office.Writer/Content/Update"><prop oor:name="Link" oor:op="fuse"><value>2</value></prop></item>
<item oor:path="/org.openoffice.Office.Calc/Content/Update"><prop oor:name="Link" oor:op="fuse"><value>2</value></prop></item>
<item oor:path="/org.openoffice.Office.Common/Misc"><prop oor:name="UseLocking" oor:op="fuse"><value>false</value></prop></item>
</oor:items>
"""


def _limits():  # pragma: no cover — exécuté dans le processus enfant
    import resource

    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    # Aucun fichier écrit ne dépasse 300 Mo (PDF, fichiers temporaires).
    resource.setrlimit(resource.RLIMIT_FSIZE, (300 * 1024 * 1024, 300 * 1024 * 1024))


def soffice_convert(data, source_ext, target, *, timeout=None, deadline=None):
    """
    Convertit `data` (extension `source_ext`) vers `target` (« pdf », « odt »,
    « odp ») avec LibreOffice, dans un environnement jetable. Renvoie
    `(octets, rapport)`. Lève ConversionError, avec une raison lisible.

    `deadline` (Deadline) : le processus ne reçoit que le temps RESTANT de
    l'échéance globale ; le message cite le délai global configuré.
    """
    binary = soffice_path()
    if binary is None:
        raise ConversionError("Le convertisseur bureautique (LibreOffice) n'est pas installé.")
    if deadline is None:
        deadline = Deadline(timeout or conversion_timeout())
    budget = deadline.remaining()
    filters = {"pdf": "pdf", "odt": "odt", "odp": "odp"}
    workdir = tempfile.mkdtemp(prefix="feba-conversion-")
    started = time.monotonic()
    try:
        profile = os.path.join(workdir, "profil")
        os.makedirs(os.path.join(profile, "user"))
        with open(os.path.join(profile, "user", "registrymodifications.xcu"), "w",
                  encoding="utf-8") as handle:
            handle.write(_PROFILE_XCU)
        output = os.path.join(workdir, "sortie")
        os.makedirs(output)
        source = os.path.join(workdir, f"source{source_ext}")
        with open(source, "wb") as handle:
            handle.write(data)
        command = [
            binary, f"-env:UserInstallation=file://{profile}", "--headless", "--invisible",
            "--nologo", "--nodefault", "--nolockcheck", "--norestore", "--nofirststartwizard",
            "--convert-to", filters[target], "--outdir", output, source,
        ]
        env = {"HOME": workdir, "PATH": "/usr/local/bin:/usr/bin:/bin", "LANG": "C.UTF-8",
               "TMPDIR": workdir, "SAL_USE_VCLPLUGIN": "svp"}
        process = subprocess.Popen(
            command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env, cwd=workdir,
            start_new_session=True, preexec_fn=_limits if os.name == "posix" else None,
        )
        try:
            _stdout, stderr = process.communicate(timeout=budget)
        except subprocess.TimeoutExpired:
            _kill_group(process)
            raise _timeout_error(deadline.timeout)
        except BaseException:
            # Interruption inattendue (signal, erreur) : aucun LibreOffice
            # ne doit survivre à la requête.
            _kill_group(process)
            raise
        finally:
            # Un descendant détaché (soffice.bin) peut survivre au parent :
            # le groupe entier est arrêté dans tous les cas.
            _kill_group(process, wait=False)
        result = os.path.join(output, f"source.{target}")
        if process.returncode != 0 or not os.path.isfile(result) or os.path.getsize(result) == 0:
            detail = (stderr or b"").decode("utf-8", "replace").strip().splitlines()[-1:]
            raise ConversionError(
                "La conversion de ce document a échoué : LibreOffice n'a pas pu le lire "
                "(fichier abîmé, protégé ou d'un type inattendu)."
                + (f" Détail : {detail[0][:200]}" if detail else "")
            )
        with open(result, "rb") as handle:
            content = handle.read()
        return content, {"engine": "libreoffice", "target": target,
                         "seconds": round(time.monotonic() - started, 2)}
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


def _kill_group(process, wait=True):
    """Arrête le processus et TOUS ses descendants (session dédiée)."""
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        pass
    if wait:
        try:
            process.communicate(timeout=10)
        except Exception:  # pragma: no cover — processus déjà récolté
            pass


# ── Marqueurs {{ champ }} dans un document OpenDocument ───────────────
#
# POURQUOI ILS NE SONT PAS SIMPLEMENT EFFACÉS DU DOCUMENT
# -------------------------------------------------------
# Remplacer « {{ school_year }} » par des espaces change la largeur de la
# ligne : sur une ligne centrée, tout le texte voisin se décale, et la
# valeur écrite à l'emplacement relevé vient chevaucher « pour l'année
# scolaire ». (Constaté sur un rendu réel, puis corrigé ainsi.)
#
# Les marqueurs sont donc ISOLÉS dans leur propre portion de texte (style
# sans effet sur la mise en page), le document est rendu UNE fois, leurs
# positions sont relevées sur CE rendu, puis leurs objets texte sont
# retirés de CE MÊME PDF. Le fond est identique au point près, marqueurs
# en moins.

_TOKENS = re.compile(r"(<[^>]+>)|([^<]+)")
_PARA_OPEN = re.compile(r"^<text:(p|h)[\s>/]")
_PARA_CLOSE = re.compile(r"^</text:(p|h)>")
_MARKER_STYLE = "FebaMarqueur"
#: Style « neutre » : langue « sans contenu linguistique », aucun attribut
#: de métrique. Il ne sert qu'à faire du marqueur une portion à part.
_MARKER_STYLE_XML = (
    f'<style:style style:name="{_MARKER_STYLE}" style:family="text">'
    '<style:text-properties fo:language="zxx" fo:country="none"/></style:style>'
)


def _isolate_in_xml(xml):
    """
    Place chaque marqueur dans un `<text:span>` à lui, paragraphe par
    paragraphe — y compris quand Word l'a découpé entre plusieurs portions :
    son texte est alors regroupé dans la première. Renvoie `(xml, nombre)`.
    """
    tokens = [m.group(0) for m in _TOKENS.finditer(xml)]
    stack, count = [], 0
    for index, token in enumerate(tokens):
        if token.startswith("<"):
            if _PARA_CLOSE.match(token):
                if stack:
                    count += _isolate_in_paragraph(tokens, stack.pop())
            elif _PARA_OPEN.match(token) and not token.endswith("/>"):
                stack.append([])
        elif stack:
            stack[-1].append(index)
    xml = "".join(tokens)
    if count:
        if "</office:automatic-styles>" in xml:
            xml = xml.replace("</office:automatic-styles>",
                              _MARKER_STYLE_XML + "</office:automatic-styles>", 1)
        elif "<office:automatic-styles/>" in xml:
            xml = xml.replace("<office:automatic-styles/>",
                              f"<office:automatic-styles>{_MARKER_STYLE_XML}</office:automatic-styles>", 1)
        else:
            raise ConversionError("Structure OpenDocument inattendue : styles automatiques absents.")
    return xml, count


def _isolate_in_paragraph(tokens, indexes):
    text = "".join(tokens[i] for i in indexes)
    matches = list(MARKER.finditer(text))
    if not matches:
        return 0
    # Position de chaque caractère : (jeton, décalage dans le jeton).
    owner = [(i, offset) for i in indexes for offset in range(len(tokens[i]))]
    edits = {}  # jeton -> liste de (début, fin, remplacement)
    for match in reversed(matches):
        literal = match.group(0)
        first_token, first_offset = owner[match.start()]
        # Texte du marqueur retiré des jetons qui le portent…
        spans = {}
        for position in range(match.start(), match.end()):
            token, offset = owner[position]
            low, high = spans.get(token, (offset, offset))
            spans[token] = (min(low, offset), max(high, offset))
        for token, (low, high) in spans.items():
            replacement = ""
            if token == first_token:
                # …et réinséré, entier et isolé, dans le premier.
                replacement = f'<text:span text:style-name="{_MARKER_STYLE}">{literal}</text:span>'
            edits.setdefault(token, []).append((low, high + 1, replacement))
    for token, changes in edits.items():
        value = tokens[token]
        for low, high, replacement in sorted(changes, reverse=True):
            value = value[:low] + replacement + value[high:]
        tokens[token] = value
    return len(matches)


def isolate_markers_odf(odf_bytes):
    """Copie du document OpenDocument aux marqueurs isolés. Renvoie (octets, nombre)."""
    source = zipfile.ZipFile(io.BytesIO(odf_bytes))
    out = io.BytesIO()
    total = 0
    with zipfile.ZipFile(out, "w") as target:
        for info in source.infolist():
            content = source.read(info.filename)
            if info.filename in ("content.xml", "styles.xml"):
                xml, count = _isolate_in_xml(content.decode("utf-8"))
                content = xml.encode("utf-8")
                total += count
            # « mimetype » doit rester le premier élément, non compressé.
            compression = zipfile.ZIP_STORED if info.filename == "mimetype" else zipfile.ZIP_DEFLATED
            target.writestr(info, content, compress_type=compression)
    return out.getvalue(), total


def _text_of(obj, textpage):
    import ctypes

    import pypdfium2.raw as raw

    size = raw.FPDFTextObj_GetText(obj, textpage, None, 0)
    if size <= 2:
        return ""
    buffer = ctypes.create_string_buffer(size)
    raw.FPDFTextObj_GetText(obj, textpage, ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ushort)), size)
    return buffer.raw[:size].decode("utf-16-le", "replace").rstrip("\x00")


def remove_marker_objects(pdf_bytes):
    """
    Retire du PDF les objets texte qui ne contiennent QUE des marqueurs.
    Tout le reste du fichier — dessin, images, autres textes — est conservé
    tel quel. Renvoie `(octets, nombre_retiré)`.
    """
    import pypdfium2 as pdfium
    import pypdfium2.raw as raw

    only_markers = re.compile(r"\s*(\{\{\s*[A-Za-z_][A-Za-z0-9_]*\s*\}\}\s*)+")
    document = pdfium.PdfDocument(pdf_bytes)
    removed = 0
    modified = set()
    try:
        for page_index in range(len(document)):
            page = document[page_index]
            textpage = page.get_textpage()
            try:
                doomed = []
                for k in range(raw.FPDFPage_CountObjects(page)):
                    obj = raw.FPDFPage_GetObject(page, k)
                    if raw.FPDFPageObj_GetType(obj) == raw.FPDF_PAGEOBJ_TEXT:
                        text = _text_of(obj, textpage)
                        if only_markers.fullmatch(text):
                            doomed.append((obj, len(MARKER.findall(text))))
                for obj, markers in doomed:
                    if raw.FPDFPage_RemoveObject(page, obj):
                        raw.FPDFPageObj_Destroy(obj)
                        removed += markers
                if doomed:
                    raw.FPDFPage_GenerateContent(page)
                    modified.add(page_index)
            finally:
                textpage.close()
        if not modified:
            return pdf_bytes, 0
        out = io.BytesIO()
        document.save(out)
    finally:
        document.close()
    return _recompose(pdf_bytes, out.getvalue(), modified), removed


def _recompose(original, cleaned, modified):
    """
    Pages nettoyées là où des marqueurs ont été retirés, pages D'ORIGINE
    partout ailleurs. PDFium, en régénérant une page, réécrit les polices
    qu'elle partage avec les autres : sans cette recomposition, le texte
    des pages non modifiées devenait illisible à l'extraction (constaté sur
    un document de deux pages).
    """
    from pypdf import PdfReader, PdfWriter

    first, second = PdfReader(io.BytesIO(original)), PdfReader(io.BytesIO(cleaned))
    writer = PdfWriter()
    for index in range(len(first.pages)):
        writer.add_page(second.pages[index] if index in modified else first.pages[index])
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def locate_markers(pdf_bytes):
    """
    Marqueurs `{{ nom }}` et leur position exacte, page par page.
    Renvoie [{page, name, x_mm, y_mm, width_mm, height_mm, size_pt}] —
    coordonnées depuis le coin HAUT-GAUCHE de la page, comme l'éditeur.
    """
    import pypdfium2 as pdfium

    found = []
    document = pdfium.PdfDocument(pdf_bytes)
    try:
        for page_index in range(len(document)):
            page = document[page_index]
            width_pt, height_pt = page.get_size()
            textpage = page.get_textpage()
            try:
                count = textpage.count_chars()
                text = textpage.get_text_range(0, count) if count else ""
                for match in MARKER.finditer(text):
                    literal = match.group(0)
                    searcher = textpage.search(literal, match_case=True)
                    try:
                        hit = searcher.get_next()
                        while hit is not None:
                            start, length = hit
                            boxes = [textpage.get_charbox(i) for i in range(start, start + length)]
                            boxes = [b for b in boxes if b[2] > b[0]]
                            if boxes:
                                left = min(b[0] for b in boxes)
                                right = max(b[2] for b in boxes)
                                bottom = min(b[1] for b in boxes)
                                top = max(b[3] for b in boxes)
                                entry = {
                                    "page": page_index, "name": match.group(1),
                                    "x_mm": round(left / mm, 2),
                                    "y_mm": round((height_pt - top) / mm, 2),
                                    "width_mm": round((right - left) / mm, 2),
                                    "height_mm": round((top - bottom) / mm, 2),
                                    "size_pt": round((top - bottom) / 0.72, 1),
                                }
                                if entry not in found:
                                    found.append(entry)
                            hit = searcher.get_next()
                    finally:
                        searcher.close()
            finally:
                textpage.close()
    finally:
        document.close()
    return found


#: Caractères de remplissage (« Nom : ........ ») : on peut écrire dessus.
#: Seuls pointillés, soulignés et espaces : un tiret ou un deux-points est
#: du texte (« 2025 — 2026 », « Nom : ») et ne doit pas être recouvert.
FILLER_CHARS = set(" .\u2026_\u00b7\u00a0\t\r\n")


def text_boxes(pdf, page_index):
    """
    Caractères visibles d'une page du fond et leur boîte, en mm depuis le
    coin HAUT-GAUCHE (repère de l'éditeur) : [(car, x0, y0, x1, y1)].
    `pdf` : octets ou chemin.
    """
    import pypdfium2 as pdfium

    document = pdfium.PdfDocument(pdf)
    try:
        page = document[page_index]
        left, bottom, _right, top = page.get_cropbox()
        textpage = page.get_textpage()
        try:
            import pypdfium2.raw as raw

            boxes = []
            for index in range(textpage.count_chars()):
                # Caractère lu À SON INDEX : le texte « assemblé » de la page
                # contient des caractères générés (retours, espaces) qui
                # décaleraient la correspondance avec les boîtes.
                code = raw.FPDFText_GetUnicode(textpage, index)
                char = chr(code) if code else ""
                if not char or char in FILLER_CHARS or not char.isprintable():
                    continue
                x0, y0, x1, y1 = textpage.get_charbox(index)
                if x1 <= x0 or y1 <= y0:
                    continue
                boxes.append((char, (x0 - left) / mm, (top - y1) / mm, (x1 - left) / mm, (top - y0) / mm))
            return boxes
        finally:
            textpage.close()
    finally:
        document.close()


def _line_neighbours(markers, clean_pdf):
    """
    Pour chaque marqueur : texte du fond le plus proche à sa gauche et à sa
    droite SUR SA LIGNE (le marqueur, lui, a été retiré). Le champ créé à
    sa place ne doit pas déborder sur ce texte.
    """
    by_page = {}
    for marker in markers:
        by_page.setdefault(marker["page"], []).append(marker)
    for page_index, items in by_page.items():
        boxes = text_boxes(clean_pdf, page_index)
        for marker in items:
            top, bottom = marker["y_mm"], marker["y_mm"] + marker["height_mm"]
            line = [b for b in boxes if b[2] < bottom - 0.2 and b[4] > top + 0.2]
            right = [b[1] for b in line if b[1] >= marker["x_mm"] - 0.2]
            left = [b[3] for b in line if b[3] <= marker["x_mm"] + 0.2]
            marker["text_right_mm"] = round(min(right), 2) if right else None
            marker["text_left_mm"] = round(max(left), 2) if left else None
    return markers


def pdf_text(pdf_bytes, page_index=None):
    import pypdfium2 as pdfium

    document = pdfium.PdfDocument(pdf_bytes)
    try:
        pages = range(len(document)) if page_index is None else [page_index]
        parts = []
        for index in pages:
            textpage = document[index].get_textpage()
            try:
                parts.append(textpage.get_text_bounded())
            finally:
                textpage.close()
        return "\n".join(parts)
    finally:
        document.close()


def convert_office(data, fmt, extension):
    """
    Document bureautique → PDF normalisé (+ marqueurs repérés et effacés).

    Sans marqueur : une seule conversion directe, la plus fidèle.
    Avec marqueurs : le document passe par OpenDocument (ODT ou ODP), où
    chaque marqueur est isolé ; un seul rendu PDF sert à relever leurs
    positions PUIS, privé de leurs objets texte, de fond.
    """
    deadline = Deadline(conversion_timeout())
    pdf, report = soffice_convert(data, extension, "pdf", deadline=deadline)
    report["markers"] = []
    if not MARKER.search(pdf_text(pdf)):
        deadline.remaining()
        return pdf, report

    odf_format = FORMATS[fmt]["odf"]
    odf, odf_report = (data, {"seconds": 0}) if fmt == odf_format else \
        soffice_convert(data, extension, odf_format, deadline=deadline)
    isolated, count = isolate_markers_odf(odf)
    with_markers, rendered = soffice_convert(isolated, f".{odf_format}", "pdf", deadline=deadline)
    report["markers"] = locate_markers(with_markers)
    clean, removed = remove_marker_objects(with_markers)
    _line_neighbours(report["markers"], clean)
    # Le relevé et le retrait des marqueurs comptent dans le délai global.
    deadline.remaining()
    report["markers_erased"] = removed
    report["seconds"] = round(report["seconds"] + odf_report["seconds"] + rendered["seconds"], 2)
    report["via"] = odf_format
    leftover = MARKER_DEBRIS.findall(pdf_text(clean))
    if leftover or removed < count:
        raise ConversionError(
            "Des marqueurs {{ … }} n'ont pas pu être retirés du fond (marqueur coupé par un "
            "saut de ligne, placé dans un élément graphique ou mal fermé). Corrigez-les dans "
            "le document, ou retirez-les et placez les champs dans l'éditeur."
        )
    return clean, report


# ── Images ────────────────────────────────────────────────────────────

def normalize_image(data, fmt):
    """
    TIFF / WEBP (et JPEG orienté) → PNG redressé. Un TIFF de plusieurs pages
    devient un PDF (une page par image), pour pouvoir choisir la page.
    Renvoie `(octets, format_moteur, info)`.
    """
    from PIL import Image, ImageOps

    with Image.open(io.BytesIO(data)) as image:
        frames = getattr(image, "n_frames", 1)
        if fmt == "tiff" and frames > 1:
            pages = []
            for index in range(min(frames, 10)):
                image.seek(index)
                pages.append(ImageOps.exif_transpose(image.copy()).convert("RGB"))
            out = io.BytesIO()
            dpi = float((image.info.get("dpi") or (0, 0))[0] or 0)
            if not 72 <= dpi <= 1200:
                # Résolution absente ou fantaisiste (un TIFF sans en-tête de
                # résolution vaut « 1 dpi » : une page de plusieurs mètres).
                # La page est alors dimensionnée pour tenir sur un A4.
                dpi = max(pages[0].size) / (297 / 25.4)
            pages[0].save(out, "PDF", save_all=True, append_images=pages[1:], resolution=dpi)
            return out.getvalue(), "pdf", {"frames": frames}
        upright = ImageOps.exif_transpose(image)
        if upright.mode not in ("RGB", "RGBA", "L"):
            upright = upright.convert("RGBA" if "A" in upright.mode else "RGB")
        out = io.BytesIO()
        upright.save(out, "PNG", optimize=True)
        return out.getvalue(), "png", {"frames": frames}
