"""
Tests de la matrice de fonctionnalités par entité (V4 multi-entités).

Exigence : une fonctionnalité désactivée pour une entité doit être REFUSÉE
PAR L'API. Masquer le menu React ne protège rien — l'utilisateur peut
appeler l'endpoint directement.
"""
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import CustomUser
from apps.schools.models import School


def auth(client, email, password="Pass1234!"):
    resp = client.post("/api/auth/login/", {"email": email, "password": password})
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {resp.data.get('access', '')}")


class EntityFeatureMatrixTests(TestCase):
    """La matrice elle-même : valeurs par défaut et surcharges."""

    def test_campus_entity_has_no_online_features(self):
        feba = School.objects.create(
            name="FEBA campus", address="Cotonou", entity_type="campus",
        )
        self.assertFalse(feba.has_feature("virtual_classrooms"))
        self.assertFalse(feba.has_feature("video_conferencing"))
        self.assertFalse(feba.has_feature("placement_tests"))
        # Les fonctions scolaires classiques restent actives.
        self.assertTrue(feba.has_feature("payments"))
        self.assertTrue(feba.has_feature("messaging"))
        self.assertTrue(feba.has_feature("schedules"))

    def test_online_entity_has_full_online_school_features(self):
        fha = School.objects.create(
            name="FHA", address="En ligne", entity_type="online",
        )
        for flag in (
            "virtual_classrooms", "video_conferencing", "placement_tests",
            "online_lessons", "online_assignments", "learning_library",
            "skill_progress", "certificates", "support_tickets",
        ):
            self.assertTrue(fha.has_feature(flag), flag)

    def test_settings_override_is_administrable(self):
        """Un drapeau peut être surchargé par l'administration."""
        school = School.objects.create(
            name="Mixte", address="X", entity_type="campus",
            settings={"features": {"virtual_classrooms": True}},
        )
        self.assertTrue(school.has_feature("virtual_classrooms"))

    def test_unknown_flag_in_settings_is_ignored(self):
        """Une clé inconnue ne peut pas injecter une fonctionnalité."""
        school = School.objects.create(
            name="Mixte2", address="X", entity_type="campus",
            settings={"features": {"root_access": True}},
        )
        self.assertNotIn("root_access", school.features)

    def test_seeded_entities_have_expected_types(self):
        """La migration de données crée FEBA FHA en académie en ligne."""
        fha = School.objects.filter(code=School.CODE_FEBA_FHA).first()
        self.assertIsNotNone(fha, "L'entité FEBA_FHA doit exister après migration.")
        self.assertEqual(fha.entity_type, "online")
        self.assertTrue(fha.has_feature("virtual_classrooms"))
        # Cible États-Unis / Canada : devise et langue par défaut adaptées.
        # `currency_code` est la source d'autorité ; `currency` en dérive.
        self.assertEqual(fha.currency_code, "USD")
        self.assertEqual(fha.currency_symbol, "$")
        self.assertEqual(fha.currency_decimal_places, 2)
        self.assertEqual(fha.default_language, "en")

    def test_fha_has_no_invented_commercial_data(self):
        """
        Les informations non validées par la direction (tarif, rentrée,
        horaires, enseignants, prestataire de paiement) ne doivent PAS être
        inventées par le code.
        """
        fha = School.objects.get(code=School.CODE_FEBA_FHA)
        pending = fha.settings.get("pending_direction_validation", {})
        for key in (
            "annual_fee", "school_year_start_date", "group_schedules",
            "refund_policy", "teacher_names", "payment_provider",
        ):
            self.assertIsNone(pending.get(key), f"{key} ne doit pas être inventé")


