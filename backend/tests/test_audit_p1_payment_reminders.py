"""
P1 — Relances automatiques des paiements en retard (e-mail + notification).

Données fictives, backend e-mail `locmem` : aucun message réel.

Échéancier de référence (affiche FEBA 2026-2027, CE1 & CE2) :
    30/09/2026  150 000   — 30/11/2026  100 000   — 31/01/2027  79 800
"""
import datetime
import smtplib
from datetime import date, timedelta
from decimal import Decimal
from unittest import mock

from django.core import mail
from django.core.management import call_command
from django.test import TestCase, TransactionTestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import CustomUser
from apps.notifications.email_models import EmailDelivery
from apps.notifications.models import Notification
from apps.parents.models import Parent, ParentStudent
from apps.payments.models import (
    FeeInstallment, FeeSchedule, Payment, PaymentReminder, PaymentReminderPolicy, ReminderRun,
    StudentFeeArrangement,
)
from apps.payments.reminders import compute_dues, run_reminders
from apps.schools.models import Level, School, SchoolYear
from apps.students.models import Student

D = date


class ReminderBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.feba = School.objects.create(name="FEBA Rel", address="Cotonou", code="REL-FEBA",
                                         currency_code="XOF", phone="+229 01 96 69 73 63")
        cls.fha = School.objects.create(name="FHA Rel", address="En ligne", code="REL-FHA",
                                        entity_type="online", currency_code="USD",
                                        timezone="America/New_York", default_language="en")
        cls.year = SchoolYear.objects.create(school=cls.feba, name="2026-2027", is_current=True,
                                             start_date="2026-09-01", end_date="2027-06-30")
        cls.fha_year = SchoolYear.objects.create(school=cls.fha, name="2026-2027", is_current=True,
                                                 start_date="2026-09-01", end_date="2027-06-30")
        cls.ce = Level.objects.create(school=cls.feba, name="CE1", order=3)
        cls.cm = Level.objects.create(school=cls.feba, name="CM1", order=5)
        from apps.classes.models import Class
        cls.class_ce = Class.objects.create(name="CE1-A", level=cls.ce, school_year=cls.year)
        cls.class_cm = Class.objects.create(name="CM1-A", level=cls.cm, school_year=cls.year)

        cls.tuition_ce = cls.fee(cls.feba, "mensualite", 329800, level=cls.ce, installments=[
            ("1re tranche", D(2026, 9, 30), 150000), ("2e tranche", D(2026, 11, 30), 100000),
            ("3e tranche", D(2027, 1, 31), 79800)])
        cls.tuition_cm = cls.fee(cls.feba, "mensualite", 349500, level=cls.cm, installments=[
            ("1re tranche", D(2026, 9, 30), 150000), ("2e tranche", D(2026, 11, 30), 110000),
            ("3e tranche", D(2027, 1, 31), 89500)])

        cls.admin = cls.user("rel_admin", "admin", cls.feba)
        cls.parent_user = cls.user("rel_parent", "parent", cls.feba)
        cls.parent2_user = cls.user("rel_parent2", "parent", cls.feba)
        cls.alice = cls.student("Alice", cls.class_ce)
        cls.bob = cls.student("Bob", cls.class_cm)
        cls.link(cls.parent_user, cls.alice)
        cls.link(cls.parent_user, cls.bob)
        PaymentReminderPolicy.objects.create(academy=cls.feba, enabled=True, grace_days=7,
                                             interval_days=14, max_reminders=3,
                                             payment_instructions="Espèces au secrétariat ou MTN MoMo.")

    @classmethod
    def fee(cls, academy, ptype, amount, level=None, installments=(), mandatory=True, mode="split", year=None):
        fee = FeeSchedule.objects.create(
            academy=academy, payment_type=ptype, amount_minor=amount, level=level,
            school_year=year or (cls.year if academy == cls.feba else cls.fha_year),
            is_mandatory=mandatory, installment_mode=mode, label=f"{ptype} test",
        )
        for i, (label, due, minor) in enumerate(installments):
            FeeInstallment.objects.create(fee_schedule=fee, label=label, due_date=due,
                                          amount_minor=minor, order=i)
        return fee

    @classmethod
    def user(cls, name, role, school, email=None):
        return CustomUser.objects.create_user(
            username=name, email=email if email is not None else f"{name}@test.io", password="x",
            role=role, school=school, first_name=name.title(), last_name="Test")

    @classmethod
    def student(cls, first, klass, school=None, year=None):
        return Student.objects.create(school=school or cls.feba, school_year=year or cls.year,
                                      current_class=klass, first_name=first, last_name="Élève",
                                      date_of_birth="2016-05-01")

    @staticmethod
    def link(user, student, **flags):
        parent, _ = Parent.objects.get_or_create(user=user)
        return ParentStudent.objects.create(parent=parent, student=student, **flags)

    def pay(self, student, amount, ptype="mensualite", **extra):
        extra.setdefault("school_year", self.year if student.school_id == self.feba.pk else self.fha_year)
        return Payment.objects.create(student=student, payment_type=ptype, amount=Decimal(amount),
                                      payment_method="cash", payment_date=extra.pop("payment_date", D(2026, 9, 15)),
                                      **extra)

    def dues(self, on, academy=None):
        return {(i.student.first_name, i.installment.label): i
                for i in compute_dues(academy or self.feba, on).items}

    def run_engine(self, on, academy=None, **kw):
        kw.setdefault("now", timezone.now())
        with override_settings(PAYMENT_REMINDERS_ENABLED=True):
            return run_reminders(academy or self.feba, trigger=ReminderRun.TRIGGER_BEAT, on_date=on, **kw)


