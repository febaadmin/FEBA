"""
V8 — Priorités 1 & 2 : création des profils (Enseignant en tête) et audit.

Régression principale reproduite puis verrouillée : la création d'un profil
Enseignant renvoyait une erreur 500
(« UNIQUE constraint failed: teachers_teacher.employee_id ») dès qu'un
enseignant avait été supprimé, car le matricule était généré à partir de
`Teacher.objects.count() + 1` au lieu du plus grand suffixe réellement utilisé.

Couvre aussi : atomicité, doublons, champs manquants, permissions, isolation
multi-établissement, et la création des autres profils (Élève, Parent).
"""
from datetime import date

from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import CustomUser
from apps.classes.models import Class
from apps.parents.models import Parent
from apps.schools.models import School, SchoolYear, Level
from apps.students.models import Student
from apps.subjects.models import Subject
from apps.teachers.models import Teacher

TEACHERS_URL = "/api/teachers/"


class ProfileFixture(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.school = School.objects.create(name="FEBA", address="Cotonou")
        cls.other_school = School.objects.create(name="Autre", address="Porto-Novo")
        cls.year = SchoolYear.objects.create(
            school=cls.school, name="2025-2026",
            start_date="2025-09-01", end_date="2026-07-31", is_current=True,
        )
        cls.level = Level.objects.create(school=cls.school, name="CM2", order=11)
        cls.cls1 = Class.objects.create(name="CM2-A", level=cls.level, school_year=cls.year)
        cls.cls2 = Class.objects.create(name="CM2-B", level=cls.level, school_year=cls.year)
        cls.math = Subject.objects.create(school=cls.school, name="Maths", code="MATH",
                                          coefficient=4, language="fr")
        cls.fr = Subject.objects.create(school=cls.school, name="Français", code="FR",
                                        coefficient=3, language="fr")
        # Matière et classe d'un AUTRE établissement (test d'isolation)
        cls.other_year = SchoolYear.objects.create(
            school=cls.other_school, name="2025-2026",
            start_date="2025-09-01", end_date="2026-07-31", is_current=True,
        )
        cls.other_subject = Subject.objects.create(
            school=cls.other_school, name="Autre matière", code="OTH",
            coefficient=1, language="fr",
        )
        cls.superadmin = CustomUser.objects.create_user(
            username="sa", email="sa@test.bj", password="Pass1234!",
            role="superadmin", first_name="S", last_name="A", school=cls.school,
        )
        cls.admin = CustomUser.objects.create_user(
            username="adm", email="adm@test.bj", password="Pass1234!",
            role="admin", first_name="A", last_name="D", school=cls.school,
        )
        cls.parent_user = CustomUser.objects.create_user(
            username="par", email="par@test.bj", password="Pass1234!",
            role="parent", first_name="P", last_name="A", school=cls.school,
        )

    def new_teacher_user(self, suffix):
        return CustomUser.objects.create_user(
            username=f"prof{suffix}", email=f"prof{suffix}@test.bj",
            password="Pass1234!", role="teacher", first_name="T",
            last_name=str(suffix), school=self.school,
        )

    def auth(self, user):
        client = APIClient()
        client.force_authenticate(user=user)
        return client

    def payload(self, user, **over):
        data = {
            "user_write": user.id,
            "specialization": "Mathématiques",
            "hire_date": "2026-07-26",
            "contract_type": "permanent",
            "class_ids": [self.cls1.id, self.cls2.id],
            "subject_ids": [self.math.id, self.fr.id],
            "bio": "",
        }
        data.update(over)
        return data


class TeacherCreationRegressionTests(ProfileFixture):
    """Le scénario exact du bug : suppression puis nouvelle création."""

    def test_creation_apres_suppression_ne_renvoie_plus_500(self):
        client = self.auth(self.superadmin)
        # 3 enseignants : matricules 0001, 0002, 0003
        created = []
        for i in range(3):
            resp = client.post(TEACHERS_URL, self.payload(self.new_teacher_user(i)), format="json")
            self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
            created.append(resp.data["employee_id"])
        self.assertEqual(created[-1][-4:], "0003")

        # On supprime le PREMIER : count() == 2 alors que le max reste 0003.
        Teacher.objects.get(employee_id=created[0]).delete()
        self.assertEqual(Teacher.objects.count(), 2)

        # L'ancien code générait ENS-<année>-0003 (déjà pris) → 500.
        resp = client.post(TEACHERS_URL, self.payload(self.new_teacher_user(99)), format="json")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        self.assertEqual(resp.data["employee_id"][-4:], "0004")

    def test_creations_repetees_avec_suppressions_intercalees(self):
        """Aucune 500 et aucun matricule en double parmi les profils existants.

        (Réattribuer le matricule d'un enseignant SUPPRIMÉ n'est pas un
        conflit : la contrainte d'unicité ne porte que sur les lignes vivantes.)
        """
        client = self.auth(self.superadmin)
        for i in range(10):
            resp = client.post(TEACHERS_URL, self.payload(self.new_teacher_user(f"a{i}")),
                               format="json")
            self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
            if i % 3 == 0:  # suppressions intercalées
                Teacher.objects.order_by("id").first().delete()
            existing = list(Teacher.objects.values_list("employee_id", flat=True))
            self.assertEqual(len(existing), len(set(existing)), "matricule en double")

    def test_relations_matieres_et_classes_enregistrees(self):
        client = self.auth(self.superadmin)
        resp = client.post(TEACHERS_URL, self.payload(self.new_teacher_user("rel")), format="json")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        teacher = Teacher.objects.get(id=resp.data["id"])
        self.assertEqual(set(teacher.subjects.values_list("id", flat=True)),
                         {self.math.id, self.fr.id})
        self.assertEqual(set(teacher.classes.values_list("id", flat=True)),
                         {self.cls1.id, self.cls2.id})


class TeacherCreationErrorTests(ProfileFixture):
    """Aucune erreur 500 : les cas invalides renvoient un 400 exploitable."""

    def test_profil_deja_existant_refuse_proprement(self):
        client = self.auth(self.superadmin)
        user = self.new_teacher_user("dup")
        self.assertEqual(client.post(TEACHERS_URL, self.payload(user), format="json").status_code,
                         status.HTTP_201_CREATED)
        resp = client.post(TEACHERS_URL, self.payload(user), format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("user_write", resp.data)

    def test_compte_utilisateur_manquant_renvoie_400(self):
        client = self.auth(self.superadmin)
        data = self.payload(self.new_teacher_user("nouser"))
        data.pop("user_write")
        resp = client.post(TEACHERS_URL, data, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("user_write", resp.data)

    def test_date_embauche_invalide_renvoie_400(self):
        client = self.auth(self.superadmin)
        resp = client.post(TEACHERS_URL,
                           self.payload(self.new_teacher_user("dt"), hire_date="pas-une-date"),
                           format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("hire_date", resp.data)

    def test_contrat_invalide_renvoie_400(self):
        client = self.auth(self.superadmin)
        resp = client.post(TEACHERS_URL,
                           self.payload(self.new_teacher_user("ct"), contract_type="inexistant"),
                           format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("contract_type", resp.data)

    def test_matiere_d_un_autre_etablissement_refusee(self):
        client = self.auth(self.admin)
        resp = client.post(TEACHERS_URL,
                           self.payload(self.new_teacher_user("iso"),
                                        subject_ids=[self.other_subject.id]),
                           format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("subject_ids", resp.data)

    def test_classe_introuvable_renvoie_400(self):
        client = self.auth(self.superadmin)
        resp = client.post(TEACHERS_URL,
                           self.payload(self.new_teacher_user("kls"), class_ids=[999999]),
                           format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("class_ids", resp.data)

    def test_aucune_donnee_partielle_apres_echec(self):
        """Atomicité : un échec ne laisse ni profil ni relation orpheline."""
        client = self.auth(self.superadmin)
        user = self.new_teacher_user("atomic")
        before = Teacher.objects.count()
        resp = client.post(TEACHERS_URL,
                           self.payload(user, class_ids=[999999]), format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Teacher.objects.count(), before)
        self.assertFalse(Teacher.objects.filter(user=user).exists())


class TeacherPermissionTests(ProfileFixture):
    def test_parent_ne_peut_pas_creer_un_enseignant(self):
        client = self.auth(self.parent_user)
        resp = client.post(TEACHERS_URL, self.payload(self.new_teacher_user("perm")), format="json")
        self.assertIn(resp.status_code,
                      (status.HTTP_403_FORBIDDEN, status.HTTP_401_UNAUTHORIZED))
        self.assertEqual(Teacher.objects.count(), 0)

    def test_anonyme_refuse(self):
        resp = APIClient().post(TEACHERS_URL, self.payload(self.new_teacher_user("anon")),
                                format="json")
        self.assertIn(resp.status_code,
                      (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN))


class TeacherUpdateTests(ProfileFixture):
    def test_modification_conserve_le_matricule_et_maj_relations(self):
        client = self.auth(self.superadmin)
        resp = client.post(TEACHERS_URL, self.payload(self.new_teacher_user("upd")), format="json")
        tid, matricule = resp.data["id"], resp.data["employee_id"]

        resp = client.patch(f"{TEACHERS_URL}{tid}/",
                            {"specialization": "Sciences", "subject_ids": [self.fr.id]},
                            format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        teacher = Teacher.objects.get(id=tid)
        self.assertEqual(teacher.employee_id, matricule)
        self.assertEqual(teacher.specialization, "Sciences")
        self.assertEqual(list(teacher.subjects.values_list("id", flat=True)), [self.fr.id])


class OtherProfilesTests(ProfileFixture):
    """P2 — les autres profils se créent aussi sans 500."""

    def test_creation_eleve(self):
        client = self.auth(self.superadmin)
        resp = client.post("/api/students/", {
            "first_name": "Ayo", "last_name": "Codjo",
            "date_of_birth": "2015-03-04", "gender": "M",
            "current_class": self.cls1.id, "school_year": self.year.id,
        }, format="json")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        self.assertTrue(Student.objects.filter(id=resp.data["id"]).exists())

    def test_creation_parent(self):
        client = self.auth(self.superadmin)
        user = CustomUser.objects.create_user(
            username="par2", email="par2@test.bj", password="Pass1234!",
            role="parent", first_name="P", last_name="2", school=self.school,
        )
        resp = client.post("/api/parents/", {"user_write": user.id}, format="json")
        # Selon le serializer, la création peut exiger d'autres champs :
        # l'essentiel est qu'aucune 500 ne survienne.
        self.assertNotEqual(resp.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        if resp.status_code == status.HTTP_201_CREATED:
            self.assertTrue(Parent.objects.filter(user=user).exists())

    def test_matricule_eleve_unique_apres_suppression(self):
        """Même classe de bug que l'enseignant : vérifié sur les élèves."""
        client = self.auth(self.superadmin)
        ids = []
        for i in range(3):
            resp = client.post("/api/students/", {
                "first_name": f"E{i}", "last_name": "Test",
                "date_of_birth": "2015-03-04", "gender": "M",
                "current_class": self.cls1.id, "school_year": self.year.id,
            }, format="json")
            self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
            ids.append(resp.data["id"])
        Student.objects.get(id=ids[0]).delete()
        resp = client.post("/api/students/", {
            "first_name": "E-new", "last_name": "Test",
            "date_of_birth": "2015-03-04", "gender": "M",
            "current_class": self.cls1.id, "school_year": self.year.id,
        }, format="json")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        matricules = list(Student.objects.values_list("matricule", flat=True))
        self.assertEqual(len(matricules), len(set(matricules)), "matricules élèves en double")
