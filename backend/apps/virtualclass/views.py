from django.db.models import Q
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from feba_project.bulk_delete import BulkDeleteMixin
from apps.accounts.permissions import IsTeacherOrAbove
from apps.core.tenancy import get_request_school, IsSameTenant

from .models import VirtualRoom, VirtualRoomAttendance
from .serializers import VirtualRoomSerializer, VirtualRoomAttendanceSerializer


class VirtualRoomViewSet(BulkDeleteMixin, viewsets.ModelViewSet):
    """
    Salles virtuelles (visioconférence Jitsi Meet).

    Visibilité :
      - superadmin / admin : toutes les salles de l'établissement ;
      - enseignant : salles qu'il a créées + salles de ses classes
        + salles générales ;
      - élève : salles de sa classe + salles générales ;
      - parent : salles des classes de ses enfants + salles générales.

    Création / modification / suppression : enseignant et au-dessus.
    """
    serializer_class = VirtualRoomSerializer
    permission_classes = [IsAuthenticated, IsSameTenant]
    search_fields = ["name", "description", "room_code"]
    tenant_lookup = "school"

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

    def get_permissions(self):
        if self.action in ["create", "update", "partial_update", "destroy", "bulk_delete", "end_meeting"]:
            return [IsAuthenticated(), IsTeacherOrAbove()]
        return [IsAuthenticated(), IsSameTenant()]

    def perform_create(self, serializer):
        from apps.schools.models import SchoolYear

        school = get_request_school(self.request)
        school_year = serializer.validated_data.get("school_year")
        if not school_year and school is not None:
            school_year = SchoolYear.objects.filter(school=school, is_current=True).first()
        serializer.save(created_by=self.request.user, school=school, school_year=school_year)

    @action(detail=True, methods=["post"])
    def join(self, request, pk=None):
        """
        Enregistre la participation et renvoie les informations de
        connexion Jitsi (domaine + nom de salle). Le client ouvre
        ensuite l'iframe Jitsi avec ces informations.
        """
        from .services import build_jitsi_jwt

        room = self.get_object()
        if not room.is_active or room.status == "cancelled":
            return Response(
                {"detail": "Cette salle n'est plus disponible."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # FIX v35 : présence liée à l'INSCRIPTION ANNUELLE pour les élèves
        enrollment = None
        student = getattr(request.user, "student_profile", None)
        if student is not None and room.school_year_id:
            enrollment = student.enrollments.filter(school_year_id=room.school_year_id).first()
        attendance = VirtualRoomAttendance.objects.create(
            room=room, user=request.user, enrollment=enrollment,
        )

        if room.status == "scheduled":
            room.status = "live"
            room.save(update_fields=["status"])

        data = self.get_serializer(room).data
        # FIX v35 : jeton JWT signé par le backend (instance auto-hébergée) —
        # seuls les utilisateurs autorisés par FEBA peuvent ouvrir la salle.
        # Enseignants/admins = modérateurs.
        data["jwt"] = build_jitsi_jwt(
            request.user, room.room_code,
            moderator=request.user.role_level >= 50,
        )
        data["attendance_id"] = attendance.id
        return Response(data)

    @action(detail=True, methods=["post"])
    def leave(self, request, pk=None):
        """Clôt la participation courante (left_at + durée) — FIX v35."""
        from django.utils import timezone
        room = self.get_object()
        attendance = (
            room.attendances.filter(user=request.user, left_at__isnull=True)
            .order_by("-joined_at").first()
        )
        if attendance is None:
            return Response({"detail": "Aucune participation en cours."})
        attendance.left_at = timezone.now()
        attendance.duration_seconds = int(
            (attendance.left_at - attendance.joined_at).total_seconds()
        )
        attendance.save(update_fields=["left_at", "duration_seconds"])
        return Response({"detail": "Participation clôturée.",
                         "duration_seconds": attendance.duration_seconds})

    @action(detail=True, methods=["post"], url_path="end")
    def end_meeting(self, request, pk=None):
        """Clôture la salle (enseignant/admin)."""
        room = self.get_object()
        room.status = "ended"
        room.save(update_fields=["status"])
        return Response(self.get_serializer(room).data)

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
