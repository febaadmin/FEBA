"""
Vérification de l'infrastructure de visioconférence auto-hébergée.

Code de sortie 0 si l'instance est opérationnelle, 1 sinon : utilisable
directement dans un pipeline CI ou une sonde de supervision.
"""
import sys

from django.core.management.base import BaseCommand

from apps.virtualclass.services import jitsi_health


class Command(BaseCommand):
    help = "Vérifie l'état de l'instance Jitsi auto-hébergée."

    def handle(self, *args, **options):
        report = jitsi_health()

        labels = {
            "operational": self.style.SUCCESS("OPÉRATIONNEL"),
            "degraded": self.style.WARNING("DÉGRADÉ"),
            "unavailable": self.style.ERROR("INDISPONIBLE"),
        }
        self.stdout.write(f"État             : {labels.get(report['status'], report['status'])}")
        self.stdout.write(f"Domaine          : {report['domain'] or '(non configuré)'}")
        self.stdout.write(f"Configuration    : {'oui' if report['configured'] else 'NON'}")
        self.stdout.write(f"Signature jeton  : {'oui' if report['token_signing'] else 'NON'}")
        self.stdout.write(f"Instance joignable : {'oui' if report['reachable'] else 'NON'}")
        if report.get("probed_url"):
            self.stdout.write(f"URL testée (interne) : {report['probed_url']}")
        if report["detail"]:
            self.stdout.write(f"Détail           : {report['detail']}")

        if report["status"] != "operational":
            self.stdout.write("")
            self.stdout.write(self.style.WARNING(
                "Aucune session n'est basculée vers un service public : "
                "les cours restent indisponibles tant que l'instance FEBA "
                "n'est pas rétablie."
            ))
            sys.exit(1)
