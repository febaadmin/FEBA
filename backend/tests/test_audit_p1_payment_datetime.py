"""
P1 — Date ET heure des transactions de paiement.

Cause racine : `Payment.payment_date` est un DateField ; l'heure n'était
conservée nulle part. Ces tests verrouillent :
  - l'heure saisie, convertie depuis le fuseau DE L'ACADÉMIE (Cotonou UTC+1,
    New York UTC-4 en octobre) et restituée « JJ/MM/AAAA HH:mm » ;
  - l'heure d'enregistrement quand le paiement est saisi le jour même ;
  - l'ABSENCE d'heure (jamais inventée) pour un paiement antidaté ;
  - le passage de jour et de mois (23 h 30 à New York = lendemain en UTC) ;
  - le tri chronologique et les filtres par date ;
  - la reprise des données historiques (migration 0011) sans altération ;
  - le paiement carte (date locale de l'académie, heure de confirmation) ;
  - l'isolation : impossible d'encaisser sur l'élève d'une autre académie.
"""
import datetime
import importlib
from decimal import Decimal
from unittest import mock

from django.apps import apps as django_apps
from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import CustomUser
from apps.payments.models import Payment
from apps.schools.models import School, SchoolYear
from apps.students.models import Student

UTC = datetime.timezone.utc


def at(*args):
    return datetime.datetime(*args, tzinfo=UTC)


class PaymentDateTimeBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.feba = School.objects.create(
            name="FEBA DT", address="Cotonou", code="DT-FEBA", currency_code="XOF",
            timezone="Africa/Porto-Novo",
        )
        cls.fha = School.objects.create(
            name="FHA DT", address="En ligne", code="DT-FHA", entity_type="online",
            currency_code="USD", timezone="America/New_York",
        )
        cls.year, cls.student, cls.admin = {}, {}, {}
        for key, school in (("feba", cls.feba), ("fha", cls.fha)):
            cls.year[key] = SchoolYear.objects.create(
                school=school, name="2026-2027", is_current=True,
                start_date="2026-09-01", end_date="2027-07-01",
            )
            cls.student[key] = Student.objects.create(
                school=school, school_year=cls.year[key], first_name="Élève", last_name=key,
            )
            cls.admin[key] = CustomUser.objects.create_user(
                username=f"dt_admin_{key}", email=f"dt.admin.{key}@test.io",
                password="x", role="admin", school=school,
            )

    def api(self, key):
        client = APIClient()
        client.force_authenticate(self.admin[key])
        return client

    def create(self, key, now, **payload):
        body = {
            "student": self.student[key].id, "payment_type": "mensualite",
            "amount": "1000", "payment_method": "cash", **payload,
        }
        with mock.patch("django.utils.timezone.now", return_value=now):
            return self.api(key).post("/api/payments/", body, format="json")


