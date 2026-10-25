"""
Adresse d'expédition : noreply@globalfeba.com sur TOUS les chemins d'envoi.

L'adresse noreply@feba.bj est retirée. Ces tests envoient réellement par
chaque chemin de FEBA (backend mémoire de Django) et lisent l'en-tête From
du message produit — pas une variable de configuration :

  e-mail groupé · relance de paiement · accusé FHA au parent et alerte
  admin · notification FHA (test de niveau) · envoi direct send_mail ·
  alerte d'erreur Django (mail_admins) · nouvel essai d'un envoi créé
  avant le changement · envoi de test SMTP.

Les rapports mensuels sont couverts dans test_monthly_reports.py.
"""
from datetime import date as D

from django.core import mail
from django.core.mail import mail_admins, send_mail
from django.test import TestCase, override_settings

from apps.notifications.email_models import EmailDelivery
from apps.notifications.mailer import (
    OFFICIAL_NOREPLY, create_delivery, deliver, normalize_sender, send_tracked_email, sender_for,
)
from tests import test_audit_p1_confirmation_emails as conf
from tests import test_audit_p1_payment_reminders as rem
from tests import test_email_outbox as outbox

OFFICIAL = "noreply@globalfeba.com"
TRACKING = "apps.notifications.backends.TrackingEmailBackend"
LOCMEM = "django.core.mail.backends.locmem.EmailBackend"
ROUTING = dict(EMAIL_BACKEND=TRACKING, EMAIL_TRANSPORT_BACKEND=LOCMEM,
               DEFAULT_FROM_EMAIL=OFFICIAL, FEBA_FROM_EMAIL="", FHA_FROM_EMAIL="", SERVER_EMAIL=OFFICIAL)


def senders():
    return {m.from_email for m in mail.outbox}


class DefaultsTests(TestCase):
    def test_valeurs_par_defaut_du_code(self):
        import feba_project.settings.base as base
        source = open(base.__file__, encoding="utf-8").read()
        self.assertIn("DEFAULT_FROM_EMAIL = config('DEFAULT_FROM_EMAIL', default='noreply@globalfeba.com')", source)
        self.assertIn("SERVER_EMAIL = config('SERVER_EMAIL', default=DEFAULT_FROM_EMAIL)", source)
        self.assertEqual(OFFICIAL_NOREPLY, OFFICIAL)

    def test_exemples_de_configuration(self):
        from tests.repo_root import read_repo_file
        for name in (".env.example", ".env.dev.example", ".env.prod.example"):
            text = read_repo_file(name)
            with self.subTest(fichier=name):
                self.assertNotIn("noreply@feba.bj", text)
                self.assertIn("DEFAULT_FROM_EMAIL=noreply@globalfeba.com", text)

    @override_settings(DEFAULT_FROM_EMAIL="noreply@feba.bj", FEBA_FROM_EMAIL="", FHA_FROM_EMAIL="")
    def test_ancienne_adresse_dans_l_environnement_jamais_utilisee(self):
        self.assertEqual(sender_for(None), OFFICIAL)
        self.assertEqual(normalize_sender("FEBA <noreply@feba.bj>"), f"FEBA <{OFFICIAL}>")
        self.assertEqual(normalize_sender("contact@globalfeba.com"), "contact@globalfeba.com")

    @override_settings(DEFAULT_FROM_EMAIL="noreply@feba.bj")
    def test_check_signale_l_adresse_retiree(self):
        from apps.notifications.checks import email_sender_configuration
        self.assertIn("notifications.W001", [w.id for w in email_sender_configuration(None)])

    @override_settings(EMAIL_BACKEND=TRACKING, EMAIL_TRANSPORT_BACKEND="django.core.mail.backends.smtp.EmailBackend",
                       EMAIL_HOST_USER="contact@autre-domaine.com", DEFAULT_FROM_EMAIL=OFFICIAL,
                       FEBA_FROM_EMAIL="", FHA_FROM_EMAIL="")
    def test_check_signale_un_expediteur_hors_du_compte_smtp(self):
        from apps.notifications.checks import email_sender_configuration
        self.assertIn("notifications.W002", [w.id for w in email_sender_configuration(None)])

    @override_settings(EMAIL_BACKEND=TRACKING, EMAIL_TRANSPORT_BACKEND="django.core.mail.backends.smtp.EmailBackend",
                       EMAIL_HOST_USER=OFFICIAL, DEFAULT_FROM_EMAIL=OFFICIAL, SERVER_EMAIL=OFFICIAL,
                       FEBA_FROM_EMAIL="", FHA_FROM_EMAIL="")
    def test_configuration_hostinger_coherente_aucun_avertissement(self):
        from apps.notifications.checks import email_sender_configuration
        self.assertEqual(email_sender_configuration(None), [])


