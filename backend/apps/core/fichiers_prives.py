"""
Fichiers de MEDIA_ROOT liés à une personne : bulletins, reçus, photos d'élèves,
pièces jointes. nginx refuse ces dossiers ; ils ne sortent que par un lien signé
et limité dans le temps, produit par l'API pour qui a le droit de les voir.

Le stockage par défaut signe les URL : tout `.url`, y compris dans les
sérialiseurs, donne le bon lien sans autre modification.
"""
import mimetypes
import os

from django.conf import settings
from django.core import signing
from django.core.files.storage import FileSystemStorage
from django.http import FileResponse, HttpResponse, HttpResponseNotFound
from django.utils._os import safe_join
from django.views.decorators.clickjacking import xframe_options_sameorigin
from django.views.decorators.http import require_GET

# Même liste que le refus de nginx (nginx/nginx.prod.conf).
DOSSIERS_PRIVES = (
    "bulletins", "receipts", "students", "homework", "messages",
    "user_files", "attendance", "announcements",
)
SEL = "feba.fichiers-prives"
AFFICHABLES = {"application/pdf", "image/jpeg", "image/png", "image/webp", "image/gif"}


def est_prive(nom):
    return str(nom).replace("\\", "/").split("/", 1)[0] in DOSSIERS_PRIVES


class StockageMedia(FileSystemStorage):
    def url(self, name):
        if name and est_prive(name):
            return f"/api/files/{signing.dumps(str(name), salt=SEL)}/"
        return super().url(name)


@require_GET
@xframe_options_sameorigin
def telecharger(request, jeton):
    try:
        nom = signing.loads(jeton, salt=SEL, max_age=settings.PRIVATE_FILE_LINK_SECONDS)
    except signing.SignatureExpired:
        return HttpResponse("Ce lien a expiré. Rechargez la page pour en obtenir un nouveau.",
                            status=403, content_type="text/plain; charset=utf-8")
    except signing.BadSignature:
        return HttpResponseNotFound()
    if not est_prive(nom):
        return HttpResponseNotFound()
    try:
        chemin = safe_join(settings.MEDIA_ROOT, nom)
    except Exception:
        return HttpResponseNotFound()
    if not os.path.isfile(chemin):
        return HttpResponseNotFound()

    type_mime = mimetypes.guess_type(chemin)[0] or "application/octet-stream"
    # Un fichier déposé (HTML, SVG…) ne s'exécute jamais sur le domaine FEBA.
    reponse = FileResponse(open(chemin, "rb"), content_type=type_mime,
                           as_attachment=type_mime not in AFFICHABLES,
                           filename=os.path.basename(chemin))
    reponse["Cache-Control"] = "private, no-store"
    reponse["X-Content-Type-Options"] = "nosniff"
    reponse["Referrer-Policy"] = "no-referrer"
    return reponse
