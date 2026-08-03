import logging
logger = logging.getLogger("apps")
from feba_project.bulk_delete import BulkDeleteMixin
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from apps.accounts.permissions import IsAdminOrTeacher
from apps.core.tenancy import get_request_school, IsSameTenant
from .models import Homework, HomeworkAttachment
from .serializers import HomeworkSerializer


class HomeworkViewSet(BulkDeleteMixin, viewsets.ModelViewSet):
    serializer_class = HomeworkSerializer
    permission_classes = [IsAuthenticated, IsSameTenant]
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    filterset_fields = ["cls", "subject", "teacher", "school_year"]
    search_fields = ["title"]
    tenant_lookup = "cls__school_year__school"

    def get_queryset(self):
        user = self.request.user
        school = get_request_school(self.request)
        qs = Homework.objects.select_related(
            "subject", "teacher__user", "cls", "school_year"
        ).prefetch_related("attachments")

        # --- Isolation multi-tenant (FIX v29) -------------------------------
        if school is not None:
            qs = qs.filter(cls__school_year__school=school)
        elif not user.is_superadmin():
            return qs.none()

        # Filter by active year by default (unless school_year param or all_years=1 provided)
        if (
            not self.request.query_params.get("school_year")
            and self.request.query_params.get("all_years") != "1"
        ):
            from apps.core.tenancy import current_school_years
            active_years = current_school_years(school)
            if active_years.exists():
                qs = qs.filter(school_year__in=active_years)

        if user.role_level >= 80:
            return qs
        elif user.is_teacher():
            try:
                return qs.filter(teacher__user=user)
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
        elif user.is_student():
            try:
                return qs.filter(cls=user.student_profile.current_class)
            except Exception:
                return qs.none()
        return qs.none()

    def get_permissions(self):
        if self.action in ["create", "update", "partial_update", "destroy"]:
            return [IsAuthenticated(), IsAdminOrTeacher()]
        return super().get_permissions()

    def perform_create(self, serializer):
        teacher = None
        school_year = None
        if self.request.user.is_teacher():
            try:
                teacher = self.request.user.teacher_profile
            except Exception as exc:
                logger.warning("Erreur non bloquante ignorée : %s", exc, exc_info=True)
        # BUG FIX: Backend subject restriction for teachers
        if teacher:
            subject = serializer.validated_data.get("subject")
            if subject and not teacher.subjects.filter(id=subject.id).exists():
                from rest_framework.exceptions import PermissionDenied
                raise PermissionDenied(
                    f"Vous ne pouvez pas créer un devoir pour la matière '{subject.name}' "
                    "car elle ne fait pas partie de vos matières assignées."
                )
        if not self.request.data.get("school_year"):
            from apps.schools.models import SchoolYear
            school = get_request_school(self.request)
            school_year = SchoolYear.objects.filter(school=school, is_current=True).first()
        kwargs = {"teacher": teacher}
        if school_year:
            kwargs["school_year"] = school_year
        instance = serializer.save(**kwargs)
        files = self.request.FILES.getlist("attachments")
        for f in files:
            HomeworkAttachment.objects.create(homework=instance, file=f, name=f.name)

    def perform_update(self, serializer):
        instance = serializer.save()
        # Append any new attachments on edit
        files = self.request.FILES.getlist("attachments")
        for f in files:
            HomeworkAttachment.objects.create(homework=instance, file=f, name=f.name)

    @action(detail=True, methods=["delete"], url_path="attachments/(?P<att_id>[^/.]+)")
    def delete_attachment(self, request, pk=None, att_id=None):
        """DELETE /api/homework/{id}/attachments/{att_id}/"""
        try:
            att = HomeworkAttachment.objects.get(pk=att_id, homework_id=pk)
            att.file.delete(save=False)
            att.delete()
            return Response(status=204)
        except HomeworkAttachment.DoesNotExist:
            return Response({"error": "Pièce jointe introuvable."}, status=404)
