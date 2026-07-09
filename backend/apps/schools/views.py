from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from apps.accounts.permissions import IsAdminOrAbove, IsSuperAdmin
from apps.core.tenancy import get_request_school
from .models import School, SchoolYear, Level, Room, RoomType, SchoolBranding
from .serializers import (
    SchoolSerializer, SchoolPlatformSerializer, SchoolYearSerializer, LevelSerializer,
    RoomSerializer, RoomTypeSerializer, SchoolBrandingSerializer
)


class SchoolViewSet(viewsets.ModelViewSet):
    """
    FIX SÉCURITÉ CRITIQUE (v29) : avant cette version, n'importe quel
    utilisateur authentifié (y compris un parent ou un élève) pouvait
    lister TOUS les établissements de la plateforme via GET /api/schools/,
    quel que soit son propre établissement. Avec l'arrivée du multi-
    tenant, ceci exposerait les données commerciales (plan, quota,
    notes internes) de TOUS les clients SaaS à n'importe quel compte.

    Comportement désormais :
      - superadmin (rôle plateforme) : voit tous les établissements,
        peut en créer/suspendre/modifier le plan (vue "gestion clients").
      - tout autre rôle : ne voit QUE son propre établissement (lecture,
        et écriture limitée aux champs non-commerciaux via SchoolSerializer).
    """
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.request.user.is_authenticated and self.request.user.is_superadmin():
            return SchoolPlatformSerializer
        return SchoolSerializer

    def get_queryset(self):
        user = self.request.user
        if user.is_superadmin():
            return School.objects.all().order_by('name')
        if user.school_id is None:
            return School.objects.none()
        return School.objects.filter(id=user.school_id)

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx['request'] = self.request
        return ctx

    def get_permissions(self):
        if self.action == 'create':
            # Seul un superadmin crée un nouvel établissement (= nouveau client SaaS)
            return [IsAuthenticated(), IsSuperAdmin()]
        if self.action in ['update', 'partial_update']:
            # L'admin de l'école peut modifier SON établissement (champs non-commerciaux,
            # cf. read_only_fields de SchoolSerializer) ; le superadmin peut tout modifier.
            return [IsAuthenticated(), IsAdminOrAbove()]
        if self.action == 'destroy':
            return [IsAuthenticated(), IsSuperAdmin()]
        return [IsAuthenticated()]


class SchoolYearViewSet(viewsets.ModelViewSet):
    serializer_class = SchoolYearSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        school = get_request_school(self.request)
        qs = SchoolYear.objects.select_related('school').all()
        if school is not None:
            return qs.filter(school=school)
        if self.request.user.is_superadmin():
            return qs  # vue plateforme volontaire
        return qs.none()

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy', 'set_current', 'close']:
            return [IsAuthenticated(), IsAdminOrAbove()]
        return [IsAuthenticated()]

    def _resolve_school(self, serializer):
        """
        FIX v32 (cause racine de l'IntegrityError school_id NOT NULL) :
        un superadmin n'a pas d'établissement propre → get_request_school()
        renvoyait None et serializer.save(school=None) violait la contrainte
        de base. Résolution : établissement de l'utilisateur, sinon celui du
        payload, sinon — cas mono-établissement — l'unique établissement.
        """
        from rest_framework.exceptions import ValidationError
        school = get_request_school(self.request)
        if school is None:
            school = serializer.validated_data.get('school')
        if school is None and self.request.user.is_superadmin():
            schools = list(School.objects.all()[:2])
            if len(schools) == 1:
                school = schools[0]
        if school is None:
            raise ValidationError({
                'school': "Précisez l'établissement de cette année scolaire.",
            })
        return school

    def perform_create(self, serializer):
        school = self._resolve_school(serializer)
        from django.db import transaction
        with transaction.atomic():
            # Le save() du modèle désactive déjà les autres années actives
            # avant l'insertion (ordre requis par la contrainte partielle).
            instance = serializer.save(school=school)

    def perform_update(self, serializer):
        instance = serializer.save()
        if instance.is_current:
            SchoolYear.objects.filter(school=instance.school, is_current=True).exclude(pk=instance.pk).update(is_current=False)

    @action(detail=True, methods=['post'])
    def set_current(self, request, pk=None):
        from django.db import transaction
        year = self.get_object()
        # FIX v39 : opérations atomiques — on désactive les autres années PUIS
        # on active celle-ci, dans une seule transaction, pour respecter la
        # contrainte « une seule année active par établissement ».
        with transaction.atomic():
            SchoolYear.objects.filter(
                school=year.school, is_current=True
            ).exclude(pk=year.pk).update(is_current=False)
            if not year.is_current:
                year.is_current = True
                year.save(update_fields=['is_current'])
        return Response({'detail': f'{year.name} définie comme année active.'})

    @action(detail=True, methods=['post'])
    def close(self, request, pk=None):
        """Clôture l'année (elle n'est plus l'année active)."""
        year = self.get_object()
        if not year.is_current:
            return Response({'detail': f"{year.name} n'est pas l'année active."})
        year.is_current = False
        year.save(update_fields=['is_current'])
        return Response({'detail': f'{year.name} clôturée. Activez la nouvelle année via "Définir comme active".'})


