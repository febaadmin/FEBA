"""
Tests de l'ARCHITECTURE MULTI-DEVISES (P0).

Le défaut corrigé : un paiement n'était qu'un montant, et l'interface
ajoutait « FCFA » en dur. FEBA French Heritage Academy facture en dollars —
chacun de ses encaissements s'affichait donc dans la mauvaise monnaie. Le
nombre était juste, l'unité fausse, et rien ne le signalait.

Ces tests verrouillent quatre propriétés :

  1. la devise vient de l'ACADÉMIE, jamais du client ;
  2. les montants sont des ENTIERS en unité mineure, sans perte ;
  3. deux devises ne s'additionnent JAMAIS ;
  4. le formatage suit l'usage de chaque zone monétaire.

Le point 1 est celui qui se contourne le plus facilement : il suffirait
d'accepter un champ `currency` envoyé par un formulaire.
"""
import datetime
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import CustomUser
from apps.core.currency import (
    Money, format_totals, get_currency, totals_by_currency,
)
from apps.payments.models import Payment
from apps.schools.models import School, SchoolYear
from apps.students.models import Student


def auth(client, email, password="Pass1234!"):
    resp = client.post("/api/auth/login/", {"email": email, "password": password})
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {resp.data.get('access', '')}")
    return client


def rows(resp):
    data = resp.data
    if isinstance(data, dict) and "results" in data:
        return data["results"]
    return data


class CurrencyRegistryTests(TestCase):
    """Conversion et formatage, sans base de données."""

    def test_le_dollar_a_cent_unites_mineures(self):
        usd = get_currency("USD")
        self.assertEqual(usd.to_minor("10.00"), 1000)
        self.assertEqual(usd.to_minor("125.50"), 12550)
        self.assertEqual(usd.to_minor("1250.00"), 125000)

    def test_le_franc_cfa_n_a_pas_de_subdivision(self):
        """
        50 000 FCFA valent 50 000 unités mineures, pas 5 000 000.
        Se tromper de facteur multiplierait toutes les recettes par cent.
        """
        xof = get_currency("XOF")
        self.assertEqual(xof.to_minor("50000"), 50000)
        self.assertEqual(xof.to_decimal(50000), Decimal("50000"))

    def test_l_arrondi_suit_la_regle_comptable(self):
        """
        Python arrondit 2,5 vers le pair (donc 2). Sur une facture, un
        parent attend 2,51 → 2,51 et 0,005 → 0,01.
        """
        usd = get_currency("USD")
        self.assertEqual(usd.to_minor("0.005"), 1)
        self.assertEqual(usd.to_minor("0.015"), 2)

    def test_le_symbole_se_place_selon_l_usage_de_la_zone(self):
        self.assertEqual(get_currency("USD").format(125000), "$1,250.00")
        self.assertEqual(get_currency("XOF").format(50000), "50\u202f000 FCFA")

    def test_les_montants_negatifs_restent_lisibles(self):
        self.assertEqual(get_currency("USD").format(-12550), "-$125.50")

    def test_une_devise_inconnue_echoue_bruyamment(self):
        """
        Retomber silencieusement sur une devise par défaut afficherait un
        montant dans la mauvaise unité, ce qui ne se voit pas à l'œil.
        """
        with self.assertRaises(ValidationError):
            get_currency("EUR")

    def test_deux_devises_ne_s_additionnent_pas(self):
        with self.assertRaises(ValidationError) as ctx:
            Money(1000, "USD") + Money(50000, "XOF")
        self.assertIn("taux de conversion", str(ctx.exception))

    def test_deux_montants_de_meme_devise_s_additionnent(self):
        self.assertEqual(Money(1000, "USD") + Money(250, "USD"), Money(1250, "USD"))


