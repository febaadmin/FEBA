"""
UserFile — per-user file storage module.
Supports image, PDF, doc, and other file types.
"""
import os
from django.db import models
from django.core.validators import FileExtensionValidator


def user_upload_path(instance, filename):
    return f"user_files/{instance.user.id}/{filename}"


ALLOWED_EXTENSIONS = [
    "jpg", "jpeg", "png", "gif", "webp",
    "pdf",
    "doc", "docx", "odt",
    "xls", "xlsx", "ods",
    "ppt", "pptx",
    "txt", "csv",
    "zip", "rar",
    "mp4", "mp3",
]

MIME_MAP = {
    "jpg": "image/jpeg", "jpeg": "image/jpeg",
    "png": "image/png", "gif": "image/gif", "webp": "image/webp",
    "pdf": "application/pdf",
    "doc": "application/msword",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "xls": "application/vnd.ms-excel",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "txt": "text/plain", "csv": "text/csv",
    "zip": "application/zip",
}


class UserFile(models.Model):
    user = models.ForeignKey(
        "accounts.CustomUser",
        on_delete=models.CASCADE,
        related_name="files",
    )
    name = models.CharField(max_length=255, help_text="Nom affiché du fichier")
    description = models.TextField(blank=True)
    file = models.FileField(
        upload_to=user_upload_path,
        validators=[FileExtensionValidator(allowed_extensions=ALLOWED_EXTENSIONS)],
    )
    file_size = models.PositiveBigIntegerField(default=0)
    mime_type = models.CharField(max_length=100, blank=True)
    original_filename = models.CharField(max_length=255, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Fichier utilisateur"
        ordering = ["-uploaded_at"]

    def __str__(self):
        return f"{self.user} — {self.name}"

    def save(self, *args, **kwargs):
        if self.file:
            ext = os.path.splitext(self.file.name)[-1].lstrip(".").lower()
            self.mime_type = MIME_MAP.get(ext, "application/octet-stream")
            if hasattr(self.file, "size"):
                self.file_size = self.file.size
            if not self.original_filename:
                self.original_filename = os.path.basename(self.file.name)
        super().save(*args, **kwargs)
