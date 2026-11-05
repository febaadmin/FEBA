"""
apps/notifications/campaign_views.py — API des envois d'e-mails groupés.

    GET  /api/mass-email/options/?academy_id=     académies, types de profil, état SMTP
    GET  /api/mass-email/recipients/?academy_id=&roles=&search=
    POST /api/mass-email/preview/                 destinataires effectifs, sans envoi
    GET  /api/mass-email/campaigns/?academy_id=   historique
    POST /api/mass-email/campaigns/               création + mise en file
    GET  /api/mass-email/campaigns/<id>/          rapport détaillé
    POST /api/mass-email/campaigns/<id>/retry-failed/

PERMISSIONS
-----------
Administrateurs (leur académie, et elle seule) et super-administrateurs
(une académie active, choisie explicitement). L'académie demandée est
TOUJOURS revalidée ici : un `academy_id` d'une autre académie envoyé par un
administrateur est refusé (403), jamais « corrigé ».
"""
from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsAdminOrAbove
from apps.core.tenancy import get_request_school

from . import campaigns as svc
from .campaign_models import EmailCampaign, EmailCampaignRecipient
from django.conf import settings

from .attachments import limits_payload
from .mailer import current_transport, provider_is_configured


def resolve_academy(request, raw_id=None):
    """Académie autorisée pour cette requête, ou erreur explicite."""
    from apps.accounts.entity_views import accessible_entities

    user = request.user
    if raw_id in (None, ""):
        raw_id = request.query_params.get("academy_id")
    if raw_id in (None, "") and request.method == "POST":
        raw_id = request.data.get("academy_id")
    if user.is_superadmin():
        if raw_id in (None, ""):
            academy = get_request_school(request)
            if academy is None:
                raise ValidationError({"academy_id": "Choisissez l'académie destinataire."})
            return academy
        try:
            academy_pk = int(raw_id)
        except (TypeError, ValueError):
            raise ValidationError({"academy_id": "Académie invalide."})
        academy = accessible_entities(user).filter(pk=academy_pk).first()
        if academy is None:
            raise ValidationError({"academy_id": "Académie inconnue ou inactive."})
        return academy

    academy = getattr(user, "school", None)
    if academy is None:
        raise PermissionDenied("Votre compte n'est rattaché à aucune académie.")
    if raw_id not in (None, "") and str(raw_id) != str(academy.pk):
        raise PermissionDenied(
            "Vous ne pouvez envoyer des e-mails qu'aux membres de votre académie."
        )
    return academy


def _audience_from(data):
    try:
        return svc.normalize_audience(data)
    except svc.AudienceError as exc:
        raise ValidationError({exc.field or "non_field_errors": str(exc)})


def _academy_payload(academy):
    return {"id": academy.pk, "code": academy.code, "name": academy.name,
            "short_name": getattr(academy, "short_name", academy.name)}


def campaign_summary(campaign):
    counts = campaign.counts()
    return {
        "id": campaign.pk,
        "academy": _academy_payload(campaign.academy),
        "subject": campaign.subject,
        "status": campaign.status,
        "status_display": campaign.get_status_display(),
        "created_by": campaign.created_by_email,
        "created_at": campaign.created_at,
        "started_at": campaign.started_at,
        "finished_at": campaign.finished_at,
        "total_recipients": campaign.total_recipients,
        "skipped_count": campaign.skipped_count,
        "counts": counts,
        "audience": campaign.audience,
        "body_format": campaign.body_format,
        "mode": campaign.mode,
        "last_error": campaign.last_error,
        "attachments": [
            {"id": a.pk, "name": a.original_name, "size": a.size, "content_type": a.content_type}
            for a in (campaign.content.attachments.all() if campaign.content_id else [])
        ],
    }


class MassEmailOptionsView(APIView):
    permission_classes = [IsAuthenticated, IsAdminOrAbove]

    def get(self, request):
        from apps.accounts.entity_views import accessible_entities

        academy = resolve_academy(request)
        academies = (
            accessible_entities(request.user) if request.user.is_superadmin()
            else [academy]
        )
        return Response({
            "academy": _academy_payload(academy),
            "academies": [_academy_payload(a) for a in academies],
            "roles": svc.audience_roles(academy),
            "provider_configured": provider_is_configured(),
            "transport": current_transport(),
            "capture_ui_url": getattr(settings, "MAILPIT_UI_URL", ""),
            "max_recipients": svc.max_recipients(),
            "attachments": limits_payload(),
        })


