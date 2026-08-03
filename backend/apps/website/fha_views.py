"""
apps/website/fha_views.py — Endpoints publics et administratifs FEBA FHA

SÉPARATION DES FORMULAIRES
--------------------------
  /api/website/public/contact/          → contact FEBA      (entité FEBA)
  /api/website/public/fha/contact/      → contact FEBA FHA  (entité FEBA_FHA)
  /api/website/public/preregistration/  → préinscription FEBA
  /api/website/public/fha/enroll/       → fiche FEBA FHA

L'entité est déduite de la ROUTE et fixée côté serveur. Les boîtes de
réception administratives sont filtrées par entité : un admin FEBA ne voit
jamais un message FHA, et réciproquement.
"""
import logging

from django.utils import timezone
from django.utils.decorators import method_decorator
from django_ratelimit.decorators import ratelimit
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsAdminOrAbove
from apps.core.tenancy import get_request_school

from .fha_serializers import (
    FHAApplicationDetailSerializer, FHAApplicationListSerializer,
    FHAContactMessageCreateSerializer, FHAEnrollmentCreateSerializer,
    get_fha_entity,
)
from .models import (
    ContactMessage, FHAApplicationStatusHistory, FHAEnrollmentApplication,
)

logger = logging.getLogger("apps")


# ── Endpoints publics FEBA FHA ────────────────────────────────────────────────

class FHAContactCreateView(APIView):
    """
    POST /api/website/public/fha/contact/

    Formulaire de contact FEBA FHA. L'entité est FEBA_FHA par construction.
    """
    permission_classes = [AllowAny]
    authentication_classes = []

    @method_decorator(ratelimit(key="ip", rate="5/m", method="POST", block=True))
    def post(self, request):
        serializer = FHAContactMessageCreateSerializer(
            data=request.data, context={'request': request},
        )
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        msg = serializer.save()
        logger.info("FEBA FHA — message de contact reçu (#%d, catégorie %s)",
                    msg.pk, msg.category)
        return Response(
            {
                "detail": (
                    "Merci ! Votre message a bien été envoyé à FEBA French "
                    "Heritage Academy. Notre équipe vous répondra rapidement."
                ),
                "detail_en": (
                    "Thank you! Your message has been sent to FEBA French "
                    "Heritage Academy. Our team will reply shortly."
                ),
            },
            status=status.HTTP_201_CREATED,
        )


