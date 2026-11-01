"""Examens en ligne : passage côté serveur, correction, tentatives, transfert unique vers les notes."""
import json
from datetime import timedelta
from decimal import Decimal

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.classes.models import Class
from apps.evaluations import correction, services
from apps.evaluations.models import Amenagement, Epreuve, EpreuveQuestion, EvenementTentative, Question, Reponse, Tentative, TransfertNote
from apps.grades.models import Grade, GradeHistory
from apps.parents.models import Parent, ParentStudent
from apps.schools.models import Level, SchoolYear
from apps.students.models import Student
from apps.subjects.models import Subject
from apps.suivi.models import Competence, EvaluationCompetence, Referentiel
from apps.teachers.models import Teacher, TeacherAssignment
from tests.test_suivi import activer
from tests.test_virtualclass import make_school, make_user


class CorrectionTests(SimpleTestCase):
    def f(self, t, c, v):
        return correction.fraction(t, c, v)

    def test_objectifs(self):
        self.assertEqual(self.f("qcm_unique", {"bonne": "a"}, "a"), 1)
        self.assertEqual(self.f("qcm_unique", {"bonne": "a"}, "b"), 0)
        self.assertEqual(self.f("vrai_faux", {"valeur": True}, True), 1)
        self.assertEqual(self.f("vrai_faux", {"valeur": True}, "true"), 0)
        self.assertEqual(self.f("courte", {"acceptees": ["Paris"]}, "  paris "), 1)
        self.assertEqual(self.f("courte", {"acceptees": ["Paris"], "casse": True}, "paris"), 0)
        self.assertEqual(self.f("numerique", {"valeur": 3.14, "tolerance": 0.01}, "3,15"), 1)
        self.assertEqual(self.f("numerique", {"valeur": 3.14, "tolerance": 0.01}, "3.2"), 0)

    def test_points_partiels(self):
        self.assertEqual(self.f("qcm_multiple", {"bonnes": ["a", "b"]}, ["a"]), Decimal("0.5"))
        self.assertEqual(self.f("qcm_multiple", {"bonnes": ["a", "b"]}, ["a", "c"]), 0)
        self.assertEqual(self.f("trous", {"reponses": [["x"], ["y"]]}, ["x", "z"]), Decimal("0.5"))
        self.assertEqual(self.f("association", {"paires": {"1": "a", "2": "b"}}, {"1": "a", "2": "a"}), Decimal("0.5"))
        self.assertEqual(self.f("classement", {"ordre": ["a", "b"]}, ["a", "b"]), 1)

    def test_manuel_et_valeurs_hostiles(self):
        self.assertIsNone(self.f("ouverte", {}, "texte"))
        self.assertIsNone(self.f("fichier", {}, None))
        self.assertEqual(self.f("qcm_multiple", {"bonnes": ["a"]}, "a"), 0)
        self.assertEqual(self.f("numerique", {"valeur": 1}, {"x": 1}), 0)
        self.assertEqual(self.f("association", {"paires": {"1": "a"}}, [1]), 0)
        self.assertEqual(self.f("courte", {"acceptees": ["a"]}, 12), 0)


