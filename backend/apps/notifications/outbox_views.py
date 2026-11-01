"""
apps/notifications/outbox_views.py — Boîte d'envoi et diagnostic SMTP.

    GET  /api/notifications/outbox/                       liste paginée et filtrable
    GET  /api/notifications/outbox/<id>/                  détail (texte, HTML, pièces jointes, tentatives)
    GET  /api/notifications/outbox/<id>/attachments/<a>/  fichier (téléchargement ou aperçu)
    POST /api/notifications/outbox/<id>/retry/            relance manuelle d'un échec
    GET  /api/notifications/email-config/                 configuration EFFECTIVE (secrets masqués)
    POST /api/notifications/email-config/test/            message de test à une adresse choisie

ISOLATION
---------
Le périmètre est calculé ICI, côté serveur : un administrateur ne voit que
les envois de SON académie ; le super-administrateur voit tout, ou
l'académie choisie. Un identifiant d'envoi ou de pièce jointe hors
périmètre répond 404 — comme s'il n'existait pas.
"""
import logging
import socket
from datetime import timedelta

from apps.core.textes import sans_tiret
from apps.core.request_text import text_field
from django.conf import settings
from django.core.cache import cache
from django.core.validators import validate_email
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.db.models import Count, Q
from django.http import FileResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.dateparse import parse_date
from rest_framework import status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsAdminOrAbove

from .attachments import INLINE_TYPES
from .email_models import EmailAttachment, EmailDelivery

logger = logging.getLogger("apps")

#: Origine lisible de chaque envoi.
PURPOSE_LABELS = {
    "academy_mass_email": "E-mail groupé",
    "fha_enrollment_ack": "Accusé de réception FHA (parent)",
    "fha_enrollment_admin_alert": "Alerte admissions FHA (équipe)",
    "fha_notification": "Notification admissions FHA",
    "payment_reminder": "Relance de paiement",
    "monthly_report": "Rapport mensuel",
    "smtp_test": "Test de configuration SMTP",
    "email_check": "Diagnostic (ligne de commande)",
    "untracked_module": "Envoi hors couche centrale (tracé automatiquement)",
}


def outbox_scope(request):
    """
    (académie, toutes) autorisées. Admin : son académie, toujours ; un
    `academy_id` différent est refusé. Super-admin : `academy_id`, sinon
    l'académie active, sinon toutes.
    """
    from apps.accounts.entity_views import accessible_entities
    from apps.core.tenancy import get_request_school

    user = request.user
    raw = request.query_params.get("academy_id")
    if user.is_superadmin():
        if raw:
            academy = accessible_entities(user).filter(pk=raw).first() if str(raw).isdigit() else None
            if academy is None:
                raise ValidationError({"academy_id": "Académie inconnue ou inactive."})
            return academy
        return get_request_school(request)
    academy = getattr(user, "school", None)
    if academy is None:
        raise PermissionDenied("Votre compte n'est rattaché à aucune académie.")
    if raw and str(raw) != str(academy.pk):
        raise PermissionDenied("Vous ne pouvez consulter que les envois de votre académie.")
    return academy


def visible_deliveries(request):
    academy = outbox_scope(request)
    qs = EmailDelivery.objects.select_related("entity", "content", "initiated_by")
    if academy is not None:
        return qs.filter(entity=academy)
    if request.user.is_superadmin():
        return qs
    return qs.none()  # pragma: no cover


def _row(d):
    attachments = list(d.content.attachments.all()) if d.content_id else []
    return {
        "id": d.pk,
        "created_at": d.created_at,
        "sent_at": d.sent_at,
        "last_attempt_at": d.last_attempt_at,
        "purpose": d.purpose,
        "purpose_label": PURPOSE_LABELS.get(d.purpose, d.purpose),
        "academy": ({"id": d.entity.pk, "code": d.entity.code, "name": d.entity.name}
                    if d.entity_id else None),
        "to_email": d.to_email,
        "from_email": d.from_email,
        "subject": sans_tiret(d.subject),
        "status": d.status,
        "status_display": d.get_status_display(),
        "delivery_summary": d.delivery_summary(),
        "transport": d.transport,
        "transport_display": d.get_transport_display() if d.transport else "Non enregistré (envoi historique)",
        "used_real_provider": d.used_real_provider,
        "attempts": d.attempts,
        "next_retry_at": d.next_retry_at,
        "last_error": d.last_error,
        "has_content": d.content_id is not None,
        "attachments_count": len(attachments),
        "reference": d.subject_reference,
        # Copie SMS de cet e-mail : statut DISTINCT de celui de l'e-mail.
        "sms": _sms_summary(d),
    }


