"""
UserFile CRUD API — v18 Fixed
Fixes:
  - Added proper permission classes for admin/superadmin
  - Fixed 404 on download
  - Fixed notification API compatibility
  - CORS-safe file serving
"""
import os
import logging
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser
from django.http import FileResponse, Http404
from .models import UserFile
from .serializers import UserFileSerializer
from apps.core.tenancy import get_request_school

logger = logging.getLogger("apps")


class UserFileViewSet(viewsets.ModelViewSet):
    serializer_class = UserFileSerializer
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]
    filterset_fields = ["user"]
    search_fields = ["name", "description", "original_filename"]

    def get_queryset(self):
        user = self.request.user
        school = get_request_school(self.request)
        qs = UserFile.objects.select_related("user")

        # --- Isolation multi-tenant (FIX v29) -------------------------------
        if school is not None:
            qs = qs.filter(user__school=school)
        elif not user.is_superadmin():
            return qs.none()

        if user.role_level >= 80:
            # Admins and superadmins can see all files DE LEUR établissement
            user_id = self.request.query_params.get("user")
            if user_id:
                return qs.filter(user_id=user_id)
            return qs

        # Regular users see only their own files
        return qs.filter(user=user)

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["request"] = self.request
        return ctx

    def perform_create(self, serializer):
        user = self.request.user
        school = get_request_school(self.request)
        target_user_id = self.request.data.get("user")
        if user.role_level >= 80 and target_user_id:
            from apps.accounts.models import CustomUser
            target_qs = CustomUser.objects.all()
            if school is not None:
                # FIX SÉCURITÉ (v29) : un admin ne doit pas pouvoir déposer
                # un fichier au nom d'un utilisateur d'un AUTRE établissement.
                target_qs = target_qs.filter(school=school)
            try:
                target = target_qs.get(pk=target_user_id)
                serializer.save(user=target)
                return
            except CustomUser.DoesNotExist as exc:
                logger.warning("Erreur non bloquante ignorée : %s", exc, exc_info=True)
        serializer.save(user=user)

    def perform_update(self, serializer):
        instance = serializer.instance
        old_file = instance.file
        serializer.save()
        if "file" in self.request.FILES and old_file and old_file != serializer.instance.file:
            try:
                old_file.delete(save=False)
            except Exception as exc:
                logger.warning("Erreur non bloquante ignorée : %s", exc, exc_info=True)
    def perform_destroy(self, instance):
        # Delete the actual file from storage
        try:
            if instance.file:
                instance.file.delete(save=False)
        except Exception as e:
            logger.warning(f"Could not delete file from storage: {e}")
        instance.delete()

    @action(detail=True, methods=["get"], url_path="download")
    def download(self, request, pk=None):
        """GET /api/user-files/{id}/download/ — secure file download."""
        try:
            file_obj = self.get_object()
        except Exception:
            raise Http404("Fichier introuvable.")

        try:
            if not file_obj.file:
                return Response({"error": "Fichier introuvable."}, status=status.HTTP_404_NOT_FOUND)

            file_path = file_obj.file.path
            if not os.path.exists(file_path):
                return Response({"error": "Fichier non trouvé sur le serveur."}, status=status.HTTP_404_NOT_FOUND)

            response = FileResponse(
                open(file_path, "rb"),
                as_attachment=True,
                filename=file_obj.original_filename or file_obj.name,
                content_type=file_obj.mime_type or "application/octet-stream",
            )
            response["Content-Length"] = file_obj.file_size or os.path.getsize(file_path)
            return response
        except Exception as e:
            logger.error(f"File download error for {pk}: {e}", exc_info=True)
            return Response({"error": "Erreur lors du téléchargement."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=["get"], url_path="preview")
    def preview(self, request, pk=None):
        """GET /api/user-files/{id}/preview/ — inline preview for images/PDFs."""
        try:
            file_obj = self.get_object()
        except Exception:
            raise Http404

        try:
            if not file_obj.file or not os.path.exists(file_obj.file.path):
                return Response({"error": "Fichier introuvable."}, status=404)

            response = FileResponse(
                open(file_obj.file.path, "rb"),
                as_attachment=False,
                content_type=file_obj.mime_type or "application/octet-stream",
            )
            return response
        except Exception as e:
            logger.error(f"File preview error: {e}")
            return Response({"error": "Erreur de prévisualisation."}, status=500)
