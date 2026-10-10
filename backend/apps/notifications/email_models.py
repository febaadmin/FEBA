"""
apps/notifications/email_models.py — Journal d'envoi des e-mails.

POURQUOI CE MODÈLE EXISTE
-------------------------
L'écran public affichait « Vous recevrez un e-mail de confirmation » avant
même que la couche d'envoi ait répondu — et l'envoi lui-même passait par
`send_mail(..., fail_silently=True)`. Un serveur SMTP injoignable, une
authentification refusée, une adresse rejetée : rien ne remontait. La
famille attendait un message qui n'arriverait jamais, et l'administration
n'avait aucun moyen de le savoir.

CE QUE CE JOURNAL GARANTIT
--------------------------
Chaque envoi laisse une ligne, avec un état explicite :

  pending   — enregistré, pas encore remis au fournisseur
  accepted  — le fournisseur l'a accepté (il ne dit pas qu'il est arrivé)
  sent      — remis sans erreur par le backend d'envoi
  failed    — refusé, avec l'erreur exacte
  retry     — un nouvel essai est programmé

`accepted` et `sent` sont distincts À DESSEIN. Un serveur SMTP qui accepte
un message ne promet pas qu'il sera distribué ; confondre les deux, c'est
réinventer le « e-mail envoyé » qui ne veut rien dire.

CE QU'IL NE FAIT PAS
--------------------
Il ne prétend jamais qu'un e-mail a été RÇU. Aucune couche logicielle ne
peut le savoir sans accusé de lecture, et un accusé de lecture n'est pas
fiable. L'état le plus fort que ce journal atteint est « remis au
fournisseur sans erreur ».
"""
import uuid

from django.db import models