class FHAEnrollmentCreateView(APIView):
    """
    POST /api/website/public/fha/enroll/

    Fiche de renseignements FEBA FHA (12 étapes). Accepte le multipart
    (photo facultative de l'enfant) comme le JSON.
    """
    permission_classes = [AllowAny]
    authentication_classes = []

    @method_decorator(ratelimit(key="ip", rate="5/m", method="POST", block=True))
    def post(self, request):
        from .fha_enrollment import create_application, process_submission

        serializer = FHAEnrollmentCreateSerializer(
            data=request.data, context={'request': request},
        )
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        # ÉTAPE ATOMIQUE : numéro, champs, consentements, historique. Si
        # quoi que ce soit échoue ici, rien n'est écrit — une fiche à
        # moitié enregistrée est un dossier qu'on croira complet.
        application = create_application(serializer)

        logger.info(
            "FEBA FHA — fiche d'inscription enregistrée (dossier %s, groupe "
            "suggéré %s)",
            application.reference, application.suggested_group or "à déterminer",
        )

        # ÉTAPES HORS TRANSACTION : PDF, notifications, accusé de réception.
        # Un serveur SMTP injoignable ne doit pas faire perdre une
        # inscription déjà validée.
        outcome = process_submission(application)

        # L'ÉCRAN NE PROMET QUE CE QUI S'EST PRODUIT.
        #
        # « Vous recevrez un e-mail de confirmation » s'affichait avant même
        # que la couche d'envoi ait répondu. Le numéro de dossier, lui, est
        # acquis : c'est lui qu'on met en avant, et l'e-mail n'est annoncé
        # que si le fournisseur l'a accepté.
        reference = application.reference
        if outcome["parent_email_accepted"]:
            detail = (
                f"Merci ! Votre fiche est enregistrée sous le numéro de "
                f"dossier {reference}. Un e-mail de confirmation vient de "
                f"vous être envoyé à {application.parent1_email}."
            )
            detail_en = (
                f"Thank you! Your form is registered under file number "
                f"{reference}. A confirmation e-mail has just been sent to "
                f"{application.parent1_email}."
            )
        else:
            detail = (
                f"Merci ! Votre fiche est enregistrée sous le numéro de "
                f"dossier {reference}. Notez-le : l'envoi de l'e-mail de "
                f"confirmation n'a pas pu être effectué pour l'instant, "
                f"notre équipe a été prévenue et vous recontactera."
            )
            detail_en = (
                f"Thank you! Your form is registered under file number "
                f"{reference}. Please note it down: the confirmation e-mail "
                f"could not be sent for now. Our team has been alerted and "
                f"will get back to you."
            )

        return Response(
            {
                "detail": detail,
                "detail_en": detail_en,
                "reference": reference,
                "status": application.status,
                "child_age": application.child_age,
                "suggested_group": application.suggested_group,
                # État RÉEL de l'envoi, exposé sans fard. Le frontend peut
                # ainsi adapter son écran au lieu d'annoncer un succès
                # uniforme.
                "email": {
                    "status": outcome["parent_email_status"],
                    "accepted": outcome["parent_email_accepted"],
                    "tracking_id": outcome["parent_email_tracking_id"],
                },
                "sheet_generated": outcome["sheet_generated"],
                # Récapitulatif minimal — aucune donnée confidentielle.
                "summary": {
                    "child": f"{application.child_first_name} {application.child_last_name}",
                    "parent_email": application.parent1_email,
                },
            },
            status=status.HTTP_201_CREATED,
        )


class FHAProgramInfoView(APIView):
    """
    GET /api/website/public/fha/program/

    Informations publiques du programme, servies depuis la base pour rester
    ADMINISTRABLES. Les valeurs non validées par la direction (tarif, date
    de rentrée, horaires, enseignants, prestataire de paiement) sont
    renvoyées à null : le frontend masque alors le bloc au lieu d'afficher
    une information inventée.
    """
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        entity = get_fha_entity()
        if entity is None:
            return Response(
                {"detail": "Programme non configuré."},
                status=status.HTTP_404_NOT_FOUND,
            )
        settings_data = entity.settings or {}
        pending = settings_data.get("pending_direction_validation", {})
        return Response({
            "name": entity.name,
            "legal_name": entity.legal_name or entity.name,
            "short_name": "FEBA FHA",
            "tagline": settings_data.get("tagline", ""),
            "whatsapp": entity.whatsapp,
            "email": entity.email,
            "timezone": entity.timezone,
            # `currency` renvoie l'objet devise ; l'API expose le CODE.
            "currency": entity.currency_code,
            "currency_symbol": entity.currency_symbol,
            "default_language": entity.default_language,
            # Ces champs restent null tant que la direction ne les a pas
            # validés — ils ne doivent JAMAIS être devinés par le code.
            "annual_fee": pending.get("annual_fee"),
            "installments_allowed": pending.get("installments_allowed"),
            "school_year_start_date": pending.get("school_year_start_date"),
            "group_schedules": pending.get("group_schedules"),
            "sibling_discount": pending.get("sibling_discount"),
            "early_bird_discount": pending.get("early_bird_discount"),
            "refund_policy": pending.get("refund_policy"),
            "teacher_names": pending.get("teacher_names"),
            "payment_provider": pending.get("payment_provider"),
        })


# ── Administration FEBA FHA ───────────────────────────────────────────────────