class RecordedTimeTests(PaymentDateTimeBase):
    def test_explicit_time_feba_cotonou(self):
        resp = self.create("feba", at(2026, 10, 9, 15, 0),
                           payment_date="2026-10-09", payment_time="14:37")
        self.assertEqual(resp.status_code, 201, resp.content)
        data = resp.json()
        # 14:37 à Cotonou (UTC+1) = 13:37 UTC.
        self.assertEqual(Payment.objects.get(pk=data["id"]).paid_at, at(2026, 10, 9, 13, 37))
        self.assertEqual(data["paid_at_display"], "09/10/2026 14:37")
        self.assertEqual(data["paid_at_local"], "2026-10-09T14:37")
        self.assertTrue(data["has_time"])
        self.assertEqual(data["paid_at_source"], "recorded")
        self.assertEqual(data["academy_timezone"], "Africa/Porto-Novo")

    def test_explicit_time_fha_new_york(self):
        resp = self.create("fha", at(2026, 10, 9, 20, 0),
                           payment_date="2026-10-09", payment_time="14:37")
        self.assertEqual(resp.status_code, 201, resp.content)
        # 14:37 à New York (UTC-4 en octobre) = 18:37 UTC.
        self.assertEqual(Payment.objects.get(pk=resp.json()["id"]).paid_at, at(2026, 10, 9, 18, 37))
        self.assertEqual(resp.json()["paid_at_display"], "09/10/2026 14:37")

    def test_minutes_are_kept_distinct(self):
        now = at(2026, 10, 9, 18, 0)
        first = self.create("feba", now, payment_date="2026-10-09", payment_time="10:05").json()
        second = self.create("feba", now, payment_date="2026-10-09", payment_time="10:06").json()
        self.assertEqual(first["paid_at_display"], "09/10/2026 10:05")
        self.assertEqual(second["paid_at_display"], "09/10/2026 10:06")

    def test_same_day_without_time_uses_recording_instant(self):
        resp = self.create("feba", at(2026, 10, 9, 13, 37), payment_date="2026-10-09")
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertEqual(resp.json()["paid_at_display"], "09/10/2026 14:37")

    def test_backdated_without_time_keeps_time_unknown(self):
        resp = self.create("feba", at(2026, 10, 9, 13, 37), payment_date="2026-10-01")
        self.assertEqual(resp.status_code, 201, resp.content)
        data = resp.json()
        self.assertIsNone(data["paid_at"])
        self.assertFalse(data["has_time"])
        self.assertEqual(data["paid_at_display"], "01/10/2026")

    def test_future_time_refused(self):
        resp = self.create("feba", at(2026, 10, 9, 10, 0),
                           payment_date="2026-10-09", payment_time="18:00")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("payment_time", resp.json())

    def test_future_date_judged_in_academy_timezone(self):
        # 9 oct. 02:00 UTC = 8 oct. 22:00 à New York : le 9 est encore futur
        # pour FHA, alors qu'il est déjà « aujourd'hui » à Cotonou.
        now = at(2026, 10, 9, 2, 0)
        self.assertEqual(self.create("fha", now, payment_date="2026-10-09").status_code, 400)
        self.assertEqual(self.create("feba", now, payment_date="2026-10-09").status_code, 201)

    def test_invalid_time_format(self):
        resp = self.create("feba", at(2026, 10, 9, 15), payment_date="2026-10-09",
                           payment_time="25:61")
        self.assertEqual(resp.status_code, 400)

    def test_day_and_month_boundary_new_york(self):
        # 31 octobre 23:30 à New York = 1er novembre 03:30 UTC.
        resp = self.create("fha", at(2026, 11, 1, 4, 0),
                           payment_date="2026-10-31", payment_time="23:30")
        self.assertEqual(resp.status_code, 201, resp.content)
        payment = Payment.objects.get(pk=resp.json()["id"])
        self.assertEqual(payment.paid_at, at(2026, 11, 1, 3, 30))
        self.assertEqual(payment.payment_date, datetime.date(2026, 10, 31))
        self.assertEqual(resp.json()["paid_at_display"], "31/10/2026 23:30")

    def test_period_month_is_saved(self):
        resp = self.create("feba", at(2026, 10, 9, 15), payment_date="2026-10-09",
                           period_month="2026-11")
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertEqual(resp.json()["period_month"], "2026-11")
        self.assertEqual(Payment.objects.get(pk=resp.json()["id"]).period_month,
                         datetime.date(2026, 11, 1))


class OrderingAndFilterTests(PaymentDateTimeBase):
    def setUp(self):
        now = at(2026, 10, 9, 20, 0)
        for date, time in (("2026-10-09", "09:15"), ("2026-10-09", "16:45"),
                           ("2026-10-08", "23:59"), ("2026-09-30", "08:00")):
            self.assertEqual(self.create("feba", now, payment_date=date, payment_time=time).status_code, 201)
        # Paiement du 9 saisi le 10 sans heure : heure inconnue. Il doit
        # passer APRÈS ceux du même jour dont l'heure est connue (NULLS LAST).
        self.create("feba", at(2026, 10, 10, 9), payment_date="2026-10-09")

    def displays(self, **params):
        rows = self.api("feba").get("/api/payments/", params).json()["results"]
        return [r["paid_at_display"] for r in rows]

    def test_default_order_is_reverse_chronological(self):
        self.assertEqual(self.displays(), [
            "09/10/2026 16:45", "09/10/2026 09:15", "09/10/2026",
            "08/10/2026 23:59", "30/09/2026 08:00",
        ])

    def test_ascending_order_param(self):
        got = self.displays(ordering="paid_at")
        known = [d for d in got if len(d) > 10]
        self.assertEqual(known, sorted(known, key=lambda d: (d[6:10], d[3:5], d[0:2], d[11:])))

    def test_date_filters(self):
        got = self.displays(date_from="2026-10-01", date_to="2026-10-08")
        self.assertEqual(got, ["08/10/2026 23:59"])

    def test_invalid_date_filter(self):
        self.assertEqual(self.api("feba").get("/api/payments/", {"date_from": "hier"}).status_code, 400)