class ComputationTests(ReminderBase):
    def test_future_installment_is_not_due(self):
        dues = self.dues(D(2026, 9, 30))       # le jour même : pas encore en retard
        self.assertEqual(dues[("Alice", "1re tranche")].status, "upcoming")
        self.assertEqual(dues[("Alice", "2e tranche")].status, "upcoming")

    def test_overdue_installment(self):
        item = self.dues(D(2026, 10, 9))[("Alice", "1re tranche")]
        self.assertEqual((item.status, item.outstanding, item.days_overdue), ("overdue", 150000, 9))

    def test_fully_paid(self):
        self.pay(self.alice, "150000")
        self.assertEqual(self.dues(D(2026, 10, 9))[("Alice", "1re tranche")].status, "paid")

    def test_partial_payment_shows_only_balance(self):
        self.pay(self.alice, "100000")
        item = self.dues(D(2026, 10, 9))[("Alice", "1re tranche")]
        self.assertEqual((item.status, item.paid, item.outstanding), ("partial", 100000, 50000))

    def test_cancelled_and_deleted_payments_do_not_count(self):
        self.pay(self.alice, "150000", is_confirmed=False)
        self.pay(self.alice, "150000", is_deleted=True)
        self.assertEqual(self.dues(D(2026, 10, 9))[("Alice", "1re tranche")].outstanding, 150000)

    def test_pending_card_payment_suspends_reminder(self):
        from apps.payments.transaction_models import PaymentTransaction
        PaymentTransaction.objects.create(academy=self.feba, student=self.alice, school_year=self.year,
                                          payment_type="mensualite", amount_minor=150000, status="pending")
        item = self.dues(D(2026, 10, 9))[("Alice", "1re tranche")]
        self.assertIn("Paiement par carte en cours", item.blockers)

    def test_refund_reduces_amount_paid(self):
        from apps.payments.transaction_models import PaymentTransaction
        payment = self.pay(self.alice, "150000")
        PaymentTransaction.objects.create(academy=self.feba, student=self.alice, school_year=self.year,
                                          payment_type="mensualite", amount_minor=150000,
                                          amount_refunded_minor=50000, status="partially_refunded",
                                          payment=payment)
        self.assertEqual(self.dues(D(2026, 10, 9))[("Alice", "1re tranche")].outstanding, 50000)

    def test_exemption_and_discount(self):
        StudentFeeArrangement.objects.create(student=self.alice, fee_schedule=self.tuition_ce, kind="exemption")
        StudentFeeArrangement.objects.create(student=self.bob, fee_schedule=self.tuition_cm,
                                             kind="discount", discount_minor=100000)
        dues = self.dues(D(2027, 2, 15))
        self.assertTrue(all(i.status == "exempted" for k, i in dues.items() if k[0] == "Alice"))
        # Réduction imputée sur les DERNIÈRES tranches : la 1re reste due en entier.
        self.assertEqual(dues[("Bob", "3e tranche")].outstanding, 0)
        self.assertEqual(dues[("Bob", "2e tranche")].outstanding, 110000 - 10500)
        self.assertEqual(dues[("Bob", "1re tranche")].outstanding, 150000)

    def test_several_installments_and_months_unpaid_cumulative(self):
        self.pay(self.alice, "200000")      # 150 000 + 50 000 imputés dans l'ordre
        dues = self.dues(D(2027, 2, 15))
        self.assertEqual(dues[("Alice", "1re tranche")].status, "paid")
        self.assertEqual((dues[("Alice", "2e tranche")].status, dues[("Alice", "2e tranche")].outstanding),
                         ("partial", 50000))
        self.assertEqual(dues[("Alice", "3e tranche")].outstanding, 79800)

    def test_payment_with_month_is_allocated_to_that_installment(self):
        self.pay(self.alice, "100000", period_month=D(2026, 11, 1))
        dues = self.dues(D(2026, 12, 15))
        self.assertEqual(dues[("Alice", "2e tranche")].status, "paid")
        self.assertEqual(dues[("Alice", "1re tranche")].outstanding, 150000)

    def test_level_specific_amounts(self):
        dues = self.dues(D(2026, 12, 15))
        self.assertEqual(dues[("Alice", "2e tranche")].expected, 100000)
        self.assertEqual(dues[("Bob", "2e tranche")].expected, 110000)

    def test_inconsistent_schedule_is_flagged_and_blocks(self):
        FeeInstallment.objects.filter(fee_schedule=self.tuition_ce, label="3e tranche").update(amount_minor=1)
        computation = compute_dues(self.feba, D(2026, 10, 9))
        self.assertIn("fee_sum_mismatch", {a["kind"] for a in computation.anomalies})
        alice = [i for i in computation.items if i.student == self.alice]
        self.assertTrue(all(i.blockers for i in alice))

    def test_payment_without_year_blocks(self):
        Payment.objects.create(student=self.alice, payment_type="mensualite", amount=Decimal("1000"),
                               payment_method="cash", payment_date=D(2026, 9, 1))
        Payment.objects.filter(student=self.alice).update(school_year=None)
        computation = compute_dues(self.feba, D(2026, 10, 9))
        self.assertIn("payment_without_year", {a["kind"] for a in computation.anomalies})

    def test_each_fee_category(self):
        inscription = self.fee(self.feba, "inscription", 10000, installments=[("Inscription", D(2026, 9, 30), 10000)])
        cantine = self.fee(self.feba, "cantine", 15000, mandatory=False, mode="recurring",
                           installments=[("Octobre", D(2026, 10, 31), 15000), ("Novembre", D(2026, 11, 30), 15000)])
        transport = self.fee(self.feba, "transport", 20000, mandatory=False, mode="recurring",
                             installments=[("Octobre", D(2026, 10, 31), 20000)])
        garderie = self.fee(self.feba, "garderie", 41900, mandatory=False, mode="recurring",
                            installments=[("Octobre", D(2026, 10, 31), 41900)])
        other = self.fee(self.feba, "other", 5000, mandatory=False, mode="recurring",
                         installments=[("Tenue", D(2026, 10, 15), 5000)])
        for fee in (cantine, transport, garderie, other):
            StudentFeeArrangement.objects.create(student=self.alice, fee_schedule=fee, kind="subscription")
        dues = compute_dues(self.feba, D(2026, 12, 10)).items
        alice_types = {i.fee.payment_type for i in dues if i.student == self.alice and i.status == "overdue"}
        self.assertEqual(alice_types, {"mensualite", "inscription", "cantine", "transport", "garderie", "other"})
        # Bob n'est abonné à rien : seuls les frais obligatoires le concernent.
        bob_types = {i.fee.payment_type for i in dues if i.student == self.bob}
        self.assertEqual(bob_types, {"mensualite", "inscription"})
        self.assertTrue(inscription.pk)

    def test_subscription_period_limits_installments(self):
        cantine = self.fee(self.feba, "cantine", 15000, mandatory=False, mode="recurring",
                           installments=[("Octobre", D(2026, 10, 31), 15000), ("Novembre", D(2026, 11, 30), 15000)])
        StudentFeeArrangement.objects.create(student=self.alice, fee_schedule=cantine, kind="subscription",
                                             start_date=D(2026, 11, 1))
        labels = {i.installment.label for i in compute_dues(self.feba, D(2026, 12, 10)).items
                  if i.fee == cantine}
        self.assertEqual(labels, {"Novembre"})


