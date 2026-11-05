"""
apps/boite_mail/imap.py — Accès IMAP à la boîte professionnelle et synchronisation.

Fournisseur : Hostinger Email (MX mx1/mx2.hostinger.com, IMAP imap.hostinger.com:993 SSL).
Identifiants : ceux du compte SMTP déjà configuré pour FEBA (EMAIL_HOST_USER /
EMAIL_HOST_PASSWORD, variables d'environnement du serveur) ; jamais en base, jamais
journalisés, jamais renvoyés par l'API.

Synchronisation incrémentale par dossier : UIDVALIDITY + dernier UID connu. Les corps
sont lus avec BODY.PEEK[] (la lecture ne marque rien comme lu chez le fournisseur).
Drapeaux (lu, important) et disparitions sont rapprochés à chaque passage.
"""
import email
import email.policy
import imaplib
import logging
import re
from contextlib import contextmanager
from datetime import timezone as dt_tz
from email.utils import getaddresses, parsedate_to_datetime

from django.conf import settings
from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone

logger = logging.getLogger("apps")

MAX_MESSAGE = 25 * 1024 * 1024       # au-delà : en-têtes seulement
MAX_PIECE = 15 * 1024 * 1024         # au-delà : pièce signalée, non copiée
LOT = 20


class BoiteIndisponible(Exception):
    """Fournisseur injoignable ou boîte non configurée (message destiné à l'utilisateur)."""


def configuration():
    hote = getattr(settings, "MAILBOX_IMAP_HOST", "")
    return {
        "hote": hote, "port": int(getattr(settings, "MAILBOX_IMAP_PORT", 993)),
        "adresse": (getattr(settings, "MAILBOX_ADDRESS", "") or "").lower(),
        "utilisateur": getattr(settings, "MAILBOX_IMAP_USER", ""),
        "configuree": bool(hote and getattr(settings, "MAILBOX_IMAP_USER", "") and getattr(settings, "MAILBOX_IMAP_PASSWORD", "")),
    }


@contextmanager
def connexion():
    conf = configuration()
    if not conf["configuree"]:
        raise BoiteIndisponible("La boîte contact n'est pas configurée sur ce serveur (accès IMAP).")
    try:
        m = imaplib.IMAP4_SSL(conf["hote"], conf["port"], timeout=30)
        m.login(conf["utilisateur"], settings.MAILBOX_IMAP_PASSWORD)
    except (imaplib.IMAP4.error, OSError) as exc:
        # Jamais le mot de passe : seulement la nature de l'échec.
        logger.warning("Boîte contact : connexion IMAP impossible (%s).", type(exc).__name__)
        raise BoiteIndisponible("Le fournisseur de messagerie est injoignable ou a refusé la connexion.") from exc
    try:
        yield m
    finally:
        try:
            m.logout()
        except Exception:
            pass


def _nom_dossier(ligne):
    texte = ligne.decode() if isinstance(ligne, bytes) else ligne
    m = re.match(r'\((?P<flags>[^)]*)\) "(?P<sep>[^"]*)" (?P<nom>.+)$', texte)
    if not m:
        return None, ""
    return m.group("nom").strip('"'), m.group("flags")


def dossiers(m):
    """Correspondance dossier logique → dossier IMAP, d'après les attributs SPECIAL-USE."""
    from .models import MessageMail as M
    carte = {M.RECEPTION: "INBOX"}
    typ, lignes = m.list()
    noms = []
    for ligne in lignes or []:
        nom, flags = _nom_dossier(ligne)
        if not nom:
            continue
        noms.append(nom)
        for drapeau, logique in (("\\Sent", M.ENVOYES), ("\\Trash", M.CORBEILLE), ("\\Junk", M.INDESIRABLES),
                                 ("\\Drafts", M.BROUILLONS), ("\\Archive", M.ARCHIVES)):
            if drapeau in flags:
                carte.setdefault(logique, nom)
    if M.ARCHIVES not in carte:
        for nom in noms:
            if nom.lower().endswith("archive") or nom.lower().endswith("archives"):
                carte[M.ARCHIVES] = nom
    return carte


