"""
Centre d'analyse (phase 5, lot A1) : calculs exacts, périmètre de chaque profil,
isolation entre académies, requêtes en nombre constant.

Les valeurs attendues sont recalculées à la main à partir des notes de test.
Barème : CE1 (primaire) sur 10, 6e (collège) sur 20 ; calculs internes sur 20.
"""
from decimal import Decimal

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient

from apps.accounts.models import CustomUser
from apps.attendance.models import Attendance
from apps.classes.models import Class
from apps.grades.models import Grade
from apps.parents.models import Parent, ParentStudent
from apps.schools.models import Level, School, SchoolYear
from apps.students.models import Student, StudentEnrollment
from apps.subjects.models import Subject
from apps.teachers.models import Teacher, TeacherAssignment

URL = "/api/analytics/"


class CentreAnalyseTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.a = School.objects.create(name="Académie A", address="Cotonou", code="AN-A", currency_code="XOF")
        cls.b = School.objects.create(name="Académie B", address="Lomé", code="AN-B", currency_code="XOF")
        cls.annee = SchoolYear.objects.create(school=cls.a, name="2026-2027", is_current=True, start_date="2026-09-01", end_date="2027-06-30")
        cls.annee_b = SchoolYear.objects.create(school=cls.b, name="2026-2027", is_current=True, start_date="2026-09-01", end_date="2027-06-30")
        cls.ce1 = Level.objects.create(school=cls.a, name="CE1", order=3, cycle="primaire")
        cls.sixieme = Level.objects.create(school=cls.a, name="6e", order=12, cycle="college")
        cls.ce1a = Class.objects.create(name="CE1-A", level=cls.ce1, school_year=cls.annee)
        cls.ce1b = Class.objects.create(name="CE1-B", level=cls.ce1, school_year=cls.annee)
        cls.sixa = Class.objects.create(name="6e-A", level=cls.sixieme, school_year=cls.annee)
        cls.maths = Subject.objects.create(school=cls.a, name="Mathématiques", code="MATH", coefficient=2)
        cls.fr = Subject.objects.create(school=cls.a, name="Français", code="FR", coefficient=1)

        def user(nom, role, ecole):
            return CustomUser.objects.create_user(username=nom, email=f"{nom}@an.io", password="x", role=role,
                                                  school=ecole, first_name=nom.title(), last_name="Test")
        cls.sa = user("an_sa", "superadmin", None)
        cls.admin = user("an_admin", "admin", cls.a)
        cls.admin_b = user("an_admin_b", "admin", cls.b)
        cls.prof1 = Teacher.objects.create(user=user("an_prof1", "teacher", cls.a))
        cls.prof2 = Teacher.objects.create(user=user("an_prof2", "teacher", cls.a))
        TeacherAssignment.objects.create(teacher=cls.prof1, class_obj=cls.ce1a, subject=cls.maths)
        TeacherAssignment.objects.create(teacher=cls.prof2, class_obj=cls.sixa, subject=cls.maths)
        cls.parent = user("an_parent", "parent", cls.a)
        cls.u_ana = user("an_ana", "student", cls.a)

        def eleve(prenom, classe, genre, u=None, inscrit=True, ecole=None, annee=None):
            e = Student.objects.create(school=ecole or cls.a, school_year=annee or cls.annee, current_class=classe,
                                       first_name=prenom, last_name="Élève", gender=genre, date_of_birth="2016-05-01", user=u)
            if inscrit:
                StudentEnrollment.objects.create(student=e, school_year=annee or cls.annee, class_obj=classe)
            return e
        cls.ana = eleve("Ana", cls.ce1a, "F", cls.u_ana)
        cls.ben = eleve("Ben", cls.ce1a, "M")
        cls.cleo = eleve("Cleo", cls.ce1b, "F")
        cls.dan = eleve("Dan", cls.sixa, "M")
        cls.eve = eleve("Eve", cls.ce1b, "F", inscrit=False)        # active, sans inscription annuelle
        ParentStudent.objects.create(parent=Parent.objects.create(user=cls.parent), student=cls.ana)

        def note(e, matiere, v, periode="T1", prof=None, **kw):
            return Grade.objects.create(student=e, subject=matiere, school_year=e.school_year, period=periode,
                                        value=Decimal(v), teacher=prof, enrollment=e.enrollments.first(), **kw)
        # T1 — Ana : maths 16 et 14 (15), français 12 → (15×2 + 12) / 3 = 14
        note(cls.ana, cls.maths, 16, prof=cls.prof1); note(cls.ana, cls.maths, 14, prof=cls.prof1); note(cls.ana, cls.fr, 12)
        # Ben : maths 8, français 6 → 22/3 ≈ 7,333
        note(cls.ben, cls.maths, 8, prof=cls.prof1); note(cls.ben, cls.fr, 6)
        # Cleo : 10 et 10 → 10 ; Dan : maths 18, français 12 → 16
        note(cls.cleo, cls.maths, 10); note(cls.cleo, cls.fr, 10)
        note(cls.dan, cls.maths, 18, prof=cls.prof2); note(cls.dan, cls.fr, 12)
        # T2 — Ana : maths 18
        note(cls.ana, cls.maths, 18, periode="T2", prof=cls.prof1)
        note(cls.ben, cls.maths, 0, is_deleted=True)                  # supprimée : ignorée
        # Académie B : ne doit jamais apparaître.
        autre = eleve("Zoe", Class.objects.create(name="B-1", level=Level.objects.create(school=cls.b, name="CE1", cycle="primaire"),
                                                    school_year=cls.annee_b), "F", ecole=cls.b, annee=cls.annee_b)
        Grade.objects.create(student=autre, subject=Subject.objects.create(school=cls.b, name="Maths", code="M"),
                             school_year=cls.annee_b, period="T1", value=Decimal(2))
        for e, statut in ((cls.ana, "present"), (cls.ana, "absent"), (cls.ben, "late"), (cls.dan, "excused")):
            Attendance.objects.create(student=e, date="2026-10-05" if statut != "absent" else "2026-10-06", status=statut,
                                      school_year=cls.annee, enrollment=e.enrollments.first())

    def cli(self, u, academie=None):
        c = APIClient()
        c.force_authenticate(u)
        if academie is not None:
            c.post("/api/auth/entity-context/switch/", {"entity_id": academie.id})
        return c

    def get(self, u, chemin, academie=None, **params):
        return self.cli(u, academie).get(URL + chemin, params)

    # ── Calculs ─────────────────────────────────────────────────────────

    def test_resultats_niveau_exacts(self):
        r = self.get(self.admin, "resultats/", niveau=self.ce1.pk, periode="T1")
        self.assertEqual(r.status_code, 200, r.data)
        s = r.data["synthese"]
        self.assertEqual((r.data["bareme"], r.data["bareme_mixte"]), (10, False))
        self.assertEqual((s["eleves_notes"], s["notes"]), (3, 7))
        moy20 = (Decimal(14) + Decimal(22) / 3 + Decimal(10)) / 3
        self.assertEqual(s["moyenne"], round(float(moy20 / 2), 2))
        self.assertEqual(s["taux_reussite"], 66.7)                    # Ana 14 et Cleo 10 sur 20
        self.assertEqual(sum(t["eleves"] for t in r.data["repartition"]), 3)
        self.assertEqual(sum(m["eleves"] for m in r.data["maitrise"]), 3)
        self.assertEqual([c["nom"] for c in r.data["par_classe"]], ["CE1-A", "CE1-B"])
        self.assertEqual(r.data["par_classe"][0]["moyenne"], round(float((Decimal(14) + Decimal(22) / 3) / 2 / 2), 2))

    def test_bareme_mixte_et_progression(self):
        r = self.get(self.admin, "resultats/", periode="T1").data
        self.assertEqual((r["bareme"], r["bareme_mixte"]), (20, True))
        p = self.get(self.admin, "resultats/", classe=self.ce1a.pk).data["progression"]
        self.assertEqual([x["periode"] for x in p], ["T1", "T2"])
        self.assertEqual(p[0]["moyenne"], round(float((Decimal(14) + Decimal(22) / 3) / 2 / 2), 2))
        self.assertEqual((p[1]["moyenne"], p[1]["eleves_notes"]), (9.0, 1))

    def test_listes_conditions_comparables(self):
        r = self.get(self.admin, "resultats/", periode="T1").data
        self.assertIsNone(r["listes"])
        self.assertIn("conditions comparables", r["listes_indisponibles"])
        l = self.get(self.admin, "resultats/", classe=self.ce1a.pk, periode="T1").data["listes"]
        self.assertEqual([x["nom"] for x in l["plus_hautes"]], [self.ana.get_full_name()])   # Ben : 2 notes < 3
        self.assertEqual(l["exclus_trop_peu_de_notes"], 1)
        l = self.get(self.admin, "resultats/", classe=self.ce1a.pk, periode="T1", min_evaluations=2).data["listes"]
        self.assertEqual([x["nom"] for x in l["a_accompagner"]], [self.ben.get_full_name()])
        self.assertEqual(self.get(self.admin, "resultats/", seuil="0").status_code, 400)

    def test_matieres(self):
        m = {x["nom"]: x for x in self.get(self.admin, "matieres/", niveau=self.ce1.pk, periode="T1").data["matieres"]}
        self.assertEqual(m["Mathématiques"]["moyenne"], 5.5)            # (15 + 8 + 10) / 3 = 11 sur 20
        self.assertEqual((m["Mathématiques"]["notes"], m["Mathématiques"]["eleves_notes"]), (4, 3))
        self.assertEqual(m["Mathématiques"]["coefficient"], 2)

    def test_enseignants_contexte_et_perimetre(self):
        r = self.get(self.admin, "enseignants/", periode="T1").data
        self.assertIn("aucune conclusion", r["avertissement"])
        noms = [l["enseignant"] for l in r["lignes"]]
        self.assertEqual(noms, sorted(noms))                           # tri par nom, pas par résultat
        self.assertIn(self.prof2.user.get_full_name(), noms)
        mes = self.get(self.prof1.user, "enseignants/", periode="T1").data["lignes"]
        self.assertEqual({l["enseignant"] for l in mes}, {self.prof1.user.get_full_name()})
        self.assertEqual(mes[0]["notes"], 3)

    def test_effectifs(self):
        r = self.get(self.admin, "effectifs/").data
        self.assertEqual(r["inscrits"], 4)
        self.assertEqual(r["par_genre"], {"F": 2, "M": 2, "non_renseigne": 0})
        self.assertEqual((r["eleves_actifs"], r["actifs_sans_inscription"]), (5, 1))
        prof = self.get(self.prof1.user, "effectifs/").data
        self.assertEqual((prof["inscrits"], [c["nom"] for c in prof["par_classe"]]), (2, ["CE1-A"]))
        self.assertNotIn("actifs_sans_inscription", prof)

    def test_presences(self):
        r = self.get(self.admin, "presences/").data["synthese"]
        self.assertEqual((r["appels"], r["taux_presence"], r["taux_absence"]), (4, 50.0, 25.0))
        prof = self.get(self.prof1.user, "presences/").data
        self.assertEqual((prof["synthese"]["appels"], prof["synthese"]["taux_presence"]), (3, 66.7))
        self.assertEqual(prof["eleves_a_suivre"][0]["id"], self.ana.pk)
        self.assertEqual(self.get(self.admin, "presences/", du="2026-10-06").data["synthese"]["appels"], 1)
        self.assertEqual(self.get(self.admin, "presences/", du="pas-une-date").status_code, 400)

    # ── Vue personnelle ─────────────────────────────────────────────────

    def test_vue_eleve_parent_eleve_enseignant(self):
        r = self.get(self.parent, f"eleves/{self.ana.pk}/")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual([(m["periode"], m["moyenne"]) for m in r.data["moyennes_generales"]], [("T1", 7.0), ("T2", 9.0)])
        self.assertEqual(r.data["presences"]["appels"], 2)
        self.assertNotIn("listes", r.data)
        self.assertEqual(self.get(self.parent, f"eleves/{self.ben.pk}/").status_code, 404)
        self.assertEqual(self.get(self.u_ana, f"eleves/{self.ana.pk}/").status_code, 200)
        self.assertEqual(self.get(self.u_ana, f"eleves/{self.ben.pk}/").status_code, 404)
        self.assertEqual(self.get(self.prof1.user, f"eleves/{self.ana.pk}/").status_code, 200)
        self.assertEqual(self.get(self.prof1.user, f"eleves/{self.dan.pk}/").status_code, 403)
        self.assertEqual(self.get(self.admin_b, f"eleves/{self.ana.pk}/").status_code, 404)
        self.assertEqual([e["id"] for e in self.get(self.parent, "mes-eleves/").data["eleves"]], [self.ana.pk])
        self.assertEqual([e["id"] for e in self.get(self.u_ana, "mes-eleves/").data["eleves"]], [self.ana.pk])
        self.assertEqual(self.get(self.admin, "mes-eleves/").status_code, 403)

    # ── Droits et isolation ─────────────────────────────────────────────

    def test_droits_et_isolation(self):
        for chemin in ("resultats/", "matieres/", "enseignants/", "effectifs/", "presences/", "filtres/"):
            self.assertEqual(APIClient().get(URL + chemin).status_code, 401, chemin)
            for u in (self.parent, self.u_ana):
                self.assertEqual(self.get(u, chemin).status_code, 403, chemin)
        self.assertEqual(self.get(self.prof1.user, "resultats/", classe=self.sixa.pk).status_code, 403)
        self.assertEqual(self.get(self.prof1.user, "resultats/", enseignant=self.prof2.pk).status_code, 403)
        self.assertEqual(self.get(self.prof1.user, "resultats/", eleve=self.dan.pk).status_code, 403)
        self.assertEqual(self.get(self.admin_b, "resultats/", classe=self.ce1a.pk).status_code, 404)
        self.assertEqual(self.get(self.sa, "resultats/").status_code, 400)          # « Toutes les Académies »
        self.assertEqual(self.get(self.admin, "resultats/", periode="T9").status_code, 400)
        self.assertEqual(self.get(self.admin, "resultats/", classe="abc").status_code, 400)
        r = self.get(self.sa, "resultats/", academie=self.a)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["synthese"]["eleves_notes"], 4)                    # rien de l'académie B
        b = self.get(self.admin_b, "resultats/").data["synthese"]
        self.assertEqual((b["eleves_notes"], b["notes"]), (1, 1))
        o = self.get(self.prof1.user, "filtres/").data
        self.assertEqual(([c["nom"] for c in o["classes"]], o["enseignants"]), (["CE1-A"], []))
        o = self.get(self.admin, "filtres/", niveau=self.ce1.pk).data
        self.assertEqual([c["nom"] for c in o["classes"]], ["CE1-A", "CE1-B"])
        self.assertEqual(len(self.get(self.admin, "filtres/", classe=self.ce1b.pk).data["eleves"]), 2)

    def test_requetes_en_nombre_constant(self):
        def compter():
            c = self.cli(self.admin)
            with CaptureQueriesContext(connection) as q:
                self.assertEqual(c.get(URL + "resultats/").status_code, 200)
            return len(q)
        avant = compter()
        for i in range(6):
            e = Student.objects.create(school=self.a, school_year=self.annee, current_class=self.ce1b, first_name=f"N{i}",
                                       last_name="Élève", gender="M", date_of_birth="2016-05-01")
            StudentEnrollment.objects.create(student=e, school_year=self.annee, class_obj=self.ce1b)
            Grade.objects.create(student=e, subject=self.maths, school_year=self.annee, period="T1", value=Decimal(11))
        self.assertEqual(compter(), avant)
