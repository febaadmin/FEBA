"""
Graphique des paiements du tableau de bord super administrateur.

Chaque total est comparé à une requête indépendante sur la base de test.
Cas couverts : paiements confirmés, annulés, supprimés, hors période ; deux
devises jamais additionnées ; transaction carte réussie (pas de double
comptage avec son paiement) puis remboursée en partie ; transactions en
attente et échouées ; échéancier (attendu, restant, taux) et absence
d'échéancier (None, jamais 0) ; filtre par académie ; périodes ; droits.
"""
from datetime import date

from django.db.models import Sum
from rest_framework.test import APIClient

from apps.payments.models import Payment
from apps.payments.tableau_bord import calculer, PeriodeInvalide
from apps.payments.transaction_models import PaymentTransaction
from tests.test_audit_p1_payment_reminders import D, ReminderBase

AUJ = D(2026, 12, 15)


class TableauBordPaiementsTests(ReminderBase):
    def setUp(self):
        self.cyril = self.student("Cyril", None, school=self.fha, year=self.fha_year)
        # FEBA (XOF) : Alice a payé la 1re tranche (150 000) le 20/09.
        self.p1 = self.pay(self.alice, "150000", payment_date=D(2026, 9, 20))
        self.pay(self.bob, "60000", payment_date=D(2026, 10, 5))
        self.pay(self.bob, "0", payment_date=D(2026, 10, 6))                              # montant nul
        self.pay(self.bob, "40000", payment_date=D(2026, 10, 7), is_confirmed=False)      # annulé
        self.pay(self.bob, "99000", payment_date=D(2026, 10, 8), is_deleted=True)         # supprimé
        self.pay(self.alice, "7000", payment_date=D(2025, 9, 1))                          # hors période
        # FHA (USD) : paiement carte réussi (crée son Payment), puis remboursé de 20,00.
        tx = PaymentTransaction.objects.create(academy=self.fha, student=self.cyril, school_year=self.fha_year,
                                               payment_type="mensualite", amount_minor=12550, provider="stripe",
                                               provider_session_id="cs_tb", status=PaymentTransaction.PENDING)
        self.carte = tx.mark_succeeded()
        Payment.objects.filter(pk=self.carte.pk).update(payment_date=D(2026, 11, 3))
        tx.refresh_from_db()
        tx.register_refund(2000)
        PaymentTransaction.objects.create(academy=self.fha, student=self.cyril, payment_type="mensualite",
                                          amount_minor=5000, status=PaymentTransaction.PENDING)
        PaymentTransaction.objects.create(academy=self.fha, student=self.cyril, payment_type="mensualite",
                                          amount_minor=3000, status=PaymentTransaction.FAILED)

    def calc(self, academies=None, periode="12m", **kw):
        return calculer(academies or [self.feba, self.fha], periode, aujourd_hui=AUJ, **kw)

    def devise(self, r, code):
        return next(d for d in r["devises"] if d["devise"] == code)

    def test_totaux_par_devise_jamais_melangees(self):
        r = self.calc()
        self.assertEqual(sorted(d["devise"] for d in r["devises"]), ["USD", "XOF"])
        xof = self.devise(r, "XOF")["indicateurs"]
        attendu = Payment.objects.filter(student__school=self.feba, is_confirmed=True, is_deleted=False,
                                         payment_date__gte=D(2026, 1, 1), payment_date__lte=AUJ
                                         ).aggregate(t=Sum("amount_minor"))["t"]
        self.assertEqual(xof["encaisse_minor"], attendu)
        self.assertEqual(xof["encaisse_minor"], 210000)
        self.assertEqual(xof["nb_paiements"], 3)            # dont le paiement nul
        self.assertEqual((xof["annule_minor"], xof["nb_annules"]), (40000, 1))

    def test_carte_sans_double_comptage_et_remboursement_deduit(self):
        usd = self.devise(self.calc(), "USD")["indicateurs"]
        self.assertEqual(Payment.objects.filter(student=self.cyril).count(), 1)
        self.assertEqual(usd["encaisse_minor"], 12550 - 2000)
        self.assertEqual(usd["rembourse_minor"], 2000)
        self.assertEqual((usd["en_attente_minor"], usd["nb_en_attente"]), (5000, 1))
        self.assertEqual((usd["echoue_minor"], usd["nb_echoues"]), (3000, 1))

    def test_echeancier_attendu_restant_taux(self):
        xof = self.devise(self.calc(), "XOF")
        i = xof["indicateurs"]
        self.assertTrue(xof["echeancier_configure"])
        # Échéances dans la période (12 mois jusqu'au 15/12/2026) : 30/09 et 30/11 pour Alice et Bob.
        self.assertEqual(i["attendu_minor"], 150000 + 100000 + 150000 + 110000)
        # Échues au 15/12 : les mêmes. Payé imputé : Alice 150 000 + 7 000 (même année
        # scolaire, daté hors période : l'imputation suit l'année, pas la date), Bob 60 000.
        self.assertEqual(i["restant_minor"], 510000 - 217000)
        self.assertEqual(i["taux_recouvrement"], round(100 * 217000 / 510000, 1))

    def test_sans_echeancier_valeurs_non_calculables(self):
        usd = self.devise(self.calc(), "USD")
        self.assertFalse(usd["echeancier_configure"])
        self.assertIsNone(usd["indicateurs"]["attendu_minor"])
        self.assertIsNone(usd["indicateurs"]["restant_minor"])
        self.assertIsNone(usd["indicateurs"]["taux_recouvrement"])

    def test_filtre_academie(self):
        r = self.calc([self.feba])
        self.assertEqual([d["devise"] for d in r["devises"]], ["XOF"])
        self.assertEqual([a["nom"] for a in r["par_academie"]], [self.feba.name])

    def test_serie_mensuelle_somme_egale_total(self):
        xof = self.devise(self.calc(), "XOF")
        self.assertEqual(len(xof["serie"]), 12)
        self.assertEqual(sum(c["encaisse_minor"] for c in xof["serie"]), xof["indicateurs"]["encaisse_minor"])
        septembre = next(c for c in xof["serie"] if c["date"] == "2026-09-01")
        self.assertEqual(septembre["encaisse_minor"], 150000)
        self.assertEqual(septembre["attendu_minor"], 300000)

    def test_periodes(self):
        self.assertEqual(self.calc(periode="7j")["periode"]["du"], "2026-12-09")
        r30 = self.calc(periode="30j")
        self.assertEqual((r30["periode"]["granularite"], len(self.devise(r30, "XOF")["serie"])), ("jour", 30))
        self.assertEqual(self.calc(periode="3m")["periode"]["du"], "2026-10-01")
        annee = self.calc(periode="annee")["periode"]
        self.assertEqual((annee["du"], annee["au"]), ("2026-09-01", "2027-06-30"))
        perso = self.calc(periode="perso", du=D(2026, 10, 1), au=D(2026, 10, 31))
        self.assertEqual(self.devise(perso, "XOF")["indicateurs"]["encaisse_minor"], 60000)
        for mauvais in ({"periode": "perso"}, {"periode": "perso", "du": D(2026, 2, 1), "au": D(2026, 1, 1)},
                        {"periode": "xx"}):
            with self.assertRaises(PeriodeInvalide):
                self.calc(**mauvais)

    def test_droits_et_selecteur(self):
        url = "/api/payments/tableau-de-bord/?periode=perso&du=2026-01-01&au=2026-12-31"
        admin = APIClient()
        admin.force_authenticate(self.admin)
        self.assertEqual(admin.get(url).status_code, 403)
        self.assertEqual(APIClient().get(url).status_code, 401)
        sa = self.user("tb_sa", "superadmin", None)
        client = APIClient()
        client.force_authenticate(sa)
        r = client.get(url)
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(sorted(d["devise"] for d in r.data["devises"]), ["USD", "XOF"])
        client.post("/api/auth/entity-context/switch/", {"entity_id": self.fha.id})
        r = client.get(url)
        self.assertEqual([d["devise"] for d in r.data["devises"]], ["USD"])
        self.assertEqual(client.get(url.replace("2026-01-01", "pas-une-date")).status_code, 400)