class EmailDelivery(models.Model):
    """Une tentative d'acheminement d'un e-mail, et ce qu'elle est devenue."""

    QUEUED = "queued"
    PENDING = "pending"
    ACCEPTED = "accepted"
    SENT = "sent"
    FAILED = "failed"
    RETRY = "retry"
    STATUS_CHOICES = [
        (QUEUED, "Enregistré — en file d'attente"),
        (PENDING, "Envoi en cours"),
        (ACCEPTED, "Accepté par le fournisseur"),
        # « sent » = le serveur SMTP a ACCEPTÉ le message. Cela ne prouve pas
        # qu'il est arrivé dans la boîte du destinataire.
        (SENT, "Accepté par le serveur de messagerie"),
        (FAILED, "Échec définitif"),
        (RETRY, "Échec temporaire — nouvel essai programmé"),
    ]

    # ── Transport réellement utilisé (octobre 2026) ───────────────────
    # « smtp » seul ne disait rien : un SMTP vers Mailpit CAPTURE le message
    # (il ne part jamais sur Internet) et l'écran l'affichait pourtant comme
    # « envoyé par un fournisseur réel ». Le transport est désormais
    # constaté à chaque tentative.
    TRANSPORT_CONSOLE = "console"
    TRANSPORT_MEMORY = "memory"
    TRANSPORT_FILE = "file"
    TRANSPORT_CAPTURE = "capture"
    TRANSPORT_SMTP = "smtp"
    TRANSPORT_UNCONFIGURED = "unconfigured"
    TRANSPORT_OTHER = "other"
    TRANSPORT_CHOICES = [
        (TRANSPORT_CONSOLE, "Console du serveur (aucun envoi)"),
        (TRANSPORT_MEMORY, "Mémoire (tests, aucun envoi)"),
        (TRANSPORT_FILE, "Fichier local (aucun envoi)"),
        (TRANSPORT_CAPTURE, "Serveur de test (Mailpit) — capturé, non distribué"),
        (TRANSPORT_SMTP, "Serveur SMTP réel"),
        (TRANSPORT_UNCONFIGURED, "SMTP sans hôte configuré"),
        (TRANSPORT_OTHER, "Fournisseur tiers (API)"),
    ]
    REAL_TRANSPORTS = {TRANSPORT_SMTP, TRANSPORT_OTHER}

    #: Identifiant interne communiqué dans les en-têtes du message. Il
    #: permet de relier une plainte (« je n'ai rien reçu ») à une ligne de
    #: ce journal, sans avoir à chercher par adresse et par date.
    tracking_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)

    entity = models.ForeignKey(
        "schools.School", on_delete=models.CASCADE, related_name="email_deliveries",
        null=True, blank=True,
        help_text="Académie émettrice. Détermine l'expéditeur et le destinataire interne.",
    )
    purpose = models.CharField(
        max_length=64,
        help_text="Nature de l'envoi (ex: fha_enrollment_ack, fha_admin_alert).",
    )
    #: Objet métier concerné, en texte libre (numéro de dossier, référence).
    #: Volontairement pas une clé étrangère générique : le journal doit
    #: survivre à la suppression de l'objet qu'il documente.
    subject_reference = models.CharField(max_length=64, blank=True)

    to_email = models.EmailField()
    cc_emails = models.JSONField(default=list, blank=True)
    from_email = models.EmailField(blank=True)
    reply_to = models.EmailField(blank=True)
    subject = models.CharField(max_length=255)
    language = models.CharField(max_length=5, blank=True)

    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default=PENDING)
    attempts = models.PositiveSmallIntegerField(default=0)
    last_error = models.TextField(
        blank=True,
        help_text="Message d'erreur EXACT du fournisseur. Jamais reformulé.",
    )
    #: Backend réellement utilisé. Sur une installation sans fournisseur,
    #: c'est `console` ou `locmem` — et le rapport doit le dire, plutôt que
    #: de laisser croire qu'un e-mail est parti sur Internet.
    backend = models.CharField(max_length=120, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    next_retry_at = models.DateTimeField(null=True, blank=True)
    #: Dernier renvoi MANUEL (bouton « Renvoyer »). Sert à la fenêtre
    #: anti-doublon : un double clic ne renvoie pas deux fois, mais l'envoi
    #: automatique initial n'empêche pas un renvoi demandé aussitôt.
    manual_resend_at = models.DateTimeField(null=True, blank=True)

    #: Contenu archivé (objet, corps, pièces jointes). PARTAGÉ entre tous
    #: les destinataires d'un même envoi groupé : un seul exemplaire du
    #: contenu et des fichiers. NULL pour les envois historiques antérieurs
    #: à l'archivage (« contenu non archivé »).
    content = models.ForeignKey(
        "notifications.EmailContent", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="deliveries",
    )
    transport = models.CharField(max_length=16, choices=TRANSPORT_CHOICES, blank=True)
    #: Hôte:port SMTP effectivement visé (jamais d'identifiant ni de secret).
    smtp_host = models.CharField(max_length=255, blank=True)
    #: En-tête Message-ID du message émis : permet de le retrouver côté
    #: serveur de messagerie.
    message_id = models.CharField(max_length=255, blank=True)
    last_attempt_at = models.DateTimeField(null=True, blank=True)
    initiated_by = models.ForeignKey(
        "accounts.CustomUser", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="+",
    )

    class Meta:
        verbose_name = "Envoi d'e-mail"
        verbose_name_plural = "Envois d'e-mail"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["entity", "status"]),
            models.Index(fields=["purpose", "subject_reference"]),
            models.Index(fields=["entity", "created_at"]),
            models.Index(fields=["status", "next_retry_at"]),
        ]

    def __str__(self):
        return f"{self.purpose} → {self.to_email} [{self.status}]"

    @property
    def is_delivered_to_provider(self):
        return self.status in (self.ACCEPTED, self.SENT)

    @property
    def needs_attention(self):
        """Vrai quand l'administration doit agir (relancer, corriger l'adresse)."""
        return self.status in (self.FAILED, self.RETRY)

    @property
    def used_real_provider(self):
        """
        Vrai seulement si le message a été confié à un VRAI serveur de
        messagerie. Console, mémoire, fichier et Mailpit (capture) → faux.

        Pour les envois antérieurs au champ `transport`, on retombe sur le
        nom du backend (seule information conservée à l'époque).
        """
        if self.transport:
            return self.transport in self.REAL_TRANSPORTS
        backend = (self.backend or "").lower()
        return not any(
            marker in backend
            for marker in ("console", "locmem", "dummy", "filebased")
        )

    @property
    def is_captured(self):
        return self.transport == self.TRANSPORT_CAPTURE

    def delivery_summary(self):
        """Libellé honnête de ce qui est arrivé au message."""
        if self.status in (self.SENT, self.ACCEPTED):
            if self.transport == self.TRANSPORT_CAPTURE:
                return "Capturé par le serveur de test (Mailpit) — non distribué sur Internet"
            if self.transport in (self.TRANSPORT_CONSOLE, self.TRANSPORT_MEMORY, self.TRANSPORT_FILE):
                return "Écrit localement — aucun envoi réel"
            if not self.transport and not self.used_real_provider:
                return "Écrit localement — aucun envoi réel"
            return "Accepté par le serveur de messagerie (réception non garantie)"
        return self.get_status_display()


