"""
apps/core/preflight.py — contrôle de la configuration EFFECTIVE avant démarrage.

Exécuté par l'entrée du backend de production ET par le worker Celery et
Celery Beat (docker-compose.prod.yml) : un service mal configuré REFUSE de
démarrer, avec un message qui dit quoi corriger, au lieu de démarrer sur
une valeur de développement (e-mails écrits dans la console, SMS
« capturés », liens de retour vers localhost…).

Niveaux :
  ERROR    bloque le démarrage ;
  WARNING  affiché, ne bloque pas (service externe facultatif ou désactivé).

DEPLOYMENT_STAGE :
  production (défaut)  transports de test interdits (Mailpit, console,
                       capture SMS) ;
  staging              préproduction : ces transports sont tolérés, en
                       avertissement — tout le reste est exigé.

Aucun secret n'est jamais affiché : seulement « défini / absent » et, pour
comparer les services entre eux, une empreinte (`fingerprint`).
"""
import hashlib
import json
from urllib.parse import urlparse

from django.conf import settings

ERROR, WARNING = "ERROR", "WARNING"
LOCAL_HOSTS = {"localhost", "127.0.0.1", "0.0.0.0", "::1", ""}
WEAK_MARKERS = ("change", "insecure", "dev-", "django-insecure", "secret-key", "example")


def stage():
    return (getattr(settings, "DEPLOYMENT_STAGE", "production") or "production").lower()


def _host(url):
    return (urlparse(url or "").hostname or "").lower()


def _https(url):
    return urlparse(url or "").scheme == "https"


def _allowed(host):
    for h in (a.strip().lower() for a in settings.ALLOWED_HOSTS):
        if h == "*" or h == host or (h.startswith(".") and (host == h[1:] or host.endswith(h))):
            return True
    return False


