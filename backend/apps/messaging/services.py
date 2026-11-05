"""
apps/messaging/services.py — Règles de la messagerie interne (phase 7).

- Seuls les PARTICIPANTS voient une conversation, ses messages et ses pièces
  jointes : tout passe par `conversations_de(user)` (un identifiant deviné
  répond 404).
- Les destinataires possibles sont ceux de `allowed_message_recipients` (même
  règle que la liste de l'interface), dans l'académie de l'expéditeur.
- Archiver, marquer important, mettre à la corbeille, supprimer définitivement :
  état PERSONNEL (EtatConversation). Rien n'est effacé pour les autres.
- Un nouveau message ramène la conversation dans la boîte de réception des
  autres participants (comme une messagerie classique).

Lecture : un message reçu en tête-à-tête porte `recipient` et `is_read` ; un
message de groupe (plusieurs destinataires) n'a pas de destinataire unique et
sa lecture se mesure par `EtatConversation.lu_le`.
"""
from datetime import timedelta

from django.db import transaction
from django.db.models import Exists, OuterRef, Q
from django.utils import timezone

from .models import Conversation, EtatConversation, Message, PieceJointeMessage

DOSSIERS_LISTE = ("reception", "envoyes", "importants", "archives", "corbeille")
MAX_DESTINATAIRES = 50
MAX_PIECES = 5


class RegleMessagerie(ValueError):
    def __init__(self, message, champ="non_field_errors", statut=400):
        super().__init__(message)
        self.champ, self.statut = champ, statut


def conversations_de(user):
    return Conversation.objects.filter(participants=user).distinct()


def etat(conversation, user):
    e, _ = EtatConversation.objects.get_or_create(conversation=conversation, utilisateur=user)
    return e


def destinataires_autorises(user, request=None):
    from apps.accounts.views import allowed_message_recipients
    from apps.core.tenancy import get_request_school
    qs = allowed_message_recipients(user)
    school = get_request_school(request) if request is not None else getattr(user, "school", None)
    if school is not None:
        qs = qs.filter(school=school)
    return qs


def resoudre_destinataires(user, ids, request=None):
    """Comptes destinataires, tous autorisés ; sinon refus global (rien n'est envoyé)."""
    from apps.core.request_text import identifiant
    if not isinstance(ids, (list, tuple)):
        ids = [ids] if ids not in (None, "") else []
    propres = []
    for v in ids:
        # Bornes de clé : un identifiant démesuré ferait échouer la requête SQL (500).
        valeur = identifiant(v)
        if valeur is None:
            raise RegleMessagerie("Destinataire introuvable.", "recipient_ids", statut=404)
        propres.append(valeur)
    propres = list(dict.fromkeys(propres))
    if not propres:
        raise RegleMessagerie("Choisissez au moins un destinataire.", "recipient_ids")
    if len(propres) > MAX_DESTINATAIRES:
        raise RegleMessagerie(f"Au plus {MAX_DESTINATAIRES} destinataires par message.", "recipient_ids")
    comptes = list(destinataires_autorises(user, request).filter(pk__in=propres))
    if len(comptes) != len(propres):
        # On ne dit pas lesquels : confirmer l'existence d'un compte hors périmètre est déjà une fuite.
        raise RegleMessagerie("Destinataire introuvable.", "recipient_ids", statut=404)
    return sorted(comptes, key=lambda u: propres.index(u.pk))


def valider_pieces(fichiers):
    from apps.core.request_text import checked_upload
    fichiers = [f for f in fichiers if f]
    if len(fichiers) > MAX_PIECES:
        raise RegleMessagerie(f"Au plus {MAX_PIECES} pièces jointes par message.", "attachments")
    return [checked_upload(f) for f in fichiers]


def _joindre(message, fichiers):
    for f in fichiers:
        PieceJointeMessage.objects.create(message=message, fichier=f, nom=(f.name or "piece")[:200],
                                          type_mime=getattr(f, "content_type", "") or "",
                                          taille=getattr(f, "size", 0) or 0)


