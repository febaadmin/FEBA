"""
E-mails : transport honnête, archivage, pièces jointes, boîte d'envoi.

Défaut d'origine (reproduit sur l'installation Docker locale, octobre
2026) : les envois partaient vers Mailpit (`EMAIL_HOST=mailpit`), qui les
CAPTURE sans jamais les distribuer, et FEBA les affichait « envoyés par un
fournisseur réel ». Aucune pièce jointe possible, aucune boîte d'envoi.

Tests SMTP réels : `MailpitSmtpTests` (Mailpit local, variables
MAILPIT_SMTP_PORT et MAILPIT_API_URL). Aucun envoi vers Internet.
"""
import io
import json
import os
import shutil
import smtplib
import tempfile
import urllib.request
import uuid
from datetime import timedelta
from unittest import mock

from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import CustomUser
from apps.notifications.attachments import AttachmentError, safe_filename, validate_uploads
from apps.notifications.email_models import EmailAttachment, EmailContent, EmailDelivery
from apps.notifications.mailer import current_transport, send_tracked_email
from apps.schools.models import School

PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
DOCX = b"PK\x03\x04" + b"\x00" * 64
TRACKING = "apps.notifications.backends.TrackingEmailBackend"


def upload(name, data, ctype="application/octet-stream"):
    return SimpleUploadedFile(name, data, content_type=ctype)


class PrivateMediaMixin:
    def setUp(self):
        super().setUp()
        self._media = tempfile.mkdtemp(prefix="feba-mail-")
        self._override = override_settings(PRIVATE_MEDIA_ROOT=self._media)
        self._override.enable()
        self.addCleanup(self._override.disable)
        self.addCleanup(shutil.rmtree, self._media, True)


class TransportTests(TestCase):
    def test_mailpit_is_capture_not_real(self):
        with override_settings(EMAIL_BACKEND="django.core.mail.backends.smtp.EmailBackend",
                               EMAIL_HOST="mailpit"):
            self.assertEqual(current_transport(), "capture")
        with override_settings(EMAIL_BACKEND=TRACKING,
                               EMAIL_TRANSPORT_BACKEND="django.core.mail.backends.smtp.EmailBackend",
                               EMAIL_HOST="mailpit"):
            self.assertEqual(current_transport(), "capture")

    def test_real_provider_and_overrides(self):
        smtp = "django.core.mail.backends.smtp.EmailBackend"
        with override_settings(EMAIL_BACKEND=smtp, EMAIL_HOST="smtp.fournisseur.test"):
            self.assertEqual(current_transport(), "smtp")
        with override_settings(EMAIL_BACKEND=smtp, EMAIL_HOST="smtp.fournisseur.test",
                               EMAIL_DELIVERY_MODE="capture"):
            self.assertEqual(current_transport(), "capture")
        with override_settings(EMAIL_BACKEND=smtp, EMAIL_HOST="relais.interne", EMAIL_CAPTURE_HOSTS="relais.interne"):
            self.assertEqual(current_transport(), "capture")
        with override_settings(EMAIL_BACKEND=smtp, EMAIL_HOST=""):
            self.assertEqual(current_transport(), "unconfigured")
        with override_settings(EMAIL_BACKEND="django.core.mail.backends.console.EmailBackend"):
            self.assertEqual(current_transport(), "console")

    def test_capture_is_never_reported_as_real_delivery(self):
        with override_settings(EMAIL_BACKEND="django.core.mail.backends.smtp.EmailBackend",
                               EMAIL_HOST="mailpit"), \
                mock.patch.object(mail.EmailMultiAlternatives, "send", return_value=1):
            d = send_tracked_email(purpose="t", to_email="a@b.test", subject="s", text_body="b")
        self.assertEqual(d.status, "sent")
        self.assertFalse(d.used_real_provider)
        self.assertIn("Mailpit", d.delivery_summary())
        self.assertIn("non distribué", d.delivery_summary())