class Base(TestCase):
    def setUp(self):
        self.school = make_school()
        activer(self.school, "evaluations_en_ligne", "suivi_pedagogique")
        self.year = SchoolYear.objects.create(school=self.school, name="2026-2027", start_date="2026-09-01", end_date="2027-06-30", is_current=True)
        level = Level.objects.create(school=self.school, name="CM1", order=1, cycle="primaire")
        self.cl = Class.objects.create(name="A", level=level, school_year=self.year)
        self.autre_cl = Class.objects.create(name="B", level=level, school_year=self.year)
        self.maths = Subject.objects.create(school=self.school, name="Maths", coefficient=1, level=level, language="fr")
        self.fr = Subject.objects.create(school=self.school, name="Français", coefficient=1, level=level, language="fr")
        self.cl.subjects.set([self.maths, self.fr])
        self.prof = make_user("prof@e.bj", "teacher", self.school)
        self.teacher = Teacher.objects.create(user=self.prof)
        self.teacher.classes.set([self.cl])
        self.teacher.subjects.set([self.maths, self.fr])
        TeacherAssignment.objects.create(teacher=self.teacher, class_obj=self.cl, subject=self.maths)
        self.compte = make_user("el@e.bj", "student", self.school)
        self.eleve = Student.objects.create(user=self.compte, school=self.school, first_name="E", last_name="A", current_class=self.cl)
        self.compte2 = make_user("el2@e.bj", "student", self.school)
        self.eleve2 = Student.objects.create(user=self.compte2, school=self.school, first_name="E", last_name="B", current_class=self.autre_cl)
        self.admin = make_user("adm@e.bj", "admin", self.school)
        self.client = APIClient()
        self.q1 = self.question("qcm_unique", "2+2 ?", {"choix": [{"id": "a", "texte": "4"}, {"id": "b", "texte": "5"}]}, {"bonne": "a"}, 2)
        self.q2 = self.question("ouverte", "Expliquez", {}, {}, 3)
        self.epreuve = self.nouvelle()

    def question(self, type_q, enonce, contenu, corrige, points=1, **k):
        q = Question.objects.create(school=self.school, auteur=self.prof, subject=self.maths, type=type_q, **k)
        services.creer_version(q, {"enonce": enonce, "contenu": contenu, "corrige": corrige, "points": points, "explication": "SECRET-EXPLICATION", "criteres": "SECRET-CRITERE"}, self.prof)
        return q

    def nouvelle(self, questions=None, **k):
        m = timezone.now()
        d = dict(school=self.school, titre="Contrôle", subject=self.maths, class_obj=self.cl, school_year=self.year, periode="T1",
                 responsable=self.prof, ouverture=m - timedelta(hours=1), fermeture=m + timedelta(hours=1), duree_minutes=30,
                 statut=Epreuve.PUBLIEE, produit_note=True, politique="derniere", tentatives_max=2)
        d.update(k)
        e = Epreuve.objects.create(**d)
        for i, q in enumerate(questions if questions is not None else [self.q1, self.q2]):
            v = q.version_courante
            EpreuveQuestion.objects.create(epreuve=e, version=v, ordre=i, points=v.points)
        return e

    def en(self, u):
        self.client.force_authenticate(u)

    def demarrer(self, e=None):
        self.en(self.compte)
        r = self.client.post(f"/api/evaluations/passage/{(e or self.epreuve).pk}/demarrer/")
        self.assertEqual(r.status_code, 200, r.data)
        return r.data

    def repondre(self, d, version, valeur):
        return self.client.post(f"/api/evaluations/passage/{d['id']}/repondre/", {"version": version, "valeur": valeur, "jeton": d["jeton"]}, format="json")

    def passer_et_valider(self, bonne=True, texte=12):
        d = self.demarrer()
        v1, v2 = self.q1.version_courante.pk, self.q2.version_courante.pk
        self.repondre(d, v1, "a" if bonne else "b")
        self.repondre(d, v2, "ma réponse")
        self.client.post(f"/api/evaluations/passage/{d['id']}/remettre/")
        t = Tentative.objects.get(pk=d["id"])
        self.en(self.prof)
        r = t.reponses.get(version_id=v2)
        self.assertEqual(self.client.post(f"/api/evaluations/copies/{t.pk}/corriger/", {"reponse": r.pk, "points": "3"}, format="json").status_code, 200)
        self.assertEqual(self.client.post(f"/api/evaluations/copies/{t.pk}/valider/").status_code, 200)
        return Tentative.objects.get(pk=t.pk)


