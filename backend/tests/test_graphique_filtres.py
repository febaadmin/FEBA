"""
Graphique des paiements : filtres, comparaison, détail d'une barre, export (phase 5, lot F3).

Chaque total filtré est comparé à une requête indépendante ou à une valeur
calculée à la main à partir des données de test.
"""
import csv
import io

from django.db.models import Sum
from rest_framework.test import APIClient

from apps.payments.models import Payment
from apps.payments.tableau_bord import FiltreInvalide, Filtres, calculer, detail, lire_filtres
from tests.test_audit_p1_payment_reminders import D, ReminderBase

AUJ = D(2026, 12, 15)


class GraphiqueFiltresTests(ReminderBase):
    def setUp(self):
        # Alice (CE1) : 150 000 le 20/09 ; 7 000 hors période (même année scolaire).
        # Bob (CM1) : 60 000 le 05/10 (mobile money), 0, 40 000 annulé, 99 000 supprimé.
        self.pay(self.alice, "150000", payment_date=D(2026, 9, 20))
        self.pay(self.alice, "7000", payment_date=D(2025, 9, 1))
        Payment.objects.filter(pk=self.pay(self.bob, "60000", payment_date=D(2026, 10, 5)).pk).update(payment_method="mtn_momo")
        self.pay(self.bob, "0", payment_date=D(2026, 10, 6))
        self.pay(self.bob, "40000", payment_date=D(2026, 10, 7), is_confirmed=False)
        self.pay(self.bob, "99000", payment_date=D(2026, 10, 8), is_deleted=True)
        self.sa = self.user("gf_sa", "superadmin", None)

    def ind(self, periode="12m", **filtres):
        r = calculer([self.feba], periode, aujourd_hui=AUJ, filtres=Filtres(**filtres))
        return r["devises"][0]["indicateurs"]

    def encaisse_sql(self, **filtre):
        return Payment.objects.filter(student__school=self.feba, is_confirmed=True, is_deleted=False,
                                      payment_date__gte=D(2026, 1, 1), payment_date__lte=AUJ, **filtre
                                      ).aggregate(t=Sum("amount_minor"))["t"] or 0

    def test_filtres_de_structure(self):
        ce = self.ind(classe=self.class_ce.pk)
        self.assertEqual(ce["encaisse_minor"], self.encaisse_sql(student__current_class=self.class_ce))
        self.assertEqual(ce["encaisse_minor"], 150000)
        # Échéances d'Alice dans la période : 150 000 + 100 000 ; imputé 157 000.
        self.assertEqual((ce["attendu_minor"], ce["restant_minor"]), (250000, 93000))
        cm = self.ind(niveau=self.cm.pk)
        self.assertEqual((cm["encaisse_minor"], cm["nb_paiements"], cm["annule_minor"]), (60000, 2, 40000))
        self.assertEqual(self.ind(eleve=self.alice.pk)["encaisse_minor"], 150000)
        self.cm.cycle = "college"
        self.cm.save()
        self.assertEqual(self.ind(cycle="college")["encaisse_minor"], 60000)
        self.assertEqual(self.ind(cycle="lycee")["encaisse_minor"], 0)
        self.assertEqual(self.ind(annee=self.year.pk)["encaisse_minor"], 210000)

    def test_filtres_financiers(self):
        self.assertEqual(self.ind(natures=("cantine",))["encaisse_minor"], 0)
        self.assertEqual(self.ind(natures=("cantine",))["attendu_minor"], 0)       # aucun tarif cantine
        self.assertEqual(self.ind(modes=("mtn_momo",))["encaisse_minor"], self.encaisse_sql(payment_method="mtn_momo"))
        self.assertEqual(self.ind(modes=("cash",))["encaisse_minor"], 150000)
        annules = self.ind(statut="annule")
        self.assertEqual((annules["encaisse_minor"], annules["annule_minor"]), (0, 40000))
        self.assertEqual(self.ind(statut="confirme")["annule_minor"], 0)
        self.assertEqual(self.ind(statut="rembourse")["encaisse_minor"], 0)        # aucun remboursement FEBA
        bande = self.ind(montant_min=50000)
        self.assertEqual((bande["encaisse_minor"], bande["nb_paiements"], bande["annule_minor"]), (210000, 2, 0))
        self.assertEqual(self.ind(montant_max=50000)["nb_paiements"], 1)          # le paiement nul

    def test_statut_echeance_et_solde(self):
        # Au 15/12 : Alice 1re réglée, 2e partielle ; Bob 1re partielle, 2e en retard (110 000).
        retard = self.ind(statuts_echeance=("overdue",))
        self.assertEqual((retard["attendu_minor"], retard["restant_minor"]), (110000, 110000))
        self.assertEqual(self.ind(statuts_echeance=("paid",))["attendu_minor"], 150000)
        self.assertEqual(self.ind(solde="du")["encaisse_minor"], 210000)           # les deux doivent encore
        a_jour = self.ind(solde="a_jour")
        self.assertEqual((a_jour["encaisse_minor"], a_jour["attendu_minor"]), (0, 0))

    def test_comparaison_periode_precedente(self):
        r = calculer([self.feba], "perso", D(2026, 10, 1), D(2026, 10, 31), aujourd_hui=AUJ, comparer=True)
        self.assertEqual(r["periode_precedente"], {"du": "2026-08-31", "au": "2026-09-30"})
        xof = r["devises"][0]
        self.assertEqual(xof["indicateurs"]["encaisse_minor"], 60000)
        self.assertEqual(xof["precedent"]["encaisse_minor"], 150000)
        self.assertEqual(xof["variations"]["encaisse_minor"], -60.0)
        # Base nulle : pas de variation (jamais une division par zéro ni un faux 0 %).
        r = calculer([self.feba], "perso", D(2026, 8, 1), D(2026, 8, 31), aujourd_hui=AUJ, comparer=True)
        self.assertIsNone(r["devises"][0]["variations"]["encaisse_minor"])
        self.assertNotIn("precedent", calculer([self.feba], "12m", aujourd_hui=AUJ)["devises"][0])

    def test_periode_precedente_par_type(self):
        from apps.payments.tableau_bord import periode_precedente
        self.assertEqual(periode_precedente("12m", D(2025, 12, 1), D(2026, 11, 4)), (D(2024, 12, 1), D(2025, 11, 4)))
        self.assertEqual(periode_precedente("3m", D(2026, 3, 1), D(2026, 5, 31)), (D(2025, 12, 1), D(2026, 2, 28)))
        self.assertEqual(periode_precedente("annee", D(2026, 9, 1), D(2027, 6, 30)), (D(2025, 9, 1), D(2026, 6, 30)))
        self.assertEqual(periode_precedente("civile", D(2024, 1, 1), D(2024, 12, 31)), (D(2023, 1, 1), D(2023, 12, 31)))
        self.assertEqual(periode_precedente("7j", D(2026, 12, 9), D(2026, 12, 15)), (D(2026, 12, 2), D(2026, 12, 8)))

    def test_annee_civile(self):
        p = calculer([self.feba], "civile", aujourd_hui=AUJ)["periode"]
        self.assertEqual((p["du"], p["au"]), ("2026-01-01", "2026-12-31"))

    def test_detail_d_une_barre_egal_a_la_barre(self):
        r = calculer([self.feba], "12m", aujourd_hui=AUJ)
        octobre = next(c for c in r["devises"][0]["serie"] if c["date"] == "2026-10-01")
        d = detail([self.feba], "12m", aujourd_hui=AUJ, case=D(2026, 10, 1))
        self.assertEqual((d["du"], d["au"]), ("2026-10-01", "2026-10-31"))
        self.assertEqual(d["total"], 3)                                             # supprimé exclu
        self.assertEqual(sum(l["montant_minor"] for l in d["paiements"] if l["statut"] == "confirme"),
                         octobre["encaisse_minor"])
        self.assertEqual({l["eleve"] for l in d["paiements"]}, {self.bob.get_full_name()})
        tout = detail([self.feba], "12m", aujourd_hui=AUJ)
        self.assertEqual(tout["total"], Payment.objects.filter(student__school=self.feba, is_deleted=False,
                                                               payment_date__gte=D(2026, 1, 1)).count())
        self.assertEqual(detail([self.feba], "12m", aujourd_hui=AUJ, filtres=Filtres(classe=self.class_ce.pk))["total"], 1)

    def test_validation_des_filtres(self):
        for params in ({"nature": "xx"}, {"statut": "x"}, {"classe": "abc"}, {"montant_min": "-1"},
                       {"montant_min": "10", "montant_max": "5"}, {"cycle": "fac"}, {"solde": "?"},
                       {"statut_echeance": "late"}, {"montant_max": "NaN"}):
            with self.assertRaises(FiltreInvalide, msg=params):
                lire_filtres(params)
        f = lire_filtres({"nature": "mensualite,cantine", "montant_min": "1,5", "classe": "3"})
        self.assertEqual((f.natures, str(f.montant_min), f.classe), (("mensualite", "cantine"), "1.5", 3))
        with self.assertRaises(FiltreInvalide):
            calculer([self.feba, self.fha], "12m", aujourd_hui=AUJ, filtres=Filtres(classe=self.class_ce.pk))

    def client_sa(self, academie=None):
        c = APIClient()
        c.force_authenticate(self.sa)
        if academie:
            c.post("/api/auth/entity-context/switch/", {"entity_id": academie.id})
        return c

    def test_api_droits_export_et_isolation(self):
        base = "/api/payments/tableau-de-bord/"
        admin = APIClient()
        admin.force_authenticate(self.admin)
        for chemin in ("", "detail/", "filtres/"):
            self.assertEqual(admin.get(base + chemin).status_code, 403)
            self.assertEqual(APIClient().get(base + chemin).status_code, 401)
        tous = self.client_sa()
        self.assertEqual(tous.get(base + f"?classe={self.class_ce.pk}").status_code, 400)  # plusieurs académies
        self.assertFalse(tous.get(base + "filtres/").data["structure_disponible"])
        c = self.client_sa(self.feba)
        r = c.get(base + f"?periode=perso&du=2026-01-01&au=2026-12-31&classe={self.class_ce.pk}&comparer=1")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data["filtres"], {"classe": self.class_ce.pk})
        self.assertIn("variations", r.data["devises"][0])
        self.assertEqual(c.get(base + "?nature=inconnue").status_code, 400)
        self.assertEqual(c.get(base + "detail/?case=2026-13-01").status_code, 400)
        # Export CSV : en-tête + une ligne par paiement de la sélection.
        r = c.get(base + "detail/?periode=perso&du=2026-01-01&au=2026-12-31&export=csv")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r["Content-Type"].startswith("text/csv"))
        lignes = list(csv.reader(io.StringIO(r.content.decode("utf-8-sig")), delimiter=";"))
        self.assertEqual(lignes[0][0], "Date")
        self.assertEqual(len(lignes) - 1, 4)
        self.assertIn("150000", [l[9] for l in lignes[1:]])
        # Options dépendantes : niveau → ses classes ; classe → ses élèves.
        o = c.get(base + f"filtres/?niveau={self.ce.pk}").data
        self.assertEqual([x["nom"] for x in o["classes"]], ["CE1-A"])
        self.assertEqual(o["eleves"], [])
        o = c.get(base + f"filtres/?classe={self.class_ce.pk}").data
        self.assertEqual([x["id"] for x in o["eleves"]], [self.alice.pk])
        # Isolation : une classe FEBA demandée sur FHA ne renvoie rien de FEBA.
        fha = self.client_sa(self.fha)
        r = fha.get(base + f"detail/?classe={self.class_ce.pk}&periode=perso&du=2026-01-01&au=2026-12-31")
        self.assertEqual((r.status_code, r.data["total"]), (200, 0))
        o = fha.get(base + f"filtres/?classe={self.class_ce.pk}").data
        self.assertEqual(o["eleves"], [])


class CouvertureTarifsTests(ReminderBase):
    """Situations 2 et 3 : données partielles ou absentes, toujours expliquées."""

    def test_couverture(self):
        from apps.classes.models import Class
        from apps.schools.models import Level
        # Élève d'un niveau sans tarif (CP) : il n'a aucune échéance.
        cp = Class.objects.create(name="CP-A", level=Level.objects.create(school=self.feba, name="CP", order=1), school_year=self.year)
        self.student("Chloé", cp)
        xof = calculer([self.feba], "12m", aujourd_hui=AUJ)["devises"][0]
        self.assertTrue(xof["echeancier_configure"])
        self.assertEqual(xof["couverture"], {"eleves_actifs": 3, "eleves_avec_echeances": 2, "eleves_sans_tarif": 1,
                                             "academies_sans_tarif": []})
        usd = calculer([self.fha], "12m", aujourd_hui=AUJ)
        self.assertFalse(usd["devises"][0]["echeancier_configure"])
        self.assertEqual(usd["devises"][0]["couverture"]["academies_sans_tarif"], [self.fha.name])
        self.assertEqual(usd["par_academie"][0]["eleves_sans_tarif"], usd["par_academie"][0]["eleves_actifs"])
