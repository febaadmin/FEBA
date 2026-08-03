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
import os

from django.db import transaction
from django.utils import timezone
from django.utils.decorators import method_decorator
from django_ratelimit.decorators import ratelimit
from rest_framework import generics, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsAdminOrAbove
from apps.core.tenancy import get_request_school
from .feba_prereg import (
    generate_and_store_prereg_sheet, process_submission,
)
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

        # P2 — La demande et son numéro de dossier sont écrits dans une
        # transaction. La fiche PDF est produite ENSUITE, hors
        # transaction : une erreur de mise en page ne doit pas annuler une
        # demande valide. Une famille qui a rempli le formulaire a déposé
        # sa demande, que le PDF sorte ou non.
        with transaction.atomic():
            prereg = serializer.save()

        outcome = process_submission(prereg)
        if not outcome["sheet_generated"]:
            # On ne le cache pas, mais on ne le fait pas peser sur la
            # famille non plus : sa demande est bien enregistrée. L'échec
            # part vers le super administrateur et l'écran d'administration.
            logger.error("Site vitrine — fiche non produite pour %s : %s",
                         prereg.reference, outcome["sheet_error"])

        logger.info("Site vitrine — préinscription %s reçue (#%d), fiche : %s",
                    prereg.reference, prereg.pk,
                    "produite" if outcome["sheet_generated"] else "en échec")
        return Response(
            {
                "detail": "Merci ! Votre demande de préinscription a bien été "
                          "enregistrée. Notre équipe vous contactera.",
                "reference": prereg.reference,
            },
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
    """
    Lecture + marquage lu + suppression (pas de création côté admin).

    MULTI-ENTITÉS : boîte de réception SÉPARÉE par entité. Un admin FEBA ne
    voit que les messages FEBA, un admin FEBA FHA que les messages FHA. Le
    filtrage est appliqué au queryset — un accès direct par identifiant
    renvoie donc 404 et non l'objet d'une autre entité.
    """
    permission_classes = [IsAuthenticated, IsAdminOrAbove]
    serializer_class = ContactMessageAdminSerializer
    http_method_names = ['get', 'patch', 'delete', 'head', 'options']

    def get_queryset(self):
        qs = ContactMessage.objects.select_related('entity').all()
        school = get_request_school(self.request)
        if school is not None:
            return qs.filter(entity=school)
        if self.request.user.is_superadmin():
            # Vue consolidée du superadmin : l'entité de chaque message est
            # exposée par le serializer (champ `entity`).
            entity_code = self.request.query_params.get('entity_code')
            if entity_code:
                return qs.filter(entity__code=entity_code)
            return qs
        return qs.none()


class AdminPreRegistrationViewSet(viewsets.ModelViewSet):
    """
    Lecture + changement de statut + suppression.

    MULTI-ENTITÉS : les préinscriptions FEBA restent visibles des seuls
    administrateurs FEBA. Les fiches FEBA FHA sont un modèle distinct
    (`FHAEnrollmentApplication`), exposé par son propre ViewSet.
    """
    permission_classes = [IsAuthenticated, IsAdminOrAbove]
    serializer_class = PreRegistrationAdminSerializer
    # `post` est nécessaire à l'action « régénérer la fiche ». Sans lui,
    # DRF répondait 405 et le bouton de l'écran était mort — l'action
    # existait, la route existait, et le clic ne faisait rien.
    http_method_names = ['get', 'post', 'patch', 'delete', 'head', 'options']

    def create(self, request, *args, **kwargs):
        """
        Créer une demande depuis le back-office reste INTERDIT.

        Ouvrir `post` pour l'action « régénérer » ouvre aussi, par
        construction, la création d'objets. Or une préinscription est une
        déclaration de la famille : une demande saisie par un
        administrateur ferait dire à une famille ce qu'elle n'a pas dit,
        avec un numéro de dossier officiel à l'appui.
        """
        from rest_framework.exceptions import MethodNotAllowed

        raise MethodNotAllowed(
            "POST",
            detail="Une préinscription est déposée par la famille depuis le "
                   "site public. Elle ne se crée pas depuis l'administration."
        )

    def get_permissions(self):
        """
        P2 — Les préinscriptions de ce ViewSet sont celles de FEBA
        (modèle `PreRegistration`). FEBA French Heritage Academy traite
        ses inscriptions dans `FHAEnrollmentApplication`.

        Masquer l'onglet côté React ne suffit pas : l'endpoint doit
        REFUSER un administrateur d'académie en ligne, sinon l'URL reste
        atteignable à la main.
        """
        return [permission() for permission in self.permission_classes]

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        from rest_framework.exceptions import PermissionDenied

        user = request.user
        # Le superadmin garde l'accès : en mode consolidé il consulte
        # légitimement les préinscriptions FEBA.
        if user.is_authenticated and not user.is_superadmin():
            academy = getattr(user, 'school', None)
            if academy is not None and academy.entity_type == 'online':
                raise PermissionDenied(
                    "Cette académie ne gère pas de préinscriptions FEBA. "
                    "Utilisez le module « Admissions FEBA FHA »."
                )

    def get_queryset(self):
        qs = PreRegistration.objects.select_related('entity').all()
        school = get_request_school(self.request)
        if school is not None:
            return qs.filter(entity=school)
        if self.request.user.is_superadmin():
            entity_code = self.request.query_params.get('entity_code')
            if entity_code:
                return qs.filter(entity__code=entity_code)
            return qs
        return qs.none()

    # ── Fiche PDF institutionnelle ───────────────────────────────────

    @action(detail=True, methods=['get'], url_path='sheet')
    def sheet(self, request, pk=None):
        """
        GET /api/website/admin/preregistrations/<id>/sheet/

        P2 — Le fichier NE PASSE JAMAIS par une URL publique. Il contient
        l'adresse, le téléphone et l'âge d'un mineur ; servi depuis
        `/media/`, il serait accessible à qui devine le chemin, et
        indexable. Il sort d'ici, authentifié, et `get_queryset()` a déjà
        restreint la portée à l'académie du demandeur — un identifiant
        d'une autre académie donne donc un 404, pas un 403 : révéler
        qu'un dossier existe ailleurs est déjà une fuite.
        """
        from django.http import FileResponse

        from .feba_prereg_pdf import sheet_filename

        demande = self.get_object()

        if not demande.has_sheet:
            # Fiche absente : on tente de la produire maintenant plutôt
            # que de renvoyer une erreur à un administrateur qui n'y peut
            # rien. Si la production échoue, on le DIT.
            if generate_and_store_prereg_sheet(demande) is None:
                return Response(
                    {"detail": "La fiche n'a pas pu être produite.",
                     "error": demande.sheet_error},
                    status=status.HTTP_503_SERVICE_UNAVAILABLE,
                )

        path = demande.sheet_absolute_path
        if not path or not os.path.exists(path):
            return Response(
                {"detail": "Le fichier de la fiche est introuvable sur le "
                           "serveur. Utilisez « Régénérer »."},
                status=status.HTTP_404_NOT_FOUND,
            )

        response = FileResponse(open(path, "rb"), content_type="application/pdf")
        response["Content-Disposition"] = (
            f'attachment; filename="{sheet_filename(demande)}"'
        )
        # Une pièce de dossier ne doit rester ni dans un cache partagé, ni
        # dans le cache disque du navigateur d'un poste mutualisé.
        response["Cache-Control"] = "private, no-store"
        logger.info("Préinscription — fiche %s téléchargée par %s",
                    demande.reference, request.user.email)
        return response

    @action(detail=True, methods=['post'], url_path='regenerate-sheet')
    def regenerate_sheet(self, request, pk=None):
        """Reconstruit la fiche à partir des données actuelles."""
        demande = self.get_object()
        if generate_and_store_prereg_sheet(demande) is None:
            return Response(
                {"detail": "La fiche n'a pas pu être produite.",
                 "error": demande.sheet_error},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        logger.info("Préinscription — fiche %s régénérée par %s",
                    demande.reference, request.user.email)
        return Response(PreRegistrationAdminSerializer(demande).data)

    @action(detail=False, methods=['get'], url_path='export')
    def export(self, request):
        """
        Export CSV de TOUTES les colonnes du modèle.

        L'export est construit à partir des champs réels du modèle, pas
        d'une liste écrite à la main : une liste manuelle oublie la
        colonne ajoutée la semaine suivante, et l'export paraît complet.
        """
        import csv
        from django.http import HttpResponse

        rows = self.filter_queryset(self.get_queryset())
        colonnes = _prereg_export_columns()

        response = HttpResponse(content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = (
            'attachment; filename="preinscriptions-feba.csv"'
        )
        # BOM UTF-8 : sans lui, Excel affiche « Ã© » à la place de « é ».
        response.write("\ufeff")
        writer = csv.writer(response, delimiter=";")
        writer.writerow([label for label, _ in colonnes])
        for demande in rows:
            writer.writerow([_prereg_export_value(demande, key)
                             for _, key in colonnes])
        logger.info("Préinscriptions — export CSV (%d lignes) par %s",
                    rows.count(), request.user.email)
        return response


#: Colonnes de l'export. Les champs techniques du stockage privé sont
#: exclus : un chemin de fichier serveur dans un tableur diffusé n'aide
#: personne et renseigne un attaquant.
_PREREG_EXPORT_EXCLUDED = {"id", "sheet_path", "sheet_sha256"}

#: Intitulés français des colonnes.
#:
#: DÉFAUT TROUVÉ EN OUVRANT LE FICHIER PRODUIT — pas en lisant le code.
#: L'export dérivait ses intitulés de `field.verbose_name`, que Django
#: fabrique à partir du NOM DE L'ATTRIBUT quand on ne lui en donne pas.
#: Le secrétariat recevait donc un tableau titré « Address », « Phone
#: secondary », « Child birth date » — dans un établissement dont toute
#: l'administration travaille en français.
#:
#: Le test qui prétendait couvrir ce point comparait l'en-tête produit à
#: `field.verbose_name.capitalize()` : c'est-à-dire à lui-même. Il
#: passait sans rien prouver. Les intitulés sont désormais écrits, et le
#: test cite les chaînes attendues.
_PREREG_EXPORT_LABELS = {
    "reference": "Numéro de dossier",
    "parent_name": "Nom du parent",
    "phone": "Téléphone principal",
    "phone_secondary": "Téléphone secondaire",
    "whatsapp": "WhatsApp",
    "email": "Adresse électronique",
    "address": "Adresse du domicile",
    "child_name": "Nom de l'enfant",
    "child_age": "Âge déclaré",
    "child_birth_date": "Date de naissance",
    "desired_level": "Niveau demandé",
    "school_year": "Année scolaire souhaitée",
    "message": "Message de la famille",
    "status": "Statut",
    "created_at": "Reçue le",
    "sheet_generated_at": "Fiche produite le",
    "sheet_error": "Dernier échec de production",
}


def _prereg_export_columns():
    from .models import PreRegistration

    colonnes = [("Académie", "__academy__")]
    for field in PreRegistration._meta.fields:
        if field.name in _PREREG_EXPORT_EXCLUDED or field.name == "entity":
            continue
        colonnes.append((_PREREG_EXPORT_LABELS[field.name], field.name))
    colonnes.append(("Fiche PDF produite", "__has_sheet__"))
    return colonnes


def _prereg_export_value(demande, key):
    if key == "__academy__":
        return demande.entity.name if demande.entity else ""
    if key == "__has_sheet__":
        return "oui" if demande.has_sheet else "non"
    value = getattr(demande, key, "")
    display = getattr(demande, f"get_{key}_display", None)
    if display is not None:
        value = display()
    if value is None:
        return ""
    if hasattr(value, "strftime"):
        return value.strftime("%d/%m/%Y %H:%M") if hasattr(value, "hour") \
            else value.strftime("%d/%m/%Y")
    return str(value)
