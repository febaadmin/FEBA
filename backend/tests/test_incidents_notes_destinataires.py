"""
Reproduction des 8 incidents d'octobre 2026 et de leurs causes communes.

ERR-72B72D, FF13EF, 291699, CBAA57, A036A8, FC6DC7, 4744E2 :
  DELETE /api/grades/<id>/ → 'dict' object has no attribute 'strip'.
ERR-5D12BE : GET /api/auth/recipients/ → CustomUser has no teacher_profile.
"""
from django.test import SimpleTestCase, TestCase
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIClient

from apps.accounts.models import CustomUser
from apps.core.request_text import text_field
from apps.grades.models import Grade
from apps.incidents.models import TechnicalIncident, build_fingerprint
from apps.parents.models import Parent, ParentStudent
from apps.teachers.models import Teacher
from tests.test_bulk_grades import BulkGradeFixture, auth


class SuppressionNoteTests(BulkGradeFixture):
    def setUp(self):
        self.client = APIClient()
        # Un enseignant ne voit que les notes d'élèves dont le compte est actif.
        self.student.user = CustomUser.objects.create_user(
            username="ayo", email="ayo@test.bj", password="Pass1234!", role="student",
            first_name="Ayo", last_name="Codjo", school=self.school)
        self.student.save(update_fields=["user"])
        self.grade = Grade.objects.create(student=self.student, subject=self.math, school_year=self.year,
                                          value=12, period="T1", note_type="controle", teacher=self.teacher)
        self.url = f"/api/grades/{self.grade.id}/"

    def supprimer(self, data=None, compte="prof@test.bj", url=None):
        auth(self.client, compte)
        return self.client.delete(url or self.url, data if data is not None else {"justification": "Doublon"},
                                  format="json")

    def test_suppression_normale_tracee(self):
        self.assertEqual(self.supprimer().status_code, 204)
        self.grade.refresh_from_db()
        self.assertTrue(self.grade.is_deleted)
        self.assertEqual(self.grade.deleted_by.email, "prof@test.bj")
        self.assertTrue(self.grade.history.filter(justification="Doublon").exists())

    def test_reproduction_justification_objet_refusee_sans_incident(self):
        # Ce qu'envoyait la page enseignant : le contexte de React Query.
        resp = self.supprimer({"justification": {"client": {}, "meta": None}})
        self.assertEqual(resp.status_code, 400)
        self.assertIn("justification", resp.data)
        self.assertFalse(TechnicalIncident.objects.exists())
        self.grade.refresh_from_db()
        self.assertFalse(self.grade.is_deleted)

    def test_justification_absente_vide_ou_mal_typee(self):
        for data in ({}, {"justification": None}, {"justification": "   "}, {"justification": 12}, {"justification": []}):
            with self.subTest(data=data):
                self.assertEqual(self.supprimer(data).status_code, 400)
        self.grade.refresh_from_db()
        self.assertFalse(self.grade.is_deleted)

    def test_note_inexistante(self):
        self.assertEqual(self.supprimer(url="/api/grades/99999999/").status_code, 404)

    def test_suppression_repetee(self):
        self.assertEqual(self.supprimer().status_code, 204)
        self.assertIn(self.supprimer().status_code, (400, 404))
        self.assertEqual(self.grade.history.filter(action="delete").count(), 1)

    def test_enseignant_d_une_autre_matiere_refuse(self):
        hist = Grade.objects.create(student=self.student, subject=self.hist, school_year=self.year,
                                    value=9, period="T1", note_type="controle")
        self.assertEqual(self.supprimer(url=f"/api/grades/{hist.id}/").status_code, 403)
        hist.refresh_from_db()
        self.assertFalse(hist.is_deleted)

    def test_autre_etablissement_et_eleve_sans_droit(self):
        CustomUser.objects.create_user(username="adm2", email="adm2@test.bj", password="Pass1234!", role="admin",
                                       first_name="A", last_name="B", school=self.other)
        self.assertEqual(self.supprimer(compte="adm2@test.bj").status_code, 404)
        CustomUser.objects.create_user(username="el", email="el@test.bj", password="Pass1234!", role="student",
                                       first_name="E", last_name="L", school=self.school)
        self.assertEqual(self.supprimer(compte="el@test.bj").status_code, 403)
        self.grade.refresh_from_db()
        self.assertFalse(self.grade.is_deleted)

    def test_admin_supprime(self):
        self.assertEqual(self.supprimer(compte="adm@test.bj").status_code, 204)

    def test_sans_authentification(self):
        self.assertEqual(APIClient().delete(self.url, {"justification": "x"}, format="json").status_code, 401)


