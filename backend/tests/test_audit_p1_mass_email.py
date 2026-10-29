"""
P1 — Envoi d'e-mails par académie et par type de profil.

Aucun e-mail réel : le backend `locmem` capture les messages dans
`django.core.mail.outbox`. Un test d'intégration SMTP séparé
(`MailpitSmtpIntegrationTests`) s'exécute contre Mailpit quand
`MAILPIT_SMTP_PORT` est défini — jamais contre un serveur réel.
"""
import json
import os
import smtplib
import urllib.request
import uuid
from datetime import timedelta
from unittest import mock

from django.core import mail
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import CustomUser
from apps.notifications.campaign_models import EmailCampaign, EmailCampaignRecipient
from apps.notifications.campaigns import process_campaign, recover_stale
from apps.notifications.email_models import EmailDelivery
from apps.schools.models import School

URL = "/api/mass-email"


def token():
    return uuid.uuid4().hex


class MassEmailBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.feba = School.objects.create(name="FEBA Mail", address="x", code="ME-FEBA")
        cls.fha = School.objects.create(name="FHA Mail", address="x", code="ME-FHA", entity_type="online")

        def mk(name, role, school, email=None, active=True):
            return CustomUser.objects.create_user(
                username=name, email=email if email is not None else f"{name}@test.io",
                password="x", role=role, school=school, first_name=name.title(),
                last_name="Test", is_active=active,
            )

        cls.admin = mk("admin_feba", "admin", cls.feba)
        cls.admin_fha = mk("admin_fha", "admin", cls.fha)
        cls.superadmin = mk("super", "superadmin", None)
        cls.teachers = [mk(f"teacher{i}", "teacher", cls.feba) for i in range(3)]
        cls.parents = [mk(f"parent{i}", "parent", cls.feba) for i in range(4)]
        cls.students = [mk(f"student{i}", "student", cls.feba) for i in range(2)]
        cls.inactive_parent = mk("parentoff", "parent", cls.feba, active=False)
        cls.fha_parent = mk("fhaparent", "parent", cls.fha)
        # Adresse invalide insérée hors validation (donnée historique).
        cls.bad_teacher = mk("badteacher", "teacher", cls.feba, email="pas-une-adresse")

    def client_for(self, user):
        client = APIClient()
        client.force_authenticate(user)
        return client

    def preview(self, user, **audience):
        return self.client_for(user).post(f"{URL}/preview/", audience, format="json")

    def send(self, user, *, subject="Réunion", body="Bonjour,\nRéunion lundi.", expected=None,
             client_token=None, run=True, **audience):
        client = self.client_for(user)
        if expected is None:
            pv = client.post(f"{URL}/preview/", audience, format="json")
            assert pv.status_code == 200, pv.content
            expected = pv.json()["count"]
        with mock.patch("apps.notifications.tasks.send_campaign.delay") as delay:
            with self.captureOnCommitCallbacks(execute=True):
                resp = client.post(f"{URL}/campaigns/", {
                    **audience, "subject": subject, "body": body, "confirm": True,
                    "expected_count": expected, "client_token": client_token or token(),
                }, format="json")
        if run and resp.status_code in (200, 201):
            for call in delay.call_args_list:
                process_campaign(*call.args)
        return resp


