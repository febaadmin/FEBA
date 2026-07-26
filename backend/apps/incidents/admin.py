from django.contrib import admin

from .models import TechnicalIncident


@admin.register(TechnicalIncident)
class TechnicalIncidentAdmin(admin.ModelAdmin):
    list_display = ("reference", "severity", "status", "exception_type",
                    "endpoint", "occurrences", "last_seen_at")
    list_filter = ("status", "severity", "module")
    search_fields = ("reference", "message", "endpoint", "exception_type")
    readonly_fields = ("reference", "fingerprint", "occurrences",
                       "first_seen_at", "last_seen_at", "created_at")