def _decoder(valeur):
    return str(valeur or "").strip()


def _adresses(valeur):
    return [{"nom": n.strip(), "email": e.strip().lower()} for n, e in getaddresses([str(valeur or "")]) if e]


def analyser(brut):
    """Message RFC 822 → champs FEBA (texte, HTML nettoyé, pièces jointes)."""
    from .html_mail import nettoyer_mail
    msg = email.message_from_bytes(brut, policy=email.policy.default)
    texte, html, pieces = "", "", []
    for part in msg.walk():
        if part.is_multipart():
            continue
        dispo = (part.get_content_disposition() or "").lower()
        nom = part.get_filename()
        type_mime = part.get_content_type()
        if dispo == "attachment" or (nom and dispo != "inline") or (nom and not type_mime.startswith("text/")):
            try:
                donnees = part.get_payload(decode=True) or b""
            except Exception:
                donnees = b""
            pieces.append({"nom": (nom or "piece-jointe")[:255], "type": type_mime, "donnees": donnees})
            continue
        try:
            contenu = part.get_content()
        except Exception:
            contenu = (part.get_payload(decode=True) or b"").decode("utf-8", "replace")
        if type_mime == "text/plain" and not texte:
            texte = contenu
        elif type_mime == "text/html" and not html:
            html = contenu
    propre, propre_images, distantes = nettoyer_mail(html) if html else ("", "", False)
    if not texte and html:
        from apps.notifications.html_securise import en_texte
        texte = en_texte(propre)
    try:
        date = parsedate_to_datetime(msg.get("Date")) if msg.get("Date") else None
        if date and date.tzinfo is None:
            date = date.replace(tzinfo=dt_tz.utc)
    except (TypeError, ValueError):
        date = None
    exp = _adresses(msg.get("From"))
    return {
        "message_id": _decoder(msg.get("Message-ID"))[:255], "in_reply_to": _decoder(msg.get("In-Reply-To"))[:255],
        "references": _decoder(msg.get("References"))[:5000], "sujet": _decoder(msg.get("Subject"))[:500],
        "expediteur_nom": (exp[0]["nom"] if exp else "")[:255], "expediteur_email": (exp[0]["email"] if exp else "")[:255],
        "a": _adresses(msg.get("To")), "cc": _adresses(msg.get("Cc")), "cci": _adresses(msg.get("Bcc")),
        "repondre_a": (_adresses(msg.get("Reply-To")) or [{"email": ""}])[0]["email"][:255],
        "date": date, "texte": texte[:500000], "html": propre, "html_images": propre_images,
        "a_images_distantes": distantes, "extrait": re.sub(r"\s+", " ", texte).strip()[:300], "pieces": pieces,
    }


def _drapeaux(reponse):
    m = re.search(rb"FLAGS \(([^)]*)\)", reponse)
    flags = m.group(1).decode() if m else ""
    return "\\Seen" in flags, "\\Flagged" in flags


def _enregistrer(dossier, nom_imap, uidvalidity, uid, champs, lu, important, taille):
    from .models import MessageMail, PieceJointeMail
    pieces = champs.pop("pieces", [])
    date = champs.pop("date", None) or timezone.now()
    with transaction.atomic():
        # Rapprochement : même Message-ID déjà connu dans ce dossier sans identité IMAP
        # (envoi FEBA, message déplacé depuis FEBA) → on complète cette ligne, pas de doublon.
        existant = None
        if champs["message_id"]:
            existant = MessageMail.objects.select_for_update().filter(
                dossier=dossier, message_id=champs["message_id"], uid__isnull=True).first()
        if existant is not None:
            existant.dossier_imap, existant.uidvalidity, existant.uid = nom_imap, uidvalidity, uid
            existant.lu, existant.important, existant.taille = lu, important, taille
            existant.save(update_fields=["dossier_imap", "uidvalidity", "uid", "lu", "important", "taille", "synchronise_le"])
            return existant, False
        obj = MessageMail.objects.create(dossier=dossier, source=MessageMail.IMAP, dossier_imap=nom_imap,
                                         uidvalidity=uidvalidity, uid=uid, date=date, lu=lu, important=important,
                                         taille=taille, nb_pieces=len(pieces), **champs)
        for p in pieces:
            piece = PieceJointeMail(message=obj, nom=p["nom"], type_mime=p["type"], taille=len(p["donnees"]))
            if len(p["donnees"]) > MAX_PIECE:
                piece.non_copiee = True
                piece.save()
            else:
                piece.save()
                piece.fichier.save(p["nom"], ContentFile(p["donnees"]), save=True)
        return obj, True