class AudienceTests(MassEmailBase):
    def test_options_list_real_roles_only(self):
        data = self.client_for(self.admin).get(f"{URL}/options/").json()
        roles = {r["role"]: r for r in data["roles"]}
        self.assertEqual(set(roles), {"admin", "teacher", "parent", "student"})
        self.assertEqual(roles["parent"]["count"], 5)          # 4 actifs + 1 inactif
        self.assertEqual(roles["parent"]["active_count"], 4)
        self.assertNotIn("superadmin", roles)
        self.assertEqual(data["academy"]["code"], "ME-FEBA")

    def test_single_recipient(self):
        resp = self.send(self.admin, include_ids=[self.parents[0].id])
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [self.parents[0].email])

    def test_several_selected_recipients(self):
        ids = [self.parents[0].id, self.teachers[1].id]
        self.send(self.admin, include_ids=ids)
        self.assertEqual(sorted(m.to[0] for m in mail.outbox),
                         sorted([self.parents[0].email, self.teachers[1].email]))

    def test_whole_profile_type(self):
        resp = self.send(self.admin, roles=["parent"])
        self.assertEqual(resp.json()["total_recipients"], 4)
        self.assertEqual(len(mail.outbox), 4)
        self.assertNotIn(self.fha_parent.email, [m.to[0] for m in mail.outbox])

    def test_several_profile_types(self):
        self.send(self.admin, roles=["parent", "student"])
        self.assertEqual(len(mail.outbox), 6)

    def test_all_profiles_of_academy(self):
        resp = self.send(self.admin, all_profiles=True)
        # admin + 3 enseignants + 4 parents + 2 élèves ; inactif et adresse
        # invalide ignorés et rapportés.
        self.assertEqual(resp.json()["total_recipients"], 10)
        self.assertEqual(resp.json()["skipped_count"], 2)
        self.assertEqual(len(mail.outbox), 10)
        recipients = {m.to[0] for m in mail.outbox}
        self.assertNotIn(self.superadmin.email, recipients)
        self.assertNotIn(self.fha_parent.email, recipients)

    def test_exclusions(self):
        self.send(self.admin, roles=["parent"], exclude_ids=[self.parents[0].id])
        self.assertNotIn(self.parents[0].email, [m.to[0] for m in mail.outbox])
        self.assertEqual(len(mail.outbox), 3)

    def test_inactive_missing_and_invalid_are_reported(self):
        pv = self.preview(self.admin, roles=["parent", "teacher"]).json()
        skipped = {r["user_id"]: r["status"] for r in pv["skipped"]}
        self.assertEqual(skipped[self.inactive_parent.id], "skipped_inactive")
        self.assertEqual(skipped[self.bad_teacher.id], "skipped_invalid_email")

    def test_user_without_email(self):
        CustomUser.objects.filter(pk=self.students[0].pk).update(email="")
        pv = self.preview(self.admin, roles=["student"]).json()
        self.assertEqual(pv["count"], 1)
        self.assertEqual(pv["skipped"][0]["status"], "skipped_no_email")

    def test_duplicates_removed_case_insensitive(self):
        CustomUser.objects.filter(pk=self.parents[1].pk).update(email=self.parents[0].email.upper())
        pv = self.preview(self.admin, roles=["parent"]).json()
        self.assertEqual(pv["count"], 3)
        self.assertIn("skipped_duplicate", {r["status"] for r in pv["skipped"]})
        # Inclure deux fois le même compte ne le fait pas compter deux fois.
        pv = self.preview(self.admin, include_ids=[self.teachers[0].id, self.teachers[0].id]).json()
        self.assertEqual(pv["count"], 1)

    def test_recipients_never_see_each_other(self):
        self.send(self.admin, roles=["teacher"])
        for message in mail.outbox:
            self.assertEqual(len(message.to), 1)
            self.assertFalse(message.cc)
            self.assertFalse(message.bcc)


