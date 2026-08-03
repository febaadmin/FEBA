"""
Vérifie que le paiement par carte est réellement opérationnel.

La question à laquelle cette commande répond n'est pas « les variables
sont-elles renseignées » — un fichier `.env` bien rempli avec une clé
révoquée passe ce test-là. La question est : **le prestataire nous
reconnaît-il, et dans quel mode.**

C'est pourquoi la vérification appelle réellement l'API du prestataire
(en lecture seule, sans créer ni débiter quoi que ce soit) lorsque le
réseau est disponible, et le dit franchement quand il ne l'est pas.
"""
from django.conf import settings
from django.core.management.base import BaseCommand

from apps.payments.providers import (
    PaymentProviderNotConfigured, get_provider,
)


class Command(BaseCommand):
    help = "Vérifie la configuration et les identifiants du paiement par carte."

    def add_arguments(self, parser):
        parser.add_argument(
            "--offline", action="store_true",
            help="N'appelle pas le prestataire ; vérifie seulement la configuration locale.",
        )
        parser.add_argument(
            "--strict", action="store_true",
            help="Code de sortie non nul si une vérification échoue (intégration continue).",
        )

    def handle(self, *args, **options):
        failures = []
        self.stdout.write(self.style.MIGRATE_HEADING(
            "\nVérification du paiement par carte\n"
        ))

        enabled = getattr(settings, "CARD_PAYMENTS_ENABLED", False)
        self.line("Paiement par carte activé", enabled,
                  "CARD_PAYMENTS_ENABLED=False — le bouton de paiement reste masqué.")
        if not enabled:
            self.stdout.write(
                "\n  Le paiement par carte est désactivé sur cette instance.\n"
                "  Lancez « make payments-setup » pour le configurer.\n"
            )
            return

        for name in ("STRIPE_SECRET_KEY", "STRIPE_PUBLISHABLE_KEY",
                     "STRIPE_WEBHOOK_SECRET"):
            present = bool(getattr(settings, name, ""))
            self.line(f"{name} renseignée", present, f"{name} est vide.")
            if not present:
                failures.append(name)

        mode = getattr(settings, "STRIPE_MODE", "test")
        secret = getattr(settings, "STRIPE_SECRET_KEY", "")
        coherent = not secret or secret.startswith(f"sk_{mode}_")
        self.line(f"Mode « {mode} » cohérent avec la clé", coherent,
                  "La clé secrète n'appartient pas au mode déclaré : les "
                  "paiements créés ne seraient jamais confirmés.")
        if not coherent:
            failures.append("STRIPE_MODE")

        base_url = getattr(settings, "PUBLIC_BASE_URL", "")
        secure = base_url.startswith("https://")
        if mode == "live":
            self.line("URL publique en HTTPS", secure,
                      "En production, les pages de retour et le webhook "
                      "doivent être servis en HTTPS.")
            if not secure:
                failures.append("PUBLIC_BASE_URL")
        else:
            self.stdout.write(f"  · URL publique : {base_url or '(non définie)'}")

        # ── Le prestataire nous reconnaît-il ? ────────────────────────
        if options["offline"]:
            self.stdout.write(
                "\n  Mode hors ligne : les identifiants n'ont PAS été soumis au "
                "prestataire.\n  Une clé bien formée peut être révoquée — seul "
                "« make payments-check » en ligne le dira.\n"
            )
        elif not failures:
            failures.extend(self.check_credentials())

        self.stdout.write("")
        if failures:
            self.stdout.write(self.style.ERROR(
                f"  {len(failures)} vérification(s) en échec : "
                f"{', '.join(dict.fromkeys(failures))}"
            ))
            if options["strict"]:
                raise SystemExit(1)
        else:
            self.stdout.write(self.style.SUCCESS(
                "  Configuration du paiement par carte conforme."
            ))
            self.stdout.write(
                f"  Webhook attendu : {base_url.rstrip('/')}"
                f"/api/payments/webhook/stripe/\n"
            )

    def check_credentials(self):
        """Appel en LECTURE SEULE : rien n'est créé, rien n'est débité."""
        try:
            provider = get_provider()
            stripe = provider._stripe()
            account = stripe.Account.retrieve()
        except PaymentProviderNotConfigured as exc:
            self.line("Identifiants acceptés par le prestataire", False, str(exc))
            return ["provider"]
        except Exception as exc:
            message = str(exc)
            if "Invalid API Key" in message or "authentication" in message.lower():
                self.line("Identifiants acceptés par le prestataire", False,
                          "Clé refusée par le prestataire (révoquée ou erronée).")
                return ["STRIPE_SECRET_KEY"]
            # Une panne réseau n'est pas une configuration invalide : le
            # dire clairement évite de faire chercher une erreur qui
            # n'existe pas.
            self.stdout.write(self.style.WARNING(
                f"  ? Prestataire injoignable ({message[:120]}).\n"
                "    La configuration locale est correcte ; les identifiants "
                "n'ont pas pu être vérifiés."
            ))
            return []

        self.line("Identifiants acceptés par le prestataire", True, "")
        charges = getattr(account, "charges_enabled", None)
        if charges is False:
            self.stdout.write(self.style.WARNING(
                "  ⚠ Le compte marchand n'est pas encore autorisé à encaisser.\n"
                "    Les paiements de TEST fonctionneront ; les paiements réels "
                "seront refusés\n    tant que le prestataire n'a pas validé le "
                "dossier de l'établissement."
            ))
        return []

    def line(self, label, ok, failure_hint):
        if ok:
            self.stdout.write(self.style.SUCCESS(f"  ✓ {label}"))
        else:
            self.stdout.write(self.style.ERROR(f"  ✗ {label}"))
            if failure_hint:
                self.stdout.write(f"    {failure_hint}")
