"""
tests/test_payments_summary_consolidation.py — Régression P1 (juillet 2026).

BUG REPRODUIT
-------------
Sur /superadmin/payments, sélectionner « Toutes les Académies » affichait
« 2 850 601,5 » comme total encaissé : le serveur additionnait
2 850 000 FCFA (FEBA) et 601,50 $ (FEBA FHA) sans convertir, comme si
1 FCFA valait 1 $.

Ces tests verrouillent le comportement attendu :
  - une académie précise (une seule devise) : le total reste NATIF, non
    converti — comportement déjà correct, qu'il ne fallait pas casser ;
  - « Toutes les Académies » (plusieurs devises) : le total consolidé est
    exprimé dans UNE SEULE devise (XOF par défaut), avec le détail par
    devise ET le taux utilisé exposés dans la réponse ;
  - l'exemple donné dans la demande (1 000 000 FCFA + 1 000 $, taux
    1 $ = 600 FCFA -> 1 600 000 FCFA, PAS 1 001 000) est vérifié
    littéralement ;
  - paiements annulés, remboursés (soft-cancel) et en attente
    n'entachent pas le total consolidé ;
  - un taux manquant ne produit jamais un total silencieusement faux :
    l'API signale l'absence de taux au lieu de l'ignorer.
"""
import datetime
from decimal import Decimal

from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.accounts.models import CustomUser
from apps.payments.models import ExchangeRate, Payment
from apps.schools.models import School, SchoolYear
from apps.students.models import Student


def auth(client, email, password="Pass1234!"):
    resp = client.post("/api/auth/login/", {"email": email, "password": password})
    assert resp.status_code == 200, resp.data
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {resp.data.get('access', '')}")
    return client


class ConsolidatedSummaryTestBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.feba = School.objects.create(
            name="Faith & Excellence Bilingual Academy", address="Cotonou",
            entity_type="campus", code="SUM-FEBA", currency_code="XOF",
        )
        cls.fha = School.objects.create(
            name="FEBA French Heritage Academy", address="En ligne",
            entity_type="online", code="SUM-FHA", currency_code="USD",
        )
        cls.years = {}
        cls.students = {}
        for key, school in (("feba", cls.feba), ("fha", cls.fha)):
            year = cls.years[key] = SchoolYear.objects.create(
                school=school, name=f"2025-2026-{key}", is_current=True,
                start_date="2025-09-01", end_date="2026-07-01",
            )
            cls.students[key] = Student.objects.create(
                school=school, school_year=year, first_name="Élève",
                last_name=key.upper(), date_of_birth="2014-01-01",
            )

        cls.superadmin = CustomUser.objects.create_user(
            username="sum_super", email="sum.super@test.io", password="Pass1234!",
            role="superadmin", first_name="Super", last_name="Admin",
        )
        cls.feba_admin = CustomUser.objects.create_user(
            username="sum_admin_feba", email="sum.admin.feba@test.io", password="Pass1234!",
            role="admin", school=cls.feba, first_name="Admin", last_name="Feba",
        )
        cls.fha_admin = CustomUser.objects.create_user(
            username="sum_admin_fha", email="sum.admin.fha@test.io", password="Pass1234!",
            role="admin", school=cls.fha, first_name="Admin", last_name="Fha",
        )

    def _payment(self, key, amount, payment_type="mensualite", **extra):
        return Payment.objects.create(
            student=self.students[key], amount=Decimal(str(amount)),
            payment_type=payment_type, payment_method="cash",
            payment_date=datetime.date(2025, 10, 1),
            school_year=self.years[key], **extra,
        )

    def _as_superadmin_all_academies(self):
        """« Toutes les Académies » = superadmin sans école active ni ?school_id."""
        return auth(APIClient(), "sum.super@test.io")


class SingleAcademyUnaffectedTests(ConsolidatedSummaryTestBase):
    """Le correctif ne doit RIEN changer quand une seule devise est en jeu."""

    def test_feba_seule_reste_en_fcfa_sans_conversion(self):
        self._payment("feba", "1000000", payment_type="mensualite")
        client = auth(APIClient(), "sum.admin.feba@test.io")
        resp = client.get("/api/payments/summary/")
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data["reporting_currency"], "XOF")
        self.assertFalse(resp.data["is_consolidated"])
        self.assertEqual(resp.data["consolidated_total"]["formatted"], "1\u202f000\u202f000 FCFA")
        self.assertEqual(resp.data["conversions"], [])

    def test_fha_seule_reste_en_dollars_sans_conversion(self):
        self._payment("fha", "601.50", payment_type="mensualite")
        client = auth(APIClient(), "sum.admin.fha@test.io")
        resp = client.get("/api/payments/summary/")
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data["reporting_currency"], "USD")
        self.assertFalse(resp.data["is_consolidated"])
        self.assertEqual(resp.data["consolidated_total"]["formatted"], "$601.50")
        self.assertEqual(resp.data["conversions"], [])


