"""Suivi pédagogique : système distinct des notes, droits par rôle et par académie, données réelles seulement."""
from datetime import date

from django.test import TestCase
from rest_framework.test import APIClient

from apps.attendance.models import Attendance
from apps.classes.models import Class
from apps.grades.models import Grade, GradeHistory
from apps.parents.models import Parent, ParentStudent
from apps.schools.models import Level, SchoolYear
from apps.students.models import Student
from apps.subjects.models import Subject
from apps.suivi import services
from apps.suivi.models import (
    Competence,
    EvaluationCompetence,
    EvaluationPedagogique,
    NiveauMaitrise,
    Objectif,
    ObjectifHistorique,
    ObservationParticipation,
    PlanAccompagnement,
    Referentiel,
)
from apps.teachers.models import Teacher, TeacherAssignment
from tests.test_virtualclass import make_school, make_user


def activer(school, *flags):
    school.settings = {**(school.settings or {}), "features": {f: True for f in flags}}
    school.save(update_fields=["settings"])


class Base(TestCase):
    def setUp(self):
        self.school = make_school()
        activer(self.school, "suivi_pedagogique")
        self.year = SchoolYear.objects.create(school=self.school, name="2026-2027", start_date="2026-09-01",
                                              end_date="2027-06-30", is_current=True)
        level = Level.objects.create(school=self.school, name="CM1", order=1, cycle="primaire")
        self.a = Class.objects.create(name="A", level=level, school_year=self.year)
        self.b = Class.objects.create(name="B", level=level, school_year=self.year)
        self.maths = Subject.objects.create(school=self.school, name="Maths", coefficient=1, level=level, language="fr")
        self.fr = Subject.objects.create(school=self.school, name="Français", coefficient=1, level=level, language="fr")
        self.a.subjects.set([self.maths, self.fr])
        self.prof = make_user("prof@s.bj", "teacher", self.school)
        self.teacher = Teacher.objects.create(user=self.prof)
        self.teacher.classes.set([self.a])
        self.teacher.subjects.set([self.maths, self.fr])
        TeacherAssignment.objects.create(teacher=self.teacher, class_obj=self.a, subject=self.maths)
        self.compte = make_user("el@s.bj", "student", self.school)
        self.eleve = Student.objects.create(user=self.compte, school=self.school, first_name="E", last_name="A", current_class=self.a)
        self.autre = Student.objects.create(user=make_user("el2@s.bj", "student", self.school), school=self.school,
                                            first_name="E", last_name="B", current_class=self.b)
        self.parent = make_user("pa@s.bj", "parent", self.school)
        ParentStudent.objects.create(parent=Parent.objects.create(user=self.parent), student=self.eleve, relationship="mother")
        self.admin = make_user("adm@s.bj", "admin", self.school)
        self.niveaux = {n.code: n for n in services.assurer_niveaux(self.school)}
        self.ref = Referentiel.objects.create(school=self.school, nom="Langue")
        self.comp = Competence.objects.create(referentiel=self.ref, nom="Compréhension", subject=self.maths)
        self.client = APIClient()

    def en(self, user):
        self.client.force_authenticate(user)

    def evaluer(self, code, jour, statut="validee"):
        return EvaluationCompetence.objects.create(student=self.eleve, competence=self.comp, niveau=self.niveaux[code],
                                                   date_evaluation=jour, statut=statut, evalue_par=self.prof)


class ActivationTests(Base):
    def test_desactive_par_defaut(self):
        autre = make_school(name="Sans suivi")
        self.assertFalse(autre.has_feature("suivi_pedagogique"))
        self.assertFalse(autre.has_feature("suivi_familles"))
        self.assertFalse(autre.has_feature("evaluations_en_ligne"))
        self.en(make_user("adm3@s.bj", "admin", autre))
        self.assertEqual(self.client.get("/api/suivi/eleves/").status_code, 403)

    def test_quatre_niveaux_par_defaut(self):
        self.assertEqual([n.libelle for n in NiveauMaitrise.objects.filter(school=self.school)],
                         ["À travailler", "À renforcer", "En progression", "Acquis"])

    def test_sans_authentification(self):
        self.assertEqual(self.client.get("/api/suivi/eleves/").status_code, 401)


