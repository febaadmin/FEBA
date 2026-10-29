"""
SMS : copie des e-mails et des relances de paiement.

Twilio est simulé au niveau du TRANSPORT HTTP (urlopen) : chaque test lit
la requête réellement émise (To, From, Body, authentification). Aucun SMS
réel n'est envoyé ; la remise réelle se vérifie avec `manage.py sms_check
--to` (voir SMS_CONFIGURATION_GUIDE.md) — ces tests ne la prouvent pas.
"""
import base64
import hashlib
import hmac
import io
import json
import socket
import urllib.error
import urllib.parse
from datetime import date as D, timedelta
from decimal import Decimal
from unittest import mock

from django.core import mail
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.accounts.models import CustomUser
from apps.notifications import sms as sms_service
from apps.notifications.mailer import send_tracked_email
from apps.notifications.sms_models import SmsMessage, SmsPart
from apps.notifications.sms_providers import (
    PROVIDER_MAX_CHARS, encoding_of, segment_count, split_for_provider, strip_part_prefix,
)
from apps.payments.models import PaymentReminder
from tests import test_audit_p1_payment_reminders as rem
from tests import test_email_outbox as outbox

FROM = "+12157155406"
SMS_ON = dict(SMS_ENABLED=True, SMS_PROVIDER="twilio", SMS_FROM_NUMBER=FROM,
              TWILIO_ACCOUNT_SID="ACtest0000000000000000000000000000", TWILIO_AUTH_TOKEN="jeton-de-test",
              SMS_REQUIRE_EXPLICIT_CONSENT=True, SMS_STATUS_CALLBACK_URL="",
              SMS_DEFAULT_REGIONS="FEBA:BJ,REL-FEBA:BJ", SMS_MAX_MESSAGES_PER_NOTIFICATION=5)
PARENT_PHONE = "+2290196697363"


class _Resp(io.BytesIO):
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class FakeTwilio:
    """Transport HTTP simulé. `fail` : exception ou liste d'exceptions à lever en séquence."""

    def __init__(self):
        self.sent = []
        self.fail = []
        self.counter = 0

    def http_error(self, code, twilio_code=None, message="erreur"):
        body = json.dumps({"code": twilio_code or code, "message": message}).encode()
        return urllib.error.HTTPError("https://api.twilio.com", code, message, {}, io.BytesIO(body))

    def __call__(self, request, timeout=None):
        if self.fail:
            exc = self.fail.pop(0)
            if exc is not None:
                raise exc
        data = dict(urllib.parse.parse_qsl(request.data.decode())) if request.data else {}
        if request.get_method() == "GET":
            return _Resp(json.dumps({"incoming_phone_numbers": [
                {"phone_number": FROM, "capabilities": {"sms": True}}]}).encode())
        self.counter += 1
        self.sent.append({"to": data.get("To"), "from": data.get("From"), "body": data.get("Body"),
                          "auth": request.get_header("Authorization"), "url": request.full_url,
                          "callback": data.get("StatusCallback")})
        return _Resp(json.dumps({"sid": f"SM{self.counter:032d}", "status": "queued"}).encode())


class SmsBaseMixin:
    def setUp(self):
        super().setUp()
        self.twilio = FakeTwilio()
        for target, side in (("apps.notifications.sms_providers.urllib.request.urlopen", self.twilio),
                             ("apps.notifications.sms._enqueue", lambda pk: sms_service.deliver(pk))):
            p = mock.patch(target, side_effect=side)
            p.start()
            self.addCleanup(p.stop)

    def consent(self, user, phone=PARENT_PHONE, state=CustomUser.SMS_CONSENT_GRANTED):
        CustomUser.objects.filter(pk=user.pk).update(phone=phone, sms_consent=state)
        user.refresh_from_db()
        return user


# ── Encodage, découpage ───────────────────────────────────────────────