class ArchiveTests(PrivateMediaMixin, TestCase):
    def test_content_attachment_and_attempt_are_archived(self):
        d = send_tracked_email(purpose="t", to_email="a@b.test", subject="Objet", text_body="Texte",
                               html_body="<p>HTML</p>", attachments=[("bulletin.pdf", PDF, "application/pdf")])
        self.assertEqual(d.status, "sent")
        self.assertEqual((d.content.subject, d.content.text_body, d.content.html_body),
                         ("Objet", "Texte", "<p>HTML</p>"))
        att = d.content.attachments.get()
        self.assertEqual((att.original_name, att.content_type, att.size), ("bulletin.pdf", "application/pdf", len(PDF)))
        self.assertEqual(att.read_bytes(), PDF)
        self.assertTrue(att.file.path.startswith(self._media))
        self.assertEqual(d.attempt_log.count(), 1)
        self.assertTrue(d.message_id)
        sent = mail.outbox[0]
        self.assertEqual(sent.attachments[0][0], "bulletin.pdf")
        self.assertEqual(sent.attachments[0][1], PDF)

    def test_sensitive_content_is_redacted_in_archive_only(self):
        d = send_tracked_email(purpose="t", to_email="a@b.test", subject="Réinitialisation",
                               text_body="Lien : https://globalfeba.com/reset/abc/tok-123/ ?token=XYZ",
                               sensitive=True)
        self.assertIn("tok-123", mail.outbox[0].body)          # le message part intact
        self.assertNotIn("tok-123", d.content.text_body)      # l'archive est expurgée
        self.assertTrue(d.content.is_redacted)

    def test_missing_file_fails_explicitly(self):
        d = send_tracked_email(purpose="t", to_email="a@b.test", subject="s", text_body="b",
                               attachments=[("x.pdf", PDF, "application/pdf")])
        att = d.content.attachments.get()
        os.remove(att.file.path)
        from apps.notifications.mailer import deliver
        d = deliver(d, manual=True)
        self.assertEqual(d.status, "retry")
        self.assertIn("FileNotFoundError", d.last_error)


class AttachmentValidationTests(TestCase):
    def test_allowed_formats(self):
        files = validate_uploads([upload("a.pdf", PDF), upload("b.png", PNG), upload("c.docx", DOCX),
                                  upload("d.csv", "nom;âge\nAna;9\n".encode())])
        self.assertEqual([f[2] for f in files][:2], ["application/pdf", "image/png"])

    def test_disguised_executable_refused(self):
        with self.assertRaises(AttachmentError):
            validate_uploads([upload("facture.pdf", b"MZ\x90\x00 executable")])

    def test_forbidden_extensions(self):
        for name in ("script.exe", "page.html", "image.svg", "archive.zip", "macro.js"):
            with self.subTest(name=name), self.assertRaises(AttachmentError):
                validate_uploads([upload(name, b"x")])

    @override_settings(EMAIL_ATTACHMENT_MAX_FILE_MB=1, EMAIL_ATTACHMENT_MAX_TOTAL_MB=1)
    def test_size_limits(self):
        big = PDF + b"0" * (1024 * 1024)
        with self.assertRaises(AttachmentError):
            validate_uploads([upload("big.pdf", big)])
        half = PDF + b"0" * (600 * 1024)
        with self.assertRaises(AttachmentError):
            validate_uploads([upload("a.pdf", half), upload("b.pdf", half)])

    def test_empty_and_count(self):
        with self.assertRaises(AttachmentError):
            validate_uploads([upload("vide.pdf", b"")])
        with override_settings(EMAIL_ATTACHMENT_MAX_FILES=1), self.assertRaises(AttachmentError):
            validate_uploads([upload("a.pdf", PDF), upload("b.pdf", PDF)])

    def test_dangerous_names_neutralised(self):
        self.assertEqual(safe_filename("../../etc/passwd.pdf"), "passwd.pdf")
        self.assertEqual(safe_filename("C:\\\\x\\\\évaluation.pdf"), "évaluation.pdf")
        self.assertNotIn("\x00", safe_filename("a\x00b.pdf"))
        self.assertEqual(safe_filename(""), "piece-jointe")


