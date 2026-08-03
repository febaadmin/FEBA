"""
Configuration guidée du paiement par carte.

POURQUOI UNE COMMANDE PLUTÔT QU'UN PARAGRAPHE DE DOCUMENTATION
--------------------------------------------------------------
Une documentation dit quoi écrire ; elle ne dit pas si c'est correct. Les
erreurs de configuration d'un prestataire de paiement sont silencieuses et
coûteuses : une clé de test en production encaisse zéro euro sans jamais
échouer visiblement, une clé de production en développement encaisse de
l'argent réel pendant une démonstration.

Cette commande écrit les clés, vérifie leur cohérence, et refuse les
combinaisons dangereuses.

CE QU'ELLE NE FAIT PAS
----------------------
Elle n'invente aucune clé et ne crée aucun compte. Les identifiants
viennent du tableau de bord du prestataire, obtenus par l'établissement.
Sans compte marchand valide, aucun encaissement réel n'est possible — et
aucune configuration ne peut y suppléer.
"""
import os
import re

from django.core.management.base import BaseCommand, CommandError

ENV_PATH_DEFAULT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.dirname(os.path.abspath(__file__)))))),
    ".env",
)

#: Préfixes officiels des clés Stripe. Le préfixe encode le mode : c'est
#: ce qui permet de détecter une clé de production posée par erreur dans
#: un environnement de test, et inversement.
KEY_PATTERNS = {
    "STRIPE_SECRET_KEY": re.compile(r"^sk_(test|live)_[A-Za-z0-9]+$"),
    "STRIPE_PUBLISHABLE_KEY": re.compile(r"^pk_(test|live)_[A-Za-z0-9]+$"),
    "STRIPE_WEBHOOK_SECRET": re.compile(r"^whsec_[A-Za-z0-9]+$"),
}


def key_mode(value):
    """« test », « live », ou None si le format est inconnu."""
    match = re.match(r"^(?:sk|pk)_(test|live)_", value or "")
    return match.group(1) if match else None