class SendingTests(ReminderBase):
    def test_no_reminder_during_grace_period(self):
        self.run_engine(D(2026, 10, 5))   # 5 jours de retard < 7 jours de tolérance
        self.assertEqual(PaymentReminder.objects.count(), 0)
        self.assertEqual(len(mail.outbox), 0)

    def test_overdue_reminder_email_and_notification(self):
        run = self.run_engine(D(2026, 10, 9))
        self.assertEqual(run.status, "done")
        reminders = PaymentReminder.objects.order_by("student__first_name")
        self.assertEqual([r.student.first_name for r in reminders], ["Alice", "Bob"])
        self.assertTrue(all(r.status == "sent" and r.level == 1 for r in reminders))
        # Plusieurs enfants, une famille : UN seul message, chaque enfant identifié.
        self.assertEqual(len(mail.outbox), 1)
        body = mail.outbox[0].body
        self.assertIn("Alice Élève", body)
        self.assertIn("Bob Élève", body)
        self.assertIn("150\u202f000 FCFA", body)   # espace fine insécable du formatage monétaire
        self.assertIn("30/09/2026", body)
        self.assertIn("MTN MoMo", body)
        self.assertEqual(mail.outbox[0].to, [self.parent_user.email])
        notification = Notification.objects.get(user=self.parent_user, type="payment")
        self.assertIn("Alice", notification.message)
        self.assertEqual(reminders[0].notification_id, notification.pk)

    def test_paid_installment_is_not_reminded(self):
        self.pay(self.alice, "150000")
        self.run_engine(D(2026, 10, 9))
        self.assertEqual(list(PaymentReminder.objects.values_list("student__first_name", flat=True)), ["Bob"])

    def test_partial_payment_reminds_only_balance(self):
        self.pay(self.alice, "120000")
        self.run_engine(D(2026, 10, 9))
        reminder = PaymentReminder.objects.get(student=self.alice)
        self.assertEqual((reminder.amount_paid_minor, reminder.amount_due_minor), (120000, 30000))
        self.assertIn("reste à payer 30\u202f000 FCFA", mail.outbox[0].body)

    def test_repeated_run_creates_no_duplicate(self):
        self.run_engine(D(2026, 10, 9))
        self.run_engine(D(2026, 10, 9))
        self.run_engine(D(2026, 10, 12))
        self.assertEqual(PaymentReminder.objects.count(), 2)
        self.assertEqual(len(mail.outbox), 1)

    def test_second_level_after_interval_and_max(self):
        self.run_engine(D(2026, 10, 9))
        later = timezone.now() + timedelta(days=15)
        self.run_engine(D(2026, 10, 22), now=later)       # 22 jours ≥ 7 + 14
        self.assertEqual(sorted(PaymentReminder.objects.filter(student=self.alice).values_list("level", flat=True)), [1, 2])
        self.run_engine(D(2026, 11, 5), now=later + timedelta(days=15))
        self.run_engine(D(2026, 11, 20), now=later + timedelta(days=30))
        self.assertEqual(PaymentReminder.objects.filter(student=self.alice, installment__label="1re tranche").count(), 3)

    def test_payment_after_first_reminder_stops_reminders(self):
        self.run_engine(D(2026, 10, 9))
        self.pay(self.alice, "150000")
        self.run_engine(D(2026, 10, 22), now=timezone.now() + timedelta(days=15))
        self.assertEqual(PaymentReminder.objects.filter(student=self.alice).count(), 1)
        self.assertEqual(PaymentReminder.objects.filter(student=self.bob).count(), 2)

    def test_existing_reminder_is_not_produced_again(self):
        # Une exécution précédente a déjà produit la relance d'Alice.
        inst = FeeInstallment.objects.get(fee_schedule=self.tuition_ce, label="1re tranche")
        PaymentReminder.objects.create(
            academy=self.feba, student=self.alice, fee_schedule=self.tuition_ce, installment=inst,
            recipient=self.parent_user, level=1, status="sent", currency="XOF", due_date=inst.due_date,
            idempotency_key=PaymentReminder.make_key(inst.pk, self.alice.pk, self.parent_user.pk, 1),
            amount_expected_minor=150000, amount_paid_minor=0, amount_due_minor=150000,
        )
        run = self.run_engine(D(2026, 10, 9))
        self.assertEqual(PaymentReminder.objects.filter(student=self.alice).count(), 1)
        self.assertEqual(run.status, "done")
        self.assertNotIn("Alice", mail.outbox[0].body)   # seul Bob est relancé

    def test_race_on_insert_is_absorbed(self):
        """Le plan voit 0 relance, mais l'insertion heurte la clé : aucun doublon, aucun e-mail."""
        from apps.payments import reminders as engine
        real_plan = engine.plan_reminders

        def plan_then_race(*args, **kwargs):
            plan, comp = real_plan(*args, **kwargs)
            for entry in plan:
                item = entry["item"]
                PaymentReminder.objects.create(
                    academy=self.feba, student=item.student, fee_schedule=item.fee,
                    installment=item.installment, recipient=entry["recipient"], level=entry["level"],
                    status="sent", currency="XOF", due_date=item.installment.due_date,
                    idempotency_key=PaymentReminder.make_key(item.installment.pk, item.student.pk,
                                                             entry["recipient"].pk, entry["level"]),
                    amount_expected_minor=item.expected, amount_paid_minor=0, amount_due_minor=item.outstanding,
                )
            return plan, comp

        with mock.patch.object(engine, "plan_reminders", plan_then_race):
            run = self.run_engine(D(2026, 10, 9))
        self.assertEqual(PaymentReminder.objects.count(), 2)
        self.assertEqual(run.stats["duplicates_avoided"], 2)
        self.assertEqual(len(mail.outbox), 0)

    def test_several_guardians_and_dedup(self):
        self.link(self.parent2_user, self.alice)
        self.run_engine(D(2026, 10, 9))
        recipients = sorted(m.to[0] for m in mail.outbox)
        self.assertEqual(recipients, sorted([self.parent_user.email, self.parent2_user.email]))
        self.assertEqual(PaymentReminder.objects.filter(student=self.alice).count(), 2)

    def test_financial_responsible_preferred(self):
        ParentStudent.objects.filter(parent__user=self.parent_user, student=self.alice).update(
            is_financial_responsible=False)
        self.link(self.parent2_user, self.alice, is_financial_responsible=True)
        self.run_engine(D(2026, 10, 9))
        self.assertEqual(set(PaymentReminder.objects.filter(student=self.alice).values_list("recipient", flat=True)),
                         {self.parent2_user.pk})

    def test_parent_without_email_gets_internal_notification(self):
        CustomUser.objects.filter(pk=self.parent_user.pk).update(email="")
        self.run_engine(D(2026, 10, 9))
        self.assertEqual(len(mail.outbox), 0)
        self.assertTrue(all(r.status == "notified" for r in PaymentReminder.objects.all()))
        self.assertTrue(Notification.objects.filter(user=self.parent_user, type="payment").exists())

    def test_smtp_failure_then_automatic_retry_without_duplicate(self):
        from apps.notifications.tasks import retry_due_deliveries
        with mock.patch.object(mail.EmailMultiAlternatives, "send",
                               side_effect=smtplib.SMTPServerDisconnected("down")):
            self.run_engine(D(2026, 10, 9))
        self.assertTrue(all(r.status == "retry" for r in PaymentReminder.objects.all()))
        self.assertEqual(Notification.objects.filter(user=self.parent_user).count(), 1)
        EmailDelivery.objects.update(next_retry_at=timezone.now() - timedelta(minutes=1))
        self.assertEqual(retry_due_deliveries(), 1)
        self.assertTrue(all(r.status == "sent" for r in PaymentReminder.objects.all()))
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(retry_due_deliveries(), 0)
        self.assertEqual(Notification.objects.filter(user=self.parent_user).count(), 1)

    def test_worker_restart_between_record_and_send(self):
        inst = FeeInstallment.objects.get(fee_schedule=self.tuition_ce, label="1re tranche")
        PaymentReminder.objects.create(
            academy=self.feba, student=self.alice, fee_schedule=self.tuition_ce, installment=inst,
            recipient=self.parent_user, level=1, currency="XOF", due_date=inst.due_date,
            idempotency_key=PaymentReminder.make_key(inst.pk, self.alice.pk, self.parent_user.pk, 1),
            amount_expected_minor=150000, amount_paid_minor=0, amount_due_minor=150000,
        )
        PaymentReminder.objects.update(created_at=timezone.now() - timedelta(hours=1))
        run = self.run_engine(D(2026, 10, 9))
        self.assertEqual(run.stats["resumed"], 1)
        alice = PaymentReminder.objects.get(student=self.alice)
        self.assertEqual(alice.status, "sent")
        self.assertEqual(PaymentReminder.objects.filter(student=self.alice).count(), 1)

    def test_schedule_change_after_reminder_keeps_snapshot(self):
        self.run_engine(D(2026, 10, 9))
        FeeInstallment.objects.filter(fee_schedule=self.tuition_ce, label="1re tranche").update(amount_minor=140000)
        FeeInstallment.objects.filter(fee_schedule=self.tuition_ce, label="2e tranche").update(amount_minor=110000)
        reminder = PaymentReminder.objects.get(student=self.alice)
        self.assertEqual(reminder.amount_due_minor, 150000)
        self.assertEqual(self.dues(D(2026, 10, 9))[("Alice", "1re tranche")].outstanding, 140000)
        FeeInstallment.objects.filter(fee_schedule=self.tuition_ce).delete()
        reminder.refresh_from_db()
        self.assertIsNone(reminder.installment_id)
        self.assertEqual(reminder.installment_label, "1re tranche")

    def test_multi_academy_isolation(self):
        fha_fee = self.fee(self.fha, "mensualite", 12550, installments=[("October", D(2026, 10, 1), 12550)])
        fha_parent = self.user("fha_parent", "parent", self.fha)
        # La langue du message suit la préférence du responsable.
        CustomUser.objects.filter(pk=fha_parent.pk).update(preferred_language="en")
        fha_kid = self.student("Fhakid", None, school=self.fha, year=self.fha_year)
        self.link(fha_parent, fha_kid)
        PaymentReminderPolicy.objects.create(academy=self.fha, enabled=True, grace_days=3)
        self.run_engine(D(2026, 10, 9))
        self.assertFalse(PaymentReminder.objects.filter(academy=self.fha).exists())
        self.assertNotIn(fha_parent.email, [m.to[0] for m in mail.outbox])
        mail.outbox.clear()
        self.run_engine(D(2026, 10, 9), academy=self.fha)
        self.assertEqual([m.to[0] for m in mail.outbox], [fha_parent.email])
        self.assertIn("$125.50", mail.outbox[0].body)
        self.assertIn("payment reminder", mail.outbox[0].subject)
        self.assertTrue(fha_fee.pk)

    def test_parent_of_other_academy_never_reminded(self):
        stranger = self.user("stranger", "parent", self.fha)
        parent = Parent.objects.create(user=stranger)
        ParentStudent.objects.bulk_create([ParentStudent(parent=parent, student=self.alice)])  # contourne clean()
        computation_run = self.run_engine(D(2026, 10, 9))
        self.assertNotIn(stranger.email, [m.to[0] for m in mail.outbox])
        self.assertGreaterEqual(computation_run.stats["anomalies"], 1)

    def test_dry_run_writes_and_sends_nothing(self):
        with override_settings(PAYMENT_REMINDERS_ENABLED=True):
            run = run_reminders(self.feba, trigger="manual", on_date=D(2026, 10, 9), dry_run=True)
        self.assertEqual(run.trigger, "dry_run")
        self.assertEqual(len(run.plan), 2)
        self.assertEqual(PaymentReminder.objects.count(), 0)
        self.assertEqual(len(mail.outbox), 0)
        self.assertFalse(Notification.objects.exists())