def _sms_summary(d):
    from .sms_views import sms_row

    sms = d.sms_messages.order_by("created_at").first()
    return sms_row(sms) if sms is not None else None


def _attachment(a, delivery):
    return {
        "id": a.pk, "name": a.original_name, "content_type": a.content_type, "size": a.size,
        "sha256": a.sha256, "available": a.is_available,
        "previewable": a.content_type in INLINE_TYPES,
        "url": f"/api/notifications/outbox/{delivery.pk}/attachments/{a.pk}/",
    }


class OutboxListView(APIView):
    permission_classes = [IsAuthenticated, IsAdminOrAbove]

    def get(self, request):
        qs = visible_deliveries(request).prefetch_related("content__attachments")
        p = request.query_params
        if p.get("status"):
            statuses = [x for x in p["status"].split(",") if x]
            qs = qs.filter(status__in=statuses)
        if p.get("purpose"):
            qs = qs.filter(purpose=p["purpose"])
        if p.get("to"):
            qs = qs.filter(to_email__icontains=p["to"].strip())
        if p.get("subject"):
            qs = qs.filter(subject__icontains=p["subject"].strip())
        if p.get("q"):
            q = p["q"].strip()
            qs = qs.filter(Q(subject__icontains=q) | Q(to_email__icontains=q)
                           | Q(content__text_body__icontains=q) | Q(subject_reference__icontains=q))
        for key, lookup in (("date_from", "created_at__date__gte"), ("date_to", "created_at__date__lte")):
            if p.get(key):
                value = parse_date(p[key])
                if value is None:
                    raise ValidationError({key: "Date invalide : AAAA-MM-JJ."})
                qs = qs.filter(**{lookup: value})
        if p.get("has_attachments") == "1":
            qs = qs.filter(content__attachments__isnull=False).distinct()
        qs = qs.order_by("-created_at", "-pk")
        try:
            page = max(int(p.get("page", 1)), 1)
            size = min(max(int(p.get("page_size", 25)), 1), 100)
        except ValueError:
            raise ValidationError({"page": "Pagination invalide."})
        total = qs.count()
        rows = qs[(page - 1) * size: page * size]
        counts = dict(visible_deliveries(request).values_list("status").annotate(n=Count("id")))
        return Response({
            "count": total, "page": page, "page_size": size,
            "results": [_row(d) for d in rows],
            "status_counts": counts,
            "purposes": [{"value": k, "label": v} for k, v in PURPOSE_LABELS.items()],
        })


class OutboxDetailView(APIView):
    permission_classes = [IsAuthenticated, IsAdminOrAbove]

    def get(self, request, pk):
        from .mailer import replay_blocker

        d = get_object_or_404(visible_deliveries(request).prefetch_related("content__attachments"), pk=pk)
        body = _row(d)
        content = d.content
        body.update({
            "cc": d.cc_emails,
            "reply_to": d.reply_to,
            "tracking_id": str(d.tracking_id),
            "message_id": d.message_id,
            "smtp_host": d.smtp_host,
            "initiated_by": getattr(d.initiated_by, "email", None),
            "text_body": content.text_body if content else None,
            "html_body": content.html_body if content else None,
            "is_redacted": bool(content and content.is_redacted),
            "redaction_note": content.redaction_note if content else "",
            "content_note": (None if content else "Contenu non archivé pour cet envoi historique."),
            "attachments": [_attachment(a, d) for a in (content.attachments.all() if content else [])],
            "attempt_log": [
                {"at": a.attempted_at, "outcome": a.outcome, "transport": a.transport,
                 "smtp_host": a.smtp_host, "error": a.error, "manual": a.manual}
                for a in d.attempt_log.all()
            ],
            "can_retry": d.status in (EmailDelivery.FAILED, EmailDelivery.RETRY) and not replay_blocker(d),
            "retry_note": (replay_blocker(d) or None)
            if d.status in (EmailDelivery.FAILED, EmailDelivery.RETRY) else None,
        })
        return Response(body)