class DestinatairesTests(BulkGradeFixture):
    URL = "/api/auth/recipients/"

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        def compte(email, role, school):
            return CustomUser.objects.create_user(username=email.split("@")[0], email=email, password="Pass1234!",
                                                  role=role, first_name="X", last_name="Y", school=school)
        cls.sans_profil = compte("prof-sans-profil@test.bj", "teacher", cls.school)
        cls.parent_u = compte("parent@test.bj", "parent", cls.school)
        ParentStudent.objects.create(parent=Parent.objects.create(user=cls.parent_u), student=cls.student)
        cls.autre_admin = compte("adm-autre@test.bj", "admin", cls.other)
        cls.inactif = compte("inactif@test.bj", "admin", cls.school)
        cls.inactif.is_active = False
        cls.inactif.save()

    def ids(self, email):
        client = APIClient()
        auth(client, email)
        resp = client.get(self.URL)
        self.assertEqual(resp.status_code, 200, resp.data)
        data = resp.data.get("results", resp.data) if isinstance(resp.data, dict) else resp.data
        return {r["id"] for r in data}

    def test_reproduction_enseignant_sans_profil(self):
        ids = self.ids("prof-sans-profil@test.bj")
        self.assertIn(self.admin.id, ids)        # il peut écrire à l'administration
        self.assertNotIn(self.parent_u.id, ids)  # aucune classe : aucun parent

    def test_enseignant_avec_profil(self):
        ids = self.ids("prof@test.bj")
        self.assertIn(self.parent_u.id, ids)
        self.assertIn(self.admin.id, ids)

    def test_parent(self):
        ids = self.ids("parent@test.bj")
        self.assertIn(self.teacher.user_id, ids)
        self.assertIn(self.admin.id, ids)

    def test_admin_limite_a_son_etablissement_et_aux_comptes_actifs(self):
        ids = self.ids("adm@test.bj")
        self.assertIn(self.parent_u.id, ids)
        self.assertNotIn(self.autre_admin.id, ids)
        self.assertNotIn(self.inactif.id, ids)

    def test_superadmin(self):
        self.assertIn(self.autre_admin.id, self.ids("sa@test.bj"))


class CreationCompteTests(TestCase):
    def test_creation_generique_cree_le_profil(self):
        from apps.accounts.serializers import UserCreateSerializer
        from apps.schools.models import School
        school = School.objects.create(name="E", address="A")
        for role, attr, modele in (("teacher", "teacher_profile", Teacher), ("parent", "parent_profile", Parent)):
            s = UserCreateSerializer(data={"email": f"{role}@test.bj", "first_name": "A", "last_name": "B", "role": role,
                                           "school": school.id, "password": "Zk9!tYq3pLm", "password2": "Zk9!tYq3pLm"})
            self.assertTrue(s.is_valid(), s.errors)
            user = s.save()
            self.assertTrue(modele.objects.filter(user=user).exists())


class TexteEtEmpreinteTests(SimpleTestCase):
    def test_text_field(self):
        self.assertEqual(text_field({"a": "  x "}, "a"), "x")
        self.assertEqual(text_field({}, "a"), "")
        self.assertEqual(text_field({"a": None}, "a"), "")
        for mauvais in ({"k": 1}, [], 3):
            with self.assertRaises(ValidationError):
                text_field({"a": mauvais}, "a")

    def test_meme_defaut_sur_deux_notes_un_seul_incident(self):
        args = ("AttributeError", "grade", "apps/grades/views.py:274 (destroy)", "m")
        def empreinte(url):
            return build_fingerprint(args[0], url, args[1], args[2], args[3])
        self.assertEqual(empreinte("/api/grades/742/"), empreinte("/api/grades/934/"))
        self.assertNotEqual(empreinte("/api/grades/742/"), empreinte("/api/payments/742/"))


class ReparationProfilsTests(TestCase):
    def test_simulation_puis_application(self):
        from io import StringIO

        from django.core.management import call_command
        user = CustomUser.objects.create_user(username="t", email="t@test.bj", password="Pass1234!", role="teacher",
                                              first_name="T", last_name="T")
        out = StringIO()
        call_command("repair_missing_profiles", stdout=out)
        self.assertIn("profil manquant", out.getvalue())
        self.assertFalse(Teacher.objects.filter(user=user).exists())
        call_command("repair_missing_profiles", "--apply", stdout=StringIO())
        self.assertTrue(Teacher.objects.filter(user=user).exists())