class SchedulingTests(ReminderBase):
    def test_globally_disabled_by_default_and_logged(self):
        from apps.payments.tasks import run_payment_reminders
        with mock.patch("apps.core.age.timezone.now",
                        return_value=datetime.datetime(2026, 10, 9, 8, tzinfo=datetime.timezone.utc)):
            run_payment_reminders()
        self.assertEqual(PaymentReminder.objects.count(), 0)
        self.assertEqual(len(mail.outbox), 0)
        run = ReminderRun.objects.get(academy=self.feba)
        self.assertEqual(run.status, "skipped")
        self.assertIn("PAYMENT_REMINDERS_ENABLED", run.error)

    def test_policy_disabled_is_respected(self):
        from apps.payments.tasks import run_payment_reminders
        PaymentReminderPolicy.objects.filter(academy=self.feba).update(enabled=False)
        with override_settings(PAYMENT_REMINDERS_ENABLED=True):
            run_payment_reminders()
        self.assertEqual(PaymentReminder.objects.count(), 0)
        self.assertIn("désactivées", ReminderRun.objects.get(academy=self.feba).error)

    def test_beat_entry_is_configured(self):
        from django.conf import settings
        entry = settings.CELERY_BEAT_SCHEDULE["relances-paiements-quotidiennes"]
        self.assertEqual(entry["task"], "payments.run_payment_reminders")
        self.assertIn("notifications.retry_due_deliveries",
                      {e["task"] for e in settings.CELERY_BEAT_SCHEDULE.values()})


