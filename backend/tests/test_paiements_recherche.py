"""
Phase 7 — page « Paiements » (recherche, filtres, tri, totaux, export) et
graphique du tableau de bord (nouvelles périodes, granularités, répartitions).

Chaque total est comparé à une requête indépendante, et un test compare le
graphique du tableau de bord à la page Paiements pour les mêmes filtres :
un même paiement ne doit jamais être compté différemment selon l'écran.
"""
import io
from datetime import datetime, timezone as dt_tz
from decimal import Decimal

from django.db.models import Sum
from openpyxl import load_workbook
from rest_framework.test import APIClient

from apps.payments.models import Payment
from apps.payments.tableau_bord import (
    Filtres, PeriodeInvalide, bornes, calculer, choisir_granularite, detail, granularites_possibles,
)
from apps.payments.transaction_models import PaymentTransaction
from tests.test_audit_p1_payment_reminders import D, ReminderBase

AUJ = D(2026, 10, 14)   # un mercredi


class PeriodesEtGranularitesTests(ReminderBase):
    def test_nouvelles_periodes(self):
        b = lambda p: bornes(p, AUJ, [self.feba])
        self.assertEqual(b("jour"), (AUJ, AUJ))
        self.assertEqual(b("hier"), (D(2026, 10, 13), D(2026, 10, 13)))
        self.assertEqual(b("semaine"), (D(2026, 10, 12), D(2026, 10, 18)))          # lundi → dimanche
        self.assertEqual(b("semaine_prec"), (D(2026, 10, 5), D(2026, 10, 11)))
        self.assertEqual(b("mois"), (D(2026, 10, 1), D(2026, 10, 31)))
        self.assertEqual(b("mois_prec"), (D(2026, 9, 1), D(2026, 9, 30)))
        self.assertEqual(bornes("mois_prec", D(2027, 1, 5), [self.feba]), (D(2026, 12, 1), D(2026, 12, 31)))

    def test_granularite_adaptee_jamais_artificielle(self):
        self.assertEqual(choisir_granularite(AUJ, AUJ), "heure")
        self.assertEqual(choisir_granularite(D(2026, 10, 12), D(2026, 10, 18)), "jour")
        self.assertEqual(choisir_granularite(D(2026, 8, 1), D(2026, 10, 14)), "semaine")
        self.assertEqual(choisir_granularite(D(2025, 11, 1), D(2026, 10, 14)), "mois")
        self.assertEqual(granularites_possibles(AUJ, AUJ), ["heure", "jour"])
        self.assertNotIn("heure", granularites_possibles(D(2026, 10, 12), D(2026, 10, 18)))
        with self.assertRaises(PeriodeInvalide):
            choisir_granularite(D(2026, 10, 12), D(2026, 10, 18), "heure")         # une semaine heure par heure
        with self.assertRaises(PeriodeInvalide):
            choisir_granularite(D(2026, 10, 12), D(2026, 10, 18), "mois")
        with self.assertRaises(PeriodeInvalide):
            choisir_granularite(AUJ, AUJ, "siecle")