class EncodingTests(TestCase):
    def test_gsm_et_unicode(self):
        self.assertEqual(encoding_of("Bonjour, réglez 150 000 FCFA avant le 30/09."), "GSM-7")
        self.assertEqual(encoding_of("Échéance de l'élève : 1re tranche — merci"), "UCS-2")  # « — »
        self.assertEqual(segment_count("a" * 160), 1)
        self.assertEqual(segment_count("a" * 161), 2)
        self.assertEqual(segment_count("ê" * 70), 1)
        self.assertEqual(segment_count("ê" * 71), 2)

    def test_decoupage_sans_perte_et_dans_l_ordre(self):
        text = "\n\n".join(f"Paragraphe {i} : " + "mot " * 60 for i in range(12))
        parts = split_for_provider(text)
        self.assertGreater(len(parts), 1)
        self.assertTrue(all(len(p) <= PROVIDER_MAX_CHARS for p in parts))
        self.assertEqual("".join(strip_part_prefix(p) for p in parts), text)
        self.assertTrue(parts[0].startswith(f"(1/{len(parts)}) "))

    def test_texte_court_un_seul_message_sans_numerotation(self):
        self.assertEqual(split_for_provider("Bonjour"), ["Bonjour"])


# ── Copie des e-mails ─────────────────────────────────────────────────

