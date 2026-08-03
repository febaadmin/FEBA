"""
apps/schedule/views.py — Emplois du temps FEBA et FEBA FHA

DEUX ENDPOINTS, DEUX ACADÉMIES (P3)
-----------------------------------
    /api/schedule/                  créneaux présentiels FEBA
    /api/schedule/online-sessions/  séances en direct FEBA FHA

Un seul endpoint mélangeait deux métiers incompatibles et rendait
impossible de dire, en lisant une ligne, à quelle académie elle
appartenait. Voir apps/schedule/models.py pour la justification des deux
modèles.

ISOLATION (rappel v29)
----------------------
« admin/superadmin voient TOUS les emplois du temps » renvoyait
littéralement ceux de toutes les écoles de la plateforme à n'importe quel
admin. Le filtrage tenant est donc systématique et explicite.

MODE « TOUTES LES ACADÉMIES »
----------------------------
Réservé au superadmin, il renvoie l'UNION des académies — jamais une seule.
Chaque objet porte son `academy_code`, sinon l'union serait illisible.
En revanche la CRÉATION y est refusée : créer un créneau sans académie
explicite reviendrait à en choisir une au hasard.
"""
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.permissions import IsAdminOrReadOnly
from apps.core.features import HasEntityFeature
from apps.core.tenancy import IsSameTenant, get_request_school

from .models import ClassSchedule, OnlineSessionSchedule
from .serializers import ClassScheduleSerializer, OnlineSessionScheduleSerializer


class ClassScheduleViewSet(viewsets.ModelViewSet):
    """Emploi du temps présentiel — académies de type « campus »."""

    serializer_class = ClassScheduleSerializer
    permission_classes = [IsAuthenticated, IsAdminOrReadOnly, IsSameTenant]
    filterset_fields = ["cls", "teacher", "school_year", "day_of_week"]
    tenant_lookup = "school_year__school"

    def get_queryset(self):
        user = self.request.user
        school = get_request_school(self.request)
        qs = ClassSchedule.objects.select_related(
            "cls__level", "subject", "teacher__user",
            "school_year__school",
        ).order_by("day_of_week", "start_time")

        if school is not None:
            qs = qs.filter(school_year__school=school)
        elif user.is_superadmin():
            # Mode consolidé : l'union des académies, jamais une seule.
            # Chaque ligne porte academy_code pour rester identifiable.
            qs = qs.filter(school_year__school__entity_type="campus")
        else:
            return qs.none()

        if user.role_level >= 80:
            return qs

        elif user.is_teacher():
            try:
                return qs.filter(teacher__user=user)
            except Exception:
                return qs.none()

        elif user.is_student():
            try:
                return qs.filter(cls=user.student_profile.current_class)
            except Exception:
                return qs.none()

        elif user.is_parent():
            try:
                classes = [
                    ps.student.current_class
                    for ps in user.parent_profile.children_links
                    .select_related("student__current_class").all()
                    if ps.student.current_class
                ]
                return qs.filter(cls__in=classes)
            except Exception:
                return qs.none()

        return qs.none()

    def perform_create(self, serializer):
        # Interdiction de créer « quelque part » : en mode consolidé, aucune
        # académie n'est active, donc aucune ne peut être choisie.
        if get_request_school(self.request) is None:
            raise PermissionDenied(
                "Sélectionnez une académie avant de créer un créneau : en mode "
                "« Toutes les Académies », aucune académie n'est active."
            )
        serializer.save()

    @action(detail=False, methods=["get"], url_path="class/(?P<class_id>[^/.]+)")
    def by_class(self, request, class_id=None):
        qs = self.get_queryset().filter(cls_id=class_id)
        return Response(ClassScheduleSerializer(qs, many=True).data)

    @action(detail=False, methods=["get"], url_path="teacher/(?P<teacher_id>[^/.]+)")
    def by_teacher(self, request, teacher_id=None):
        qs = self.get_queryset().filter(teacher_id=teacher_id)
        return Response(ClassScheduleSerializer(qs, many=True).data)

    @action(detail=False, methods=["get"])
    def my_schedule(self, request):
        """GET /api/schedule/my_schedule/ — emploi du temps de l'utilisateur."""
        user = request.user
        base = self.get_queryset()
        if user.is_teacher():
            try:
                qs = base.filter(teacher__user=user)
                return Response(ClassScheduleSerializer(qs, many=True).data)
            except Exception:
                return Response([])
        elif user.is_student():
            try:
                qs = base.filter(cls=user.student_profile.current_class)
                return Response(ClassScheduleSerializer(qs, many=True).data)
            except Exception:
                return Response([])
        return Response(ClassScheduleSerializer(base, many=True).data)


