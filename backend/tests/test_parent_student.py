"""
Tests — Parent ↔ Élève (FEBA v29)

Changements v29 par rapport à la v8 :
  - Un élève peut désormais avoir PLUSIEURS parents (la contrainte DB
    "un seul parent par élève" a été supprimée). Les anciens tests qui
    vérifiaient un 409 Conflict sur double-affectation ont été
    remplacés par des tests qui vérifient que les DEUX affectations
    réussissent.
  - Isolation multi-tenant : nouveaux tests vérifiant qu'un admin (ou
    un parent) d'un établissement ne peut pas voir/lier les données
    d'un autre établissement.

Couverture :
  1. Création d'un profil Parent via POST /api/parents/
  2. Création d'un profil Étudiant via POST /api/students/
  3. Affectation Parent ↔ Élève via POST /api/parents/{id}/link_student/
  4. Affectation d'un SECOND parent au même élève → succès (plus de 409)
  5. Assign_child endpoint (detail=False)
  6. Remove/unlink student
  7. Concurrence simulée (deux parents différents, en parallèle)
  8. Plusieurs parents simultanés en base (DB ne bloque plus)
  9. Validation rôle utilisateur incorrect
 10. check_child_assignment endpoint (liste de parents)
 11. Isolation multi-tenant (établissement A ne voit/ne touche pas B)
 12. parent_user_id — liaison rapide depuis le serializer Student
"""
import threading
from django.test import TestCase, TransactionTestCase
from rest_framework.test import APIClient
from rest_framework import status
from apps.accounts.models import CustomUser
from apps.parents.models import Parent, ParentStudent
from apps.students.models import Student
from apps.schools.models import School


# ── Helpers ──────────────────────────────────────────────────────────────────

_DEFAULT_SCHOOL = {}


def make_school(name="École Test FEBA"):
    return School.objects.create(name=name, address="Cotonou")


def get_default_school():
    """Une école partagée par défaut pour les tests qui n'en testent pas
    explicitement plusieurs (évite de créer 50 écoles inutiles).

    FIX : le cache module survivait au rollback effectué entre chaque test
    (TestCase) → les utilisateurs créés ensuite pointaient vers une école
    SUPPRIMÉE de la base, et le login échouait en School.DoesNotExist.
    On revalide donc l'existence de l'école cachée à chaque appel."""
    school = _DEFAULT_SCHOOL.get("school")
    if school is None or not School.objects.filter(pk=school.pk).exists():
        _DEFAULT_SCHOOL["school"] = make_school("École par défaut (tests)")
    return _DEFAULT_SCHOOL["school"]


def make_user(email, role, password="Pass1234!", first_name="Test", last_name="User", school=None):
    if school is None and role != "superadmin":
        school = get_default_school()
    u = CustomUser.objects.create_user(
        username=email.split("@")[0],
        email=email,
        password=password,
        role=role,
        first_name=first_name,
        last_name=last_name,
        school=school,
    )
    return u


def make_admin(school=None):
    return make_user("admin@feba.test", "admin", first_name="Admin", last_name="FEBA", school=school)


def make_student_obj(first_name="Élève", last_name="Test", user=None, school=None):
    """Create a Student instance directly."""
    return Student.objects.create(
        first_name=first_name,
        last_name=last_name,
        user=user,
        school=school or get_default_school(),
    )


def make_parent_obj(user):
    return Parent.objects.create(user=user)


def get_token(client, email, password="Pass1234!"):
    resp = client.post("/api/auth/login/", {"email": email, "password": password})
    return resp.data.get("access", "")


# ── Test Suite ────────────────────────────────────────────────────────────────

class ParentCreationTest(TestCase):
    """Test 1 & 9: POST /api/parents/ — création et validation rôle."""

    def setUp(self):
        self.client = APIClient()
        self.admin = make_admin()
        token = get_token(self.client, self.admin.email)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def test_create_parent_success(self):
        """Création d'un profil parent pour un utilisateur avec rôle 'parent'."""
        parent_user = make_user("parent1@feba.test", "parent", first_name="Marie", last_name="Dupont",
                                 school=self.admin.school)
        resp = self.client.post("/api/parents/", {"user": parent_user.id, "profession": "Médecin"})
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        self.assertTrue(Parent.objects.filter(user=parent_user).exists())

    def test_create_parent_wrong_role_returns_400(self):
        """Création refusée si l'utilisateur n'a pas le rôle 'parent'."""
        teacher_user = make_user("teacher1@feba.test", "teacher", school=self.admin.school)
        resp = self.client.post("/api/parents/", {"user": teacher_user.id})
        self.assertIn(resp.status_code, [status.HTTP_400_BAD_REQUEST, status.HTTP_409_CONFLICT])

    def test_create_parent_duplicate_returns_conflict(self):
        """Un deuxième profil parent pour le même utilisateur → 409."""
        parent_user = make_user("parent2@feba.test", "parent", school=self.admin.school)
        Parent.objects.create(user=parent_user)
        resp = self.client.post("/api/parents/", {"user": parent_user.id})
        self.assertIn(resp.status_code, [status.HTTP_400_BAD_REQUEST, status.HTTP_409_CONFLICT])