class LevelViewSet(viewsets.ModelViewSet):
    serializer_class = LevelSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        school = get_request_school(self.request)
        qs = Level.objects.select_related('school').all()
        if school is not None:
            return qs.filter(school=school)
        if self.request.user.is_superadmin():
            # Superadmin : autorisé à cibler un établissement précis via ?school=
            requested = self.request.query_params.get('school')
            return qs.filter(school=requested) if requested else qs
        return qs.none()

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAuthenticated(), IsAdminOrAbove()]
        return [IsAuthenticated()]

    def perform_create(self, serializer):
        school = get_request_school(self.request)
        serializer.save(school=school or serializer.validated_data.get('school'))


class RoomTypeViewSet(viewsets.ModelViewSet):
    serializer_class = RoomTypeSerializer
    permission_classes = [IsAuthenticated, IsAdminOrAbove]

    def get_queryset(self):
        school = get_request_school(self.request)
        qs = RoomType.objects.all()
        if school is not None:
            return qs.filter(school=school)
        if self.request.user.is_superadmin():
            requested = self.request.query_params.get('school')
            return qs.filter(school=requested) if requested else qs
        return qs.none()

    def perform_create(self, serializer):
        school = get_request_school(self.request)
        serializer.save(school=school or serializer.validated_data.get('school'))


class RoomViewSet(viewsets.ModelViewSet):
    serializer_class = RoomSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        school = get_request_school(self.request)
        qs = Room.objects.all()
        if school is not None:
            return qs.filter(school=school)
        if self.request.user.is_superadmin():
            requested = self.request.query_params.get('school')
            return qs.filter(school=requested) if requested else qs
        return qs.none()

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAuthenticated(), IsAdminOrAbove()]
        return [IsAuthenticated()]

    def perform_create(self, serializer):
        school = get_request_school(self.request)
        serializer.save(school=school or serializer.validated_data.get('school'))


class SchoolBrandingViewSet(viewsets.ModelViewSet):
    """
    Gestion centralisée du branding/logo de l'école.
    GET /api/schools/branding/ — liste les versions DE SON établissement (admin+)
    POST /api/schools/branding/ — upload nouveau logo (admin+)
    POST /api/schools/branding/{id}/activate/ — activer cette version (admin+)
    GET /api/schools/branding/active/ — version active DE SON établissement
        (tous utilisateurs authentifiés du même établissement)

    FIX SÉCURITÉ (v29) : ?school=<id> n'est plus honoré pour un compte
    non-superadmin — avant cette version, n'importe quel utilisateur
    pouvait passer l'ID d'un AUTRE établissement pour voir son logo/branding.
    """
    serializer_class = SchoolBrandingSerializer
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_permissions(self):
        read_only_actions = ['active', 'retrieve', 'list']
        if self.action in read_only_actions:
            return [IsAuthenticated()]
        return [IsAuthenticated(), IsAdminOrAbove()]

    def get_queryset(self):
        school = get_request_school(self.request)
        qs = SchoolBranding.objects.select_related('school', 'uploaded_by')
        if school is not None:
            return qs.filter(school=school)
        if self.request.user.is_superadmin():
            requested = self.request.query_params.get('school')
            return qs.filter(school_id=requested) if requested else qs
        return qs.none()

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx['request'] = self.request
        return ctx

    def perform_create(self, serializer):
        school = get_request_school(self.request)
        branding = serializer.save(uploaded_by=self.request.user, school=school or serializer.validated_data.get('school'))
        activate = self.request.data.get('activate', True)
        if activate and str(activate).lower() not in ('false', '0', 'no'):
            branding.activate()

    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        branding = self.get_object()
        branding.activate()
        return Response({
            'detail': 'Logo activé avec succès. Propagé dans toute l\'application.',
            'branding': SchoolBrandingSerializer(branding, context={'request': request}).data,
        })

    @action(detail=False, methods=['get'])
    def active(self, request):
        school = get_request_school(request)
        qs = SchoolBranding.objects.filter(is_active=True)
        if school is not None:
            qs = qs.filter(school=school)
        elif request.user.is_superadmin():
            school_id = request.query_params.get('school')
            if school_id:
                qs = qs.filter(school_id=school_id)
                school = School.objects.filter(pk=school_id).first()
        else:
            qs = qs.none()

        branding = qs.first()
        if not branding:
            return Response({
                'id': None,
                'logo_url': school.get_active_logo_url(request) if school else None,
                'is_active': True,
                'label': 'Logo école (par défaut)',
            })
        return Response(SchoolBrandingSerializer(branding, context={'request': request}).data)