class ApiTests(ReminderBase):
    def client_for(self, user):
        client = APIClient()
        client.force_authenticate(user)
        return client

    def test_preview_lists_amounts_and_planned_reminders(self):
        resp = self.client_for(self.admin).get("/api/payments/reminders/preview/", {"on": "2026-10-09"})
        self.assertEqual(resp.status_code, 200, resp.content)
        data = resp.json()
        self.assertEqual(data["planned_count"], 2)
        alice = next(i for i in data["items"] if i["student_name"].startswith("Alice"))
        self.assertEqual(alice["outstanding_display"], "150\u202f000 FCFA")
        self.assertEqual(alice["planned_reminders"][0]["level"], 1)
        self.assertEqual(PaymentReminder.objects.count(), 0)

    def test_status_reports_degraded_state(self):
        data = self.client_for(self.admin).get("/api/payments/reminders/status/").json()
        self.assertFalse(data["operational"])
        self.assertFalse(data["global_enabled"])
        self.assertTrue(any("PAYMENT_REMINDERS_ENABLED" in issue for issue in data["issues"]))

    def test_manual_run_refused_when_globally_disabled(self):
        resp = self.client_for(self.admin).post("/api/payments/reminders/run/", {"confirm": True}, format="json")
        self.assertEqual(resp.status_code, 409)

    def test_manual_run_queued_when_enabled(self):
        with override_settings(PAYMENT_REMINDERS_ENABLED=True), \
                mock.patch("apps.payments.tasks.run_payment_reminders_for.delay") as delay:
            resp = self.client_for(self.admin).post("/api/payments/reminders/run/", {"confirm": True}, format="json")
        self.assertEqual(resp.status_code, 202)
        delay.assert_called_once_with(self.feba.pk, self.admin.pk)

    def test_policy_update_and_pause(self):
        client = self.client_for(self.admin)
        resp = client.patch("/api/payments/reminders/policy/", {"enabled": False, "grace_days": 10,
                                                                "paused_reason": "Vacances"}, format="json")
        self.assertEqual(resp.status_code, 200, resp.content)
        policy = PaymentReminderPolicy.objects.get(academy=self.feba)
        self.assertEqual((policy.enabled, policy.grace_days), (False, 10))

    def test_permissions_and_isolation(self):
        teacher = self.user("rel_teacher", "teacher", self.feba)
        self.assertEqual(self.client_for(teacher).get("/api/payments/reminders/status/").status_code, 403)
        self.assertEqual(self.client_for(self.parent_user).get("/api/payments/fee-schedules/").status_code, 403)
        fha_admin = self.user("rel_fha_admin", "admin", self.fha)
        rows = self.client_for(fha_admin).get("/api/payments/fee-schedules/").json()
        self.assertEqual(rows, [])
        resp = self.client_for(fha_admin).get("/api/payments/reminders/preview/", {"academy_id": self.feba.pk})
        self.assertEqual(resp.status_code, 403)

    def test_fee_schedule_crud_with_installments(self):
        client = self.client_for(self.admin)
        resp = client.post("/api/payments/fee-schedules/", {
            "payment_type": "transport", "label": "Transport", "amount": "60000", "is_mandatory": False,
            "installment_mode": "split", "school_year": self.year.pk,
            "installments": [{"label": "T1", "due_date": "2026-10-15", "amount": "30000"},
                             {"label": "T2", "due_date": "2027-01-15", "amount": "30000"}],
        }, format="json")
        self.assertEqual(resp.status_code, 201, resp.content)
        fee_id = resp.json()["id"]
        self.assertTrue(resp.json()["is_consistent"])
        resp = client.patch(f"/api/payments/fee-schedules/{fee_id}/", {
            "installments": [{"label": "T1", "due_date": "2026-10-15", "amount": "60000"}]}, format="json")
        self.assertEqual(len(resp.json()["installments"]), 1)
        # Niveau d'une autre académie refusé.
        fha_level = Level.objects.create(school=self.fha, name="Juniors")
        resp = client.post("/api/payments/fee-schedules/", {
            "payment_type": "cantine", "amount": "1000", "level": fha_level.pk}, format="json")
        self.assertEqual(resp.status_code, 400)

    def test_arrangement_cannot_cross_academy(self):
        fha_kid = self.student("Fhakid", None, school=self.fha, year=self.fha_year)
        resp = self.client_for(self.admin).post("/api/payments/fee-arrangements/", {
            "student": fha_kid.pk, "fee_schedule": self.tuition_ce.pk, "kind": "exemption"}, format="json")
        self.assertEqual(resp.status_code, 400)


