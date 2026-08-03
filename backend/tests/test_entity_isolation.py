"""
Tests d'ISOLATION INTER-ENTITÉS (anti-IDOR, anti-fuite).

Chaque test répond à une exigence explicite du cahier des charges :
  1. un Admin FEBA ne voit aucun utilisateur FHA ;
  2. un Admin FHA ne voit aucun utilisateur FEBA ;
  3. un Enseignant FEBA ne voit aucun élève FHA ;
  4. un Enseignant FHA ne voit aucun élève FEBA ;
  5. un Parent ne voit que ses enfants, dans son entité ;
  6. un Élève ne voit que ses données ;
  7. une modification manuelle d'ID retourne 403 ou 404 ;
  8. un entity_id / school_id falsifié est ignoré ou rejeté ;
  9. les statistiques et recherches restent séparées.

Le point 8 est le plus important : c'est la tentative d'évasion la plus
simple à faire depuis un navigateur.
"""
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import CustomUser
from apps.classes.models import Class
from apps.schools.models import Level, School, SchoolYear
from apps.students.models import Student
from apps.teachers.models import Teacher


def auth(client, email, password="Pass1234!"):
    resp = client.post("/api/auth/login/", {"email": email, "password": password})
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {resp.data.get('access', '')}")
    return client


def rows(resp):
    """Lignes d'une réponse paginée ou non."""
    data = resp.data
    if isinstance(data, dict) and "results" in data:
        return data["results"]
    return data


