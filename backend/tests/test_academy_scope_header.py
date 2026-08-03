"""
Tests de l'en-tête `X-Academy-Scope` (P0).

Le symptôme corrigé : après un changement d'académie, les écrans
continuaient d'afficher pendant plusieurs secondes les données de
l'académie quittée. Une des causes était qu'une réponse API ne disait pas
à quelle académie elle correspondait — le navigateur n'avait donc aucun
moyen d'écarter une réponse arrivée trop tard.

Ces tests verrouillent deux propriétés :

  1. TOUTE réponse annonce la portée réellement utilisée pour la calculer ;
  2. cette portée est celle du SERVEUR — un en-tête envoyé par le client
     ne la modifie jamais, sous aucune forme.

Le point 2 est le plus important : si l'en-tête client avait la moindre
autorité, il suffirait de le forger pour lire les données de l'autre
académie.
"""
from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import CustomUser
from apps.core.academy_scope import HEADER, SCOPE_ALL, SCOPE_NONE
from apps.schools.models import School, SchoolYear
from apps.students.models import Student


def auth(client, email, password="Pass1234!"):
    resp = client.post("/api/auth/login/", {"email": email, "password": password})
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {resp.data.get('access', '')}")
    return client


def rows(resp):
    data = resp.data
    if isinstance(data, dict) and "results" in data:
        return data["results"]
    return data


class AcademyScopeHeaderTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.feba = School.objects.create(
            name="FEBA Cotonou", address="Akpakpa",
            entity_type="campus", code="SCOPE-FEBA",
        )
        cls.fha = School.objects.create(
            name="FEBA FHA", address="En ligne",
            entity_type="online", code="SCOPE-FHA",
        )
        for school, label in ((cls.feba, "feba"), (cls.fha, "fha")):
            year = SchoolYear.objects.create(
                school=school, name=f"2025-2026-{label}", is_current=True,
                start_date="2025-09-01", end_date="2026-07-01",
            )
            Student.objects.create(
                school=school, school_year=year,
                first_name="Élève", last_name=label.upper(),
                date_of_birth="2015-01-01",
            )

        cls.admin_feba = CustomUser.objects.create_user(
            username="admin_scope_feba", email="admin.scope.feba@feba.bj", password="Pass1234!",
            first_name="A", last_name="Feba", role="admin", school=cls.feba,
        )
        cls.admin_fha = CustomUser.objects.create_user(
            username="admin_scope_fha", email="admin.scope.fha@febafha.org", password="Pass1234!",
            first_name="A", last_name="Fha", role="admin", school=cls.fha,
        )
        cls.superadmin = CustomUser.objects.create_user(
            username="super_scope", email="super.scope@feba.bj", password="Pass1234!",
            first_name="S", last_name="Admin", role="superadmin",
        )

    # ── La portée est annoncée sur toutes les réponses ────────────────────

    def test_reponse_annonce_l_academie_de_l_administrateur(self):
        client = auth(APIClient(), "admin.scope.feba@feba.bj")
        resp = client.get("/api/students/")
        self.assertEqual(resp[HEADER], "SCOPE-FEBA")

    def test_chaque_academie_annonce_son_propre_code(self):
        client = auth(APIClient(), "admin.scope.fha@febafha.org")
        resp = client.get("/api/students/")
        self.assertEqual(resp[HEADER], "SCOPE-FHA")

    def test_superadmin_sans_academie_active_annonce_le_mode_consolide(self):
        client = auth(APIClient(), "super.scope@feba.bj")
        resp = client.get("/api/schools/schools/")
        self.assertEqual(resp[HEADER], SCOPE_ALL)

    def test_superadmin_apres_bascule_annonce_l_academie_choisie(self):
        client = auth(APIClient(), "super.scope@feba.bj")
        client.post("/api/auth/entity-context/switch/", {"entity_id": self.fha.id})
        resp = client.get("/api/students/")
        self.assertEqual(resp[HEADER], "SCOPE-FHA")

        client.post("/api/auth/entity-context/switch/", {"entity_id": self.feba.id})
        resp = client.get("/api/students/")
        self.assertEqual(resp[HEADER], "SCOPE-FEBA")

    def test_requete_anonyme_annonce_une_portee_neutre(self):
        resp = APIClient().get("/api/students/")
        self.assertEqual(resp[HEADER], SCOPE_NONE)

    def test_l_en_tete_est_present_meme_sur_une_erreur(self):
        """
        Une réponse d'erreur doit elle aussi être identifiable : sinon le
        frontend garderait pour toujours l'écran de chargement d'une
        requête qu'il n'a pas su rattacher à une académie.
        """
        client = auth(APIClient(), "admin.scope.feba@feba.bj")
        resp = client.get("/api/students/99999999/")
        self.assertEqual(resp.status_code, 404)
        self.assertEqual(resp[HEADER], "SCOPE-FEBA")

    # ── L'en-tête client n'a AUCUNE autorité ──────────────────────────────

    def test_en_tete_client_forge_ne_change_pas_la_portee_annoncee(self):
        client = auth(APIClient(), "admin.scope.feba@feba.bj")
        resp = client.get("/api/students/", HTTP_X_ACADEMY_SCOPE="SCOPE-FHA")
        self.assertEqual(resp[HEADER], "SCOPE-FEBA")

    def test_en_tete_client_forge_ne_change_pas_les_donnees_servies(self):
        client = auth(APIClient(), "admin.scope.feba@feba.bj")
        resp = client.get("/api/students/", HTTP_X_ACADEMY_SCOPE="SCOPE-FHA")
        noms = {row["last_name"] for row in rows(resp)}
        self.assertEqual(noms, {"FEBA"})
        self.assertNotIn("FHA", noms)

    def test_en_tete_client_all_ne_donne_pas_le_mode_consolide(self):
        """Tentative d'évasion la plus évidente : prétendre être en mode ALL."""
        client = auth(APIClient(), "admin.scope.fha@febafha.org")
        resp = client.get("/api/students/", HTTP_X_ACADEMY_SCOPE=SCOPE_ALL)
        self.assertEqual(resp[HEADER], "SCOPE-FHA")
        noms = {row["last_name"] for row in rows(resp)}
        self.assertEqual(noms, {"FHA"})