@override_settings(**SMS_ON)
class EmailMirrorTests(SmsBaseMixin, outbox.OutboxBase):
    def send(self, to, text="Bonjour,\nRéunion jeudi 18 h — salle B.\nhttps://globalfeba.com/x", **kw):
        with self.captureOnCommitCallbacks(execute=True):
            return send_tracked_email(purpose="test_mirror", to_email=to, subject="Objet",
                                      text_body=text, entity=self.a, **kw)

    def test_meme_texte_bon_numero_bon_expediteur(self):
        self.consent(self.parent_a)
        d = self.send(self.parent_a.email)
        self.assertEqual(len(self.twilio.sent), 1)
        sent = self.twilio.sent[0]
        self.assertEqual(sent["to"], PARENT_PHONE)
        self.assertEqual(sent["from"], FROM)
        self.assertEqual(sent["body"], "Bonjour,\nRéunion jeudi 18 h — salle B.\nhttps://globalfeba.com/x")
        self.assertTrue(sent["auth"].startswith("Basic "))
        sms = SmsMessage.objects.get()
        self.assertEqual((sms.status, sms.email_delivery_id, sms.user_id), ("sent", d.pk, self.parent_a.pk))
        self.assertEqual(SmsPart.objects.get().provider_message_id, "SM" + "0" * 31 + "1")
        # Statuts distincts : l'e-mail a le sien.
        d.refresh_from_db()
        self.assertEqual(d.status, "sent")

    def test_email_html_seul_converti_en_texte_complet(self):
        self.consent(self.parent_a)
        html = ("<p>Chers parents,</p><ul><li>Cahier</li><li>Stylo</li></ul>"
                "<p>Détails : <a href='https://globalfeba.com/rentree'>ici</a></p>")
        self.send(self.parent_a.email, text="", html_body=html)
        body = self.twilio.sent[0]["body"]
        self.assertIn("Chers parents,", body)
        self.assertIn("- Cahier", body)
        self.assertIn("- Stylo", body)
        self.assertIn("https://globalfeba.com/rentree", body)

    def test_piece_jointe_signalee_jamais_envoyee(self):
        self.consent(self.parent_a)
        self.send(self.parent_a.email, attachments=[("a.pdf", outbox.PDF, "application/pdf")])
        body = self.twilio.sent[0]["body"]
        self.assertTrue(body.endswith("[Pièce(s) jointe(s) : consultez l'e-mail correspondant.]"))

    def test_texte_long_plusieurs_sms_numerotes_aucune_troncature(self):
        self.consent(self.parent_a)
        text = "\n\n".join(f"Point {i} : " + "information importante " * 30 for i in range(8))
        self.send(self.parent_a.email, text=text)
        bodies = [s["body"] for s in self.twilio.sent]
        self.assertGreater(len(bodies), 1)
        self.assertEqual("".join(strip_part_prefix(b) for b in bodies), text)
        sms = SmsMessage.objects.get()
        self.assertEqual((sms.status, sms.parts), ("sent", len(bodies)))

    @override_settings(SMS_MAX_MESSAGES_PER_NOTIFICATION=2)
    def test_texte_trop_long_echec_explicite_rien_de_tronque(self):
        self.consent(self.parent_a)
        self.send(self.parent_a.email, text="x " * 2500)
        self.assertEqual(self.twilio.sent, [])
        sms = SmsMessage.objects.get()
        self.assertEqual(sms.status, "failed")
        self.assertIn("Aucun SMS tronqué", sms.last_error)

    def test_motifs_d_exclusion_explicites(self):
        cases = [
            ("no_phone", dict(phone="", state="granted")),
            ("invalid_phone", dict(phone="+229123", state="granted")),
            ("not_mobile", dict(phone="+33145000000", state="granted")),  # fixe parisien
            ("no_consent", dict(phone=PARENT_PHONE, state="unknown")),
            ("consent_refused", dict(phone=PARENT_PHONE, state="refused")),
        ]
        for reason, params in cases:
            with self.subTest(reason=reason):
                SmsMessage.objects.all().delete()
                self.consent(self.parent_a, **params)
                self.send(self.parent_a.email)
                sms = SmsMessage.objects.get()
                self.assertEqual((sms.status, sms.skip_reason), ("skipped", reason))
        self.send("inconnu@nowhere.test")
        self.assertEqual(SmsMessage.objects.latest("pk").skip_reason, "no_matching_account")
        self.assertEqual(self.twilio.sent, [])

    @override_settings(SMS_REQUIRE_EXPLICIT_CONSENT=False)
    def test_consentement_implicite_mais_refus_toujours_respecte(self):
        self.consent(self.parent_a, state="unknown")
        self.send(self.parent_a.email)
        self.assertEqual(len(self.twilio.sent), 1)
        self.consent(self.parent_a2, state="refused")
        self.send(self.parent_a2.email)
        self.assertEqual(len(self.twilio.sent), 1)

    def test_numero_local_indicatif_de_l_academie_jamais_devine_ailleurs(self):
        self.assertEqual(sms_service.normalize_phone("0196697363", type("E", (), {"code": "FEBA"})()),
                         (PARENT_PHONE, ""))
        self.assertEqual(sms_service.normalize_phone("0196697363", type("E", (), {"code": "FEBA_FHA"})())[1],
                         "invalid_phone")

    @override_settings(SMS_ENABLED=False)
    def test_desactive_rien_ne_part(self):
        self.consent(self.parent_a)
        self.send(self.parent_a.email)
        self.assertEqual(self.twilio.sent, [])
        self.assertEqual(SmsMessage.objects.get().skip_reason, "sms_disabled")

    def test_message_de_securite_jamais_copie(self):
        from django.core.mail import send_mail
        self.consent(self.parent_a)
        with override_settings(EMAIL_BACKEND=outbox.TRACKING,
                               EMAIL_TRANSPORT_BACKEND="django.core.mail.backends.locmem.EmailBackend"):
            with self.captureOnCommitCallbacks(execute=True):
                send_mail("Mot de passe", "Lien : https://globalfeba.com/reset/MQ/abc-123/", None,
                          [self.parent_a.email])
        self.assertEqual(self.twilio.sent, [])
        self.assertEqual(SmsMessage.objects.get().skip_reason, "sensitive_content")

    @override_settings(ADMINS=[("Ops", "ob.a@test.io")])
    def test_alerte_d_erreur_django_jamais_copiee(self):
        from django.core.mail import mail_admins
        self.consent(self.admin_a)
        with override_settings(EMAIL_BACKEND=outbox.TRACKING,
                               EMAIL_TRANSPORT_BACKEND="django.core.mail.backends.locmem.EmailBackend"):
            with self.captureOnCommitCallbacks(execute=True):
                mail_admins("Erreur 500", "Traceback (most recent call last): …")
        self.assertEqual(self.twilio.sent, [])
        self.assertFalse(SmsMessage.objects.exists())

    def test_test_smtp_jamais_copie(self):
        from django.core.cache import cache
        cache.clear()
        self.consent(self.admin_a)
        self.api(self.admin_a).post("/api/notifications/email-config/test/", {"to": self.admin_a.email},
                                    format="json")
        self.assertFalse(SmsMessage.objects.exists())

    def test_campagne_un_sms_par_destinataire_rejeu_sans_doublon(self):
        self.consent(self.parent_a)
        self.consent(self.parent_a2, phone="+2290197000001")
        with self.captureOnCommitCallbacks(execute=True):
            resp = self.campaign(self.admin_a, self.a)
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertEqual(sorted(s["to"] for s in self.twilio.sent), ["+2290196697363", "+2290197000001"])
        self.assertTrue(all("Voir la pièce jointe." in s["body"] for s in self.twilio.sent))
        from apps.notifications.campaigns import process_campaign
        from apps.notifications.models import EmailCampaign
        process_campaign(EmailCampaign.objects.get().pk)
        sms_service.retry_due()
        self.assertEqual(len(self.twilio.sent), 2)

    # ── Fiabilité ──────────────────────────────────────────────────
    def test_fournisseur_indisponible_reprise_sans_renvoyer_l_email(self):
        self.consent(self.parent_a)
        self.twilio.fail = [self.twilio.http_error(503)]
        d = self.send(self.parent_a.email)
        sms = SmsMessage.objects.get()
        self.assertEqual(sms.status, "retry")
        self.assertIn("503", sms.last_error)
        emails_before = len(mail.outbox)
        SmsMessage.objects.filter(pk=sms.pk).update(next_retry_at=timezone.now() - timedelta(seconds=1))
        sms_service.retry_due()
        sms.refresh_from_db()
        self.assertEqual((sms.status, sms.attempts), ("sent", 2))
        self.assertEqual(len(mail.outbox), emails_before)       # l'e-mail n'est pas renvoyé
        d.refresh_from_db()
        self.assertEqual(d.attempts, 1)

    def test_delai_depasse_et_erreur_d_authentification_reprises(self):
        self.consent(self.parent_a)
        self.twilio.fail = [urllib.error.URLError(socket.timeout("timed out"))]
        self.send(self.parent_a.email)
        self.assertEqual(SmsMessage.objects.get().status, "retry")
        SmsMessage.objects.all().delete()
        self.twilio.fail = [self.twilio.http_error(401, 20003, "Authenticate")]
        self.send(self.parent_a2.email) if False else self.send(self.parent_a.email)
        sms = SmsMessage.objects.get()
        self.assertEqual(sms.status, "retry")
        self.assertIn("Authentification Twilio refusée", sms.last_error)

    def test_numero_refuse_definitivement_et_stop(self):
        self.consent(self.parent_a)
        self.twilio.fail = [self.twilio.http_error(400, 21211, "Invalid 'To'")]
        self.send(self.parent_a.email)
        self.assertEqual(SmsMessage.objects.get().status, "failed")
        SmsMessage.objects.all().delete()
        self.twilio.fail = [self.twilio.http_error(400, 21610, "Unsubscribed recipient")]
        self.send(self.parent_a.email)
        self.assertEqual(SmsMessage.objects.get().status, "failed")
        self.parent_a.refresh_from_db()
        self.assertEqual(self.parent_a.sms_consent, "refused")   # STOP respecté ensuite

    def test_tache_rejouee_un_seul_envoi(self):
        self.consent(self.parent_a)
        self.send(self.parent_a.email)
        sms = SmsMessage.objects.get()
        sms_service.deliver(sms.pk)
        sms_service.deliver(sms.pk)
        self.assertEqual(len(self.twilio.sent), 1)

    def test_envoi_en_plusieurs_parties_reprend_seulement_les_parties_manquantes(self):
        self.consent(self.parent_a)
        text = "\n\n".join(f"Point {i} : " + "information importante " * 30 for i in range(8))
        self.twilio.fail = [None, self.twilio.http_error(500)]   # 1re partie acceptée, 2e en panne
        self.send(self.parent_a.email, text=text)
        sms = SmsMessage.objects.get()
        self.assertEqual((sms.status, sms.part_records.count()), ("retry", 1))
        SmsMessage.objects.filter(pk=sms.pk).update(next_retry_at=timezone.now())
        sms_service.retry_due()
        sms.refresh_from_db()
        self.assertEqual(sms.status, "sent")
        indexes = [p.index for p in sms.part_records.all()]
        self.assertEqual(indexes, list(range(1, sms.parts + 1)))
        self.assertEqual(len(self.twilio.sent), sms.parts)       # aucune partie envoyée deux fois

    def test_envoi_interrompu_par_un_redemarrage_repris(self):
        self.consent(self.parent_a)
        with mock.patch("apps.notifications.sms._enqueue"):   # worker absent
            with self.captureOnCommitCallbacks(execute=True):
                send_tracked_email(purpose="t", to_email=self.parent_a.email, subject="s",
                                   text_body="Bonjour", entity=self.a)
        sms = SmsMessage.objects.get()
        SmsMessage.objects.filter(pk=sms.pk).update(created_at=timezone.now() - timedelta(minutes=30))
        sms_service.retry_due()
        sms.refresh_from_db()
        self.assertEqual(sms.status, "sent")


