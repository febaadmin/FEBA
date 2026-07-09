"""
Schedule views — v29 (multi-tenant)

FIX SÉCURITÉ (v29) : "admin/superadmin see ALL schedules" retournait
littéralement l'emploi du temps de TOUTES les écoles de la plateforme
à n'importe quel admin. Idem pour le fallback par défaut et les
actions by_class / by_teacher. Corrigé par filtrage tenant systématique.

Fix v7 conservé : admin/superadmin voient bien tous les créneaux...
de LEUR établissement (et non plus de la plateforme entière).
"""
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from apps.accounts.permissions import IsAdminOrReadOnly
from apps.core.tenancy import get_request_school, IsSameTenant
from .models import ClassSchedule
from .serializers import ClassScheduleSerializer


class ClassScheduleViewSet(viewsets.ModelViewSet):
    serializer_class = ClassScheduleSerializer
    permission_classes = [IsAuthenticated, IsAdminOrReadOnly, IsSameTenant]
    filterset_fields = ["cls", "teacher", "school_year", "day_of_week"]
    tenant_lookup = "school_year__school"

    def get_queryset(self):
        user = self.request.user
        school = get_request_school(self.request)
        qs = ClassSchedule.objects.select_related(
            "cls__level", "subject", "teacher__user", "school_year"
        ).order_by("day_of_week", "start_time")

        # --- Isolation multi-tenant (FIX CRITIQUE v29) ----------------------
        if school is not None:
            qs = qs.filter(school_year__school=school)
        elif not user.is_superadmin():
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

    @action(
        detail=False, methods=["get"],
        url_path="class/(?P<class_id>[^/.]+)"
    )
    def by_class(self, request, class_id=None):
        qs = self.get_queryset().filter(cls_id=class_id)
        return Response(ClassScheduleSerializer(qs, many=True).data)

    @action(
        detail=False, methods=["get"],
        url_path="teacher/(?P<teacher_id>[^/.]+)"
    )
    def by_teacher(self, request, teacher_id=None):
        qs = self.get_queryset().filter(teacher_id=teacher_id)
        return Response(ClassScheduleSerializer(qs, many=True).data)

    @action(detail=False, methods=["get"])
    def my_schedule(self, request):
        """GET /api/schedule/my_schedule/ — schedule for logged-in user."""
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
        # Admin — return all (déjà filtré par établissement dans get_queryset)
        return Response(
            ClassScheduleSerializer(base, many=True).data
        )
