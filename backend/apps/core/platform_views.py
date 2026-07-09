"""
apps/core/platform_views.py — Gestion de la plateforme SaaS

Vues réservées au rôle `superadmin` (rôle transverse, non rattaché à un
établissement), permettant la gestion du cycle de vie des établissements
clients :
  - création d'un nouveau tenant
  - liste et recherche de tous les tenants
  - suspension / réactivation
  - changement de plan / quota
  - statistiques d'utilisation par tenant

Ces vues ne sont JAMAIS accessibles à un `admin` d'établissement :
  - `IsSuperAdmin` est vérifié sur chaque action
  - Le queryset n'est pas scopé par un tenant (c'est précisément le but
    de cette "vue plateforme" — le superadmin gère les tenants eux-mêmes)
"""
from rest_framework import generics, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework import serializers
from django.db.models import Count, Sum
from apps.accounts.permissions import IsSuperAdmin
from apps.schools.models import School
from apps.schools.serializers import SchoolPlatformSerializer


class TenantListCreateView(generics.ListCreateAPIView):
    """
    GET  /api/platform/schools/       — Liste tous les tenants (superadmin)
    POST /api/platform/schools/       — Crée un nouveau tenant (établissement client)
    """
    serializer_class = SchoolPlatformSerializer
    permission_classes = [IsAuthenticated, IsSuperAdmin]

    def get_queryset(self):
        qs = School.objects.annotate(
            student_count=Count('students', distinct=True),
            user_count=Count('users', distinct=True),
        ).order_by('name')
        name = self.request.query_params.get('search')
        if name:
            qs = qs.filter(name__icontains=name)
        is_active = self.request.query_params.get('is_active')
        if is_active is not None:
            qs = qs.filter(is_active=is_active in ('true', '1', 'True'))
        plan = self.request.query_params.get('plan')
        if plan:
            qs = qs.filter(plan=plan)
        return qs

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx['request'] = self.request
        return ctx


class TenantDetailView(generics.RetrieveUpdateAPIView):
    """
    GET   /api/platform/schools/{slug}/  — Détails d'un tenant
    PATCH /api/platform/schools/{slug}/  — Modifier plan/quota/statut/notes
    """
    serializer_class = SchoolPlatformSerializer
    permission_classes = [IsAuthenticated, IsSuperAdmin]
    lookup_field = 'slug'
    queryset = School.objects.all()

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx['request'] = self.request
        return ctx


class TenantSuspendView(APIView):
    """
    POST /api/platform/schools/{slug}/suspend/
    Body: { "reason"?: str }
    Suspend a tenant. All users of this school will be blocked at login.
    """
    permission_classes = [IsAuthenticated, IsSuperAdmin]

    def post(self, request, slug):
        school = School.objects.filter(slug=slug).first()
        if not school:
            return Response({'error': 'Établissement introuvable.'}, status=404)
        if not school.is_active:
            return Response({'error': 'Cet établissement est déjà suspendu.'}, status=400)
        school.is_active = False
        reason = request.data.get('reason', '')
        if reason:
            school.subscription_notes = f"[SUSPENDU par {request.user.email}]: {reason}\n{school.subscription_notes}"
        school.save(update_fields=['is_active', 'subscription_notes'])
        return Response({
            'detail': f'Établissement "{school.name}" suspendu.',
            'school': SchoolPlatformSerializer(school, context={'request': request}).data,
        })


class TenantReactivateView(APIView):
    """
    POST /api/platform/schools/{slug}/reactivate/
    Reactivate a suspended tenant.
    """
    permission_classes = [IsAuthenticated, IsSuperAdmin]

    def post(self, request, slug):
        school = School.objects.filter(slug=slug).first()
        if not school:
            return Response({'error': 'Établissement introuvable.'}, status=404)
        if school.is_active:
            return Response({'error': 'Cet établissement est déjà actif.'}, status=400)
        school.is_active = True
        school.subscription_notes = (
            f"[RÉACTIVÉ par {request.user.email}]\n{school.subscription_notes}"
        )
        school.save(update_fields=['is_active', 'subscription_notes'])
        return Response({
            'detail': f'Établissement "{school.name}" réactivé.',
            'school': SchoolPlatformSerializer(school, context={'request': request}).data,
        })


class PlatformStatsView(APIView):
    """
    GET /api/platform/stats/
    Tableau de bord plateforme global (superadmin uniquement).
    """
    permission_classes = [IsAuthenticated, IsSuperAdmin]

    def get(self, request):
        from apps.students.models import Student
        from apps.accounts.models import CustomUser

        total_schools = School.objects.count()
        active_schools = School.objects.filter(is_active=True).count()
        total_students = Student.objects.filter(is_active=True).count()
        total_users = CustomUser.objects.filter(is_active=True).count()

        by_plan = {}
        for plan, label in School.PLAN_CHOICES:
            by_plan[plan] = {
                'label': label,
                'count': School.objects.filter(plan=plan).count(),
            }

        top_schools = School.objects.annotate(
            sc=Count('students')
        ).order_by('-sc')[:10].values('name', 'slug', 'plan', 'is_active', 'sc')

        return Response({
            'total_schools': total_schools,
            'active_schools': active_schools,
            'suspended_schools': total_schools - active_schools,
            'total_students': total_students,
            'total_users': total_users,
            'by_plan': by_plan,
            'top_schools_by_students': list(top_schools),
        })
