"""
Incidents techniques (V8 — Priorité 3).

Avant : lorsqu'une erreur 500 survenait, l'interface affirmait « L'équipe
technique a été notifiée » alors qu'AUCUNE notification n'était créée et
qu'aucune trace n'était consultable. Message trompeur.

Désormais : chaque erreur serveur inattendue crée un `TechnicalIncident`
(dédoublonné par empreinte), notifie les super administrateurs et renvoie à
l'utilisateur une référence courte vérifiable (ERR-XXXXXX).
"""
import hashlib
import re
import secrets

from django.db import models

from apps.accounts.models import CustomUser
from apps.schools.models import School

# ── Sanitisation centrale ───────────────────────────────────────────────────
# Clés dont la valeur ne doit JAMAIS être enregistrée dans un incident.
SENSITIVE_KEYS = {
    "password", "password1", "password2", "new_password", "old_password",
    "current_password", "confirm_password", "token", "access", "refresh",
    "authorization", "cookie", "session", "secret", "api_key", "apikey",
    "secret_key", "private_key", "card", "card_number", "cvv", "cvc", "iban",
    "credit_card", "csrf", "csrftoken", "sessionid",
}
REDACTED = "[expurgé]"

# Motifs repérés dans du texte libre (messages d'exception, traceback…).
# ORDRE IMPORTANT : les motifs les plus spécifiques (JWT, Bearer) passent
# AVANT le motif générique « clé=valeur ». Sinon « Authorization: Bearer eyJ… »
# voyait seulement « Bearer » consommé comme valeur, laissant le jeton en clair.
_TEXT_PATTERNS = [
    # En-tête Authorization: Bearer <jwt> (jeton compris)
    (re.compile(r"(?i)bearer\s+[A-Za-z0-9._\-]+"), "Bearer " + REDACTED),
    # JWT nu (3 segments base64url ; signature parfois courte)
    (re.compile(r"\beyJ[A-Za-z0-9_\-]{4,}\.[A-Za-z0-9_\-]{4,}\.[A-Za-z0-9_\-]{2,}"),
     REDACTED),
    # password=..., "token": "...", api_key: ...
    (re.compile(
        r"(?i)\b(" + "|".join(sorted(SENSITIVE_KEYS)) + r")\b\s*[:=]\s*"
        r"['\"]?[^\s'\",;}\]]+['\"]?"
    ), r"\1=" + REDACTED),
    # Numéros type carte bancaire (13–19 chiffres, séparateurs tolérés)
    (re.compile(r"\b(?:\d[ \-]?){13,19}\b"), REDACTED),
]


def sanitize_text(value, max_length=4000):
    """Nettoie un texte libre de tout secret avant enregistrement."""
    if value is None:
        return ""
    text = str(value)
    for pattern, replacement in _TEXT_PATTERNS:
        text = pattern.sub(replacement, text)
    return text[:max_length]


def sanitize_data(value, _depth=0):
    """Nettoie récursivement une structure (dict/list) : clés sensibles expurgées."""
    if _depth > 6:
        return REDACTED
    if isinstance(value, dict):
        clean = {}
        for key, item in value.items():
            if str(key).lower() in SENSITIVE_KEYS:
                clean[key] = REDACTED
            else:
                clean[key] = sanitize_data(item, _depth + 1)
        return clean
    if isinstance(value, (list, tuple)):
        return [sanitize_data(item, _depth + 1) for item in value[:50]]
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    return sanitize_text(value, max_length=500)


def build_fingerprint(exception_type, endpoint, module, location, message):
    """Empreinte de dédoublonnage (deux fois la même erreur = un incident)."""
    normalized = re.sub(r"\d+", "N", sanitize_text(message, 300) or "")
    raw = "|".join([
        exception_type or "", endpoint or "", module or "", location or "", normalized,
    ])
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:40]


class TechnicalIncident(models.Model):
    SEVERITY_CHOICES = [
        ("low", "Faible"), ("medium", "Moyenne"),
        ("high", "Élevée"), ("critical", "Critique"),
    ]
    STATUS_CHOICES = [
        ("new", "Nouveau"), ("in_progress", "En cours"), ("resolved", "Résolu"),
        ("ignored", "Ignoré"), ("reopened", "Réouvert"),
    ]

    reference = models.CharField(max_length=20, unique=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    environment = models.CharField(max_length=30, blank=True)
    severity = models.CharField(max_length=10, choices=SEVERITY_CHOICES, default="high")
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default="new")

    module = models.CharField(max_length=80, blank=True)
    frontend_route = models.CharField(max_length=255, blank=True)
    endpoint = models.CharField(max_length=255, blank=True)
    http_method = models.CharField(max_length=10, blank=True)
    status_code = models.PositiveSmallIntegerField(null=True, blank=True)
    exception_type = models.CharField(max_length=120, blank=True)
    # Message TECHNIQUE déjà nettoyé (jamais de secret, jamais de traceback brut).
    message = models.TextField(blank=True)
    location = models.CharField(max_length=255, blank=True,
                                help_text="Fichier:ligne (fonction) d'origine.")

    user = models.ForeignKey(CustomUser, null=True, blank=True,
                             on_delete=models.SET_NULL, related_name="technical_incidents")
    user_role = models.CharField(max_length=20, blank=True)
    school = models.ForeignKey(School, null=True, blank=True,
                               on_delete=models.SET_NULL, related_name="technical_incidents")
    attempted_action = models.CharField(max_length=255, blank=True)
    context_data = models.JSONField(default=dict, blank=True)
    user_agent = models.CharField(max_length=255, blank=True)
    app_version = models.CharField(max_length=40, blank=True)
    release = models.CharField(max_length=60, blank=True)

    fingerprint = models.CharField(max_length=40, db_index=True)
    occurrences = models.PositiveIntegerField(default=1)
    first_seen_at = models.DateTimeField(auto_now_add=True)
    last_seen_at = models.DateTimeField(auto_now=True)

    assigned_to = models.ForeignKey(CustomUser, null=True, blank=True,
                                    on_delete=models.SET_NULL,
                                    related_name="assigned_incidents")
    resolution_notes = models.TextField(blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Incident technique"
        verbose_name_plural = "Incidents techniques"
        ordering = ["-last_seen_at"]
        indexes = [
            models.Index(fields=["status", "-last_seen_at"]),
            models.Index(fields=["severity"]),
        ]

    def __str__(self):
        return f"{self.reference} — {self.exception_type or 'Erreur'}"

    def save(self, *args, **kwargs):
        if not self.reference:
            self.reference = self._generate_reference()
        # Ceinture et bretelles : rien de sensible ne doit atteindre la base.
        self.message = sanitize_text(self.message)
        self.context_data = sanitize_data(self.context_data or {})
        super().save(*args, **kwargs)

    @staticmethod
    def _generate_reference():
        for _ in range(12):
            candidate = f"ERR-{secrets.token_hex(3).upper()}"
            if not TechnicalIncident.objects.filter(reference=candidate).exists():
                return candidate
        return f"ERR-{secrets.token_hex(5).upper()}"