class OutboxBase(PrivateMediaMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.a = School.objects.create(name="Acad A", address="x", code="OB-A")
        cls.b = School.objects.create(name="Acad B", address="x", code="OB-B")
        cls.admin_a = CustomUser.objects.create_user(username="ob_a", email="ob.a@test.io", password="x",
                                                     role="admin", school=cls.a)
        cls.admin_b = CustomUser.objects.create_user(username="ob_b", email="ob.b@test.io", password="x",
                                                     role="admin", school=cls.b)
        cls.teacher_a = CustomUser.objects.create_user(username="ob_t", email="ob.t@test.io", password="x",
                                                       role="teacher", school=cls.a)
        cls.parent_a = CustomUser.objects.create_user(username="ob_p", email="ob.p@test.io", password="x",
                                                      role="parent", school=cls.a)
        cls.parent_a2 = CustomUser.objects.create_user(username="ob_p2", email="ob.p2@test.io", password="x",
                                                       role="parent", school=cls.a)
        cls.parent_b = CustomUser.objects.create_user(username="ob_pb", email="ob.pb@test.io", password="x",
                                                      role="parent", school=cls.b)
        cls.superadmin = CustomUser.objects.create_user(username="ob_s", email="ob.s@test.io", password="x",
                                                        role="superadmin")

    def api(self, user):
        client = APIClient()
        client.force_authenticate(user)
        return client

    def campaign(self, user, academy, files=(), roles=("parent",), run=True, **extra):
        client = self.api(user)
        pv = client.post("/api/mass-email/preview/", {"academy_id": academy.pk, "roles": list(roles)},
                         format="json").json()
        payload = {"academy_id": academy.pk, "roles": list(roles), "subject": "Sortie scolaire",
                   "body": "Bonjour,\nVoir la pièce jointe.", "confirm": True,
                   "expected_count": pv["count"], "client_token": uuid.uuid4().hex, **extra}
        data = {"payload": json.dumps(payload), "attachments": list(files)}
        with mock.patch("apps.notifications.tasks.send_campaign.delay") as delay:
            with self.captureOnCommitCallbacks(execute=True):
                resp = client.post("/api/mass-email/campaigns/", data, format="multipart")
        if run and resp.status_code in (200, 201):
            from apps.notifications.campaigns import process_campaign
            for call in delay.call_args_list:
                process_campaign(*call.args)
        return resp


class CampaignAttachmentTests(OutboxBase):
    def test_campaign_with_several_attachments_shared_once(self):
        resp = self.campaign(self.admin_a, self.a, files=[
            upload("programme.pdf", PDF, "application/pdf"), upload("photo.png", PNG, "image/png"),
            upload("autorisation.docx", DOCX)])
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertEqual(len(resp.json()["attachments"]), 3)
        self.assertEqual(EmailAttachment.objects.count(), 3)       # un seul exemplaire
        self.assertEqual(EmailContent.objects.count(), 1)
        self.assertEqual(len(mail.outbox), 2)
        for message in mail.outbox:
            self.assertEqual(len(message.to), 1)
            self.assertEqual(sorted(a[0] for a in message.attachments),
                             ["autorisation.docx", "photo.png", "programme.pdf"])
            self.assertEqual(dict((a[0], a[2]) for a in message.attachments)["programme.pdf"], "application/pdf")

    def test_invalid_attachment_rejects_whole_send(self):
        resp = self.campaign(self.admin_a, self.a, files=[upload("virus.pdf", b"MZ fake")])
        self.assertEqual(resp.status_code, 400)
        self.assertIn("attachments", resp.json())
        self.assertEqual(len(mail.outbox), 0)
        from apps.notifications.campaign_models import EmailCampaign
        self.assertFalse(EmailCampaign.objects.exists())

    def test_json_campaign_still_works_without_attachments(self):
        client = self.api(self.admin_a)
        pv = client.post("/api/mass-email/preview/", {"roles": ["parent"]}, format="json").json()
        with mock.patch("apps.notifications.tasks.send_campaign.delay"):
            resp = client.post("/api/mass-email/campaigns/", {
                "roles": ["parent"], "subject": "s", "body": "b", "confirm": True,
                "expected_count": pv["count"], "client_token": uuid.uuid4().hex}, format="json")
        self.assertEqual(resp.status_code, 201, resp.content)

    def test_queued_deliveries_visible_before_worker(self):
        self.campaign(self.admin_a, self.a, run=False)
        rows = self.api(self.admin_a).get("/api/notifications/outbox/").json()["results"]
        self.assertEqual({r["status"] for r in rows}, {"queued"})
        self.assertEqual(len(rows), 2)


class OutboxApiTests(OutboxBase):
    def setUp(self):
        super().setUp()
        self.campaign(self.admin_a, self.a, files=[upload("a.pdf", PDF, "application/pdf")])
        self.campaign(self.admin_b, self.b, files=[upload("b.pdf", PDF, "application/pdf")])
        self.d_a = EmailDelivery.objects.filter(entity=self.a).first()
        self.d_b = EmailDelivery.objects.filter(entity=self.b).first()

    def test_admin_sees_only_own_academy(self):
        data = self.api(self.admin_a).get("/api/notifications/outbox/").json()
        self.assertEqual(data["count"], 2)
        self.assertTrue(all(r["academy"]["code"] == "OB-A" for r in data["results"]))
        self.assertEqual(self.api(self.admin_a).get(f"/api/notifications/outbox/{self.d_b.pk}/").status_code, 404)
        self.assertEqual(self.api(self.admin_a).get("/api/notifications/outbox/",
                                                    {"academy_id": self.b.pk}).status_code, 403)

    def test_attachment_download_isolation(self):
        att_b = self.d_b.content.attachments.get()
        client = self.api(self.admin_a)
        # Fichier de B demandé via un envoi de A, ou via l'envoi de B : refusé.
        self.assertEqual(client.get(f"/api/notifications/outbox/{self.d_a.pk}/attachments/{att_b.pk}/").status_code, 404)
        self.assertEqual(client.get(f"/api/notifications/outbox/{self.d_b.pk}/attachments/{att_b.pk}/").status_code, 404)
        att_a = self.d_a.content.attachments.get()
        resp = client.get(f"/api/notifications/outbox/{self.d_a.pk}/attachments/{att_a.pk}/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(b"".join(resp.streaming_content), PDF)
        self.assertIn("attachment", resp["Content-Disposition"])
        inline = client.get(f"/api/notifications/outbox/{self.d_a.pk}/attachments/{att_a.pk}/?inline=1")
        self.assertIn("inline", inline["Content-Disposition"])
        self.assertEqual(inline["X-Content-Type-Options"], "nosniff")

    def test_non_admin_forbidden(self):
        for user in (self.teacher_a, self.parent_a):
            self.assertEqual(self.api(user).get("/api/notifications/outbox/").status_code, 403)
            att = self.d_a.content.attachments.get()
            self.assertEqual(self.api(user).get(
                f"/api/notifications/outbox/{self.d_a.pk}/attachments/{att.pk}/").status_code, 403)

    def test_superadmin_global_and_filtered(self):
        client = self.api(self.superadmin)
        self.assertEqual(client.get("/api/notifications/outbox/").json()["count"], 3)
        self.assertEqual(client.get("/api/notifications/outbox/", {"academy_id": self.b.pk}).json()["count"], 1)

    def test_detail_contains_bodies_attachments_attempts(self):
        detail = self.api(self.admin_a).get(f"/api/notifications/outbox/{self.d_a.pk}/").json()
        self.assertEqual(detail["subject"], "Sortie scolaire")
        self.assertIn("Voir la pièce jointe.", detail["text_body"])
        self.assertIn("<br>", detail["html_body"])
        self.assertEqual(detail["attachments"][0]["name"], "a.pdf")
        self.assertTrue(detail["attachments"][0]["previewable"])
        self.assertEqual(len(detail["attempt_log"]), 1)
        self.assertEqual(detail["purpose_label"], "E-mail groupé")

    def test_filters_and_pagination(self):
        client = self.api(self.admin_a)
        self.assertEqual(client.get("/api/notifications/outbox/", {"to": "ob.p2"}).json()["count"], 1)
        self.assertEqual(client.get("/api/notifications/outbox/", {"status": "failed"}).json()["count"], 0)
        self.assertEqual(client.get("/api/notifications/outbox/", {"purpose": "academy_mass_email"}).json()["count"], 2)
        self.assertEqual(client.get("/api/notifications/outbox/", {"q": "pièce jointe"}).json()["count"], 2)
        today = timezone.localdate().isoformat()
        self.assertEqual(client.get("/api/notifications/outbox/", {"date_from": today}).json()["count"], 2)
        page = client.get("/api/notifications/outbox/", {"page_size": 1, "page": 2}).json()
        self.assertEqual((page["count"], len(page["results"])), (2, 1))
        self.assertEqual(client.get("/api/notifications/outbox/", {"date_from": "hier"}).status_code, 400)

    def test_legacy_delivery_without_content(self):
        legacy = EmailDelivery.objects.create(entity=self.a, purpose="fha_enrollment_ack", to_email="x@y.test",
                                              subject="Ancien", status="sent", backend="smtp")
        detail = self.api(self.admin_a).get(f"/api/notifications/outbox/{legacy.pk}/").json()
        self.assertIsNone(detail["text_body"])
        self.assertEqual(detail["content_note"], "Contenu non archivé pour cet envoi historique.")


class FailureAndRetryTests(OutboxBase):
    def test_smtp_down_then_manual_retry_without_duplicate(self):
        with mock.patch.object(mail.EmailMultiAlternatives, "send",
                               side_effect=smtplib.SMTPServerDisconnected("Connection unexpectedly closed")):
            self.campaign(self.admin_a, self.a, files=[upload("a.pdf", PDF)])
        rows = self.api(self.admin_a).get("/api/notifications/outbox/").json()["results"]
        self.assertEqual({r["status"] for r in rows}, {"retry"})
        self.assertTrue(all("SMTPServerDisconnected" in r["last_error"] for r in rows))
        client = self.api(self.admin_a)
        target = rows[0]["id"]
        first = client.post(f"/api/notifications/outbox/{target}/retry/")
        self.assertEqual(first.status_code, 200, first.content)
        self.assertEqual(first.json()["status"], "sent")
        self.assertEqual(client.post(f"/api/notifications/outbox/{target}/retry/").status_code, 409)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].attachments[0][1], PDF)
        detail = client.get(f"/api/notifications/outbox/{target}/").json()
        self.assertEqual([a["outcome"] for a in detail["attempt_log"]], ["retry", "sent"])
        self.assertTrue(detail["attempt_log"][1]["manual"])

    def test_auth_error_recorded_and_automatic_retry_from_archive(self):
        from apps.notifications.tasks import retry_due_deliveries
        with mock.patch.object(mail.EmailMultiAlternatives, "send",
                               side_effect=smtplib.SMTPAuthenticationError(535, b"5.7.8 Authentication failed")):
            d = send_tracked_email(purpose="t", to_email="a@b.test", subject="s", text_body="corps",
                                   entity=self.a, attachments=[("a.pdf", PDF, "application/pdf")])
        self.assertEqual(d.status, "retry")
        self.assertIn("SMTPAuthenticationError", d.last_error)
        EmailDelivery.objects.filter(pk=d.pk).update(next_retry_at=timezone.now() - timedelta(minutes=1))
        self.assertEqual(retry_due_deliveries(), 1)
        d.refresh_from_db()
        self.assertEqual((d.status, d.attempts), ("sent", 2))
        self.assertEqual(mail.outbox[0].attachments[0][1], PDF)
        self.assertEqual(retry_due_deliveries(), 0)
        self.assertEqual(len(mail.outbox), 1)

    def test_retry_refused_for_successful_delivery_and_other_academy(self):
        d = send_tracked_email(purpose="t", to_email="a@b.test", subject="s", text_body="b", entity=self.a)
        self.assertEqual(self.api(self.admin_a).post(f"/api/notifications/outbox/{d.pk}/retry/").status_code, 409)
        self.assertEqual(self.api(self.admin_b).post(f"/api/notifications/outbox/{d.pk}/retry/").status_code, 404)

    def test_fha_placement_notification_failure_does_not_break_business(self):
        from apps.website.fha_notifications import _send
        with mock.patch.object(mail.EmailMultiAlternatives, "send", side_effect=OSError("no route")):
            accepted = _send("Sujet", "Corps", ["parent@x.test"], entity=self.a, reference="FHA-1")
        self.assertEqual(accepted, 0)
        d = EmailDelivery.objects.get(subject_reference="FHA-1")
        self.assertEqual((d.status, d.purpose), ("retry", "fha_notification"))