# ── Accusés de remise ─────────────────────────────────────────────────

CALLBACK = "https://globalfeba.com/api/notifications/sms/status/"


@override_settings(**{**SMS_ON, "SMS_STATUS_CALLBACK_URL": CALLBACK})
class StatusCallbackTests(SmsBaseMixin, outbox.OutboxBase):
    def post_callback(self, params, token="jeton-de-test"):
        data = CALLBACK + "".join(f"{k}{params[k]}" for k in sorted(params))
        sig = base64.b64encode(hmac.new(token.encode(), data.encode(), hashlib.sha1).digest()).decode()
        return self.client.post("/api/notifications/sms/status/", params, HTTP_X_TWILIO_SIGNATURE=sig)

    def test_remise_confirmee_puis_signature_invalide_refusee(self):
        self.consent(self.parent_a)
        with self.captureOnCommitCallbacks(execute=True):
            send_tracked_email(purpose="t", to_email=self.parent_a.email, subject="s", text_body="Bonjour",
                               entity=self.a)
        self.assertEqual(self.twilio.sent[0]["callback"], CALLBACK)
        sid = SmsPart.objects.get().provider_message_id
        self.assertEqual(self.post_callback({"MessageSid": sid, "MessageStatus": "delivered"}).status_code, 200)
        self.assertEqual(SmsMessage.objects.get().status, "delivered")
        bad = self.post_callback({"MessageSid": sid, "MessageStatus": "failed"}, token="faux")
        self.assertEqual(bad.status_code, 403)
        self.assertEqual(SmsMessage.objects.get().status, "delivered")

    def test_non_remis_par_l_operateur(self):
        self.consent(self.parent_a)
        with self.captureOnCommitCallbacks(execute=True):
            send_tracked_email(purpose="t", to_email=self.parent_a.email, subject="s", text_body="Bonjour",
                               entity=self.a)
        sid = SmsPart.objects.get().provider_message_id
        self.post_callback({"MessageSid": sid, "MessageStatus": "undelivered", "ErrorCode": "30003"})
        sms = SmsMessage.objects.get()
        self.assertEqual(sms.status, "failed")
        self.assertIn("30003", sms.last_error)


