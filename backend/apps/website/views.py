"""
API du site vitrine public (P4 v4).

Deux familles d'endpoints :
- PUBLICS (AllowAny) : lecture seule du contenu + dépôt des deux formulaires.
  Les POST sont limités par IP (django-ratelimit) et protégés par honeypot.
  L'API publique n'expose JAMAIS les soumissions reçues.
- ADMIN (IsAdminOrAbove) : CRUD complet du contenu, consultation des messages
  et des demandes de préinscription.
"""
import logging

from django.utils import timezone
from django.utils.decorators import method_decorator
from django_ratelimit.decorators import ratelimit
from rest_framework import generics, status, viewsets
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsAdminOrAbove
from .models import (
    SiteSettings, HeroSlide, NewsPost, GalleryAlbum, GalleryItem,
    ContactMessage, PreRegistration,
)
from .serializers import (
    SiteSettingsPublicSerializer, HeroSlideSerializer,
    NewsPostListSerializer, NewsPostDetailSerializer, GalleryAlbumSerializer,
    ContactMessageCreateSerializer, PreRegistrationCreateSerializer,
    SiteSettingsAdminSerializer, NewsPostAdminSerializer,
    GalleryAlbumAdminSerializer, GalleryItemAdminSerializer,
    ContactMessageAdminSerializer, PreRegistrationAdminSerializer,
)

logger = logging.getLogger("apps")


# ── Endpoints publics (lecture) ────────────────────────────────────────────────

class PublicSettingsView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        return Response(SiteSettingsPublicSerializer(SiteSettings.load()).data)


class PublicHeroSlidesView(generics.ListAPIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    serializer_class = HeroSlideSerializer
    pagination_class = None
    queryset = HeroSlide.objects.filter(is_active=True)


class PublicNewsListView(generics.ListAPIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    serializer_class = NewsPostListSerializer

    def get_queryset(self):
        qs = NewsPost.objects.filter(is_published=True)
        kind = self.request.query_params.get('kind')
        if kind in ('news', 'event'):
            qs = qs.filter(kind=kind)
        return qs


class PublicNewsDetailView(generics.RetrieveAPIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    serializer_class = NewsPostDetailSerializer
    lookup_field = 'slug'
    queryset = NewsPost.objects.filter(is_published=True)


class PublicGalleryView(generics.ListAPIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    serializer_class = GalleryAlbumSerializer
    pagination_class = None
    queryset = GalleryAlbum.objects.filter(is_active=True)


# ── Formulaires publics (écriture, anti-spam) ─────────────────────────────────

class ContactMessageCreateView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    @method_decorator(ratelimit(key="ip", rate="5/m", method="POST", block=True))
    def post(self, request):
        serializer = ContactMessageCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        msg = serializer.save()
        logger.info("Site vitrine — message de contact reçu (#%d)", msg.pk)
        return Response(
            {"detail": "Merci ! Votre message a bien été envoyé. Nous vous répondrons rapidement."},
            status=status.HTTP_201_CREATED,
        )


class PreRegistrationCreateView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    @method_decorator(ratelimit(key="ip", rate="5/m", method="POST", block=True))
    def post(self, request):
        serializer = PreRegistrationCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        prereg = serializer.save()
        logger.info("Site vitrine — préinscription reçue (#%d)", prereg.pk)
        return Response(
            {"detail": "Merci ! Votre demande de préinscription a bien été enregistrée. Notre équipe vous contactera."},
            status=status.HTTP_201_CREATED,
        )


# ── Administration du contenu ─────────────────────────────────────────────────

class AdminSiteSettingsView(APIView):
    permission_classes = [IsAuthenticated, IsAdminOrAbove]

    def get(self, request):
        return Response(SiteSettingsAdminSerializer(SiteSettings.load()).data)

    def patch(self, request):
        obj = SiteSettings.load()
        serializer = SiteSettingsAdminSerializer(obj, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        logger.info("Site vitrine — paramètres modifiés par %s", request.user.email)
        return Response(serializer.data)


class AdminHeroSlideViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, IsAdminOrAbove]
    serializer_class = HeroSlideSerializer
    queryset = HeroSlide.objects.all()
    pagination_class = None


class AdminNewsViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, IsAdminOrAbove]
    serializer_class = NewsPostAdminSerializer
    queryset = NewsPost.objects.all()


class AdminGalleryAlbumViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, IsAdminOrAbove]
    serializer_class = GalleryAlbumAdminSerializer
    queryset = GalleryAlbum.objects.all()
    pagination_class = None


class AdminGalleryItemViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, IsAdminOrAbove]
    serializer_class = GalleryItemAdminSerializer
    queryset = GalleryItem.objects.all()
    pagination_class = None


class AdminContactMessageViewSet(viewsets.ModelViewSet):
    """Lecture + marquage lu + suppression (pas de création côté admin)."""
    permission_classes = [IsAuthenticated, IsAdminOrAbove]
    serializer_class = ContactMessageAdminSerializer
    queryset = ContactMessage.objects.all()
    http_method_names = ['get', 'patch', 'delete', 'head', 'options']


class AdminPreRegistrationViewSet(viewsets.ModelViewSet):
    """Lecture + changement de statut + suppression."""
    permission_classes = [IsAuthenticated, IsAdminOrAbove]
    serializer_class = PreRegistrationAdminSerializer
    queryset = PreRegistration.objects.all()
    http_method_names = ['get', 'patch', 'delete', 'head', 'options']