class SecurityTests(MassEmailBase):
    def test_admin_cannot_target_other_academy_user(self):
        resp = self.preview(self.admin, include_ids=[self.fha_parent.id])
        self.assertEqual(resp.status_code, 400)
        resp = self.send(self.admin, include_ids=[self.fha_parent.id], expected=1)
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(len(mail.outbox), 0)
        self.assertFalse(EmailCampaign.objects.exists())

    def test_admin_cannot_pick_other_academy(self):
        resp = self.client_for(self.admin).get(f"{URL}/options/", {"academy_id": self.fha.id})
        self.assertEqual(resp.status_code, 403)
        resp = self.client_for(self.admin).post(
            f"{URL}/preview/", {"academy_id": self.fha.id, "roles": ["parent"]}, format="json")
        self.assertEqual(resp.status_code, 403)

    def test_superadmin_must_choose_academy_and_stays_in_it(self):
        client = self.client_for(self.superadmin)
        self.assertEqual(client.post(f"{URL}/preview/", {"roles": ["parent"]}, format="json").status_code, 400)
        pv = client.post(f"{URL}/preview/", {"academy_id": self.fha.id, "roles": ["parent"]},
                         format="json").json()
        self.assertEqual([r["user_id"] for r in pv["recipients"]], [self.fha_parent.id])

    def test_non_admin_roles_forbidden(self):
        for user in (self.teachers[0], self.parents[0], self.students[0]):
            self.assertEqual(self.client_for(user).get(f"{URL}/options/").status_code, 403)
            self.assertEqual(self.preview(user, roles=["parent"]).status_code, 403)

    def test_campaign_of_other_academy_is_invisible(self):
        self.send(self.admin_fha, roles=["parent"])
        campaign = EmailCampaign.objects.get()
        resp = self.client_for(self.admin).get(f"{URL}/campaigns/{campaign.id}/")
        self.assertEqual(resp.status_code, 404)
        self.assertEqual(self.client_for(self.admin).get(f"{URL}/campaigns/").json()["results"], [])

    def test_confirmation_and_expected_count_required(self):
        client = self.client_for(self.admin)
        resp = client.post(f"{URL}/campaigns/", {
            "roles": ["parent"], "subject": "s", "body": "b", "client_token": token(),
            "expected_count": 4,
        }, format="json")
        self.assertEqual(resp.status_code, 400)       # pas de confirm
        resp = self.send(self.admin, roles=["parent"], expected=99)
        self.assertEqual(resp.status_code, 400)       # le nombre a « changé »
        self.assertIn("expected_count", resp.json())

    @override_settings(MASS_EMAIL_MAX_RECIPIENTS=3)
    def test_recipient_ceiling(self):
        resp = self.send(self.admin, roles=["parent"], expected=4)
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(len(mail.outbox), 0)

    def test_subject_and_body_required(self):
        self.assertEqual(self.send(self.admin, roles=["parent"], subject=" ").status_code, 400)
        self.assertEqual(self.send(self.admin, roles=["parent"], body="").status_code, 400)

    def test_unknown_role_rejected(self):
        self.assertEqual(self.preview(self.admin, roles=["superadmin"]).status_code, 400)