# ── API : isolation par académie ──────────────────────────────────────

@override_settings(**SMS_ON)
class SmsApiTests(SmsBaseMixin, outbox.OutboxBase):
    def test_isolation_et_resume_dans_la_boite_d_envoi(self):
        self.consent(self.parent_a)
        with self.captureOnCommitCallbacks(execute=True):
            d = send_tracked_email(purpose="t", to_email=self.parent_a.email, subject="s",
                                   text_body="Bonjour", entity=self.a)
        sms = SmsMessage.objects.get()
        rows = self.api(self.admin_a).get("/api/notifications/sms/").json()
        self.assertEqual([r["id"] for r in rows["results"]], [sms.pk])
        self.assertNotIn(PARENT_PHONE, json.dumps(rows))        # numéro masqué
        self.assertEqual(self.api(self.admin_b).get("/api/notifications/sms/").json()["count"], 0)
        self.assertEqual(self.api(self.admin_b).post(f"/api/notifications/sms/{sms.pk}/retry/").status_code, 404)
        self.assertEqual(self.api(self.parent_a).get("/api/notifications/sms/").status_code, 403)
        detail = self.api(self.admin_a).get(f"/api/notifications/outbox/{d.pk}/").json()
        self.assertEqual(detail["sms"]["status"], "sent")

    def test_relance_manuelle_d_un_echec_seulement(self):
        self.consent(self.parent_a)
        self.twilio.fail = [self.twilio.http_error(400, 21211)]
        with self.captureOnCommitCallbacks(execute=True):
            send_tracked_email(purpose="t", to_email=self.parent_a.email, subject="s", text_body="Bonjour",
                               entity=self.a)
        sms = SmsMessage.objects.get()
        r = self.api(self.admin_a).post(f"/api/notifications/sms/{sms.pk}/retry/")
        self.assertEqual(r.json()["status"], "sent")
        self.assertEqual(self.api(self.admin_a).post(f"/api/notifications/sms/{sms.pk}/retry/").status_code, 409)


