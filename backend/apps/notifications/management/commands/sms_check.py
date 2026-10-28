"""
manage.py sms_check [--to +229…]

Diagnostic SMS SANS secret affiché : fournisseur, numéro d'expédition,
appartenance du numéro au compte Twilio et droit d'envoyer des SMS. Avec
--to, envoie UN SMS de test au numéro indiqué (à n'utiliser que vers un
numéro autorisé).

Codes de sortie : 0 numéro vérifié (et SMS accepté si --to) ; 1 échec ;
2 transport de test (capture/console) — rien n'est parti.
"""
from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Vérifie la configuration SMS et le numéro d'expédition."

    def add_arguments(self, parser):
        parser.add_argument("--to", help="Numéro E.164 qui recevra un SMS de test.")

    def handle(self, *args, **options):
        from apps.notifications.sms_providers import SmsProviderError, get_provider

        provider = get_provider()
        sid = settings.TWILIO_ACCOUNT_SID
        self.stdout.write(self.style.MIGRATE_HEADING("Configuration SMS EFFECTIVE"))
        self.stdout.write(f"  SMS_ENABLED     : {settings.SMS_ENABLED}")
        self.stdout.write(f"  Fournisseur     : {provider.name}")
        self.stdout.write(f"  Expéditeur      : {settings.SMS_FROM_NUMBER or '(non défini)'}")
        self.stdout.write(f"  Compte Twilio   : {(sid[:4] + '…' + sid[-4:]) if sid else '(non défini)'}")
        self.stdout.write(f"  Jeton Twilio    : {'défini' if settings.TWILIO_AUTH_TOKEN else 'absent'}")
        self.stdout.write(f"  Consentement    : {'explicite requis' if settings.SMS_REQUIRE_EXPLICIT_CONSENT else 'tous sauf refus'}")
        self.stdout.write(f"  Accusés remise  : {settings.SMS_STATUS_CALLBACK_URL or '(désactivés)'}")
        if getattr(provider, "captured", False):
            self.stdout.write(self.style.WARNING(
                "\nTransport de TEST : les SMS sont enregistrés dans FEBA et ne partent JAMAIS."))
            raise SystemExit(2)
        if not settings.SMS_FROM_NUMBER:
            self.stderr.write(self.style.ERROR("SMS_FROM_NUMBER n'est pas défini."))
            raise SystemExit(1)
        try:
            check = provider.verify_sender(settings.SMS_FROM_NUMBER)
        except SmsProviderError as exc:
            self.stderr.write(self.style.ERROR(f"Vérification du numéro impossible : {exc}"))
            raise SystemExit(1)
        style = self.style.SUCCESS if check["owned"] and check["sms"] else self.style.ERROR
        self.stdout.write(style(f"  Numéro          : {check['detail']}"))
        if not (check["owned"] and check["sms"]):
            raise SystemExit(1)
        target = options.get("to")
        if not target:
            self.stdout.write("\nPour un essai réel : manage.py sms_check --to +229XXXXXXXXXX")
            return
        try:
            message_id, state = provider.send(target, settings.SMS_FROM_NUMBER,
                                              "FEBA — test de configuration SMS. Merci d'ignorer ce message.")
        except SmsProviderError as exc:
            self.stderr.write(self.style.ERROR(f"Envoi refusé : {exc}"))
            raise SystemExit(1)
        self.stdout.write(self.style.SUCCESS(
            f"\nSMS ACCEPTÉ par Twilio (identifiant {message_id}, état « {state} »). La réception se "
            "constate sur le téléphone ou dans la console Twilio (Messaging > Logs)."))
