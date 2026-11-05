"""
API de la boîte professionnelle — /api/boite-mail/

Toutes les routes exigent un droit EXPLICITE (super administrateur, ou membre de
l'administration à qui il a été accordé). Aucun identifiant du fournisseur n'est
jamais renvoyé.
"""
import os

from django.db.models import Count, Q
from django.http import FileResponse
from django.shortcuts import get_object_or_404
from django.utils.dateparse import parse_date
from rest_framework import status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.request_text import identifiant

from . import services as svc
from .imap import BoiteIndisponible, configuration
from .models import AccesBoiteMail, EtatSynchroDossier, JournalBoiteMail, MessageMail

PAR_PAGE = 50


def _exiger(request, droit="lire"):
    d = svc.droits(request.user)
    if not d.get(droit):
        return Response({"detail": "Accès à la boîte contact non autorisé."}, status=status.HTTP_403_FORBIDDEN)
    return None


def _personnes(liste):
    return [{"nom": p.get("nom", ""), "email": p.get("email", "")} for p in liste or []]


def _resume(m, voir_cci):
    return {
        "id": m.pk, "dossier": m.dossier, "source": m.source, "sujet": m.sujet or "(sans objet)",
        "expediteur": {"nom": m.expediteur_nom, "email": m.expediteur_email}, "a": _personnes(m.a),
        "date": m.date, "extrait": m.extrait, "lu": m.lu, "important": m.important, "nb_pieces": m.nb_pieces,
        "statut_envoi": m.statut_envoi, "origine": m.origine,
        **({"cci": _personnes(m.cci)} if voir_cci else {}),
    }


class EtatView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        d = svc.droits(request.user)
        if not d["lire"]:
            return Response({"acces": False, "droits": d})
        conf = configuration()
        non_lus = dict(MessageMail.objects.filter(lu=False).values_list("dossier").annotate(n=Count("id")).order_by())
        totaux = dict(MessageMail.objects.values_list("dossier").annotate(n=Count("id")).order_by())
        etats = list(EtatSynchroDossier.objects.order_by("dossier_imap").values("dossier_imap", "derniere_synchro", "derniere_erreur"))
        return Response({"acces": True, "droits": d, "adresse": conf["adresse"], "configuree": conf["configuree"],
                         "fournisseur": "Hostinger Email (IMAP)" if "hostinger" in conf["hote"] else conf["hote"],
                         "non_lus": non_lus, "totaux": totaux,
                         "importants": MessageMail.objects.filter(important=True).exclude(dossier=MessageMail.CORBEILLE).count(),
                         "synchro": etats})