# ── Relances de paiement : les 10 scénarios exigés ────────────────────

@override_settings(**SMS_ON, PAYMENT_REMINDERS_ENABLED=True)
class ReminderSmsTests(SmsBaseMixin, rem.ReminderBase):
    def setUp(self):
        super().setUp()
        self.consent(self.parent_user)

    def run_and_commit(self, on=D(2026, 10, 9), **kw):
        with self.captureOnCommitCallbacks(execute=True):
            return self.run_engine(on, **kw)

    def test_1_relance_par_email_declenche_le_sms(self):
        self.run_and_commit()
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(len(self.twilio.sent), 1)
        self.assertEqual(self.twilio.sent[0]["to"], PARENT_PHONE)

    def test_2_relance_par_notification_interne_seule(self):
        from apps.payments.models import PaymentReminderPolicy
        PaymentReminderPolicy.objects.filter(academy=self.feba).update(send_email=False)
        self.run_and_commit()
        self.assertEqual(len(mail.outbox), 0)
        self.assertEqual(len(self.twilio.sent), 1)
        self.assertIn("Alice Élève", self.twilio.sent[0]["body"])

    def test_3_plusieurs_canaux_et_reprise_aucun_doublon(self):
        self.run_and_commit()
        rows = list(PaymentReminder.objects.all())
        from apps.payments.reminders import _deliver, get_policy
        with self.captureOnCommitCallbacks(execute=True):
            _deliver(self.feba, get_policy(self.feba), self.parent_user, rows)   # reprise rejouée
        self.assertEqual(len(self.twilio.sent), 1)
        self.assertEqual(SmsMessage.objects.count(), 1)
        self.assertEqual({r.sms_message_id for r in PaymentReminder.objects.all()}, {SmsMessage.objects.get().pk})

    def test_3b_une_relance_distincte_produit_son_propre_sms(self):
        self.run_and_commit(D(2026, 10, 9))
        # Niveau 2 après l'intervalle de 14 jours (même procédé que
        # test_second_level_after_interval_and_max).
        self.run_and_commit(D(2026, 10, 22), now=timezone.now() + timedelta(days=15))
        self.assertEqual(SmsMessage.objects.filter(purpose="payment_reminder").count(), 2)
        self.assertEqual(len(self.twilio.sent), 2)

    def test_4_plusieurs_contacts_le_responsable_financier_et_son_numero(self):
        other = self.consent(self.parent2_user, phone="+2290197000002")
        link = self.link(other, self.alice)
        link.is_financial_responsible = True
        link.save()
        self.run_and_commit()
        by_number = {s["to"]: s["body"] for s in self.twilio.sent}
        self.assertIn("+2290197000002", by_number)            # Alice → son responsable financier
        self.assertIn("Alice", by_number["+2290197000002"])
        self.assertNotIn("Bob", by_number["+2290197000002"])

    def test_5_numero_absent_ou_invalide_enregistre(self):
        CustomUser.objects.filter(pk=self.parent_user.pk).update(phone="12")
        self.run_and_commit()
        sms = SmsMessage.objects.get()
        self.assertEqual((sms.status, sms.skip_reason), ("skipped", "invalid_phone"))
        self.assertTrue(all(r.sms_message_id == sms.pk for r in PaymentReminder.objects.all()))
        self.assertEqual(self.twilio.sent, [])

    def test_6_fournisseur_indisponible_relance_non_perdue(self):
        self.twilio.fail = [self.twilio.http_error(503)]
        self.run_and_commit()
        sms = SmsMessage.objects.get()
        self.assertEqual(sms.status, "retry")
        SmsMessage.objects.filter(pk=sms.pk).update(next_retry_at=timezone.now())
        sms_service.retry_due()
        sms.refresh_from_db()
        self.assertEqual(sms.status, "sent")

    def test_7_paiement_recu_avant_l_envoi_du_sms(self):
        with mock.patch("apps.notifications.sms._enqueue"):     # SMS en file, pas encore parti
            self.run_and_commit()
        self.pay(self.alice, "150000", payment_date=D(2026, 10, 9))
        sms = SmsMessage.objects.get()
        sms_service.deliver(sms.pk)
        sms.refresh_from_db()
        self.assertEqual((sms.status, sms.skip_reason), ("skipped", "no_longer_due"))
        self.assertIn("réglée", sms.last_error)
        self.assertEqual(self.twilio.sent, [])

    def test_8_tache_celery_rejouee_aucun_doublon(self):
        self.run_and_commit()
        sms = SmsMessage.objects.get()
        from apps.notifications.tasks import retry_due_sms, send_sms
        send_sms(sms.pk)
        send_sms(sms.pk)
        retry_due_sms()
        self.assertEqual(len(self.twilio.sent), 1)

    def test_9_autre_academie_acces_refuse(self):
        self.run_and_commit()
        sms = SmsMessage.objects.get()
        intrus = self.user("rel_intrus", "admin", self.fha)
        from rest_framework.test import APIClient
        client = APIClient()
        client.force_authenticate(intrus)
        self.assertEqual(client.get("/api/notifications/sms/").json()["count"], 0)
        self.assertEqual(client.post(f"/api/notifications/sms/{sms.pk}/retry/").status_code, 404)
        reminders = client.get("/api/payments/reminders/").json()
        rows = reminders.get("results", reminders) if isinstance(reminders, dict) else reminders
        self.assertFalse(any(str(r).find("Alice") >= 0 for r in rows))

    def test_10_montants_references_echeances_identiques_a_la_relance(self):
        self.run_and_commit()
        body = self.twilio.sent[0]["body"]
        self.assertEqual(body, SmsMessage.objects.get().body)
        email_body = mail.outbox[0].body
        self.assertEqual(body, email_body)                      # même texte que l'e-mail
        for expected in ("150 000 FCFA", "30/09/2026", "Alice Élève", "Bob Élève", "MTN MoMo"):
            self.assertIn(expected, body)
        for reminder in PaymentReminder.objects.all():
            self.assertIn(reminder.installment_label, body)