def synchroniser_dossier(m, dossier, nom_imap, initial_max=500):
    """Nouveaux messages, drapeaux et disparitions d'un dossier. Renvoie le nombre de nouveaux."""
    from .models import EtatSynchroDossier, MessageMail
    typ, data = m.select(f'"{nom_imap}"', readonly=True)
    if typ != "OK":
        raise BoiteIndisponible(f"Dossier {nom_imap} inaccessible.")
    uidvalidity = int((m.response("UIDVALIDITY")[1] or [b"0"])[0] or 0)
    etat, _ = EtatSynchroDossier.objects.get_or_create(dossier_imap=nom_imap)
    if etat.uidvalidity != uidvalidity:
        # Dossier recréé chez le fournisseur : les anciens UID ne valent plus rien.
        MessageMail.objects.filter(dossier_imap=nom_imap, source=MessageMail.IMAP).exclude(uidvalidity=uidvalidity).delete()
        etat.uidvalidity, etat.dernier_uid = uidvalidity, 0
    typ, data = m.uid("SEARCH", None, "ALL")
    tous = sorted(int(x) for x in (data[0] or b"").split())
    nouveaux = [u for u in tous if u > etat.dernier_uid]
    if etat.dernier_uid == 0 and len(nouveaux) > initial_max:
        nouveaux = nouveaux[-initial_max:]            # synchronisation initiale bornée : les plus récents
    crees = 0
    for i in range(0, len(nouveaux), LOT):
        lot = nouveaux[i:i + LOT]
        typ, reponse = m.uid("FETCH", ",".join(map(str, lot)), "(UID FLAGS RFC822.SIZE)")
        tailles = {}
        for item in reponse or []:
            ligne = item[0] if isinstance(item, tuple) else item
            if not isinstance(ligne, bytes):
                continue
            u = re.search(rb"UID (\d+)", ligne)
            t = re.search(rb"RFC822\.SIZE (\d+)", ligne)
            if u:
                tailles[int(u.group(1))] = (int(t.group(1)) if t else 0, *_drapeaux(ligne))
        for uid in lot:
            taille, lu, important = tailles.get(uid, (0, False, False))
            partie = "BODY.PEEK[HEADER]" if taille > MAX_MESSAGE else "BODY.PEEK[]"
            typ, corps = m.uid("FETCH", str(uid), f"({partie})")
            brut = next((x[1] for x in corps or [] if isinstance(x, tuple)), b"")
            try:
                champs = analyser(brut)
            except Exception:
                logger.exception("Boîte contact : message %s/%s illisible, ignoré.", nom_imap, uid)
                continue
            _, cree = _enregistrer(dossier, nom_imap, uidvalidity, uid, champs, lu, important, taille)
            crees += int(cree)
        etat.dernier_uid = max(etat.dernier_uid, max(lot))
        etat.save(update_fields=["uidvalidity", "dernier_uid"])
    # Drapeaux et disparitions (messages lus, marqués, déplacés ou supprimés ailleurs).
    if tous:
        recents = tous[-2000:]
        typ, reponse = m.uid("FETCH", f"{recents[0]}:{recents[-1]}", "(UID FLAGS)")
        etats = {}
        for item in reponse or []:
            ligne = item[0] if isinstance(item, tuple) else item
            if isinstance(ligne, bytes) and (u := re.search(rb"UID (\d+)", ligne)):
                etats[int(u.group(1))] = _drapeaux(ligne)
        for obj in MessageMail.objects.filter(dossier_imap=nom_imap, uidvalidity=uidvalidity, uid__in=list(etats)):
            lu, important = etats[obj.uid]
            if (obj.lu, obj.important) != (lu, important):
                obj.lu, obj.important = lu, important
                obj.save(update_fields=["lu", "important", "synchronise_le"])
    disparus = MessageMail.objects.filter(dossier_imap=nom_imap, uidvalidity=uidvalidity, uid__isnull=False).exclude(uid__in=tous)
    disparus.delete()       # copie locale seulement : le message n'existe plus dans ce dossier chez le fournisseur
    etat.uidvalidity = uidvalidity
    etat.derniere_synchro, etat.derniere_erreur = timezone.now(), ""
    etat.save()
    return crees