class StudentCreationTest(TestCase):
    """Test 2: POST /api/students/ — création élève avec et sans compte."""

    def setUp(self):
        self.client = APIClient()
        self.admin = make_admin()
        token = get_token(self.client, self.admin.email)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def test_create_student_with_user(self):
        student_user = make_user("student1@feba.test", "student", first_name="Kévin", last_name="Martin",
                                  school=self.admin.school)
        resp = self.client.post("/api/students/", {
            "user": student_user.id,
            "first_name": "Kévin",
            "last_name": "Martin",
            "gender": "M",
        })
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        self.assertTrue(Student.objects.filter(user=student_user).exists())
        # L'établissement doit être assigné automatiquement (tenant courant)
        self.assertEqual(Student.objects.get(user=student_user).school_id, self.admin.school_id)

    def test_create_student_without_user(self):
        """Élève sans compte utilisateur (saisie manuelle)."""
        resp = self.client.post("/api/students/", {
            "first_name": "Awa",
            "last_name": "Coulibaly",
            "gender": "F",
        })
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)

    def test_create_student_missing_name_returns_400(self):
        resp = self.client.post("/api/students/", {"gender": "M"})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)


class ParentStudentAssignmentTest(TestCase):
    """Test 3, 4, 5, 6, 10: affectation et désaffectation Parent ↔ Élève (multi-parents)."""

    def setUp(self):
        self.client = APIClient()
        self.admin = make_admin()
        token = get_token(self.client, self.admin.email)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

        self.parent_user = make_user("parent_a@feba.test", "parent", first_name="Jean", last_name="Parent",
                                      school=self.admin.school)
        self.parent = make_parent_obj(self.parent_user)
        self.student = make_student_obj(first_name="Paul", last_name="Élève", school=self.admin.school)

    def test_link_student_success(self):
        """POST /api/parents/{id}/link_student/ — 201."""
        resp = self.client.post(
            f"/api/parents/{self.parent.id}/link_student/",
            {"student_id": self.student.id},
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        self.assertTrue(
            ParentStudent.objects.filter(parent=self.parent, student=self.student).exists()
        )

    def test_link_student_idempotent(self):
        """Re-lier le même élève au même parent → 200 (mise à jour, pas de doublon)."""
        ParentStudent.objects.create(parent=self.parent, student=self.student)
        resp = self.client.post(
            f"/api/parents/{self.parent.id}/link_student/",
            {"student_id": self.student.id},
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_link_second_parent_now_succeeds(self):
        """
        v29 : affecter un élève à un DEUXIÈME parent réussit désormais
        (au lieu du 409 Conflict de la v8). L'élève a alors bien 2 parents.
        """
        other_parent_user = make_user("parent_b@feba.test", "parent", first_name="Autre", last_name="Parent",
                                       school=self.admin.school)
        other_parent = make_parent_obj(other_parent_user)
        ParentStudent.objects.create(parent=other_parent, student=self.student)

        resp = self.client.post(
            f"/api/parents/{self.parent.id}/link_student/",
            {"student_id": self.student.id, "relationship": "father"},
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        self.assertEqual(
            ParentStudent.objects.filter(student=self.student).count(), 2,
            "L'élève devrait maintenant avoir 2 parents enregistrés.",
        )

    def test_assign_child_endpoint(self):
        """POST /api/parents/assign_child/ — detail=False endpoint."""
        student2 = make_student_obj(first_name="Léa", last_name="Test", school=self.admin.school)
        resp = self.client.post("/api/parents/assign_child/", {
            "parent_id": self.parent.id,
            "student_id": student2.id,
            "relationship": "mother",
        })
        self.assertIn(resp.status_code, [status.HTTP_200_OK, status.HTTP_201_CREATED])

    def test_assign_child_second_parent_now_succeeds(self):
        """v29 : assign_child n'est plus bloqué par un parent déjà existant."""
        other_pu = make_user("parent_c@feba.test", "parent", school=self.admin.school)
        other_p = make_parent_obj(other_pu)
        ParentStudent.objects.create(parent=other_p, student=self.student)

        resp = self.client.post("/api/parents/assign_child/", {
            "parent_id": self.parent.id,
            "student_id": self.student.id,
        })
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)

    def test_unlink_student(self):
        """POST /api/parents/{id}/unlink_student/ — suppression du lien."""
        ParentStudent.objects.create(parent=self.parent, student=self.student)
        resp = self.client.post(
            f"/api/parents/{self.parent.id}/unlink_student/",
            {"student_id": self.student.id},
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertFalse(
            ParentStudent.objects.filter(parent=self.parent, student=self.student).exists()
        )

    def test_check_child_assignment_lists_all_parents(self):
        """
        GET /api/parents/check_child_assignment/?student_id= → v29 : retourne
        la LISTE de tous les parents (et plus un seul `parent_id`).
        """
        other_pu = make_user("parent_d@feba.test", "parent", school=self.admin.school)
        other_p = make_parent_obj(other_pu)
        ParentStudent.objects.create(parent=self.parent, student=self.student)
        ParentStudent.objects.create(parent=other_p, student=self.student)

        resp = self.client.get(
            "/api/parents/check_child_assignment/",
            {"student_id": self.student.id},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data["assigned"])
        self.assertEqual(len(resp.data["parents"]), 2)

    def test_check_child_assignment_free(self):
        """GET /api/parents/check_child_assignment/?student_id= → assigned=False."""
        resp = self.client.get(
            "/api/parents/check_child_assignment/",
            {"student_id": self.student.id},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.data["assigned"])


class ParentStudentMultipleParentsDbTest(TestCase):
    """Test 8: la base de données autorise désormais plusieurs parents par élève."""

    def test_db_allows_two_parents_for_same_student(self):
        pu1 = make_user("db_parent1@feba.test", "parent")
        pu2 = make_user("db_parent2@feba.test", "parent")
        p1 = make_parent_obj(pu1)
        p2 = make_parent_obj(pu2)
        student = make_student_obj()

        ParentStudent.objects.create(parent=p1, student=student)
        # v29 : ceci NE doit PLUS lever d'IntegrityError.
        ParentStudent.objects.create(parent=p2, student=student)
        self.assertEqual(ParentStudent.objects.filter(student=student).count(), 2)


class ParentStudentConcurrencyTest(TransactionTestCase):
    """
    Test 7: Concurrence — deux parents différents tentent de se lier au
    même élève simultanément. Les DEUX doivent réussir (multi-parents),
    et aucun doublon ne doit être créé.
    """

    def setUp(self):
        self.admin = make_admin()
        self.client = APIClient()
        token = get_token(self.client, self.admin.email)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def test_concurrent_assignment_both_succeed(self):
        pu1 = make_user("conc_parent1@feba.test", "parent", school=self.admin.school)
        pu2 = make_user("conc_parent2@feba.test", "parent", school=self.admin.school)
        p1 = make_parent_obj(pu1)
        p2 = make_parent_obj(pu2)
        student = make_student_obj(first_name="Concurrent", last_name="Test", school=self.admin.school)

        results = []
        barrier = threading.Barrier(2)

        def assign(parent, result_list):
            try:
                c = APIClient()
                c.force_authenticate(user=self.admin)
                barrier.wait()  # synchronise les deux threads
                resp = c.post(
                    f"/api/parents/{parent.id}/link_student/",
                    {"student_id": student.id},
                )
                result_list.append(resp.status_code)
            finally:
                # FIX : chaque thread ouvre sa propre connexion DB ; sans
                # fermeture explicite, la destruction de la base de test
                # échouait ("database is being accessed by 2 other sessions").
                from django.db import connections
                connections.close_all()

        t1 = threading.Thread(target=assign, args=(p1, results))
        t2 = threading.Thread(target=assign, args=(p2, results))
        t1.start()
        t2.start()
        t1.join(timeout=10)
        t2.join(timeout=10)

        # Les deux liens doivent exister (un par parent), pas de doublon.
        link_count = ParentStudent.objects.filter(student=student).count()
        self.assertEqual(link_count, 2, f"Attendu 2 liens (un par parent), trouvé: {link_count}")
        self.assertEqual(results.count(status.HTTP_201_CREATED), 2)


class StudentWithParentCreationTest(TestCase):
    """Test parent_user_id — flux de liaison rapide depuis le serializer Student."""

    def setUp(self):
        self.client = APIClient()
        self.admin = make_admin()
        token = get_token(self.client, self.admin.email)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def test_create_student_with_parent_user_id(self):
        """Création élève + lien parent en une requête via parent_user_id."""
        pu = make_user("stu_parent@feba.test", "parent", school=self.admin.school)
        parent = make_parent_obj(pu)
        su = make_user("stu_user@feba.test", "student", first_name="Chloé", last_name="Moreau",
                        school=self.admin.school)
        resp = self.client.post("/api/students/", {
            "user": su.id,
            "first_name": "Chloé",
            "last_name": "Moreau",
            "parent_user_id": pu.id,
        })
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        student = Student.objects.get(user=su)
        self.assertTrue(ParentStudent.objects.filter(parent=parent, student=student).exists())

    def test_add_second_parent_via_patch_now_succeeds(self):
        """
        v29 : lier un DEUXIÈME parent via PATCH /students/{id}/ réussit
        désormais (au lieu de l'erreur 400/409 de la v8) — l'élève a
        alors 2 parents.
        """
        pu1 = make_user("sp1@feba.test", "parent", school=self.admin.school)
        pu2 = make_user("sp2@feba.test", "parent", school=self.admin.school)
        parent1 = make_parent_obj(pu1)
        make_parent_obj(pu2)
        su = make_user("sp_stu@feba.test", "student", first_name="Tom", last_name="Legrand",
                        school=self.admin.school)
        student = make_student_obj(first_name="Tom", last_name="Legrand", user=su, school=self.admin.school)
        ParentStudent.objects.create(parent=parent1, student=student)

        resp = self.client.patch(f"/api/students/{student.id}/", {
            "parent_user_id": pu2.id,
        })
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        self.assertEqual(ParentStudent.objects.filter(student=student).count(), 2)


class MultiTenantIsolationTest(TestCase):
    """
    Test 11 : deux établissements (tenants) distincts ne doivent JAMAIS
    se voir ni interagir, quel que soit l'endpoint utilisé.
    """

    def setUp(self):
        self.school_a = make_school("Établissement A")
        self.school_b = make_school("Établissement B")
        self.admin_a = make_admin_for_school(self.school_a, "admin_a@feba.test")
        self.admin_b = make_admin_for_school(self.school_b, "admin_b@feba.test")

        self.client_a = APIClient()
        self.client_a.credentials(HTTP_AUTHORIZATION=f"Bearer {get_token(self.client_a, self.admin_a.email)}")
        self.client_b = APIClient()
        self.client_b.credentials(HTTP_AUTHORIZATION=f"Bearer {get_token(self.client_b, self.admin_b.email)}")

        self.student_a = make_student_obj(first_name="Eleve", last_name="A", school=self.school_a)
        self.student_b = make_student_obj(first_name="Eleve", last_name="B", school=self.school_b)

    def test_admin_a_cannot_list_student_b(self):
        resp = self.client_a.get("/api/students/")
        ids = [s["id"] for s in resp.data.get("results", resp.data)]
        self.assertNotIn(self.student_b.id, ids)
        self.assertIn(self.student_a.id, ids)

    def test_admin_a_cannot_retrieve_student_b_by_id(self):
        resp = self.client_a.get(f"/api/students/{self.student_b.id}/")
        self.assertIn(resp.status_code, [403, 404])

    def test_admin_a_cannot_link_parent_to_student_b(self):
        parent_user_a = make_user("parent_school_a@feba.test", "parent", school=self.school_a)
        parent_a = make_parent_obj(parent_user_a)
        resp = self.client_a.post(
            f"/api/parents/{parent_a.id}/link_student/",
            {"student_id": self.student_b.id},
        )
        self.assertEqual(resp.status_code, 404)

    def test_matricule_can_be_identical_across_two_schools(self):
        """
        Le matricule n'est unique que PAR établissement : deux écoles
        clientes différentes doivent pouvoir attribuer le même
        matricule sans collision.
        """
        s1 = Student.objects.create(first_name="X", last_name="Y", school=self.school_a, matricule="ECOLE-0001")
        s2 = Student.objects.create(first_name="X", last_name="Z", school=self.school_b, matricule="ECOLE-0001")
        self.assertEqual(s1.matricule, s2.matricule)
        self.assertNotEqual(s1.school_id, s2.school_id)


def make_admin_for_school(school, email):
    return make_user(email, "admin", first_name="Admin", last_name=school.name, school=school)
