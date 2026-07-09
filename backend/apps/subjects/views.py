from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from apps.accounts.permissions import IsAdminOrReadOnly
from apps.core.tenancy import get_request_school, IsSameTenant
from .models import Subject
from .serializers import SubjectSerializer


class SubjectViewSet(viewsets.ModelViewSet):
    serializer_class = SubjectSerializer
    permission_classes = [IsAuthenticated, IsAdminOrReadOnly, IsSameTenant]
    filterset_fields = ["school", "level"]
    search_fields = ["name", "code"]
    tenant_lookup = "school"

    def get_queryset(self):
        school = get_request_school(self.request)
        qs = Subject.objects.select_related("school", "level")
        if school is not None:
            return qs.filter(school=school)
        if self.request.user.is_superadmin():
            return qs
        return qs.none()

    def perform_create(self, serializer):
        school = get_request_school(self.request)
        serializer.save(school=school or serializer.validated_data.get('school'))
