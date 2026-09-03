"""
Vérification de l'infrastructure de visioconférence auto-hébergée.

Code de sortie 0 si l'instance est opérationnelle, 1 sinon : utilisable
directement dans un pipeline CI ou une sonde de supervision.

P6 — La commande détaille désormais CHAQUE contrôle (configuration,
domaine non public, signature de jeton, DNS, TLS, HTTP, page Jitsi). Un
« injoignable » global ne dit pas quoi faire ; « le DNS ne résout pas » et
« le certificat a expiré » désignent deux gestes différents, chez deux
prestataires différents.

`--domain` permet de contrôler l'instance de PRODUCTION depuis n'importe
où — poste d'exploitation, CI — sans déployer de configuration :

    python manage.py jitsi_health --domain meet.globalfeba.com
"""
import sys

from django.core.management.base import BaseCommand
from django.test import override_settings

from apps.virtualclass.services import jitsi_health


class Command(BaseCommand):
    help = "Vérifie l'état de l'instance Jitsi auto-hébergée."

    def add_arguments(self, parser):
        parser.add_argument(
            "--domain",
            help=(
                "Contrôler CE domaine au lieu de JITSI_DOMAIN. Sert à "
                "vérifier l'instance de production depuis un poste "
                "d'exploitation (ex. meet.globalfeba.com)."
            ),
        )
        parser.add_argument(
            "--timeout", type=float, default=5.0,
            help="Délai maximum par contrôle réseau, en secondes (défaut : 5).",
        )

    def handle(self, *args, **options):
        domain = options.get("domain")
        timeout = options.get("timeout") or 5.0

        if domain:
            # Le domaine visé prime, et l'URL interne est neutralisée :
            # sonder « http://jitsi-web:80 » en croyant contrôler
            # meet.globalfeba.com donnerait un feu vert sur la mauvaise
            # instance — précisément l'erreur que --domain sert à éviter.
            with override_settings(JITSI_DOMAIN=domain, JITSI_INTERNAL_URL=""):
                report = jitsi_health(timeout=timeout)
        else:
            report = jitsi_health(timeout=timeout)

        labels = {
            "operational": self.style.SUCCESS("OPÉRATIONNEL"),
            "degraded": self.style.WARNING("DÉGRADÉ"),
            "unavailable": self.style.ERROR("INDISPONIBLE"),
        }
        self.stdout.write(f"État               : {labels.get(report['status'], report['status'])}")
        self.stdout.write(f"Domaine            : {report['domain'] or '(non configuré)'}")
        self.stdout.write(f"Configuration      : {'oui' if report['configured'] else 'NON'}")
        self.stdout.write(f"Signature jeton    : {'oui' if report['token_signing'] else 'NON'}")
        self.stdout.write(f"Instance joignable : {'oui' if report['reachable'] else 'NON'}")
        if report.get("probed_url"):
            self.stdout.write(f"URL testée         : {report['probed_url']}")

        if report.get("checks"):
            self.stdout.write("")
            self.stdout.write("Contrôles :")
            for check in report["checks"]:
                mark = (self.style.SUCCESS("  OK  ") if check["ok"]
                        else self.style.ERROR(" ÉCHEC"))
                self.stdout.write(f"{mark}  {check['name']:<20} {check['detail']}")

        if report["detail"]:
            self.stdout.write("")
            self.stdout.write(f"Détail             : {report['detail']}")

        if report["status"] != "operational":
            self.stdout.write("")
            self.stdout.write(self.style.WARNING(
                "Aucune session n'est basculée vers un service public : "
                "les cours restent indisponibles tant que l'instance FEBA "
                "n'est pas rétablie."
            ))
            sys.exit(1)