class AcademyCurrencyAuthorityTests(TestCase):
    """La devise est imposée par l'académie propriétaire."""

    @classmethod
    def setUpTestData(cls):
        cls.feba = School.objects.create(
            name="FEBA Cotonou", address="Akpakpa", entity_type="campus",
            code="CUR-FEBA", currency_code="XOF",
        )
        cls.fha = School.objects.create(
            name="FEBA French Heritage Academy", address="En ligne",
            entity_type="online", code="CUR-FHA", currency_code="USD",
        )
        cls.students = {}
        cls.years = {}
        for key, school in (("feba", cls.feba), ("fha", cls.fha)):
            year = cls.years[key] = SchoolYear.objects.create(
                school=school, name=f"2025-2026-{key}", is_current=True,
                start_date="2025-09-01", end_date="2026-07-01",
            )
            cls.students[key] = Student.objects.create(
                school=school, school_year=year, first_name="Élève",
                last_name=key.upper(), date_of_birth="2014-01-01",
            )
            CustomUser.objects.create_user(
                username=f"cur_admin_{key}", email=f"cur.admin.{key}@test.io",
                password="Pass1234!", role="admin", school=school,
                first_name="Admin", last_name=key.upper(),
            )

    def _payment(self, key, amount, **extra):
        return Payment.objects.create(
            student=self.students[key], amount=Decimal(str(amount)),
            payment_type="mensualite", payment_method="cash",
            payment_date=datetime.date(2025, 10, 1),
            # L'année scolaire conditionne le filtre par défaut de la vue :
            # sans elle, le paiement existe mais n'apparaît pas dans la liste.
            school_year=self.years[key], **extra,
        )

    def test_un_paiement_fha_est_enregistre_en_dollars(self):
        payment = self._payment("fha", "125.50")
        self.assertEqual(payment.currency, "USD")
        self.assertEqual(payment.amount_minor, 12550)
        self.assertEqual(payment.formatted_amount, "$125.50")

    def test_un_paiement_feba_reste_en_francs_cfa(self):
        payment = self._payment("feba", "50000")
        self.assertEqual(payment.currency, "XOF")
        self.assertEqual(payment.amount_minor, 50000)
        self.assertEqual(payment.formatted_amount, "50\u202f000 FCFA")

    def test_une_devise_imposee_a_la_creation_est_ignoree(self):
        """
        Tentative la plus simple : forcer XOF sur un paiement FEBA FHA.
        L'académie doit l'emporter — l'utilisateur ne choisit pas la
        monnaie dans laquelle son école facture.
        """
        payment = self._payment("fha", "100.00", currency="XOF")
        self.assertEqual(payment.currency, "USD")
        self.assertEqual(payment.formatted_amount, "$100.00")

    def test_l_api_refuse_une_devise_transmise_par_le_client(self):
        client = auth(APIClient(), "cur.admin.fha@test.io")
        resp = client.post("/api/payments/", {
            "student": self.students["fha"].id,
            "amount": "80.00",
            "payment_type": "mensualite",
            "payment_method": "cash",
            "payment_date": "2025-10-01",
            "school_year": self.years["fha"].id,
            "currency": "XOF",          # falsification
            "amount_minor": 999999,     # falsification
        })
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        payment = Payment.objects.get(pk=resp.data["id"])
        self.assertEqual(payment.currency, "USD")
        self.assertEqual(payment.amount_minor, 8000)

    def test_l_api_renvoie_la_devise_et_le_montant_formate(self):
        self._payment("fha", "1250.00")
        client = auth(APIClient(), "cur.admin.fha@test.io")
        row = rows(client.get("/api/payments/"))[0]
        self.assertEqual(row["currency"], "USD")
        self.assertEqual(row["currency_symbol"], "$")
        self.assertEqual(row["amount_display"], "$1,250.00")

    def test_un_montant_negatif_est_refuse(self):
        payment = Payment(
            student=self.students["fha"], amount=Decimal("-10.00"),
            payment_type="mensualite", payment_method="cash",
            payment_date=datetime.date(2025, 10, 1),
        )
        with self.assertRaises(ValidationError):
            payment.save()

    def test_l_academie_expose_sa_devise_sans_la_dupliquer(self):
        """
        Symbole et décimales sont DÉRIVÉS du code : ils ne peuvent pas
        contredire la devise, contrairement à des colonnes séparées.
        """
        self.assertEqual(self.fha.currency_code, "USD")
        self.assertEqual(self.fha.currency_symbol, "$")
        self.assertEqual(self.fha.currency_decimal_places, 2)
        self.assertEqual(self.feba.currency_symbol, "FCFA")
        self.assertEqual(self.feba.currency_decimal_places, 0)


class ConsolidatedTotalsTests(TestCase):
    """Le mode « Toutes les Académies » ne mélange jamais les devises."""

    @classmethod
    def setUpTestData(cls):
        cls.feba = School.objects.create(
            name="FEBA", address="Akpakpa", entity_type="campus",
            code="TOT-FEBA", currency_code="XOF",
        )
        cls.fha = School.objects.create(
            name="FHA", address="En ligne", entity_type="online",
            code="TOT-FHA", currency_code="USD",
        )
        for key, school, amount in (("feba", cls.feba, "500000"), ("fha", cls.fha, "1250.00")):
            year = SchoolYear.objects.create(
                school=school, name=f"2025-2026-{key}", is_current=True,
                start_date="2025-09-01", end_date="2026-07-01",
            )
            student = Student.objects.create(
                school=school, school_year=year, first_name="E", last_name=key,
                date_of_birth="2014-01-01",
            )
            Payment.objects.create(
                student=student, amount=Decimal(amount), payment_type="mensualite",
                payment_method="cash", payment_date=datetime.date(2025, 10, 1),
            )

    def test_les_totaux_sont_ventiles_par_devise(self):
        totals = totals_by_currency(Payment.objects.all())
        self.assertEqual(set(totals), {"XOF", "USD"})
        self.assertEqual(totals["XOF"].amount_minor, 500000)
        self.assertEqual(totals["USD"].amount_minor, 125000)

    def test_le_rendu_consolide_affiche_deux_lignes_distinctes(self):
        """
        Un total unique serait plus commode et complètement faux :
        500 000 FCFA et 1 250 $ n'ont pas de somme.
        """
        rendered = format_totals(totals_by_currency(Payment.objects.all()))
        self.assertEqual(rendered, ["$1,250.00", "500\u202f000 FCFA"])


