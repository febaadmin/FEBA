"""
apps/notifications/campaigns.py — Envoi d'e-mails par académie et par profil.

RÈGLES
------
1. **Le serveur décide des destinataires.** Le navigateur envoie des
   règles (rôles, « tous les profils », inclusions, exclusions) ; la liste
   est recalculée ici, dans le périmètre de L'ACADÉMIE autorisée. Un
   identifiant qui n'appartient pas à cette académie fait échouer la
   demande entière : on ne « nettoie » pas silencieusement une requête
   qui tente de franchir la frontière.
2. **Les profils sont ceux qui existent.** Les types proposés sont les
   rôles réellement présents parmi les comptes de l'académie (admin,
   enseignant, parent, élève). Le super-administrateur, rôle plateforme
   sans académie, n'est jamais destinataire.
3. **Un destinataire = un message.** Personne ne voit l'adresse des
   autres.
4. **Ce qui n'est pas envoyable est dit.** Compte inactif, adresse
   absente, invalide ou en double : la ligne existe avec un statut
   « ignoré » explicite, visible dans le rapport.
5. **Pas d'envoi massif par accident.** Plafond configurable, nombre
   attendu confirmé par l'utilisateur, jeton anti-double-clic, limite de
   campagnes par heure.
"""
import html
import logging
from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.validators import validate_email
from django.db import IntegrityError, transaction
from django.db.models import Count, Q
from django.utils import timezone

from .campaign_models import EmailCampaign, EmailCampaignRecipient

logger = logging.getLogger("apps")

PURPOSE_CAMPAIGN = "academy_mass_email"

#: Rôles qui peuvent recevoir un envoi groupé, dans l'ordre d'affichage.
#: Ce sont les rôles du modèle `CustomUser` rattachés à une académie.
AUDIENCE_ROLES = ("admin", "teacher", "parent", "student")
ROLE_LABELS = {
    "admin": "Administrateurs",
    "teacher": "Enseignants",
    "parent": "Parents",
    "student": "Élèves",
}


class AudienceError(Exception):
    """Demande d'audience refusée — le message est destiné à l'utilisateur."""

    def __init__(self, message, field=None):
        super().__init__(message)
        self.field = field


def max_recipients():
    return int(getattr(settings, "MASS_EMAIL_MAX_RECIPIENTS", 2000))


def max_campaigns_per_hour():
    return int(getattr(settings, "MASS_EMAIL_MAX_CAMPAIGNS_PER_HOUR", 10))


def batch_size():
    return max(1, int(getattr(settings, "MASS_EMAIL_BATCH_SIZE", 50)))


# ── Audience ──────────────────────────────────────────────────────────

def academy_users(academy):
    from apps.accounts.models import CustomUser

    return CustomUser.objects.filter(school=academy, role__in=AUDIENCE_ROLES)


def audience_roles(academy):
    """Rôles réellement présents dans l'académie, avec leurs effectifs."""
    rows = (
        academy_users(academy)
        .values("role")
        .annotate(
            total=Count("id"),
            active=Count("id", filter=Q(is_active=True)),
        )
    )
    by_role = {row["role"]: row for row in rows}
    return [
        {
            "role": role,
            "label": ROLE_LABELS[role],
            "count": by_role[role]["total"],
            "active_count": by_role[role]["active"],
        }
        for role in AUDIENCE_ROLES
        if role in by_role
    ]


def _clean_ids(values, field):
    if values in (None, ""):
        return set()
    if not isinstance(values, (list, tuple, set)):
        raise AudienceError("Liste d'identifiants attendue.", field)
    cleaned = set()
    for value in values:
        try:
            cleaned.add(int(value))
        except (TypeError, ValueError):
            raise AudienceError(f"Identifiant invalide : {value!r}.", field)
    return cleaned


def normalize_audience(data):
    """Valide la forme des règles d'audience (sans toucher à la base)."""
    roles = data.get("roles") or []
    if isinstance(roles, str):
        roles = [r for r in roles.split(",") if r]
    unknown = sorted(set(roles) - set(AUDIENCE_ROLES))
    if unknown:
        raise AudienceError(f"Type de profil inconnu : {', '.join(unknown)}.", "roles")
    return {
        "roles": sorted(set(roles)),
        "all_profiles": bool(data.get("all_profiles")),
        "include_ids": sorted(_clean_ids(data.get("include_ids"), "include_ids")),
        "exclude_ids": sorted(_clean_ids(data.get("exclude_ids"), "exclude_ids")),
    }