class PassageTests(Base):
    def test_le_corrige_ne_part_jamais_vers_l_eleve(self):
        d = self.demarrer()
        texte = json.dumps(d, default=str)
        for secret in ("corrige", "bonne", "SECRET-EXPLICATION", "SECRET-CRITERE"):
            self.assertNotIn(secret, texte)
        self.assertEqual(self.client.get("/api/evaluations/questions/").status_code, 403)
        self.assertEqual(self.client.get(f"/api/evaluations/epreuves/{self.epreuve.pk}/").status_code, 403)
        self.assertEqual(self.client.get(f"/api/evaluations/copies/{d['id']}/").status_code, 403)

    def test_demarrer_deux_fois_reprend_la_meme_tentative_et_le_meme_sujet(self):
        a = self.demarrer()
        self.repondre(a, self.q1.version_courante.pk, "a")
        b = self.demarrer()
        self.assertEqual(a["id"], b["id"])
        self.assertEqual([q["version"] for q in a["questions"]], [q["version"] for q in b["questions"]])
        self.assertEqual(next(q for q in b["questions"] if q["type"] == "qcm_unique")["valeur"], "a")
        self.assertEqual(Tentative.objects.count(), 1)
        self.assertTrue(EvenementTentative.objects.filter(type="reprise").exists())

    def test_ordre_reproductible_et_propre_a_la_graine(self):
        self.assertEqual(services._sujet(self.epreuve, 7), services._sujet(self.epreuve, 7))

    def test_sauvegarde_idempotente_et_question_hors_sujet(self):
        d = self.demarrer()
        v = self.q1.version_courante.pk
        self.assertEqual(self.repondre(d, v, "a").status_code, 200)
        self.assertEqual(self.repondre(d, v, "b").status_code, 200)
        self.assertEqual(Reponse.objects.get().valeur, "b")
        autre = self.question("qcm_unique", "x", {"choix": [{"id": "a", "texte": "1"}, {"id": "b", "texte": "2"}]}, {"bonne": "a"})
        self.assertEqual(self.repondre(d, autre.version_courante.pk, "a").status_code, 400)

    def test_chronometre_serveur_et_remise_automatique(self):
        d = self.demarrer()
        Tentative.objects.filter(pk=d["id"]).update(echeance=timezone.now() - timedelta(seconds=1))
        r = self.repondre(d, self.q1.version_courante.pk, "a")
        self.assertEqual(r.status_code, 400)
        t = Tentative.objects.get(pk=d["id"])
        self.assertEqual((t.statut, t.mode_remise), (Tentative.REMISE, "auto"))
        self.assertFalse(Reponse.objects.filter(tentative=t, valeur="a").exists())

    def test_tache_de_cloture(self):
        d = self.demarrer()
        Tentative.objects.filter(pk=d["id"]).update(echeance=timezone.now() - timedelta(seconds=1))
        self.assertEqual(services.cloturer_echues(), 1)
        self.assertEqual(services.cloturer_echues(), 0)

    def test_double_remise(self):
        d = self.demarrer()
        url = f"/api/evaluations/passage/{d['id']}/remettre/"
        a, b = self.client.post(url), self.client.post(url)
        self.assertEqual((a.status_code, b.status_code), (200, 200))
        self.assertEqual(a.data["recu"], b.data["recu"])
        self.assertEqual(EvenementTentative.objects.filter(type="remise").count(), 1)

    def test_limite_de_tentatives_et_conservation(self):
        for _ in range(2):
            d = self.demarrer()
            self.client.post(f"/api/evaluations/passage/{d['id']}/remettre/")
        self.assertEqual(self.client.post(f"/api/evaluations/passage/{self.epreuve.pk}/demarrer/").status_code, 403)
        self.assertEqual(Tentative.objects.count(), 2)

    def test_amenagement(self):
        Amenagement.objects.create(epreuve=self.epreuve, student=self.eleve, minutes_sup=20, tentatives_sup=1)
        d = self.demarrer()
        self.assertGreater(d["secondes_restantes"], 49 * 60)

    def test_hors_horaires_et_autre_classe(self):
        m = timezone.now()
        e = self.nouvelle(ouverture=m + timedelta(hours=1), fermeture=m + timedelta(hours=2))
        self.en(self.compte)
        self.assertEqual(self.client.post(f"/api/evaluations/passage/{e.pk}/demarrer/").status_code, 403)
        self.en(self.compte2)
        self.assertEqual(self.client.post(f"/api/evaluations/passage/{self.epreuve.pk}/demarrer/").status_code, 404)

    def test_brouillon_invisible(self):
        e = self.nouvelle(statut=Epreuve.BROUILLON)
        self.en(self.compte)
        self.assertNotIn(e.pk, [x["id"] for x in self.client.get("/api/evaluations/passage/").data])

    def test_tentative_d_un_autre_eleve(self):
        d = self.demarrer()
        self.en(self.compte2)
        self.assertEqual(self.client.get(f"/api/evaluations/passage/{d['id']}/tentative/").status_code, 404)
        self.assertEqual(self.client.post(f"/api/evaluations/passage/{d['id']}/remettre/").status_code, 404)

    def test_evenement_signale_sans_sanction(self):
        d = self.demarrer()
        self.assertEqual(self.client.post(f"/api/evaluations/passage/{d['id']}/evenement/", {"type": "sortie_fenetre"}, format="json").status_code, 204)
        self.assertEqual(self.client.post(f"/api/evaluations/passage/{d['id']}/evenement/", {"type": "x"}, format="json").status_code, 400)
        self.assertEqual(Tentative.objects.get(pk=d["id"]).statut, Tentative.EN_COURS)

    def test_session_concurrente_journalisee(self):
        d = self.demarrer()
        self.demarrer()
        self.repondre(d, self.q1.version_courante.pk, "a")
        self.assertTrue(EvenementTentative.objects.filter(type="session_concurrente").exists())

    def test_version_figee(self):
        d = self.demarrer()
        services.creer_version(self.q1, {"enonce": "Autre", "corrige": {"bonne": "b"}, "contenu": self.q1.version_courante.contenu}, self.prof)
        again = self.client.get(f"/api/evaluations/passage/{d['id']}/tentative/").data
        self.assertIn("2+2 ?", [q["enonce"] for q in again["questions"]])

    def test_tirage_depuis_la_banque(self):
        for i in range(3):
            self.question("qcm_unique", f"Q{i}", {"choix": [{"id": "a", "texte": "1"}, {"id": "b", "texte": "2"}]}, {"bonne": "a"}, difficulte=3)
        e = self.nouvelle(questions=[], regles_tirage=[{"difficulte": 3, "nombre": 2, "points": 1}])
        d = self.demarrer(e)
        self.assertEqual(len(d["questions"]), 2)
        self.assertEqual(Tentative.objects.get(pk=d["id"]).total_points, 2)


