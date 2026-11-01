"""
Droit de noter : enseignant, classe et matière croisés. Un enseignant de maths en
A et de français en B ne note ni le français en A ni les maths en B.
"""
from importlib import import_module

from django.apps import apps as django_apps
from django.test import TestCase
from rest_framework.test import APIClient

from apps.classes.models import Class
from apps.grades.models import Grade
from apps.parents.models import Parent, ParentStudent
from apps.schools.models import Level, SchoolYear
from apps.students.models import Student
from apps.subjects.models import Subject
from apps.teachers.affectations import paires_autorisees
from apps.teachers.models import Teacher, TeacherAssignment
from tests.test_virtualclass import make_school, make_user


def academie(nom):
    school = make_school() if nom == "A" else make_school(name="Autre")
    year = SchoolYear.objects.create(school=school, name="2026-2027", start_date="2026-09-01",
                                     end_date="2027-06-30", is_current=True)
    level = Level.objects.create(school=school, name="CM1", order=1, cycle="primaire")
    return school, year, level


class Base(TestCase):
    def setUp(self):
        self.school, self.year, level = academie("A")
        self.a = Class.objects.create(name="A", level=level, school_year=self.year)
        self.b = Class.objects.create(name="B", level=level, school_year=self.year)
        self.maths = Subject.objects.create(school=self.school, name="Maths", coefficient=1, level=level, language="fr")
        self.francais = Subject.objects.create(school=self.school, name="Français", coefficient=1, level=level, language="fr")
        self.a.subjects.set([self.maths, self.francais])
        self.b.subjects.set([self.maths, self.francais])
        self.user = make_user("prof@test.bj", "teacher", self.school)
        self.teacher = Teacher.objects.create(user=self.user)
        self.teacher.classes.set([self.a, self.b])
        self.teacher.subjects.set([self.maths, self.francais])
        TeacherAssignment.objects.create(teacher=self.teacher, class_obj=self.a, subject=self.maths)
        TeacherAssignment.objects.create(teacher=self.teacher, class_obj=self.b, subject=self.francais)
        self.compte_a = make_user("el-a@test.bj", "student", self.school)
        self.eleve_a = Student.objects.create(user=self.compte_a, school=self.school, first_name="E", last_name="A", current_class=self.a)
        self.eleve_b = Student.objects.create(user=make_user("el-b@test.bj", "student", self.school), school=self.school,
                                              first_name="E", last_name="B", current_class=self.b)
        self.client = APIClient()

    def corps(self, eleve, matiere):
        return {"student": eleve.pk, "subject": matiere.pk, "school_year": self.year.pk, "period": "T1",
                "value": "12", "note_type": "devoir"}

    def note(self, eleve, matiere):
        return Grade.objects.create(student=eleve, subject=matiere, school_year=self.year, period="T1", value=10)