def _email_status(user):
    """Statut d'envoyabilité d'un compte (sans requête)."""
    email = (user.email or "").strip()
    if not user.is_active:
        return EmailCampaignRecipient.SKIPPED_INACTIVE, email
    if not email:
        return EmailCampaignRecipient.SKIPPED_NO_EMAIL, email
    try:
        validate_email(email)
    except DjangoValidationError:
        return EmailCampaignRecipient.SKIPPED_INVALID, email
    return EmailCampaignRecipient.PENDING, email


def resolve_audience(academy, audience):
    """
    Destinataires effectifs pour ces règles, dans CETTE académie.

    Renvoie `{"recipients": [...], "skipped": [...]}` ; chaque entrée est un
    dict `{user, email, status, full_name, role}`. Lève AudienceError si un
    identifiant inclus ou exclu n'appartient pas à l'académie.
    """
    users = academy_users(academy)
    explicit = set(audience["include_ids"]) | set(audience["exclude_ids"])
    if explicit:
        found = set(users.filter(pk__in=explicit).values_list("pk", flat=True))
        outside = sorted(explicit - found)
        if outside:
            # On ne dit pas à qui appartiennent ces comptes : on dit
            # seulement qu'ils ne sont pas dans le périmètre.
            raise AudienceError(
                "Certains destinataires sélectionnés n'appartiennent pas à "
                f"cette académie ou n'existent pas (identifiants : "
                f"{', '.join(map(str, outside))}). Rien n'a été envoyé.",
                "include_ids",
            )

    selector = Q(pk__in=audience["include_ids"])
    if audience["all_profiles"]:
        selector |= Q(role__in=AUDIENCE_ROLES)
    elif audience["roles"]:
        selector |= Q(role__in=audience["roles"])

    selected = (
        users.filter(selector)
        .exclude(pk__in=audience["exclude_ids"])
        .order_by("last_name", "first_name", "pk")
    )

    recipients, skipped, seen = [], [], set()
    for user in selected:
        status, email = _email_status(user)
        entry = {
            "user": user, "email": email, "status": status,
            "full_name": user.get_full_name() or email, "role": user.role,
        }
        if status == EmailCampaignRecipient.PENDING:
            key = email.lower()
            if key in seen:
                entry["status"] = EmailCampaignRecipient.SKIPPED_DUPLICATE
                skipped.append(entry)
                continue
            seen.add(key)
            recipients.append(entry)
        else:
            skipped.append(entry)
    return {"recipients": recipients, "skipped": skipped}


def preview_payload(resolution, limit=500):
    def row(entry):
        user = entry["user"]
        return {
            "user_id": user.pk, "full_name": entry["full_name"], "email": entry["email"],
            "role": entry["role"], "status": entry["status"],
        }

    return {
        "count": len(resolution["recipients"]),
        "skipped_count": len(resolution["skipped"]),
        "recipients": [row(e) for e in resolution["recipients"][:limit]],
        "skipped": [row(e) for e in resolution["skipped"][:limit]],
        "truncated": len(resolution["recipients"]) > limit,
        "max_recipients": max_recipients(),
    }


# ── Création ──────────────────────────────────────────────────────────

