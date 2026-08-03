"""
Réparation des devises — uniquement les cas SANS AMBIGUÏTÉ.

CE QUE CETTE COMMANDE FAIT
--------------------------
Elle pose le code de devise de l'académie sur les paiements où ce code
était absent, ou incorrect sans que la VALEUR soit remise en cause (les
deux devises ayant le même nombre de décimales).

CE QU'ELLE NE FERA JAMAIS
-------------------------
Convertir un montant. Si un paiement de FEBA FHA porte « 50000 » et que la
devise attendue est le dollar, il est impossible de savoir depuis le code
si la personne a saisi 50 000 francs CFA ou 50 000 dollars. Diviser par
655,957 « pour arranger » réécrirait une somme réellement encaissée, sur la
foi d'une supposition. La commande signale, et laisse un humain trancher.

Usage :
    python manage.py repair_payment_currencies --dry-run
    python manage.py repair_payment_currencies --apply
"""
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.core.currency import DEFAULT_CURRENCY, Money

from .audit_payment_currencies import AFFICHAGE, AMBIGU, ORPHELIN, collect


class Command(BaseCommand):
    help = "Corrige les codes de devise sûrs. N'altère jamais un montant."

    def add_arguments(self, parser):
        group = parser.add_mutually_exclusive_group(required=True)
        group.add_argument("--dry-run", action="store_true",
                           help="Affiche ce qui serait corrigé, sans rien écrire.")
        group.add_argument("--apply", action="store_true",
                           help="Applique les corrections sûres.")

    def handle(self, *args, **options):
        buckets = collect()
        safe = buckets[AFFICHAGE]
        ambiguous = buckets[AMBIGU]
        orphans = buckets[ORPHELIN]

        self.stdout.write(self.style.MIGRATE_HEADING(
            "Réparation des devises — corrections sûres uniquement"
        ))

        if not safe:
            self.stdout.write(self.style.SUCCESS("Aucune correction sûre à appliquer."))
        else:
            self.stdout.write(f"{len(safe)} paiement(s) à corriger :")
            for payment, expected in safe[:30]:
                money = Money(payment.amount_minor, payment.currency or DEFAULT_CURRENCY)
                self.stdout.write(
                    f"  #{payment.pk:<5} {money.formatted():<16} "
                    f"{(payment.currency or 'aucune'):>8} → {expected}"
                )
            if len(safe) > 30:
                self.stdout.write(f"  … et {len(safe) - 30} de plus")

        if options["dry_run"]:
            self.stdout.write("")
            self.stdout.write("Simulation : aucune écriture effectuée.")
        elif safe:
            with transaction.atomic():
                from apps.payments.models import Payment
                for payment, expected in safe:
                    # `update()` plutôt que `save()` : on corrige UNIQUEMENT
                    # le code de devise, sans déclencher la dérivation du
                    # montant ni toucher à quoi que ce soit d'autre.
                    Payment.objects.filter(pk=payment.pk).update(currency=expected)
            self.stdout.write("")
            self.stdout.write(self.style.SUCCESS(f"{len(safe)} paiement(s) corrigé(s)."))

        if ambiguous or orphans:
            self.stdout.write("")
            self.stdout.write(self.style.WARNING(
                "REVUE MANUELLE REQUISE — non corrigés volontairement :"
            ))
            for payment, expected in ambiguous:
                money = Money(payment.amount_minor, payment.currency or DEFAULT_CURRENCY)
                self.stdout.write(
                    f"  #{payment.pk:<5} {money.formatted():<16} enregistré en "
                    f"{payment.currency}, académie attendue en {expected} — "
                    f"la valeur elle-même est peut-être à revoir."
                )
            for payment, _ in orphans:
                self.stdout.write(
                    f"  #{payment.pk:<5} sans académie : impossible de déterminer une devise."
                )
            self.stdout.write("")
            self.stdout.write(
                "Aucun montant n'a été converti. Reprenez ces lignes avec "
                "l'administration avant toute correction."
            )
            if options["apply"]:
                raise CommandError(
                    f"{len(ambiguous) + len(orphans)} cas restent à trancher manuellement."
                )
