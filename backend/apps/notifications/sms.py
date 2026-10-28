"""
apps/notifications/sms.py — copie par SMS des e-mails et des relances.

DÉCLENCHEMENT CENTRAL
---------------------
`mailer.create_delivery` appelle `schedule_for_email` pour CHAQUE e-mail
enregistré (un envoi = un destinataire). Aucun module d'envoi ne peut
donc oublier le SMS. Les relances de paiement passent en plus la clé de
leur événement (`reminder:<id>`) : e-mail et notification interne d'une
même relance ne produisent qu'UN SMS.

CONTENU
-------
Le corps du SMS est le TEXTE de l'e-mail, tel quel (mêmes paragraphes,
montants, dates, références, liens). Pour un e-mail uniquement HTML, une
version texte est produite en conservant paragraphes, listes et liens.
Rien n'est résumé ni tronqué : un texte de plus de 1 600 caractères part
en plusieurs SMS numérotés ; au-delà de SMS_MAX_MESSAGES_PER_NOTIFICATION,
l'envoi ÉCHOUE explicitement. Une pièce jointe n'est jamais « envoyée par
SMS » : une ligne signale qu'elle se trouve dans l'e-mail.

EXCLUSIONS (statut « skipped », raison lisible)
-----------------------------------------------
- messages porteurs d'un lien ou d'un code de sécurité (réinitialisation
  de mot de passe…) : un SMS s'affiche sur l'écran verrouillé et survit à
  un vol de carte SIM — dupliquer ces liens affaiblirait l'authentification ;
- diagnostics (test SMTP) ;
- destinataire sans compte, sans numéro, numéro invalide ou fixe,
  consentement refusé ou non recueilli (voir SMS_REQUIRE_EXPLICIT_CONSENT).
Aucun autre numéro n'est jamais choisi à la place de celui du destinataire.
"""
import html as html_lib
import logging
import re
from datetime import timedelta
from html.parser import HTMLParser

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from .sms_models import SmsMessage
from .sms_providers import (
    SmsNotConfigured, SmsProviderError, encoding_of, get_provider, segment_count, split_for_provider,
)

logger = logging.getLogger("apps")

RETRY_DELAYS_MINUTES = (1, 5, 30, 120)
MAX_ATTEMPTS = len(RETRY_DELAYS_MINUTES) + 1
#: Envois jamais copiés par SMS (diagnostics, essais d'infrastructure).
NO_SMS_PURPOSES = {"smtp_test", "email_check"}
ATTACHMENT_NOTICE = {
    "fr": "[Pièce(s) jointe(s) : consultez l'e-mail correspondant.]",
    "en": "[Attachment(s): see the corresponding e-mail.]",
}


# ── Texte ─────────────────────────────────────────────────────────────