class OnlineSessionScheduleViewSet(viewsets.ModelViewSet):
    """
    Séances en direct FEBA FHA — académies de type « online » uniquement.

    `required_feature` fait refuser l'endpoint côté SERVEUR pour une
    académie présentielle : masquer l'onglet dans React ne protégerait
    rien, l'URL resterait appelable à la main.
    """

    serializer_class = OnlineSessionScheduleSerializer
    permission_classes = [IsAuthenticated, IsAdminOrReadOnly, IsSameTenant, HasEntityFeature]
    required_feature = "online_lessons"
    filterset_fields = ["group", "teacher", "school_year", "day_of_week", "is_active"]
    tenant_lookup = "academy"

    def get_queryset(self):
        user = self.request.user
        school = get_request_school(self.request)
        qs = OnlineSessionSchedule.objects.select_related(
            "academy", "group__level", "subject", "teacher__user",
            "school_year", "virtual_room",
        ).order_by("day_of_week", "start_time_utc")

        if school is not None:
            qs = qs.filter(academy=school)
        elif user.is_superadmin():
            qs = qs.filter(academy__entity_type="online")
        else:
            return qs.none()

        if user.role_level >= 80:
            return qs
        if user.is_teacher():
            return qs.filter(teacher__user=user)
        if user.is_student():
            try:
                return qs.filter(group=user.student_profile.current_class)
            except Exception:
                return qs.none()
        if user.is_parent():
            try:
                groups = [
                    link.student.current_class
                    for link in user.parent_profile.children_links
                    .select_related("student__current_class").all()
                    if link.student.current_class
                ]
                return qs.filter(group__in=groups)
            except Exception:
                return qs.none()
        return qs.none()

    def get_serializer_context(self):
        context = super().get_serializer_context()
        # L'académie n'est JAMAIS lue depuis le payload : elle vient du
        # contexte serveur. Un `academy` envoyé par le client est ignoré
        # (champ en lecture seule) — il ne peut pas déplacer une séance
        # vers l'autre académie.
        context["academy"] = get_request_school(self.request)
        return context

    def perform_create(self, serializer):
        academy = get_request_school(self.request)
        if academy is None:
            raise PermissionDenied(
                "Sélectionnez FEBA FHA avant de créer une séance : en mode "
                "« Toutes les Académies », aucune académie n'est active."
            )
        serializer.save(academy=academy)

    def perform_update(self, serializer):
        # L'académie d'une séance existante ne change jamais : déplacer une
        # séance d'une académie à l'autre casserait toutes ses relations
        # (groupe, matière, enseignant, salle virtuelle).
        serializer.save(academy=serializer.instance.academy)

    @action(detail=False, methods=["get"])
    def my_sessions(self, request):
        """GET /api/schedule/online-sessions/my_sessions/ — séances de l'utilisateur."""
        qs = self.get_queryset()
        user = request.user
        if user.is_teacher():
            qs = qs.filter(teacher__user=user)
        return Response(self.get_serializer(qs, many=True).data)

    @action(detail=False, methods=["get"])
    def week(self, request):
        """
        GET …/week/?timezone=America/New_York

        Emploi du temps hebdomadaire rendu dans le fuseau demandé. Le calcul
        est fait côté serveur : laisser chaque client convertir l'UTC lui-même
        multiplierait les implémentations — et les erreurs de changement de
        jour au passage de minuit.
        """
        tz_name = request.query_params.get("timezone") or None
        days = {}
        for session in self.get_queryset():
            local = session.local_start(tz_name)
            if local is None:
                continue
            days.setdefault(local.weekday(), []).append({
                **self.get_serializer(session).data,
                "local_time": local.strftime("%H:%M"),
                "local_weekday": local.weekday(),
            })
        return Response(
            {"timezone": tz_name or "fuseau de la séance", "days": days},
            status=status.HTTP_200_OK,
        )