def create_campaign(*, academy, user, subject, body, audience, client_token,
                    expected_count, attachments=None):
    """
    Crée la campagne et ses destinataires, puis la met en file d'attente.

    Idempotent par `client_token` : un second envoi du même formulaire
    renvoie la campagne existante (`created=False`) sans rien renvoyer.

    `attachments` : [(nom, octets, type MIME)] DÉJÀ validés
    (apps.notifications.attachments.validate_uploads). Ils sont archivés UNE
    fois, avec le contenu, et partagés par tous les destinataires.
    """
    subject = (subject or "").strip()
    body = (body or "").strip()
    client_token = (client_token or "").strip()
    if not subject:
        raise AudienceError("L'objet du message est obligatoire.", "subject")
    if len(subject) > 200:
        raise AudienceError("L'objet ne peut pas dépasser 200 caractères.", "subject")
    if not body:
        raise AudienceError("Le contenu du message est obligatoire.", "body")
    if not client_token or len(client_token) > 64:
        raise AudienceError("Jeton de formulaire manquant ou invalide.", "client_token")

    existing = EmailCampaign.objects.filter(created_by=user, client_token=client_token).first()
    if existing is not None:
        return existing, False

    since = timezone.now() - timedelta(hours=1)
    recent = EmailCampaign.objects.filter(created_by=user, created_at__gte=since).count()
    if recent >= max_campaigns_per_hour():
        raise AudienceError(
            f"Limite atteinte : {max_campaigns_per_hour()} envois groupés par heure. "
            "Réessayez plus tard.", "non_field_errors",
        )

    resolution = resolve_audience(academy, audience)
    count = len(resolution["recipients"])
    if count == 0:
        raise AudienceError("Aucun destinataire joignable pour cette sélection.", "non_field_errors")
    if count > max_recipients():
        raise AudienceError(
            f"{count} destinataires : au-delà du plafond de {max_recipients()} par envoi. "
            "Divisez l'envoi par type de profil.", "non_field_errors",
        )
    try:
        expected = int(expected_count)
    except (TypeError, ValueError):
        expected = None
    if expected != count:
        # La liste a changé depuis l'aperçu (compte créé, désactivé…) :
        # l'utilisateur a confirmé un AUTRE nombre que celui qui partirait.
        raise AudienceError(
            f"Le nombre de destinataires a changé depuis l'aperçu ({expected} → {count}). "
            "Affichez de nouveau l'aperçu avant de confirmer.", "expected_count",
        )

    from .email_models import EmailDelivery
    from .mailer import create_content, create_delivery

    try:
        with transaction.atomic():
            campaign = EmailCampaign.objects.create(
                academy=academy, created_by=user, created_by_email=user.email or "",
                subject=subject, body=body, audience=audience, client_token=client_token,
                total_recipients=count, skipped_count=len(resolution["skipped"]),
            )
            text, html_body = _bodies(campaign)
            campaign.content = create_content(subject=subject, text_body=text,
                                              html_body=html_body, attachments=attachments)
            campaign.save(update_fields=["content"])
            EmailCampaignRecipient.objects.bulk_create([
                EmailCampaignRecipient(
                    campaign=campaign, user=entry["user"], email=entry["email"],
                    full_name=entry["full_name"][:200], role=entry["role"],
                    status=entry["status"],
                )
                for entry in resolution["recipients"] + resolution["skipped"]
            ])
            # Chaque destinataire joignable a, DÈS MAINTENANT, son envoi
            # enregistré (« en file d'attente ») : la boîte d'envoi montre
            # le message avant même que le worker l'ait traité.
            for recipient in campaign.recipients.filter(status=EmailCampaignRecipient.PENDING):
                recipient.delivery = create_delivery(
                    purpose=PURPOSE_CAMPAIGN, to_email=recipient.email, subject=subject,
                    entity=academy, reference=recipient.tracking_reference,
                    content=campaign.content, initiated_by=user, status=EmailDelivery.QUEUED,
                    sms_user=recipient.user, sms_key=f"campaign:{campaign.pk}:{recipient.pk}",
                )
                recipient.save(update_fields=["delivery"])
    except IntegrityError:
        # Course entre deux soumissions du même jeton : l'autre a gagné.
        existing = EmailCampaign.objects.filter(created_by=user, client_token=client_token).first()
        if existing is not None:
            return existing, False
        raise

    logger.info(
        "Envoi groupé %s créé par %s pour %s : %d destinataire(s), %d ignoré(s).",
        campaign.pk, user.email, academy.code, count, len(resolution["skipped"]),
    )
    transaction.on_commit(lambda: enqueue_campaign(campaign.pk))
    return campaign, True


def enqueue_campaign(campaign_id):
    """Confie la campagne au worker Celery ; consigne l'échec sans lever."""
    from .tasks import send_campaign

    try:
        send_campaign.delay(campaign_id)
        return True
    except Exception as exc:  # broker indisponible
        EmailCampaign.objects.filter(pk=campaign_id).update(
            last_error=(
                "File d'attente indisponible (Redis/Celery) : l'envoi reprendra "
                f"automatiquement dès le retour du service. Détail : {exc}"
            )[:2000],
        )
        logger.error("Envoi groupé %s : mise en file impossible — %s", campaign_id, exc)
        return False


# ── Envoi ─────────────────────────────────────────────────────────────