class CorrectionApiTests(Base):
    def test_auto_puis_manuel_et_scores_separes(self):
        d = self.demarrer()
        self.repondre(d, self.q1.version_courante.pk, "a")
        self.client.post(f"/api/evaluations/passage/{d['id']}/remettre/")
        t = Tentative.objects.get(pk=d["id"])
        self.assertEqual((t.statut, t.score_brut, t.score_corrige, t.note_echelle), (Tentative.REMISE, 2, None, None))
        self.en(self.prof)
        r = t.reponses.get(version=self.q2.version_courante)
        self.assertIsNone(r.points_auto)
        self.assertEqual(self.client.post(f"/api/evaluations/copies/{t.pk}/valider/").status_code, 400)
        self.assertEqual(self.client.post(f"/api/evaluations/copies/{t.pk}/corriger/", {"reponse": r.pk, "points": "9"}, format="json").status_code, 400)
        self.assertEqual(self.client.post(f"/api/evaluations/copies/{t.pk}/corriger/", {"reponse": r.pk, "points": "1.5", "commentaire": "Partiel"}, format="json").status_code, 200)
        self.assertEqual(self.client.post(f"/api/evaluations/copies/{t.pk}/valider/").status_code, 200)
        t.refresh_from_db()
        self.assertEqual((t.score_brut, t.score_corrige, t.score_valide, t.pourcentage, t.note_echelle), (2, Decimal("3.5"), Decimal("3.5"), Decimal("70.00"), Decimal("14.00")))
        self.assertTrue(t.reussie)
        self.assertEqual(r.historique.count(), 1)

    def test_resultat_invisible_avant_publication(self):
        t = self.passer_et_valider()
        self.en(self.compte)
        self.assertEqual(self.client.get(f"/api/evaluations/passage/{t.pk}/resultat/").status_code, 403)
        self.assertEqual(self.client.get("/api/evaluations/passage/resultats/").data, [])
        self.en(self.prof)
        self.client.post(f"/api/evaluations/epreuves/{self.epreuve.pk}/publier_resultats/")
        self.en(self.compte)
        self.assertEqual(self.client.get(f"/api/evaluations/passage/{t.pk}/resultat/").data["note"], Decimal("20.00"))

    def test_parent_soumis_au_drapeau_famille(self):
        t = self.passer_et_valider()
        Epreuve.objects.filter(pk=self.epreuve.pk).update(resultats_publies=True)
        parent = make_user("pa@e.bj", "parent", self.school)
        ParentStudent.objects.create(parent=Parent.objects.create(user=parent), student=self.eleve, relationship="mother")
        self.en(parent)
        self.assertEqual(self.client.get("/api/evaluations/passage/resultats/").status_code, 403)
        activer(self.school, "evaluations_en_ligne", "suivi_pedagogique", "suivi_familles")
        self.assertEqual(self.client.get("/api/evaluations/passage/resultats/").data[0]["id"], t.pk)

    def test_enseignant_non_affecte(self):
        d = self.demarrer()
        self.client.post(f"/api/evaluations/passage/{d['id']}/remettre/")
        TeacherAssignment.objects.all().delete()
        self.en(self.prof)
        t = Tentative.objects.get(pk=d["id"])
        r = t.reponses.first()
        self.assertEqual(self.client.post(f"/api/evaluations/copies/{t.pk}/corriger/", {"reponse": r.pk, "points": "1"}, format="json").status_code, 403)

    def test_statistiques_reelles(self):
        self.passer_et_valider()
        self.en(self.prof)
        s = self.client.get(f"/api/evaluations/epreuves/{self.epreuve.pk}/statistiques/").data
        self.assertEqual((s["participants"], s["moyenne"], s["mediane"], s["taux_reussite"]), (1, 100.0, 100.0, 100.0))
        self.assertEqual(s["inscrits"], 1)