def problems():
    """Liste de (niveau, code, message). Lit la configuration effective."""
    out = []
    prod = stage() == "production"
    test_level = ERROR if prod else WARNING

    def add(level, code, message):
        out.append((level, code, message))

    # ── Socle Django ──────────────────────────────────────────────────
    key = settings.SECRET_KEY or ""
    if len(key) < 50 or any(m in key.lower() for m in WEAK_MARKERS):
        add(ERROR, "secret_key", "SECRET_KEY absente, trop courte (< 50) ou valeur d'exemple.")
    if settings.DEBUG:
        add(ERROR, "debug", "DEBUG est actif : interdit hors développement.")
    hosts = [h.strip() for h in settings.ALLOWED_HOSTS if h.strip()]
    if not hosts or "*" in hosts:
        add(ERROR, "allowed_hosts", "ALLOWED_HOSTS vide ou « * ».")
    if "postgresql" not in settings.DATABASES["default"].get("ENGINE", ""):
        add(ERROR, "database", "La base de données n'est pas PostgreSQL (DATABASE_URL).")
    if _host(getattr(settings, "REDIS_URL", "")) in LOCAL_HOSTS:
        add(ERROR, "redis", "REDIS_URL pointe sur localhost : dans Docker, utilisez redis://redis-prod:6379/0.")
    base = getattr(settings, "PUBLIC_BASE_URL", "")
    if not _https(base) or _host(base) in LOCAL_HOSTS:
        add(ERROR, "public_base_url",
            "PUBLIC_BASE_URL doit être l'adresse HTTPS publique de FEBA (retours de visioconférence, "
            "paiements Stripe) ; valeur actuelle : " + (base or "(vide)"))

    # ── E-mail ────────────────────────────────────────────────────────
    from apps.notifications.mailer import (
        OBSOLETE_SENDERS, _address_of, current_transport,
    )
    transport = current_transport()
    if transport in ("console", "memory", "file", "unconfigured", "other"):
        add(ERROR, "email_transport",
            f"Transport e-mail « {transport} » : aucun e-mail ne partirait. "
            "EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend et EMAIL_HOST requis.")
    elif transport == "capture":
        add(test_level, "email_capture",
            f"Le serveur SMTP « {settings.EMAIL_HOST} » est un serveur de TEST (capture) : "
            "les messages ne sont distribués à personne.")
    if transport in ("smtp", "capture") and prod:
        if not settings.EMAIL_HOST_USER or not settings.EMAIL_HOST_PASSWORD:
            add(ERROR, "email_credentials", "EMAIL_HOST_USER / EMAIL_HOST_PASSWORD manquants.")
    for name in ("DEFAULT_FROM_EMAIL", "SERVER_EMAIL", "FEBA_FROM_EMAIL", "FHA_FROM_EMAIL"):
        if _address_of(getattr(settings, name, "")) in OBSOLETE_SENDERS:
            add(ERROR, "email_sender_obsolete", f"{name} vaut encore une adresse retirée.")
    login = (settings.EMAIL_HOST_USER or "").lower()
    sender = _address_of(settings.DEFAULT_FROM_EMAIL)
    if transport == "smtp" and "@" in login and sender and sender.rsplit("@", 1)[1] != login.rsplit("@", 1)[1]:
        add(ERROR, "email_sender_domain",
            f"DEFAULT_FROM_EMAIL (« {sender} ») n'appartient pas au compte SMTP (« {login} »).")

    # ── Visioconférence ───────────────────────────────────────────────
    provider = (getattr(settings, "VIDEO_PROVIDER", "") or "").lower()
    if provider == "plugnmeet":
        url = settings.PLUGNMEET_SERVER_URL
        if not _https(url):
            add(ERROR, "plugnmeet_url", "PLUGNMEET_SERVER_URL doit être une adresse HTTPS.")
        elif _host(url) != settings.VIDEO_PUBLIC_HOST:
            add(ERROR, "plugnmeet_domain",
                f"PLUGNMEET_SERVER_URL doit viser {settings.VIDEO_PUBLIC_HOST} (domaine public des classes).")
        if len(settings.PLUGNMEET_API_KEY or "") < 8 or len(settings.PLUGNMEET_API_SECRET or "") < 20:
            add(ERROR, "plugnmeet_credentials", "PLUGNMEET_API_KEY / PLUGNMEET_API_SECRET absents ou trop courts.")
        hook = settings.PLUGNMEET_WEBHOOK_URL
        if not hook:
            add(ERROR, "plugnmeet_webhook", "PLUGNMEET_WEBHOOK_URL vide : présences et fins de réunion non suivies.")
        elif not _https(hook) or not _allowed(_host(hook)):
            add(ERROR, "plugnmeet_webhook",
                "PLUGNMEET_WEBHOOK_URL doit être en HTTPS et son hôte figurer dans ALLOWED_HOSTS "
                "(sinon Django refuse les webhooks : 400).")
    elif provider == "jitsi":
        from apps.virtualclass.services import JitsiNotConfigured, assert_jitsi_configured
        try:
            assert_jitsi_configured()
        except JitsiNotConfigured as exc:
            add(ERROR, "jitsi", f"VIDEO_PROVIDER=jitsi mais configuration incomplète : {exc}")
        # Jitsi n'est plus le moteur de FEBA : un déploiement ne le réactive pas
        # par accident. Retour arrière délibéré : VIDEO_ROLLBACK_JITSI=true
        # (posé par plugnmeet/ops/basculer_feba.sh retour).
        if settings.VIDEO_ROLLBACK_JITSI:
            add(WARNING, "video_rollback", "VIDEO_PROVIDER=jitsi : RETOUR ARRIÈRE délibéré (VIDEO_ROLLBACK_JITSI).")
        else:
            add(ERROR, "video_rollback",
                "VIDEO_PROVIDER=jitsi sans VIDEO_ROLLBACK_JITSI=true : plugNmeet est le moteur de production.")
    else:
        add(ERROR, "video_provider", f"VIDEO_PROVIDER « {provider} » inconnu (plugnmeet ou jitsi).")

    # ── SMS ───────────────────────────────────────────────────────────
    if settings.SMS_ENABLED:
        sms_provider = (settings.SMS_PROVIDER or "").lower()
        if sms_provider != "twilio":
            add(test_level, "sms_provider",
                f"SMS_PROVIDER « {sms_provider} » n'envoie rien (transport de test).")
        else:
            sid, token = settings.TWILIO_ACCOUNT_SID or "", settings.TWILIO_AUTH_TOKEN or ""
            if not sid.startswith("AC") or len(sid) != 34 or len(token) < 32:
                add(ERROR, "sms_credentials", "TWILIO_ACCOUNT_SID (AC…, 34 caractères) / TWILIO_AUTH_TOKEN invalides.")
        try:
            import phonenumbers
            ok = phonenumbers.is_valid_number(phonenumbers.parse(settings.SMS_FROM_NUMBER or "", None))
        except Exception:
            ok = False
        if not ok:
            add(ERROR, "sms_from", "SMS_FROM_NUMBER absent ou invalide (format E.164, ex. +12157155406).")
        callback = settings.SMS_STATUS_CALLBACK_URL
        if callback and (not _https(callback) or not _allowed(_host(callback))):
            add(ERROR, "sms_callback", "SMS_STATUS_CALLBACK_URL doit être en HTTPS et son hôte dans ALLOWED_HOSTS.")
    else:
        add(WARNING, "sms_disabled", "SMS désactivés (SMS_ENABLED=False) : aucune copie SMS ne part.")
    if not settings.PAYMENT_REMINDERS_ENABLED:
        add(WARNING, "reminders_disabled", "Relances de paiement automatiques désactivées (PAYMENT_REMINDERS_ENABLED).")
    return out