class CrossEntityIsolationTests(TestCase):
    """Deux entités complètes, peuplées symétriquement."""

    @classmethod
    def setUpTestData(cls):
        cls.feba = School.objects.create(
            name="FEBA Cotonou", address="Akpakpa", entity_type="campus",
            code="ISO-FEBA",
        )
        cls.fha = School.objects.create(
            name="FEBA FHA", address="En ligne", entity_type="online",
            code="ISO-FHA",
        )

        cls.data = {}
        for key, school in (("feba", cls.feba), ("fha", cls.fha)):
            year = SchoolYear.objects.create(
                school=school, name=f"2025-2026-{key}", is_current=True,
                start_date="2025-09-01", end_date="2026-06-30",
            )
            level = Level.objects.create(school=school, name=f"N-{key}", order=1)
            klass = Class.objects.create(
                school_year=year, level=level, name=f"Classe {key}",
            )

            admin = CustomUser.objects.create_user(
                username=f"admin_{key}", email=f"admin.{key}@test.io",
                password="Pass1234!", role="admin", school=school,
                first_name="Admin", last_name=key.upper(),
            )
            teacher_user = CustomUser.objects.create_user(
                username=f"teacher_{key}", email=f"teacher.{key}@test.io",
                password="Pass1234!", role="teacher", school=school,
                first_name="Teacher", last_name=key.upper(),
            )
            # Teacher n'a pas de champ `school` : son entité est celle de
            # son compte utilisateur (user.school). C'est ce rattachement
            # qui est filtré par l'isolation.
            teacher = Teacher.objects.create(user=teacher_user)
            student_user = CustomUser.objects.create_user(
                username=f"student_{key}", email=f"student.{key}@test.io",
                password="Pass1234!", role="student", school=school,
                first_name="Eleve", last_name=key.upper(),
            )
            student = Student.objects.create(
                user=student_user, school=school, current_class=klass,
                # `school_year` est requis pour apparaître dans les KPI du
                # tableau de bord, qui filtrent sur l'année active.
                school_year=year,
                first_name="Eleve", last_name=key.upper(),
                date_of_birth="2015-01-01",
            )
            cls.data[key] = {
                "school": school, "year": year, "level": level, "class": klass,
                "admin": admin, "teacher_user": teacher_user, "teacher": teacher,
                "student_user": student_user, "student": student,
            }

    # ── 1 & 2 : utilisateurs ────────────────────────────────────────────

    def test_feba_admin_sees_no_fha_users(self):
        client = auth(APIClient(), "admin.feba@test.io")
        emails = [u["email"] for u in rows(client.get("/api/auth/users/"))]
        self.assertIn("teacher.feba@test.io", emails)
        for foreign in ("admin.fha@test.io", "teacher.fha@test.io", "student.fha@test.io"):
            self.assertNotIn(foreign, emails)

    def test_fha_admin_sees_no_feba_users(self):
        client = auth(APIClient(), "admin.fha@test.io")
        emails = [u["email"] for u in rows(client.get("/api/auth/users/"))]
        self.assertIn("teacher.fha@test.io", emails)
        for foreign in ("admin.feba@test.io", "teacher.feba@test.io", "student.feba@test.io"):
            self.assertNotIn(foreign, emails)

    # ── 3 & 4 : élèves ──────────────────────────────────────────────────

    def test_feba_admin_sees_no_fha_students(self):
        client = auth(APIClient(), "admin.feba@test.io")
        ids = [s["id"] for s in rows(client.get("/api/students/"))]
        self.assertIn(self.data["feba"]["student"].id, ids)
        self.assertNotIn(self.data["fha"]["student"].id, ids)

    def test_fha_admin_sees_no_feba_students(self):
        client = auth(APIClient(), "admin.fha@test.io")
        ids = [s["id"] for s in rows(client.get("/api/students/"))]
        self.assertIn(self.data["fha"]["student"].id, ids)
        self.assertNotIn(self.data["feba"]["student"].id, ids)

    def test_feba_teacher_sees_no_fha_students(self):
        client = auth(APIClient(), "teacher.feba@test.io")
        ids = [s["id"] for s in rows(client.get("/api/students/"))]
        self.assertNotIn(self.data["fha"]["student"].id, ids)

    def test_fha_teacher_sees_no_feba_students(self):
        client = auth(APIClient(), "teacher.fha@test.io")
        ids = [s["id"] for s in rows(client.get("/api/students/"))]
        self.assertNotIn(self.data["feba"]["student"].id, ids)

    # ── 5 : classes ─────────────────────────────────────────────────────

    def test_classes_are_isolated(self):
        client = auth(APIClient(), "admin.feba@test.io")
        ids = [c["id"] for c in rows(client.get("/api/classes/"))]
        self.assertNotIn(self.data["fha"]["class"].id, ids)

    # ── 7 : anti-IDOR par modification d'URL ────────────────────────────

    def test_direct_id_access_to_foreign_student_is_refused(self):
        client = auth(APIClient(), "admin.feba@test.io")
        foreign_id = self.data["fha"]["student"].id
        resp = client.get(f"/api/students/{foreign_id}/")
        self.assertIn(
            resp.status_code,
            (status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND),
            "Un élève d'une autre entité ne doit jamais être lisible par ID.",
        )

    def test_direct_id_update_of_foreign_student_is_refused(self):
        client = auth(APIClient(), "admin.feba@test.io")
        foreign = self.data["fha"]["student"]
        resp = client.patch(
            f"/api/students/{foreign.id}/", {"first_name": "Piraté"}, format="json",
        )
        self.assertIn(
            resp.status_code,
            (status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND),
        )
        foreign.refresh_from_db()
        self.assertNotEqual(foreign.first_name, "Piraté")

    def test_direct_id_delete_of_foreign_student_is_refused(self):
        client = auth(APIClient(), "admin.feba@test.io")
        foreign = self.data["fha"]["student"]
        resp = client.delete(f"/api/students/{foreign.id}/")
        self.assertIn(
            resp.status_code,
            (status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND),
        )
        self.assertTrue(Student.objects.filter(pk=foreign.pk).exists())

    def test_direct_id_access_to_foreign_user_is_refused(self):
        client = auth(APIClient(), "admin.feba@test.io")
        foreign_id = self.data["fha"]["teacher_user"].id
        resp = client.get(f"/api/auth/users/{foreign_id}/")
        self.assertIn(
            resp.status_code,
            (status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND),
        )

    # ── 8 : falsification de l'entité par le client ─────────────────────

    def test_forged_school_id_query_param_is_ignored_for_admin(self):
        """
        Un admin qui ajoute `?school_id=<autre entité>` — le paramètre
        réservé au support superadmin — ne doit RIEN gagner.
        """
        client = auth(APIClient(), "admin.feba@test.io")
        foreign_school = self.data["fha"]["school"].id
        resp = client.get(f"/api/students/?school_id={foreign_school}")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        ids = [s["id"] for s in rows(resp)]
        self.assertNotIn(self.data["fha"]["student"].id, ids)
        # Il continue de voir sa propre entité, inchangée.
        self.assertIn(self.data["feba"]["student"].id, ids)

    def test_forged_entity_id_in_payload_cannot_move_a_student(self):
        """
        Envoyer `school`/`entity` dans le corps ne doit pas rattacher un
        élève à une autre entité.
        """
        client = auth(APIClient(), "admin.feba@test.io")
        student = self.data["feba"]["student"]
        foreign_school = self.data["fha"]["school"].id
        client.patch(
            f"/api/students/{student.id}/",
            {"school": foreign_school, "entity": foreign_school, "entity_id": foreign_school},
            format="json",
        )
        student.refresh_from_db()
        self.assertEqual(
            student.school_id, self.data["feba"]["school"].id,
            "Un élève ne doit jamais changer d'entité via un payload client.",
        )

    def test_admin_cannot_create_user_in_another_entity(self):
        """
        Un admin FEBA qui force `school` vers FHA doit soit être refusé,
        soit voir le compte créé DANS SON ENTITÉ — jamais dans l'autre.
        """
        client = auth(APIClient(), "admin.feba@test.io")
        foreign_school = self.data["fha"]["school"].id
        resp = client.post("/api/auth/users/", {
            "email": "intrus@test.io", "username": "intrus",
            "first_name": "In", "last_name": "Trus",
            "role": "teacher", "password": "Pass1234!",
            "school": foreign_school,
        }, format="json")

        created = CustomUser.objects.filter(email="intrus@test.io").first()
        if resp.status_code in (status.HTTP_200_OK, status.HTTP_201_CREATED):
            self.assertIsNotNone(created)
            self.assertNotEqual(
                created.school_id, foreign_school,
                "Un admin ne doit jamais créer d'utilisateur dans une autre entité.",
            )
        else:
            self.assertIn(
                resp.status_code,
                (status.HTTP_400_BAD_REQUEST, status.HTTP_403_FORBIDDEN),
            )

    # ── 6 : périmètre de l'élève ────────────────────────────────────────

    def test_student_cannot_list_all_users(self):
        client = auth(APIClient(), "student.feba@test.io")
        resp = client.get("/api/auth/users/")
        if resp.status_code == status.HTTP_200_OK:
            emails = [u["email"] for u in rows(resp)]
            self.assertNotIn("student.fha@test.io", emails)
        else:
            self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_student_cannot_read_foreign_student(self):
        client = auth(APIClient(), "student.feba@test.io")
        resp = client.get(f"/api/students/{self.data['fha']['student'].id}/")
        self.assertIn(
            resp.status_code,
            (status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND),
        )

    # ── 9 : statistiques et recherche ───────────────────────────────────

    def test_dashboard_statistics_are_separated(self):
        feba_client = auth(APIClient(), "admin.feba@test.io")
        fha_client = auth(APIClient(), "admin.fha@test.io")

        feba_resp = feba_client.get("/api/dashboard/admin/")
        fha_resp = fha_client.get("/api/dashboard/admin/")

        self.assertEqual(feba_resp.status_code, status.HTTP_200_OK, feba_resp.data)
        self.assertEqual(fha_resp.status_code, status.HTTP_200_OK, fha_resp.data)

        def total_students(payload):
            """Le tableau de bord admin expose ses totaux sous « kpis »."""
            kpis = payload.get("kpis") or {}
            for key in ("total_students", "students", "students_count", "nb_students"):
                if key in kpis:
                    return kpis[key]
            raise AssertionError(
                f"Aucun total d'élèves trouvé dans les KPI : {list(kpis)}"
            )

        # Chaque entité ne compte QUE son propre élève : les statistiques
        # ne sont jamais consolidées à l'insu de l'administrateur.
        self.assertEqual(total_students(feba_resp.data), 1)
        self.assertEqual(total_students(fha_resp.data), 1)

    def test_search_does_not_cross_entities(self):
        client = auth(APIClient(), "admin.feba@test.io")
        resp = client.get("/api/students/?search=FHA")
        ids = [s["id"] for s in rows(resp)]
        self.assertNotIn(self.data["fha"]["student"].id, ids)