class CompetencesTests(Base):
    def corps(self, **k):
        return {"student": self.eleve.pk, "competence": self.comp.pk, "niveau": self.niveaux["acquis"].pk,
                "date_evaluation": "2026-10-01", "commentaire": "Bien", **k}

    def test_enseignant_evalue_son_eleve_et_rien_n_est_ecrase(self):
        self.en(self.prof)
        for jour in ("2026-10-01", "2026-11-01"):
            self.assertEqual(self.client.post("/api/suivi/evaluations-competences/", self.corps(date_evaluation=jour), format="json").status_code, 201)
        self.assertEqual(EvaluationCompetence.objects.count(), 2)
        ligne = EvaluationCompetence.objects.first()
        url = f"/api/suivi/evaluations-competences/{ligne.pk}/"
        self.assertEqual(self.client.patch(url, {"commentaire": "x"}, format="json").status_code, 405)
        self.assertEqual(self.client.delete(url).status_code, 405)

    def test_matiere_non_affectee_refusee(self):
        comp = Competence.objects.create(referentiel=self.ref, nom="Écrit", subject=self.fr)
        self.en(self.prof)
        r = self.client.post("/api/suivi/evaluations-competences/", self.corps(competence=comp.pk), format="json")
        self.assertEqual(r.status_code, 403)

    def test_eleve_d_une_autre_classe_refuse(self):
        self.en(self.prof)
        r = self.client.post("/api/suivi/evaluations-competences/", self.corps(student=self.autre.pk), format="json")
        self.assertEqual(r.status_code, 403)

    def test_eleve_et_parent_n_ecrivent_pas(self):
        activer(self.school, "suivi_pedagogique", "suivi_familles")
        for u in (self.compte, self.parent):
            self.en(u)
            self.assertEqual(self.client.post("/api/suivi/evaluations-competences/", self.corps(), format="json").status_code, 403)
            self.assertEqual(self.client.post("/api/suivi/evaluations/", {"student": self.eleve.pk, "titre": "x", "score_pourcent": 10, "date_evaluation": "2026-10-01"}, format="json").status_code, 403)

    def test_decision_sur_une_proposition(self):
        p = self.evaluer("en_progression", date(2026, 10, 1), "proposee")
        self.assertFalse(services.etat_competences(self.eleve)["has_data"])
        self.en(self.prof)
        url = f"/api/suivi/evaluations-competences/{p.pk}/decider/"
        self.assertEqual(self.client.post(url, {"decision": "x"}, format="json").status_code, 400)
        self.assertEqual(self.client.post(url, {"decision": "validee", "niveau": self.niveaux["a_renforcer"].pk}, format="json").status_code, 200)
        self.assertEqual(services.etat_competences(self.eleve)["lignes"][0]["niveau"], "À renforcer")
        self.assertEqual(self.client.post(url, {"decision": "refusee"}, format="json").status_code, 400)

    def test_tendances(self):
        self.evaluer("a_travailler", date(2026, 9, 1))
        self.assertEqual(services.etat_competences(self.eleve)["lignes"][0]["tendance"], "premiere")
        self.evaluer("en_progression", date(2026, 10, 1))
        self.assertEqual(services.etat_competences(self.eleve)["lignes"][0]["tendance"], "progresse")
        self.evaluer("en_progression", date(2026, 10, 15))
        self.assertEqual(services.etat_competences(self.eleve)["lignes"][0]["tendance"], "stagne")
        self.evaluer("a_renforcer", date(2026, 11, 1))
        self.assertEqual(services.etat_competences(self.eleve)["lignes"][0]["tendance"], "regresse")
        self.evaluer("acquis", date(2026, 12, 1))
        ligne = services.etat_competences(self.eleve)["lignes"][0]
        self.assertTrue(ligne["acquis"] and ligne["nouvellement_acquis"])


