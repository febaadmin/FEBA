from django.apps import AppConfig


class VirtualclassConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.virtualclass"
    verbose_name = "Salles virtuelles"

    def ready(self):
        from . import checks  # noqa: F401 — enregistre les contrôles de configuration
