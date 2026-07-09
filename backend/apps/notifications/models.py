from django.db import models
from apps.accounts.models import CustomUser

class Notification(models.Model):
    TYPE_CHOICES = [
        ("grade","Note"),("absence","Absence"),("payment","Paiement"),
        ("message","Message"),("homework","Devoir"),("announcement","Annonce"),
    ]
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name="notifications")
    type = models.CharField(max_length=15, choices=TYPE_CHOICES)
    title = models.CharField(max_length=200)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    related_url = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Notification"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user} - {self.title}"