class RedactedReplayTests(OutboxBase):
    """
    Un message porteur d'un lien de sécurité est archivé MASQUÉ. Le rejouer
    enverrait un lien inutilisable, présenté comme « accepté » : ni la
    relance manuelle ni la relance automatique ne doivent le faire.
    """
    RESET = "Réinitialisez : https://globalfeba.com/reset/MQ/abc-123/"

    def test_transient_failure_of_sensitive_message_is_final_and_never_replayed(self):
        from apps.notifications.tasks import retry_due_deliveries
        with mock.patch.object(mail.EmailMultiAlternatives, "send",
                               side_effect=smtplib.SMTPServerDisconnected("Connection unexpectedly closed")):
            d = send_tracked_email(purpose="password_reset", to_email="u@b.test", subject="Mot de passe",
                                   text_body=self.RESET, entity=self.a, sensitive=True)
        self.assertEqual(d.status, "failed")
        self.assertIsNone(d.next_retry_at)
        self.assertIn("SMTPServerDisconnected", d.last_error)
        self.assertIn("nouveau lien", d.last_error)
        self.assertEqual(retry_due_deliveries(), 0)
        client = self.api(self.admin_a)
        detail = client.get(f"/api/notifications/outbox/{d.pk}/").json()
        self.assertFalse(detail["can_retry"])
        self.assertIn("nouveau lien", detail["retry_note"])
        self.assertNotIn("abc-123", detail["text_body"])
        resp = client.post(f"/api/notifications/outbox/{d.pk}/retry/")
        self.assertEqual(resp.status_code, 409)
        self.assertEqual(len(mail.outbox), 0)

    @override_settings(EMAIL_BACKEND=TRACKING,
                       EMAIL_TRANSPORT_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_untracked_reset_mail_failure_cannot_be_retried_from_outbox(self):
        from django.core.mail import send_mail
        from django.core.mail.backends.locmem import EmailBackend
        with mock.patch.object(EmailBackend, "send_messages", side_effect=OSError("no route")):
            send_mail("Mot de passe", self.RESET, "noreply@feba.bj", ["u@test.io"], fail_silently=True)
        d = EmailDelivery.objects.get(purpose="untracked_module")
        self.assertEqual(d.status, "failed")
        resp = self.api(self.superadmin).post(f"/api/notifications/outbox/{d.pk}/retry/")
        self.assertEqual(resp.status_code, 409, resp.content)
        self.assertEqual(len(mail.outbox), 0)

    def test_ordinary_message_stays_retryable(self):
        with mock.patch.object(mail.EmailMultiAlternatives, "send", side_effect=OSError("no route")):
            d = send_tracked_email(purpose="t", to_email="u@b.test", subject="s",
                                   text_body="Bonjour, rien de secret.", entity=self.a, sensitive=True)
        self.assertEqual(d.status, "retry")
        detail = self.api(self.admin_a).get(f"/api/notifications/outbox/{d.pk}/").json()
        self.assertTrue(detail["can_retry"])
        self.assertIsNone(detail["retry_note"])


class TrackingBackendTests(PrivateMediaMixin, TestCase):
    @override_settings(EMAIL_BACKEND=TRACKING,
                       EMAIL_TRANSPORT_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_untracked_send_mail_is_logged_and_redacted(self):
        from django.core.mail import send_mail
        send_mail("Mot de passe", "https://globalfeba.com/reset/MQ/abc-123/", "noreply@feba.bj",
                  ["u1@test.io", "u2@test.io"])
        rows = EmailDelivery.objects.filter(purpose="untracked_module").order_by("to_email")
        self.assertEqual([r.to_email for r in rows], ["u1@test.io", "u2@test.io"])
        self.assertTrue(all(r.status == "sent" for r in rows))
        self.assertNotIn("abc-123", rows[0].content.text_body)
        self.assertIn("abc-123", mail.outbox[0].body)

    @override_settings(EMAIL_BACKEND=TRACKING,
                       EMAIL_TRANSPORT_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_tracked_messages_not_logged_twice(self):
        send_tracked_email(purpose="t", to_email="a@b.test", subject="s", text_body="b")
        self.assertEqual(EmailDelivery.objects.count(), 1)
        self.assertEqual(len(mail.outbox), 1)


class EmailConfigApiTests(OutboxBase):
    @override_settings(EMAIL_BACKEND="django.core.mail.backends.smtp.EmailBackend", EMAIL_HOST="mailpit",
                       EMAIL_HOST_USER="noreply@feba.bj", EMAIL_HOST_PASSWORD="secret-value-123")
    def test_config_masks_secrets_and_explains_capture(self):
        data = self.api(self.admin_a).get("/api/notifications/email-config/").json()
        self.assertEqual(data["transport"], "capture")
        self.assertEqual(data["user"], "n***@feba.bj")
        self.assertTrue(data["password_set"])
        self.assertNotIn("secret-value-123", json.dumps(data))
        self.assertIn("Mailpit", data["explanation"])
        self.assertTrue(data["capture_ui_url"])

    def test_test_send_traced_and_rate_limited(self):
        from django.core.cache import cache
        cache.clear()
        client = self.api(self.admin_a)
        with override_settings(EMAIL_TEST_MAX_PER_HOUR=2):
            r1 = client.post("/api/notifications/email-config/test/", {"to": "moi@test.io"}, format="json")
            client.post("/api/notifications/email-config/test/", {"to": "moi@test.io"}, format="json")
            r3 = client.post("/api/notifications/email-config/test/", {"to": "moi@test.io"}, format="json")
        self.assertEqual(r1.status_code, 200)
        self.assertEqual(r1.json()["purpose"], "smtp_test")
        self.assertEqual(r3.status_code, 429)
        self.assertEqual(EmailDelivery.objects.filter(purpose="smtp_test", entity=self.a).count(), 2)
        self.assertEqual(client.post("/api/notifications/email-config/test/", {"to": "pas-une-adresse"},
                                     format="json").status_code, 400)
        self.assertEqual(self.api(self.parent_a).post("/api/notifications/email-config/test/",
                                                      {"to": "x@test.io"}, format="json").status_code, 403)


@override_settings(EMAIL_BACKEND="django.core.mail.backends.smtp.EmailBackend", EMAIL_HOST="127.0.0.1",
                   EMAIL_USE_TLS=False, EMAIL_USE_SSL=False, EMAIL_HOST_USER="", EMAIL_HOST_PASSWORD="")
class MailpitSmtpTests(OutboxBase):
    """Vrai protocole SMTP vers Mailpit ; pièces jointes inspectées dans Mailpit."""

    def setUp(self):
        super().setUp()
        port, api = os.environ.get("MAILPIT_SMTP_PORT"), os.environ.get("MAILPIT_API_URL")
        if not port or not api:
            self.skipTest("Mailpit non configuré (MAILPIT_SMTP_PORT / MAILPIT_API_URL).")
        self.api_url = api.rstrip("/")
        urllib.request.urlopen(urllib.request.Request(f"{self.api_url}/api/v1/messages", method="DELETE"))
        override = override_settings(EMAIL_PORT=int(port), EMAIL_CAPTURE_HOSTS="127.0.0.1")
        override.enable()
        self.addCleanup(override.disable)

    def mailpit(self, path):
        return urllib.request.urlopen(f"{self.api_url}{path}").read()

    def test_campaign_attachments_arrive_in_mailpit(self):
        resp = self.campaign(self.admin_a, self.a, files=[
            upload("programme.pdf", PDF), upload("photo.png", PNG), upload("autorisation.docx", DOCX)])
        self.assertEqual(resp.status_code, 201, resp.content)
        listing = json.loads(self.mailpit("/api/v1/messages"))
        self.assertEqual(listing["total"], 2)
        for summary in listing["messages"]:
            self.assertEqual(len(summary["To"]), 1)
            message = json.loads(self.mailpit(f"/api/v1/message/{summary['ID']}"))
            names = {a["FileName"]: a for a in message["Attachments"]}
            self.assertEqual(set(names), {"programme.pdf", "photo.png", "autorisation.docx"})
            self.assertEqual(names["programme.pdf"]["ContentType"], "application/pdf")
            raw = self.mailpit(f"/api/v1/message/{summary['ID']}/part/{names['programme.pdf']['PartID']}")
            self.assertEqual(raw, PDF)
            self.assertIn("Voir la pièce jointe.", message["Text"])
        rows = EmailDelivery.objects.filter(entity=self.a)
        self.assertTrue(all(r.status == "sent" and r.transport == "capture" for r in rows))

    def test_unreachable_smtp_is_recorded(self):
        with override_settings(EMAIL_PORT=1, EMAIL_TIMEOUT=2):
            d = send_tracked_email(purpose="t", to_email="a@b.test", subject="s", text_body="b", entity=self.a)
        self.assertEqual(d.status, "retry")
        self.assertRegex(d.last_error, "ConnectionRefused|OSError|timed out")
