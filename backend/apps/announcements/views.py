from feba_project.bulk_delete import BulkDeleteMixin
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from apps.accounts.permissions import IsAdminOrAbove
from apps.core.tenancy import get_request_school, IsSameTenant
from .models import Announcement
from .serializers import AnnouncementSerializer


class AnnouncementViewSet(BulkDeleteMixin, viewsets.ModelViewSet):
    serializer_class = AnnouncementSerializer
    permission_classes = [IsAuthenticated, IsSameTenant]
    search_fields = ["title", "content"]
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    tenant_lookup = "author__school"

    def get_queryset(self):
        user = self.request.user
        school = get_request_school(self.request)
        qs = Announcement.objects.select_related("author")
        school_year_id = self.request.query_params.get("school_year")
        all_years = self.request.query_params.get("all_years") == "1"

        # --- Isolation multi-tenant (FIX v29) -------------------------------
        # FIX SÉCURITÉ : "role_level >= 80 → return qs" exposait les
        # annonces de TOUS les établissements à n'importe quel admin.
        if school is not None:
            qs = qs.filter(author__school=school)
        elif not user.is_superadmin():
            return qs.none()

        if user.role_level >= 80:
            if school_year_id:
                qs = qs.filter(school_year_id=school_year_id)
            elif not all_years:
                from apps.schools.models import SchoolYear
                active = SchoolYear.objects.filter(school=school, is_current=True).first()
                if active:
                    qs = qs.filter(school_year=active)
            return qs.order_by("-created_at")

        # Non-admin: published announcements targeted to this role
        qs = qs.filter(is_published=True)
        role = user.role
        from .utils import filter_targets_role
        qs = filter_targets_role(qs, role)
        if school_year_id:
            qs = qs.filter(school_year_id=school_year_id)
        elif not all_years:
            from apps.schools.models import SchoolYear
            active = SchoolYear.objects.filter(school=school, is_current=True).first()
            if active:
                qs = qs.filter(school_year=active)
        return qs.order_by("-created_at")

    def get_permissions(self):
        if self.action in ["create", "update", "partial_update", "destroy"]:
            return [IsAuthenticated(), IsAdminOrAbove()]
        return [IsAuthenticated()]

    def perform_create(self, serializer):
        from apps.schools.models import SchoolYear
        school = get_request_school(self.request)
        school_year = serializer.validated_data.get("school_year")
        if not school_year:
            school_year = SchoolYear.objects.filter(school=school, is_current=True).first()

        # Store original filename
        attachment = self.request.FILES.get("attachment")
        kwargs = {"author": self.request.user}
        if school_year:
            kwargs["school_year"] = school_year
        if attachment:
            kwargs["attachment_name"] = attachment.name
        # Handle target_roles sent as JSON string (from FormData)
        target_roles = self.request.data.get("target_roles")
        if isinstance(target_roles, str):
            import json
            try:
                kwargs["target_roles"] = json.loads(target_roles)
            except (json.JSONDecodeError, TypeError):
                kwargs["target_roles"] = [target_roles] if target_roles else ["all"]
        serializer.save(**kwargs)

    def perform_update(self, serializer):
        attachment = self.request.FILES.get("attachment")
        kwargs = {}
        if attachment:
            kwargs["attachment_name"] = attachment.name
        target_roles = self.request.data.get("target_roles")
        if isinstance(target_roles, str):
            import json
            try:
                kwargs["target_roles"] = json.loads(target_roles)
            except (json.JSONDecodeError, TypeError):
                kwargs["target_roles"] = [target_roles] if target_roles else ["all"]
        serializer.save(**kwargs)