class TransfertTests(Base):
    def test_transfert_unique_et_notes_intactes(self):
        existante = Grade.objects.create(student=self.eleve, subject=self.maths, school_year=self.year, period="T1", value=10)
        self.assertEqual(Grade.objects.count(), 1)
        t = self.passer_et_valider()
        self.assertEqual(Grade.objects.count(), 1, "aucune note avant le transfert explicite")
        self.en(self.prof)
        url = f"/api/evaluations/epreuves/{self.epreuve.pk}/transferer/"
        a = self.client.post(url, {}, format="json")
        self.assertEqual((a.data["crees"], a.data["erreurs"]), (1, []))
        b = self.client.post(url, {}, format="json")
        self.assertEqual((b.data["crees"], b.data["deja_transferes"]), (0, 1))
        self.assertEqual(Grade.objects.count(), 2)
        transfert = TransfertNote.objects.get()
        self.assertEqual((transfert.tentative_id, transfert.grade.value, transfert.grade.note_coefficient), (t.pk, Decimal("20.00"), 1))
        self.assertEqual(GradeHistory.objects.filter(grade=transfert.grade).count(), 1)
        existante.refresh_from_db()
        self.assertEqual(existante.value, 10)
        t.refresh_from_db()
        self.assertEqual(t.score_valide, Decimal("5.00"))
        self.assertEqual(Grade.calculate_average(self.eleve, self.year, "T1"), Decimal("15.00"))

    def test_note_sur_20_quelle_que_soit_l_echelle(self):
        Epreuve.objects.filter(pk=self.epreuve.pk).update(note_max=100)
        self.epreuve.refresh_from_db()
        t = self.passer_et_valider(bonne=False)
        self.assertEqual(t.note_echelle, Decimal("60.00"))
        self.en(self.admin)
        self.client.post(f"/api/evaluations/epreuves/{self.epreuve.pk}/transferer/", {}, format="json")
        self.assertEqual(TransfertNote.objects.get().grade.value, Decimal("12.00"))

    def test_quiz_ne_produit_pas_de_note(self):
        Epreuve.objects.filter(pk=self.epreuve.pk).update(produit_note=False)
        self.passer_et_valider()
        self.en(self.prof)
        r = self.client.post(f"/api/evaluations/epreuves/{self.epreuve.pk}/transferer/", {}, format="json")
        self.assertEqual(r.data["crees"], 0)
        self.assertEqual(Grade.objects.count(), 0)

    def test_non_validee_ne_transfere_pas(self):
        d = self.demarrer()
        self.client.post(f"/api/evaluations/passage/{d['id']}/remettre/")
        self.en(self.prof)
        self.assertEqual(self.client.post(f"/api/evaluations/epreuves/{self.epreuve.pk}/transferer/", {}, format="json").data["crees"], 0)
        self.assertEqual(Grade.objects.count(), 0)

    def test_correction_refusee_apres_transfert(self):
        t = self.passer_et_valider()
        self.en(self.prof)
        self.client.post(f"/api/evaluations/epreuves/{self.epreuve.pk}/transferer/", {}, format="json")
        r = t.reponses.first()
        self.assertEqual(self.client.post(f"/api/evaluations/copies/{t.pk}/corriger/", {"reponse": r.pk, "points": "1"}, format="json").status_code, 400)

    def test_politiques(self):
        self.epreuve.politique = "meilleure"
        self.epreuve.save()
        a = self.passer_et_valider(bonne=True)
        b = self.passer_et_valider(bonne=False)
        self.assertEqual(services.tentative_retenue(self.epreuve, self.eleve), a)
        for politique, attendue in (("derniere", b), ("premiere", a)):
            self.epreuve.politique = politique
            self.assertEqual(services.tentative_retenue(self.epreuve, self.eleve), attendue)
        self.epreuve.politique = "validee"
        self.assertIsNone(services.tentative_retenue(self.epreuve, self.eleve))
        self.en(self.prof)
        self.client.post(f"/api/evaluations/copies/{b.pk}/choisir/")
        self.assertEqual(services.tentative_retenue(self.epreuve, self.eleve), b)