class ReliabilityTests(MassEmailBase):
    def test_double_submit_creates_one_campaign(self):
        same = token()
        first = self.send(self.admin, roles=["parent"], client_token=same)
        second = self.send(self.admin, roles=["parent"], client_token=same)
        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 200)
        self.assertFalse(second.json()["created"])
        self.assertEqual(EmailCampaign.objects.count(), 1)
        self.assertEqual(len(mail.outbox), 4)

    def test_rerunning_task_never_resends(self):
        self.send(self.admin, roles=["parent"])
        campaign = EmailCampaign.objects.get()
        process_campaign(campaign.id)
        process_campaign(campaign.id)
        self.assertEqual(len(mail.outbox), 4)
        campaign.refresh_from_db()
        self.assertEqual(campaign.status, EmailCampaign.DONE)

    def test_smtp_failure_on_one_recipient_then_retry_only_failed(self):
        target = self.parents[2].email
        original = mail.EmailMultiAlternatives.send

        def flaky(message, *args, **kwargs):
            if message.to == [target]:
                raise smtplib.SMTPRecipientsRefused({target: (550, b"mailbox unavailable")})
            return original(message, *args, **kwargs)

        with mock.patch.object(mail.EmailMultiAlternatives, "send", flaky):
            resp = self.send(self.admin, roles=["parent"])
        campaign = EmailCampaign.objects.get(pk=resp.json()["id"])
        detail = self.client_for(self.admin).get(f"{URL}/campaigns/{campaign.id}/").json()
        self.assertEqual(detail["status"], "partial")
        self.assertEqual(detail["counts"]["sent"], 3)
        self.assertEqual(detail["counts"]["retry"], 1)
        failed_row = next(r for r in detail["recipients"] if r["email"] == target)
        self.assertIn("SMTPRecipientsRefused", failed_row["error"])
        self.assertEqual(len(mail.outbox), 3)

        # Relance des seuls échecs : les trois envois réussis ne repartent pas.
        with mock.patch("apps.notifications.tasks.send_campaign.delay") as delay:
            with self.captureOnCommitCallbacks(execute=True):
                retry = self.client_for(self.admin).post(f"{URL}/campaigns/{campaign.id}/retry-failed/")
        self.assertEqual(retry.json()["requeued"], 1)
        process_campaign(*delay.call_args.args)
        self.assertEqual(len(mail.outbox), 4)
        self.assertEqual([m.to[0] for m in mail.outbox].count(target), 1)
        campaign.refresh_from_db()
        self.assertEqual(campaign.status, EmailCampaign.DONE)

    def test_automatic_retry_task(self):
        from apps.notifications.tasks import retry_due_deliveries

        target = self.teachers[0].email
        original = mail.EmailMultiAlternatives.send

        def down(message, *a, **k):
            if message.to == [target]:
                raise smtplib.SMTPServerDisconnected("Connection unexpectedly closed")
            return original(message, *a, **k)

        with mock.patch.object(mail.EmailMultiAlternatives, "send", down):
            self.send(self.admin, include_ids=[self.teachers[0].id])
        delivery = EmailDelivery.objects.get(to_email=target)
        self.assertEqual(delivery.status, EmailDelivery.RETRY)
        EmailDelivery.objects.filter(pk=delivery.pk).update(next_retry_at=timezone.now() - timedelta(minutes=1))
        self.assertEqual(retry_due_deliveries(), 1)
        delivery.refresh_from_db()
        self.assertEqual(delivery.status, EmailDelivery.SENT)
        self.assertEqual(delivery.attempts, 2)
        recipient = EmailCampaignRecipient.objects.get(email=target)
        self.assertEqual(recipient.status, EmailCampaignRecipient.SENT)
        # Rejouer la tâche ne renvoie rien.
        self.assertEqual(retry_due_deliveries(), 0)
        self.assertEqual(len(mail.outbox), 1)

    def test_worker_crash_recovery_without_duplicate(self):
        resp = self.send(self.admin, roles=["teacher"], run=False)
        campaign = EmailCampaign.objects.get(pk=resp.json()["id"])
        first, second = campaign.recipients.filter(status="pending").order_by("pk")[:2]
        # Simulation : le worker a envoyé `first` puis s'est arrêté avant de
        # mettre la ligne à jour ; `second` était réservé mais pas envoyé.
        # Chaque destinataire a son envoi enregistré dès la création :
        # le worker l'a tenté avec succès, puis s'est arrêté.
        from apps.notifications.mailer import deliver
        deliver(first.delivery)
        old = timezone.now() - timedelta(hours=1)
        EmailCampaignRecipient.objects.filter(pk__in=[first.pk, second.pk]).update(status="sending")
        EmailCampaignRecipient.objects.filter(pk__in=[first.pk, second.pk]).update(updated_at=old)
        self.assertEqual(recover_stale(campaign.id), 2)
        process_campaign(campaign.id)
        sent_to = [m.to[0] for m in mail.outbox]
        self.assertEqual(sent_to.count(first.email), 1)
        self.assertEqual(sent_to.count(second.email), 1)
        self.assertEqual(len(sent_to), 3)

    def test_broker_down_is_reported_not_hidden(self):
        client = self.client_for(self.admin)
        expected = self.preview(self.admin, roles=["parent"]).json()["count"]
        with mock.patch("apps.notifications.tasks.send_campaign.delay", side_effect=ConnectionError("redis down")):
            with self.captureOnCommitCallbacks(execute=True):
                resp = client.post(f"{URL}/campaigns/", {
                    "roles": ["parent"], "subject": "s", "body": "b", "confirm": True,
                    "expected_count": expected, "client_token": token()}, format="json")
        self.assertEqual(resp.status_code, 201)
        campaign = EmailCampaign.objects.get()
        self.assertIn("File d'attente indisponible", campaign.last_error)
        self.assertEqual(len(mail.outbox), 0)
        # La tâche planifiée de reprise envoie dès que le service revient.
        from apps.notifications.tasks import process_pending_campaigns
        process_pending_campaigns()
        self.assertEqual(len(mail.outbox), 4)
        campaign.refresh_from_db()
        self.assertEqual(campaign.last_error, "")

    def test_bulk_volume(self):
        CustomUser.objects.bulk_create([
            CustomUser(username=f"bulk{i}", email=f"bulk{i}@test.io", role="parent",
                       school=self.feba, first_name="B", last_name=str(i))
            for i in range(180)
        ])
        with override_settings(MASS_EMAIL_BATCH_SIZE=25):
            resp = self.send(self.admin, roles=["parent"])
        self.assertEqual(resp.json()["total_recipients"], 184)
        self.assertEqual(len(mail.outbox), 184)
        self.assertEqual(len({m.to[0] for m in mail.outbox}), 184)

    @override_settings(MASS_EMAIL_MAX_CAMPAIGNS_PER_HOUR=2)
    def test_hourly_campaign_limit(self):
        self.assertEqual(self.send(self.admin, roles=["admin"]).status_code, 201)
        self.assertEqual(self.send(self.admin, roles=["admin"]).status_code, 201)
        self.assertEqual(self.send(self.admin, roles=["admin"]).status_code, 400)