def importer_envois_feba():
    """Envois réussis de FEBA depuis l'adresse officielle → dossier « Messages envoyés »."""
    from apps.notifications.email_models import EmailDelivery
    from .models import MessageMail
    adresse = configuration()["adresse"]
    deja = set(MessageMail.objects.filter(envoi__isnull=False).values_list("envoi_id", flat=True))
    envois = (EmailDelivery.objects.filter(status__in=[EmailDelivery.SENT, EmailDelivery.ACCEPTED])
              .exclude(pk__in=deja).select_related("content").order_by("pk"))
    crees = 0
    for d in envois.iterator():
        if adresse and d.from_email and adresse not in d.from_email.lower():
            continue
        contenu = d.content
        texte = (contenu.text_body if contenu else "") or ""
        if contenu is not None and contenu.is_redacted:
            texte = contenu.redaction_note or "Contenu confidentiel non archivé."
        visibles = d.en_tetes_visibles or {}
        a = [{"nom": "", "email": e} for e in (visibles.get("to") or [d.to_email])]
        cc = [{"nom": "", "email": e} for e in (visibles.get("cc") or d.cc_emails or [])]
        if MessageMail.objects.filter(dossier=MessageMail.ENVOYES, message_id=d.message_id).exclude(message_id="").exists():
            existant = MessageMail.objects.filter(dossier=MessageMail.ENVOYES, message_id=d.message_id).first()
            existant.envoi, existant.origine, existant.statut_envoi = d, d.purpose, d.status
            existant.save(update_fields=["envoi", "origine", "statut_envoi"])
            continue
        MessageMail.objects.create(
            dossier=MessageMail.ENVOYES, source=MessageMail.FEBA, message_id=d.message_id or "", sujet=d.subject,
            expediteur_email=(d.from_email or adresse)[:255], a=a, cc=cc, date=d.sent_at or d.created_at,
            texte=texte, extrait=re.sub(r"\s+", " ", texte).strip()[:300], lu=True, envoi=d, statut_envoi=d.status,
            origine=d.purpose, nb_pieces=contenu.attachments.count() if contenu else 0,
        )
        crees += 1
    return crees


def synchroniser_tout():
    """Passage complet (tâche périodique ou bouton « Actualiser »). Ne lève pas : journalise."""
    from django.core.cache import cache
    from .models import EtatSynchroDossier
    if not cache.add("boite_mail:synchro", "1", timeout=600):
        return {"en_cours": True}
    bilan = {"nouveaux": 0, "envois_feba": 0, "erreur": ""}
    try:
        bilan["envois_feba"] = importer_envois_feba()
        with connexion() as m:
            for logique, nom in dossiers(m).items():
                try:
                    bilan["nouveaux"] += synchroniser_dossier(m, logique, nom)
                except (imaplib.IMAP4.error, BoiteIndisponible) as exc:
                    EtatSynchroDossier.objects.update_or_create(dossier_imap=nom, defaults={"derniere_erreur": str(exc)[:500]})
                    logger.warning("Boîte contact : dossier %s non synchronisé (%s).", nom, type(exc).__name__)
    except BoiteIndisponible as exc:
        bilan["erreur"] = str(exc)
    finally:
        cache.delete("boite_mail:synchro")
    return bilan
