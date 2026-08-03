import logging
logger = logging.getLogger("apps")
from feba_project.bulk_delete import BulkDeleteMixin
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from apps.core.tenancy import get_request_school, IsSameTenant
from .models import Attendance
from .serializers import AttendanceSerializer


class AttendanceViewSet(BulkDeleteMixin, viewsets.ModelViewSet):
    serializer_class = AttendanceSerializer
    permission_classes = [IsAuthenticated, IsSameTenant]
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    filterset_fields = ["student", "date", "status", "school_year"]
    tenant_lookup = "student__school"

    def get_queryset(self):
        user = self.request.user
        school = get_request_school(self.request)
        qs = Attendance.objects.select_related("student", "created_by", "school_year", "subject")

        # --- Isolation multi-tenant (FIX v29) -------------------------------
        if school is not None:
            qs = qs.filter(student__school=school)
        elif not user.is_superadmin():
            return qs.none()

        # FIX: Default to current active year if no school_year filter provided
        if not self.request.query_params.get("school_year") and self.request.query_params.get("all_years") != "1":
            # FIX v29 : scoper "année courante" par établissement (bug latent multi-tenant)
            # P2 : en mode consolidé, l'année courante de CHAQUE académie.
            from apps.core.tenancy import current_school_years
            current_years = current_school_years(school)
            if current_years.exists():
                qs = qs.filter(school_year__in=current_years)

        if user.role_level >= 80:
            return qs
        # BUG FIX: exclude attendance for inactive students
        qs = qs.filter(student__is_active=True, student__user__is_active=True)
        if user.is_teacher():
            try:
                return qs.filter(student__current_class__in=user.teacher_profile.classes.all())
            except Exception:
                return qs.none()
        elif user.is_parent():
            return qs.filter(student__parents__parent__user=user)
        elif user.is_student():
            try:
                return qs.filter(student__user=user)
            except Exception:
                return qs.none()
        return qs.none()

    def perform_create(self, serializer):
        # BUG FIX #2: Auto-assign school_year so records are never orphaned from the filter
        from apps.schools.models import SchoolYear
        from apps.students.services import get_or_create_enrollment

        school = get_request_school(self.request)
        school_year = serializer.validated_data.get("school_year")
        if not school_year:
            school_year = SchoolYear.objects.filter(school=school, is_current=True).first()

        student = serializer.validated_data.get("student")
        enrollment = None
        if student and school_year:
            enrollment, _ = get_or_create_enrollment(student, school_year.id)

        serializer.save(created_by=self.request.user, school_year=school_year, enrollment=enrollment)
        # Notify parent
        try:
            record = serializer.instance
            if record.status in ("absent", "late"):
                from apps.notifications.utils import create_notification, notification_path
                for ps in record.student.parents.select_related("parent__user").all():
                    create_notification(
                        ps.parent.user, "absence",
                        f"{record.student.get_full_name()} — {record.get_status_display()}",
                        f"Le {record.date} : {record.get_status_display()}",
                        related_url=notification_path(ps.parent.user, "attendance"),
                    )
                if record.student.user:
                    create_notification(
                        record.student.user, "absence",
                        f"{record.get_status_display()}",
                        f"Le {record.date} : {record.get_status_display()}",
                        related_url=notification_path(record.student.user, "attendance"),
                    )
        except Exception as exc:
            logger.warning("Erreur non bloquante ignorée : %s", exc, exc_info=True)
    @action(detail=False, methods=["post"])
    def bulk(self, request):
        # FIX SÉCURITÉ (v29) : chaque élève référencé dans le lot doit
        # appartenir au tenant courant — sinon un enregistrement de
        # présence pourrait être créé pour un élève d'un autre établissement.
        from apps.students.models import Student
        from apps.students.services import get_or_create_enrollment

        school = get_request_school(request)
        records = request.data.get("records", [])
        created = []
        errors = []
        for r in records:
            student_id = r.get("student")
            if school is not None and student_id:
                if not Student.objects.filter(pk=student_id, school=school).exists():
                    errors.append({"student": student_id, "error": "Élève introuvable dans cet établissement."})
                    continue

            s = AttendanceSerializer(data=r)
            if s.is_valid():
                save_kwargs = {"created_by": request.user}
                school_year = s.validated_data.get("school_year")
                student = s.validated_data.get("student")
                if student and school_year:
                    enrollment, _ = get_or_create_enrollment(student, school_year.id)
                    save_kwargs["enrollment"] = enrollment
                s.save(**save_kwargs)
                created.append(s.data)
            else:
                errors.append(s.errors)
        return Response({"created": len(created), "errors": errors, "records": created})

    @action(detail=False, methods=["get"])
    def stats(self, request):
        student_id = request.query_params.get("student")
        if not student_id:
            return Response({"error": "student requis"}, 400)
        qs = self.get_queryset().filter(student_id=student_id)
        return Response({
            "total": qs.count(),
            "present": qs.filter(status="present").count(),
            "absent": qs.filter(status="absent").count(),
            "late": qs.filter(status="late").count(),
            "excused": qs.filter(status="excused").count(),
        })