class MultiAcademyConsolidationTests(ConsolidatedSummaryTestBase):
    """Le cas exact reproduit sur /superadmin/payments."""

    def setUp(self):
        super().setUp()
        ExchangeRate.objects.create(
            base_currency="USD", quote_currency="XOF", rate=Decimal("600"),
            effective_date=datetime.date(2025, 1, 1), source="test",
        )

    def test_exemple_litteral_de_la_demande(self):
        """
        FEBA = 1 000 000 FCFA, FEBA FHA = 1 000 USD, taux 1 USD = 600 FCFA
        -> total consolidé attendu : 1 600 000 FCFA (PAS 1 001 000).
        """
        self._payment("feba", "1000000")
        self._payment("fha", "1000.00")
        client = self._as_superadmin_all_academies()
        resp = client.get("/api/payments/summary/")
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertTrue(resp.data["is_consolidated"])
        self.assertEqual(resp.data["reporting_currency"], "XOF")
        # Le point qui compte : PAS l'addition brute 1 001 000.
        self.assertNotEqual(Decimal(resp.data["consolidated_total"]["amount"]), Decimal("1001000"))
        self.assertEqual(Decimal(resp.data["consolidated_total"]["amount"]), Decimal("1600000"))
        self.assertEqual(resp.data["consolidated_total"]["formatted"], "1\u202f600\u202f000 FCFA")

    def test_capture_ecran_reproduite_601_50_plus_2_850_000(self):
        """Le scénario visible sur la capture d'écran d'origine."""
        # FEBA : 7 mensualités à 35 000 FCFA + reste jusqu'à 2 850 000.
        self._payment("feba", "2850000", payment_type="mensualite")
        self._payment("fha", "125.50", payment_type="mensualite")
        self._payment("fha", "75.00", payment_type="inscription")
        self._payment("fha", "125.50", payment_type="mensualite")
        self._payment("fha", "75.00", payment_type="inscription")
        self._payment("fha", "125.50", payment_type="mensualite")
        self._payment("fha", "75.00", payment_type="inscription")
        # Total USD = 601.50 ; converti à 600 -> 360 900 FCFA.
        client = self._as_superadmin_all_academies()
        resp = client.get("/api/payments/summary/")
        total = Decimal(resp.data["consolidated_total"]["amount"])
        self.assertEqual(total, Decimal("2850000") + Decimal("601.50") * Decimal("600"))
        self.assertNotEqual(total, Decimal("2850601.5"))  # l'ancien bug, littéralement

    def test_detail_par_devise_est_expose(self):
        self._payment("feba", "500000")
        self._payment("fha", "1000.00")
        client = self._as_superadmin_all_academies()
        resp = client.get("/api/payments/summary/")
        by_currency = {row["currency"]: row for row in resp.data["totals_by_currency"]}
        self.assertEqual(by_currency["XOF"]["formatted"], "500\u202f000 FCFA")
        self.assertEqual(by_currency["USD"]["formatted"], "$1,000.00")

    def test_taux_utilise_est_explicite(self):
        self._payment("feba", "100000")
        self._payment("fha", "100.00")
        client = self._as_superadmin_all_academies()
        resp = client.get("/api/payments/summary/")
        self.assertEqual(len(resp.data["conversions"]), 1)
        conversion = resp.data["conversions"][0]["conversion"]
        self.assertEqual(conversion["source_currency"], "USD")
        self.assertEqual(conversion["target_currency"], "XOF")
        self.assertEqual(Decimal(conversion["rate"]), Decimal("600"))
        self.assertEqual(conversion["rate_date"], "2025-01-01")
        self.assertFalse(conversion["is_fallback"])

    def test_by_type_inscriptions_et_mensualites_consolides(self):
        self._payment("feba", "750000", payment_type="inscription")
        self._payment("fha", "75.00", payment_type="inscription")
        self._payment("feba", "2100000", payment_type="mensualite")
        self._payment("fha", "125.50", payment_type="mensualite")
        client = self._as_superadmin_all_academies()
        resp = client.get("/api/payments/summary/")
        inscriptions = Decimal(resp.data["by_type"]["inscription"]["amount"])
        mensualites = Decimal(resp.data["by_type"]["mensualite"]["amount"])
        self.assertEqual(inscriptions, Decimal("750000") + Decimal("75") * Decimal("600"))
        self.assertEqual(mensualites, Decimal("2100000") + Decimal("125.50") * Decimal("600"))


