"""
manage.py production_preflight [--network] [--fingerprint] [--quiet]

Contrôle de la configuration EFFECTIVE avant démarrage (voir
apps/core/preflight.py). Code de sortie 1 si une erreur bloquante est
trouvée : l'entrée de production, le worker et Beat s'arrêtent alors
avec ce message au lieu de démarrer mal configurés.
"""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Refuse le démarrage si la configuration de production est incomplète ou dangereuse."

    def add_arguments(self, parser):
        parser.add_argument("--network", action="store_true", help="Vérifie aussi PostgreSQL et Redis.")
        parser.add_argument("--fingerprint", action="store_true", help="Affiche seulement l'empreinte de configuration.")
        parser.add_argument("--quiet", action="store_true", help="N'affiche que les erreurs.")

    def handle(self, *args, **options):
        from apps.core.preflight import ERROR, fingerprint, network_problems, problems, stage

        if options["fingerprint"]:
            self.stdout.write(fingerprint())
            return
        found = problems() + (network_problems() if options["network"] else [])
        errors = [p for p in found if p[0] == ERROR]
        if not options["quiet"]:
            self.stdout.write(f"Contrôle de configuration - étape « {stage()} », empreinte {fingerprint()}")
        for level, code, message in found:
            if options["quiet"] and level != ERROR:
                continue
            style = self.style.ERROR if level == ERROR else self.style.WARNING
            self.stdout.write(style(f"  [{level}] {code} : {message}"))
        if errors:
            self.stderr.write(self.style.ERROR(
                f"\nDÉMARRAGE REFUSÉ : {len(errors)} erreur(s) de configuration. Corrigez .env.prod "
                "(voir .env.prod.example et DEPLOYMENT_PRODUCTION.md)."))
            raise SystemExit(1)
        if not options["quiet"]:
            self.stdout.write(self.style.SUCCESS("Configuration acceptée."))