def network_problems(timeout=5):
    """Services INDISPENSABLES joignables (base, Redis) — erreurs bloquantes."""
    out = []
    try:
        from django.db import connection
        connection.ensure_connection()
    except Exception as exc:
        out.append((ERROR, "database_down", f"PostgreSQL injoignable : {type(exc).__name__}: {exc}"))
    try:
        import redis
        redis.Redis.from_url(settings.REDIS_URL, socket_timeout=timeout).ping()
    except Exception as exc:
        out.append((ERROR, "redis_down", f"Redis injoignable : {type(exc).__name__}: {exc}"))
    return out


SECRET_NAMES = ("SECRET_KEY", "EMAIL_HOST_PASSWORD", "PLUGNMEET_API_SECRET", "TWILIO_AUTH_TOKEN",
                "JITSI_APP_SECRET", "STRIPE_SECRET_KEY", "STRIPE_WEBHOOK_SECRET")
COMPARED_NAMES = ("DEPLOYMENT_STAGE", "DEBUG", "ALLOWED_HOSTS", "PUBLIC_BASE_URL", "REDIS_URL",
                  "EMAIL_HOST", "EMAIL_PORT", "EMAIL_USE_TLS", "EMAIL_USE_SSL", "EMAIL_HOST_USER",
                  "EMAIL_TRANSPORT_BACKEND", "DEFAULT_FROM_EMAIL", "SERVER_EMAIL", "FEBA_FROM_EMAIL",
                  "FHA_FROM_EMAIL", "VIDEO_PROVIDER", "PLUGNMEET_SERVER_URL", "PLUGNMEET_API_KEY",
                  "PLUGNMEET_WEBHOOK_URL", "SMS_ENABLED", "SMS_PROVIDER", "SMS_FROM_NUMBER",
                  "TWILIO_ACCOUNT_SID", "SMS_REQUIRE_EXPLICIT_CONSENT", "PAYMENT_REMINDERS_ENABLED",
                  "TIME_ZONE")


def fingerprint():
    """
    Empreinte de la configuration (secrets hachés, jamais affichés) : le
    backend, le worker et Beat doivent produire la MÊME empreinte.
    """
    data = {n: str(getattr(settings, n, None)) for n in COMPARED_NAMES}
    data["DATABASE"] = "{ENGINE}:{HOST}:{PORT}:{NAME}".format(**{
        k: settings.DATABASES["default"].get(k, "") for k in ("ENGINE", "HOST", "PORT", "NAME")})
    for n in SECRET_NAMES:
        value = str(getattr(settings, n, "") or "")
        data[n] = hashlib.sha256(value.encode()).hexdigest()[:12] if value else ""
    return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()[:16]