class VirtualRoomFeatureEnforcementTests(TestCase):
    """L'API refuse les salles virtuelles à une entité présentielle."""

    def setUp(self):
        self.campus = School.objects.create(
            name="FEBA Campus", address="Cotonou", entity_type="campus",
        )
        self.online = School.objects.create(
            name="FHA Test", address="En ligne", entity_type="online",
        )
        self.campus_admin = CustomUser.objects.create_user(
            username="ca", email="campus.admin@test.bj", password="Pass1234!",
            role="admin", school=self.campus, first_name="C", last_name="A",
        )
        self.online_admin = CustomUser.objects.create_user(
            username="oa", email="online.admin@test.bj", password="Pass1234!",
            role="admin", school=self.online, first_name="O", last_name="A",
        )

    def test_campus_admin_cannot_list_virtual_rooms(self):
        client = APIClient()
        auth(client, "campus.admin@test.bj")
        resp = client.get("/api/virtual-rooms/")
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_campus_admin_cannot_create_virtual_room(self):
        """Le refus porte aussi sur l'écriture, pas seulement la lecture."""
        client = APIClient()
        auth(client, "campus.admin@test.bj")
        resp = client.post("/api/virtual-rooms/", {
            "name": "Salle interdite", "description": "test",
        }, format="json")
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_online_admin_can_use_virtual_rooms(self):
        client = APIClient()
        auth(client, "online.admin@test.bj")
        resp = client.get("/api/virtual-rooms/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)


class EntityContextEndpointTests(TestCase):
    """Contexte d'entité et bascule du Super Administrateur."""

    def setUp(self):
        self.feba = School.objects.create(
            name="FEBA", address="Cotonou", entity_type="campus", code="FEBA-T",
        )
        self.fha = School.objects.create(
            name="FHA", address="En ligne", entity_type="online", code="FHA-T",
        )
        self.superadmin = CustomUser.objects.create_user(
            username="su", email="su@test.bj", password="Pass1234!",
            role="superadmin", first_name="S", last_name="U",
        )
        self.feba_admin = CustomUser.objects.create_user(
            username="fa", email="fa@test.bj", password="Pass1234!",
            role="admin", school=self.feba, first_name="F", last_name="A",
        )

    def test_normal_user_sees_only_own_entity_and_cannot_switch(self):
        client = APIClient()
        auth(client, "fa@test.bj")
        resp = client.get("/api/auth/entity-context/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertFalse(resp.data["can_switch"])
        self.assertEqual(len(resp.data["entities"]), 1)
        self.assertEqual(resp.data["active_entity"]["id"], self.feba.id)

    def test_admin_cannot_switch_entity(self):
        """Un admin ne peut jamais changer son propre rattachement."""
        client = APIClient()
        auth(client, "fa@test.bj")
        resp = client.post(
            "/api/auth/entity-context/switch/",
            {"entity_id": self.fha.id}, format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        self.feba_admin.refresh_from_db()
        self.assertIsNone(self.feba_admin.active_organization)
        # Et son contexte réel n'a pas bougé.
        ctx = client.get("/api/auth/entity-context/")
        self.assertEqual(ctx.data["active_entity"]["id"], self.feba.id)

    def test_superadmin_can_switch_and_switch_is_logged(self):
        from apps.schools.models import EntitySwitchLog

        client = APIClient()
        auth(client, "su@test.bj")

        resp = client.post(
            "/api/auth/entity-context/switch/",
            {"entity_id": self.fha.id}, format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["active_entity"]["id"], self.fha.id)
        self.assertTrue(resp.data["cache_invalidated"])

        self.superadmin.refresh_from_db()
        self.assertEqual(self.superadmin.active_organization_id, self.fha.id)

        # Bascule retour vers FEBA.
        resp = client.post(
            "/api/auth/entity-context/switch/",
            {"entity_id": self.feba.id}, format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        logs = EntitySwitchLog.objects.filter(user=self.superadmin).order_by("created_at")
        self.assertEqual(logs.count(), 2)
        self.assertEqual(logs[0].to_organization_id, self.fha.id)
        self.assertEqual(logs[1].from_organization_id, self.fha.id)
        self.assertEqual(logs[1].to_organization_id, self.feba.id)

    def test_superadmin_switch_to_all_entities_mode(self):
        client = APIClient()
        auth(client, "su@test.bj")
        client.post("/api/auth/entity-context/switch/",
                    {"entity_id": self.fha.id}, format="json")
        resp = client.post("/api/auth/entity-context/switch/",
                           {"entity_id": None}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIsNone(resp.data["active_entity"])

        ctx = client.get("/api/auth/entity-context/")
        self.assertTrue(ctx.data["all_entities_mode"])

    def test_switch_to_unknown_entity_rejected(self):
        client = APIClient()
        auth(client, "su@test.bj")
        resp = client.post("/api/auth/entity-context/switch/",
                           {"entity_id": 999999}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_switch_to_inactive_entity_rejected(self):
        self.fha.is_active = False
        self.fha.save(update_fields=["is_active"])
        client = APIClient()
        auth(client, "su@test.bj")
        resp = client.post("/api/auth/entity-context/switch/",
                           {"entity_id": self.fha.id}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_switch_log_reserved_to_superadmin(self):
        client = APIClient()
        auth(client, "fa@test.bj")
        resp = client.get("/api/auth/entity-context/log/")
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_features_follow_active_entity(self):
        """Le contexte renvoie la matrice de l'entité active, pas une autre."""
        client = APIClient()
        auth(client, "su@test.bj")

        client.post("/api/auth/entity-context/switch/",
                    {"entity_id": self.feba.id}, format="json")
        ctx = client.get("/api/auth/entity-context/")
        self.assertFalse(ctx.data["features"]["virtual_classrooms"])

        client.post("/api/auth/entity-context/switch/",
                    {"entity_id": self.fha.id}, format="json")
        ctx = client.get("/api/auth/entity-context/")
        self.assertTrue(ctx.data["features"]["virtual_classrooms"])


class MembershipTests(TestCase):
    """Appartenances : synchronisation, unicité, historique."""

    def setUp(self):
        self.feba = School.objects.create(
            name="FEBA M", address="Cotonou", entity_type="campus",
        )
        self.fha = School.objects.create(
            name="FHA M", address="En ligne", entity_type="online",
        )

    def test_membership_created_for_normal_user(self):
        from apps.schools.models import OrganizationMembership

        user = CustomUser.objects.create_user(
            username="t1", email="t1@test.bj", password="Pass1234!",
            role="teacher", school=self.feba, first_name="T", last_name="1",
        )
        membership = OrganizationMembership.objects.get(user=user)
        self.assertEqual(membership.organization_id, self.feba.id)
        self.assertEqual(membership.role, "teacher")
        self.assertTrue(membership.is_primary)
        self.assertEqual(membership.status, "active")

    def test_superadmin_gets_membership_on_every_entity(self):
        from apps.schools.models import OrganizationMembership

        su = CustomUser.objects.create_user(
            username="su2", email="su2@test.bj", password="Pass1234!",
            role="superadmin", first_name="S", last_name="U",
        )
        orgs = set(
            OrganizationMembership.objects.filter(user=su)
            .values_list("organization_id", flat=True)
        )
        self.assertIn(self.feba.id, orgs)
        self.assertIn(self.fha.id, orgs)
        # Aucune appartenance principale : le superadmin démarre en mode
        # « toutes les entités ».
        self.assertFalse(
            OrganizationMembership.objects.filter(user=su, is_primary=True).exists()
        )

    def test_duplicate_membership_rejected_by_database(self):
        from django.db import IntegrityError, transaction
        from apps.schools.models import OrganizationMembership

        user = CustomUser.objects.create_user(
            username="t2", email="t2@test.bj", password="Pass1234!",
            role="teacher", school=self.feba, first_name="T", last_name="2",
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                OrganizationMembership.objects.create(
                    user=user, organization=self.feba, role="teacher",
                )

    def test_only_one_primary_membership_per_user(self):
        from django.db import IntegrityError, transaction
        from apps.schools.models import OrganizationMembership

        user = CustomUser.objects.create_user(
            username="t3", email="t3@test.bj", password="Pass1234!",
            role="teacher", school=self.feba, first_name="T", last_name="3",
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                OrganizationMembership.objects.create(
                    user=user, organization=self.fha, role="teacher",
                    is_primary=True,
                )
