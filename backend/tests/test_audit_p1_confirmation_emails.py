"""
P1 — Envoi des e-mails de confirmation : une ligne = un envoi, et envoi groupé.

Cause racine du défaut signalé (« cliquer une ligne déclenche toutes les
lignes ») : côté écran, un indicateur d'occupation UNIQUE partagé par
toutes les lignes. Côté serveur, rien n'empêchait non plus deux envois
simultanés pour le même dossier. Ces tests verrouillent le serveur :
  - un appel individuel n'envoie qu'au dossier visé ;
  - double clic / double requête : un seul envoi ;
  - envoi groupé : seuls les dossiers sélectionnés, résultat par ligne ;
  - échec SMTP sur une ligne sans bloquer les autres, reprise des seuls
    échecs sans renvoyer les succès ;
  - destinataire manquant ; dossier d'une autre académie ; permissions.
"""
import smtplib
from datetime import timedelta
from unittest import mock

from django.core import mail
from django.test import TestCase, TransactionTestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import CustomUser
from apps.notifications.email_models import EmailDelivery
from apps.schools.models import School
from apps.website.models import FHAEnrollmentApplication

from .test_fha_enrollment_workflow import payload

URL = "/api/website/admin/fha-applications"


def make_fha():
    fha, _ = School.objects.update_or_create(
        code=School.CODE_FEBA_FHA,
        defaults=dict(name="FEBA French Heritage Academy", address="En ligne",
                      entity_type="online", currency_code="USD", matricule_prefix="FHA"),
    )
    return fha


def submit(first, email=None):
    data = payload(child_first_name=first, child_last_name="Test")
    if email is not None:
        data["parent1_email"] = email
    resp = APIClient().post("/api/website/fha/enroll/", data, format="json")
    assert resp.status_code == 201, resp.data
    return FHAEnrollmentApplication.objects.get(reference=resp.data["reference"])


def age_deliveries():
    """Sort de la fenêtre anti-doublon les envois faits pendant la mise en place."""
    EmailDelivery.objects.update(updated_at=timezone.now() - timedelta(minutes=5))


class ConfirmationBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.fha = make_fha()
        cls.feba = School.objects.create(name="FEBA", address="Cotonou", code="CONF-FEBA")
        cls.admin = CustomUser.objects.create_user(
            username="conf_admin", email="conf.admin@test.io", password="x",
            role="admin", school=cls.fha)
        cls.feba_admin = CustomUser.objects.create_user(
            username="conf_feba", email="conf.feba@test.io", password="x",
            role="admin", school=cls.feba)
        cls.teacher = CustomUser.objects.create_user(
            username="conf_teacher", email="conf.teacher@test.io", password="x",
            role="teacher", school=cls.fha)
        cls.apps = [submit(name, email=f"parent.{name.lower()}@example.org")
                    for name in ("Naomi", "Kofi", "Ama", "Elise")]

    def setUp(self):
        age_deliveries()
        mail.outbox.clear()
        self.client = APIClient()
        self.client.force_authenticate(self.admin)

    def acks_to(self, application):
        return [m for m in mail.outbox if m.to == [application.parent1_email]
                and application.reference in m.subject + m.body]


