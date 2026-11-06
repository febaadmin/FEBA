"""
apps/boite_mail/models.py — Copie locale de la boîte professionnelle (contact@globalfeba.com).

La boîte RÉELLE est chez le fournisseur (Hostinger, IMAP). FEBA en garde une copie
synchronisée pour l'afficher vite et la rechercher ; toute action (lu, important,
archiver, corbeille) est d'abord appliquée chez le fournisseur, puis recopiée ici.

Identité d'un message : (dossier IMAP, UIDVALIDITY, UID). Rapprochement entre sources
(fournisseur et historique d'envoi FEBA) : en-tête Message-ID — jamais deux lignes pour
le même Message-ID dans le même dossier logique.
"""
from django.conf import settings
from django.db import models

from apps.notifications.email_models import email_attachment_storage


class MessageMail(models.Model):
    RECEPTION, ENVOYES, BROUILLONS, ARCHIVES, CORBEILLE, INDESIRABLES = (
        "reception", "envoyes", "brouillons", "archives", "corbeille", "indesirables")
    DOSSIERS = [(RECEPTION, "Boîte de réception"), (ENVOYES, "Messages envoyés"), (BROUILLONS, "Brouillons"),
                (ARCHIVES, "Archivés"), (CORBEILLE, "Corbeille"), (INDESIRABLES, "Indésirables")]
    IMAP, FEBA = "imap", "feba"
    SOURCES = [(IMAP, "Boîte du fournisseur"), (FEBA, "Envoyé depuis FEBA")]

    dossier = models.CharField(max_length=12, choices=DOSSIERS, db_index=True)
    source = models.CharField(max_length=5, choices=SOURCES, default=IMAP)
    #: Identité chez le fournisseur (vide pour un envoi FEBA pas encore retrouvé dans « Envoyés »).
    dossier_imap = models.CharField(max_length=120, blank=True)
    uidvalidity = models.BigIntegerField(null=True, blank=True)
    uid = models.BigIntegerField(null=True, blank=True)
    message_id = models.CharField(max_length=255, blank=True, db_index=True)
    in_reply_to = models.CharField(max_length=255, blank=True)
    references = models.TextField(blank=True)
    sujet = models.CharField(max_length=500, blank=True)
    expediteur_nom = models.CharField(max_length=255, blank=True)
    expediteur_email = models.CharField(max_length=255, blank=True, db_index=True)
    a = models.JSONField(default=list, blank=True)       # [{"nom", "email"}]
    cc = models.JSONField(default=list, blank=True)
    cci = models.JSONField(default=list, blank=True)     # connu seulement pour les envois
    repondre_a = models.CharField(max_length=255, blank=True)
    date = models.DateTimeField(db_index=True)
    extrait = models.CharField(max_length=300, blank=True)
    texte = models.TextField(blank=True)
    #: HTML NETTOYÉ à la synchronisation (liste blanche) ; jamais le HTML brut.
    html = models.TextField(blank=True)
    #: Même HTML nettoyé, images distantes comprises (affiché seulement à la demande).
    html_images = models.TextField(blank=True)
    a_images_distantes = models.BooleanField(default=False)
    lu = models.BooleanField(default=False)
    important = models.BooleanField(default=False)
    taille = models.PositiveIntegerField(default=0)
    nb_pieces = models.PositiveSmallIntegerField(default=0)
    #: Envoi FEBA correspondant (historique de la boîte d'envoi).
    envoi = models.ForeignKey("notifications.EmailDelivery", on_delete=models.SET_NULL, null=True, blank=True,
                              related_name="messages_boite")
    statut_envoi = models.CharField(max_length=20, blank=True)
    origine = models.CharField(max_length=64, blank=True)
    supprime_chez_fournisseur = models.BooleanField(default=False)
    #: Réponse à un message reçu par le formulaire du site vitrine (traçabilité).
    message_site = models.ForeignKey("website.ContactMessage", on_delete=models.SET_NULL, null=True, blank=True,
                                     related_name="reponses_email")
    #: Auteur FEBA d'un envoi fait depuis l'application (réponse, transfert, site vitrine).
    envoye_par = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name="+")
    synchronise_le = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Message de la boîte contact"
        verbose_name_plural = "Messages de la boîte contact"
        ordering = ["-date", "-pk"]
        constraints = [
            models.UniqueConstraint(fields=["dossier_imap", "uidvalidity", "uid"], name="uniq_message_imap",
                                    condition=models.Q(uid__isnull=False)),
            models.UniqueConstraint(fields=["envoi"], name="uniq_message_envoi_feba",
                                    condition=models.Q(envoi__isnull=False)),
        ]
        indexes = [models.Index(fields=["dossier", "-date"]), models.Index(fields=["dossier", "lu"])]

    def __str__(self):
        return f"[{self.dossier}] {self.sujet[:60]}"


def _piece_path(instance, filename):
    import uuid
    return f"boite_mail/{instance.message_id}/{uuid.uuid4().hex}"


class PieceJointeMail(models.Model):
    message = models.ForeignKey(MessageMail, on_delete=models.CASCADE, related_name="pieces")
    nom = models.CharField(max_length=255)
    type_mime = models.CharField(max_length=127, blank=True)
    taille = models.PositiveIntegerField(default=0)
    fichier = models.FileField(storage=email_attachment_storage, upload_to=_piece_path, max_length=255, blank=True)
    #: Pièce trop volumineuse : non copiée (consultable chez le fournisseur).
    non_copiee = models.BooleanField(default=False)

    class Meta:
        ordering = ["pk"]


class EtatSynchroDossier(models.Model):
    dossier_imap = models.CharField(max_length=120, unique=True)
    uidvalidity = models.BigIntegerField(null=True, blank=True)
    dernier_uid = models.BigIntegerField(default=0)
    derniere_synchro = models.DateTimeField(null=True, blank=True)
    derniere_erreur = models.TextField(blank=True)


class AccesBoiteMail(models.Model):
    """Droits explicites sur la boîte professionnelle (le super administrateur a tous les droits)."""
    utilisateur = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="acces_boite_mail")
    peut_lire = models.BooleanField(default=True)
    peut_envoyer = models.BooleanField(default=False, help_text="Répondre, répondre à tous, transférer, écrire.")
    peut_supprimer = models.BooleanField(default=False, help_text="Corbeille et suppression définitive.")
    accorde_par = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+")
    modifie_le = models.DateTimeField(auto_now=True)


class JournalBoiteMail(models.Model):
    """Actions sensibles sur la boîte : qui, quoi, quand (jamais le contenu)."""
    utilisateur = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+")
    action = models.CharField(max_length=40)
    message = models.ForeignKey(MessageMail, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    detail = models.CharField(max_length=300, blank=True)
    le = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-le"]
