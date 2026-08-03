from feba_project.bulk_delete import BulkDeleteMixin
"""
Bulletins views — v29 (multi-tenant)

Corrections v29 :
  - generate_all() ne générait AUCUN filtre par établissement : un clic
    générait un bulletin pour TOUS les élèves de TOUS les tenants de la
    plateforme. Corrigé : scope systématique par établissement courant.
  - generate() / generate_class() : l'élève / l'année scolaire ciblés
    doivent appartenir au tenant courant (sinon 404).
  - Lien vers l'inscription annuelle (enrollment) lors de la génération.

Corrections v20 conservées :
  - generate() : supprime le bulletin existant avant régénération → plus de doublons
  - generate_class() / generate_all() : idem
  - Filtre par année active par défaut dans get_queryset
  - Gestion du bulletin annuel (agrège T1+T2+T3 via pdf_generator)
"""
import logging
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from apps.accounts.permissions import IsAdminOrAbove
from apps.core.tenancy import get_request_school, IsSameTenant
from .models import Bulletin
from .serializers import BulletinSerializer

logger = logging.getLogger("apps")


class BulletinViewSet(BulkDeleteMixin, viewsets.ModelViewSet):
    serializer_class   = BulletinSerializer
    permission_classes = [IsAuthenticated, IsSameTenant]
    filterset_fields   = ["student", "school_year", "period"]
    tenant_lookup = "student__school"

    def get_queryset(self):
        user = self.request.user
        school = get_request_school(self.request)
        qs   = Bulletin.objects.select_related("student__current_class", "school_year")

        # --- Isolation multi-tenant (FIX v29) -------------------------------
        if school is not None:
            qs = qs.filter(student__school=school)
        elif not user.is_superadmin():
            return qs.none()

        # Par défaut, filtrer sur l'année active (sauf si school_year est précisé dans les params)
        from apps.schools.models import SchoolYear
        school_year_param = self.request.query_params.get("school_year")
        if not school_year_param and self.request.query_params.get("all_years") != "1":
            from apps.core.tenancy import current_school_years
            active_years = current_school_years(school)
            if active_years.exists():
                qs = qs.filter(school_year__in=active_years)

        if user.role_level >= 80:
            return qs
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

    def get_permissions(self):
        if self.action in ["generate", "generate_class", "generate_all", "destroy"]:
            return [IsAuthenticated(), IsAdminOrAbove()]
        return [IsAuthenticated()]

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["request"] = self.request
        return ctx

    # ──────────────────────────────────────────────────────────────────────────

    @action(detail=False, methods=["post"])
    def generate(self, request):
        """POST /api/bulletins/generate/"""
        student_id     = request.data.get("student_id")
        period         = request.data.get("period")
        school_year_id = request.data.get("school_year_id")

        if not all([student_id, period, school_year_id]):
            return Response(
                {"error": "student_id, period et school_year_id sont requis."},
                status=400,
            )

        school = get_request_school(request)
        try:
            from apps.students.models import Student
            from apps.schools.models import SchoolYear
            from apps.students.services import get_or_create_enrollment
            from apps.bulletins.pdf_generator import generate_bulletin

            student_qs = Student.objects.all()
            year_qs = SchoolYear.objects.all()
            if school is not None:
                student_qs = student_qs.filter(school=school)
                year_qs = year_qs.filter(school=school)

            student = student_qs.get(pk=student_id)

            if not student.is_active or (student.user and not student.user.is_active):
                return Response(
                    {"error": "Impossible de générer un bulletin pour un élève désactivé."},
                    status=400,
                )

            school_year = year_qs.get(pk=school_year_id)

            # FIX: Supprimer l'ancien bulletin pour éviter les doublons (unique_together)
            Bulletin.objects.filter(
                student=student, school_year=school_year, period=period
            ).delete()

            # generate_bulletin gère lui-même ensure_zeros
            bulletin = generate_bulletin(student, period, school_year)
            enrollment, _ = get_or_create_enrollment(student, school_year.id)
            bulletin.enrollment = enrollment
            bulletin.save(update_fields=["enrollment"])

            url = bulletin.pdf_file.url if bulletin.pdf_file else None

            return Response(
                {**BulletinSerializer(bulletin, context={"request": request}).data,
                 "pdf_url": url},
                status=status.HTTP_201_CREATED,
            )

        except Exception as e:
            logger.error(f"Bulletin generation error: {e}", exc_info=True)
            return Response({"error": str(e)}, status=500)

    @action(detail=False, methods=["post"], url_path="generate-class")
    def generate_class(self, request):
        """POST /api/bulletins/generate-class/"""
        class_id       = request.data.get("class_id")
        period         = request.data.get("period")
        school_year_id = request.data.get("school_year_id")

        if not all([class_id, period, school_year_id]):
            return Response(
                {"error": "class_id, period et school_year_id requis."},
                status=400,
            )

        school = get_request_school(request)
        from apps.students.models import Student
        from apps.schools.models import SchoolYear
        from apps.students.services import get_or_create_enrollment
        from apps.bulletins.pdf_generator import generate_bulletin

        try:
            year_qs = SchoolYear.objects.all()
            if school is not None:
                year_qs = year_qs.filter(school=school)
            school_year = year_qs.get(pk=school_year_id)
        except SchoolYear.DoesNotExist:
            return Response({"error": "Année scolaire introuvable."}, status=404)

        students = Student.objects.filter(current_class_id=class_id, is_active=True)
        if school is not None:
            students = students.filter(school=school)
        elif not request.user.is_superadmin():
            students = students.none()
        ok, failed = 0, []

        for s in students:
            try:
                # FIX: Supprimer l'ancien bulletin avant régénération
                Bulletin.objects.filter(student=s, school_year=school_year, period=period).delete()
                bulletin = generate_bulletin(s, period, school_year)
                enrollment, _ = get_or_create_enrollment(s, school_year.id)
                bulletin.enrollment = enrollment
                bulletin.save(update_fields=["enrollment"])
                ok += 1
            except Exception as e:
                failed.append({"student": s.get_full_name(), "error": str(e)})
                logger.error(f"Bulletin class error {s.matricule}: {e}")

        return Response({
            "generated": ok,
            "failed":    len(failed),
            "errors":    failed,
            "detail":    f"{ok} bulletin(s) générés, {len(failed)} échec(s).",
        })

    @action(detail=False, methods=["post"], url_path="generate-all")
    def generate_all(self, request):
        """
        POST /api/bulletins/generate-all/
        FIX SÉCURITÉ CRITIQUE (v29) : avant cette version, cet endpoint
        générait un bulletin pour TOUS les élèves actifs de la PLATEFORME
        entière (toutes écoles confondues), faute de filtre par
        établissement. Désormais strictement limité au tenant courant.
        """
        period         = request.data.get("period")
        school_year_id = request.data.get("school_year_id")

        if not all([period, school_year_id]):
            return Response(
                {"error": "period et school_year_id requis."},
                status=400,
            )

        school = get_request_school(request)
        if school is None and not request.user.is_superadmin():
            return Response({"error": "Établissement introuvable pour ce compte."}, status=403)

        from apps.students.models import Student
        from apps.schools.models import SchoolYear
        from apps.students.services import get_or_create_enrollment
        from apps.bulletins.pdf_generator import generate_bulletin

        try:
            year_qs = SchoolYear.objects.all()
            if school is not None:
                year_qs = year_qs.filter(school=school)
            school_year = year_qs.get(pk=school_year_id)
        except SchoolYear.DoesNotExist:
            return Response({"error": "Année scolaire introuvable."}, status=404)

        students = Student.objects.filter(is_active=True, user__is_active=True)
        if school is not None:
            students = students.filter(school=school)
        # superadmin sans school_id explicite : refusé plus haut, jamais "toutes écoles"
        total = students.count()
        ok, failed = 0, []

        for s in students:
            try:
                # FIX: Supprimer l'ancien bulletin avant régénération
                Bulletin.objects.filter(student=s, school_year=school_year, period=period).delete()
                bulletin = generate_bulletin(s, period, school_year)
                enrollment, _ = get_or_create_enrollment(s, school_year.id)
                bulletin.enrollment = enrollment
                bulletin.save(update_fields=["enrollment"])
                ok += 1
            except Exception as e:
                failed.append({"student": s.get_full_name(), "error": str(e)})
                logger.error(f"Bulletin all error {s.matricule}: {e}")

        return Response({
            "generated": ok,
            "failed":    len(failed),
            "errors":    failed,
            "detail":    f"{ok} bulletin(s) générés sur {total} élèves actifs.",
        })