def _bodies(campaign):
    academy = campaign.academy
    footer = (
        f"\n\n—\n{academy.name}\n"
        "Message envoyé depuis la plateforme de gestion de l'académie. Merci de ne pas transférer "
        "ce message s'il contient des informations personnelles."
    )
    text = campaign.body + footer
    html_body = (
        "<div style=\"font-family:Arial,sans-serif;font-size:14px;line-height:1.5\">"
        + html.escape(campaign.body).replace("\n", "<br>")
        + "<hr style=\"border:none;border-top:1px solid #ddd;margin:16px 0\">"
        + f"<p style=\"color:#666;font-size:12px\">{html.escape(academy.name)}<br>"
        + "Message envoyé depuis la plateforme de gestion de l'académie.</p></div>"
    )
    return text, html_body


def _claim_batch(campaign_id, size):
    """
    Réserve un lot de destinataires « en attente » pour CE worker.

    `select_for_update(skip_locked=True)` : deux workers qui traitent la
    même campagne (tâche rejouée, redémarrage de Celery) ne prennent jamais
    les mêmes lignes. Le passage à « en cours » est fait dans la même
    transaction.
    """
    with transaction.atomic():
        rows = list(
            EmailCampaignRecipient.objects.select_for_update(skip_locked=True)
            .filter(campaign_id=campaign_id, status=EmailCampaignRecipient.PENDING)
            .order_by("pk")[:size]
        )
        ids = [r.pk for r in rows]
        if ids:
            EmailCampaignRecipient.objects.filter(
                pk__in=ids, status=EmailCampaignRecipient.PENDING,
            ).update(status=EmailCampaignRecipient.SENDING, updated_at=timezone.now())
    return ids


def _ensure_delivery(recipient):
    """Envoi enregistré du destinataire (campagnes antérieures : créé à la volée)."""
    from .email_models import EmailDelivery
    from .mailer import create_content, create_delivery

    if recipient.delivery_id and recipient.delivery.content_id:
        return recipient.delivery
    campaign = recipient.campaign
    if campaign.content_id is None:
        text, html_body = _bodies(campaign)
        campaign.content = create_content(subject=campaign.subject, text_body=text, html_body=html_body)
        campaign.save(update_fields=["content"])
    recipient.delivery = create_delivery(
        purpose=PURPOSE_CAMPAIGN, to_email=recipient.email, subject=campaign.subject,
        entity=campaign.academy, reference=recipient.tracking_reference,
        content=campaign.content, status=EmailDelivery.QUEUED,
        sms_user=recipient.user, sms_key=f"campaign:{campaign.pk}:{recipient.pk}",
    )
    return recipient.delivery


def sync_recipient(recipient, delivery):
    """Reporte sur la ligne de campagne le résultat réel de l'envoi."""
    from .email_models import EmailDelivery

    recipient.delivery = delivery
    if delivery.status in (EmailDelivery.SENT, EmailDelivery.ACCEPTED):
        recipient.status = EmailCampaignRecipient.SENT
        recipient.sent_at = delivery.sent_at or timezone.now()
        recipient.error = ""
    elif delivery.status == EmailDelivery.RETRY:
        recipient.status = EmailCampaignRecipient.RETRY
        recipient.error = delivery.last_error
    else:
        recipient.status = EmailCampaignRecipient.FAILED
        recipient.error = delivery.last_error
    recipient.save(update_fields=["delivery", "attempts", "status", "sent_at", "error", "updated_at"])
    return recipient.status


def _send_one(recipient, manual=False):
    from .mailer import deliver

    delivery = deliver(_ensure_delivery(recipient), manual=manual)
    recipient.attempts += 1
    return sync_recipient(recipient, delivery)


def recover_stale(campaign_id, older_than_minutes=15):
    """
    Lignes restées « en cours » après un arrêt brutal du worker.

    Si le journal d'envoi montre que le message est parti, la ligne est
    marquée envoyée ; sinon elle revient « en attente ». C'est ce qui permet
    de redémarrer Celery sans perdre ni doubler un envoi.
    """
    from .email_models import EmailDelivery

    limit = timezone.now() - timedelta(minutes=older_than_minutes)
    stale = EmailCampaignRecipient.objects.filter(
        campaign_id=campaign_id, status=EmailCampaignRecipient.SENDING, updated_at__lt=limit,
    )
    recovered = 0
    for recipient in stale:
        delivery = recipient.delivery or (
            EmailDelivery.objects.filter(
                purpose=PURPOSE_CAMPAIGN, subject_reference=recipient.tracking_reference,
            ).order_by("-created_at").first()
        )
        if delivery is not None and delivery.is_delivered_to_provider:
            recipient.status = EmailCampaignRecipient.SENT
            recipient.delivery = delivery
            recipient.sent_at = delivery.sent_at
        else:
            recipient.status = EmailCampaignRecipient.PENDING
            if delivery is not None:
                recipient.delivery = delivery
        recipient.save(update_fields=["status", "delivery", "sent_at", "updated_at"])
        recovered += 1
    return recovered


