"""
Tarifs : natures de frais étendues, historique des changements, motif obligatoire
pour changer le montant d'un tarif déjà payé, suppression refusée d'un tarif utilisé.
"""
from datetime import date

from rest_framework.test import APIClient

from apps.payments.models import FeeSchedule, FeeScheduleChange, Payment, StudentFeeArrangement
from tests.test_audit_p1_payment_reminders import D, ReminderBase


class TarifsHistoriqueTests(ReminderBase):
    def setUp(self):
        self.c = APIClient()
        self.c.force_authenticate(self.admin)

    def creer(self, **extra):
        corps = {"payment_type": "examen", "label": "Examen BEPC", "school_year": self.year.pk,
                 "amount": "15000", "installments": [], **extra}
        r = self.c.post("/api/payments/fee-schedules/", corps, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        return FeeSchedule.objects.get(pk=r.data["id"])

    def test_nouvelles_natures_acceptees(self):
        for nature in ("reinscription", "dossier", "examen", "fournitures", "activites"):
            self.assertIn(nature, dict(Payment.PAYMENT_TYPES))
        tarif = self.creer()
        self.assertEqual(tarif.amount_minor, 15000)
        r = self.c.post("/api/payments/fee-schedules/", {"payment_type": "inconnu", "amount": "1"}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_historique_creation_modification_desactivation(self):
        tarif = self.creer()
        self.c.patch(f"/api/payments/fee-schedules/{tarif.pk}/", {"amount": "17500", "motif": "Révision 2026"}, format="json")
        self.c.patch(f"/api/payments/fee-schedules/{tarif.pk}/", {"is_active": False}, format="json")
        actions = list(FeeScheduleChange.objects.filter(fee_schedule=tarif).order_by("pk").values_list("action", flat=True))
        self.assertEqual(actions, ["creation", "modification", "desactivation"])
        modif = FeeScheduleChange.objects.get(fee_schedule=tarif, action="modification")
        self.assertEqual((modif.old_amount_minor, modif.new_amount_minor, modif.reason), (15000, 17500, "Révision 2026"))
        self.assertEqual(modif.changed_by, self.admin)
        r = self.c.get("/api/payments/fee-schedules/historique/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual([h["action"] for h in r.data[:3]], ["desactivation", "modification", "creation"])
        self.assertIn("Examen BEPC", r.data[0]["description"])

    def test_motif_obligatoire_si_tarif_deja_paye(self):
        tarif = self.tuition_ce
        self.pay(self.alice, "150000")
        r = self.c.patch(f"/api/payments/fee-schedules/{tarif.pk}/", {"amount": "350000"}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("motif", r.data)
        tarif.refresh_from_db()
        self.assertEqual(tarif.amount_minor, 329800)
        r = self.c.patch(f"/api/payments/fee-schedules/{tarif.pk}/", {"amount": "329800"}, format="json")
        self.assertEqual(r.status_code, 200, "même montant : aucun motif exigé")

    def test_suppression_refusee_si_utilise(self):
        StudentFeeArrangement.objects.create(student=self.alice, fee_schedule=self.tuition_ce, kind="exemption", reason="Bourse")
        r = self.c.delete(f"/api/payments/fee-schedules/{self.tuition_ce.pk}/")
        self.assertEqual(r.status_code, 409)
        self.assertTrue(StudentFeeArrangement.objects.filter(student=self.alice).exists())
        libre = self.creer(payment_type="activites", label="Sortie")
        r = self.c.delete(f"/api/payments/fee-schedules/{libre.pk}/", {"motif": "Erreur de saisie"}, format="json")
        self.assertEqual(r.status_code, 204)
        trace = FeeScheduleChange.objects.get(action="suppression")
        self.assertIsNone(trace.fee_schedule)
        self.assertEqual((trace.old_amount_minor, trace.reason), (15000, "Erreur de saisie"))

    def test_historique_limite_a_l_academie(self):
        self.creer()
        from apps.accounts.models import CustomUser
        autre = CustomUser.objects.create_user(username="fha_admin_h", email="fha_admin_h@test.io", password="x",
                                               role="admin", school=self.fha, first_name="F", last_name="H")
        c = APIClient()
        c.force_authenticate(autre)
        self.assertEqual(c.get("/api/payments/fee-schedules/historique/").data, [])
        enseignant = CustomUser.objects.create_user(username="prof_h", email="prof_h@test.io", password="x",
                                                    role="teacher", school=self.feba, first_name="P", last_name="H")
        c.force_authenticate(enseignant)
        self.assertEqual(c.get("/api/payments/fee-schedules/historique/").status_code, 403)
