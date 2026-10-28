from django.db.models import Q
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from feba_project.bulk_delete import BulkDeleteMixin
from apps.accounts.permissions import IsTeacherOrAbove
from apps.core.features import HasEntityFeature
from apps.core.tenancy import get_request_school, IsSameTenant

from .models import VirtualRoom, VirtualRoomAttendance
from .serializers import VirtualRoomSerializer, VirtualRoomAttendanceSerializer


class VirtualRoomViewSet(BulkDeleteMixin, viewsets.ModelViewSet):
    """
    Salles virtuelles (visioconférence plugNmeet ; Jitsi en retour arrière).

    Visibilité :
      - superadmin / admin : toutes les salles de l'établissement ;
      - enseignant : salles qu'il a créées + salles de ses classes
        + salles générales ;
      - élève : salles de sa classe + salles générales ;
      - parent : salles des classes de ses enfants + salles générales.

    Création / modification / suppression : enseignant et au-dessus.
    """
    serializer_class = VirtualRoomSerializer
    permission_classes = [IsAuthenticated, HasEntityFeature, IsSameTenant]
    search_fields = ["name", "description", "room_code"]
    tenant_lookup = "school"
    # Fonctionnalité activée pour toutes les académies (FEBA comprise depuis
    # le 26/10/2026) ; elle reste vérifiée côté API : une entité pour
    # laquelle l'administration la désactive explicitement reçoit 403.
    required_feature = "virtual_classrooms"

    def get_queryset(self):
        user = self.request.user
        school = get_request_school(self.request)

        qs = VirtualRoom.objects.select_related(
            "class_obj", "subject", "created_by", "school",
        ).filter(is_active=True)

        # --- Isolation multi-tenant --------------------------------------
        if school is not None:
            qs = qs.filter(school=school)
        elif not user.is_superadmin():
            return qs.none()

        # Filtres facultatifs
        class_id = self.request.query_params.get("class")
        if class_id:
            qs = qs.filter(class_obj_id=class_id)
        room_status = self.request.query_params.get("status")
        if room_status:
            qs = qs.filter(status=room_status)

        # --- Visibilité par rôle ------------------------------------------
        if user.role_level >= 80:  # admin / superadmin
            return qs

        general = Q(class_obj__isnull=True)

        if user.role == "teacher":
            teacher = getattr(user, "teacher_profile", None)
            own = Q(created_by=user)
            if teacher:
                return qs.filter(own | general | Q(class_obj__in=teacher.classes.all())).distinct()
            return qs.filter(own | general).distinct()

        if user.role == "student":
            student = getattr(user, "student_profile", None)
            if student and student.current_class_id:
                return qs.filter(general | Q(class_obj_id=student.current_class_id)).distinct()
            return qs.filter(general)

        if user.role == "parent":
            parent = getattr(user, "parent_profile", None)
            if parent:
                class_ids = parent.children_links.filter(
                    student__current_class__isnull=False,
                ).values_list("student__current_class_id", flat=True)
                return qs.filter(general | Q(class_obj_id__in=list(class_ids))).distinct()
            return qs.filter(general)

        return qs.filter(general)

    def get_bulk_delete_permissions(self):
        # `bulk_delete` est déjà couvert par get_permissions() ci-dessous
        # (enseignant ou plus, fonctionnalité de l'entité).
        return []

    def get_permissions(self):
        # `HasEntityFeature` est présent sur TOUTES les actions, y compris
        # les actions d'écriture : sans lui, un enseignant FEBA pourrait
        # créer une salle virtuelle que son entité n'a pas le droit d'avoir.
        if self.action in ["create", "update", "partial_update", "destroy", "bulk_delete", "end_meeting"]:
            return [IsAuthenticated(), HasEntityFeature(), IsTeacherOrAbove()]
        return [IsAuthenticated(), HasEntityFeature(), IsSameTenant()]

    def perform_create(self, serializer):
        from rest_framework.exceptions import ValidationError
        from apps.schools.models import SchoolYear

        school = get_request_school(self.request)
        if school is None:
            # Super administrateur en mode « toutes les académies » : une salle
            # appartient toujours à UNE académie, choisie explicitement.
            raise ValidationError({"school": "Sélectionnez d'abord l'académie de la salle."})
        school_year = serializer.validated_data.get("school_year")
        if not school_year:
            school_year = SchoolYear.objects.filter(school=school, is_current=True).first()
        class_obj = serializer.validated_data.get("class_obj")
        if class_obj is not None and school_year is not None and class_obj.school_year_id != school_year.id:
            raise ValidationError({"class_obj": "Cette classe n'appartient pas à l'année scolaire choisie."})
        self._assert_can_manage_class(class_obj)
        serializer.save(created_by=self.request.user, school=school, school_year=school_year)

    # ── Gestion par un enseignant ───────────────────────────────────────
    #
    # Un enseignant gère SES salles et celles des classes qui lui sont
    # confiées. Avant, il pouvait modifier, supprimer ou fermer n'importe
    # quelle salle visible — y compris la salle générale de l'académie
    # créée par l'administration, ou le cours d'un collègue.

    def _teacher_class_ids(self):
        teacher = getattr(self.request.user, "teacher_profile", None)
        return set(teacher.classes.values_list("pk", flat=True)) if teacher else set()

    def _assert_can_manage_class(self, class_obj):
        from rest_framework.exceptions import PermissionDenied
        user = self.request.user
        if user.role_level >= 80 or class_obj is None:
            return
        if class_obj.pk not in self._teacher_class_ids():
            raise PermissionDenied("Cette classe ne vous est pas affectée.")

    def _assert_can_manage(self, room):
        from rest_framework.exceptions import PermissionDenied
        user = self.request.user
        if user.role_level >= 80 or room.created_by_id == user.id:
            return
        if room.class_obj_id and room.class_obj_id in self._teacher_class_ids():
            return
        raise PermissionDenied("Vous ne pouvez gérer que vos salles et celles de vos classes.")

    def perform_update(self, serializer):
        self._assert_can_manage(serializer.instance)
        if "class_obj" in serializer.validated_data:
            self._assert_can_manage_class(serializer.validated_data["class_obj"])
        serializer.save()

    def perform_destroy(self, instance):
        self._assert_can_manage(instance)
        instance.delete()

    def get_bulk_delete_queryset(self, ids):
        qs = self.get_queryset().filter(pk__in=ids)
        user = self.request.user
        if user.role_level >= 80:
            return qs
        return qs.filter(Q(created_by=user) | Q(class_obj_id__in=self._teacher_class_ids()))

    def _salle_a_rejoindre(self):
        """
        La salle visée, résolue dans le périmètre de l'ACADÉMIE.

        POURQUOI PAS `get_object()`
        ---------------------------
        `get_queryset()` filtre déjà par rôle : un élève ne voit que les
        salles de sa classe. Passer par lui ici donnait un 404 à un élève
        qui vise la salle d'une autre classe — et rendait du même coup
        INATTEIGNABLES les messages de `assert_can_join` écrits pour ce
        cas précis (« Vous n'êtes pas inscrit dans le groupe de cette
        salle »). L'utilisateur lisait « ressource introuvable » sur une
        salle qui existe, sans savoir quoi faire.

        La frontière qui doit rester opaque est celle de l'ACADÉMIE : la
        salle d'un autre établissement reste un 404, son existence n'est
        pas révélée. À l'intérieur de l'académie, l'autorisation est une
        décision qu'on explique — c'est le rôle de `assert_can_join`, qui
        répond 403 avec le motif.
        """
        from django.shortcuts import get_object_or_404

        user = self.request.user
        qs = VirtualRoom.objects.select_related(
            "class_obj", "subject", "created_by", "school",
        ).filter(is_active=True)

        school = get_request_school(self.request)
        if school is not None:
            qs = qs.filter(school=school)
        elif not user.is_superadmin():
            qs = qs.none()

        room = get_object_or_404(qs, pk=self.kwargs.get("pk"))
        self.check_object_permissions(self.request, room)
        return room

    @action(detail=True, methods=["post"])
    def join(self, request, pk=None):
        """
        Contrôle le droit d'entrer, ouvre (ou retrouve) la réunion et renvoie
        l'URL d'adhésion. Le jeton d'adhésion est à usage unique, émis par
        le serveur après ce contrôle ; la clé et le secret de l'API ne
        quittent jamais le backend.
        """
        from .services import JitsiAccessDenied, assert_can_join

        room = self._salle_a_rejoindre()

        # 1. Droit de rejoindre : académie, fonctionnalité, groupe, état.
        try:
            assert_can_join(request.user, room)
        except JitsiAccessDenied as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)

        moderator = request.user.role_level >= 50
        # Une réunion FERMÉE par l'enseignant ne se rouvre pas par un élève :
        # seul un modérateur peut relancer une salle terminée.
        if room.status == "ended" and not moderator:
            return Response(
                {"detail": "Ce cours est terminé. Il pourra être rejoint quand "
                           "l'enseignant l'aura rouvert.", "code": "meeting_ended"},
                status=status.HTTP_409_CONFLICT,
            )

        from .meetings import provider
        if provider() == "jitsi":
            return self._join_jitsi(request, room)
        return self._join_plugnmeet(request, room, moderator)

    def _join_plugnmeet(self, request, room, moderator):
        from . import plugnmeet
        from .meetings import open_meeting

        lang = (request.headers.get("Accept-Language") or "fr")[:2].lower()
        try:
            opened = open_meeting(room, request.user, moderator=moderator, lang=lang)
        except plugnmeet.PlugNmeetNotConfigured as exc:
            return Response(
                {"detail": "La visioconférence n'est pas encore configurée. Contactez "
                           "l'administration : aucune session n'est ouverte sur un "
                           "service public.",
                 "infrastructure_error": str(exc), "code": "video_not_configured"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except plugnmeet.PlugNmeetUnavailable:
            return Response(
                {"detail": "Le serveur de visioconférence ne répond pas. Réessayez dans "
                           "quelques instants ; si le problème persiste, contactez le "
                           "support technique.", "code": "video_unavailable"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except plugnmeet.PlugNmeetError as exc:
            return Response(
                {"detail": f"La réunion n'a pas pu être ouverte : {exc}", "code": "video_refused"},
                status=status.HTTP_502_BAD_GATEWAY,
            )
        room.refresh_from_db()
        data = self.get_serializer(room).data
        data.update({
            "provider": "plugnmeet",
            "join_url": opened["join_url"],
            "attendance_id": opened["attendance"].id if opened["attendance"] else None,
            "moderator": moderator,
            # Titre de l'onglet : celui de l'académie de la salle (serveur).
            "meeting_title": _meeting_title(room),
        })
        response = Response(data)
        # L'URL contient un jeton : jamais en cache.
        response["Cache-Control"] = "no-store"
        return response

    def _join_jitsi(self, request, room):
        """Moteur de RETOUR ARRIÈRE (VIDEO_PROVIDER=jitsi) — inchangé."""
        from .services import JitsiNotConfigured, build_jitsi_jwt

        try:
            jwt_token = build_jitsi_jwt(
                request.user, room.room_code,
                moderator=request.user.role_level >= 50,
                academy=room.school.code if room.school else "",
                group=room.class_obj.name if room.class_obj else "",
            )
        except JitsiNotConfigured as exc:
            return Response(
                {
                    "detail": (
                        "La visioconférence est momentanément indisponible : "
                        "l'instance de la plateforme n'est pas joignable. Contactez le "
                        "support technique."
                    ),
                    "infrastructure_error": str(exc),
                    "code": "jitsi_not_configured",
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        # FIX v35 : présence liée à l'INSCRIPTION ANNUELLE pour les élèves
        enrollment = None
        student = getattr(request.user, "student_profile", None)
        if student is not None and room.school_year_id:
            enrollment = student.enrollments.filter(school_year_id=room.school_year_id).first()
        attendance = VirtualRoomAttendance.objects.create(
            room=room, user=request.user, enrollment=enrollment,
        )

        if room.status in ("scheduled", "ended"):
            room.status = "live"
            room.save(update_fields=["status"])

        data = self.get_serializer(room).data
        data["provider"] = "jitsi"
        data["jwt"] = jwt_token
        data["attendance_id"] = attendance.id
        return Response(data)

    @action(detail=True, methods=["post"])
    def leave(self, request, pk=None):
        """
        Départ signalé par le navigateur (FIX v35). Avec plugNmeet, les
        événements du serveur font foi ; cet appel ne clôt que les
        présences qu'aucun événement ne suit.
        """
        from .meetings import record_api_leave

        room = self.get_object()
        attendance = record_api_leave(room, request.user)
        if attendance is None:
            return Response({"detail": "Aucune participation en cours."})
        return Response({"detail": "Participation enregistrée.",
                         "duration_seconds": attendance.duration_seconds,
                         "source": attendance.source})

    @action(detail=True, methods=["post"], url_path="end")
    def end_meeting(self, request, pk=None):
        """Ferme RÉELLEMENT la réunion (enseignant/admin), puis la salle FEBA."""
        from . import plugnmeet
        from .meetings import end_meeting

        room = self.get_object()
        self._assert_can_manage(room)
        try:
            end_meeting(room)
        except plugnmeet.PlugNmeetUnavailable:
            return Response(
                {"detail": "Le serveur de visioconférence ne répond pas : la réunion "
                           "n'a pas pu être fermée. Réessayez.", "code": "video_unavailable"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except plugnmeet.PlugNmeetError as exc:
            return Response({"detail": f"Fermeture refusée : {exc}"}, status=status.HTTP_502_BAD_GATEWAY)
        return Response(self.get_serializer(room).data)

    @action(detail=True, methods=["get"], url_path="meeting-status")
    def meeting_status(self, request, pk=None):
        """État RÉEL de la réunion côté plugNmeet (et resynchronisation)."""
        from . import plugnmeet
        from .meetings import close_open_attendances, provider

        room = self.get_object()
        if provider() != "plugnmeet":
            return Response({"provider": provider(), "status": room.status, "active": None})
        try:
            active = plugnmeet.is_room_active(room)
        except plugnmeet.PlugNmeetError:
            return Response({"provider": "plugnmeet", "status": room.status, "active": None,
                             "detail": "Serveur de visioconférence injoignable."},
                            status=status.HTTP_503_SERVICE_UNAVAILABLE)
        if not active and room.status == "live":
            from django.utils import timezone
            room.status = "ended"
            room.meeting_ended_at = room.meeting_ended_at or timezone.now()
            room.save(update_fields=["status", "meeting_ended_at", "updated_at"])
            close_open_attendances(room)
        return Response({"provider": "plugnmeet", "status": room.status, "active": active})

    def _recordings_room(self, request):
        """Salle dont on consulte les enregistrements : mêmes droits que pour y entrer."""
        from .services import JitsiAccessDenied, assert_can_join

        room = self._salle_a_rejoindre()
        try:
            assert_can_join(request.user, room)
        except JitsiAccessDenied as exc:
            return None, Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        from django.conf import settings
        if not settings.PLUGNMEET_RECORDING_ENABLED:
            return None, Response(
                {"detail": "L'enregistrement n'est pas activé sur ce serveur (service "
                           "d'enregistrement non déployé).", "code": "recording_disabled"},
                status=status.HTTP_404_NOT_FOUND,
            )
        return room, None

    @action(detail=True, methods=["get"])
    def recordings(self, request, pk=None):
        from . import plugnmeet

        room, error = self._recordings_room(request)
        if error:
            return error
        try:
            items = plugnmeet.fetch_recordings(room)
        except plugnmeet.PlugNmeetError:
            return Response({"detail": "Serveur de visioconférence injoignable."},
                            status=status.HTTP_503_SERVICE_UNAVAILABLE)
        return Response([
            {"record_id": r.get("record_id"), "created_at": r.get("creation_time"),
             "size_mb": r.get("file_size"), "duration": r.get("duration")}
            for r in items
        ])

    @action(detail=True, methods=["post"], url_path=r"recordings/(?P<record_id>[\w.\-]+)/download")
    def recording_download(self, request, pk=None, record_id=None):
        """Lien de téléchargement à durée limitée, émis après contrôle des droits."""
        from . import plugnmeet

        room, error = self._recordings_room(request)
        if error:
            return error
        try:
            info = plugnmeet.recording_info(record_id)
            # L'enregistrement doit appartenir à CETTE salle : pas d'accès à un
            # autre cours par simple changement d'identifiant.
            if (info.get("room_id") or "") != plugnmeet.room_id_for(room):
                return Response({"detail": "Enregistrement introuvable."}, status=status.HTTP_404_NOT_FOUND)
            url = plugnmeet.recording_download_url(record_id)
        except plugnmeet.PlugNmeetUnavailable:
            return Response({"detail": "Serveur de visioconférence injoignable."},
                            status=status.HTTP_503_SERVICE_UNAVAILABLE)
        except plugnmeet.PlugNmeetError:
            return Response({"detail": "Enregistrement introuvable."}, status=status.HTTP_404_NOT_FOUND)
        response = Response({"url": url})
        response["Cache-Control"] = "no-store"
        return response

    @action(detail=True, methods=["get"])
    def participants(self, request, pk=None):
        """Historique des participants (enseignant/admin)."""
        room = self.get_object()
        if request.user.role_level < 50:
            return Response(
                {"detail": "Accès réservé aux enseignants et administrateurs."},
                status=status.HTTP_403_FORBIDDEN,
            )
        qs = room.attendances.select_related("user").order_by("-joined_at")[:200]
        return Response(VirtualRoomAttendanceSerializer(qs, many=True).data)


def _meeting_title(room):
    from apps.schools.branding import get_branding
    return get_branding(room.school).meeting_title if room.school else ""


class PlugNmeetWebhookView(APIView):
    """
    POST /api/virtual-rooms/webhook/ — événements plugNmeet.

    Pas de session ni de jeton FEBA : l'authenticité est prouvée par la
    signature (en-tête Hash-Token, JWT HS256 sur l'empreinte du corps).
    Une signature invalide → 401, rien n'est enregistré.
    """
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        from . import plugnmeet
        from .meetings import handle_webhook

        body = request.body
        token = request.headers.get("Hash-Token") or request.headers.get("Authorization") or ""
        try:
            event = plugnmeet.verify_webhook(body, token)
        except plugnmeet.WebhookRejected as exc:
            import logging
            logging.getLogger("apps").warning("Webhook plugNmeet refusé : %s", exc)
            return Response({"detail": "Signature invalide."}, status=status.HTTP_401_UNAUTHORIZED)
        record, created = handle_webhook(event)
        return Response({"received": True, "stored": record is not None,
                         "duplicate": not created and record is not None})


class MeetingBrandingView(APIView):
    """
    POST /api/virtual-rooms/meeting-branding/   {"access_token": "<jeton plugNmeet>"}

    Identité de l'académie d'une réunion, pour l'onglet du client plugNmeet
    (titre exact et favicon). Appelé par `plugnmeet/client-branding/
    feba-branding.js`, injecté dans le client plugNmeet par
    scripts/plugnmeet_setup.sh.

    L'académie vient de la SALLE désignée par un jeton dont la signature est
    vérifiée côté serveur : modifier un identifiant ou un paramètre dans le
    navigateur ne permet pas d'afficher l'identité d'une autre académie.
    Réponse limitée à l'identité publique ; aucun secret, aucune donnée de
    la salle.
    """
    authentication_classes = []
    permission_classes = []

    def _cors(self, response):
        from urllib.parse import urlparse
        from . import plugnmeet
        if plugnmeet.is_configured():
            u = urlparse(plugnmeet.public_url())
            response["Access-Control-Allow-Origin"] = f"{u.scheme}://{u.netloc}"
            response["Vary"] = "Origin"
            response["Access-Control-Allow-Methods"] = "POST, OPTIONS"
            response["Access-Control-Allow-Headers"] = "Content-Type"
            response["Access-Control-Max-Age"] = "600"
        response["Cache-Control"] = "no-store"
        return response

    def options(self, request, *args, **kwargs):
        return self._cors(Response(status=status.HTTP_204_NO_CONTENT))

    def post(self, request):
        from django.conf import settings
        from apps.schools.public_branding import public_payload
        from . import plugnmeet

        token = request.data.get("access_token") if hasattr(request.data, "get") else None
        room = plugnmeet.room_for_join_token(token)
        if room is None or room.school is None:
            return self._cors(Response({"detail": "Jeton invalide."}, status=status.HTTP_404_NOT_FOUND))
        code = room.school.code
        base = (settings.PUBLIC_BASE_URL or "").rstrip("/") + f"/api/schools/public-branding/{code}/"
        data = public_payload(room.school, lambda suffix: base + suffix)
        return self._cors(Response({k: data[k] for k in (
            "academy_code", "short_name", "meeting_title", "favicon_16_url", "favicon_32_url",
            "apple_touch_icon_url", "version")}))


class JitsiHealthView(APIView):
    """
    GET /api/virtual-rooms/health/

    État de l'infrastructure de visioconférence, destiné à l'écran
    d'administration : « operational », « degraded » ou « unavailable ».

    Réservé aux enseignants et au-dessus : l'état d'infrastructure ne
    regarde ni les élèves ni les parents.
    """
    permission_classes = [IsAuthenticated, IsTeacherOrAbove]

    def get(self, request):
        from .meetings import provider
        if provider() == "plugnmeet":
            from .plugnmeet import health
            payload = health()
        else:
            from .services import jitsi_health
            payload = jitsi_health()
            payload["provider"] = "jitsi"

        # Le statut HTTP reflète l'état : un moniteur externe peut s'y fier.
        http_status = (
            status.HTTP_200_OK if payload["status"] == "operational"
            else status.HTTP_503_SERVICE_UNAVAILABLE
        )
        return Response(payload, status=http_status)