class LoadFeePlanCommandTests(TestCase):
    def test_flyer_plan_dry_run_then_apply(self):
        from io import StringIO
        feba = School.objects.create(name="FEBA Plan", address="x", code="FEBA", currency_code="XOF")
        SchoolYear.objects.create(school=feba, name="2026-2027", start_date="2026-09-01", end_date="2027-06-30")
        for name in ("Maternelle 1", "Maternelle 2", "CI", "CP", "CE1", "CE2", "CM1", "CM2"):
            Level.objects.create(school=feba, name=name)
        path = "apps/payments/fee_plans/feba_2026_2027.json"
        out = StringIO()
        call_command("load_fee_plan", path, stdout=out)
        self.assertIn("Simulation", out.getvalue())
        self.assertFalse(FeeSchedule.objects.exists())
        call_command("load_fee_plan", path, "--apply", stdout=StringIO())
        cm2 = FeeSchedule.objects.get(level__name="CM2", payment_type="mensualite")
        self.assertEqual(cm2.amount_minor, 349500)
        self.assertEqual([i.amount_minor for i in cm2.installments.order_by("due_date")], [150000, 110000, 89500])
        garderie = FeeSchedule.objects.get(payment_type="garderie")
        self.assertFalse(garderie.is_mandatory)
        self.assertEqual(garderie.installments.count(), 10)
        # Rejouer sans --update ne modifie rien.
        call_command("load_fee_plan", path, "--apply", stdout=StringIO())
        self.assertEqual(FeeSchedule.objects.count(), 10)


