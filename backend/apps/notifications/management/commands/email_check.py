"""
Vérifie la configuration d'envoi des e-mails, et l'éprouve pour de vrai.

    python manage.py email_check                    # diagnostic seul
    python manage.py email_check --to a@b.test      # envoi de test réel

CE QUE CETTE COMMANDE REFUSE DE FAIRE
-------------------------------------
Annoncer un succès quand le backend configuré est `console` ou `locmem`.
Un e-mail écrit dans la console du serveur n'est pas un e-mail envoyé, et
un rapport qui les confond rend la vérification inutile — c'est
exactement l'erreur que ce projet corrige ailleurs.
"""
from django.conf import settings
from django.core.management.base import BaseCommand

from apps.notifications.mailer import provider_is_configured, sender_for
from apps.schools.models import School

#: Réglages attendus, avec ce que leur absence provoque.
EXPECTED = [
    ("EMAIL_BACKEND", "Sans lui, Django écrit les messages dans la console."),
    ("EMAIL_HOST", "Adresse du serveur SMTP."),
    ("EMAIL_PORT", "Port SMTP (587 pour STARTTLS, 465 pour SSL)."),
    ("EMAIL_HOST_USER", "Compte d'authentification SMTP."),
    ("EMAIL_HOST_PASSWORD", "Mot de passe ou jeton d'application."),
    ("EMAIL_USE_TLS", "Chiffrement de la connexion."),
    ("EMAIL_TIMEOUT", "Sans délai maximal, une requête peut rester bloquée."),
    ("DEFAULT_FROM_EMAIL", "Expéditeur par défaut."),
    ("FEBA_FROM_EMAIL", "Expéditeur propre à FEBA (facultatif)."),
    ("FHA_FROM_EMAIL", "Expéditeur propre à FEBA FHA (facultatif)."),
    ("EMAIL_REPLY_TO", "Adresse de réponse (facultative)."),
]

#: Réglages dont la valeur ne doit JAMAIS être affichée.
SECRETS = {"EMAIL_HOST_PASSWORD"}


class Command(BaseCommand):
    help = "Diagnostique la configuration d'envoi des e-mails."

    def add_arguments(self, parser):
        parser.add_argument(
            "--to", default=None,
            help="Adresse de destination d'un e-mail de test RÉEL.",
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING("\nConfiguration d'envoi\n"))

        for name, why in EXPECTED:
            value = getattr(settings, name, None)
            if name in SECRETS:
                shown = "défini" if value else ""
            else:
                shown = "" if value in (None, "") else str(value)
            if shown:
                self.stdout.write(self.style.SUCCESS(f"  ✓ {name} = {shown}"))
            else:
                self.stdout.write(self.style.WARNING(f"  · {name} — non défini. {why}"))

        self.stdout.write("")
        for academy in School.objects.order_by("id"):
            self.stdout.write(
                f"  Expéditeur de {academy.name} [{academy.code or '—'}] : "
                f"{sender_for(academy) or 'aucun'}"
            )

        self.stdout.write("")
        if provider_is_configured():
            self.stdout.write(self.style.SUCCESS(
                "Un fournisseur d'envoi réel est configuré."
            ))
        else:
            self.stdout.write(self.style.WARNING(
                f"AUCUN fournisseur d'envoi réel : le backend est "
                f"« {settings.EMAIL_BACKEND} ». Les messages sont enregistrés "
                f"et visibles dans l'administration, mais ils NE PARTENT PAS "
                f"sur Internet. Ne présentez aucun envoi comme réel dans cet état."
            ))

        target = options["to"]
        if not target:
            self.stdout.write(
                "\nPour éprouver l'envoi : manage.py email_check --to vous@exemple.test"
            )
            return

        self.stdout.write(self.style.MIGRATE_HEADING(
            f"\nEnvoi de test vers {target}\n"
        ))
        from apps.notifications.mailer import send_tracked_email

        delivery = send_tracked_email(
            purpose="email_check",
            to_email=target,
            subject="Test de configuration — FEBA",
            text_body=(
                "Ce message confirme que la configuration d'envoi fonctionne.\n"
                "Si vous le recevez, le serveur peut joindre son fournisseur."
            ),
            html_body=(
                "<p>Ce message confirme que la configuration d'envoi "
                "fonctionne.</p>"
            ),
            entity=School.objects.filter(code=School.CODE_FEBA).first(),
            reference="email_check",
        )

        self.stdout.write(f"  État        : {delivery.get_status_display()}")
        self.stdout.write(f"  Suivi       : {delivery.tracking_id}")
        self.stdout.write(f"  Backend     : {delivery.backend}")
        if delivery.last_error:
            self.stdout.write(self.style.ERROR(f"  Erreur      : {delivery.last_error}"))

        if not delivery.used_real_provider:
            self.stdout.write(self.style.WARNING(
                "\nCe message n'est PAS parti sur Internet : le backend "
                "configuré est un backend de développement."
            ))
            raise SystemExit(1)

        if delivery.is_delivered_to_provider:
            self.stdout.write(self.style.SUCCESS(
                "\nLe fournisseur a accepté le message. Cela ne garantit pas "
                "sa distribution : vérifiez la boîte de réception."
            ))
            return

        self.stderr.write(self.style.ERROR("\nL'envoi a échoué."))
        raise SystemExit(1)
