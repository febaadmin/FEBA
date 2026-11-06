"""
apps/boite_mail/services.py — Droits, actions et envois de la boîte contact.

Règle : une action modifie D'ABORD la boîte réelle (IMAP) ; la copie locale n'est mise
à jour que si le fournisseur a accepté. Un échec chez le fournisseur n'est jamais
présenté comme une réussite.
"""
import logging
import re

from django.conf import settings
from django.utils import timezone

from .imap import BoiteIndisponible, configuration, connexion, dossiers
from .models import AccesBoiteMail, JournalBoiteMail, MessageMail

logger = logging.getLogger("apps")

DROITS = ("lire", "envoyer", "supprimer")


def droits(user):
    """Droits de `user` sur la boîte : le super administrateur a tout ; les autres, ce qui leur a été accordé."""
    if not user.is_authenticated:
        return {d: False for d in DROITS} | {"gerer": False}
    if user.is_superadmin():
        return {d: True for d in DROITS} | {"gerer": True}
    acces = AccesBoiteMail.objects.filter(utilisateur=user).first()
    if acces is None or user.role_level < 80 or not user.is_active:
        # Réservé à l'administration : un enseignant, un parent ou un élève n'y accède jamais.
        return {d: False for d in DROITS} | {"gerer": False}
    return {"lire": acces.peut_lire, "envoyer": acces.peut_lire and acces.peut_envoyer,
            "supprimer": acces.peut_lire and acces.peut_supprimer, "gerer": False}


def journaliser(user, action, message=None, detail=""):
    JournalBoiteMail.objects.create(utilisateur=user if user and user.is_authenticated else None, action=action,
                                    message=message, detail=detail[:300])


class ActionRefusee(Exception):
    pass


ACTIONS = {"lu", "non_lu", "important", "non_important", "archiver", "corbeille", "restaurer", "supprimer_definitivement"}


def _deplacer(m, msg, cible_imap):
    """Déplacement chez le fournisseur (COPY + suppression marquée + EXPUNGE, MOVE absent)."""
    typ, _ = m.select(f'"{msg.dossier_imap}"')
    if typ != "OK":
        raise BoiteIndisponible("Dossier source inaccessible.")
    typ, _ = m.uid("COPY", str(msg.uid), f'"{cible_imap}"')
    if typ != "OK":
        raise BoiteIndisponible("Le fournisseur a refusé le déplacement.")
    m.uid("STORE", str(msg.uid), "+FLAGS.SILENT", "(\\Deleted)")
    m.expunge()


def appliquer(user, msg, action):
    """Applique l'action chez le fournisseur puis dans la copie locale."""
    if action not in ACTIONS:
        raise ActionRefusee("Action inconnue.")
    d = droits(user)
    if not d["lire"] or (action in ("corbeille", "supprimer_definitivement") and not d["supprimer"]):
        raise ActionRefusee("Vous n'avez pas le droit d'effectuer cette action.")
    if msg.source == MessageMail.FEBA and msg.uid is None:
        # Envoi FEBA non présent chez le fournisseur : seuls lu/important ont un sens, localement.
        if action not in ("lu", "non_lu", "important", "non_important"):
            raise ActionRefusee("Ce message envoyé par FEBA n'existe pas dans la boîte du fournisseur.")
        champ, valeur = ("lu", action == "lu") if action in ("lu", "non_lu") else ("important", action == "important")
        setattr(msg, champ, valeur)
        msg.save(update_fields=[champ, "synchronise_le"])
        return msg
    with connexion() as m:
        carte = dossiers(m)
        if action in ("lu", "non_lu", "important", "non_important"):
            m.select(f'"{msg.dossier_imap}"')
            drapeau = "\\Seen" if action in ("lu", "non_lu") else "\\Flagged"
            signe = "+" if action in ("lu", "important") else "-"
            typ, _ = m.uid("STORE", str(msg.uid), f"{signe}FLAGS.SILENT", f"({drapeau})")
            if typ != "OK":
                raise BoiteIndisponible("Le fournisseur a refusé la modification.")
            champ = "lu" if drapeau == "\\Seen" else "important"
            setattr(msg, champ, signe == "+")
            msg.save(update_fields=[champ, "synchronise_le"])
            return msg
        if action == "supprimer_definitivement":
            if msg.dossier != MessageMail.CORBEILLE:
                raise ActionRefusee("Placez d'abord le message dans la corbeille.")
            m.select(f'"{msg.dossier_imap}"')
            m.uid("STORE", str(msg.uid), "+FLAGS.SILENT", "(\\Deleted)")
            m.expunge()
            journaliser(user, "suppression_definitive", None, msg.sujet[:120])
            msg.delete()
            return None
        if action == "archiver":
            cible = MessageMail.ARCHIVES
            if cible not in carte:
                nom = "INBOX.Archive"
                m.create(f'"{nom}"')
                carte[cible] = nom
        elif action == "corbeille":
            cible = MessageMail.CORBEILLE
        else:   # restaurer : vers la réception (ou « envoyés » pour un message de l'adresse officielle)
            cible = MessageMail.ENVOYES if msg.expediteur_email == configuration()["adresse"] else MessageMail.RECEPTION
        if cible not in carte:
            raise BoiteIndisponible("Dossier de destination introuvable chez le fournisseur.")
        _deplacer(m, msg, carte[cible])
        # Identité IMAP inconnue dans le dossier cible : retrouvée à la prochaine synchronisation
        # (rapprochement par Message-ID, sans doublon).
        msg.dossier, msg.dossier_imap, msg.uid = cible, carte[cible], None
        msg.save(update_fields=["dossier", "dossier_imap", "uid", "synchronise_le"])
        journaliser(user, action, msg)
        return msg