class PrivateEmailStorage:
    """
    Stockage PRIVÉ des pièces jointes : `PRIVATE_MEDIA_ROOT/email_attachments`,
    hors du dossier média public. Le réglage est relu à chaque accès (et non
    figé au chargement des modèles). Les fichiers ne sont servis que par la
    vue de téléchargement, après contrôle des droits.
    """

    def __new__(cls):
        import os

        from django.conf import settings
        from django.core.files.storage import FileSystemStorage

        class _Storage(FileSystemStorage):
            @property
            def base_location(self):
                return os.path.join(getattr(settings, "PRIVATE_MEDIA_ROOT", "private_media"),
                                    "email_attachments")

            @property
            def location(self):
                return os.path.abspath(self.base_location)

            def deconstruct(self):
                return ("apps.notifications.email_models.email_attachment_storage", (), {})

        return _Storage()


def email_attachment_storage():
    return PrivateEmailStorage()


def _attachment_path(instance, filename):
    import os

    from django.utils import timezone

    ext = os.path.splitext(filename)[1].lower()[:10]
    return f"{timezone.now():%Y/%m}/{uuid.uuid4().hex}{ext}"


class EmailContent(models.Model):
    """
    Contenu d'un e-mail tel qu'il a été envoyé : objet, texte, HTML.

    Un envoi groupé partage UN contenu entre tous ses destinataires. Les
    contenus porteurs de secrets (lien de réinitialisation, jeton) sont
    archivés EXPURGÉS (`is_redacted`).
    """

    subject = models.CharField(max_length=255)
    text_body = models.TextField(blank=True)
    html_body = models.TextField(blank=True)
    is_redacted = models.BooleanField(default=False)
    redaction_note = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Contenu d'e-mail archivé"
        verbose_name_plural = "Contenus d'e-mail archivés"

    def __str__(self):
        return self.subject[:80]


class EmailAttachment(models.Model):
    """Pièce jointe archivée (fichier privé), rattachée à un contenu."""

    content = models.ForeignKey(EmailContent, on_delete=models.CASCADE, related_name="attachments")
    file = models.FileField(storage=email_attachment_storage, upload_to=_attachment_path, max_length=255)
    original_name = models.CharField(max_length=255)
    content_type = models.CharField(max_length=127)
    size = models.PositiveBigIntegerField()
    sha256 = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Pièce jointe archivée"
        verbose_name_plural = "Pièces jointes archivées"
        ordering = ["content", "id"]

    def __str__(self):
        return self.original_name

    def read_bytes(self):
        with self.file.open("rb") as handle:
            return handle.read()

    @property
    def is_available(self):
        try:
            return bool(self.file) and self.file.storage.exists(self.file.name)
        except Exception:
            return False


class EmailDeliveryAttempt(models.Model):
    """Une tentative d'envoi et son résultat exact (historique conservé)."""

    delivery = models.ForeignKey(EmailDelivery, on_delete=models.CASCADE, related_name="attempt_log")
    attempted_at = models.DateTimeField(auto_now_add=True)
    outcome = models.CharField(max_length=12)
    transport = models.CharField(max_length=16, blank=True)
    smtp_host = models.CharField(max_length=255, blank=True)
    error = models.TextField(blank=True)
    manual = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Tentative d'envoi"
        ordering = ["delivery", "attempted_at"]
