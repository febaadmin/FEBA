"""
Clôture — module financier : remises, exonérations, échéanciers personnels, journal,
situation financière (vues, KPI, filtres, export) et permissions.

Fixture (ReminderBase) : académie XOF, Alice CE1 (150 000 au 30/09, 100 000 au 30/11,
79 800 au 31/01 ; total 329 800) et Bob CM1 (150 000, 110 000, 89 500 ; total 349 500),
même responsable (fratrie : Alice rang 1, Bob rang 2 à date de naissance égale).
Aucun e-mail, aucun paiement réel : base de test.
"""
from decimal import Decimal

from rest_framework.test import APIClient

from apps.payments.models import (
    EcheanceEleve, JournalFinancier, Payment, PaymentReminder, RegleRemise, StudentFeeArrangement,
)
from apps.payments.situation import situation_eleve, situation_groupee, Filtres
from apps.payments.transaction_models import PaymentTransaction
from tests.test_audit_p1_payment_reminders import D, ReminderBase

AUJ = D(2026, 12, 15)
R = "/api/payments/regles-remise/"


class Base(ReminderBase):
    def regle(self, **kw):
        kw.setdefault("academy", self.feba)
        kw.setdefault("nom", "Règle test")
        kw.setdefault("mode", RegleRemise.POURCENTAGE)
        if kw["mode"] == RegleRemise.POURCENTAGE:
            kw.setdefault("pourcentage", Decimal("10"))
        if kw.get("genre") == RegleRemise.EXONERATION or kw.get("categorie") in RegleRemise.JUSTIFICATION_REQUISE:
            kw.setdefault("justification", "Décision du conseil")
        return RegleRemise.objects.create(**kw)

    def net(self, eleve, on=AUJ):
        return situation_eleve(eleve, aujourd_hui=on)["totaux"]

    def cli(self, user=None):
        c = APIClient()
        c.force_authenticate(user or self.admin)
        return c


class RemisesTests(Base):
    def test_remise_pourcentage_sur_une_nature_et_un_eleve(self):
        self.regle(student=self.alice, payment_type="mensualite", pourcentage=Decimal("10"))
        t = self.net(self.alice)
        self.assertEqual((t["theorique_minor"], t["remises_minor"], t["net_minor"]), (329800, 32980, 296820))
        self.assertEqual(self.net(self.bob)["remises_minor"], 0)          # n'affecte pas les autres élèves

    def test_remise_fixe_imputee_sur_les_dernieres_echeances_et_jamais_negative(self):
        self.regle(student=self.alice, mode=RegleRemise.MONTANT, montant_minor=90000)
        d = self.dues(AUJ)
        self.assertEqual(d[("Alice", "3e tranche")].discount, 79800)
        self.assertEqual(d[("Alice", "2e tranche")].discount, 10200)
        self.assertEqual(d[("Alice", "1re tranche")].discount, 0)
        self.regle(student=self.alice, mode=RegleRemise.MONTANT, montant_minor=10_000_000, nom="Énorme")
        t = self.net(self.alice)
        self.assertEqual(t["net_minor"], 0)
        self.assertTrue(all(i.net >= 0 and i.outstanding >= 0 for i in self.dues(AUJ).values()))

    def test_cumul_et_non_cumul(self):
        self.regle(student=self.alice, pourcentage=Decimal("10"), nom="A")                 # 32 980
        self.regle(student=self.alice, mode=RegleRemise.MONTANT, montant_minor=20000, nom="B")
        self.assertEqual(self.net(self.alice)["remises_minor"], 52980)                    # cumulables additionnées
        seule = self.regle(student=self.alice, pourcentage=Decimal("20"), cumulable=False, nom="C")   # 65 960
        t = situation_eleve(self.alice, aujourd_hui=AUJ)
        self.assertEqual(t["totaux"]["remises_minor"], 65960)                             # la plus favorable, seule
        ajust = {a["nom"]: a for a in t["tarifs"][0]["ajustements"]}
        self.assertTrue(ajust["C"]["retenue"])
        self.assertFalse(ajust["A"]["retenue"])
        self.assertIn("non cumulable", ajust["A"]["raison"])
        seule.pourcentage = Decimal("5")
        seule.save()
        self.assertEqual(self.net(self.alice)["remises_minor"], 52980)                    # les cumulables reprennent

    def test_une_regle_ne_compte_qu_une_fois(self):
        self.regle(payment_type="mensualite", pourcentage=Decimal("10"), level=self.ce, class_obj=self.class_ce)
        self.assertEqual(self.net(self.alice)["remises_minor"], 32980)

    def test_fratrie_famille_et_classe(self):
        self.regle(categorie=RegleRemise.FRATRIE, rang_enfant_min=2, pourcentage=Decimal("15"), nom="Fratrie")
        self.assertEqual(self.net(self.alice)["remises_minor"], 0)                         # aîné (rang 1)
        self.assertEqual(self.net(self.bob)["remises_minor"], round(349500 * 0.15))
        famille = self.alice.parents.first().parent
        self.regle(famille=famille, mode=RegleRemise.MONTANT, montant_minor=5000, nom="Famille")
        self.assertEqual(self.net(self.alice)["remises_minor"], 5000)
        self.regle(class_obj=self.class_cm, mode=RegleRemise.MONTANT, montant_minor=1000, nom="Classe CM")
        self.assertEqual(self.net(self.alice)["remises_minor"], 5000)

    def test_paiement_anticipe_et_integral(self):
        self.regle(categorie=RegleRemise.ANTICIPE, date_limite_paiement=D(2026, 9, 30), pourcentage=Decimal("5"),
                   student=self.alice, nom="Anticipé")
        self.assertEqual(self.net(self.alice)["remises_minor"], 0)                         # rien payé : écartée
        self.pay(self.alice, "200000", payment_date=D(2026, 9, 10))
        self.assertEqual(self.net(self.alice)["remises_minor"], 0)                         # partiel : écartée
        self.pay(self.alice, str(329800 - 16490 - 200000), payment_date=D(2026, 9, 25))
        t = self.net(self.alice)
        self.assertEqual((t["remises_minor"], t["restant_minor"]), (16490, 0))            # condition remplie : soldé
        self.regle(categorie=RegleRemise.INTEGRAL, pourcentage=Decimal("3"), student=self.bob, nom="Intégral")
        self.pay(self.bob, "100000")
        self.assertEqual(self.net(self.bob)["remises_minor"], 0)
        self.pay(self.bob, str(349500 - 10485))
        self.assertEqual(self.net(self.bob)["remises_minor"], 10485)


