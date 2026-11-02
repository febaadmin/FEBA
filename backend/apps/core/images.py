"""Image déposée par un utilisateur : contenu réel contrôlé, nom imposé."""
import uuid

from django.core.files.uploadedfile import UploadedFile
from PIL import Image, UnidentifiedImageError
from rest_framework.exceptions import ValidationError

FORMATS = {"PNG": "png", "JPEG": "jpg", "WEBP": "webp", "GIF": "gif"}
TAILLE_MAX = 5 * 1024 * 1024


def image_sure(fichier: UploadedFile) -> UploadedFile:
    """
    Refuse tout ce qui n'est pas une vraie image, quels que soient son nom et son type annoncé.
    L'extension vient du format lu : le dossier des avatars est public, et un fichier .html ou
    .svg y exécuterait du script sur le domaine FEBA, où se trouve la session.
    """
    if fichier.size > TAILLE_MAX:
        raise ValidationError({"avatar": "Image de 5 Mo au plus attendue."})
    try:
        image = Image.open(fichier)
        image.verify()
        extension = FORMATS.get(image.format)
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError):
        extension = None
    if extension is None:
        raise ValidationError({"avatar": "Image PNG, JPEG, WEBP ou GIF attendue."})
    fichier.seek(0)
    fichier.name = f"{uuid.uuid4().hex}.{extension}"
    return fichier