class GraphiqueGranulariteTests(ReminderBase):
    def setUp(self):
        # 14/10 : 10 000 à 9 h (heure locale Cotonou = UTC+1), 20 000 à 15 h, 5 000 sans heure.
        self.pay(self.alice, "10000", payment_date=AUJ, paid_at=datetime(2026, 10, 14, 8, 30, tzinfo=dt_tz.utc))
        self.pay(self.bob, "20000", ptype="cantine", payment_date=AUJ,
                 paid_at=datetime(2026, 10, 14, 14, 5, tzinfo=dt_tz.utc))
        Payment.objects.filter(pk=self.pay(self.bob, "5000", payment_date=AUJ).pk).update(payment_method="mtn_momo")
        self.pay(self.alice, "70000", payment_date=D(2026, 10, 2))
        self.pay(self.alice, "3000", payment_date=D(2026, 10, 13), is_confirmed=False)

    def test_journee_heure_par_heure(self):
        r = calculer([self.feba], "jour", aujourd_hui=AUJ)
        self.assertEqual(r["periode"]["granularite"], "heure")
        xof = r["devises"][0]
        par_heure = {c["date"]: c["encaisse_minor"] for c in xof["serie"]}
        self.assertEqual(len(par_heure), 24)
        self.feba.refresh_from_db()
        decalage = 1 if self.feba.timezone in ("Africa/Porto-Novo", "Africa/Lagos") else None
        if decalage:
            self.assertEqual((par_heure[9], par_heure[15]), (10000, 20000))
        self.assertEqual(sum(par_heure.values()), 30000)
        ind = xof["indicateurs"]
        # Tout est compté dans les indicateurs ; le paiement sans heure est signalé, pas perdu.
        self.assertEqual((ind["encaisse_minor"], ind["nb_paiements"], ind["nb_sans_heure"]), (35000, 3, 1))
        self.assertEqual(ind["moyenne_minor"], round(35000 / 3))
        self.assertEqual(ind["nb_eleves_payeurs"], 2)
        self.assertIsNone(xof["serie"][0]["attendu_minor"])                 # pas d'échéance à l'heure

    def test_repartitions_par_nature_et_mode(self):
        xof = calculer([self.feba], "mois", aujourd_hui=AUJ)["devises"][0]
        natures = {n["code"]: (n["montant_minor"], n["nb"]) for n in xof["par_nature"]}
        self.assertEqual(natures, {"mensualite": (85000, 3), "cantine": (20000, 1)})
        modes = {m["code"]: m["montant_minor"] for m in xof["par_mode"]}
        self.assertEqual(modes, {"cash": 100000, "mtn_momo": 5000})
        self.assertEqual(sum(modes.values()), xof["indicateurs"]["encaisse_minor"])

    def test_semaine_jour_par_jour_et_detail_d_une_case(self):
        r = calculer([self.feba], "perso", D(2026, 9, 1), D(2026, 10, 31), aujourd_hui=AUJ, granularite="semaine")
        semaines = {c["date"]: c["encaisse_minor"] for c in r["devises"][0]["serie"]}
        self.assertEqual(semaines["2026-09-28"], 70000)      # le 02/10 tombe dans la semaine du lundi 28/09
        self.assertEqual(semaines["2026-10-12"], 35000)
        d = detail([self.feba], "perso", D(2026, 9, 1), D(2026, 10, 31), aujourd_hui=AUJ,
                   granularite="semaine", case=D(2026, 9, 28))
        self.assertEqual((d["du"], d["au"], d["total"]), ("2026-09-28", "2026-10-04", 1))

    def test_comparaison_mois_precedent(self):
        r = calculer([self.feba], "mois", aujourd_hui=AUJ, comparer=True)
        self.assertEqual(r["periode_precedente"], {"du": "2026-09-01", "au": "2026-09-30"})

    def test_options_natures_et_modes_reels(self):
        from apps.payments.tableau_bord import natures_et_modes
        o = natures_et_modes([self.feba])
        self.assertEqual({m["id"] for m in o["modes"]}, {"cash", "mtn_momo"})   # pas de mode jamais utilisé
        natures = {n["id"]: n["nb"] for n in o["natures"]}
        self.assertEqual(natures["cantine"], 1)
        self.assertIn("mensualite", natures)
        self.assertNotIn("transport", natures)                                  # ni payé, ni tarifé

    def test_api_granularite_invalide(self):
        sa = self.user("pr_sa", "superadmin", None)
        c = APIClient()
        c.force_authenticate(sa)
        c.post("/api/auth/entity-context/switch/", {"entity_id": self.feba.id})
        r = c.get("/api/payments/tableau-de-bord/", {"periode": "semaine", "granularite": "heure"})
        self.assertEqual(r.status_code, 400)
        self.assertIn("Granularité", r.data["detail"])