class MassEmailRecipientsView(APIView):
    """Comptes sélectionnables de l'académie, avec leur envoyabilité."""
    permission_classes = [IsAuthenticated, IsAdminOrAbove]

    def get(self, request):
        academy = resolve_academy(request)
        roles = [r for r in (request.query_params.get("roles") or "").split(",") if r]
        if set(roles) - set(svc.AUDIENCE_ROLES):
            raise ValidationError({"roles": "Type de profil inconnu."})
        users = svc.academy_users(academy)
        if roles:
            users = users.filter(role__in=roles)
        search = (request.query_params.get("search") or "").strip()
        if search:
            users = users.filter(
                Q(first_name__icontains=search) | Q(last_name__icontains=search)
                | Q(email__icontains=search)
            )
        rows = []
        for user in users.order_by("last_name", "first_name", "pk")[:2000]:
            state, email = svc._email_status(user)
            rows.append({
                "id": user.pk, "full_name": user.get_full_name() or email, "email": email,
                "role": user.role, "role_label": svc.ROLE_LABELS.get(user.role, user.role),
                "is_active": user.is_active, "sendable": state == EmailCampaignRecipient.PENDING,
                "status": state,
            })
        return Response({"academy": _academy_payload(academy), "results": rows})


class MassEmailPreviewView(APIView):
    permission_classes = [IsAuthenticated, IsAdminOrAbove]

    def post(self, request):
        academy = resolve_academy(request)
        audience = _audience_from(request.data)
        try:
            resolution = svc.resolve_audience(academy, audience)
        except svc.AudienceError as exc:
            raise ValidationError({exc.field or "non_field_errors": str(exc)})
        payload = svc.preview_payload(resolution)
        payload["academy"] = _academy_payload(academy)
        # Aperçu fidèle du message mis en forme : le HTML tel qu'il sera ENVOYÉ (nettoyé ici).
        if request.data.get("body_format") == EmailCampaign.HTML:
            from .html_securise import HtmlRefuse, en_texte, nettoyer
            try:
                propre = nettoyer(request.data.get("body_html"))
            except HtmlRefuse as exc:
                raise ValidationError({"body": str(exc)})
            payload["html_nettoye"], payload["texte"] = propre, en_texte(propre)
        payload["provider_configured"] = provider_is_configured()
        return Response(payload)