def _liste(valeurs):
    from django.core.exceptions import ValidationError
    from django.core.validators import validate_email
    if isinstance(valeurs, str):
        valeurs = [v for v in re.split(r"[,;\s]+", valeurs) if v]
    propres = []
    for v in valeurs or []:
        v = str(v).strip().lower()
        try:
            validate_email(v)
        except ValidationError:
            raise ActionRefusee(f"Adresse invalide : {v}")
        if v not in propres:
            propres.append(v)
    return propres


def envoyer(user, *, a, cc=(), cci=(), sujet, texte="", html="", fichiers=(), origine=None, mode="nouveau",
            message_site=None, controle_droits=True):
    """
    Envoi depuis l'adresse officielle (nouveau, répondre, répondre à tous, transférer).
    Passe par le journal d'envoi FEBA (mailer), puis la copie est déposée dans le dossier
    « Envoyés » du fournisseur (comme le ferait un logiciel de messagerie).
    """
    from apps.notifications.attachments import AttachmentError, validate_uploads
    from apps.notifications.html_securise import HtmlRefuse, en_texte, nettoyer
    from apps.notifications.mailer import build_message, create_delivery, deliver
    # `controle_droits=False` : l'appelant a déjà vérifié un droit équivalent (réponse à un
    # message du site vitrine que l'utilisateur est autorisé à consulter).
    if controle_droits and not droits(user)["envoyer"]:
        raise ActionRefusee("Vous n'avez pas le droit d'écrire depuis l'adresse officielle.")
    a, cc, cci = _liste(a), _liste(cc), _liste(cci)
    if not a:
        raise ActionRefusee("Indiquez au moins un destinataire.")
    if len(a) + len(cc) + len(cci) > 50:
        raise ActionRefusee("Au plus 50 destinataires.")
    sujet = (sujet or "").strip()[:250]
    if not sujet:
        raise ActionRefusee("L'objet est obligatoire.")
    if html:
        try:
            html = nettoyer(html)
        except HtmlRefuse as exc:
            raise ActionRefusee(str(exc))
        texte = en_texte(html)
    if not (texte or "").strip():
        raise ActionRefusee("Le message est vide.")
    try:
        pieces = validate_uploads(fichiers)
    except AttachmentError as exc:
        raise ActionRefusee(str(exc))
    if origine is not None and mode == "transferer":
        for p in origine.pieces.filter(non_copiee=False):
            with p.fichier.open("rb") as f:
                pieces.append((p.nom, f.read(), p.type_mime or "application/octet-stream"))
    entetes = {"to": a, "cc": cc}
    if origine is not None and mode in ("repondre", "repondre_tous") and origine.message_id:
        refs = f"{origine.references} {origine.message_id}".strip()
        entetes["extra"] = {"In-Reply-To": origine.message_id, "References": refs[-990:]}
    envoi = create_delivery(purpose="boite_contact", to_email=a[0], cc=a[1:] + cc + cci, subject=sujet,
                            text_body=texte, html_body=html or None, attachments=pieces or None,
                            initiated_by=user, sms=False, en_tetes_visibles=entetes)
    envoi = deliver(envoi)
    journaliser(user, f"envoi_{mode}", origine, f"{len(a) + len(cc) + len(cci)} destinataire(s), statut {envoi.status}")
    msg = MessageMail.objects.create(
        dossier=MessageMail.ENVOYES, source=MessageMail.FEBA, message_id=envoi.message_id or "", sujet=sujet,
        expediteur_email=configuration()["adresse"] or (envoi.from_email or ""), a=[{"nom": "", "email": e} for e in a],
        cc=[{"nom": "", "email": e} for e in cc], cci=[{"nom": "", "email": e} for e in cci],
        date=envoi.sent_at or timezone.now(), texte=texte, html=html, extrait=re.sub(r"\s+", " ", texte)[:300],
        lu=True, envoi=envoi, statut_envoi=envoi.status,
        origine="site_vitrine" if message_site is not None else "boite_contact", nb_pieces=len(pieces),
        message_site=message_site, envoye_par=user,
        in_reply_to=(entetes.get("extra") or {}).get("In-Reply-To", ""),
    )
    if envoi.status == envoi.SENT:
        # Copie dans « Envoyés » chez le fournisseur (Hostinger ne garde pas les envois SMTP).
        try:
            brut = build_message(envoi).message().as_bytes()
            with connexion() as m:
                cible = dossiers(m).get(MessageMail.ENVOYES)
                if cible:
                    m.append(f'"{cible}"', "(\\Seen)", None, brut)
        except Exception as exc:  # l'envoi a réussi ; la copie est un confort
            logger.warning("Boîte contact : copie dans « Envoyés » impossible (%s).", type(exc).__name__)
    if origine is not None and mode in ("repondre", "repondre_tous") and not origine.lu:
        try:
            appliquer(user, origine, "lu")
        except Exception:
            pass
    return msg, envoi