def refresh_campaign_status(campaign):
    counts = campaign.counts()
    remaining = counts[EmailCampaignRecipient.PENDING] + counts[EmailCampaignRecipient.SENDING]
    failed = counts[EmailCampaignRecipient.FAILED] + counts[EmailCampaignRecipient.RETRY]
    sent = counts[EmailCampaignRecipient.SENT]
    if remaining:
        status = EmailCampaign.SENDING if (sent or failed) else campaign.status
    elif failed and not sent:
        status = EmailCampaign.FAILED
    elif failed:
        status = EmailCampaign.PARTIAL
    else:
        status = EmailCampaign.DONE
    fields = ["status"]
    campaign.status = status
    if not remaining and campaign.finished_at is None:
        campaign.finished_at = timezone.now()
        fields.append("finished_at")
    campaign.save(update_fields=fields)
    return counts


def process_campaign(campaign_id):
    """
    Envoie tous les destinataires « en attente » de la campagne, par lots.

    Rejouable à volonté : seules les lignes « en attente » sont prises, et
    chaque ligne passe en « en cours » avant l'envoi.
    """
    campaign = EmailCampaign.objects.select_related("academy").filter(pk=campaign_id).first()
    if campaign is None:
        return {"sent": 0, "failed": 0}
    recover_stale(campaign_id)
    if campaign.started_at is None:
        campaign.started_at = timezone.now()
        campaign.status = EmailCampaign.SENDING
        campaign.save(update_fields=["started_at", "status"])

    sent = failed = 0
    while True:
        ids = _claim_batch(campaign_id, batch_size())
        if not ids:
            break
        for recipient in EmailCampaignRecipient.objects.filter(pk__in=ids).select_related(
            "campaign__academy", "campaign__content", "delivery__content",
        ):
            outcome = _send_one(recipient)
            if outcome == EmailCampaignRecipient.SENT:
                sent += 1
            else:
                failed += 1
    counts = refresh_campaign_status(campaign)
    if campaign.last_error and counts[EmailCampaignRecipient.PENDING] == 0:
        EmailCampaign.objects.filter(pk=campaign.pk).update(last_error="")
    logger.info("Envoi groupé %s : %d remis, %d en échec.", campaign_id, sent, failed)
    return {"sent": sent, "failed": failed}


def retry_failed(campaign):
    """
    Remet en file les seuls destinataires en échec. Les envois réussis ne
    sont JAMAIS renvoyés.
    """
    from .email_models import EmailDelivery

    with transaction.atomic():
        rows = campaign.recipients.select_for_update().filter(status__in=EmailCampaignRecipient.RETRYABLE)
        delivery_ids = [r.delivery_id for r in rows if r.delivery_id]
        # Relance HUMAINE : compteur remis à zéro, et l'envoi est retiré de la
        # reprise automatique (statut « en file ») pour qu'aucune tâche ne
        # le traite en même temps que le worker de la campagne.
        EmailDelivery.objects.filter(pk__in=delivery_ids).update(
            status=EmailDelivery.QUEUED, attempts=0, next_retry_at=None, updated_at=timezone.now(),
        )
        updated = campaign.recipients.filter(
            status__in=EmailCampaignRecipient.RETRYABLE,
        ).update(status=EmailCampaignRecipient.PENDING, updated_at=timezone.now())
    if updated:
        campaign.status = EmailCampaign.SENDING
        campaign.finished_at = None
        campaign.save(update_fields=["status", "finished_at"])
        transaction.on_commit(lambda: enqueue_campaign(campaign.pk))
    return updated


def recipient_for_delivery(delivery):
    """Ligne de campagne d'un envoi (relance automatique), ou None."""
    return (
        EmailCampaignRecipient.objects.select_related("campaign__academy")
        .filter(delivery=delivery).first()
    )
