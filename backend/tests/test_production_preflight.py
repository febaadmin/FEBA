"""
Contrôle de pré-démarrage : une configuration de production incomplète ou
de développement REFUSE le démarrage (code de sortie 1), avec la raison.
"""
from io import StringIO

from django.core.management import call_command
from django.test import SimpleTestCase, override_settings

from apps.core.preflight import ERROR, fingerprint, problems

GOOD = dict(
    DEPLOYMENT_STAGE="production", DEBUG=False,
    SECRET_KEY="k" * 30 + "Zq8vT2mX9pL4wR7nB1cY6",
    ALLOWED_HOSTS=["globalfeba.com", "www.globalfeba.com"],
    DATABASES={"default": {"ENGINE": "django.db.backends.postgresql", "NAME": "feba_prod",
                           "HOST": "postgres-prod", "PORT": "5432"}},
    REDIS_URL="redis://redis-prod:6379/0", PUBLIC_BASE_URL="https://globalfeba.com",
    EMAIL_BACKEND="apps.notifications.backends.TrackingEmailBackend",
    EMAIL_TRANSPORT_BACKEND="django.core.mail.backends.smtp.EmailBackend",
    EMAIL_HOST="smtp.hostinger.com", EMAIL_HOST_USER="noreply@globalfeba.com",
    EMAIL_HOST_PASSWORD="mot-de-passe-test", EMAIL_DELIVERY_MODE="auto",
    DEFAULT_FROM_EMAIL="noreply@globalfeba.com", SERVER_EMAIL="noreply@globalfeba.com",
    FEBA_FROM_EMAIL="", FHA_FROM_EMAIL="",
    VIDEO_PROVIDER="plugnmeet", PLUGNMEET_SERVER_URL="https://meet.globalfeba.com",
    PLUGNMEET_API_KEY="APIabcdef12345", PLUGNMEET_API_SECRET="s" * 40,
    PLUGNMEET_WEBHOOK_URL="https://globalfeba.com/api/virtual-rooms/webhook/",
    SMS_ENABLED=True, SMS_PROVIDER="twilio", SMS_FROM_NUMBER="+12157155406",
    TWILIO_ACCOUNT_SID="AC" + "0" * 32, TWILIO_AUTH_TOKEN="t" * 32,
    SMS_STATUS_CALLBACK_URL="https://globalfeba.com/api/notifications/sms/status/",
    PAYMENT_REMINDERS_ENABLED=True,
)


def codes(level=ERROR):
    return {code for lvl, code, _ in problems() if lvl == level}


