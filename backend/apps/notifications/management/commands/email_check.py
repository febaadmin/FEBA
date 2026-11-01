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
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Diagnostique la configuration d'envoi des e-mails."

    def add_arguments(self, parser):
        parser.add_argument(
            "--to", default=None,
            help="Adresse de destination d'un e-mail de test RÉEL.",
        )

    def handle(self, *args, **options):
        from apps.notifications.outbox_views import email_configuration, smtp_reachability

        config = email_configuration()
        self.stdout.write(self.style.MIGRATE_HEADING("\nConfiguration d'envoi EFFECTIVE\n"))
        self.stdout.write(f"  Transport Django : {config['transport_backend']}")
        self.stdout.write(f"  Qualification    : {config['transport_display']}")
        self.stdout.write(f"  Hôte:port        : {config['host'] or '-'}:{config['port']}")
        self.stdout.write(f"  TLS / SSL        : {config['use_tls']} / {config['use_ssl']}")
        self.stdout.write(f"  Utilisateur      : {config['user'] or '(aucun)'}")
        self.stdout.write(f"  Mot de passe     : {'défini (masqué)' if config['password_set'] else 'vide'}")
        self.stdout.write(f"  Expéditeur       : {config['default_from'] or '-'}")
        self.stdout.write(f"  Délai max        : {config['timeout']} s")
        for row in config["academy_senders"]:
            self.stdout.write(f"  Expéditeur {row['code'] or '-'} : {row['from'] or 'aucun'}")
        self.stdout.write("")
        self.stdout.write(config["explanation"])
        if config["capture_ui_url"]:
            self.stdout.write(self.style.WARNING(
                f"Messages lisibles dans Mailpit : {config['capture_ui_url']} "
                "(ils n'atteignent AUCUNE boîte réelle)."
            ))

        reach = smtp_reachability()
        if reach["checked"]:
            style = self.style.SUCCESS if reach["reachable"] else self.style.ERROR
            self.stdout.write(style(f"  Réseau : {reach['detail']}"))

        target = options["to"]
        if not target:
            self.stdout.write("\nPour éprouver l'envoi : manage.py email_check --to vous@exemple.test")
            return

        self.stdout.write(self.style.MIGRATE_HEADING(f"\nEnvoi de test vers {target}\n"))
        from apps.notifications.mailer import send_tracked_email

        delivery = send_tracked_email(
            purpose="email_check", to_email=target, subject="Test de configuration - FEBA",
            text_body=("Ce message confirme que la configuration d'envoi fonctionne.\n"
                       "Si vous le recevez, le serveur peut joindre son fournisseur."),
            html_body="<p>Ce message confirme que la configuration d'envoi fonctionne.</p>",
            entity=None, reference="email_check",
        )
        self.stdout.write(f"  État        : {delivery.get_status_display()}")
        self.stdout.write(f"  Résultat    : {delivery.delivery_summary()}")
        self.stdout.write(f"  Suivi       : {delivery.tracking_id}")
        if delivery.last_error:
            self.stdout.write(self.style.ERROR(f"  Erreur      : {delivery.last_error}"))
            self.stderr.write(self.style.ERROR("\nL'envoi a échoué."))
            raise SystemExit(1)
        if not delivery.used_real_provider:
            self.stdout.write(self.style.WARNING(
                "\nCe message n'est PAS parti sur Internet (transport de test ou local)."
            ))
            raise SystemExit(2)
        self.stdout.write(self.style.SUCCESS(
            "\nLe serveur de messagerie a ACCEPTÉ le message. Cela ne garantit pas sa "
            "distribution : vérifiez la boîte de réception (et les indésirables)."
        ))