class MetierTests(Base):
    def test_eleve_sans_historique(self):
        f = services.fiche(self.eleve)
        for section in ("progression", "assiduite", "participation", "competences", "evaluations", "objectifs", "resultats_historiques"):
            self.assertFalse(f[section]["has_data"], section)
        self.assertIsNone(f["progression"]["valeur"])
        self.assertIsNone(f["assiduite"]["taux"])

    def test_anciennes_notes_seules_ne_donnent_pas_de_progression(self):
        g = Grade.objects.create(student=self.eleve, subject=self.maths, school_year=self.year, period="T1", value=12)
        f = services.fiche(self.eleve)
        self.assertFalse(f["progression"]["has_data"])
        self.assertEqual(f["resultats_historiques"]["lignes"][0]["origine"], "notes_historiques")
        self.assertEqual(EvaluationPedagogique.objects.count(), 0)
        self.assertEqual(EvaluationCompetence.objects.count(), 0)
        g.refresh_from_db()
        self.assertEqual(g.value, 12)

    def test_le_suivi_n_ecrit_jamais_dans_les_notes(self):
        g = Grade.objects.create(student=self.eleve, subject=self.maths, school_year=self.year, period="T1", value=12)
        avant = Grade.calculate_average(self.eleve, self.year, "T1")
        self.evaluer("acquis", date(2026, 10, 1))
        EvaluationPedagogique.objects.create(student=self.eleve, titre="T", score_pourcent=10, date_evaluation=date(2026, 10, 1))
        services.fiche(self.eleve)
        self.assertEqual(Grade.objects.count(), 1)
        self.assertEqual(GradeHistory.objects.filter(grade=g).count(), 0)
        self.assertEqual(Grade.calculate_average(self.eleve, self.year, "T1"), avant)

    def test_calcul_de_la_progression_et_poids(self):
        self.evaluer("en_progression", date(2026, 10, 1))    # rang 3 sur 4 : 66,7
        EvaluationPedagogique.objects.create(student=self.eleve, titre="T", score_pourcent=50, date_evaluation=date(2026, 10, 1))
        p = services.progression(self.eleve)
        self.assertEqual(p["composantes"]["competences"], 66.7)
        self.assertEqual(p["valeur"], round((66.7 * 50 + 50 * 30) / 80, 1))
        Objectif.objects.create(school=self.school, student=self.eleve, titre="O", statut="atteint")
        self.assertEqual(services.progression(self.eleve)["composantes"]["objectifs"], 100.0)
        reglages = services.parametres(self.school)
        reglages.poids = {"competences": 0, "evaluations": 100, "objectifs": 0}
        reglages.save()
        self.assertEqual(services.progression(self.eleve)["valeur"], 50.0)

    def test_assiduite_lue_sans_inventer(self):
        for jour, st in ((1, "present"), (2, "late"), (3, "absent"), (4, "excused")):
            Attendance.objects.create(student=self.eleve, date=date(2026, 10, jour), status=st)
        a = services.assiduite(self.eleve)
        self.assertEqual((a["total"], a["absents"], a["taux"]), (4, 1, 50.0))

    def test_comparaison_de_periodes(self):
        EvaluationPedagogique.objects.create(student=self.eleve, titre="S", score_pourcent=45, date_evaluation=date(2026, 9, 15))
        EvaluationPedagogique.objects.create(student=self.eleve, titre="D", score_pourcent=78, date_evaluation=date(2026, 12, 15))
        r = services.comparer(self.eleve, (date(2026, 9, 1), date(2026, 9, 30)), (date(2026, 12, 1), date(2026, 12, 31)))
        self.assertEqual(r["ecart_evaluations"], 33.0)
        self.assertIsNone(r["note_moyenne_a"])
        r = services.comparer(self.eleve, (date(2026, 1, 1), date(2026, 1, 31)), (date(2026, 12, 1), date(2026, 12, 31)))
        self.assertIsNone(r["ecart_progression"])

    def test_participation_insuffisante(self):
        ObservationParticipation.objects.create(student=self.eleve, niveau=4, date_observation=date(2026, 10, 1))
        p = services.participation(self.eleve)
        self.assertTrue(p["has_data"])
        self.assertIsNone(p["moyenne"])