class IndividualTests(ConfirmationBase):
    def test_first_row_sends_only_first(self):
        resp = self.client.post(f"{URL}/{self.apps[0].id}/resend-confirmation/")
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp.json()["result"], "sent")
        self.assertEqual(resp.json()["reference"], self.apps[0].reference)
        self.assertEqual([m.to for m in mail.outbox], [[self.apps[0].parent1_email]])

    def test_other_row_sends_only_that_row(self):
        self.client.post(f"{URL}/{self.apps[2].id}/resend-confirmation/")
        self.assertEqual([m.to for m in mail.outbox], [[self.apps[2].parent1_email]])

    def test_double_click_sends_once(self):
        first = self.client.post(f"{URL}/{self.apps[1].id}/resend-confirmation/")
        second = self.client.post(f"{URL}/{self.apps[1].id}/resend-confirmation/")
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 409)
        self.assertEqual(second.json()["result"], "recently_sent")
        self.assertEqual(len(mail.outbox), 1)

    def test_explicit_resend_allowed_after_window(self):
        self.client.post(f"{URL}/{self.apps[1].id}/resend-confirmation/")
        age_deliveries()
        self.assertEqual(self.client.post(f"{URL}/{self.apps[1].id}/resend-confirmation/").status_code, 200)
        self.assertEqual(len(mail.outbox), 2)

    def test_missing_recipient(self):
        FHAEnrollmentApplication.objects.filter(pk=self.apps[3].pk).update(parent1_email="")
        resp = self.client.post(f"{URL}/{self.apps[3].id}/resend-confirmation/")
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()["result"], "missing_recipient")
        self.assertEqual(len(mail.outbox), 0)

    def test_other_academy_and_permissions(self):
        feba_client = APIClient()
        feba_client.force_authenticate(self.feba_admin)
        self.assertEqual(feba_client.post(f"{URL}/{self.apps[0].id}/resend-confirmation/").status_code, 404)
        teacher_client = APIClient()
        teacher_client.force_authenticate(self.teacher)
        self.assertEqual(teacher_client.post(f"{URL}/{self.apps[0].id}/resend-confirmation/").status_code, 403)
        self.assertEqual(len(mail.outbox), 0)


