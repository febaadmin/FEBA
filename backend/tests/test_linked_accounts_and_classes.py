"""
Tests — Comptes liés, parents en masse, effectifs et suppression de classes (FIX v37).

Causes racines couvertes (3 vidéos fournies) :
  1. Créer un élève avec un compte DÉJÀ lié → message clair orientant vers la
     réinscription (avant : IntegrityError 500). Le sélecteur ?unlinked=1
     n'expose que les comptes libres.
  2. Suppression en masse des parents = DÉSACTIVATION réversible ; liens
     familiaux et historique intacts.
  3. L'effectif d'une classe se compte via les inscriptions annuelles
     (les classes des années passées n'affichent plus 0/30).
  4. Une classe référencée par l'historique ne peut pas être supprimée
     (409 avec dépendances), à l'unité comme en masse.
"""
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status

from apps.accounts.models import CustomUser
from apps.classes.models import Class
from apps.parents.models import Parent, ParentStudent
from apps.schools.models import School, SchoolYear, Level
from apps.students.models import Student, StudentEnrollment


def auth(client, email, password="Pass1234!"):
    resp = client.post("/api/auth/login/", {"email": email, "password": password})
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {resp.data.get('access', '')}")


class BaseSetup(TestCase):
    def setUp(self):
        self.school = School.objects.create(name="Ecole V37", address="X")
        self.year = SchoolYear.objects.create(
            school=self.school, name="2025-2026", is_current=True,
            start_date="2025-10-01", end_date="2026-07-31",
        )
        lvl = Level.objects.create(school=self.school, name="CP1", order=1)
        self.cls = Class.objects.create(name="CP1-A", level=lvl, school_year=self.year)
        self.admin = CustomUser.objects.create_user(
            username="a37", email="a37@test.bj", password="Pass1234!",
            role="admin", first_name="A", last_name="V", school=self.school,
        )
        self.client = APIClient()
        auth(self.client, "a37@test.bj")