@override_settings(**ROUTING)
class EveryPathTests(outbox.PrivateMediaMixin, TestCase):
    def test_envoi_central(self):
        send_tracked_email(purpose="t", to_email="a@test.io", subject="s", text_body="b")
        self.assertEqual(senders(), {OFFICIAL})

    @override_settings(DEFAULT_FROM_EMAIL="noreply@feba.bj")
    def test_ancienne_adresse_configuree_corrigee_a_l_envoi(self):
        send_tracked_email(purpose="t", to_email="a@test.io", subject="s", text_body="b")
        self.assertEqual(senders(), {OFFICIAL})
        self.assertEqual(EmailDelivery.objects.get().from_email, OFFICIAL)

    def test_envoi_en_file_cree_avant_le_changement(self):
        d = create_delivery(purpose="t", to_email="a@test.io", subject="s", text_body="b")
        EmailDelivery.objects.filter(pk=d.pk).update(from_email="noreply@feba.bj")
        d.refresh_from_db()
        deliver(d)
        self.assertEqual(senders(), {OFFICIAL})

    def test_send_mail_direct_d_un_module(self):
        send_mail("Sujet", "Corps", "noreply@feba.bj", ["x@test.io"])
        send_mail("Sujet", "Corps", None, ["y@test.io"])
        self.assertEqual(senders(), {OFFICIAL})

    @override_settings(ADMINS=[("Ops", "ops@test.io")], SERVER_EMAIL="noreply@feba.bj")
    def test_alerte_d_erreur_django(self):
        mail_admins("Erreur 500", "Trace")
        self.assertEqual(senders(), {OFFICIAL})

    def test_notification_fha(self):
        from apps.website.fha_notifications import _send
        _send("Test de niveau", "Corps", ["parent@test.io"], entity=None, reference="FHA-X")
        self.assertEqual(senders(), {OFFICIAL})


@override_settings(**ROUTING)
class CampaignPathTests(outbox.OutboxBase):
    def test_email_groupe(self):
        resp = self.campaign(self.admin_a, self.a)
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertTrue(mail.outbox)
        self.assertEqual(senders(), {OFFICIAL})


@override_settings(**ROUTING)
class ReminderPathTests(rem.ReminderBase):
    def test_relance_de_paiement(self):
        self.run_engine(D(2026, 10, 9))
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(senders(), {OFFICIAL})


@override_settings(**ROUTING)
class FhaEnrollmentPathTests(conf.ConfirmationBase):
    def test_accuse_parent_et_alerte_admin(self):
        mail.outbox.clear()
        conf.submit("Lina", email="parent.lina@example.org")
        self.assertTrue(any(m.to == ["parent.lina@example.org"] for m in mail.outbox))
        self.assertEqual(senders(), {OFFICIAL})


@override_settings(**ROUTING)
class SmtpTestPathTests(outbox.OutboxBase):
    def test_envoi_de_test_depuis_la_boite_d_envoi(self):
        from django.core.cache import cache
        cache.clear()
        r = self.api(self.admin_a).post("/api/notifications/email-config/test/", {"to": "moi@test.io"},
                                        format="json")
        self.assertIn(r.status_code, (200, 201), r.content)
        self.assertEqual(senders(), {OFFICIAL})