class DroitsLectureTests(Base):
    def test_famille_refusee_tant_que_non_ouvert(self):
        for u in (self.compte, self.parent):
            self.en(u)
            self.assertEqual(self.client.get(f"/api/suivi/eleves/{self.eleve.pk}/fiche/").status_code, 404)

    def test_famille_voit_seulement_le_valide(self):
        activer(self.school, "suivi_pedagogique", "suivi_familles")
        self.evaluer("acquis", date(2026, 10, 1), "proposee")
        PlanAccompagnement.objects.create(student=self.eleve, titre="Interne", debut=date(2026, 10, 1))
        ObservationParticipation.objects.create(student=self.eleve, niveau=4, date_observation=date(2026, 10, 1))
        for u in (self.compte, self.parent):
            self.en(u)
            f = self.client.get(f"/api/suivi/eleves/{self.eleve.pk}/fiche/").data
            self.assertFalse(f["competences"]["has_data"])
            self.assertEqual(f["plans_actifs"], 0)
            self.assertNotIn("participation", f)
            self.assertEqual(self.client.get("/api/suivi/evaluations-competences/").data["count"], 0)
            self.assertEqual(self.client.get("/api/suivi/plans/").data["count"], 0)
            self.assertEqual(self.client.get("/api/suivi/observations/").data["count"], 0)
            self.assertEqual(self.client.get(f"/api/suivi/eleves/{self.autre.pk}/fiche/").status_code, 404)

    def test_enseignant_limite_a_ses_classes(self):
        self.en(self.prof)
        self.assertEqual(self.client.get(f"/api/suivi/eleves/{self.eleve.pk}/fiche/").status_code, 200)
        self.assertEqual(self.client.get(f"/api/suivi/eleves/{self.autre.pk}/fiche/").status_code, 404)
        self.assertEqual({e["id"] for e in self.client.get("/api/suivi/eleves/").data["results"]}, {self.eleve.pk})

    def test_admin_voit_son_academie(self):
        self.en(self.admin)
        self.assertEqual(self.client.get("/api/suivi/eleves/").data["count"], 2)