class SuiviTests(Base):
    def test_proposition_plafonnee_jamais_acquis(self):
        ref = Referentiel.objects.create(school=self.school, nom="R")
        comp = Competence.objects.create(referentiel=ref, nom="C")
        self.q1.competences.add(comp)
        self.q2.competences.add(comp)
        t = self.passer_et_valider()
        self.assertEqual(t.pourcentage, 100)
        ligne = EvaluationCompetence.objects.get()
        self.assertEqual((ligne.statut, ligne.source, ligne.niveau.code), ("proposee", "examen", "en_progression"))
        self.assertEqual(services.proposer_competences(t), 0)
        self.assertEqual(EvaluationCompetence.objects.count(), 1)

    def test_sans_module_suivi_pas_de_proposition(self):
        activer(self.school, "evaluations_en_ligne")
        ref = Referentiel.objects.create(school=self.school, nom="R")
        self.q1.competences.add(Competence.objects.create(referentiel=ref, nom="C"))
        self.passer_et_valider()
        self.assertEqual(EvaluationCompetence.objects.count(), 0)

    def test_fiche_distingue_l_origine(self):
        from apps.suivi.services import fiche
        self.passer_et_valider()
        f = fiche(self.eleve)
        self.assertEqual(f["resultats_examens"]["lignes"][0]["origine"], "examens_en_ligne")
        self.assertFalse(f["resultats_historiques"]["has_data"])
        self.assertFalse(fiche(self.eleve, famille=True)["resultats_examens"]["has_data"])


class BanqueTests(Base):
    def corps(self, **k):
        return {"type": "qcm_unique", "enonce": "Q", "subject": self.maths.pk, "contenu": {"choix": [{"id": "a", "texte": "1"}, {"id": "b", "texte": "2"}]}, "corrige": {"bonne": "a"}, **k}

    def test_creation_version_et_validation(self):
        self.en(self.prof)
        r = self.client.post("/api/evaluations/questions/", self.corps(), format="json")
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(self.client.post("/api/evaluations/questions/", self.corps(corrige={"bonne": "z"}), format="json").status_code, 400)
        url = f"/api/evaluations/questions/{r.data['id']}/"
        self.assertEqual(self.client.patch(url, {"enonce": "Q2"}, format="json").status_code, 200)
        q = Question.objects.get(pk=r.data["id"])
        self.assertEqual(q.versions.count(), 2)
        self.assertEqual(q.version_courante.corrige, {"bonne": "a"})

    def test_question_privee(self):
        q = self.question("ouverte", "P", {}, {}, prive=True)
        q.auteur = self.admin
        q.save()
        self.en(self.prof)
        self.assertEqual(self.client.get(f"/api/evaluations/questions/{q.pk}/").status_code, 404)
        r = self.client.post(f"/api/evaluations/epreuves/{self.epreuve.pk}/ajouter_question/", {"question": q.pk}, format="json")
        self.assertIn(r.status_code, (400, 404))

    def test_seul_l_auteur_modifie(self):
        self.en(make_user("p2@e.bj", "teacher", self.school))
        self.assertEqual(self.client.patch(f"/api/evaluations/questions/{self.q1.pk}/", {"enonce": "x"}, format="json").status_code, 403)

    def test_import_tout_ou_rien_et_export_sur(self):
        self.en(self.prof)
        n = Question.objects.count()
        csv_ok = "type,enonce,points,difficulte,choix,bonnes\nqcm_unique,=2+2,1,1,4|5,4\nvrai_faux,Vrai ?,1,1,,vrai\n"
        mauvais = csv_ok + "qcm_unique,X,1,1,4|5,9\n"
        f = SimpleUploadedFile("q.csv", mauvais.encode())
        self.assertEqual(self.client.post("/api/evaluations/questions/importer/", {"fichier": f}, format="multipart").status_code, 400)
        self.assertEqual(Question.objects.count(), n)
        f = SimpleUploadedFile("q.csv", csv_ok.encode())
        self.assertEqual(self.client.post("/api/evaluations/questions/importer/", {"fichier": f}, format="multipart").data["importees"], 2)
        contenu = self.client.get("/api/evaluations/questions/exporter/").content.decode()
        self.assertIn("'=2+2", contenu)

    def test_archive_et_duplication(self):
        self.en(self.prof)
        self.client.post(f"/api/evaluations/questions/{self.q1.pk}/archiver/", {}, format="json")
        self.q1.refresh_from_db()
        self.assertTrue(self.q1.archive)
        r = self.client.post(f"/api/evaluations/questions/{self.q1.pk}/dupliquer/", {}, format="json")
        self.assertEqual(r.status_code, 201)
        self.assertEqual(Question.objects.get(pk=r.data["id"]).version_courante.enonce, "2+2 ?")