class MassEmailCampaignListView(APIView):
    permission_classes = [IsAuthenticated, IsAdminOrAbove]

    def get(self, request):
        """Envois de l'académie ; `q` (objet, destinataire), `statut`, `du` / `au` (dates d'envoi)."""
        from django.utils.dateparse import parse_date
        academy = resolve_academy(request)
        qs = EmailCampaign.objects.filter(academy=academy).select_related("academy", "content")
        p = request.query_params
        q = (p.get("q") or "").strip()[:100]
        if q:
            qs = qs.filter(Q(subject__icontains=q) | Q(recipients__email__icontains=q)
                           | Q(recipients__full_name__icontains=q)).distinct()
        statut = p.get("statut")
        if statut:
            if statut not in dict(EmailCampaign.STATUS_CHOICES):
                raise ValidationError({"statut": "Statut inconnu."})
            qs = qs.filter(status=statut)
        for cle, lookup in (("du", "created_at__date__gte"), ("au", "created_at__date__lte")):
            if p.get(cle):
                jour = parse_date(p[cle]) if len(p[cle]) == 10 else None
                if jour is None:
                    raise ValidationError({cle: "Date invalide (AAAA-MM-JJ)."})
                qs = qs.filter(**{lookup: jour})
        campaigns = qs.order_by("-created_at")[:200]
        return Response({"results": [campaign_summary(c) for c in campaigns]})

    def post(self, request):
        """
        JSON, ou multipart (`payload` = JSON des champs + fichiers
        `attachments`) quand le message porte des pièces jointes.
        """
        import json

        from .attachments import AttachmentError, validate_uploads

        data = request.data
        files = []
        if "payload" in data:
            try:
                data = json.loads(data["payload"])
            except (TypeError, ValueError):
                raise ValidationError({"payload": "Données du formulaire illisibles."})
            files = request.FILES.getlist("attachments")
        academy = resolve_academy(request, raw_id=data.get("academy_id"))
        audience = _audience_from(data)
        if data.get("confirm") is not True:
            raise ValidationError({"confirm": "Confirmation explicite requise avant l'envoi."})
        try:
            attachments = validate_uploads(files)
        except AttachmentError as exc:
            raise ValidationError({"attachments": str(exc)})
        brouillon = None
        if data.get("brouillon_id"):
            from .campaign_models import BrouillonEmail
            from apps.core.request_text import identifiant
            brouillon = BrouillonEmail.objects.filter(pk=identifiant(data["brouillon_id"]) or 0, auteur=request.user,
                                                      academy=academy).first()
            if brouillon is None:
                raise ValidationError({"brouillon_id": "Brouillon introuvable."})
            # Pièces du brouillon (déjà validées au dépôt) + nouvelles pièces jointes.
            deja = [(pj.nom, pj.lire(), pj.type_mime) for pj in brouillon.pieces.all()]
            if deja:
                from .attachments import max_files, max_total_bytes
                if len(deja) + len(attachments) > max_files():
                    raise ValidationError({"attachments": f"Au plus {max_files()} pièces jointes par message."})
                if sum(len(d) for _, d, _ in deja + attachments) > max_total_bytes():
                    raise ValidationError({"attachments": "Taille totale des pièces jointes dépassée."})
                attachments = deja + attachments
        try:
            campaign, created = svc.create_campaign(
                academy=academy, user=request.user,
                subject=data.get("subject"), body=data.get("body"),
                audience=audience, client_token=data.get("client_token"),
                expected_count=data.get("expected_count"), attachments=attachments,
                body_format=data.get("body_format") or "texte", body_html=data.get("body_html") or "",
                brouillon=brouillon,
            )
        except svc.AudienceError as exc:
            raise ValidationError({exc.field or "non_field_errors": str(exc)})
        if campaign.academy_id != academy.pk:
            # Jeton réutilisé pour une autre académie : on ne renvoie rien.
            raise ValidationError({"client_token": "Jeton déjà utilisé pour un autre envoi."})
        body = campaign_summary(campaign)
        body["created"] = created
        return Response(body, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


class MassEmailCampaignDetailView(APIView):
    permission_classes = [IsAuthenticated, IsAdminOrAbove]

    def get_campaign(self, request, pk):
        academy = resolve_academy(request)
        # Filtré par académie : l'identifiant d'une campagne d'une autre
        # académie répond 404, comme s'il n'existait pas.
        return get_object_or_404(
            EmailCampaign.objects.select_related("academy"), pk=pk, academy=academy,
        )

    def get(self, request, pk):
        campaign = self.get_campaign(request, pk)
        body = campaign_summary(campaign)
        body["body"] = campaign.body
        body["body_html"] = campaign.body_html
        body["recipients"] = [
            {
                "id": r.pk, "user_id": r.user_id, "full_name": r.full_name, "email": r.email,
                "champ": r.champ, "champ_display": r.get_champ_display(),
                "role": r.role, "status": r.status, "status_display": r.get_status_display(),
                "attempts": r.attempts, "error": r.error, "sent_at": r.sent_at,
                "used_real_provider": bool(r.delivery and r.delivery.used_real_provider),
                "delivery_id": r.delivery_id,
                "transport": r.delivery.transport if r.delivery else "",
                "delivery_summary": r.delivery.delivery_summary() if r.delivery else "",
            }
            for r in campaign.recipients.select_related("delivery").order_by("status", "full_name")
        ]
        return Response(body)


class MassEmailRetryFailedView(MassEmailCampaignDetailView):
    def post(self, request, pk):
        campaign = self.get_campaign(request, pk)
        requeued = svc.retry_failed(campaign)
        body = campaign_summary(campaign)
        body["requeued"] = requeued
        return Response(body)


# ── Brouillons et signature ───────────────────────────────────────────

def _brouillon_payload(b):
    return {
        "id": b.pk, "objet": b.objet, "corps": b.corps, "corps_html": b.corps_html, "format": b.format,
        "mode": b.mode, "audience": b.audience, "cree_le": b.cree_le, "modifie_le": b.modifie_le,
        "pieces": [{"id": p.pk, "nom": p.nom, "taille": p.taille, "type": p.type_mime} for p in b.pieces.all()],
    }


def _remplir_brouillon(b, data):
    from .campaign_models import BrouillonEmail
    objet = str(data.get("objet") or "").strip()
    if len(objet) > 200:
        raise ValidationError({"objet": "L'objet ne peut pas dépasser 200 caractères."})
    fmt = data.get("format") or BrouillonEmail._meta.get_field("format").default
    if fmt not in dict(EmailCampaign.FORMAT_CHOICES):
        raise ValidationError({"format": "Format inconnu."})
    corps_html = ""
    if fmt == EmailCampaign.HTML and (data.get("corps_html") or "").strip():
        from .html_securise import HtmlRefuse, nettoyer
        try:
            corps_html = nettoyer(data["corps_html"])
        except HtmlRefuse:
            corps_html = ""          # brouillon vide : accepté, l'envoi le refusera
    # Les règles et adresses sont validées à l'enregistrement (forme) et revalidées à l'envoi.
    audience = svc.normalize_audience(data.get("audience") or {})
    b.objet, b.corps, b.corps_html, b.format = objet, str(data.get("corps") or "")[:50000], corps_html, fmt
    b.mode, b.audience = audience["mode"], audience
    return b


class BrouillonListeView(APIView):
    """GET : mes brouillons dans cette académie ; POST : nouveau brouillon."""
    permission_classes = [IsAuthenticated, IsAdminOrAbove]

    def get(self, request):
        from .campaign_models import BrouillonEmail
        academy = resolve_academy(request)
        qs = BrouillonEmail.objects.filter(auteur=request.user, academy=academy).prefetch_related("pieces")
        return Response({"results": [_brouillon_payload(b) for b in qs[:100]]})

    def post(self, request):
        from .campaign_models import BrouillonEmail
        academy = resolve_academy(request, raw_id=request.data.get("academy_id"))
        if BrouillonEmail.objects.filter(auteur=request.user).count() >= 100:
            raise ValidationError({"non_field_errors": "Au plus 100 brouillons : supprimez-en avant d'en créer."})
        try:
            b = _remplir_brouillon(BrouillonEmail(academy=academy, auteur=request.user), request.data)
        except svc.AudienceError as exc:
            raise ValidationError({exc.field or "non_field_errors": str(exc)})
        b.save()
        return Response(_brouillon_payload(b), status=status.HTTP_201_CREATED)


class BrouillonDetailView(APIView):
    """Un brouillon n'est visible et modifiable que par son auteur (404 sinon)."""
    permission_classes = [IsAuthenticated, IsAdminOrAbove]

    def objet(self, request, pk):
        from .campaign_models import BrouillonEmail
        academy = resolve_academy(request)
        return get_object_or_404(BrouillonEmail, pk=pk, auteur=request.user, academy=academy)

    def get(self, request, pk):
        return Response(_brouillon_payload(self.objet(request, pk)))

    def patch(self, request, pk):
        b = self.objet(request, pk)
        try:
            _remplir_brouillon(b, {**_brouillon_payload(b), **request.data})
        except svc.AudienceError as exc:
            raise ValidationError({exc.field or "non_field_errors": str(exc)})
        b.save()
        return Response(_brouillon_payload(b))

    def delete(self, request, pk):
        b = self.objet(request, pk)
        for piece in b.pieces.all():
            piece.fichier.delete(save=False)
        b.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class BrouillonPiecesView(BrouillonDetailView):
    """POST : ajoute des pièces jointes (mêmes contrôles qu'à l'envoi) ; DELETE <piece> : retire."""

    def post(self, request, pk):
        from django.core.files.base import ContentFile
        from .attachments import AttachmentError, max_files, max_total_bytes, validate_uploads
        from .campaign_models import PieceJointeBrouillon
        b = self.objet(request, pk)
        try:
            nouvelles = validate_uploads(request.FILES.getlist("attachments"))
        except AttachmentError as exc:
            raise ValidationError({"attachments": str(exc)})
        existantes = list(b.pieces.all())
        if len(existantes) + len(nouvelles) > max_files():
            raise ValidationError({"attachments": f"Au plus {max_files()} pièces jointes par message."})
        if sum(p.taille for p in existantes) + sum(len(d) for _, d, _ in nouvelles) > max_total_bytes():
            raise ValidationError({"attachments": f"Taille totale supérieure à {max_total_bytes() // (1024 * 1024)} Mo."})
        for nom, octets, mime in nouvelles:
            piece = PieceJointeBrouillon(brouillon=b, nom=nom, type_mime=mime, taille=len(octets))
            piece.fichier.save(nom, ContentFile(octets), save=False)
            piece.save()
        b.save(update_fields=["modifie_le"])
        return Response(_brouillon_payload(b), status=status.HTTP_201_CREATED)

    def delete(self, request, pk, piece_id):
        b = self.objet(request, pk)
        piece = get_object_or_404(b.pieces, pk=piece_id)
        piece.fichier.delete(save=False)
        piece.delete()
        return Response(_brouillon_payload(b))


class SignatureView(APIView):
    """Signature personnelle (texte), insérée à la demande dans un message."""
    permission_classes = [IsAuthenticated, IsAdminOrAbove]

    def get(self, request):
        from .campaign_models import SignatureEmail
        sig = SignatureEmail.objects.filter(utilisateur=request.user).first()
        return Response({"texte": sig.texte if sig else ""})

    def put(self, request):
        from .campaign_models import SignatureEmail
        texte = (request.data.get("texte") or "").strip()
        if len(texte) > 2000:
            raise ValidationError({"texte": "Signature limitée à 2 000 caractères."})
        sig, _ = SignatureEmail.objects.get_or_create(utilisateur=request.user)
        sig.texte = texte
        sig.save()
        return Response({"texte": sig.texte})
