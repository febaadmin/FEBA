"""
Diagnostic du webhook de paiement.

Un webhook mal configuré ne produit aucune erreur visible : le parent paie,
sa carte est débitée, et l'application n'en sait rien. Le symptôme —
« j'ai payé mais ça n'apparaît pas » — arrive des jours plus tard, par
téléphone.

Cette commande répond à trois questions, dans l'ordre où elles se posent :

  1. Le point de terminaison est-il correctement déclaré et protégé ?
  2. Des événements arrivent-ils réellement ?
  3. Des tentatives sont-elles restées en attente sans jamais aboutir ?
"""
from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db.models import Count
from django.utils import timezone

from apps.payments.transaction_models import PaymentTransaction, WebhookEvent


class Command(BaseCommand):
    help = "Diagnostique la réception et le traitement des événements de paiement."

    def add_arguments(self, parser):
        parser.add_argument("--hours", type=int, default=48,
                            help="Fenêtre d'analyse en heures (défaut : 48).")

    def handle(self, *args, **options):
        since = timezone.now() - timedelta(hours=options["hours"])
        base_url = getattr(settings, "PUBLIC_BASE_URL", "").rstrip("/")

        self.stdout.write(self.style.MIGRATE_HEADING(
            "\nDiagnostic du webhook de paiement\n"
        ))
        self.stdout.write(f"  Adresse attendue : {base_url}/api/payments/webhook/stripe/")

        # ── 1. Protection ─────────────────────────────────────────────
        secret = getattr(settings, "STRIPE_WEBHOOK_SECRET", "")
        if secret:
            self.stdout.write(self.style.SUCCESS(
                "  ✓ Secret de signature configuré — les événements non signés "
                "sont refusés."
            ))
        else:
            self.stdout.write(self.style.ERROR(
                "  ✗ Aucun secret de signature : TOUS les événements sont "
                "refusés.\n    Aucun paiement ne pourra donc être encaissé."
            ))

        # ── 2. Réception ──────────────────────────────────────────────
        events = WebhookEvent.objects.filter(received_at__gte=since)
        total = events.count()
        self.stdout.write("")
        self.stdout.write(f"  Événements reçus depuis {options['hours']} h : {total}")

        if total == 0:
            self.stdout.write(self.style.WARNING(
                "  ⚠ Aucun événement reçu.\n"
                "    Soit personne n'a payé, soit le prestataire n'atteint pas\n"
                "    cette adresse — vérifiez qu'elle est publiquement joignable\n"
                "    (en développement : « stripe listen --forward-to … »)."
            ))
        else:
            by_status = events.values("status").annotate(n=Count("id"))
            for row in by_status:
                label = dict(WebhookEvent.STATUS_CHOICES).get(row["status"], row["status"])
                self.stdout.write(f"    · {label} : {row['n']}")

            failed = events.filter(status=WebhookEvent.FAILED)
            for record in failed[:10]:
                self.stdout.write(self.style.ERROR(
                    f"    ✗ {record.event_type} ({record.event_id}) : {record.detail[:120]}"
                ))

        # ── 3. Tentatives orphelines ──────────────────────────────────
        # Une tentative ouverte depuis plus d'une heure est le signe exact
        # d'un webhook qui n'arrive pas : la session Stripe expire au bout
        # de 24 h, mais le silence, lui, commence tout de suite.
        stale = PaymentTransaction.objects.filter(
            status__in=PaymentTransaction.OPEN_STATUSES,
            created_at__lte=timezone.now() - timedelta(hours=1),
            created_at__gte=since,
        )
        self.stdout.write("")
        if stale.exists():
            self.stdout.write(self.style.WARNING(
                f"  ⚠ {stale.count()} tentative(s) ouverte(s) depuis plus d'une heure :"
            ))
            for attempt in stale[:10]:
                self.stdout.write(
                    f"    · #{attempt.pk} {attempt.academy.code} "
                    f"{attempt.money.formatted()} — {attempt.get_status_display()} "
                    f"(créée le {attempt.created_at:%d/%m/%Y %H:%M})"
                )
            self.stdout.write(
                "    Si un parent affirme avoir payé l'une d'elles, l'événement\n"
                "    correspondant n'est pas arrivé : rejouez-le depuis le\n"
                "    tableau de bord du prestataire."
            )
        else:
            self.stdout.write(self.style.SUCCESS(
                "  ✓ Aucune tentative bloquée en attente."
            ))
        self.stdout.write("")