class IsolationTests(PaymentDateTimeBase):
    def test_cannot_create_payment_for_other_academy_student(self):
        resp = self.api("feba").post("/api/payments/", {
            "student": self.student["fha"].id, "payment_type": "mensualite",
            "amount": "10", "payment_method": "cash", "payment_date": "2026-10-01",
        }, format="json")
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(Payment.objects.filter(student=self.student["fha"]).exists())

    def test_cannot_attach_other_academy_year(self):
        resp = self.api("feba").post("/api/payments/", {
            "student": self.student["feba"].id, "school_year": self.year["fha"].id,
            "payment_type": "mensualite", "amount": "10", "payment_method": "cash",
            "payment_date": "2026-10-01",
        }, format="json")
        self.assertEqual(resp.status_code, 400)

    def test_lists_are_separated(self):
        self.create("feba", at(2026, 10, 9, 15), payment_date="2026-10-09")
        self.create("fha", at(2026, 10, 9, 15), payment_date="2026-10-09")
        feba_rows = self.api("feba").get("/api/payments/").json()["results"]
        self.assertEqual({r["academy_code"] for r in feba_rows}, {"DT-FEBA"})


class HistoricalBackfillTests(PaymentDateTimeBase):
    """Migration 0011 : reprise prudente, aucune heure inventée."""

    def _legacy(self, key, payment_date, created_at):
        payment = Payment.objects.create(
            student=self.student[key], school_year=self.year[key], payment_type="mensualite",
            amount=Decimal("100"), payment_method="cash", payment_date=payment_date,
        )
        Payment.objects.filter(pk=payment.pk).update(
            created_at=created_at, paid_at=None, paid_at_source="")
        return payment.pk

    def test_backfill_same_day_only(self):
        same_day = self._legacy("feba", datetime.date(2026, 9, 15), at(2026, 9, 15, 9, 12))
        backdated = self._legacy("feba", datetime.date(2026, 9, 10), at(2026, 9, 15, 9, 12))
        # FHA : saisi le 15 à 01:00 UTC = 14 à 21:00 à New York → même jour LOCAL.
        fha_same_local_day = self._legacy("fha", datetime.date(2026, 9, 14), at(2026, 9, 15, 1, 0))

        migration = importlib.import_module("apps.payments.migrations.0011_backfill_payment_paid_at")
        migration.backfill(django_apps, None)

        p = Payment.objects.get(pk=same_day)
        self.assertEqual((p.paid_at, p.paid_at_source), (at(2026, 9, 15, 9, 12), "backfill_created_at"))
        p = Payment.objects.get(pk=backdated)
        self.assertEqual((p.paid_at, p.payment_date), (None, datetime.date(2026, 9, 10)))
        p = Payment.objects.get(pk=fha_same_local_day)
        self.assertEqual(p.paid_at, at(2026, 9, 15, 1, 0))
        self.assertEqual(p.local_paid_at().strftime("%d/%m/%Y %H:%M"), "14/09/2026 21:00")

        migration.unfill(django_apps, None)
        self.assertFalse(Payment.objects.filter(paid_at_source="backfill_created_at").exists())


class CardPaymentTimeTests(PaymentDateTimeBase):
    def test_card_success_uses_academy_local_date_and_confirmation_time(self):
        from apps.payments.transaction_models import PaymentTransaction

        tx = PaymentTransaction.objects.create(
            academy=self.fha, student=self.student["fha"], school_year=self.year["fha"],
            payment_type="mensualite", amount_minor=12550,
        )
        # 10 oct. 01:15 UTC = 9 oct. 21:15 à New York.
        with mock.patch("django.utils.timezone.now", return_value=at(2026, 10, 10, 1, 15)):
            payment = tx.mark_succeeded()
        self.assertEqual(payment.payment_date, datetime.date(2026, 10, 9))
        self.assertEqual(payment.paid_at, at(2026, 10, 10, 1, 15))
        self.assertEqual(payment.paid_at_source, "card")
        self.assertEqual(payment.local_paid_at().strftime("%d/%m/%Y %H:%M"), "09/10/2026 21:15")
