from feba_project.bulk_delete import BulkDeleteMixin
"""
Teachers views — v7

Key fixes:
  - /api/teachers/{id}/subjects/ returns subjects for a specific teacher
  - /api/teachers/my_subjects/ returns subjects for the logged-in teacher
  - Proper RBAC filtering
"""
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from apps.accounts.permissions import IsAdminOrReadOnly, IsAdminOrAbove
from apps.core.tenancy import get_request_school, IsSameTenant
from .models import Teacher
from .serializers import TeacherSerializer
import logging

logger = logging.getLogger("apps")


class TeacherViewSet(BulkDeleteMixin, viewsets.ModelViewSet):
    serializer_class = TeacherSerializer
    permission_classes = [IsAuthenticated, IsAdminOrReadOnly, IsSameTenant]
    search_fields = [
        "user__first_name", "user__last_name", "user__email", "employee_id"
    ]
    tenant_lookup = "user__school"

    def get_queryset(self):
        user = self.request.user
        school = get_request_school(self.request)
        qs = Teacher.objects.select_related("user").prefetch_related(
            "subjects", "classes__level"
        )

        if school is not None:
            qs = qs.filter(user__school=school)
        elif not user.is_superadmin():
            return qs.none()

        if user.role_level >= 80:
            # Admin/superadmin sees all (can filter inactive via ?user__is_active=false)
            return qs
        # BUG FIX: For non-admins, only show teachers whose user account is active
        qs = qs.filter(user__is_active=True)
        if user.is_teacher():
            return qs.filter(user=user)
        elif user.is_parent():
            try:
                classes = [
                    ps.student.current_class
                    for ps in user.parent_profile.children_links
                    .select_related("student__current_class").all()
                    if ps.student.current_class
                ]
                return qs.filter(classes__in=classes).distinct()
            except Exception:
                return qs.none()
        elif user.is_student():
            try:
                cls = user.student_profile.current_class
                return qs.filter(classes=cls).distinct()
            except Exception:
                return qs.none()
        return qs.none()

    @action(detail=True, methods=["get"])
    def subjects(self, request, pk=None):
        """
        GET /api/teachers/{id}/subjects/
        Returns all subjects assigned to this teacher.
        FIX: This was missing — frontend needs it for dynamic subject display.
        """
        teacher = self.get_object()
        from apps.subjects.serializers import SubjectSerializer
        return Response(SubjectSerializer(teacher.subjects.all(), many=True).data)

    @action(detail=False, methods=["get"])
    def my_subjects(self, request):
        """
        GET /api/teachers/my_subjects/
        Returns subjects for the currently logged-in teacher.
        """
        try:
            teacher = request.user.teacher_profile
        except Exception:
            return Response({"error": "Profil enseignant introuvable."}, status=404)
        from apps.subjects.serializers import SubjectSerializer
        return Response(SubjectSerializer(teacher.subjects.all(), many=True).data)

    @action(detail=False, methods=["get"])
    def my_classes(self, request):
        """GET /api/teachers/my_classes/ — classes for logged-in teacher."""
        try:
            teacher = request.user.teacher_profile
        except Exception:
            return Response({"error": "Profil enseignant introuvable."}, status=404)
        from apps.classes.serializers import ClassSerializer
        return Response(ClassSerializer(teacher.classes.all(), many=True).data)

    @action(detail=True, methods=["get"])
    def schedule(self, request, pk=None):
        from apps.schedule.serializers import ClassScheduleSerializer
        teacher = self.get_object()
        schedules = teacher.schedules.select_related(
            "cls", "subject", "school_year"
        ).order_by("day_of_week", "start_time")
        return Response(ClassScheduleSerializer(schedules, many=True).data)

    @action(detail=True, methods=["get"])
    def students(self, request, pk=None):
        from apps.students.serializers import StudentSerializer
        from apps.students.models import Student
        teacher = self.get_object()
        students = Student.objects.filter(
            current_class__in=teacher.classes.all(), is_active=True
        ).select_related("current_class", "school_year").distinct()
        return Response(StudentSerializer(students, many=True).data)
