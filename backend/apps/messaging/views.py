"""
Messaging views — v7

Architecture:
  GET  /api/messages/conversations/         → list user's conversations
  GET  /api/messages/conversations/{id}/    → full thread with all messages
  POST /api/messages/conversations/         → start new conversation (compose)
  POST /api/messages/conversations/{id}/reply/ → reply in thread
  PUT  /api/messages/conversations/{id}/mark_read/ → mark all as read
  GET  /api/messages/unread_count/          → badge count
"""
from apps.core.request_text import checked_upload, identifiant, text_field
from rest_framework import viewsets, status, views
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from django.utils import timezone
from django.db.models import Q
from . import services as svc
from .models import BrouillonMessage, Conversation, EtatConversation, Message
from .serializers import MessageSerializer
import logging

logger = logging.getLogger("apps")


def _personne(u):
    return {"id": u.pk, "full_name": u.get_full_name() or u.email, "role": u.role,
            "avatar": u.avatar.url if getattr(u, "avatar", None) else None}


def _message(m, request):
    pieces = [{"id": p.pk, "nom": p.nom, "taille": p.taille, "type": p.type_mime, "url": p.fichier.url}
              for p in m.pieces.all()]
    if m.attachment:      # pièce jointe unique des messages antérieurs
        pieces.insert(0, {"id": None, "nom": m.attachment_name or m.attachment.name.rsplit("/", 1)[-1],
                          "taille": None, "type": "", "url": m.attachment.url})
    return {"id": m.pk, "sender": _personne(m.sender), "body": m.body, "sent_at": m.sent_at,
            "is_mine": m.sender_id == request.user.pk, "pieces": pieces,
            # Rétrocompatibilité des écrans précédents.
            "attachment": m.attachment.url if m.attachment else None, "attachment_name": m.attachment_name,
            "has_attachment": bool(pieces), "is_read": m.is_read}


def _resume(conv, user, etats, dernier=None, nb_non_lus=None, nb_messages=None, a_pieces=None):
    e = etats.get(conv.pk)
    if dernier is None:
        dernier = conv.messages.order_by("-sent_at").select_related("sender").first()
    autres = [p for p in conv.participants.all() if p.pk != user.pk]
    return {
        "id": conv.pk, "subject": conv.subject, "updated_at": conv.updated_at,
        "participants": [_personne(p) for p in conv.participants.all()],
        "correspondants": [_personne(p) for p in autres],
        "other_participant": _personne(autres[0]) if autres else None,
        "latest_message": {"id": dernier.pk, "body": dernier.body[:140] + ("…" if len(dernier.body) > 140 else ""),
                           "sender_name": dernier.sender.get_full_name(), "sent_at": dernier.sent_at,
                           "is_mine": dernier.sender_id == user.pk} if dernier else None,
        "unread_count": svc.nb_non_lus(user, conv) if nb_non_lus is None else nb_non_lus,
        "important": bool(e and e.important), "dossier": e.dossier if e else "reception",
        "nb_messages": conv.messages.count() if nb_messages is None else nb_messages,
        "a_pieces": (conv.messages.filter(Q(pieces__isnull=False) | ~Q(attachment="")).exists()
                     if a_pieces is None else a_pieces),
    }


def _erreur(exc):
    return Response({exc.champ: str(exc), "error": str(exc)}, status=exc.statut)


