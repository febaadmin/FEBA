from django.db import models
from apps.accounts.models import CustomUser
from apps.schools.models import SchoolYear


class Announcement(models.Model):
    title = models.CharField(max_length=200)
    content = models.TextField()
    author = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name="announcements")
    target_roles = models.JSONField(default=list)
    attachment = models.FileField(upload_to="announcements/", null=True, blank=True)
    attachment_name = models.CharField(max_length=200, blank=True)
    is_published = models.BooleanField(default=True)
    published_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    school_year = models.ForeignKey(SchoolYear, on_delete=models.SET_NULL, null=True, blank=True, related_name="announcements")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Annonce"
        ordering = ["-created_at"]

    def __str__(self):
        return self.title