class ExonerationsTests(Base):
    def test_exoneration_totale_partielle_et_temporaire(self):
        self.regle(genre=RegleRemise.EXONERATION, categorie=RegleRemise.SOCIALE, pourcentage=Decimal("100"), student=self.alice)
        t = self.net(self.alice)
        self.assertEqual((t["exonerations_minor"], t["net_minor"], t["restant_minor"]), (329800, 0, 0))
        self.assertTrue(all(i.status == "exempted" for k, i in self.dues(AUJ).items() if k[0] == "Alice"))
        self.regle(genre=RegleRemise.EXONERATION, categorie=RegleRemise.ADMINISTRATIVE, pourcentage=Decimal("50"),
                   student=self.bob, debut=D(2026, 11, 1), fin=D(2026, 12, 31))
        d = self.dues(AUJ)
        self.assertEqual(d[("Bob", "2e tranche")].exemption, 55000)                       # seule l'échéance de novembre
        self.assertEqual(d[("Bob", "1re tranche")].exemption, 0)

    def test_exoneration_puis_remise_sur_le_reste(self):
        self.regle(genre=RegleRemise.EXONERATION, categorie=RegleRemise.SOCIALE, pourcentage=Decimal("50"), student=self.alice)
        self.regle(student=self.alice, pourcentage=Decimal("10"))
        t = self.net(self.alice)
        self.assertEqual((t["exonerations_minor"], t["remises_minor"]), (164900, 16490))

    def test_justification_obligatoire(self):
        r = self.cli().post(R, {"nom": "Exo", "genre": "exoneration", "categorie": "sociale", "mode": "pourcentage",
                                "pourcentage": "100", "student": self.alice.pk}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("justification", r.data)

    def test_disposition_historique_toujours_prise_en_compte(self):
        StudentFeeArrangement.objects.create(student=self.alice, fee_schedule=self.tuition_ce, kind="discount", discount_minor=50000)
        self.assertEqual(self.net(self.alice)["remises_minor"], 50000)


class EcheancierPersonnelTests(Base):
    URL = "/api/payments/echeanciers-eleves/"

    def definir(self, lignes, **extra):
        return self.cli().post(self.URL, {"student": self.alice.pk, "fee_schedule": self.tuition_ce.pk,
                                          "school_year": self.year.pk, "motif": "Accord avec la famille",
                                          "echeances": lignes, **extra}, format="json")

    def test_remplace_les_echeances_standard_sans_toucher_aux_paiements(self):
        p = self.pay(self.alice, "150000", payment_date=D(2026, 9, 20))
        avant = (p.amount_minor, p.is_confirmed)
        r = self.definir([{"label": "A", "due_date": "2026-10-31", "montant": "100000"},
                          {"label": "B", "due_date": "2027-01-31", "montant": "100000"},
                          {"label": "C", "due_date": "2027-03-31", "montant": "129800"}])
        self.assertEqual(r.status_code, 201, r.data)
        echeances = situation_eleve(self.alice, aujourd_hui=AUJ)["echeances"]
        self.assertEqual([e["installment_label"] for e in echeances], ["A", "B", "C"])
        self.assertTrue(all(e["personnelle"] for e in echeances))
        t = self.net(self.alice)
        self.assertEqual((t["paye_minor"], t["retard_minor"]), (150000, 0))               # délai accordé : plus de retard
        p.refresh_from_db()
        self.assertEqual((p.amount_minor, p.is_confirmed), avant)
        self.assertEqual(len(self.dues(AUJ)), 6)                                           # Bob inchangé (3)

    def test_somme_controlee_et_motif_obligatoire(self):
        r = self.definir([{"label": "A", "due_date": "2026-10-31", "montant": "1000"}])
        self.assertEqual(r.status_code, 400)
        r = self.definir([{"label": "A", "due_date": "2026-10-31", "montant": "329800"}], motif="")
        self.assertEqual(r.status_code, 400)

    def test_historique_et_retour_au_standard(self):
        self.definir([{"label": "A", "due_date": "2026-10-31", "montant": "329800"}])
        self.definir([{"label": "A", "due_date": "2026-12-31", "montant": "329800"}])     # délai supplémentaire
        j = JournalFinancier.objects.filter(objet="echeancier", student=self.alice)
        self.assertEqual(list(j.values_list("action", flat=True)), ["modification", "creation"])
        self.assertEqual(j.first().avant["echeances"][0][1], "2026-10-31")
        self.assertEqual(EcheanceEleve.objects.filter(student=self.alice).count(), 2)     # rien n'est supprimé
        r = self.cli().post(self.URL + "retablir/", {"student": self.alice.pk, "fee_schedule": self.tuition_ce.pk,
                                                    "school_year": self.year.pk, "motif": "Fin de l'accord"}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertFalse(any(e["personnelle"] for e in situation_eleve(self.alice, aujourd_hui=AUJ)["echeances"]))

    def test_relances_sur_echeance_personnelle_sans_collision(self):
        self.definir([{"label": "Perso", "due_date": "2026-10-15", "montant": "329800"}])
        run = self.run_engine(AUJ)
        self.assertEqual(run.status, "done", run.error)
        perso = PaymentReminder.objects.filter(student=self.alice)
        self.assertTrue(perso.exists())
        self.assertTrue(all(r.student_installment_id and r.installment_id is None and r.idempotency_key.startswith("pers")
                            for r in perso))
        self.assertEqual(perso.first().amount_due_minor, 329800)


class PaiementsEtSituationTests(Base):
    def test_partiel_integral_multiple_remboursement_annulation_retard(self):
        self.pay(self.alice, "100000", payment_date=D(2026, 9, 1))
        self.pay(self.alice, "50000", payment_date=D(2026, 9, 2))
        annule = self.pay(self.alice, "100000", payment_date=D(2026, 9, 3), is_confirmed=False)
        t = self.net(self.alice)
        self.assertEqual((t["paye_minor"], t["retard_minor"]), (150000, 100000))         # 2e tranche en retard au 15/12
        carte = self.pay(self.alice, "179800", payment_date=D(2026, 12, 1))
        PaymentTransaction.objects.create(academy=self.feba, student=self.alice, payment=carte, payment_type="mensualite",
                                          school_year=self.year, amount_minor=179800, currency="XOF",
                                          amount_refunded_minor=79800, status="refunded")
        t = self.net(self.alice)
        self.assertEqual((t["paye_minor"], t["restant_minor"]), (250000, 79800))
        self.assertEqual(situation_groupee(self.feba, aujourd_hui=AUJ)["kpi"]["eleves_partiels"], 1)
        annule.refresh_from_db()
        self.assertFalse(annule.is_confirmed)

    def test_totaux_coherents_et_statuts(self):
        self.pay(self.alice, "329800")
        s = situation_groupee(self.feba, aujourd_hui=AUJ)
        self.assertEqual(sum(g["net_minor"] for g in s["groupes"]), s["totaux"]["net_minor"])
        self.assertEqual(sum(e["restant_minor"] for e in s["eleves"]), s["totaux"]["restant_minor"])
        self.assertEqual((s["kpi"]["eleves_soldes"], s["kpi"]["eleves_aucun_paiement"]), (1, 1))
        self.assertEqual(s["totaux"]["taux_recouvrement"], round(100 * 329800 / (329800 + 349500), 1))
        self.assertTrue(s["calculable"])

    def test_non_calculable_sans_tarif(self):
        s = situation_groupee(self.fha, aujourd_hui=AUJ)
        self.assertFalse(s["calculable"])
        self.assertIn("ne peuvent pas être calculés", s["raison_non_calculable"])

    def test_filtres(self):
        self.pay(self.alice, "329800")
        f = lambda **p: situation_groupee(self.feba, aujourd_hui=AUJ, filtres=Filtres(p))  # noqa: E731
        self.assertEqual([e["nom"] for e in f(classe=str(self.class_cm.pk))["eleves"]], ["Bob Élève"])
        self.assertEqual([e["nom"] for e in f(statut="solde")["eleves"]], ["Alice Élève"])
        self.assertEqual([e["nom"] for e in f(statut="en_retard")["eleves"]], ["Bob Élève"])
        self.assertEqual([e["nom"] for e in f(q="alic")["eleves"]], ["Alice Élève"])
        self.assertEqual(f(nature="cantine")["totaux"]["net_minor"], 0)
        self.assertEqual(f(debut="2026-11-01", fin="2026-11-30")["totaux"]["theorique_minor"], 100000 + 110000)

    def test_changement_d_annee_et_de_classe(self):
        from apps.schools.models import SchoolYear
        from apps.students.models import StudentEnrollment
        autre = SchoolYear.objects.create(school=self.feba, name="2027-2028", start_date="2027-09-01", end_date="2028-06-30")
        self.regle(school_year=autre, pourcentage=Decimal("50"), student=self.alice)
        self.assertEqual(self.net(self.alice)["remises_minor"], 0)                         # autre année : sans effet
        # Classe DE L'ANNÉE (inscription) et non classe actuelle.
        StudentEnrollment.objects.create(student=self.alice, school_year=self.year, class_obj=self.class_ce)
        self.alice.current_class = self.class_cm
        self.alice.save()
        self.regle(class_obj=self.class_ce, mode=RegleRemise.MONTANT, montant_minor=1000)
        self.assertEqual(self.net(self.alice)["remises_minor"], 1000)

    def test_export_csv(self):
        self.regle(student=self.alice, mode=RegleRemise.MONTANT, montant_minor=1000)
        r = self.cli().get("/api/payments/situation/export/", {"academy_id": self.feba.pk})
        self.assertEqual(r.status_code, 200)
        texte = r.content.decode("utf-8-sig")
        self.assertIn("Alice Élève", texte)
        self.assertIn("1000", texte)


class ApiEtPermissionsTests(Base):
    def test_creation_modification_annulation_tracees_jamais_supprimees(self):
        c = self.cli()
        r = c.post(R, {"nom": "Rentrée", "mode": "pourcentage", "pourcentage": "10", "payment_type": "mensualite",
                       "level": self.ce.pk}, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        rid = r.data["id"]
        self.assertEqual(c.patch(f"{R}{rid}/", {"pourcentage": "12"}, format="json").status_code, 400)   # motif requis
        r = c.patch(f"{R}{rid}/", {"pourcentage": "12", "motif": "Décision du 5/11"}, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(c.delete(f"{R}{rid}/").status_code, 405)
        self.assertEqual(c.post(f"{R}{rid}/annuler/", {}, format="json").status_code, 400)
        self.assertEqual(c.post(f"{R}{rid}/annuler/", {"motif": "Erreur de saisie"}, format="json").status_code, 200)
        self.assertEqual(self.net(self.alice)["remises_minor"], 0)
        j = list(JournalFinancier.objects.filter(objet="regle", objet_id=rid).order_by("le", "pk"))
        self.assertEqual([x.action for x in j], ["creation", "modification", "annulation"])
        self.assertEqual((j[1].avant["pourcentage"], j[1].apres["pourcentage"]), ("10.00", "12.00"))
        self.assertEqual(j[1].auteur, self.admin)
        self.assertTrue(RegleRemise.objects.filter(pk=rid).exists())
        h = c.get("/api/payments/journal-financier/").data
        self.assertTrue(any(x["objet"] == "regle" and x["action"] == "annulation" for x in h))

    def test_impact(self):
        r = self.regle(payment_type="mensualite", pourcentage=Decimal("10"))
        d = self.cli().get(f"{R}{r.pk}/impact/").data
        self.assertEqual(d["nombre"], 2)
        self.assertEqual(d["total_minor"], 32980 + 34950)

    def test_permissions_par_profil_et_cloisonnement(self):
        prof = self.user("fin_prof", "teacher", self.feba)
        for u in (prof, self.parent_user):
            self.assertEqual(self.cli(u).get(R).status_code, 403)
            self.assertEqual(self.cli(u).get("/api/payments/situation/").status_code, 403)
            self.assertEqual(self.cli(u).get("/api/payments/journal-financier/").status_code, 403)
        admin_fha = self.user("fin_admin_fha", "admin", self.fha)
        r = self.regle(student=self.alice)
        self.assertEqual(self.cli(admin_fha).get(f"{R}{r.pk}/").status_code, 404)
        self.assertEqual(self.cli(admin_fha).post(R, {"nom": "x", "mode": "pourcentage", "pourcentage": "5",
                                                      "student": self.alice.pk}, format="json").status_code, 400)
        # Parent : fiche de son enfant sans historique interne ni justification.
        self.regle(genre=RegleRemise.EXONERATION, categorie=RegleRemise.SOCIALE, pourcentage=Decimal("10"),
                   student=self.alice, justification="Situation familiale confidentielle")
        d = self.cli(self.parent_user).get(f"/api/payments/situation/eleves/{self.alice.pk}/").data
        self.assertEqual(d["historique"], [])
        self.assertNotIn("confidentielle", str(d))

    def test_donnees_existantes_non_alterees(self):
        p = self.pay(self.alice, "150000")
        StudentFeeArrangement.objects.create(student=self.bob, fee_schedule=self.tuition_cm, kind="discount", discount_minor=1000)
        avant = list(Payment.objects.values_list("pk", "amount_minor", "is_confirmed", "is_deleted"))
        self.regle(student=self.alice, pourcentage=Decimal("10"))
        situation_groupee(self.feba, aujourd_hui=AUJ)
        self.cli().get("/api/payments/situation/", {"groupe": "eleve"})
        self.assertEqual(list(Payment.objects.values_list("pk", "amount_minor", "is_confirmed", "is_deleted")), avant)
        self.assertEqual(StudentFeeArrangement.objects.get(student=self.bob).discount_minor, 1000)
        p.refresh_from_db()
        self.assertEqual(p.amount_minor, 150000)

    def test_vue_par_eleve_pagination_tri(self):
        d = self.cli().get("/api/payments/situation/", {"groupe": "eleve", "tri": "nom", "ordre": "asc"}).data["academies"][0]
        self.assertEqual([e["nom"] for e in d["eleves"]], ["Alice Élève", "Bob Élève"])
        self.assertEqual(d["eleves_total"], 2)
        self.assertEqual(self.cli().get("/api/payments/situation/", {"groupe": "x"}).status_code, 400)


class BaremeEtDispositionsTests(Base):
    def test_bareme_apercu_puis_import_explicite_sans_remplacement(self):
        from apps.payments.models import FeeSchedule
        from apps.schools.models import Level, School, SchoolYear
        feba = School.objects.create(name="FEBA", address="Cotonou", code="FEBA", currency_code="XOF")
        SchoolYear.objects.create(school=feba, name="2026-2027", is_current=True, start_date="2026-09-01", end_date="2027-06-30")
        Level.objects.create(school=feba, name="CE1", order=3)
        admin = self.user("bar_admin", "admin", feba)
        c = self.cli(admin)
        d = c.get("/api/payments/baremes/").data
        self.assertEqual(len(d), 1)
        self.assertTrue(d[0]["a_confirmer"])
        a_creer = sum(1 for l in d[0]["lignes"] if l["action"] == "creer")
        self.assertGreater(a_creer, 0)
        self.assertEqual(c.post("/api/payments/baremes/", {"fichier": d[0]["fichier"]}, format="json").status_code, 400)
        r = c.post("/api/payments/baremes/", {"fichier": d[0]["fichier"], "confirmation": True}, format="json")
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.data["crees"], a_creer)
        self.assertEqual(FeeSchedule.objects.filter(academy=feba).count(), a_creer)
        self.assertEqual(c.post("/api/payments/baremes/", {"fichier": d[0]["fichier"], "confirmation": True}, format="json").data["crees"], 0)
        # L'académie de test « REL-FEBA » n'a aucun barème : rien n'est proposé.
        self.assertEqual(self.cli().get("/api/payments/baremes/").data, [])

    def test_disposition_creation_et_suppression_tracees(self):
        c = self.cli()
        r = c.post("/api/payments/fee-arrangements/", {"student": self.alice.pk, "fee_schedule": self.tuition_ce.pk,
                                                       "kind": "exemption", "reason": "Bourse"}, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(c.delete(f"/api/payments/fee-arrangements/{r.data['id']}/", {"motif": "Fin de bourse"}, format="json").status_code, 204)
        j = list(JournalFinancier.objects.filter(objet="disposition", student=self.alice).order_by("le", "pk"))
        self.assertEqual([x.action for x in j], ["creation", "suppression"])
        self.assertEqual(j[1].avant["kind"], "exemption")

    def test_journal_inalterable(self):
        from django.core.exceptions import ValidationError
        j = JournalFinancier.objects.create(academy=self.feba, objet="regle", action="creation", description="x")
        j.description = "modifié"
        with self.assertRaises(ValidationError):
            j.save()
        with self.assertRaises(ValidationError):
            j.delete()


class EcheancesTarifTests(Base):
    def test_resoumettre_une_date_ou_echanger_deux_dates(self):
        c = self.cli()
        url = f"/api/payments/fee-schedules/{self.tuition_ce.pk}/"
        lignes = [{"label": "T1", "due_date": "2026-09-30", "amount": "150000"}, {"label": "T2", "due_date": "2026-11-30", "amount": "100000"},
                  {"label": "T3", "due_date": "2027-01-31", "amount": "79800"}]
        ids_avant = sorted(self.tuition_ce.installments.values_list("pk", flat=True))
        r = c.patch(url, {"installments": lignes}, format="json")                      # sans identifiants
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(sorted(self.tuition_ce.installments.values_list("pk", flat=True)), ids_avant)   # mêmes échéances
        a, b = self.tuition_ce.installments.order_by("due_date")[:2]
        r = c.patch(url, {"installments": [{"id": a.pk, "label": "T1", "due_date": "2026-11-30", "amount": "150000"},
                                           {"id": b.pk, "label": "T2", "due_date": "2026-09-30", "amount": "100000"},
                                           {"label": "T3", "due_date": "2027-01-31", "amount": "79800"}]}, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        a.refresh_from_db()
        self.assertEqual(str(a.due_date), "2026-11-30")


class EncaissementsSansTarifTests(Base):
    def test_encaissements_reels_meme_sans_echeancier(self):
        from apps.payments.models import FeeSchedule
        FeeSchedule.objects.filter(academy=self.feba).update(is_active=False)
        self.pay(self.alice, "150000", payment_date=D(2026, 9, 20))
        self.pay(self.bob, "40000", payment_date=D(2026, 10, 7), is_confirmed=False)         # annulé : exclu
        s = situation_groupee(self.feba, aujourd_hui=AUJ)
        self.assertFalse(s["calculable"])
        self.assertEqual(s["totaux"]["encaisse_total_minor"], 150000)
        self.assertEqual(s["graphiques"]["encaissements_mensuels"][0]["mois"], "2026-09")