class ConversationViewSet(viewsets.ModelViewSet):
    """
    Messagerie interne : seuls les participants accèdent à une conversation.

    GET    conversations/?dossier=reception|envoyes|importants|archives|corbeille&q=&non_lus=1&correspondant=&du=&au=
    POST   conversations/                      {recipient_ids[] | recipient_id, subject, body, attachments[], brouillon_id}
    GET    conversations/{id}/                 fil complet (pièces jointes en liens signés)
    POST   conversations/{id}/reply/           {body, attachments[], a_tous}
    PUT    conversations/{id}/mark_read/       ;  POST conversations/{id}/marquer/ {lu}
    POST   conversations/{id}/important/ {important} ; POST conversations/{id}/deplacer/ {dossier}
    POST   conversations/{id}/supprimer_definitivement/   (depuis la corbeille ; pour soi seul)
    GET    conversations/compteurs/ ; GET conversations/correspondants/ ; GET conversations/unread_count/
    """
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    http_method_names = ["get", "post", "put", "patch", "head", "options"]

    def get_queryset(self):
        return svc.conversations_de(self.request.user).prefetch_related("participants")

    def list(self, request, *args, **kwargs):
        try:
            qs = svc.filtrer(request.user, request.query_params)
        except svc.RegleMessagerie as exc:
            return _erreur(exc)
        # Requêtes groupées (pas de requête par conversation) : compteurs et dernier message.
        from django.db.models import Count, Exists, OuterRef, Subquery
        moi = request.user
        derniers = Message.objects.filter(conversation=OuterRef("pk")).order_by("-sent_at").values("pk")[:1]
        qs = qs.annotate(
            _dernier=Subquery(derniers),
            _nb=Count("messages", distinct=True),
            _pj=Exists(Message.objects.filter(conversation=OuterRef("pk")).filter(Q(pieces__isnull=False) | ~Q(attachment=""))),
        )
        convs = list(qs.prefetch_related("participants")[:200])
        etats = {e.conversation_id: e for e in EtatConversation.objects.filter(utilisateur=moi, conversation__in=convs)}
        messages = {m.pk: m for m in Message.objects.filter(pk__in=[c._dernier for c in convs]).select_related("sender")}
        non_lus = dict(Message.objects.filter(conversation__in=convs).filter(svc.non_lus_q(moi))
                       .values_list("conversation").annotate(n=Count("id")).order_by())
        return Response([_resume(c, moi, etats, dernier=messages.get(c._dernier), nb_non_lus=non_lus.get(c.pk, 0),
                                 nb_messages=c._nb, a_pieces=c._pj) for c in convs])

    def retrieve(self, request, *args, **kwargs):
        conv = self.get_object()
        e = EtatConversation.objects.filter(conversation=conv, utilisateur=request.user).first()
        messages = conv.messages.select_related("sender").prefetch_related("pieces").order_by("sent_at")
        return Response({
            **_resume(conv, request.user, {conv.pk: e} if e else {}),
            "messages": [_message(m, request) for m in messages],
        })

    def _fichiers(self, request):
        return request.FILES.getlist("attachments") + ([request.FILES["attachment"]] if "attachment" in request.FILES else [])

    def create(self, request, *args, **kwargs):
        data = request.data
        ids = data.getlist("recipient_ids") if hasattr(data, "getlist") else data.get("recipient_ids")
        if not ids:
            unique = data.get("recipient_id") or data.get("recipient")
            ids = [unique] if unique else []
        if isinstance(ids, str):
            ids = [x for x in ids.split(",") if x]
        try:
            destinataires = svc.resoudre_destinataires(request.user, ids, request)
            fichiers = svc.valider_pieces(self._fichiers(request))
            conv, _ = svc.demarrer(request.user, destinataires, text_field(data, "subject"),
                                   text_field(data, "body"), fichiers, request)
        except svc.RegleMessagerie as exc:
            return _erreur(exc)
        if identifiant(data.get("brouillon_id")):
            BrouillonMessage.objects.filter(pk=identifiant(data.get("brouillon_id")), auteur=request.user).delete()
        logger.info("Message interne : %s → %d destinataire(s) [conversation %s]",
                    request.user.pk, len(destinataires), conv.pk)
        self.kwargs["pk"] = conv.pk
        return Response(self.retrieve(request, pk=conv.pk).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def reply(self, request, pk=None):
        conv = self.get_object()
        a_tous = str(request.data.get("a_tous", "true")).lower() not in ("0", "false", "non")
        try:
            fichiers = svc.valider_pieces(self._fichiers(request))
            conv2, msg = svc.repondre(request.user, conv, text_field(request.data, "body"), fichiers, a_tous=a_tous)
        except svc.RegleMessagerie as exc:
            return _erreur(exc)
        if identifiant(request.data.get("brouillon_id")):
            BrouillonMessage.objects.filter(pk=identifiant(request.data.get("brouillon_id")), auteur=request.user).delete()
        corps = _message(Message.objects.select_related("sender").prefetch_related("pieces").get(pk=msg.pk), request)
        corps["conversation"] = conv2.pk
        return Response(corps, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["put", "patch"])
    def mark_read(self, request, pk=None):
        conv = self.get_object()
        avant = svc.nb_non_lus(request.user, conv)
        svc.marquer_lu(conv, request.user)
        return Response({"marked_read": avant})

    @action(detail=True, methods=["post"])
    def marquer(self, request, pk=None):
        conv = self.get_object()
        lu = str(request.data.get("lu", "true")).lower() not in ("0", "false")
        (svc.marquer_lu if lu else svc.marquer_non_lu)(conv, request.user)
        return Response({"lu": lu, "unread_count": svc.nb_non_lus(request.user, conv)})

    @action(detail=True, methods=["post"])
    def important(self, request, pk=None):
        conv = self.get_object()
        e = svc.etat(conv, request.user)
        e.important = str(request.data.get("important", "true")).lower() not in ("0", "false")
        e.save(update_fields=["important", "modifie_le"])
        return Response({"important": e.important})

    @action(detail=True, methods=["post"])
    def deplacer(self, request, pk=None):
        conv = self.get_object()
        dossier = request.data.get("dossier")
        if dossier not in dict(EtatConversation.DOSSIERS):
            return Response({"dossier": "Dossier inconnu."}, status=400)
        e = svc.etat(conv, request.user)
        e.dossier, e.masquee = dossier, False
        e.save(update_fields=["dossier", "masquee", "modifie_le"])
        return Response({"dossier": e.dossier})

    @action(detail=True, methods=["post"])
    def supprimer_definitivement(self, request, pk=None):
        conv = self.get_object()
        e = svc.etat(conv, request.user)
        if e.dossier != EtatConversation.CORBEILLE:
            return Response({"dossier": "Placez d'abord la conversation dans la corbeille."}, status=400)
        e.masquee = True
        e.save(update_fields=["masquee", "modifie_le"])
        return Response({"masquee": True})

    @action(detail=False, methods=["get"])
    def compteurs(self, request):
        return Response(svc.compteurs(request.user))

    @action(detail=False, methods=["get"])
    def correspondants(self, request):
        """Personnes avec qui l'utilisateur a échangé (filtre « correspondant »)."""
        from apps.accounts.models import CustomUser
        comptes = (CustomUser.objects.filter(conversations__participants=request.user)
                   .exclude(pk=request.user.pk).distinct().order_by("last_name", "first_name")[:300])
        return Response([_personne(u) for u in comptes])

    @action(detail=False, methods=["get"])
    def unread_count(self, request):
        return Response({"count": svc.compteurs(request.user)["messages_non_lus"]})


class BrouillonMessageViewSet(viewsets.ModelViewSet):
    """Brouillons de l'auteur (et de lui seul) ; destinataires revalidés à l'envoi."""
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_queryset(self):
        return BrouillonMessage.objects.filter(auteur=self.request.user)

    @staticmethod
    def _donnees(b, request):
        return {"id": b.pk, "destinataires": b.destinataires, "objet": b.objet, "corps": b.corps,
                "conversation": b.conversation_id, "modifie_le": b.modifie_le,
                "destinataires_detail": [_personne(u) for u in svc.destinataires_autorises(request.user, request)
                                         .filter(pk__in=[d for d in b.destinataires if isinstance(d, int)])]}

    def _remplir(self, b, data):
        ids = data.get("destinataires") or []
        if not isinstance(ids, list) or len(ids) > svc.MAX_DESTINATAIRES:
            raise svc.RegleMessagerie("Destinataires invalides.", "destinataires")
        propres = [identifiant(x) for x in ids]
        if None in propres:
            raise svc.RegleMessagerie("Destinataires invalides.", "destinataires")
        b.destinataires = propres
        b.objet = str(data.get("objet") or "")[:200]
        b.corps = str(data.get("corps") or "")[:20000]
        conv_id = data.get("conversation")
        cible = identifiant(conv_id) if conv_id not in (None, "") else None
        b.conversation = svc.conversations_de(self.request.user).filter(pk=cible).first() if cible else None
        if conv_id and b.conversation is None:
            raise svc.RegleMessagerie("Conversation introuvable.", "conversation", statut=404)
        return b

    def list(self, request, *args, **kwargs):
        return Response([self._donnees(b, request) for b in self.get_queryset()[:100]])

    def retrieve(self, request, *args, **kwargs):
        return Response(self._donnees(self.get_object(), request))

    def create(self, request, *args, **kwargs):
        if self.get_queryset().count() >= 100:
            return Response({"error": "Au plus 100 brouillons."}, status=400)
        try:
            b = self._remplir(BrouillonMessage(auteur=request.user), request.data)
        except svc.RegleMessagerie as exc:
            return _erreur(exc)
        b.save()
        return Response(self._donnees(b, request), status=201)

    def partial_update(self, request, *args, **kwargs):
        b = self.get_object()
        try:
            self._remplir(b, {**self._donnees(b, request), **request.data})
        except svc.RegleMessagerie as exc:
            return _erreur(exc)
        b.save()
        return Response(self._donnees(b, request))


# ── Legacy compatibility view for flat messages (inbox/sent) ──────────────────
class MessageViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Legacy read-only access for backward compatibility.
    Prefer ConversationViewSet for new code.
    """
    serializer_class = MessageSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        return (
            Message.objects
            .filter(Q(sender=user) | Q(recipient=user))
            .select_related("sender", "recipient")
            .order_by("-sent_at")
        )

    @action(detail=False, methods=["get"])
    def inbox(self, request):
        msgs = Message.objects.filter(
            recipient=request.user
        ).select_related("sender").order_by("-sent_at")
        return Response(MessageSerializer(msgs, many=True, context={"request": request}).data)

    @action(detail=False, methods=["get"])
    def sent(self, request):
        msgs = Message.objects.filter(
            sender=request.user
        ).select_related("recipient").order_by("-sent_at")
        return Response(MessageSerializer(msgs, many=True, context={"request": request}).data)

    @action(detail=False, methods=["get"])
    def unread_count(self, request):
        count = Message.objects.filter(recipient=request.user, is_read=False).count()
        return Response({"count": count})

    @action(detail=True, methods=["put", "patch"])
    def read(self, request, pk=None):
        msg = self.get_object()
        if msg.recipient == request.user:
            msg.is_read = True
            msg.read_at = timezone.now()
            msg.save(update_fields=["is_read", "read_at"])
        return Response({"detail": "Lu."})

    @action(detail=True, methods=["post"])
    def reply(self, request, pk=None):
        original = self.get_object()
        recipient = original.sender if original.recipient == request.user else original.recipient
        body = text_field(request.data, "body")
        if not body:
            return Response({"error": "Corps du message requis."}, status=400)
        subject = original.subject if original.subject.startswith("Re: ") else f"Re: {original.subject}"
        msg = Message.objects.create(
            sender=request.user, recipient=recipient,
            subject=subject, body=body,
            thread_id=original.thread_id, parent_message=original,
        )
        attachment = checked_upload(request.FILES.get("attachment"))
        if attachment:
            msg.attachment = attachment
            msg.attachment_name = attachment.name
            msg.save(update_fields=["attachment", "attachment_name"])
        return Response(MessageSerializer(msg).data, status=201)
