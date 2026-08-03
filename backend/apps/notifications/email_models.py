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

    PENDING = "pending"
    ACCEPTED = "accepted"
    SENT = "sent"
    FAILED = "failed"
    RETRY = "retry"
    STATUS_CHOICES = [
        (PENDING, "En attente d'envoi"),
        (ACCEPTED, "Accepté par le fournisseur"),
        (SENT, "Envoyé"),
        (FAILED, "Échec"),
        (RETRY, "Nouvel essai programmé"),
    ]

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

    class Meta:
        verbose_name = "Envoi d'e-mail"
        verbose_name_plural = "Envois d'e-mail"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["entity", "status"]),
            models.Index(fields=["purpose", "subject_reference"]),
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
        Faux quand l'envoi est passé par un backend de développement.

        Sans ce drapeau, un rapport pourrait annoncer « 12 e-mails envoyés »
        alors que les douze ont été écrits dans la console du serveur.
        """
        backend = (self.backend or "").lower()
        return not any(
            marker in backend
            for marker in ("console", "locmem", "dummy", "filebased")
        )
