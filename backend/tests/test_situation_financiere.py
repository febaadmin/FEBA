"""
Situation financière : totaux par élève, classe, niveau et académie calculés par
compute_dues (une seule règle), et accès limités (personnel de l'académie,
parent de l'élève ; jamais enseignant ni élève).

Fixture (ReminderBase) : Alice CE1 (150 000 au 30/09, 100 000 au 30/11,
79 800 au 31/01) et Bob CM1 (150 000, 110 000, 89 500).
"""
from rest_framework.test import APIClient

from apps.payments.models import StudentFeeArrangement
from apps.payments.situation import situation_eleve, situation_groupee
from tests.test_audit_p1_payment_reminders import D, ReminderBase

AUJ = D(2026, 12, 15)


class SituationTests(ReminderBase):
    def setUp(self):
        self.pay(self.alice, "150000", payment_date=D(2026, 9, 20))
        self.pay(self.alice, "30000", "cantine", payment_date=D(2026, 10, 2))   # aucun tarif cantine
        self.pay(self.bob, "60000", payment_date=D(2026, 10, 5))
        self.pay(self.bob, "40000", payment_date=D(2026, 10, 7), is_confirmed=False)          # annulé : ignoré

    def test_eleve(self):
        s = situation_eleve(self.alice, aujourd_hui=AUJ)
        t = s["totaux"]
        self.assertEqual((t["attendu_minor"], t["paye_minor"], t["restant_minor"]), (329800, 150000, 179800))
        self.assertEqual(t["retard_minor"], 100000)                 # tranche du 30/11 échue, impayée
        # Définition retenue (novembre 2026) : encaissé ÷ net attendu × 100 ; le taux sur les
        # seules échéances passées reste disponible sous son propre nom.
        self.assertEqual(t["taux_recouvrement"], round(100 * 150000 / 329800, 1))
        self.assertEqual(t["taux_recouvrement_echu"], round(100 * 150000 / 250000, 1))
        self.assertEqual(t["paye_total_minor"], 180000)
        self.assertEqual(t["hors_echeancier_minor"], 30000)         # cantine : sans tarif, affichée à part
        self.assertEqual(len(s["echeances"]), 3)
        self.assertEqual([e["en_retard"] for e in s["echeances"]], [False, True, False])
        self.assertEqual(len(s["paiements"]), 2)

    def test_reduction_et_exoneration(self):
        StudentFeeArrangement.objects.create(student=self.bob, fee_schedule=self.tuition_cm, kind="discount",
                                             discount_minor=50000, reason="Bourse")
        t = situation_eleve(self.bob, aujourd_hui=AUJ)["totaux"]
        self.assertEqual(t["attendu_minor"], 349500 - 50000)
        StudentFeeArrangement.objects.create(student=self.alice, fee_schedule=self.tuition_ce, kind="exemption", reason="Exonération")
        self.assertEqual(situation_eleve(self.alice, aujourd_hui=AUJ)["totaux"]["attendu_minor"], 0)

    def test_classes_niveaux_academie(self):
        r = situation_groupee(self.feba, "classe", aujourd_hui=AUJ)
        classes = {g["nom"]: g for g in r["groupes"]}
        self.assertEqual(classes["CE1-A"]["restant_minor"], 179800)
        self.assertEqual(classes["CM1-A"]["restant_minor"], 349500 - 60000)
        self.assertEqual((classes["CM1-A"]["eleves"], classes["CM1-A"]["eleves_en_retard"]), (1, 1))
        total = r["totaux"]
        self.assertEqual(total["attendu_minor"], 329800 + 349500)
        self.assertEqual(total["paye_minor"], 210000)
        self.assertEqual(total["restant_minor"], sum(g["restant_minor"] for g in r["groupes"]))
        self.assertEqual(r["eleves"][0]["nom"], self.bob.get_full_name())   # plus fort retard en tête
        niveaux = situation_groupee(self.feba, "niveau", aujourd_hui=AUJ)
        self.assertEqual(sorted(g["nom"] for g in niveaux["groupes"]), ["CE1", "CM1"])

    def test_sans_tarif(self):
        r = situation_groupee(self.fha, "classe", aujourd_hui=AUJ)
        self.assertFalse(r["echeancier_configure"])
        self.assertEqual(r["groupes"], [])

    def test_acces(self):
        url = f"/api/payments/situation/eleves/{self.alice.pk}/"
        c = APIClient()
        c.force_authenticate(self.admin)
        self.assertEqual(c.get(url).status_code, 200)
        self.assertEqual(c.get("/api/payments/situation/?groupe=niveau").status_code, 200)
        self.assertEqual(c.get("/api/payments/situation/?groupe=xx").status_code, 400)
        c.force_authenticate(self.parent_user)        # parent d'Alice et de Bob
        self.assertEqual(c.get(url).status_code, 200)
        self.assertEqual(c.get("/api/payments/situation/").status_code, 403)
        c.force_authenticate(self.parent2_user)       # autre famille
        self.assertEqual(c.get(url).status_code, 404)
        for role in ("teacher", "student"):
            u = self.user(f"sit_{role}", role, self.feba)
            c.force_authenticate(u)
            self.assertEqual(c.get(url).status_code, 403, role)
            self.assertEqual(c.get("/api/payments/situation/").status_code, 403, role)
        autre_admin = self.user("sit_admin_fha", "admin", self.fha)
        c.force_authenticate(autre_admin)
        self.assertEqual(c.get(url).status_code, 404)
        sa = self.user("sit_sa", "superadmin", None)
        c.force_authenticate(sa)
        r = c.get("/api/payments/situation/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual({a["devise"] for a in r.data["academies"]}, {"USD", "XOF"})
