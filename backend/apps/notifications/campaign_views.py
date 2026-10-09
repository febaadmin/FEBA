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
from .mailer import provider_is_configured


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
        "last_error": campaign.last_error,
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
            "max_recipients": svc.max_recipients(),
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
        payload["provider_configured"] = provider_is_configured()
        return Response(payload)


class MassEmailCampaignListView(APIView):
    permission_classes = [IsAuthenticated, IsAdminOrAbove]

    def get(self, request):
        academy = resolve_academy(request)
        campaigns = (
            EmailCampaign.objects.filter(academy=academy)
            .select_related("academy").order_by("-created_at")[:100]
        )
        return Response({"results": [campaign_summary(c) for c in campaigns]})

    def post(self, request):
        academy = resolve_academy(request)
        audience = _audience_from(request.data)
        if request.data.get("confirm") is not True:
            raise ValidationError({"confirm": "Confirmation explicite requise avant l'envoi."})
        try:
            campaign, created = svc.create_campaign(
                academy=academy, user=request.user,
                subject=request.data.get("subject"), body=request.data.get("body"),
                audience=audience, client_token=request.data.get("client_token"),
                expected_count=request.data.get("expected_count"),
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
        body["recipients"] = [
            {
                "id": r.pk, "user_id": r.user_id, "full_name": r.full_name, "email": r.email,
                "role": r.role, "status": r.status, "status_display": r.get_status_display(),
                "attempts": r.attempts, "error": r.error, "sent_at": r.sent_at,
                "used_real_provider": bool(r.delivery and r.delivery.used_real_provider),
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
