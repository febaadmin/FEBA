from django.apps import AppConfig


class DocumentsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.documents"
    verbose_name = "Documents officiels"

    def ready(self):
        """
        P7 — Contrôle d'aptitude au démarrage.

        Le diplôme doit être utilisable dès l'installation. S'il ne l'est
        pas, le défaut apparaît ICI, dans les journaux du serveur, avec sa
        cause — et non le jour où un directeur clique sur « Produire » et
        lit un message lui demandant de lancer une commande.

        Non bloquant, et silencieux hors serveur : `migrate`, `test` et les
        commandes d'atelier n'ont pas à charger les gabarits.
        """
        import os
        import sys

        if os.environ.get("FEBA_SKIP_DOCUMENT_STARTUP_CHECK"):
            return
        argv = " ".join(sys.argv)
        if not any(word in argv for word in ("runserver", "gunicorn", "uvicorn")):
            return

        from apps.documents.startup import log_startup_report

        log_startup_report()
