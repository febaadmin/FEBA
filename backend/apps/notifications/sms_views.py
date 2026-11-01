"""
apps/notifications/sms_views.py — consultation des SMS et accusés du fournisseur.

Mêmes règles que la boîte d'envoi : administrateurs uniquement, isolation
par académie côté serveur (un administrateur ne voit que la sienne).
"""
import logging

from django.conf import settings
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsAdminOrAbove

from .outbox_views import outbox_scope
from .sms_models import SmsMessage, SmsPart

logger = logging.getLogger("apps")


def visible_sms(request):
    academy = outbox_scope(request)
    qs = SmsMessage.objects.select_related("entity", "user", "email_delivery")
    if academy is not None:
        return qs.filter(entity=academy)
    if request.user.is_superadmin():
        return qs
    return qs.none()  # pragma: no cover


def sms_row(sms, *, with_body=False):
    row = {
        "id": sms.pk,
        "created_at": sms.created_at,
        "sent_at": sms.sent_at,
        "delivered_at": sms.delivered_at,
        "purpose": sms.purpose,
        "academy": sms.entity.code if sms.entity_id else None,
        "recipient": (sms.user.get_full_name() or sms.user.email) if sms.user_id else None,
        "to_number": sms.masked_number,
        "status": sms.status,
        "status_display": sms.get_status_display(),
        "skip_reason": sms.skip_reason,
        "skip_reason_display": sms.get_skip_reason_display() if sms.skip_reason else "",
        "provider": sms.provider,
        "provider_status": sms.provider_status,
        "encoding": sms.encoding,
        "segments": sms.segments,
        "parts": sms.parts,
        "attempts": sms.attempts,
        "next_retry_at": sms.next_retry_at,
        "last_error": sms.last_error,
        "email_delivery_id": sms.email_delivery_id,
        "can_retry": sms.status == SmsMessage.FAILED and not sms.skip_reason,
    }
    if with_body:
        row["body"] = sms.body
    return row


class SmsListView(APIView):
    permission_classes = [IsAuthenticated, IsAdminOrAbove]

    def get(self, request):
        qs = visible_sms(request)
        p = request.query_params
        if p.get("status"):
            qs = qs.filter(status=p["status"])
        if p.get("purpose"):
            qs = qs.filter(purpose=p["purpose"])
        if p.get("email_delivery"):
            qs = qs.filter(email_delivery_id=p["email_delivery"])
        try:
            page = max(1, int(p.get("page", 1)))
            size = min(100, max(1, int(p.get("page_size", 25))))
        except ValueError:
            page, size = 1, 25
        total = qs.count()
        items = qs.order_by("-created_at")[(page - 1) * size: page * size]
        return Response({
            "count": total, "page": page, "page_size": size,
            "enabled": bool(settings.SMS_ENABLED), "provider": settings.SMS_PROVIDER,
            "results": [sms_row(s, with_body=True) for s in items],
        })


class SmsRetryView(APIView):
    permission_classes = [IsAuthenticated, IsAdminOrAbove]

    def post(self, request, pk):
        from .sms import deliver

        with transaction.atomic():
            sms = get_object_or_404(visible_sms(request).select_for_update(of=("self",)), pk=pk)
            if sms.status != SmsMessage.FAILED or sms.skip_reason:
                return Response({"detail": "Seul un SMS en échec peut être relancé.", "status": sms.status},
                                status=status.HTTP_409_CONFLICT)
            sms.status = SmsMessage.RETRY
            sms.attempts = 0
            sms.next_retry_at = timezone.now()
            sms.save(update_fields=["status", "attempts", "next_retry_at", "updated_at"])
        return Response(sms_row(deliver(sms.pk), with_body=True))


class TwilioStatusCallbackView(APIView):
    """
    POST /api/notifications/sms/status/ — accusé de remise Twilio.

    Authentifié par X-Twilio-Signature (HMAC-SHA1 du jeton Twilio sur
    l'URL déclarée SMS_STATUS_CALLBACK_URL et les paramètres reçus).
    """
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        from .sms_providers import twilio_signature_valid

        params = {k: request.POST.get(k) for k in request.POST}
        url = settings.SMS_STATUS_CALLBACK_URL
        if not url or not twilio_signature_valid(url, params, request.headers.get("X-Twilio-Signature", "")):
            logger.warning("Accusé SMS refusé : signature Twilio invalide.")
            return Response({"detail": "Signature invalide."}, status=status.HTTP_403_FORBIDDEN)
        part = SmsPart.objects.select_related("sms").filter(provider_message_id=params.get("MessageSid", "")).first()
        if part is None:
            return Response({"received": True, "known": False})
        state = (params.get("MessageStatus") or "").lower()
        part.provider_status = state[:30]
        part.error_code = (params.get("ErrorCode") or "")[:20]
        part.save(update_fields=["provider_status", "error_code", "updated_at"])
        sms = part.sms
        states = list(sms.part_records.values_list("provider_status", flat=True))
        if states and all(s == "delivered" for s in states) and len(states) == sms.parts:
            sms.status, sms.delivered_at = SmsMessage.DELIVERED, timezone.now()
        elif state in ("undelivered", "failed"):
            sms.status = SmsMessage.FAILED
            sms.last_error = f"Non remis par l'opérateur (Twilio {state}, code {part.error_code or '-'})."
            if part.error_code == "21610" and sms.user_id:
                from .sms import _record_opt_out
                _record_opt_out(sms.user)
        sms.provider_status = state[:30]
        sms.save(update_fields=["status", "delivered_at", "last_error", "provider_status", "updated_at"])
        return Response({"received": True, "known": True})