class ExcludedPaymentStatesTests(ConsolidatedSummaryTestBase):
    """Un paiement annulé ou en attente ne doit pas fausser le consolidé."""

    def setUp(self):
        super().setUp()
        ExchangeRate.objects.create(
            base_currency="USD", quote_currency="XOF", rate=Decimal("600"),
            effective_date=datetime.date(2025, 1, 1),
        )

    def test_paiement_annule_est_exclu_du_total(self):
        self._payment("feba", "1000000")
        cancelled = self._payment("fha", "5000.00")
        cancelled.is_confirmed = False
        cancelled.save(update_fields=["is_confirmed"])
        client = self._as_superadmin_all_academies()
        resp = client.get("/api/payments/summary/")
        self.assertFalse(resp.data["is_consolidated"])  # plus qu'une seule devise confirmée
        self.assertEqual(Decimal(resp.data["consolidated_total"]["amount"]), Decimal("1000000"))

    def test_paiement_supprime_est_exclu_du_total(self):
        self._payment("feba", "1000000")
        deleted = self._payment("fha", "5000.00")
        deleted.is_deleted = True
        deleted.save(update_fields=["is_deleted"])
        client = self._as_superadmin_all_academies()
        resp = client.get("/api/payments/summary/")
        self.assertEqual(Decimal(resp.data["consolidated_total"]["amount"]), Decimal("1000000"))


class MissingRateTests(ConsolidatedSummaryTestBase):
    """Un taux absent doit être signalé, jamais masqué par un total faux."""

    @override_settings(FALLBACK_EXCHANGE_RATES={})
    def test_taux_absent_sans_secours_est_signale_pas_ignore(self):
        self._payment("feba", "500000")
        self._payment("fha", "500.00")
        client = self._as_superadmin_all_academies()
        resp = client.get("/api/payments/summary/")
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertTrue(resp.data["conversion_errors"], "l'absence de taux doit être exposée")
        # Le total consolidé ne contient QUE ce qui a pu être converti :
        # la part FEBA (déjà en XOF, pas de conversion nécessaire) reste
        # dedans ; la part FHA (USD, sans taux disponible) en est exclue
        # et signalée dans `conversion_errors` — jamais une estimation
        # inventée pour la faire rentrer quand même.
        self.assertEqual(Decimal(resp.data["consolidated_total"]["amount"]), Decimal("500000"))

    def test_taux_de_secours_est_marque_explicitement(self):
        """Sans ExchangeRate en base, le réglage FALLBACK_EXCHANGE_RATES sert, et le dit."""
        self._payment("feba", "100000")
        self._payment("fha", "100.00")
        client = self._as_superadmin_all_academies()
        resp = client.get("/api/payments/summary/")
        conversion = resp.data["conversions"][0]["conversion"]
        self.assertTrue(conversion["is_fallback"])
        self.assertEqual(Decimal(conversion["rate"]), Decimal("600"))


class DecimalAmountsTests(ConsolidatedSummaryTestBase):
    """Les montants décimaux ne doivent pas dériver lors de la conversion."""

    def setUp(self):
        super().setUp()
        ExchangeRate.objects.create(
            base_currency="USD", quote_currency="XOF", rate=Decimal("615.75"),
            effective_date=datetime.date(2025, 1, 1),
        )

    def test_conversion_avec_taux_decimal_arrondit_correctement(self):
        self._payment("fha", "10.00")
        client = self._as_superadmin_all_academies()
        # Une seule devise confirmée ici (aucun paiement FEBA) : pas de
        # consolidation, on vérifie donc directement le service.
        from apps.core.currency import Money
        from apps.core.currency_conversion import CurrencyConversionService

        result = CurrencyConversionService().convert(Money.from_decimal(Decimal("10.00"), "USD"), "XOF")
        self.assertEqual(result.converted.amount, Decimal("6158"))  # 10 * 615.75 = 6157.5 -> ROUND_HALF_UP