class OutboxAttachmentView(APIView):
    permission_classes = [IsAuthenticated, IsAdminOrAbove]

    def get(self, request, pk, attachment_id):
        delivery = get_object_or_404(visible_deliveries(request), pk=pk)
        # La pièce jointe doit appartenir au contenu de CET envoi : un
        # identifiant de fichier d'une autre académie répond 404.
        attachment = get_object_or_404(EmailAttachment, pk=attachment_id, content_id=delivery.content_id)
        if not attachment.is_available:
            return Response({"detail": "Fichier archivé introuvable sur le serveur."}, status=404)
        inline = request.query_params.get("inline") == "1" and attachment.content_type in INLINE_TYPES
        response = FileResponse(attachment.file.open("rb"), content_type=attachment.content_type,
                                as_attachment=not inline, filename=attachment.original_name)
        response["X-Content-Type-Options"] = "nosniff"
        response["Cache-Control"] = "private, no-store"
        # Un fichier servi EN LIGNE ne peut exécuter aucun script.
        response["Content-Security-Policy"] = "sandbox; default-src 'none'; img-src 'self' data:; style-src 'unsafe-inline'"
        logger.info("Pièce jointe %s (envoi %s) consultée par %s", attachment.pk, delivery.pk,
                    request.user.email)
        return response


class OutboxRetryView(APIView):
    permission_classes = [IsAuthenticated, IsAdminOrAbove]

    def post(self, request, pk):
        from .campaigns import recipient_for_delivery, refresh_campaign_status, sync_recipient
        from .mailer import deliver, replay_blocker

        visible = visible_deliveries(request)
        with transaction.atomic():
            # Verrou de ligne : deux clics, deux onglets → un seul renvoi.
            delivery = get_object_or_404(visible.select_for_update(of=("self",)), pk=pk)
            if delivery.status not in (EmailDelivery.FAILED, EmailDelivery.RETRY):
                return Response({"detail": "Seul un envoi en échec peut être relancé.",
                                 "status": delivery.status}, status=status.HTTP_409_CONFLICT)
            blocker = replay_blocker(delivery)
            if blocker:
                return Response({"detail": blocker}, status=status.HTTP_409_CONFLICT)
            delivery.status = EmailDelivery.PENDING
            delivery.next_retry_at = None
            delivery.save(update_fields=["status", "next_retry_at", "updated_at"])
        delivery = deliver(delivery, manual=True)
        recipient = recipient_for_delivery(delivery)
        if recipient is not None:
            recipient.attempts += 1
            sync_recipient(recipient, delivery)
            refresh_campaign_status(recipient.campaign)
        from apps.payments.reminders import sync_reminders_with_delivery
        sync_reminders_with_delivery(delivery)
        return Response(_row(delivery))


# ── Diagnostic SMTP ───────────────────────────────────────────────────

def _mask_user(value):
    if not value:
        return ""
    if "@" in value:
        local, domain = value.split("@", 1)
        return f"{local[:1]}***@{domain}"
    return f"{value[:1]}***"


def smtp_reachability(timeout=5):
    """Le serveur SMTP répond-il au niveau réseau ? (aucune authentification)"""
    from .mailer import transport_backend

    if "smtp" not in transport_backend().lower() or not settings.EMAIL_HOST:
        return {"checked": False, "reachable": None, "detail": "Pas de transport SMTP configuré."}
    try:
        with socket.create_connection((settings.EMAIL_HOST, int(settings.EMAIL_PORT)), timeout=timeout):
            return {"checked": True, "reachable": True,
                    "detail": f"{settings.EMAIL_HOST}:{settings.EMAIL_PORT} joignable."}
    except OSError as exc:
        return {"checked": True, "reachable": False,
                "detail": f"{settings.EMAIL_HOST}:{settings.EMAIL_PORT} injoignable - {type(exc).__name__}: {exc}"}