class SuperAdminScopeTests(TestCase):
    """Le superadmin voit chaque entité, mais une seule à la fois."""

    @classmethod
    def setUpTestData(cls):
        cls.feba = School.objects.create(
            name="FEBA SA", address="Cotonou", entity_type="campus", code="SA-FEBA",
        )
        cls.fha = School.objects.create(
            name="FHA SA", address="En ligne", entity_type="online", code="SA-FHA",
        )
        cls.superadmin = CustomUser.objects.create_user(
            username="su_scope", email="su.scope@test.io", password="Pass1234!",
            role="superadmin", first_name="S", last_name="A",
        )
        for key, school in (("feba", cls.feba), ("fha", cls.fha)):
            year = SchoolYear.objects.create(
                school=school, name=f"2025-2026-sa-{key}", is_current=True,
                start_date="2025-09-01", end_date="2026-06-30",
            )
            level = Level.objects.create(school=school, name=f"L-{key}", order=1)
            klass = Class.objects.create(
                school_year=year, level=level, name=f"C-{key}",
            )
            user = CustomUser.objects.create_user(
                username=f"sa_student_{key}", email=f"sa.student.{key}@test.io",
                password="Pass1234!", role="student", school=school,
                first_name="E", last_name=key.upper(),
            )
            student = Student.objects.create(
                user=user, school=school, current_class=klass,
                first_name="E", last_name=key.upper(), date_of_birth="2015-01-01",
            )
            setattr(cls, f"student_{key}", student)

    def test_superadmin_sees_only_active_entity_data(self):
        client = auth(APIClient(), "su.scope@test.io")

        client.post("/api/auth/entity-context/switch/",
                    {"entity_id": self.feba.id}, format="json")
        ids = [s["id"] for s in rows(client.get("/api/students/"))]
        self.assertIn(self.student_feba.id, ids)
        self.assertNotIn(self.student_fha.id, ids)

        client.post("/api/auth/entity-context/switch/",
                    {"entity_id": self.fha.id}, format="json")
        ids = [s["id"] for s in rows(client.get("/api/students/"))]
        self.assertIn(self.student_fha.id, ids)
        self.assertNotIn(self.student_feba.id, ids)

    def test_superadmin_all_entities_mode_is_consolidated_not_leaky(self):
        """
        Mode « toutes les entités » du superadmin : vue CONSOLIDÉE assumée
        (rôle plateforme / support), et non une fuite d'entité.

        Le point vérifié ici est qu'il s'agit bien d'un choix explicite —
        le superadmin voit les DEUX entités, jamais l'une déguisée en
        l'autre. Dès qu'il sélectionne une entité, le périmètre se
        restreint (cf. test_superadmin_sees_only_active_entity_data).

        Cette permissivité est strictement réservée au rôle superadmin :
        tout autre rôle sans entité reçoit un ensemble vide.
        """
        client = auth(APIClient(), "su.scope@test.io")
        client.post("/api/auth/entity-context/switch/",
                    {"entity_id": None}, format="json")
        ids = [s["id"] for s in rows(client.get("/api/students/"))]
        self.assertIn(self.student_feba.id, ids)
        self.assertIn(self.student_fha.id, ids)

    def test_non_superadmin_without_entity_sees_nothing(self):
        """
        Le garde-fou correspondant : un compte non-superadmin sans entité
        de rattachement ne voit AUCUNE donnée métier — il ne bascule pas
        sur la vue plateforme.
        """
        orphan = CustomUser.objects.create_user(
            username="orphan", email="orphan@test.io", password="Pass1234!",
            role="admin", school=None, first_name="Or", last_name="Phan",
        )
        self.assertIsNone(orphan.school_id)

        client = APIClient()
        login = client.post(
            "/api/auth/login/",
            {"email": "orphan@test.io", "password": "Pass1234!"},
        )
        # Comportement observé et souhaitable : un compte non-superadmin sans
        # entité n'obtient MÊME PAS de jeton — la protection agit dès
        # l'authentification, avant tout accès aux données.
        if login.status_code != status.HTTP_200_OK:
            self.assertIn(
                login.status_code,
                (status.HTTP_400_BAD_REQUEST, status.HTTP_401_UNAUTHORIZED,
                 status.HTTP_403_FORBIDDEN),
            )
            return

        # Si un jeton était malgré tout délivré, aucune donnée métier ne
        # doit être visible.
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data.get('access', '')}")
        resp = client.get("/api/students/")
        if resp.status_code == status.HTTP_200_OK:
            self.assertEqual(rows(resp), [])
        else:
            self.assertIn(
                resp.status_code,
                (status.HTTP_403_FORBIDDEN, status.HTTP_400_BAD_REQUEST),
            )

    def test_superadmin_can_access_both_entities_successively(self):
        client = auth(APIClient(), "su.scope@test.io")
        for entity, expected in ((self.feba, self.student_feba), (self.fha, self.student_fha)):
            resp = client.post("/api/auth/entity-context/switch/",
                               {"entity_id": entity.id}, format="json")
            self.assertEqual(resp.status_code, status.HTTP_200_OK)
            detail = client.get(f"/api/students/{expected.id}/")
            self.assertEqual(detail.status_code, status.HTTP_200_OK)

    def test_superadmin_detail_access_blocked_outside_active_entity(self):
        """Même le superadmin ne lit pas hors de l'entité qu'il a choisie."""
        client = auth(APIClient(), "su.scope@test.io")
        client.post("/api/auth/entity-context/switch/",
                    {"entity_id": self.feba.id}, format="json")
        resp = client.get(f"/api/students/{self.student_fha.id}/")
        self.assertIn(
            resp.status_code,
            (status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND),
        )