class PagePaiementsTests(ReminderBase):
    def setUp(self):
        self.alice.matricule = "MAT-ALI-01"
        self.alice.last_name = "Ébène"
        self.alice.save()
        self.p1 = self.pay(self.alice, "150000", payment_date=D(2026, 9, 20))
        self.p2 = self.pay(self.bob, "60000", ptype="cantine", payment_date=D(2026, 10, 5))
        Payment.objects.filter(pk=self.p2.pk).update(payment_method="mtn_momo")
        self.p3 = self.pay(self.bob, "40000", payment_date=D(2026, 10, 7), is_confirmed=False)
        self.p4 = self.pay(self.bob, "25000", payment_date=D(2026, 10, 14))
        self.c = APIClient()
        self.c.force_authenticate(self.admin)

    def get(self, client=None, **params):
        params.setdefault("all_years", 1)
        r = (client or self.c).get("/api/payments/", params)
        self.assertEqual(r.status_code, 200, getattr(r, "data", r))
        return r.data

    def ids(self, **params):
        return {p["id"] for p in self.get(**params)["results"]}

    def test_recherche_sans_accents_ni_casse(self):
        self.assertEqual(self.ids(q="ebene"), {self.p1.pk})
        self.assertEqual(self.ids(q="ÉBÈNE alice"), {self.p1.pk})
        self.assertEqual(self.ids(q="mat-ali"), {self.p1.pk})
        self.assertEqual(self.ids(q=self.p2.reference_number.lower()), {self.p2.pk})

    def test_recherche_montant_date_classe_type_mode_statut(self):
        self.assertEqual(self.ids(q="60000"), {self.p2.pk})
        self.assertEqual(self.ids(q="20/09/2026"), {self.p1.pk})
        self.assertEqual(self.ids(q="05/10"), {self.p2.pk})
        self.assertEqual(self.ids(q="cm1-a"), {self.p2.pk, self.p3.pk, self.p4.pk})
        self.assertEqual(self.ids(q="cantine"), {self.p2.pk})
        self.assertEqual(self.ids(q="mtn"), {self.p2.pk})
        self.assertEqual(self.ids(q="annule"), {self.p3.pk})
        self.assertEqual(self.ids(q="bob cantine"), {self.p2.pk})             # tous les mots doivent correspondre
        self.assertEqual(self.ids(q="zzz"), set())

    def test_filtres_combinables(self):
        self.assertEqual(self.ids(nature="cantine,mensualite", mode="cash"), {self.p1.pk, self.p3.pk, self.p4.pk})
        self.assertEqual(self.ids(statut="annule"), {self.p3.pk})
        self.assertEqual(self.ids(montant_min="30000", montant_max="100000"), {self.p2.pk, self.p3.pk})
        self.assertEqual(self.ids(montant="25000"), {self.p4.pk})
        self.assertEqual(self.ids(classe=self.class_ce.pk), {self.p1.pk})
        self.assertEqual(self.ids(periode="perso", du="2026-10-01", au="2026-10-10"), {self.p2.pk, self.p3.pk})
        self.assertEqual(self.ids(periode="perso", du="2026-10-01", au="2026-10-31", statut="confirme",
                                  nature="mensualite"), {self.p4.pk})

    def test_parametre_invalide_400(self):
        for params in ({"nature": "inconnue"}, {"montant": "abc"}, {"periode": "siecle"}, {"tri": "couleur"},
                       {"periode": "perso", "du": "2026-10-10", "au": "2026-10-01"}):
            r = self.c.get("/api/payments/", {**params, "all_years": 1})
            self.assertEqual(r.status_code, 400, params)

    def test_tri_stable_et_pagination(self):
        montants = [p["amount"] for p in self.get(tri="-montant")["results"]]
        self.assertEqual([Decimal(m) for m in montants], sorted((Decimal(m) for m in montants), reverse=True))
        eleves = [p["student"] for p in self.get(tri="eleve")["results"]]
        self.assertEqual(eleves, [self.alice.pk] + [self.bob.pk] * 3)            # « Ébène » avant « Élève »
        p1 = self.get(tri="date", page_size=2, page=1)
        p2 = self.get(tri="date", page_size=2, page=2)
        self.assertEqual(p1["count"], 4)
        vus = [x["id"] for x in p1["results"] + p2["results"]]
        self.assertEqual(sorted(vus), sorted({self.p1.pk, self.p2.pk, self.p3.pk, self.p4.pk}))

    def test_totaux_de_toute_la_selection(self):
        r = self.get(page_size=1)
        self.assertEqual(len(r["results"]), 1)
        tot = r["totaux"][0]
        self.assertEqual(tot["devise"], "XOF")
        self.assertEqual((tot["confirme_minor"], tot["nb_confirmes"], tot["annule_minor"], tot["nb_annules"]),
                         (235000, 3, 40000, 1))
        self.assertEqual(tot["net_minor"], Payment.objects.filter(student__school=self.feba, is_confirmed=True)
                         .aggregate(t=Sum("amount_minor"))["t"])

    def test_remboursement_compte_une_fois(self):
        PaymentTransaction.objects.create(academy=self.feba, student=self.bob, amount_minor=25000, currency="XOF",
                                          status=PaymentTransaction.PARTIALLY_REFUNDED, payment=self.p4,
                                          amount_refunded_minor=5000, idempotency_key="k-remb")
        tot = self.get()["totaux"][0]
        self.assertEqual((tot["rembourse_minor"], tot["net_minor"]), (5000, 230000))
        self.assertEqual(self.ids(statut="rembourse"), {self.p4.pk})
        xof = calculer([self.feba], "perso", D(2026, 9, 1), D(2026, 10, 31), aujourd_hui=AUJ)["devises"][0]
        self.assertEqual(xof["indicateurs"]["encaisse_minor"], 230000)

    def test_coherence_tableau_de_bord_et_page_paiements(self):
        """Mêmes filtres → mêmes montants, mêmes paiements, sur les deux écrans."""
        cas = [
            ({}, Filtres()),
            ({"nature": "cantine"}, Filtres(natures=("cantine",))),
            ({"mode": "cash"}, Filtres(modes=("cash",))),
            ({"classe": self.class_cm.pk}, Filtres(classe=self.class_cm.pk)),
            ({"montant_min": "50000"}, Filtres(montant_min=Decimal("50000"))),
        ]
        for params, filtres in cas:
            page = self.get(periode="perso", du="2026-09-01", au="2026-10-31", **params)
            graph = calculer([self.feba], "perso", D(2026, 9, 1), D(2026, 10, 31), aujourd_hui=AUJ,
                             filtres=filtres)["devises"][0]["indicateurs"]
            net = sum(t["net_minor"] for t in page["totaux"])
            nb = sum(t["nb_confirmes"] for t in page["totaux"])
            self.assertEqual((net, nb), (graph["encaisse_minor"], graph["nb_paiements"]), params)
            ann = sum(t["annule_minor"] for t in page["totaux"])
            self.assertEqual(ann, graph["annule_minor"], params)

    def test_export_excel_respecte_les_filtres(self):
        r = self.c.get("/api/payments/", {"all_years": 1, "nature": "mensualite", "export": "xlsx", "tri": "montant"})
        self.assertEqual(r.status_code, 200, r.content[:3000])
        self.assertIn("spreadsheetml", r["Content-Type"])
        ws = load_workbook(io.BytesIO(r.content)).active
        lignes = list(ws.iter_rows(min_row=2, values_only=True))
        self.assertEqual(len(lignes), 3)
        self.assertEqual([l[10] for l in lignes], [25000, 40000, 150000])
        self.assertEqual({l[12] for l in lignes}, {"XOF"})

    def test_isolation_academie_et_parent(self):
        fha_student = self.student("Zoé", None, school=self.fha, year=self.fha_year)
        self.pay(fha_student, "100", payment_date=D(2026, 10, 1))
        self.assertNotIn("Zoé", str(self.get()))                                 # admin FEBA : rien de FHA
        r = self.c.get("/api/payments/", {"all_years": 1, "export": "xlsx"})
        self.assertNotIn(b"Zo\xc3\xa9", r.content)
        # Parent : uniquement ses enfants, même avec une recherche ou un filtre élève étranger.
        autre = self.student("Carla", self.class_ce)
        self.pay(autre, "9000", payment_date=D(2026, 10, 1))
        pc = APIClient()
        pc.force_authenticate(self.parent2_user)
        self.assertEqual(self.get(client=pc, q="carla")["count"], 0)
        self.assertEqual(self.get(client=pc, eleve=autre.pk)["count"], 0)
        pc.force_authenticate(self.parent_user)
        self.assertEqual(self.get(client=pc, q="carla")["count"], 0)
        self.assertEqual(self.get(client=pc)["count"], 4)