class PreflightTests(SimpleTestCase):
    @override_settings(**GOOD)
    def test_configuration_complete_acceptee(self):
        self.assertEqual(codes(), set())
        call_command("production_preflight", stdout=StringIO())

    def assert_refused(self, code, **overrides):
        with override_settings(**{**GOOD, **overrides}):
            self.assertIn(code, codes())
            with self.assertRaises(SystemExit) as ctx:
                call_command("production_preflight", stdout=StringIO(), stderr=StringIO())
            self.assertEqual(ctx.exception.code, 1)

    def test_valeurs_de_developpement_refusees(self):
        self.assert_refused("email_transport", EMAIL_TRANSPORT_BACKEND="django.core.mail.backends.console.EmailBackend")
        self.assert_refused("email_capture", EMAIL_HOST="mailpit")
        self.assert_refused("public_base_url", PUBLIC_BASE_URL="http://localhost:5173")
        self.assert_refused("debug", DEBUG=True)
        self.assert_refused("redis", REDIS_URL="redis://localhost:6379/0")
        self.assert_refused("sms_provider", SMS_PROVIDER="capture")

    def test_secrets_manquants_refuses(self):
        self.assert_refused("secret_key", SECRET_KEY="CHANGE_ME_GENERATE_A_STRONG_SECRET_KEY")
        self.assert_refused("email_credentials", EMAIL_HOST_PASSWORD="")
        self.assert_refused("plugnmeet_credentials", PLUGNMEET_API_SECRET="")
        self.assert_refused("sms_credentials", TWILIO_AUTH_TOKEN="")

    def test_incoherences_refusees(self):
        self.assert_refused("allowed_hosts", ALLOWED_HOSTS=["*"])
        self.assert_refused("plugnmeet_url", PLUGNMEET_SERVER_URL="http://meet.globalfeba.com")
        self.assert_refused("plugnmeet_webhook",
                            PLUGNMEET_WEBHOOK_URL="https://autre-domaine.com/api/virtual-rooms/webhook/")
        self.assert_refused("email_sender_obsolete", DEFAULT_FROM_EMAIL="noreply@feba.bj")
        self.assert_refused("email_sender_domain", EMAIL_HOST_USER="contact@autre.com")
        self.assert_refused("sms_from", SMS_FROM_NUMBER="2157155406")
        self.assert_refused("video_provider", VIDEO_PROVIDER="zoom")
        # Domaine des classes et retour à Jitsi : jamais par accident.
        self.assert_refused("plugnmeet_domain", PLUGNMEET_SERVER_URL="https://pnm.globalfeba.com")
        self.assert_refused("video_rollback", VIDEO_PROVIDER="jitsi")

    def test_retour_jitsi_delibere_seulement_signale(self):
        with override_settings(**{**GOOD, "VIDEO_PROVIDER": "jitsi", "VIDEO_ROLLBACK_JITSI": True}):
            self.assertNotIn("video_rollback", codes())
            self.assertIn("video_rollback", codes("WARNING"))
        self.assert_refused("database", DATABASES={"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": "x"}})

    def test_preproduction_tolere_les_transports_de_test_en_avertissement(self):
        with override_settings(**{**GOOD, "DEPLOYMENT_STAGE": "staging", "EMAIL_HOST": "mailpit",
                                  "SMS_PROVIDER": "capture"}):
            self.assertEqual(codes(), set())
            self.assertTrue({"email_capture", "sms_provider"} <= codes("WARNING"))

    @override_settings(**{**GOOD, "SMS_ENABLED": False})
    def test_sms_desactives_signales_sans_bloquer(self):
        self.assertEqual(codes(), set())
        self.assertIn("sms_disabled", codes("WARNING"))

    def test_empreinte_identique_pour_une_meme_configuration_et_sans_secret(self):
        with override_settings(**GOOD):
            a = fingerprint()
        with override_settings(**GOOD):
            self.assertEqual(a, fingerprint())
        with override_settings(**{**GOOD, "TWILIO_AUTH_TOKEN": "u" * 32}):
            self.assertNotEqual(a, fingerprint())
        out = StringIO()
        with override_settings(**GOOD):
            call_command("production_preflight", stdout=out)
        self.assertNotIn("mot-de-passe-test", out.getvalue())
        self.assertNotIn("s" * 40, out.getvalue())


class HealthBehindTlsRedirectTests(SimpleTestCase):
    """La route de santé répond en HTTP direct malgré SECURE_SSL_REDIRECT."""

    def test_route_de_sante_exemptee_de_la_redirection_https(self):
        from tests.repo_root import read_repo_file
        prod = read_repo_file("backend", "feba_project", "settings", "prod.py")
        self.assertIn("SECURE_REDIRECT_EXEMPT = [r'^api/health/$']", prod)
        from django.test import Client
        # Un client NEUF par réglage : le middleware lit les réglages à son chargement.
        with override_settings(SECURE_SSL_REDIRECT=True, SECURE_REDIRECT_EXEMPT=[r'^api/health/$']):
            client = Client()
            self.assertNotIn(client.get("/api/health/").status_code, (301, 302))
            self.assertEqual(client.get("/api/auth/me/").status_code, 301)   # le reste reste protégé
        with override_settings(SECURE_SSL_REDIRECT=True, SECURE_REDIRECT_EXEMPT=[]):
            self.assertEqual(Client().get("/api/health/").status_code, 301)  # défaut d'origine
