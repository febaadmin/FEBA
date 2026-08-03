"""
P3 — L'API des rapports mensuels FEBA French Heritage Academy.

LE CLOISONNEMENT EST POSÉ ICI, PAS DANS LE NAVIGATEUR
------------------------------------------------------
Un rapport mensuel contient les notes, les absences et les appréciations
d'un mineur. Masquer l'entrée de menu côté React ne protège rien :
l'URL reste atteignable à la main. Trois barrières se cumulent :

  1. `initial()` refuse tout administrateur dont l'académie n'est pas
     l'académie en ligne — avant même que la vue ne s'exécute ;
  2. `get_queryset()` restreint la portée à l'académie effective, si bien
     qu'un identifiant d'une autre académie donne 404 et non 403 :
     répondre « interdit » confirmerait que le dossier existe ;
  3. le fichier PDF sort d'une vue authentifiée, jamais d'une URL
     publique.
"""
import logging
import os

from django.http import FileResponse
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.permissions import IsAdminOrAbove
from apps.core.tenancy import get_request_school
from apps.schools.models import School

from .models import MonthlyReportStatus, MonthlyStudentReport
from .serializers import (
    MonthlyReportDetailSerializer, MonthlyReportEditSerializer,
    MonthlyReportListSerializer,
)
from .services import ReportError, generate_report, send_report

logger = logging.getLogger("apps")


class MonthlyReportViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, IsAdminOrAbove]
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_serializer_class(self):
        if self.action in ("update", "partial_update"):
            return MonthlyReportEditSerializer
        if self.action == "retrieve":
            return MonthlyReportDetailSerializer
        return MonthlyReportListSerializer

    # ── Portée ───────────────────────────────────────────────────────

    def _fha(self):
        return School.objects.filter(code=School.CODE_FEBA_FHA).first()

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        user = request.user
        if not user.is_authenticated:
            return
        if user.is_superadmin():
            return
        academy = getattr(user, "school", None)
        if academy is None or academy.code != School.CODE_FEBA_FHA:
            raise PermissionDenied(
                "Les rapports mensuels sont propres à FEBA French Heritage "
                "Academy. Cette académie ne dispose pas de ce module."
            )

    def get_queryset(self):
        fha = self._fha()
        base = (MonthlyStudentReport.objects
                .select_related("academy", "student", "school_year")
                .prefetch_related("attempts"))
        if fha is None:
            return base.none()
        # Quelle que soit l'académie sélectionnée, ce module ne renvoie
        # QUE des rapports de l'académie en ligne : ce sont les seuls qui
        # existent, et le laisser dépendre d'un filtre extérieur
        # ouvrirait la porte à un élargissement silencieux.
        queryset = base.filter(academy=fha)

        scope = get_request_school(self.request)
        if scope is not None and scope.code != School.CODE_FEBA_FHA:
            # Le super administrateur regarde une AUTRE académie : la page
            # doit obéir au sélecteur placé au-dessus d'elle.
            return queryset.none()

        params = self.request.query_params
        if params.get("student"):
            queryset = queryset.filter(student_id=params["student"])
        if params.get("year"):
            queryset = queryset.filter(year=params["year"])
        if params.get("month"):
            queryset = queryset.filter(month=params["month"])
        if params.get("status"):
            queryset = queryset.filter(status=params["status"])
        recherche = params.get("search")
        if recherche:
            from django.db.models import Q

            queryset = queryset.filter(
                Q(student__first_name__icontains=recherche)
                | Q(student__last_name__icontains=recherche)
                | Q(reference__icontains=recherche)
            )
        return queryset

    def create(self, request, *args, **kwargs):
        """
        Produit le rapport d'un élève pour une période.

        Idempotent : appelé deux fois, il renvoie le rapport existant au
        lieu d'en créer un second.
        """
        from apps.students.models import Student

        fha = self._fha()
        if fha is None:
            raise ValidationError("L'académie en ligne n'est pas configurée.")

        try:
            student_id = int(request.data.get("student"))
            year = int(request.data.get("year"))
            month = int(request.data.get("month"))
        except (TypeError, ValueError):
            raise ValidationError(
                "« student », « year » et « month » sont obligatoires.")
        if not 1 <= month <= 12:
            raise ValidationError("Le mois doit être compris entre 1 et 12.")

        # Anti-IDOR : l'élève doit appartenir à l'académie en ligne. Un
        # identifiant d'élève de Cotonou produirait sinon un rapport à
        # l'identité de l'académie en ligne pour un enfant qui n'y est
        # pas inscrit.
        student = Student.objects.filter(pk=student_id, school=fha).first()
        if student is None:
            return Response(
                {"detail": "Élève introuvable dans cette académie."},
                status=status.HTTP_404_NOT_FOUND)

        try:
            report, created = generate_report(student, year, month,
                                              user=request.user)
        except ReportError as exc:
            return Response({"detail": str(exc)},
                            status=status.HTTP_503_SERVICE_UNAVAILABLE)

        return Response(
            MonthlyReportDetailSerializer(report).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    def perform_update(self, serializer):
        report = self.get_object()
        if not report.is_editable:
            raise ValidationError(
                "Ce rapport a déjà été envoyé ou archivé. Le modifier "
                "produirait un document différent portant la référence de "
                "celui que la famille détient. Créez une nouvelle version."
            )
        serializer.save(updated_by=self.request.user)

    def perform_destroy(self, instance):
        """
        Un rapport RÉELLEMENT envoyé ne disparaît pas sans trace.

        Il s'archive. Supprimer la seule preuve de ce qui a été transmis
        à une famille rendrait toute contestation invérifiable.
        """
        if instance.really_sent:
            raise ValidationError(
                "Ce rapport a été transmis à la famille. Il ne peut pas être "
                "supprimé, seulement archivé."
            )
        instance.delete()

    # ── Actions ──────────────────────────────────────────────────────

    @action(detail=True, methods=["get"], url_path="pdf")
    def pdf(self, request, pk=None):
        report = self.get_object()
        if not report.has_pdf:
            return Response(
                {"detail": "Le PDF de ce rapport est absent. Régénérez-le."},
                status=status.HTTP_404_NOT_FOUND)

        from .pdf import report_filename

        response = FileResponse(open(report.pdf_absolute_path, "rb"),
                                content_type="application/pdf")
        # `inline` : l'aperçu s'ouvre dans l'onglet. Le téléchargement
        # reste possible depuis le lecteur PDF.
        disposition = "inline" if request.query_params.get("preview") else "attachment"
        response["Content-Disposition"] = (
            f'{disposition}; filename="{report_filename(report)}"')
        response["Cache-Control"] = "private, no-store"
        logger.info("Rapport %s téléchargé par %s", report.reference,
                    request.user.email)
        return response

    @action(detail=True, methods=["post"], url_path="regenerate")
    def regenerate(self, request, pk=None):
        report = self.get_object()
        if not report.is_editable:
            return Response(
                {"detail": "Ce rapport n'est plus modifiable. Produisez une "
                           "nouvelle version."},
                status=status.HTTP_400_BAD_REQUEST)
        try:
            report, _ = generate_report(report.student, report.year,
                                        report.month, user=request.user)
        except ReportError as exc:
            return Response({"detail": str(exc)},
                            status=status.HTTP_503_SERVICE_UNAVAILABLE)
        return Response(MonthlyReportDetailSerializer(report).data)

    @action(detail=True, methods=["post"], url_path="new-version")
    def new_version(self, request, pk=None):
        """Crée une version supplémentaire, sans toucher à la précédente."""
        report = self.get_object()
        try:
            nouveau, _ = generate_report(report.student, report.year,
                                         report.month, user=request.user,
                                         force_new_version=True)
        except ReportError as exc:
            return Response({"detail": str(exc)},
                            status=status.HTTP_503_SERVICE_UNAVAILABLE)
        return Response(MonthlyReportDetailSerializer(nouveau).data,
                        status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="send")
    def send(self, request, pk=None):
        report = self.get_object()
        try:
            report = send_report(report, user=request.user)
        except ReportError as exc:
            return Response({"detail": str(exc)},
                            status=status.HTTP_400_BAD_REQUEST)

        data = MonthlyReportDetailSerializer(report).data
        if report.status != MonthlyReportStatus.SENT:
            # On rend 200 : la tentative a bien eu lieu. C'est le CORPS
            # qui dit qu'elle a échoué, et l'écran l'affiche tel quel.
            data["detail"] = report.last_error
        return Response(data)

    @action(detail=True, methods=["post"], url_path="cancel")
    def cancel(self, request, pk=None):
        return self._transition(request, MonthlyReportStatus.CANCELLED)

    @action(detail=True, methods=["post"], url_path="archive")
    def archive(self, request, pk=None):
        return self._transition(request, MonthlyReportStatus.ARCHIVED)

    @action(detail=True, methods=["post"], url_path="mark-ready")
    def mark_ready(self, request, pk=None):
        return self._transition(request, MonthlyReportStatus.READY)

    def _transition(self, request, target):
        from .models import InvalidTransition

        report = self.get_object()
        try:
            report.transition_to(target, user=request.user)
        except InvalidTransition as exc:
            return Response({"detail": str(exc)},
                            status=status.HTTP_400_BAD_REQUEST)
        return Response(MonthlyReportDetailSerializer(report).data)

    @action(detail=False, methods=["post"], url_path="generate-month")
    def generate_month_action(self, request):
        """Produit le lot d'un mois pour toute l'académie."""
        from .services import generate_month

        fha = self._fha()
        if fha is None:
            raise ValidationError("L'académie en ligne n'est pas configurée.")
        try:
            year = int(request.data.get("year"))
            month = int(request.data.get("month"))
        except (TypeError, ValueError):
            raise ValidationError("« year » et « month » sont obligatoires.")
        if not 1 <= month <= 12:
            raise ValidationError("Le mois doit être compris entre 1 et 12.")

        resultats = generate_month(fha, year, month, user=request.user)
        logger.info("Rapports mensuels — lot %04d-%02d déclenché par %s : %s",
                    year, month, request.user.email, resultats)
        return Response(resultats)