class ConcurrentRunsPostgresTests(TransactionTestCase):
    """
    Deux exécutions SIMULTANÉES (deux threads, deux connexions) : la clé
    d'idempotence unique en base garantit une seule relance. Exécuté sur
    PostgreSQL uniquement : SQLite verrouille toute la base et ne prouve
    rien sur la concurrence.
    """

    def setUp(self):
        from django.db import connection
        if connection.vendor != "postgresql":
            self.skipTest("Concurrence réelle : PostgreSQL requis.")
        ReminderBase.setUpTestData.__func__(ReminderBase)
        self.feba = ReminderBase.feba

    def test_two_parallel_runs_produce_one_reminder_each(self):
        import threading
        from django.db import connections

        barrier = threading.Barrier(2)
        results = []

        def worker():
            try:
                barrier.wait()
                with override_settings(PAYMENT_REMINDERS_ENABLED=True):
                    results.append(run_reminders(self.feba, trigger="beat", on_date=D(2026, 10, 9)).stats)
            finally:
                connections.close_all()

        threads = [threading.Thread(target=worker) for _ in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(PaymentReminder.objects.count(), 2)
        self.assertEqual(len({r.idempotency_key for r in PaymentReminder.objects.all()}), 2)
        self.assertEqual(sum(r.get("reminders", 0) for r in results), 2)
