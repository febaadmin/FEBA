"""
Colonne « Classe » de la liste des élèves (phase 6).

Cause constatée en production : les inscriptions annuelles créées automatiquement
(notes, absences, paiements, bulletins) n'avaient pas de classe. La liste, filtrée
sur l'année en cours, lisait la classe de cette inscription : colonne vide pour
76 élèves dont la classe était pourtant connue.
"""
import io
import json
import os
import tempfile
from decimal import Decimal

from django.core.management import call_command
from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import CustomUser
from apps.classes.models import Class
from apps.schools.models import Level, School, SchoolYear
from apps.students.models import Student, StudentEnrollment
from apps.students.services import get_or_create_enrollment


class ClasseElevesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.a = School.objects.create(name="Acad Classe", address="x", code="CL-A")
        cls.b = School.objects.create(name="Acad Classe B", address="x", code="CL-B")
        cls.y1 = SchoolYear.objects.create(school=cls.a, name="2025-2026", start_date="2025-09-01", end_date="2026-06-30")
        cls.y2 = SchoolYear.objects.create(school=cls.a, name="2026-2027", is_current=True, start_date="2026-09-01", end_date="2027-06-30")
        yb = SchoolYear.objects.create(school=cls.b, name="2026-2027", is_current=True, start_date="2026-09-01", end_date="2027-06-30")
        lv = Level.objects.create(school=cls.a, name="CE1", order=3)
        cls.ce1_old = Class.objects.create(name="CE1-A 2025", level=lv, school_year=cls.y1)
        cls.ce1 = Class.objects.create(name="CE1-A", level=lv, school_year=cls.y2)
        cls.ce1b = Class.objects.create(name="CE1-B", level=lv, school_year=cls.y2)
        cls.b1 = Class.objects.create(name="B-1", level=Level.objects.create(school=cls.b, name="CP"), school_year=yb)
        cls.admin = CustomUser.objects.create_user(username="cl_admin", email="cl_admin@t.io", password="x", role="admin", school=cls.a)
        cls.admin_b = CustomUser.objects.create_user(username="cl_admin_b", email="cl_admin_b@t.io", password="x", role="admin", school=cls.b)

    def eleve(self, prenom, cls=None, annee=None, ecole=None):
        return Student.objects.create(school=ecole or self.a, school_year=annee or self.y2, current_class=cls,
                                      first_name=prenom, last_name="Test", date_of_birth="2018-01-01")

    def liste(self, user=None, **params):
        c = APIClient()
        c.force_authenticate(user or self.admin)
        r = c.get("/api/students/", params)
        self.assertEqual(r.status_code, 200)
        data = r.data.get("results", r.data)
        return {e["first_name"]: e for e in data}

    def test_inscription_automatique_sans_classe_n_efface_plus_la_classe(self):
        # Cas de production : inscription créée par une note/un paiement, sans classe.
        ana = self.eleve("Ana", self.ce1)
        StudentEnrollment.objects.create(student=ana, school_year=self.y2, class_obj=None)
        l = self.liste(school_year=self.y2.pk)
        self.assertEqual((l["Ana"]["class_name"], l["Ana"]["class_level"]), ("CE1-A", "CE1"))

    def test_sans_classe_et_classe_d_une_autre_annee(self):
        self.eleve("Sans")
        vieux = self.eleve("Vieux", self.ce1_old, annee=self.y1)
        StudentEnrollment.objects.create(student=vieux, school_year=self.y2, class_obj=None)
        l = self.liste(school_year=self.y2.pk)
        self.assertIsNone(l["Sans"]["class_name"])
        self.assertIsNone(l["Vieux"]["class_name"])          # jamais la classe d'une autre année

    def test_historique_et_changement_de_classe(self):
        ben = self.eleve("Ben", self.ce1)
        StudentEnrollment.objects.create(student=ben, school_year=self.y1, class_obj=self.ce1_old)
        StudentEnrollment.objects.create(student=ben, school_year=self.y2, class_obj=self.ce1)
        self.assertEqual(self.liste(school_year=self.y1.pk)["Ben"]["class_name"], "CE1-A 2025")
        self.assertEqual(self.liste(school_year=self.y2.pk)["Ben"]["class_name"], "CE1-A")
        # Changement de classe depuis la fiche : l'inscription de l'année suit, l'historique non.
        c = APIClient(); c.force_authenticate(self.admin)
        r = c.patch(f"/api/students/{ben.pk}/", {"current_class": self.ce1b.pk}, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(ben.enrollments.get(school_year=self.y2).class_obj_id, self.ce1b.pk)
        self.assertEqual(ben.enrollments.get(school_year=self.y1).class_obj_id, self.ce1_old.pk)
        self.assertEqual(self.liste(school_year=self.y2.pk)["Ben"]["class_name"], "CE1-B")

    def test_creation_d_inscription_reprend_la_classe_de_l_annee(self):
        cleo = self.eleve("Cleo", self.ce1)
        e, _ = get_or_create_enrollment(cleo, self.y2.pk)
        self.assertEqual(e.class_obj_id, self.ce1.pk)
        e1, _ = get_or_create_enrollment(cleo, self.y1.pk)
        self.assertIsNone(e1.class_obj_id)                   # classe d'une autre année : non reprise

    def test_creation_d_eleve_cree_l_inscription_avec_sa_classe(self):
        c = APIClient(); c.force_authenticate(self.admin)
        r = c.post("/api/students/", {"first_name": "Dan", "last_name": "Test", "date_of_birth": "2018-01-01",
                                      "current_class": self.ce1.pk, "school_year": self.y2.pk}, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(Student.objects.get(pk=r.data["id"]).enrollments.get(school_year=self.y2).class_obj_id, self.ce1.pk)

    def test_isolation_entre_academies(self):
        self.eleve("Zoe", self.b1, annee=self.b1.school_year, ecole=self.b)
        self.eleve("Ana", self.ce1)
        self.assertNotIn("Zoe", self.liste())
        self.assertEqual(self.liste(self.admin_b)["Zoe"]["class_name"], "B-1")

    def test_commande_simulation_application_et_retour_arriere(self):
        ana = self.eleve("Ana", self.ce1)
        vieux = self.eleve("Vieux", self.ce1_old, annee=self.y1)
        e_ana = StudentEnrollment.objects.create(student=ana, school_year=self.y2, class_obj=None)
        e_vieux = StudentEnrollment.objects.create(student=vieux, school_year=self.y2, class_obj=None)
        sortie = io.StringIO()
        call_command("completer_classes_inscriptions", stdout=sortie)
        self.assertIn("complétables (classe actuelle de la même année) : 1", sortie.getvalue())
        e_ana.refresh_from_db()
        self.assertIsNone(e_ana.class_obj_id)                 # simulation : rien d'écrit
        with tempfile.TemporaryDirectory() as d:
            journal = os.path.join(d, "j.json")
            call_command("completer_classes_inscriptions", appliquer=True, journal=journal, stdout=io.StringIO())
            e_ana.refresh_from_db(); e_vieux.refresh_from_db()
            self.assertEqual((e_ana.class_obj_id, e_vieux.class_obj_id), (self.ce1.pk, None))
            self.assertEqual(json.load(open(journal))["inscriptions"], [{"id": e_ana.pk, "classe": self.ce1.pk}])
            call_command("completer_classes_inscriptions", annuler=journal, stdout=io.StringIO())
            e_ana.refresh_from_db()
            self.assertIsNone(e_ana.class_obj_id)

    def test_effectif_de_classe_melange_inscriptions_avec_et_sans_classe(self):
        # Avant : dès qu'un élève avait une classe sur son inscription, les élèves dont
        # l'inscription n'en avait pas disparaissaient des statistiques et rangs de la classe.
        from apps.students.services import eleves_de_la_classe
        avec = self.eleve("Avec", self.ce1)
        StudentEnrollment.objects.create(student=avec, school_year=self.y2, class_obj=self.ce1)
        sans = self.eleve("Sans", self.ce1)
        StudentEnrollment.objects.create(student=sans, school_year=self.y2, class_obj=None)
        parti = self.eleve("Parti", self.ce1)                                   # classe changée ensuite
        StudentEnrollment.objects.create(student=parti, school_year=self.y2, class_obj=self.ce1b)
        self.assertEqual(set(eleves_de_la_classe(self.ce1, self.y2).values_list("first_name", flat=True)), {"Avec", "Sans"})
        self.assertEqual(set(eleves_de_la_classe(self.ce1b, self.y2).values_list("first_name", flat=True)), {"Parti"})


class DonneesOrphelinesTests(TestCase):
    """Désinscription puis réinscription : les notes et paiements de l'année se rattachent de nouveau."""

    def test_reinscription_rattache_les_donnees(self):
        from apps.grades.models import Grade
        from apps.payments.models import Payment
        from apps.subjects.models import Subject
        a = School.objects.create(name="Orph", address="x", code="ORPH")
        y = SchoolYear.objects.create(school=a, name="2026-2027", is_current=True, start_date="2026-09-01", end_date="2027-06-30")
        autre_annee = SchoolYear.objects.create(school=a, name="2025-2026", start_date="2025-09-01", end_date="2026-06-30")
        e = Student.objects.create(school=a, school_year=y, first_name="O", last_name="T", date_of_birth="2018-01-01")
        ins = StudentEnrollment.objects.create(student=e, school_year=y)
        m = Subject.objects.create(school=a, name="Maths", code="M")
        g = Grade.objects.create(student=e, subject=m, school_year=y, enrollment=ins, period="T1", value=Decimal("12"))
        g_autre = Grade.objects.create(student=e, subject=m, school_year=autre_annee, period="T1", value=Decimal("9"))
        p = Payment.objects.create(student=e, school_year=y, enrollment=ins, payment_type="cantine", amount=Decimal("1000"), payment_method="cash")
        ins.delete()                                                   # « Désinscrire »
        g.refresh_from_db(); p.refresh_from_db()
        self.assertIsNone(g.enrollment_id)
        nouvelle = StudentEnrollment.objects.create(student=e, school_year=y)
        g.refresh_from_db(); p.refresh_from_db(); g_autre.refresh_from_db()
        self.assertEqual((g.enrollment_id, p.enrollment_id), (nouvelle.pk, nouvelle.pk))
        self.assertEqual(g.value, Decimal("12"))                       # aucune valeur modifiée
        self.assertIsNone(g_autre.enrollment_id)                       # autre année : intacte

    def test_commande_simulation_application_retour(self):
        from apps.grades.models import Grade
        from apps.subjects.models import Subject
        a = School.objects.create(name="Orph2", address="x", code="ORPH2")
        y = SchoolYear.objects.create(school=a, name="2026-2027", is_current=True, start_date="2026-09-01", end_date="2027-06-30")
        e = Student.objects.create(school=a, school_year=y, first_name="O", last_name="T", date_of_birth="2018-01-01")
        ins = StudentEnrollment.objects.create(student=e, school_year=y)
        g = Grade.objects.create(student=e, subject=Subject.objects.create(school=a, name="M", code="M"), school_year=y, period="T1", value=Decimal("12"))
        Grade.objects.filter(pk=g.pk).update(enrollment=None)          # état constaté en production
        sortie = io.StringIO()
        call_command("rattacher_donnees_inscriptions", stdout=sortie)
        self.assertIn("notes 1", sortie.getvalue())
        g.refresh_from_db(); self.assertIsNone(g.enrollment_id)
        with tempfile.TemporaryDirectory() as d:
            j = os.path.join(d, "j.json")
            call_command("rattacher_donnees_inscriptions", appliquer=True, journal=j, stdout=io.StringIO())
            g.refresh_from_db(); self.assertEqual(g.enrollment_id, ins.pk)
            call_command("rattacher_donnees_inscriptions", annuler=j, stdout=io.StringIO())
            g.refresh_from_db(); self.assertIsNone(g.enrollment_id)