class BulkTests(ConfirmationBase):
    def bulk(self, ids, client=None, **extra):
        return (client or self.client).post(f"{URL}/bulk-resend-confirmation/", {"ids": ids, **extra}, format="json")

    def test_only_selected_rows(self):
        resp = self.bulk([self.apps[0].id, self.apps[2].id], skip_sent=False)
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual({r["result"] for r in resp.json()["results"]}, {"sent"})
        self.assertEqual(sorted(m.to[0] for m in mail.outbox),
                         sorted([self.apps[0].parent1_email, self.apps[2].parent1_email]))

    def test_all_rows(self):
        resp = self.bulk([a.id for a in self.apps], skip_sent=False)
        self.assertEqual(resp.json()["summary"], {"sent": 4})
        self.assertEqual(len(mail.outbox), 4)

    def test_skip_already_sent_by_default(self):
        # Les dossiers ont reçu leur accusé à la soumission : par défaut,
        # l'envoi groupé ne les renvoie pas.
        resp = self.bulk([a.id for a in self.apps])
        self.assertEqual(resp.json()["summary"], {"already_sent": 4})
        self.assertEqual(len(mail.outbox), 0)

    def test_duplicate_ids_processed_once(self):
        resp = self.bulk([self.apps[0].id, self.apps[0].id, str(self.apps[0].id)], skip_sent=False)
        self.assertEqual(len(resp.json()["results"]), 1)
        self.assertEqual(len(mail.outbox), 1)

    def test_other_academy_ids_rejected_per_row(self):
        foreign = FHAEnrollmentApplication.objects.create(
            **{**{k: v for k, v in payload().items() if k in {f.name for f in FHAEnrollmentApplication._meta.fields}},
               "entity": self.feba, "reference": "FEBA-XX-0001"})
        resp = self.bulk([self.apps[0].id, foreign.id, 999999], skip_sent=False)
        results = {r["id"]: r["result"] for r in resp.json()["results"]}
        self.assertEqual(results[foreign.id], "not_found")
        self.assertEqual(results[999999], "not_found")
        self.assertEqual(results[self.apps[0].id], "sent")
        self.assertNotIn(foreign.parent1_email, [m.to[0] for m in mail.outbox if foreign.reference in m.subject])

    def test_smtp_failure_on_one_row_then_retry_failures_only(self):
        target = self.apps[1].parent1_email
        original = mail.EmailMultiAlternatives.send

        def flaky(message, *a, **k):
            if message.to == [target]:
                raise smtplib.SMTPRecipientsRefused({target: (550, b"no such user")})
            return original(message, *a, **k)

        ids = [a.id for a in self.apps[:3]]
        with mock.patch.object(mail.EmailMultiAlternatives, "send", flaky):
            resp = self.bulk(ids, skip_sent=False)
        results = {r["id"]: r for r in resp.json()["results"]}
        self.assertEqual(results[self.apps[1].id]["result"], "retry")
        self.assertIn("SMTPRecipientsRefused", results[self.apps[1].id]["error"])
        self.assertEqual(results[self.apps[0].id]["result"], "sent")
        self.assertEqual(results[self.apps[2].id]["result"], "sent")
        sent_before = len(mail.outbox)
        # Reprise : on renvoie TOUTE la sélection avec skip_sent — seuls les
        # échecs repartent.
        age_deliveries()
        resp = self.bulk(ids)
        results = {r["id"]: r["result"] for r in resp.json()["results"]}
        self.assertEqual(results[self.apps[1].id], "sent")
        self.assertEqual(results[self.apps[0].id], "already_sent")
        self.assertEqual(len(mail.outbox), sent_before + 1)

    def test_missing_recipient_does_not_block_others(self):
        FHAEnrollmentApplication.objects.filter(pk=self.apps[3].pk).update(parent1_email="pas-une-adresse")
        resp = self.bulk([self.apps[3].id, self.apps[0].id], skip_sent=False)
        results = {r["id"]: r["result"] for r in resp.json()["results"]}
        self.assertEqual(results, {self.apps[3].id: "missing_recipient", self.apps[0].id: "sent"})

    def test_validation(self):
        self.assertEqual(self.bulk([]).status_code, 400)
        self.assertEqual(self.bulk(["x"]).status_code, 400)
        self.assertEqual(self.bulk(list(range(1, 102))).status_code, 400)

    def test_permissions(self):
        teacher_client = APIClient()
        teacher_client.force_authenticate(self.teacher)
        self.assertEqual(self.bulk([self.apps[0].id], client=teacher_client).status_code, 403)

    def test_list_email_state_costs_constant_queries(self):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext
        with CaptureQueriesContext(connection) as ctx:
            rows = self.client.get(f"{URL}/").json()
        rows = rows.get("results", rows)
        self.assertEqual(len(rows), 4)
        self.assertTrue(all(r["confirmation_email"]["status"] == "sent" for r in rows))
        delivery_queries = [q for q in ctx.captured_queries if "notifications_emaildelivery" in q["sql"]]
        self.assertLessEqual(len(delivery_queries), 1)


class ConcurrentConfirmationPostgresTests(TransactionTestCase):
    """Deux requêtes simultanées pour le même dossier : un seul envoi (PostgreSQL)."""

    def setUp(self):
        from django.db import connection
        if connection.vendor != "postgresql":
            self.skipTest("Concurrence réelle : PostgreSQL requis.")
        make_fha()
        self.admin = CustomUser.objects.create_user(
            username="conc_admin", email="conc.admin@test.io", password="x",
            role="admin", school=School.objects.get(code=School.CODE_FEBA_FHA))
        self.application = submit("Zoe", email="parent.zoe@example.org")
        age_deliveries()
        mail.outbox.clear()

    def test_parallel_requests(self):
        import threading
        from django.db import connections

        barrier = threading.Barrier(2)
        codes = []

        def worker():
            try:
                client = APIClient()
                client.force_authenticate(self.admin)
                barrier.wait()
                codes.append(client.post(f"{URL}/{self.application.id}/resend-confirmation/").status_code)
            finally:
                connections.close_all()

        threads = [threading.Thread(target=worker) for _ in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(sorted(codes), [200, 409])
        self.assertEqual(len([m for m in mail.outbox if m.to == ["parent.zoe@example.org"]]), 1)
