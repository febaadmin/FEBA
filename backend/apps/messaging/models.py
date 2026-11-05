"""
Messaging models — v7 refactored

Architecture:
  Conversation ← (participants M2M) → CustomUser
  Message → Conversation  (all messages in one conversation)

This replaces the flat thread_id approach with a proper
Conversation object so the frontend can load a full exchange
in one GET instead of cross-joining inbox+sent.
"""
from django.db import models
from apps.accounts.models import CustomUser
import uuid


class Conversation(models.Model):
    """
    Represents an exchange between 2+ users.
    Created automatically when a new message is sent.
    """
    participants = models.ManyToManyField(
        CustomUser,
        related_name="conversations",
        blank=True,
    )
    subject = models.CharField(max_length=200)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Conversation"
        ordering = ["-updated_at"]

    def __str__(self):
        return f"[{self.id}] {self.subject}"

    @classmethod
    def get_or_create_between(cls, user1, user2, subject):
        """
        Find an existing conversation between exactly these two users
        OR create a new one. Used when composing a new message.
        """
        # Look for a conversation where both users participate
        existing = (
            cls.objects.filter(participants=user1)
            .filter(participants=user2)
            .filter(subject=subject)
            .first()
        )
        if existing:
            return existing, False
        conv = cls.objects.create(subject=subject)
        conv.participants.set([user1, user2])
        return conv, True

    @property
    def unread_count_for(self):
        """Use via annotation or filter in views — not called directly."""
        return 0

    def latest_message(self):
        return self.messages.order_by("-sent_at").first()


class Message(models.Model):
    """
    A single message inside a Conversation.
    sender is a participant of conversation.
    """
    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name="messages",
        null=True,  # null=True for backward compat migration
        blank=True,
    )
    # Keep legacy fields for zero-downtime migration
    thread_id = models.UUIDField(default=uuid.uuid4, db_index=True)
    sender = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name="sent_messages",
    )
    recipient = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name="received_messages",
        null=True,
        blank=True,
    )
    subject = models.CharField(max_length=200, blank=True)
    body = models.TextField()
    attachment = models.FileField(
        upload_to="messages/attachments/", null=True, blank=True
    )
    attachment_name = models.CharField(max_length=200, blank=True)
    is_read = models.BooleanField(default=False)
    sent_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)
    parent_message = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="replies",
    )

    class Meta:
        verbose_name = "Message"
        ordering = ["sent_at"]  # ASC for thread view

    def __str__(self):
        return f"{self.sender} → {self.recipient}: {self.subject or '(sans sujet)'}"


class EtatConversation(models.Model):
    """
    État d'une conversation POUR UN PARTICIPANT : dossier (réception, archives,
    corbeille), importance, dernière lecture. Archiver ou supprimer ne touche
    jamais la conversation des autres participants ; « supprimer définitivement »
    la masque seulement pour soi (aucune donnée effacée).
    """
    RECEPTION, ARCHIVES, CORBEILLE = "reception", "archives", "corbeille"
    DOSSIERS = [(RECEPTION, "Boîte de réception"), (ARCHIVES, "Archivés"), (CORBEILLE, "Corbeille")]

    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name="etats")
    utilisateur = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name="etats_conversation")
    dossier = models.CharField(max_length=10, choices=DOSSIERS, default=RECEPTION)
    important = models.BooleanField(default=False)
    #: Messages de groupe (sans destinataire unique) : lus jusqu'à cet instant.
    lu_le = models.DateTimeField(null=True, blank=True)
    #: Supprimée définitivement de la corbeille : invisible pour ce participant.
    masquee = models.BooleanField(default=False)
    modifie_le = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "État de conversation"
        verbose_name_plural = "États de conversation"
        constraints = [models.UniqueConstraint(fields=["conversation", "utilisateur"], name="uniq_etat_conversation")]
        indexes = [models.Index(fields=["utilisateur", "dossier"])]


def _piece_path(instance, filename):
    from django.utils import timezone
    maintenant = timezone.now()
    return f"messages/pieces/{maintenant:%Y/%m}/{uuid.uuid4().hex}_{filename[-80:]}"


class PieceJointeMessage(models.Model):
    """Pièce jointe d'un message (plusieurs par message). Dossier privé « messages/ » :
    nginx le refuse, le fichier ne sort que par un lien signé remis aux participants."""

    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name="pieces")
    fichier = models.FileField(upload_to=_piece_path, max_length=255)
    nom = models.CharField(max_length=200)
    type_mime = models.CharField(max_length=127, blank=True)
    taille = models.PositiveBigIntegerField(default=0)

    class Meta:
        verbose_name = "Pièce jointe de message"
        verbose_name_plural = "Pièces jointes de messages"
        ordering = ["pk"]


class BrouillonMessage(models.Model):
    """Brouillon de message interne, visible de son seul auteur."""

    auteur = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name="brouillons_messages")
    destinataires = models.JSONField(default=list, blank=True)
    objet = models.CharField(max_length=200, blank=True)
    corps = models.TextField(blank=True)
    #: Réponse en cours dans une conversation existante (sinon : nouvelle conversation).
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, null=True, blank=True,
                                     related_name="brouillons")
    modifie_le = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Brouillon de message"
        verbose_name_plural = "Brouillons de messages"
        ordering = ["-modifie_le"]