class Command(BaseCommand):
    help = "Configure le paiement par carte de façon guidée et vérifiée."

    def add_arguments(self, parser):
        parser.add_argument("--env-file", default=ENV_PATH_DEFAULT,
                            help="Fichier .env à écrire.")
        parser.add_argument("--secret-key", help="Clé secrète (sk_test_… ou sk_live_…).")
        parser.add_argument("--publishable-key", help="Clé publique (pk_test_… ou pk_live_…).")
        parser.add_argument("--webhook-secret", help="Secret de signature (whsec_…).")
        parser.add_argument("--public-base-url", help="URL publique de l'application.")
        parser.add_argument("--non-interactive", action="store_true",
                            help="Échoue au lieu de demander une valeur manquante.")

    # ── Saisie ────────────────────────────────────────────────────────

    def ask(self, options, key, label, help_text, required=True):
        value = options.get(key) or ""
        if value:
            return value.strip()
        if options["non_interactive"]:
            if required:
                raise CommandError(
                    f"{label} manquant. Fournissez --{key.replace('_', '-')}."
                )
            return ""
        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING(label))
        for line in help_text.splitlines():
            self.stdout.write(f"  {line}")
        return input("  > ").strip()

    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING(
            "\nConfiguration du paiement par carte (Stripe)\n"
        ))
        self.stdout.write(
            "Les clés se trouvent dans le tableau de bord Stripe, section\n"
            "« Développeurs → Clés API ». Cette commande ne crée aucun compte\n"
            "et n'invente aucune clé : sans compte marchand valide, aucun\n"
            "encaissement réel n'est possible.\n"
        )

        secret = self.ask(
            options, "secret_key", "Clé secrète",
            "Commence par sk_test_ (mode test) ou sk_live_ (production).\n"
            "Elle ne doit JAMAIS être exposée au navigateur ni commitée.",
        )
        publishable = self.ask(
            options, "publishable_key", "Clé publique",
            "Commence par pk_test_ ou pk_live_. Celle-ci peut être publique.",
        )
        webhook = self.ask(
            options, "webhook_secret", "Secret de signature du webhook",
            "Commence par whsec_. Obtenu en créant le point de terminaison\n"
            "dans « Développeurs → Webhooks », ou via « stripe listen ».\n"
            "Sans lui, tous les événements seront REFUSÉS : c'est voulu.",
        )
        base_url = self.ask(
            options, "public_base_url", "URL publique de l'application",
            "Ex. https://ecole.exemple.org — utilisée pour les pages de retour\n"
            "et l'adresse du webhook.", required=False,
        ) or "http://localhost:5173"

        errors = self.validate(secret, publishable, webhook)
        if errors:
            for error in errors:
                self.stdout.write(self.style.ERROR(f"  ✗ {error}"))
            raise CommandError(
                "Configuration refusée. Aucune clé n'a été écrite : une "
                "configuration à moitié juste est pire qu'absente."
            )

        mode = key_mode(secret)
        self.write_env(options["env_file"], {
            "CARD_PAYMENTS_ENABLED": "True",
            "PAYMENT_PROVIDER": "stripe",
            "STRIPE_MODE": mode or "test",
            "STRIPE_SECRET_KEY": secret,
            "STRIPE_PUBLISHABLE_KEY": publishable,
            "STRIPE_WEBHOOK_SECRET": webhook,
            "PUBLIC_BASE_URL": base_url,
        })

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(
            f"  ✓ Configuration écrite dans {options['env_file']} (mode {mode})."
        ))
        if mode == "live":
            self.stdout.write(self.style.WARNING(
                "  ⚠ Mode PRODUCTION : les paiements débiteront réellement les "
                "cartes.\n    Vérifiez que le compte marchand est bien activé "
                "chez le prestataire."
            ))
        self.stdout.write(
            "\nÉtapes suivantes :\n"
            "  1. Redémarrez le serveur pour recharger l'environnement.\n"
            "  2. « make payments-check » vérifie que les identifiants sont acceptés.\n"
            f"  3. Déclarez le webhook : {base_url.rstrip('/')}/api/payments/webhook/stripe/\n"
            "     Événements : checkout.session.completed, checkout.session.expired,\n"
            "     payment_intent.succeeded, payment_intent.payment_failed,\n"
            "     payment_intent.canceled, charge.refunded.\n"
        )

    # ── Vérifications ─────────────────────────────────────────────────

    def validate(self, secret, publishable, webhook):
        errors = []
        values = {
            "STRIPE_SECRET_KEY": secret,
            "STRIPE_PUBLISHABLE_KEY": publishable,
            "STRIPE_WEBHOOK_SECRET": webhook,
        }
        for name, value in values.items():
            if not value:
                errors.append(f"{name} est vide.")
            elif not KEY_PATTERNS[name].match(value):
                errors.append(
                    f"{name} n'a pas le format attendu "
                    f"({KEY_PATTERNS[name].pattern})."
                )

        # Mélanger test et production est l'erreur la plus coûteuse : la
        # session serait créée dans un mode et jamais confirmée dans l'autre.
        modes = {key_mode(secret), key_mode(publishable)} - {None}
        if len(modes) > 1:
            errors.append(
                "La clé secrète et la clé publique ne sont pas dans le même "
                "mode (test / production) : les paiements créés dans l'un ne "
                "seraient jamais confirmés dans l'autre."
            )
        if secret.startswith("pk_") or publishable.startswith("sk_"):
            errors.append(
                "Les clés secrète et publique semblent inversées. Exposer une "
                "clé secrète au navigateur donnerait à quiconque le contrôle "
                "du compte marchand."
            )
        return errors

    # ── Écriture ──────────────────────────────────────────────────────

    def write_env(self, path, values):
        """
        Met à jour les clés en place, sans réécrire le fichier.

        Réécrire écraserait les réglages voisins (base de données, e-mail).
        Une commande de configuration qui casse la configuration existante
        n'est pas une aide.
        """
        lines = []
        if os.path.exists(path):
            with open(path, encoding="utf-8") as handle:
                lines = handle.read().splitlines()

        remaining = dict(values)
        output = []
        for line in lines:
            key = line.split("=", 1)[0].strip() if "=" in line else ""
            if key in remaining:
                output.append(f"{key}={remaining.pop(key)}")
            else:
                output.append(line)

        if remaining:
            output.append("")
            output.append("# --- Paiement par carte (généré par payments_setup) ---")
            output.extend(f"{key}={value}" for key, value in remaining.items())

        with open(path, "w", encoding="utf-8") as handle:
            handle.write("\n".join(output).rstrip() + "\n")
        # Les clés secrètes ne concernent que le compte qui fait tourner le
        # service : lecture seule pour lui, rien pour les autres.
        try:
            os.chmod(path, 0o600)
        except OSError:  # pragma: no cover — dépend du système de fichiers
            pass