class FHAApplicationViewSet(viewsets.ModelViewSet):
    """
    Dossiers d'inscription FEBA FHA — réservés à l'administration.

    ISOLATION : le queryset est filtré par l'entité courante. Un admin FEBA
    ne voit AUCUN dossier FHA (son entité n'en possède pas), et un accès
    direct par identifiant renvoie 404 plutôt que d'exposer l'objet.
    """
    permission_classes = [IsAuthenticated, IsAdminOrAbove]
    http_method_names = ['get', 'patch', 'post', 'delete', 'head', 'options']

    def get_serializer_class(self):
        if self.action == 'list':
            return FHAApplicationListSerializer
        return FHAApplicationDetailSerializer

    def get_queryset(self):
        qs = FHAEnrollmentApplication.objects.select_related('entity')
        user = self.request.user
        school = get_request_school(self.request)

        if school is not None:
            return qs.filter(entity=school)
        if user.is_superadmin():
            # Mode « toutes les entités » : vue consolidée explicite, avec
            # l'entité indiquée sur chaque ligne (entity_code).
            return qs
        return qs.none()

    @action(detail=True, methods=['post'], url_path='change-status')
    def change_status(self, request, pk=None):
        """
        Change l'état d'un dossier et consigne le changement (auteur, date,
        raison, commentaire). Aucun état n'est modifié silencieusement.
        """
        application = self.get_object()
        new_status = request.data.get('status')
        valid = {c[0] for c in FHAEnrollmentApplication.STATUS_CHOICES}
        if new_status not in valid:
            return Response(
                {'status': f"État inconnu. Valeurs possibles : {', '.join(sorted(valid))}."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        previous = application.status
        if previous == new_status:
            return Response(
                {'detail': "Le dossier est déjà dans cet état."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        application.status = new_status
        application.save(update_fields=['status', 'updated_at'])

        FHAApplicationStatusHistory.objects.create(
            application=application,
            from_status=previous,
            to_status=new_status,
            changed_by=request.user,
            reason=request.data.get('reason', ''),
            comment=request.data.get('comment', ''),
        )
        logger.info(
            "FEBA FHA — dossier %s : %s → %s (par %s)",
            application.reference, previous, new_status, request.user.email,
        )

        from .fha_notifications import notify_status_changed
        notify_status_changed(application, previous)

        return Response(
            FHAApplicationDetailSerializer(
                application, context={'request': request},
            ).data
        )


    # ── P3 : la fiche PDF, par ligne ─────────────────────────────────

    @action(detail=True, methods=['get'], url_path='sheet')
    def sheet(self, request, pk=None):
        """
        GET /api/website/admin/fha-applications/<id>/sheet/

        Télécharge la fiche d'inscription. JAMAIS une URL publique :
        `get_object()` applique le filtrage par académie, donc un admin
        FEBA reçoit 404 sur un dossier FHA — y compris en devinant
        l'identifiant. Le fichier lui-même vit hors de MEDIA_ROOT et n'est
        atteignable par aucune URL statique.
        """
        import os

        from django.http import FileResponse

        from .fha_enrollment import generate_and_store_sheet
        from .fha_pdf import sheet_filename

        application = self.get_object()

        if not application.has_sheet:
            # Fiche absente (échec de production, fichier supprimé) : on la
            # refait plutôt que de renvoyer une erreur à un administrateur
            # qui n'y peut rien.
            if generate_and_store_sheet(application) is None:
                return Response(
                    {"detail": "La fiche n'a pas pu être produite.",
                     "error": application.sheet_error},
                    status=status.HTTP_503_SERVICE_UNAVAILABLE,
                )
            application.refresh_from_db()

        path = application.sheet_absolute_path
        if not path or not os.path.exists(path):
            return Response({"detail": "Fiche introuvable."},
                            status=status.HTTP_404_NOT_FOUND)

        logger.info(
            "FHA — fiche %s téléchargée par %s",
            application.reference, request.user.email,
        )
        response = FileResponse(open(path, "rb"), content_type="application/pdf")
        response["Content-Disposition"] = (
            f'attachment; filename="{sheet_filename(application)}"'
        )
        # Un dossier d'inscription ne doit pas rester dans un cache
        # partagé : un poste utilisé par plusieurs agents servirait le
        # dossier d'un autre enfant.
        response["Cache-Control"] = "private, no-store"
        return response

    @action(detail=True, methods=['post'], url_path='regenerate-sheet')
    def regenerate_sheet(self, request, pk=None):
        """Reproduit la fiche après correction. L'ancienne version est conservée."""
        from .fha_enrollment import generate_and_store_sheet

        application = self.get_object()
        if generate_and_store_sheet(application) is None:
            return Response(
                {"detail": "La fiche n'a pas pu être produite.",
                 "error": application.sheet_error},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        application.refresh_from_db()
        return Response(FHAApplicationDetailSerializer(
            application, context={'request': request},
        ).data)

    @action(detail=True, methods=['get'], url_path='photo')
    def photo(self, request, pk=None):
        """
        Photo de l'enfant, servie sous contrôle.

        Django la range dans MEDIA_ROOT, mais on ne renvoie jamais son URL
        brute : la photo d'un mineur ne doit pas être atteignable par une
        adresse devinable ou partagée par mégarde.
        """
        import os

        from django.http import FileResponse

        application = self.get_object()
        if not application.child_photo:
            return Response({"detail": "Aucune photo."},
                            status=status.HTTP_404_NOT_FOUND)
        try:
            path = application.child_photo.path
        except (NotImplementedError, ValueError):
            return Response({"detail": "Photo indisponible."},
                            status=status.HTTP_404_NOT_FOUND)
        if not os.path.exists(path):
            return Response({"detail": "Photo introuvable."},
                            status=status.HTTP_404_NOT_FOUND)

        logger.info("FHA — photo du dossier %s consultée par %s",
                    application.reference, request.user.email)
        response = FileResponse(open(path, "rb"))
        response["Cache-Control"] = "private, no-store"
        return response

    # ── P1 : état des e-mails et relance ─────────────────────────────

    @action(detail=True, methods=['post'], url_path='resend-confirmation')
    def resend_confirmation(self, request, pk=None):
        """
        Relance l'accusé de réception au responsable.

        Existe parce que l'envoi peut échouer et que l'administration doit
        pouvoir agir. Un échec sans action de rattrapage laisse une famille
        sans nouvelle et une équipe sans moyen.
        """
        from .fha_enrollment import resend_parent_acknowledgement

        application = self.get_object()
        delivery = resend_parent_acknowledgement(application, user=request.user)
        return Response({
            "status": delivery.status,
            "status_display": delivery.get_status_display(),
            "accepted": delivery.is_delivered_to_provider,
            "tracking_id": str(delivery.tracking_id),
            "error": delivery.last_error,
            "used_real_provider": delivery.used_real_provider,
        })

    # ── P4 : export CSV complet ──────────────────────────────────────

    @action(detail=False, methods=['get'], url_path='export')
    def export(self, request):
        """
        Export CSV de TOUS les champs, pour les dossiers visibles.

        Le filtrage passe par `get_queryset()` : l'export ne peut pas
        exposer davantage que la liste, et un admin FEBA n'exporte aucun
        dossier FHA. Un export plus permissif que l'écran est un moyen
        discret de contourner l'isolation.
        """
        import csv

        from django.http import HttpResponse

        queryset = self.filter_queryset(self.get_queryset())
        rows = list(queryset)

        response = HttpResponse(content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = (
            f'attachment; filename="dossiers-fha-{timezone.now():%Y%m%d-%H%M}.csv"'
        )
        # BOM UTF-8 : sans lui, Excel ouvre « Gbêdjissi » en « GbÃªdjissi »
        # et l'export paraît corrompu alors qu'il est correct.
        response.write("\ufeff")

        writer = csv.writer(response, delimiter=";")
        columns = _export_columns()
        writer.writerow([label for label, _ in columns])
        for application in rows:
            writer.writerow([_export_value(application, key) for _, key in columns])

        logger.info(
            "FHA — export CSV de %d dossier(s) par %s",
            len(rows), request.user.email,
        )
        return response


def _export_columns():
    """
    Colonnes de l'export : TOUS les champs du modèle, plus les calculés.

    Construites depuis `_meta` pour qu'un champ ajouté au modèle apparaisse
    automatiquement. Un export figé finit toujours par perdre en silence
    les colonnes ajoutées après lui — c'est le défaut le plus banal et le
    plus difficile à voir.
    """
    from .models import FHAEnrollmentApplication

    skipped = {"id", "entity", "child_photo", "submitted_ip",
               "sheet_path", "sheet_sha256"}
    columns = [
        (field.verbose_name if field.verbose_name != field.name
         else field.name, field.name)
        for field in FHAEnrollmentApplication._meta.fields
        if field.name not in skipped
    ]
    return [
        ("academie", "__entity_code__"),
        ("academie_nom", "__entity_name__"),
        *columns,
        ("age_calcule", "__child_age__"),
        ("groupe_suggere", "__suggested_group__"),
        ("photo_fournie", "__has_photo__"),
        ("fiche_pdf_produite", "__has_sheet__"),
    ]


def _export_value(application, key):
    """Valeur d'une colonne, rendue lisible sans perdre d'information."""
    computed = {
        "__entity_code__": lambda a: a.entity.code or "",
        "__entity_name__": lambda a: a.entity.name,
        "__child_age__": lambda a: a.child_age if a.child_age is not None else "",
        "__suggested_group__": lambda a: a.suggested_group,
        "__has_photo__": lambda a: "oui" if a.child_photo else "non",
        "__has_sheet__": lambda a: "oui" if a.has_sheet else "non",
    }
    if key in computed:
        return computed[key](application)

    value = getattr(application, key, "")
    if isinstance(value, bool):
        return "oui" if value else "non"
    if isinstance(value, (list, tuple)):
        # Les listes JSON (niveaux, objectifs, créneaux) sont aplaties en
        # texte lisible plutôt qu'en JSON brut : un tableur n'ouvre pas du
        # JSON, et l'information deviendrait inexploitable.
        return " | ".join(
            ", ".join(f"{k}={v}" for k, v in item.items())
            if isinstance(item, dict) else str(item)
            for item in value
        )
    if value is None:
        return ""
    return str(value)


class EntityScopedContactMessageMixin:
    """
    Filtrage par entité des boîtes de réception de contact.

    Un admin ne voit que les messages de SON entité. Le superadmin voit
    l'entité active, ou toutes s'il est en mode consolidé.
    """

    def get_queryset(self):
        qs = ContactMessage.objects.select_related('entity')
        user = self.request.user
        school = get_request_school(self.request)

        if school is not None:
            return qs.filter(entity=school)
        if user.is_superadmin():
            return qs
        return qs.none()


# ── Test de placement FEBA FHA — parcours PUBLIC distinct ────────────────────

class FHAPlacementTestCreateView(APIView):
    """
    POST /api/website/public/fha/placement-test/

    Réservation d'un test de placement. PARCOURS DISTINCT de l'inscription :
    ne crée AUCUNE inscription confirmée, seulement une demande de test.
    """
    permission_classes = [AllowAny]
    authentication_classes = []

    @method_decorator(ratelimit(key="ip", rate="5/m", method="POST", block=True))
    def post(self, request):
        from .fha_serializers import FHAPlacementTestCreateSerializer

        serializer = FHAPlacementTestCreateSerializer(
            data=request.data, context={'request': request},
        )
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        test_request = serializer.save()

        logger.info(
            "FEBA FHA — demande de test de placement reçue (dossier %s)",
            test_request.reference,
        )

        from .fha_notifications import notify_placement_test_requested
        notify_placement_test_requested(test_request)

        return Response(
            {
                "detail": (
                    "Merci ! Votre demande de test de placement est enregistrée. "
                    f"Votre numéro de dossier est {test_request.reference}. "
                    "Nous vous confirmerons un créneau par e-mail."
                ),
                "detail_en": (
                    "Thank you! Your placement assessment request has been received. "
                    f"Your file number is {test_request.reference}. "
                    "We will confirm a time slot by e-mail."
                ),
                "reference": test_request.reference,
                "status": test_request.status,
                "child_age": test_request.child_age,
                "suggested_group": test_request.suggested_group,
            },
            status=status.HTTP_201_CREATED,
        )


class FHAPlacementTestViewSet(viewsets.ModelViewSet):
    """
    Demandes de test de placement — administration FEBA FHA.

    Boîte SÉPARÉE de celle des inscriptions : ce sont deux étapes
    différentes du parcours d'admission.
    """
    permission_classes = [IsAuthenticated, IsAdminOrAbove]
    http_method_names = ['get', 'patch', 'post', 'delete', 'head', 'options']
    search_fields = ['reference', 'child_first_name', 'child_last_name', 'parent_email']

    def get_serializer_class(self):
        from .fha_serializers import (
            FHAPlacementTestDetailSerializer, FHAPlacementTestListSerializer,
        )
        if self.action == 'list':
            return FHAPlacementTestListSerializer
        return FHAPlacementTestDetailSerializer

    def get_queryset(self):
        from .models import FHAPlacementTestRequest

        qs = FHAPlacementTestRequest.objects.select_related('entity', 'application')
        school = get_request_school(self.request)

        if school is not None:
            return qs.filter(entity=school)
        if self.request.user.is_superadmin():
            entity_code = self.request.query_params.get('entity_code')
            if entity_code:
                return qs.filter(entity__code=entity_code)
            return qs
        return qs.none()

    @action(detail=True, methods=['post'], url_path='schedule')
    def schedule(self, request, pk=None):
        """
        Confirme un créneau. `scheduled_at` est attendu en ISO 8601 AVEC
        fuseau : le stockage se fait en UTC, l'affichage est recalculé dans
        le fuseau de chaque utilisateur.
        """
        from django.utils.dateparse import parse_datetime

        test_request = self.get_object()
        raw = request.data.get('scheduled_at')
        if not raw:
            return Response(
                {'scheduled_at': "Créneau requis (ISO 8601 avec fuseau)."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        moment = parse_datetime(raw)
        if moment is None:
            return Response(
                {'scheduled_at': "Format de date invalide."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if timezone.is_naive(moment):
            moment = timezone.make_aware(moment, timezone.utc)

        test_request.scheduled_at = moment
        test_request.status = 'scheduled'
        test_request.save(update_fields=['scheduled_at', 'status', 'updated_at'])

        from .fha_notifications import notify_placement_test_scheduled
        notify_placement_test_scheduled(test_request)

        logger.info(
            "FEBA FHA — test %s planifié au %s par %s",
            test_request.reference, moment.isoformat(), request.user.email,
        )
        return Response(self.get_serializer(test_request).data)

    @action(detail=True, methods=['post'], url_path='record-result')
    def record_result(self, request, pk=None):
        """Enregistre la grille d'évaluation et clôt le test."""
        from .models import FHAPlacementTestResult

        test_request = self.get_object()
        fields = ('listening', 'speaking', 'vocabulary', 'reading', 'writing', 'confidence')
        values = {}
        for field in fields:
            raw = request.data.get(field, 0)
            try:
                score = int(raw)
            except (TypeError, ValueError):
                return Response(
                    {field: "Score attendu entre 0 et 4."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if not 0 <= score <= 4:
                return Response(
                    {field: "Score attendu entre 0 et 4."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            values[field] = score

        result, _ = FHAPlacementTestResult.objects.update_or_create(
            request=test_request,
            defaults={
                **values,
                'recommended_group': request.data.get('recommended_group', ''),
                'starting_level': request.data.get('starting_level', ''),
                'priority_objectives': request.data.get('priority_objectives', ''),
                'assessor_notes': request.data.get('assessor_notes', ''),
                'assessed_by': request.user,
            },
        )
        test_request.status = 'completed'
        test_request.save(update_fields=['status', 'updated_at'])

        logger.info(
            "FEBA FHA — résultat du test %s enregistré (groupe %s)",
            test_request.reference, result.recommended_group or "à définir",
        )
        return Response(self.get_serializer(test_request).data)