class LinkedAccountTests(BaseSetup):
    def setUp(self):
        super().setUp()
        self.linked_user = CustomUser.objects.create_user(
            username="est", email="eleve5@test.bj", password="Pass1234!",
            role="student", first_name="Estelle", last_name="Acakpo", school=self.school,
        )
        self.free_user = CustomUser.objects.create_user(
            username="lib", email="libre@test.bj", password="Pass1234!",
            role="student", first_name="Libre", last_name="Compte", school=self.school,
        )
        self.existing = Student.objects.create(
            user=self.linked_user, school=self.school,
            first_name="Estelle", last_name="Acakpo",
            current_class=self.cls, school_year=self.year,
        )

    def test_unlinked_filter_hides_linked_accounts(self):
        resp = self.client.get("/api/auth/users/?role=student&unlinked=1")
        emails = [u["email"] for u in resp.data.get("results", resp.data)]
        self.assertIn("libre@test.bj", emails)
        self.assertNotIn("eleve5@test.bj", emails)   # déjà lié → masqué

    def test_creating_student_with_linked_account_gives_clear_error(self):
        """Scénario vidéo 1 : plus d'IntegrityError 500, message orientant."""
        resp = self.client.post("/api/students/", {
            "user": self.linked_user.id,
            "first_name": "Estelle", "last_name": "Acakpo",
            "school_year": self.year.id,
        }, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        msg = str(resp.data.get("user", ""))
        self.assertIn("déjà associé", msg)
        self.assertIn("Inscription individuelle", msg)
        # Aucun doublon d'identité créé
        self.assertEqual(Student.objects.filter(user=self.linked_user).count(), 1)


class ParentsBulkSoftTests(BaseSetup):
    def setUp(self):
        super().setUp()
        self.parents = []
        for i in range(3):
            u = CustomUser.objects.create_user(
                username=f"p37{i}", email=f"p37{i}@test.bj", password="Pass1234!",
                role="parent", first_name=f"P{i}", last_name="V", school=self.school,
            )
            p = Parent.objects.create(user=u)
            s = Student.objects.create(
                school=self.school, first_name=f"E{i}", last_name="V",
                current_class=self.cls, school_year=self.year,
            )
            StudentEnrollment.objects.create(student=s, school_year=self.year, class_obj=self.cls)
            ParentStudent.objects.create(parent=p, student=s, relationship="father")
            self.parents.append(p)

    def test_bulk_delete_deactivates_and_preserves_links(self):
        """Scénario vidéo 2 : plus de destruction en masse."""
        ids = [p.id for p in self.parents]
        resp = self.client.post("/api/parents/bulk-delete/", {"ids": ids}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data.get("soft"))
        for p in self.parents:
            self.assertTrue(Parent.objects.filter(pk=p.pk).exists())      # non détruit
            p.user.refresh_from_db()
            self.assertFalse(p.user.is_active)                            # désactivé
            self.assertEqual(p.children_links.count(), 1)                 # liens intacts


class ClassCountAndDeletionTests(BaseSetup):
    def setUp(self):
        super().setUp()
        self.prev_year = SchoolYear.objects.create(
            school=self.school, name="2024-2025",
            start_date="2024-10-01", end_date="2025-07-31",
        )
        self.prev_cls = Class.objects.create(
            name="CP1-A", level=self.cls.level, school_year=self.prev_year,
        )
        self.student = Student.objects.create(
            school=self.school, first_name="K", last_name="C",
            current_class=self.cls, school_year=self.year,   # pointeur = année courante
        )
        StudentEnrollment.objects.create(student=self.student, school_year=self.prev_year, class_obj=self.prev_cls)
        StudentEnrollment.objects.create(student=self.student, school_year=self.year, class_obj=self.cls)

    def test_past_year_class_counts_enrollments_not_pointer(self):
        """Scénario vidéo 3 : la classe 2024-2025 n'affiche plus 0."""
        resp = self.client.get(f"/api/classes/?school_year={self.prev_year.id}")
        row = [c for c in resp.data.get("results", resp.data) if c["id"] == self.prev_cls.id][0]
        self.assertEqual(row["student_count"], 1)

    def test_class_with_history_cannot_be_deleted(self):
        resp = self.client.delete(f"/api/classes/{self.prev_cls.id}/")
        self.assertEqual(resp.status_code, 409)
        self.assertIn("inscriptions", str(resp.data))
        self.assertTrue(Class.objects.filter(pk=self.prev_cls.pk).exists())

    def test_bulk_delete_blocks_referenced_classes_only(self):
        empty = Class.objects.create(name="Vide-A", level=self.cls.level, school_year=self.year)
        resp = self.client.post("/api/classes/bulk-delete/",
                                {"ids": [empty.id, self.prev_cls.id]}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["deleted"], 1)
        self.assertIn("CP1-A", resp.data.get("blocked", []))
        self.assertFalse(Class.objects.filter(pk=empty.pk).exists())
        self.assertTrue(Class.objects.filter(pk=self.prev_cls.pk).exists())


class CopyClassesBetweenYearsTests(BaseSetup):
    """FIX v38 — ouverture d'année : copie des classes (idempotente, matières incluses)."""

    def setUp(self):
        super().setUp()
        from apps.subjects.models import Subject
        self.new_year = SchoolYear.objects.create(
            school=self.school, name="2026-2027",
            start_date="2026-10-01", end_date="2027-07-31",
        )
        self.math = Subject.objects.create(school=self.school, name="Maths", code="MATH", coefficient=4)
        self.cls.subjects.set([self.math])
        lvl2 = Level.objects.create(school=self.school, name="CP2", order=2)
        self.cls2 = Class.objects.create(name="CP2-A", level=lvl2, school_year=self.year, max_students=25)

    def test_copy_creates_classes_with_subjects(self):
        resp = self.client.post("/api/classes/copy-from-year/", {
            "source_year_id": self.year.id, "target_year_id": self.new_year.id,
        }, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        self.assertEqual(resp.data["created"], 2)
        copied = Class.objects.get(name="CP1-A", school_year=self.new_year)
        self.assertEqual(copied.level_id, self.cls.level_id)
        self.assertEqual(list(copied.subjects.values_list("id", flat=True)), [self.math.id])
        self.assertEqual(Class.objects.get(name="CP2-A", school_year=self.new_year).max_students, 25)

    def test_copy_is_idempotent_skips_existing(self):
        self.client.post("/api/classes/copy-from-year/", {
            "source_year_id": self.year.id, "target_year_id": self.new_year.id,
        }, format="json")
        resp2 = self.client.post("/api/classes/copy-from-year/", {
            "source_year_id": self.year.id, "target_year_id": self.new_year.id,
        }, format="json")
        self.assertEqual(resp2.data["created"], 0)
        self.assertEqual(resp2.data["skipped"], 2)
        self.assertEqual(Class.objects.filter(school_year=self.new_year).count(), 2)

    def test_copy_same_year_rejected(self):
        resp = self.client.post("/api/classes/copy-from-year/", {
            "source_year_id": self.year.id, "target_year_id": self.year.id,
        }, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)


class CrossYearClassDetailTests(BaseSetup):
    """
    FIX v40 (404 console) : éditer/supprimer/consulter une classe d'une année
    NON active ne doit pas renvoyer 404. Le filtre « année active par défaut »
    ne s'applique qu'à la LISTE, pas aux actions de détail.
    """
    def setUp(self):
        super().setUp()   # self.year est active (2025-2026), self.cls dedans
        self.past_year = SchoolYear.objects.create(
            school=self.school, name="2023-2024",
            start_date="2023-10-01", end_date="2024-07-31",
        )
        self.past_cls = Class.objects.create(
            name="6eme-A", level=self.cls.level, school_year=self.past_year,
        )

    def test_list_defaults_to_active_year_only(self):
        resp = self.client.get("/api/classes/")
        ids = {c["id"] for c in resp.data.get("results", resp.data)}
        self.assertIn(self.cls.id, ids)          # année active
        self.assertNotIn(self.past_cls.id, ids)  # année passée exclue de la LISTE

    def test_retrieve_past_year_class_ok(self):
        resp = self.client.get(f"/api/classes/{self.past_cls.id}/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)   # plus de 404
        self.assertEqual(resp.data["name"], "6eme-A")

    def test_update_past_year_class_ok(self):
        resp = self.client.patch(f"/api/classes/{self.past_cls.id}/",
                                 {"max_students": 40}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)   # plus de 404
        self.past_cls.refresh_from_db()
        self.assertEqual(self.past_cls.max_students, 40)

    def test_delete_empty_past_year_class_ok(self):
        resp = self.client.delete(f"/api/classes/{self.past_cls.id}/")
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)  # plus de 404
        self.assertFalse(Class.objects.filter(pk=self.past_cls.pk).exists())