class DashboardCurrencyTests(TestCase):
    """
    Le tableau de bord annonce sa devise.

    Le défaut corrigé : les KPI de recettes sortaient en `float` nu. Le
    navigateur y ajoutait un symbole choisi côté client — et affichait
    donc « FCFA » sur les recettes de FEBA French Heritage Academy.
    """

    @classmethod
    def setUpTestData(cls):
        cls.fha = School.objects.create(
            name="FHA tableau de bord", address="En ligne", entity_type="online",
            code="DASH-FHA", currency_code="USD",
        )
        cls.year = SchoolYear.objects.create(
            school=cls.fha, name="2025-2026-dash", is_current=True,
            start_date="2025-09-01", end_date="2026-07-01",
        )
        cls.student = Student.objects.create(
            school=cls.fha, school_year=cls.year, first_name="Élève",
            last_name="Dash", date_of_birth="2014-01-01",
        )
        CustomUser.objects.create_user(
            username="dash_admin", email="dash.admin@test.io", password="Pass1234!",
            role="admin", school=cls.fha, first_name="Admin", last_name="Dash",
        )
        Payment.objects.create(
            student=cls.student, school_year=cls.year, amount=Decimal("125.50"),
            payment_type="mensualite", payment_method="card",
            payment_date=datetime.date.today(),
        )

    def test_le_tableau_de_bord_expose_la_devise_de_l_academie(self):
        client = auth(APIClient(), "dash.admin@test.io")
        data = client.get("/api/dashboard/admin/").data

        self.assertEqual(data["currency"], "USD")
        self.assertEqual(data["currency_symbol"], "$")

    def test_les_recettes_sont_rendues_par_le_serveur(self):
        client = auth(APIClient(), "dash.admin@test.io")
        kpis = client.get("/api/dashboard/admin/").data["kpis"]

        self.assertEqual(kpis["total_revenue_ytd_display"], "$125.50")
        self.assertEqual(kpis["total_revenue_ytd_minor"], 12550)

    def test_chaque_paiement_recent_porte_sa_devise(self):
        client = auth(APIClient(), "dash.admin@test.io")
        row = client.get("/api/dashboard/admin/").data["recent_payments"][0]

        self.assertEqual(row["currency"], "USD")
        self.assertEqual(row["amount_display"], "$125.50")
        self.assertEqual(row["amount_minor"], 12550)


class ReceiptGlyphTests(TestCase):
    """
    Le reçu doit être LISIBLE, pas seulement juste.

    Le défaut corrigé : le séparateur de milliers français est l'espace
    fine insécable U+202F. Helvetica — la police des reçus — ne la connaît
    pas. ReportLab ne signale rien et dessine un rectangle plein : le reçu
    partait à l'impression avec « 35■000 FCFA ».
    """

    def test_les_caracteres_absents_de_la_police_sont_remplaces(self):
        from apps.payments.pdf_generator import _pdf_safe

        self.assertEqual(_pdf_safe("35 000 FCFA"), "35 000 FCFA")
        self.assertNotIn(" ", _pdf_safe("1 250 000"))

    def test_la_propriete_insecable_est_conservee(self):
        """
        Le remplacement ne retombe pas sur une espace ordinaire : le
        nombre se couperait en fin de ligne, « 35 » d'un côté et
        « 000 FCFA » de l'autre.
        """
        from apps.payments.pdf_generator import _pdf_safe

        self.assertIn(" ", _pdf_safe("35 000"))
        self.assertNotIn("35 000", _pdf_safe("35 000"))

    def test_le_formateur_produit_bien_l_espace_fine(self):
        """
        La substitution vaut pour le PDF seulement. À l'écran, l'espace
        fine reste la bonne typographie — la corriger à la source
        dégraderait tout le reste de l'application.
        """
        self.assertIn(" ", get_currency("XOF").format(35000))