class EcheancierHorsPeriodeTests(ReminderBase):
    """Une académie avec des tarifs mais sans échéance dans la période : attendu 0, pas « non calculable »."""

    def test_attendu_zero_si_aucune_echeance_dans_la_periode(self):
        r = calculer([self.feba], "7j", aujourd_hui=D(2026, 10, 15))   # tranches au 30/09 et 30/11
        xof = r["devises"][0]
        self.assertTrue(xof["echeancier_configure"])
        self.assertEqual(xof["indicateurs"]["attendu_minor"], 0)
        self.assertEqual(r["par_academie"][0]["attendu_minor"], 0)
        self.assertIsNone(calculer([self.fha], "7j", aujourd_hui=D(2026, 10, 15))["devises"][0]["indicateurs"]["attendu_minor"])


class ExonerationGraphiqueTests(ReminderBase):
    def test_exoneration_hors_attendu(self):
        from apps.payments.models import StudentFeeArrangement
        avant = calculer([self.feba], "12m", aujourd_hui=D(2026, 12, 15))["devises"][0]["indicateurs"]["attendu_minor"]
        StudentFeeArrangement.objects.create(student=self.alice, fee_schedule=self.tuition_ce, kind="exemption", reason="Bourse totale")
        apres = calculer([self.feba], "12m", aujourd_hui=D(2026, 12, 15))["devises"][0]["indicateurs"]
        self.assertEqual(avant - apres["attendu_minor"], 150000 + 100000)   # tranches d'Alice dans la période
        self.assertEqual(apres["restant_minor"], 150000 + 110000)           # Bob seul, rien payé