class EpreuveDroitsTests(Base):
    def corps(self, **k):
        m = timezone.now()
        return {"titre": "T", "type": "examen", "subject": self.maths.pk, "class_obj": self.cl.pk, "ouverture": m.isoformat(),
                "fermeture": (m + timedelta(hours=1)).isoformat(), "duree_minutes": 20, **k}

    def test_enseignant_affecte_seulement(self):
        self.en(self.prof)
        r = self.client.post("/api/evaluations/epreuves/", self.corps(), format="json")
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data["politique"], "derniere")
        self.assertEqual(self.client.post("/api/evaluations/epreuves/", self.corps(subject=self.fr.pk), format="json").status_code, 403)
        self.assertEqual(self.client.post("/api/evaluations/epreuves/", self.corps(class_obj=self.autre_cl.pk), format="json").status_code, 403)

    def test_dates_incoherentes(self):
        self.en(self.admin)
        m = timezone.now()
        self.assertEqual(self.client.post("/api/evaluations/epreuves/", self.corps(fermeture=(m - timedelta(hours=1)).isoformat()), format="json").status_code, 400)

    def test_publiee_figee_et_publication_vide_refusee(self):
        self.en(self.prof)
        self.assertEqual(self.client.patch(f"/api/evaluations/epreuves/{self.epreuve.pk}/", {"titre": "x"}, format="json").status_code, 400)
        self.assertEqual(self.client.delete(f"/api/evaluations/epreuves/{self.epreuve.pk}/").status_code, 400)
        vide = self.nouvelle(questions=[], statut=Epreuve.BROUILLON)
        self.assertEqual(self.client.post(f"/api/evaluations/epreuves/{vide.pk}/publier/").status_code, 400)
        self.client.post(f"/api/evaluations/epreuves/{vide.pk}/ajouter_question/", {"question": self.q1.pk}, format="json")
        self.assertEqual(self.client.post(f"/api/evaluations/epreuves/{vide.pk}/publier/").status_code, 200)

    def test_autre_academie(self):
        ailleurs = make_school(name="Ailleurs")
        activer(ailleurs, "evaluations_en_ligne")
        adm = make_user("adm2@e.bj", "admin", ailleurs)
        self.en(adm)
        self.assertEqual(self.client.get(f"/api/evaluations/epreuves/{self.epreuve.pk}/").status_code, 404)
        self.assertEqual(self.client.get(f"/api/evaluations/questions/{self.q1.pk}/").status_code, 404)
        d = self.demarrer()
        self.en(adm)
        self.assertEqual(self.client.get(f"/api/evaluations/copies/{d['id']}/").status_code, 404)
        self.assertEqual(self.client.post("/api/evaluations/epreuves/", self.corps(), format="json").status_code, 400)

    def test_module_desactive(self):
        activer(self.school, "suivi_pedagogique")
        self.en(self.admin)
        self.assertEqual(self.client.get("/api/evaluations/epreuves/").status_code, 403)
        self.en(self.compte)
        self.assertEqual(self.client.get("/api/evaluations/passage/").status_code, 403)

    def test_clore_remet_les_tentatives_en_cours(self):
        d = self.demarrer()
        self.en(self.prof)
        self.client.post(f"/api/evaluations/epreuves/{self.epreuve.pk}/fermer/")
        self.assertEqual(Tentative.objects.get(pk=d["id"]).mode_remise, "auto")