class IsolationTests(Base):
    def setUp(self):
        super().setUp()
        self.ailleurs = make_school(name="Ailleurs")
        activer(self.ailleurs, "suivi_pedagogique")
        self.adm2 = make_user("adm2@s.bj", "admin", self.ailleurs)
        services.assurer_niveaux(self.ailleurs)

    def test_lecture_et_ecriture_refusees(self):
        self.evaluer("acquis", date(2026, 10, 1))
        self.en(self.adm2)
        self.assertEqual(self.client.get(f"/api/suivi/eleves/{self.eleve.pk}/fiche/").status_code, 404)
        self.assertEqual(self.client.get("/api/suivi/evaluations-competences/").data["count"], 0)
        self.assertEqual(self.client.get(f"/api/suivi/referentiels/{self.ref.pk}/").status_code, 404)
        n = NiveauMaitrise.objects.get(school=self.ailleurs, code="acquis")
        r = self.client.post("/api/suivi/evaluations-competences/", {"student": self.eleve.pk, "competence": self.comp.pk, "niveau": n.pk, "date_evaluation": "2026-10-01"}, format="json")
        self.assertEqual(r.status_code, 400)
        r = self.client.post("/api/suivi/objectifs/", {"student": self.eleve.pk, "titre": "x"}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_niveau_d_une_autre_academie_refuse(self):
        self.en(self.admin)
        n = NiveauMaitrise.objects.get(school=self.ailleurs, code="acquis")
        r = self.client.post("/api/suivi/evaluations-competences/", {"student": self.eleve.pk, "competence": self.comp.pk, "niveau": n.pk, "date_evaluation": "2026-10-01"}, format="json")
        self.assertEqual(r.status_code, 400)


class ObjectifsPlansTests(Base):
    def test_objectif_historique_et_actions(self):
        self.en(self.prof)
        r = self.client.post("/api/suivi/objectifs/", {"student": self.eleve.pk, "titre": "Lire", "subject": self.maths.pk}, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        url = f"/api/suivi/objectifs/{r.data['id']}/"
        self.assertEqual(self.client.patch(url, {"statut": "atteint", "note": "Réussi"}, format="json").status_code, 200)
        self.assertEqual(list(ObjectifHistorique.objects.values_list("nouveau_statut", flat=True)), ["atteint", "a_commencer"])
        self.assertEqual(self.client.post("/api/suivi/actions/", {"objectif": r.data["id"], "description": "Exercices"}, format="json").status_code, 201)
        self.assertEqual(self.client.delete(url).status_code, 405)

    def test_objectif_vise_un_eleve_ou_une_classe(self):
        self.en(self.admin)
        self.assertEqual(self.client.post("/api/suivi/objectifs/", {"titre": "x"}, format="json").status_code, 400)
        self.assertEqual(self.client.post("/api/suivi/objectifs/", {"titre": "x", "student": self.eleve.pk, "class_obj": self.a.pk}, format="json").status_code, 400)

    def test_objectif_collectif_limite_aux_classes_de_l_enseignant(self):
        self.en(self.prof)
        self.assertEqual(self.client.post("/api/suivi/objectifs/", {"titre": "x", "class_obj": self.a.pk}, format="json").status_code, 201)
        self.assertEqual(self.client.post("/api/suivi/objectifs/", {"titre": "x", "class_obj": self.b.pk}, format="json").status_code, 403)

    def test_plan_et_action(self):
        self.en(self.prof)
        r = self.client.post("/api/suivi/plans/", {"student": self.eleve.pk, "titre": "Soutien", "debut": "2026-10-01"}, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        a = self.client.post("/api/suivi/actions/", {"plan": r.data["id"], "description": "Séance", "type": "soutien"}, format="json")
        self.assertEqual(a.status_code, 201)
        self.assertEqual(self.client.patch(f"/api/suivi/actions/{a.data['id']}/", {"realisee_le": "2026-10-10", "resultat": "Mieux"}, format="json").status_code, 200)
        self.assertEqual(self.client.post("/api/suivi/plans/", {"student": self.autre.pk, "titre": "x", "debut": "2026-10-01"}, format="json").status_code, 403)

    def test_action_sans_rattachement_refusee(self):
        self.en(self.admin)
        self.assertEqual(self.client.post("/api/suivi/actions/", {"description": "x"}, format="json").status_code, 400)


class ReglagesTests(Base):
    def test_seule_l_administration_regle(self):
        self.en(self.prof)
        self.assertEqual(self.client.patch("/api/suivi/parametres/modifier/", {"poids": {"competences": 10}}, format="json").status_code, 403)
        n = self.niveaux["acquis"]
        self.assertEqual(self.client.patch(f"/api/suivi/niveaux/{n.pk}/", {"libelle": "x"}, format="json").status_code, 403)
        self.en(self.admin)
        self.assertEqual(self.client.patch("/api/suivi/parametres/modifier/", {"poids": {"competences": 10}}, format="json").status_code, 200)
        self.assertEqual(self.client.patch("/api/suivi/parametres/modifier/", {"poids": {"x": 10}}, format="json").status_code, 400)
        self.assertEqual(self.client.patch(f"/api/suivi/niveaux/{n.pk}/", {"libelle": "Maîtrisé", "rang": 1}, format="json").status_code, 200)
        n.refresh_from_db()
        self.assertEqual((n.libelle, n.rang), ("Maîtrisé", 4))

    def test_dates_invalides(self):
        self.en(self.admin)
        self.assertEqual(self.client.get(f"/api/suivi/eleves/{self.eleve.pk}/fiche/?du=hier").status_code, 400)
        self.assertEqual(self.client.get(f"/api/suivi/eleves/{self.eleve.pk}/comparer/?a_du=2026-01-01").status_code, 400)

    def test_compte_reference_inconnue_n_echoue_pas(self):
        self.en(self.admin)
        self.assertEqual(self.client.get("/api/suivi/eleves/abc/fiche/").status_code, 404)


class ActivationTests2(Base):
    def test_seul_le_superadmin_active(self):
        url = f"/api/suivi/activation/{self.school.pk}/"
        for u in (self.admin, self.prof, self.compte, self.parent):
            self.en(u)
            self.assertEqual(self.client.patch(url, {"suivi_familles": True}, format="json").status_code, 403)
        self.school.refresh_from_db()
        self.assertFalse(self.school.has_feature("suivi_familles"))
        self.en(make_user("su@s.bj", "superadmin", None))
        self.assertEqual(self.client.patch(url, {"suivi_familles": "oui"}, format="json").status_code, 400)
        self.assertEqual(self.client.patch(url, {"autre": True}, format="json").status_code, 400)
        self.assertTrue(self.client.patch(url, {"suivi_familles": True}, format="json").data["suivi_familles"])
        self.school.refresh_from_db()
        self.assertTrue(self.school.has_feature("suivi_familles"))
        self.assertTrue(self.school.has_feature("suivi_pedagogique"), "les autres réglages restent")