@override_settings(EMAIL_BACKEND="django.core.mail.backends.smtp.EmailBackend",
                   EMAIL_HOST="127.0.0.1", EMAIL_USE_TLS=False, EMAIL_USE_SSL=False,
                   EMAIL_HOST_USER="", EMAIL_HOST_PASSWORD="")
class MailpitSmtpIntegrationTests(MassEmailBase):
    """Vrai protocole SMTP, vers Mailpit (serveur de test local) uniquement."""

    def setUp(self):
        port = os.environ.get("MAILPIT_SMTP_PORT")
        api = os.environ.get("MAILPIT_API_URL")
        if not port or not api:
            self.skipTest("Mailpit non configuré (MAILPIT_SMTP_PORT / MAILPIT_API_URL).")
        self.api = api.rstrip("/")
        urllib.request.urlopen(urllib.request.Request(f"{self.api}/api/v1/messages", method="DELETE"))
        # 127.0.0.1 pourrait être un vrai relais : on déclare explicitement
        # que c'est ici un serveur de CAPTURE (Mailpit).
        self.override = override_settings(EMAIL_PORT=int(port), EMAIL_CAPTURE_HOSTS="127.0.0.1")
        self.override.enable()
        self.addCleanup(self.override.disable)

    def test_individual_messages_through_smtp(self):
        resp = self.send(self.admin, roles=["teacher"])
        self.assertEqual(resp.status_code, 201, resp.content)
        listing = json.load(urllib.request.urlopen(f"{self.api}/api/v1/messages"))
        self.assertEqual(listing["total"], 3)
        for message in listing["messages"]:
            self.assertEqual(len(message["To"]), 1)
            self.assertFalse(message.get("Cc"))
            self.assertFalse(message.get("Bcc"))
        campaign = EmailCampaign.objects.get()
        self.assertEqual(campaign.status, EmailCampaign.DONE)
        # Mailpit ACCEPTE mais ne distribue pas : jamais « fournisseur réel ».
        for r in campaign.recipients.filter(status="sent"):
            self.assertEqual(r.delivery.transport, "capture")
            self.assertFalse(r.delivery.used_real_provider)