def _notifier(destinataire, titre, conversation, auteur):
    try:
        from apps.notifications.utils import create_notification, notification_path
        create_notification(destinataire, "message", titre, conversation.subject,
                            related_url=notification_path(destinataire, f"messages?conversation={conversation.id}"))
    except Exception:  # une notification manquée n'annule pas l'envoi
        import logging
        logging.getLogger("apps").warning("Notification de message non créée.", exc_info=True)


def _ramener_en_reception(conversation, sauf):
    """Un nouveau message ramène la conversation chez les autres (archives, corbeille, masquée)."""
    EtatConversation.objects.filter(conversation=conversation).exclude(utilisateur=sauf).filter(
        Q(dossier__in=[EtatConversation.ARCHIVES, EtatConversation.CORBEILLE]) | Q(masquee=True)
    ).update(dossier=EtatConversation.RECEPTION, masquee=False, modifie_le=timezone.now())


@transaction.atomic
def demarrer(user, destinataires, objet, corps, fichiers=(), request=None):
    objet = (objet or "").strip()[:200] or "(Sans sujet)"
    corps = (corps or "").strip()
    if not corps:
        raise RegleMessagerie("Le message est vide.", "body")
    if len(destinataires) == 1:
        # Tête-à-tête : même conversation qu'avant pour le même objet (historique continu).
        conv, _ = Conversation.get_or_create_between(user, destinataires[0], objet)
        if conv.participants.count() != 2:
            conv = Conversation.objects.create(subject=objet)
            conv.participants.set([user, destinataires[0]])
    else:
        conv = Conversation.objects.create(subject=objet)
        conv.participants.set([user, *destinataires])
    msg = Message.objects.create(conversation=conv, sender=user,
                                 recipient=destinataires[0] if len(destinataires) == 1 else None,
                                 subject=objet, body=corps)
    _joindre(msg, fichiers)
    conv.save()
    _ramener_en_reception(conv, sauf=user)
    e = etat(conv, user)
    e.lu_le = msg.sent_at
    e.dossier, e.masquee = EtatConversation.RECEPTION, False
    e.save()
    transaction.on_commit(lambda: [
        _notifier(d, f"Nouveau message de {user.get_full_name()}", conv, user) for d in destinataires])
    return conv, msg


@transaction.atomic
def repondre(user, conv, corps, fichiers=(), a_tous=True):
    corps = (corps or "").strip()
    if not corps:
        raise RegleMessagerie("Le message est vide.", "body")
    autres = list(conv.participants.exclude(pk=user.pk))
    if not autres:
        raise RegleMessagerie("Impossible de trouver le destinataire.")
    if not a_tous and len(autres) > 1:
        # « Répondre » (à l'expéditeur seulement) dans un échange de groupe : tête-à-tête séparé.
        dernier = conv.messages.exclude(sender=user).order_by("-sent_at").first()
        cible = dernier.sender if dernier else autres[0]
        objet = conv.subject if conv.subject.startswith("Re: ") else f"Re: {conv.subject}"
        return demarrer(user, [cible], objet, corps, fichiers)
    msg = Message.objects.create(conversation=conv, sender=user, recipient=autres[0] if len(autres) == 1 else None,
                                 subject=conv.subject, body=corps)
    _joindre(msg, fichiers)
    conv.save()
    marquer_lu(conv, user)
    _ramener_en_reception(conv, sauf=user)
    transaction.on_commit(lambda: [
        _notifier(d, f"Réponse de {user.get_full_name()}", conv, user) for d in autres])
    return conv, msg


def non_lus_q(user):
    """Messages non lus par `user` (filtre sur Message)."""
    lu_le = EtatConversation.objects.filter(conversation=OuterRef("conversation"), utilisateur=user,
                                            lu_le__gte=OuterRef("sent_at"))
    return (~Q(sender=user)) & (Q(recipient=user, is_read=False) | (Q(recipient__isnull=True) & ~Exists(lu_le)))


def nb_non_lus(user, conv):
    return conv.messages.filter(non_lus_q(user)).count()