class EnseignantTests(Base):
    def setUp(self):
        super().setUp()
        self.client.force_authenticate(self.user)

    def test_creation(self):
        self.assertEqual(self.client.post("/api/grades/", self.corps(self.eleve_a, self.maths), format="json").status_code, 201)
        self.assertEqual(self.client.post("/api/grades/", self.corps(self.eleve_b, self.francais), format="json").status_code, 201)
        n = Grade.objects.count()
        self.assertEqual(self.client.post("/api/grades/", self.corps(self.eleve_a, self.francais), format="json").status_code, 403)
        self.assertEqual(self.client.post("/api/grades/", self.corps(self.eleve_b, self.maths), format="json").status_code, 403)
        self.assertEqual(Grade.objects.count(), n)

    def test_modification(self):
        permise, refusee = self.note(self.eleve_a, self.maths), self.note(self.eleve_a, self.francais)
        self.assertEqual(self.client.patch(f"/api/grades/{permise.pk}/", {"value": "13", "justification": "Erreur"}, format="json").status_code, 200)
        self.assertEqual(self.client.patch(f"/api/grades/{refusee.pk}/", {"value": "13", "justification": "Erreur"}, format="json").status_code, 403)
        refusee.refresh_from_db()
        self.assertEqual(refusee.value, 10)

    def test_changer_de_matiere_vers_une_matiere_non_affectee(self):
        permise = self.note(self.eleve_a, self.maths)
        r = self.client.patch(f"/api/grades/{permise.pk}/", {"subject": self.francais.pk, "justification": "Erreur"}, format="json")
        self.assertEqual(r.status_code, 403)

    def test_suppression_et_restauration(self):
        permise, refusee = self.note(self.eleve_b, self.francais), self.note(self.eleve_b, self.maths)
        self.assertEqual(self.client.delete(f"/api/grades/{refusee.pk}/", {"justification": "Erreur"}, format="json").status_code, 403)
        self.assertEqual(self.client.delete(f"/api/grades/{permise.pk}/", {"justification": "Erreur"}, format="json").status_code, 204)
        self.assertEqual(self.client.post(f"/api/grades/{permise.pk}/restore/").status_code, 200)
        Grade.objects.filter(pk=refusee.pk).update(is_deleted=True)
        self.assertEqual(self.client.post(f"/api/grades/{refusee.pk}/restore/").status_code, 403)

    def test_saisie_groupee_tout_ou_rien(self):
        n = Grade.objects.count()
        r = self.client.post("/api/grades/bulk-create/", {
            "student": self.eleve_a.pk, "school_year": self.year.pk,
            "grades": [{"subject": self.maths.pk, "period": "T1", "value": "12", "note_type": "devoir"},
                       {"subject": self.francais.pk, "period": "T1", "value": "12", "note_type": "devoir"}],
        }, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertEqual(Grade.objects.count(), n)

    def test_enregistrement_par_lot(self):
        r = self.client.post("/api/grades/bulk_save/", {"grades": [self.corps(self.eleve_a, self.francais)]}, format="json")
        self.assertFalse(Grade.objects.filter(student=self.eleve_a, subject=self.francais).exists(), r.data)

    def test_l_ecran_recoit_les_memes_droits(self):
        note_ok, note_ko = self.note(self.eleve_a, self.maths), self.note(self.eleve_a, self.francais)
        r = self.client.get("/api/grades/?page_size=50")
        droits = {n["id"]: n["peut_modifier"] for n in r.data.get("results", r.data)}
        self.assertTrue(droits[note_ok.pk])
        self.assertFalse(droits[note_ko.pk])
        r = self.client.get("/api/teachers/my_assignments/")
        self.assertCountEqual(r.data, [{"class_id": self.a.pk, "subject_id": self.maths.pk},
                                       {"class_id": self.b.pk, "subject_id": self.francais.pk}])

    def test_retirer_la_classe_retire_le_droit(self):
        self.teacher.classes.remove(self.a)
        self.assertEqual(paires_autorisees(self.teacher), {(self.b.pk, self.francais.pk)})

    def test_ne_gere_pas_ses_propres_affectations(self):
        url = f"/api/teachers/{self.teacher.pk}/assignments/"
        self.assertEqual(self.client.put(url, {"assignments": []}, format="json").status_code, 403)
        self.assertEqual(self.teacher.assignments.count(), 2)


class AutresRolesTests(Base):
    def test_administrateur_note_et_gere(self):
        self.client.force_authenticate(make_user("adm@test.bj", "admin", self.school))
        self.assertEqual(self.client.post("/api/grades/", self.corps(self.eleve_a, self.francais), format="json").status_code, 201)
        url = f"/api/teachers/{self.teacher.pk}/assignments/"
        r = self.client.put(url, {"assignments": [{"class_id": self.b.pk, "subject_id": self.maths.pk}]}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(paires_autorisees(self.teacher), {(self.b.pk, self.maths.pk)})
        ligne = self.teacher.assignments.get()
        self.assertEqual(ligne.source, TeacherAssignment.SOURCE_ADMIN)
        self.assertIsNotNone(ligne.confirmed_at)

    def test_matiere_hors_programme_refusee(self):
        self.client.force_authenticate(make_user("adm@test.bj", "admin", self.school))
        self.a.subjects.set([self.maths])
        r = self.client.put(f"/api/teachers/{self.teacher.pk}/assignments/",
                            {"assignments": [{"class_id": self.a.pk, "subject_id": self.francais.pk}]}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertEqual(self.teacher.assignments.count(), 2)

    def test_donnees_mal_formees(self):
        self.client.force_authenticate(make_user("adm@test.bj", "admin", self.school))
        url = f"/api/teachers/{self.teacher.pk}/assignments/"
        for corps in ({}, {"assignments": "x"}, {"assignments": [{"class_id": "x"}]}, {"assignments": [1]}):
            self.assertEqual(self.client.put(url, corps, format="json").status_code, 400, corps)

    def test_eleve_et_parent_refuses(self):
        eleve_user = self.compte_a
        parent_user = make_user("pa@test.bj", "parent", self.school)
        ParentStudent.objects.create(parent=Parent.objects.create(user=parent_user), student=self.eleve_a, relationship="mother")
        for user in (eleve_user, parent_user):
            self.client.force_authenticate(user)
            self.assertEqual(self.client.post("/api/grades/", self.corps(self.eleve_a, self.maths), format="json").status_code, 403)
            self.assertEqual(self.client.get(f"/api/teachers/{self.teacher.pk}/assignments/").status_code, 403)

    def test_sans_authentification(self):
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get(f"/api/teachers/{self.teacher.pk}/assignments/").status_code, 401)


class IsolationTests(Base):
    def setUp(self):
        super().setUp()
        self.autre, self.autre_year, level = academie("B")
        self.autre_classe = Class.objects.create(name="X", level=level, school_year=self.autre_year)
        self.autre_matiere = Subject.objects.create(school=self.autre, name="Autre", coefficient=1, level=level, language="fr")
        self.autre_admin = make_user("adm2@test.bj", "admin", self.autre)

    def test_admin_d_une_autre_academie(self):
        self.client.force_authenticate(self.autre_admin)
        r = self.client.put(f"/api/teachers/{self.teacher.pk}/assignments/", {"assignments": []}, format="json")
        self.assertIn(r.status_code, (403, 404))
        self.assertEqual(self.teacher.assignments.count(), 2)

    def test_classe_ou_matiere_d_une_autre_academie(self):
        self.client.force_authenticate(make_user("adm@test.bj", "admin", self.school))
        url = f"/api/teachers/{self.teacher.pk}/assignments/"
        for ligne in ({"class_id": self.autre_classe.pk, "subject_id": self.maths.pk},
                      {"class_id": self.a.pk, "subject_id": self.autre_matiere.pk}):
            self.assertEqual(self.client.put(url, {"assignments": [ligne]}, format="json").status_code, 400)
        self.assertEqual(self.teacher.assignments.count(), 2)

    def test_enseignant_d_une_autre_academie(self):
        autre_user = make_user("prof2@test.bj", "teacher", self.autre)
        autre = Teacher.objects.create(user=autre_user)
        autre.classes.set([self.autre_classe])
        autre.subjects.set([self.autre_matiere])
        TeacherAssignment.objects.create(teacher=autre, class_obj=self.autre_classe, subject=self.autre_matiere)
        self.client.force_authenticate(autre_user)
        r = self.client.post("/api/grades/", self.corps(self.eleve_a, self.maths), format="json")
        self.assertIn(r.status_code, (400, 403, 404))
        self.assertFalse(Grade.objects.filter(student=self.eleve_a).exists())


class RepriseTests(Base):
    def test_reprise_conserve_les_droits_et_ne_touche_pas_aux_notes(self):
        TeacherAssignment.objects.all().delete()
        self.a.subjects.set([self.maths])
        note = Grade.objects.create(student=self.eleve_a, subject=self.francais, teacher=self.teacher,
                                    school_year=self.year, period="T1", value=7)
        module = import_module("apps.teachers.migrations.0002_teacherassignment")
        module.reprendre(django_apps, None)
        self.assertEqual(paires_autorisees(self.teacher), {
            (self.a.pk, self.maths.pk), (self.a.pk, self.francais.pk),   # note existante hors programme
            (self.b.pk, self.maths.pk), (self.b.pk, self.francais.pk),
        })
        self.assertTrue(all(a.source == "reprise" for a in self.teacher.assignments.all()))
        note.refresh_from_db()
        self.assertEqual(note.value, 7)
