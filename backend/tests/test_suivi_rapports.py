"""Rapports : données réelles, validation avant publication, versions figées. Alertes : règles, décision humaine."""
from datetime import date, timedelta

import fitz

from apps.attendance.models import Attendance
from apps.notifications.models import Notification
from apps.suivi import alertes, rapports
from apps.suivi.models import AlertePedagogique, EvaluationPedagogique, Objectif, RapportPedagogique, RapportVersion, RegleAlerte
from tests.test_suivi import Base, activer
from tests.test_virtualclass import make_school, make_user


class RapportTests(Base):
    corps = {"type": "mensuel", "du": "2026-10-01", "au": "2026-10-31"}

    def creer(self):
        self.en(self.prof)
        r = self.client.post("/api/suivi/rapports/", {**self.corps, "student": self.eleve.pk}, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        return r.data["id"]

    def test_sans_donnee_rien_n_est_invente(self):
        rid = self.creer()
        d = RapportPedagogique.objects.get(pk=rid).donnees
        self.assertFalse(d["progression"]["has_data"])
        contenu = rapports.pdf(d, {})
        texte = "".join(p.get_text() for p in fitz.open(stream=contenu, filetype="pdf"))
        self.assertIn("Non renseigné", texte)
        self.assertNotIn("%", texte)

    def test_cycle_et_versions(self):
        rid = self.creer()
        url = f"/api/suivi/rapports/{rid}/"
        self.assertEqual(self.client.post(url + "publier/").status_code, 400)
        self.assertEqual(self.client.patch(url, {"contenu": {"appreciation": "Bon mois"}}, format="json").status_code, 200)
        self.assertEqual(self.client.patch(url, {"contenu": {"note": "x"}}, format="json").status_code, 400)
        self.assertEqual(self.client.post(url + "valider/").status_code, 200)
        self.assertEqual(self.client.post(url + "publier/").status_code, 200)
        self.assertEqual(self.client.patch(url, {"contenu": {"appreciation": "Autre"}}, format="json").status_code, 400)
        self.assertEqual(self.client.post(url + "nouvelle_version/").data["numero_version"], 2)
        self.client.patch(url, {"contenu": {"appreciation": "Corrigé"}}, format="json")
        self.assertEqual(RapportVersion.objects.filter(rapport_id=rid).count(), 2)
        self.assertEqual(rapports.version_publiee(RapportPedagogique.objects.get(pk=rid)).contenu["appreciation"], "Bon mois")

    def test_famille_ne_voit_que_le_publie(self):
        activer(self.school, "suivi_pedagogique", "suivi_familles")
        rid = self.creer()
        url = f"/api/suivi/rapports/{rid}/"
        self.client.patch(url, {"contenu": {"appreciation": "Publié"}}, format="json")
        for u in (self.compte, self.parent):
            self.en(u)
            self.assertEqual(self.client.get(url).status_code, 404)
            self.assertEqual(self.client.get(url + "pdf/").status_code, 404)
        self.en(self.prof)
        self.client.post(url + "valider/")
        self.assertEqual(Notification.objects.count(), 0, "pas de notification avant la publication")
        self.client.post(url + "publier/")
        self.assertEqual(Notification.objects.count(), 2)
        self.client.post(url + "nouvelle_version/")
        self.client.patch(url, {"contenu": {"appreciation": "Brouillon secret"}}, format="json")
        self.en(self.parent)
        vue = self.client.get(url).data
        self.assertEqual(vue["contenu"]["appreciation"], "Publié")
        self.assertEqual(self.client.get(url + "pdf/").status_code, 200)
        self.assertEqual(self.client.post(url + "valider/").status_code, 403)

    def test_pas_de_notification_si_familles_fermees(self):
        rid = self.creer()
        url = f"/api/suivi/rapports/{rid}/"
        self.client.post(url + "valider/")
        self.client.post(url + "publier/")
        self.assertEqual(Notification.objects.count(), 0)

    def test_droits(self):
        self.en(self.prof)
        self.assertEqual(self.client.post("/api/suivi/rapports/", {**self.corps, "student": self.autre.pk}, format="json").status_code, 404)
        self.assertEqual(self.client.post("/api/suivi/rapports/", {"type": "x", "du": "2026-10-01", "au": "2026-10-31", "student": self.eleve.pk}, format="json").status_code, 400)
        self.assertEqual(self.client.post("/api/suivi/rapports/", {"du": "2026-11-01", "au": "2026-10-01", "student": self.eleve.pk}, format="json").status_code, 400)
        rid = self.creer()
        ailleurs = make_school(name="Ailleurs")
        activer(ailleurs, "suivi_pedagogique")
        self.en(make_user("a2@s.bj", "admin", ailleurs))
        self.assertEqual(self.client.get(f"/api/suivi/rapports/{rid}/").status_code, 404)

    def test_pdf_echappe_le_texte(self):
        contenu = rapports.pdf({"eleve": {"nom": "<b>A</b> & B"}, "periode": {}}, {"bilan": "<script>x</script> & y"})
        self.assertIn("<script>", "".join(p.get_text() for p in fitz.open(stream=contenu, filetype="pdf")))


class AlerteTests(Base):
    def evaluation(self, score, jour):
        EvaluationPedagogique.objects.create(student=self.eleve, titre="T", score_pourcent=score, date_evaluation=jour)

    def detecter(self):
        return alertes.detecter_eleve(self.eleve, alertes.regles(self.school))

    def test_baisse_sans_repetition(self):
        self.evaluation(80, date(2026, 9, 1))
        self.evaluation(60, date(2026, 10, 1))
        self.assertEqual(self.detecter(), 1)
        self.assertEqual(self.detecter(), 0)
        a = AlertePedagogique.objects.get()
        self.assertEqual((a.code, a.categorie, a.statut), ("baisse_resultats", "surveiller", "nouvelle"))
        self.assertEqual(a.donnees["apres"], 60.0)

    def test_hausse_et_seuil_reglable(self):
        self.evaluation(50, date(2026, 9, 1))
        self.evaluation(55, date(2026, 10, 1))
        self.assertEqual(self.detecter(), 0)
        RegleAlerte.objects.filter(school=self.school, code="progression_positive").update(seuil=5)
        self.assertEqual(self.detecter(), 1)

    def test_stagnation_absences_objectif(self):
        for j in (1, 2, 3):
            self.evaluer("en_progression", date(2026, 10, j))
        from django.utils import timezone
        for j in range(3):
            Attendance.objects.create(student=self.eleve, date=timezone.now().date() - timedelta(days=j), status="absent")
        Objectif.objects.create(school=self.school, student=self.eleve, titre="O", statut="atteint")
        self.assertEqual(self.detecter(), 3)
        self.assertEqual(set(AlertePedagogique.objects.values_list("code", flat=True)), {"stagnation", "absences", "objectif_atteint"})

    def test_regle_desactivee(self):
        RegleAlerte.objects.create(school=self.school, code="baisse_resultats", seuil=10, actif=False)
        self.evaluation(80, date(2026, 9, 1))
        self.evaluation(10, date(2026, 10, 1))
        self.assertEqual(self.detecter(), 0)

    def test_decision_humaine_et_droits(self):
        self.evaluation(80, date(2026, 9, 1))
        self.evaluation(60, date(2026, 10, 1))
        self.detecter()
        a = AlertePedagogique.objects.get()
        self.en(self.prof)
        url = f"/api/suivi/alertes/{a.pk}/decider/"
        self.assertEqual(self.client.post(url, {"decision": "x"}, format="json").status_code, 400)
        self.assertEqual(self.client.post(url, {"decision": "modifiee", "recommandation": "Autre", "note": "Vu"}, format="json").data["recommandation"], "Autre")
        self.assertEqual(self.client.post(url, {"decision": "refusee"}, format="json").status_code, 400)
        activer(self.school, "suivi_pedagogique", "suivi_familles")
        for u in (self.compte, self.parent):
            self.en(u)
            self.assertEqual(self.client.get("/api/suivi/alertes/").status_code, 403)
            self.assertEqual(self.client.post("/api/suivi/alertes/detecter/").status_code, 403)

    def test_seuils_reserves_a_l_administration(self):
        self.en(self.prof)
        self.assertEqual(self.client.patch("/api/suivi/alertes/regles/", {"code": "absences", "seuil": 9}, format="json").status_code, 403)
        self.en(self.admin)
        self.assertEqual(self.client.patch("/api/suivi/alertes/regles/", {"code": "absences", "seuil": 0}, format="json").status_code, 400)
        self.assertEqual(self.client.patch("/api/suivi/alertes/regles/", {"code": "absences", "seuil": 9}, format="json").status_code, 200)

    def test_aucune_notification_aux_familles(self):
        self.evaluation(80, date(2026, 9, 1))
        self.evaluation(10, date(2026, 10, 1))
        self.detecter()
        self.assertEqual(Notification.objects.count(), 0)
