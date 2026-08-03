"""
Répond à une question et une seule : les documents officiels sont-ils
utilisables MAINTENANT, sur cette installation ?

    python manage.py documents_ready            # rendu réel compris
    python manage.py documents_ready --fast     # sans produire de PDF

Sort en erreur au moindre contrôle en échec. C'est ce qui en fait une
étape d'installation utile : `make install` s'arrête si le diplôme
n'est pas prêt, au lieu de laisser la découverte au premier directeur qui
cliquera sur « Produire un document officiel ».
"""
from django.core.management.base import BaseCommand

from apps.documents.startup import run_checks


class Command(BaseCommand):
    help = "Vérifie que les documents officiels peuvent être produits."

    def add_arguments(self, parser):
        parser.add_argument(
            "--fast", action="store_true",
            help="Ne produit pas de PDF de contrôle (plus rapide, moins probant).",
        )

    def handle(self, *args, **options):
        results = run_checks(include_render=not options["fast"])

        for result in results:
            if result.ok:
                self.stdout.write(self.style.SUCCESS(
                    f"  ✓ {result.name}" + (f" — {result.detail}" if result.detail else "")
                ))
            else:
                self.stdout.write(self.style.ERROR(f"  ✗ {result.name} — {result.detail}"))

        failures = [r for r in results if not r.ok]
        self.stdout.write("")
        if failures:
            self.stderr.write(self.style.ERROR(
                f"{len(failures)} contrôle(s) en échec sur {len(results)} : les "
                f"documents officiels ne peuvent pas être produits en l'état."
            ))
            raise SystemExit(1)

        self.stdout.write(self.style.SUCCESS(
            f"{len(results)} contrôles passés — les documents officiels sont "
            f"produisibles dès maintenant, sans commande supplémentaire."
        ))