class ConsentApiTests(outbox.OutboxBase):
    def test_choix_par_la_personne_horodate_par_le_serveur(self):
        r = self.api(self.parent_a).patch("/api/auth/me/", {"sms_consent": "granted", "phone": "0196697363"},
                                          format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.parent_a.refresh_from_db()
        self.assertEqual(self.parent_a.sms_consent, "granted")
        self.assertIsNotNone(self.parent_a.sms_consent_at)
        r = self.api(self.parent_a).patch("/api/auth/me/", {"sms_consent_at": "2000-01-01T00:00:00Z"},
                                          format="json")
        self.parent_a.refresh_from_db()
        self.assertNotEqual(self.parent_a.sms_consent_at.year, 2000)

    def test_numero_tel_qu_il_sera_utilise_ou_motif(self):
        CustomUser.objects.filter(pk=self.parent_a.pk).update(phone="+2290196697363")
        self.parent_a.refresh_from_db()
        data = self.api(self.parent_a).get("/api/auth/me/").json()
        self.assertEqual(data["sms_phone"], {"e164": "+2290196697363", "problem": ""})
        CustomUser.objects.filter(pk=self.parent_a.pk).update(phone="97000000")
        self.parent_a.refresh_from_db()
        self.assertEqual(self.api(self.parent_a).get("/api/auth/me/").json()["sms_phone"]["problem"],
                         "invalid_phone")

    def test_admin_d_une_autre_academie_ne_modifie_pas_le_consentement(self):
        r = self.api(self.admin_b).patch(f"/api/auth/users/{self.parent_a.pk}/", {"sms_consent": "granted"},
                                         format="json")
        self.assertIn(r.status_code, (403, 404))
        self.parent_a.refresh_from_db()
        self.assertEqual(self.parent_a.sms_consent, "unknown")