class _HtmlToText(HTMLParser):
    BLOCK = {"p", "div", "br", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6", "ul", "ol", "table"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out, self.href, self.link_text = [], None, []

    def handle_starttag(self, tag, attrs):
        if tag == "br":
            self.out.append("\n")
        elif tag in self.BLOCK:
            self.out.append("\n")
            if tag == "li":
                self.out.append("- ")
        elif tag == "a":
            self.href = dict(attrs).get("href")
            self.link_text = []

    def handle_endtag(self, tag):
        if tag == "a" and self.href:
            text = "".join(self.link_text).strip()
            if self.href not in text:
                self.out.append(f" ({self.href})")
            self.href = None
        elif tag in self.BLOCK:
            self.out.append("\n")

    def handle_data(self, data):
        self.out.append(data)
        if self.href is not None:
            self.link_text.append(data)


def html_to_text(markup):
    """Version texte complète d'un e-mail HTML : paragraphes, listes, liens."""
    parser = _HtmlToText()
    parser.feed(re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", "", markup or ""))
    text = "".join(parser.out)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return html_lib.unescape(text).strip()


def body_for_email(text_body, html_body, *, has_attachments=False, language="fr"):
    # Le texte de l'e-mail TEL QUEL (pas même un espace retiré) ; la
    # conversion HTML ne sert qu'aux e-mails sans partie texte.
    text = text_body if (text_body or "").strip() else html_to_text(html_body)
    if text and has_attachments:
        text += "\n\n" + ATTACHMENT_NOTICE["en" if language == "en" else "fr"]
    return text


# ── Destinataire et numéro ────────────────────────────────────────────

def default_region(entity):
    code = getattr(entity, "code", "") or ""
    for pair in (settings.SMS_DEFAULT_REGIONS or "").split(","):
        if ":" in pair:
            academy, region = pair.split(":", 1)
            if academy.strip() == code:
                return region.strip().upper()
    return None


def normalize_phone(raw, entity=None):
    """
    (numéro E.164, raison de refus). Jamais de devinette : un numéro sans
    indicatif n'est accepté que si l'académie a un pays par défaut.
    """
    import phonenumbers

    raw = (raw or "").strip()
    if not raw:
        return "", SmsMessage.SKIP_NO_PHONE
    try:
        number = phonenumbers.parse(raw, None if raw.startswith("+") else default_region(entity))
    except phonenumbers.NumberParseException:
        return "", SmsMessage.SKIP_INVALID_PHONE
    if not phonenumbers.is_valid_number(number):
        return "", SmsMessage.SKIP_INVALID_PHONE
    kind = phonenumbers.number_type(number)
    if kind not in (phonenumbers.PhoneNumberType.MOBILE, phonenumbers.PhoneNumberType.FIXED_LINE_OR_MOBILE):
        return "", SmsMessage.SKIP_NOT_MOBILE
    return phonenumbers.format_number(number, phonenumbers.PhoneNumberFormat.E164), ""


def resolve_user(email, entity):
    """Compte FEBA du destinataire : même académie (ou super-administrateur)."""
    from django.contrib.auth import get_user_model
    from django.db.models import Q

    if not email:
        return None
    User = get_user_model()
    qs = User.objects.filter(email__iexact=email.strip())
    if entity is not None:
        qs = qs.filter(Q(school=entity) | Q(role="superadmin"))
    return qs.first()


def consent_blocker(user):
    """Raison de ne PAS écrire à ce destinataire, ou ''."""
    from apps.accounts.models import CustomUser

    consent = getattr(user, "sms_consent", CustomUser.SMS_CONSENT_UNKNOWN) if user else CustomUser.SMS_CONSENT_UNKNOWN
    if consent == CustomUser.SMS_CONSENT_REFUSED:
        return SmsMessage.SKIP_REFUSED
    if settings.SMS_REQUIRE_EXPLICIT_CONSENT and consent != CustomUser.SMS_CONSENT_GRANTED:
        return SmsMessage.SKIP_NO_CONSENT
    return ""


# ── Enregistrement ────────────────────────────────────────────────────

def schedule(*, key, purpose, body, entity=None, user=None, phone=None, email_delivery=None,
             precheck=None, sensitive=False):
    """
    Enregistre le SMS de cet événement (une fois) et le met en file.
    Renvoie le SmsMessage (existant si l'événement a déjà été traité).
    """
    existing = SmsMessage.objects.filter(event_key=key).first()
    if existing is not None:
        return existing
    raw_phone = (phone if phone is not None else getattr(user, "phone", "")) or ""
    sms = SmsMessage(event_key=key[:120], purpose=purpose[:60], entity=entity, user=user,
                     email_delivery=email_delivery, raw_phone=raw_phone[:40], body=body or "",
                     from_number=settings.SMS_FROM_NUMBER, precheck=precheck or {},
                     provider=(settings.SMS_PROVIDER or "capture"))
    sms.encoding = encoding_of(sms.body) if sms.body else ""
    sms.segments = segment_count(sms.body)
    reason = ""
    if not settings.SMS_ENABLED:
        reason = SmsMessage.SKIP_DISABLED
    elif sensitive:
        reason = SmsMessage.SKIP_SENSITIVE
    elif not sms.body.strip():
        reason = SmsMessage.SKIP_EMPTY
    elif user is not None and not user.is_active:
        reason = SmsMessage.SKIP_INACTIVE
    elif user is None and phone is None:
        reason = SmsMessage.SKIP_NO_USER
    else:
        reason = consent_blocker(user)
        if not reason:
            sms.to_number, reason = normalize_phone(raw_phone, entity)
    if reason:
        sms.status, sms.skip_reason = SmsMessage.SKIPPED, reason
    try:
        with transaction.atomic():
            sms.save()
    except IntegrityError:  # même événement enregistré en parallèle
        return SmsMessage.objects.get(event_key=key[:120])
    if sms.status == SmsMessage.PENDING:
        transaction.on_commit(lambda: _enqueue(sms.pk))
    return sms


def _enqueue(sms_id):
    from .tasks import send_sms
    try:
        send_sms.delay(sms_id)
    except Exception as exc:  # broker indisponible : la reprise périodique s'en charge
        logger.warning("SMS %s : mise en file impossible (%s) ; reprise périodique.", sms_id, exc)


def schedule_for_email(delivery, *, user=None, phone=None, key=None, precheck=None,
                       text_body=None, html_body=None, sensitive=False):
    """SMS miroir d'un e-mail enregistré (appelé par mailer.create_delivery)."""
    if delivery.purpose in NO_SMS_PURPOSES:
        return None
    content = delivery.content
    if content is not None and content.is_redacted:
        sensitive = True
    if text_body is None and html_body is None and content is not None:
        text_body, html_body = content.text_body, content.html_body
    has_attachments = bool(content is not None and content.attachments.exists())
    body = body_for_email(text_body, html_body, has_attachments=has_attachments,
                          language=delivery.language or getattr(user, "preferred_language", "fr"))
    if user is None and phone is None:
        user = resolve_user(delivery.to_email, delivery.entity)
    return schedule(key=key or f"email:{delivery.pk}", purpose=delivery.purpose, body=body,
                    entity=delivery.entity, user=user, phone=phone, email_delivery=delivery,
                    precheck=precheck, sensitive=sensitive)


# ── Envoi ─────────────────────────────────────────────────────────────

def _precheck_blocker(sms):
    kind = (sms.precheck or {}).get("type")
    if kind == "payment_reminder":
        from apps.payments.reminders import reminder_sms_still_valid
        ok, detail = reminder_sms_still_valid(sms.precheck.get("reminder_ids") or [])
        return "" if ok else detail
    return ""


def _schedule_retry_or_fail(sms, error, permanent):
    sms.last_error = error[:2000]
    if not permanent and sms.attempts < MAX_ATTEMPTS:
        sms.status = SmsMessage.RETRY
        sms.next_retry_at = timezone.now() + timedelta(minutes=RETRY_DELAYS_MINUTES[sms.attempts - 1])
    else:
        sms.status = SmsMessage.FAILED
        sms.next_retry_at = None


def deliver(sms_id):
    """
    Une tentative pour ce SMS. Idempotent : une ligne déjà finale ou déjà
    « en cours » ailleurs n'est pas renvoyée ; les parties déjà acceptées
    par le fournisseur ne sont jamais réexpédiées.
    """
    with transaction.atomic():
        sms = SmsMessage.objects.select_for_update().filter(pk=sms_id).first()
        if sms is None or sms.status not in (SmsMessage.PENDING, SmsMessage.RETRY):
            return sms
        sms.status = SmsMessage.SENDING
        sms.attempts += 1
        sms.save(update_fields=["status", "attempts", "updated_at"])

    blocker = _precheck_blocker(sms)
    if blocker:
        sms.status, sms.skip_reason, sms.last_error = SmsMessage.SKIPPED, SmsMessage.SKIP_NO_LONGER_DUE, blocker
        sms.save(update_fields=["status", "skip_reason", "last_error", "updated_at"])
        return sms

    parts = split_for_provider(sms.body)
    if len(parts) > settings.SMS_MAX_MESSAGES_PER_NOTIFICATION:
        sms.status = SmsMessage.FAILED
        sms.last_error = (f"Texte trop long : {len(sms.body)} caractères, {len(parts)} SMS nécessaires "
                          f"(maximum {settings.SMS_MAX_MESSAGES_PER_NOTIFICATION}). Aucun SMS tronqué n'est envoyé.")
        sms.save(update_fields=["status", "last_error", "updated_at"])
        return sms

    provider = get_provider()
    sms.provider = provider.name
    sms.parts = len(parts)
    if not settings.SMS_FROM_NUMBER and not getattr(provider, "captured", False):
        _schedule_retry_or_fail(sms, "SMS_FROM_NUMBER n'est pas configuré.", permanent=False)
        sms.save()
        return sms
    from .sms_models import SmsPart
    already = sms.part_records.count()
    try:
        for index, part in enumerate(parts[already:], start=already + 1):
            message_id, provider_status = provider.send(sms.to_number, settings.SMS_FROM_NUMBER, part)
            # Enregistré AUSSITÔT : un redémarrage ne renverra pas cette partie.
            SmsPart.objects.create(sms=sms, index=index, provider_message_id=message_id[:64],
                                   provider_status=provider_status[:30])
            sms.provider_status = provider_status
    except SmsProviderError as exc:
        if exc.opt_out and sms.user_id:
            _record_opt_out(sms.user)
        _schedule_retry_or_fail(sms, str(exc), permanent=exc.permanent and not isinstance(exc, SmsNotConfigured))
        sms.save()
        logger.warning("SMS %s (%s) : échec — %s", sms.pk, sms.purpose, exc)
        return sms
    sms.status = SmsMessage.CAPTURED if getattr(provider, "captured", False) else SmsMessage.SENT
    sms.sent_at = timezone.now()
    sms.next_retry_at = None
    sms.last_error = ""
    sms.save()
    return sms


def _record_opt_out(user):
    from apps.accounts.models import CustomUser
    CustomUser.objects.filter(pk=user.pk).update(sms_consent=CustomUser.SMS_CONSENT_REFUSED,
                                                 sms_consent_at=timezone.now())


def retry_due(limit=200):
    """Reprise : SMS en nouvel essai échu, ou restés en file (worker arrêté)."""
    now = timezone.now()
    stale = now - timedelta(minutes=10)
    ids = list(
        SmsMessage.objects.filter(status=SmsMessage.RETRY, next_retry_at__lte=now)
        .values_list("pk", flat=True)[:limit]
    ) + list(
        SmsMessage.objects.filter(status=SmsMessage.PENDING, created_at__lt=stale)
        .values_list("pk", flat=True)[:limit]
    )
    # Tentative interrompue (worker tué pendant l'envoi) : reprise des
    # parties NON encore acceptées seulement.
    SmsMessage.objects.filter(status=SmsMessage.SENDING, updated_at__lt=now - timedelta(minutes=15)).update(
        status=SmsMessage.RETRY, next_retry_at=now)
    for sms_id in ids:
        deliver(sms_id)
    return len(ids)