def email_configuration(request=None):
    """
    Configuration EFFECTIVE, sans aucun secret.

    `academy_senders` : le super administrateur voit l'expéditeur de chaque
    académie ; un administrateur ne voit QUE la sienne. Avant, la liste de
    toutes les académies de la plateforme (codes, noms, adresses) était
    renvoyée à n'importe quel administrateur — trouvé par la campagne
    d'isolation à 2, 7 et 19 académies.
    """
    from apps.schools.models import School

    academies = School.objects.order_by("id")
    # Sans requête : commande d'exploitation (`email_check`), qui voit tout.
    user = getattr(request, "user", None) if request is not None else None
    if request is not None and (user is None or not user.is_superadmin()):
        academies = academies.filter(pk=getattr(user, "school_id", None))

    from .mailer import current_transport, provider_is_configured, sender_for, transport_backend

    transport = current_transport()
    return {
        "transport_backend": transport_backend(),
        "transport": transport,
        "transport_display": dict(EmailDelivery.TRANSPORT_CHOICES).get(transport, transport),
        "real_provider": provider_is_configured(),
        "host": getattr(settings, "EMAIL_HOST", ""),
        "port": getattr(settings, "EMAIL_PORT", None),
        "use_tls": bool(getattr(settings, "EMAIL_USE_TLS", False)),
        "use_ssl": bool(getattr(settings, "EMAIL_USE_SSL", False)),
        "user": _mask_user(getattr(settings, "EMAIL_HOST_USER", "")),
        "password_set": bool(getattr(settings, "EMAIL_HOST_PASSWORD", "")),
        "timeout": getattr(settings, "EMAIL_TIMEOUT", None),
        "default_from": getattr(settings, "DEFAULT_FROM_EMAIL", ""),
        "reply_to": getattr(settings, "EMAIL_REPLY_TO", ""),
        "academy_senders": [
            {"code": a.code, "name": a.name, "from": sender_for(a)} for a in academies
        ],
        "delivery_mode": getattr(settings, "EMAIL_DELIVERY_MODE", "auto"),
        "capture_ui_url": getattr(settings, "MAILPIT_UI_URL", "") if transport == "capture" else "",
        "explanation": {
            "capture": ("Les messages sont CAPTURÉS par le serveur de test (Mailpit) : ils n'atteignent "
                        "aucune boîte réelle. Consultez l'interface de Mailpit pour les lire."),
            "console": "Les messages sont écrits dans la console du serveur : aucun envoi.",
            "memory": "Backend de test en mémoire : aucun envoi.",
            "file": "Les messages sont écrits dans des fichiers locaux : aucun envoi.",
            "unconfigured": "SMTP sélectionné mais aucun hôte configuré : aucun envoi possible.",
            "smtp": ("Serveur SMTP réel : un message accepté est confié au fournisseur ; sa réception "
                     "dépend du fournisseur et des enregistrements SPF/DKIM/DMARC."),
            "other": "Fournisseur tiers : l'acceptation est rapportée par son API.",
        }.get(transport, ""),
    }


class EmailConfigView(APIView):
    permission_classes = [IsAuthenticated, IsAdminOrAbove]

    def get(self, request):
        data = email_configuration(request)
        if request.query_params.get("check") == "1":
            data["reachability"] = smtp_reachability()
        since = timezone.now() - timedelta(hours=24)
        qs = visible_deliveries(request).filter(created_at__gte=since)
        data["last_24h"] = dict(qs.values_list("status").annotate(n=Count("id")))
        return Response(data)


class EmailConfigTestView(APIView):
    """Message de test à une adresse explicitement choisie (tracé, limité)."""

    permission_classes = [IsAuthenticated, IsAdminOrAbove]

    def post(self, request):
        from .mailer import send_tracked_email

        to = text_field(request.data, "to")
        try:
            validate_email(to)
        except DjangoValidationError:
            raise ValidationError({"to": "Adresse e-mail invalide."})
        key = f"smtp-test:{request.user.pk}"
        limit = int(getattr(settings, "EMAIL_TEST_MAX_PER_HOUR", 5))
        count = cache.get(key, 0)
        if count >= limit:
            return Response({"detail": f"Limite atteinte : {limit} tests par heure."},
                            status=status.HTTP_429_TOO_MANY_REQUESTS)
        cache.set(key, count + 1, 3600)
        academy = None if request.user.is_superadmin() else request.user.school
        if request.user.is_superadmin():
            academy = outbox_scope(request)
        delivery = send_tracked_email(
            purpose="smtp_test", to_email=to, subject="FEBA - test de configuration e-mail",
            text_body=("Message de test envoyé depuis FEBA par "
                       f"{request.user.get_full_name() or request.user.email}.\n"
                       "S'il est dans votre boîte de réception, la configuration fonctionne."),
            html_body="<p>Message de test envoyé depuis <strong>FEBA</strong>.</p>",
            entity=academy, reference="smtp_test", initiated_by=request.user,
        )
        logger.info("Test SMTP par %s vers %s : %s (%s)", request.user.email, to, delivery.status,
                    delivery.transport)
        return Response({**_row(delivery), "explanation": email_configuration(request)["explanation"],
                         "capture_ui_url": getattr(settings, "MAILPIT_UI_URL", "")
                         if delivery.transport == "capture" else ""})