def marquer_lu(conv, user):
    maintenant = timezone.now()
    conv.messages.filter(recipient=user, is_read=False).update(is_read=True, read_at=maintenant)
    e = etat(conv, user)
    e.lu_le = maintenant
    e.save(update_fields=["lu_le", "modifie_le"])


def marquer_non_lu(conv, user):
    dernier = conv.messages.exclude(sender=user).order_by("-sent_at").first()
    if dernier is None:
        return
    if dernier.recipient_id == user.pk:
        Message.objects.filter(pk=dernier.pk).update(is_read=False, read_at=None)
    e = etat(conv, user)
    e.lu_le = dernier.sent_at - timedelta(microseconds=1)
    e.save(update_fields=["lu_le", "modifie_le"])


def filtrer(user, params):
    """Conversations d'un dossier, avec recherche et filtres. Lève RegleMessagerie (400)."""
    from django.utils.dateparse import parse_date
    dossier = params.get("dossier") or "reception"
    if dossier not in DOSSIERS_LISTE:
        raise RegleMessagerie("Dossier inconnu.", "dossier")
    qs = conversations_de(user)
    mes_etats = EtatConversation.objects.filter(conversation=OuterRef("pk"), utilisateur=user)
    masquee = Exists(mes_etats.filter(masquee=True))
    corbeille = Exists(mes_etats.filter(dossier=EtatConversation.CORBEILLE))
    archives = Exists(mes_etats.filter(dossier=EtatConversation.ARCHIVES))
    important = Exists(mes_etats.filter(important=True))
    recu = Exists(Message.objects.filter(conversation=OuterRef("pk")).exclude(sender=user))
    envoye = Exists(Message.objects.filter(conversation=OuterRef("pk"), sender=user))
    qs = qs.annotate(_masquee=masquee, _corbeille=corbeille, _archives=archives, _important=important,
                     _recu=recu, _envoye=envoye).filter(_masquee=False)
    if dossier == "reception":
        qs = qs.filter(_recu=True, _corbeille=False, _archives=False)
    elif dossier == "envoyes":
        qs = qs.filter(_envoye=True, _corbeille=False)
    elif dossier == "importants":
        qs = qs.filter(_important=True, _corbeille=False)
    elif dossier == "archives":
        qs = qs.filter(_archives=True)
    else:
        qs = qs.filter(_corbeille=True)
    q = (params.get("q") or "").strip()[:100]
    if q:
        qs = qs.filter(Q(subject__icontains=q) | Q(messages__body__icontains=q)
                       | Q(participants__first_name__icontains=q) | Q(participants__last_name__icontains=q)).distinct()
    if params.get("correspondant"):
        from apps.core.request_text import identifiant
        cible = identifiant(params["correspondant"])
        if cible is None:
            raise RegleMessagerie("Correspondant invalide.", "correspondant")
        qs = qs.filter(participants__pk=cible)
    if params.get("non_lus") in ("1", "true"):
        qs = qs.filter(Exists(Message.objects.filter(conversation=OuterRef("pk")).filter(non_lus_q(user))))
    for cle, lookup in (("du", "updated_at__date__gte"), ("au", "updated_at__date__lte")):
        if params.get(cle):
            jour = parse_date(params[cle]) if len(params[cle]) == 10 else None
            if jour is None:
                raise RegleMessagerie("Date invalide (AAAA-MM-JJ).", cle)
            qs = qs.filter(**{lookup: jour})
    return qs.order_by("-updated_at")


def compteurs(user):
    """Non lus par dossier (badge de la colonne de navigation)."""
    base = Message.objects.filter(conversation__participants=user).filter(non_lus_q(user))
    hors = EtatConversation.objects.filter(utilisateur=user).filter(
        Q(masquee=True) | Q(dossier__in=[EtatConversation.ARCHIVES, EtatConversation.CORBEILLE]))
    reception = base.exclude(conversation__in=hors.values("conversation")).values("conversation").distinct().count()
    from .models import BrouillonMessage
    return {"reception_non_lus": reception, "messages_non_lus": base.exclude(
        conversation__in=hors.values("conversation")).count(),
        "brouillons": BrouillonMessage.objects.filter(auteur=user).count()}