class MessagesView(APIView):
    """?dossier=reception|envoyes|brouillons|importants|archives|corbeille|indesirables&q=&expediteur=&destinataire=
       &non_lus=1&pieces=1&du=&au=&page=&tri=-date|date"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if (refus := _exiger(request)):
            return refus
        p = request.query_params
        dossier = p.get("dossier") or MessageMail.RECEPTION
        qs = MessageMail.objects.all()
        if dossier == "importants":
            qs = qs.filter(important=True).exclude(dossier=MessageMail.CORBEILLE)
        elif dossier in dict(MessageMail.DOSSIERS):
            qs = qs.filter(dossier=dossier)
        else:
            return Response({"dossier": "Dossier inconnu."}, status=400)
        if q := (p.get("q") or "").strip()[:100]:
            qs = qs.filter(Q(sujet__icontains=q) | Q(expediteur_email__icontains=q) | Q(expediteur_nom__icontains=q)
                           | Q(texte__icontains=q) | Q(a__icontains=q))
        if e := (p.get("expediteur") or "").strip()[:100]:
            qs = qs.filter(Q(expediteur_email__icontains=e) | Q(expediteur_nom__icontains=e))
        if dst := (p.get("destinataire") or "").strip()[:100]:
            qs = qs.filter(Q(a__icontains=dst) | Q(cc__icontains=dst))
        if p.get("non_lus") in ("1", "true"):
            qs = qs.filter(lu=False)
        if p.get("pieces") in ("1", "true"):
            qs = qs.filter(nb_pieces__gt=0)
        for cle, lookup in (("du", "date__date__gte"), ("au", "date__date__lte")):
            if p.get(cle):
                jour = parse_date(p[cle]) if len(p[cle]) == 10 else None
                if jour is None:
                    return Response({cle: "Date invalide (AAAA-MM-JJ)."}, status=400)
                qs = qs.filter(**{lookup: jour})
        qs = qs.order_by("date", "pk") if p.get("tri") == "date" else qs.order_by("-date", "-pk")
        total = qs.count()
        page = max(1, identifiant(p.get("page")) or 1)
        lignes = list(qs[(page - 1) * PAR_PAGE: page * PAR_PAGE])
        voir_cci = svc.droits(request.user)["envoyer"]
        return Response({"count": total, "page": page, "pages": max(1, -(-total // PAR_PAGE)),
                         "results": [_resume(m, voir_cci) for m in lignes]})


class MessageDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        if (refus := _exiger(request)):
            return refus
        m = get_object_or_404(MessageMail.objects.prefetch_related("pieces"), pk=pk)
        images = request.query_params.get("images") == "1"
        voir_cci = svc.droits(request.user)["envoyer"]
        svc.journaliser(request.user, "lecture", m)
        return Response({
            **_resume(m, voir_cci), "cc": _personnes(m.cc), "repondre_a": m.repondre_a, "message_id": m.message_id,
            "texte": m.texte, "html": (m.html_images or m.html) if images else m.html,
            "a_images_distantes": m.a_images_distantes and not images,
            "pieces": [{"id": x.pk, "nom": x.nom, "type": x.type_mime, "taille": x.taille, "non_copiee": x.non_copiee}
                       for x in m.pieces.all()],
        })


class ActionView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk=None):
        if (refus := _exiger(request)):
            return refus
        action = request.data.get("action")
        ids = [pk] if pk else request.data.get("ids") or []
        if not isinstance(ids, list) or not ids or len(ids) > 100:
            return Response({"ids": "Liste de messages invalide (100 au plus)."}, status=400)
        ids = [identifiant(i) for i in ids]
        if None in ids:
            return Response({"ids": "Identifiant invalide."}, status=400)
        faits, erreurs = [], []
        for msg in MessageMail.objects.filter(pk__in=ids):
            try:
                svc.appliquer(request.user, msg, action)
                faits.append(msg.pk)
            except svc.ActionRefusee as exc:
                return Response({"detail": str(exc)}, status=403 if "droit" in str(exc) else 400)
            except BoiteIndisponible as exc:
                erreurs.append(str(exc))
                break
        if erreurs and not faits:
            return Response({"detail": erreurs[0]}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        return Response({"faits": faits, "erreurs": erreurs})


class PieceView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        if (refus := _exiger(request)):
            return refus
        from .models import PieceJointeMail
        piece = get_object_or_404(PieceJointeMail, pk=pk, non_copiee=False)
        svc.journaliser(request.user, "piece_telechargee", piece.message, piece.nom)
        reponse = FileResponse(piece.fichier.open("rb"), as_attachment=True, filename=os.path.basename(piece.nom),
                               content_type=piece.type_mime or "application/octet-stream")
        reponse["X-Content-Type-Options"] = "nosniff"
        reponse["Cache-Control"] = "private, no-store"
        return reponse


class EnvoyerView(APIView):
    """POST {mode: nouveau|repondre|repondre_tous|transferer, origine?, a, cc, cci, sujet, texte|html, attachments[]}"""
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def post(self, request):
        if (refus := _exiger(request, "envoyer")):
            return refus
        data = request.data
        mode = data.get("mode") or "nouveau"
        if mode not in ("nouveau", "repondre", "repondre_tous", "transferer"):
            return Response({"mode": "Mode inconnu."}, status=400)
        origine = None
        if mode != "nouveau":
            origine = get_object_or_404(MessageMail, pk=identifiant(data.get("origine")) or 0)
        liste = (lambda cle: data.getlist(cle)) if hasattr(data, "getlist") else (lambda cle: data.get(cle) or [])
        try:
            msg, envoi = svc.envoyer(request.user, a=liste("a"), cc=liste("cc"), cci=liste("cci"), sujet=data.get("sujet"),
                                     texte=data.get("texte") or "", html=data.get("html") or "",
                                     fichiers=request.FILES.getlist("attachments"), origine=origine, mode=mode)
        except svc.ActionRefusee as exc:
            return Response({"detail": str(exc)}, status=400)
        if envoi.status not in (envoi.SENT, envoi.ACCEPTED):
            return Response({"detail": "Le serveur d'envoi n'a pas accepté le message ; il sera réessayé automatiquement.",
                             "id": msg.pk, "statut": envoi.status}, status=status.HTTP_202_ACCEPTED)
        return Response({"id": msg.pk, "statut": envoi.status}, status=status.HTTP_201_CREATED)


class SynchroniserView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if (refus := _exiger(request)):
            return refus
        from .imap import synchroniser_tout
        bilan = synchroniser_tout()
        if bilan.get("erreur"):
            return Response({"detail": bilan["erreur"], **bilan}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        return Response(bilan)


class AccesView(APIView):
    """Super administrateur : qui accède à la boîte, avec quels droits."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if (refus := _exiger(request, "gerer")):
            return refus
        from apps.accounts.models import CustomUser
        acces = {a.utilisateur_id: a for a in AccesBoiteMail.objects.all()}
        comptes = CustomUser.objects.filter(is_active=True, role="admin").order_by("last_name", "first_name")
        return Response([{"id": u.pk, "nom": u.get_full_name() or u.email, "email": u.email,
                          "academie": getattr(u.school, "name", ""), "lire": bool(acces.get(u.pk) and acces[u.pk].peut_lire),
                          "envoyer": bool(acces.get(u.pk) and acces[u.pk].peut_envoyer),
                          "supprimer": bool(acces.get(u.pk) and acces[u.pk].peut_supprimer)} for u in comptes])

    def put(self, request):
        if (refus := _exiger(request, "gerer")):
            return refus
        from apps.accounts.models import CustomUser
        cible = get_object_or_404(CustomUser, pk=identifiant(request.data.get("utilisateur")) or 0, role="admin", is_active=True)
        vrai = lambda cle: str(request.data.get(cle, "")).lower() in ("1", "true")
        if not vrai("lire"):
            AccesBoiteMail.objects.filter(utilisateur=cible).delete()
        else:
            AccesBoiteMail.objects.update_or_create(utilisateur=cible, defaults={
                "peut_lire": True, "peut_envoyer": vrai("envoyer"), "peut_supprimer": vrai("supprimer"), "accorde_par": request.user})
        svc.journaliser(request.user, "droits_modifies", None, f"{cible.email} lire={vrai('lire')} envoyer={vrai('envoyer')} supprimer={vrai('supprimer')}")
        return Response({"ok": True})


class JournalView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if (refus := _exiger(request, "gerer")):
            return refus
        return Response([{"le": j.le, "utilisateur": j.utilisateur.get_full_name() if j.utilisateur else "-",
                          "action": j.action, "sujet": j.message.sujet[:120] if j.message else "", "detail": j.detail}
                         for j in JournalBoiteMail.objects.select_related("utilisateur", "message")[:200]])
