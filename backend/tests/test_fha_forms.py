"""
Tests des formulaires séparés FEBA / FEBA French Heritage Academy.

Exigences couvertes :
  - la préinscription FEBA est enregistrée dans l'entité FEBA ;
  - la fiche FHA est enregistrée dans l'entité FEBA_FHA ;
  - le contact FEBA n'est visible que par FEBA, le contact FHA que par FHA ;
  - un `entity` envoyé par le navigateur est IGNORÉ (jamais une autorité) ;
  - les doublons FHA sont refusés ;
  - les consentements sont obligatoires, datés et versionnés ;
  - un numéro de dossier unique est attribué ;
  - un e-mail de confirmation est envoyé ;
  - les données confidentielles (besoins particuliers) sont protégées.
"""
from datetime import date

from django.core import mail
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import CustomUser
from apps.schools.models import School
from apps.website.models import (
    ContactMessage, FHAEnrollmentApplication, PreRegistration,
)

FHA_ENROLL_URL = "/api/website/fha/enroll/"
FHA_CONTACT_URL = "/api/website/fha/contact/"
FEBA_CONTACT_URL = "/api/website/contact/"
FEBA_PREREG_URL = "/api/website/preregistrations/"


def auth(client, email, password="Pass1234!"):
    resp = client.post("/api/auth/login/", {"email": email, "password": password})
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {resp.data.get('access', '')}")


def valid_application(**overrides):
    """Payload minimal valide de la fiche FHA (12 étapes)."""
    payload = {
        "child_last_name": "Doe",
        "child_first_name": "Ama",
        "child_birth_date": "2016-05-04",
        "child_city": "Philadelphia",
        "child_state_province": "PA",
        "child_country": "United States",
        "family_origin_country": "Bénin",
        "home_main_language": "English",
        "french_levels": ["few_words", "understands_replies_english"],
        "parent_goals": ["family_conversation", "grandparents"],
        "parent1_last_name": "Doe",
        "parent1_first_name": "Marie",
        "parent1_relation": "Mère",
        "parent1_phone": "+1 215 555 0100",
        "parent1_email": "marie.doe@example.com",
        "parent1_preferred_language": "en",
        "parent1_timezone": "America/New_York",
        "available_days": [3, 6],
        "available_time_slots": [{"start": "17:00", "end": "18:30"}],
        "family_timezone": "America/New_York",
        "weekday_or_weekend": "both",
        "has_computer": True,
        "has_internet": True,
        "consent_rules": True,
        "consent_privacy": True,
        "consent_data_processing": True,
        "consent_parental_authorization": True,
        "consent_zoom": True,
    }
    payload.update(overrides)
    return payload


class EntityBindingTests(TestCase):
    """L'entité vient de la ROUTE, jamais du navigateur."""

    def setUp(self):
        self.feba = School.objects.get(code=School.CODE_FEBA_FHA)  # sanity: FHA exists
        self.fha = self.feba
        self.feba_entity = School.objects.filter(code=School.CODE_FEBA).first()
        if self.feba_entity is None:
            # Installation neuve : la migration n'a trouvé aucune école
            # historique à coder « FEBA ». On en crée une pour le test.
            self.feba_entity = School.objects.create(
                name="FEBA", address="Cotonou", code=School.CODE_FEBA,
                entity_type="campus",
            )
        self.client = APIClient()

    def test_fha_enrollment_is_bound_to_fha_entity(self):
        resp = self.client.post(FHA_ENROLL_URL, valid_application(), format="json")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        application = FHAEnrollmentApplication.objects.get()
        self.assertEqual(application.entity.code, School.CODE_FEBA_FHA)

    def test_client_supplied_entity_is_ignored(self):
        """
        Un navigateur qui force `entity` vers FEBA ne doit pas déplacer la
        fiche : le champ n'est pas exposé en écriture.
        """
        payload = valid_application(entity=self.feba_entity.id)
        payload["entity_id"] = self.feba_entity.id
        resp = self.client.post(FHA_ENROLL_URL, payload, format="json")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        application = FHAEnrollmentApplication.objects.get()
        self.assertEqual(application.entity.code, School.CODE_FEBA_FHA)
        self.assertNotEqual(application.entity_id, self.feba_entity.id)

    def test_feba_preregistration_is_bound_to_feba_entity(self):
        resp = self.client.post(FEBA_PREREG_URL, {
            "parent_name": "Jean Kossi", "phone": "+229 90000000",
            "child_name": "Awa", "desired_level": "cp",
        }, format="json")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        prereg = PreRegistration.objects.get()
        self.assertEqual(prereg.entity.code, School.CODE_FEBA)

    def test_feba_contact_is_bound_to_feba_entity(self):
        resp = self.client.post(FEBA_CONTACT_URL, {
            "name": "Jean", "email": "jean@example.bj",
            "subject": "Info", "message": "Bonjour", "consent": True,
        }, format="json")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        self.assertEqual(ContactMessage.objects.get().entity.code, School.CODE_FEBA)

    def test_fha_contact_is_bound_to_fha_entity(self):
        resp = self.client.post(FHA_CONTACT_URL, {
            "name": "Marie Doe", "email": "marie@example.com",
            "country": "United States", "state_province": "PA",
            "timezone": "America/New_York", "preferred_language": "en",
            "subject": "Placement test", "category": "placement_test",
            "message": "How do I book?", "consent": True,
        }, format="json")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        msg = ContactMessage.objects.get()
        self.assertEqual(msg.entity.code, School.CODE_FEBA_FHA)
        self.assertEqual(msg.category, "placement_test")
        self.assertEqual(msg.timezone, "America/New_York")


class FHAValidationTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_reference_number_is_generated_and_unique(self):
        resp = self.client.post(FHA_ENROLL_URL, valid_application(), format="json")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        first = resp.data["reference"]
        self.assertTrue(first)

        resp2 = self.client.post(FHA_ENROLL_URL, valid_application(
            child_first_name="Kofi", parent1_email="other@example.com",
        ), format="json")
        self.assertEqual(resp2.status_code, status.HTTP_201_CREATED, resp2.data)
        self.assertNotEqual(resp2.data["reference"], first)

    def test_duplicate_application_rejected(self):
        self.client.post(FHA_ENROLL_URL, valid_application(), format="json")
        resp = self.client.post(FHA_ENROLL_URL, valid_application(), format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("duplicate", resp.data)
        self.assertEqual(FHAEnrollmentApplication.objects.count(), 1)

    def test_missing_required_consents_rejected(self):
        resp = self.client.post(FHA_ENROLL_URL, valid_application(
            consent_privacy=False,
        ), format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("consents", resp.data)
        self.assertEqual(FHAEnrollmentApplication.objects.count(), 0)

    def test_consents_are_dated_and_versioned(self):
        self.client.post(FHA_ENROLL_URL, valid_application(), format="json")
        application = FHAEnrollmentApplication.objects.get()
        self.assertIsNotNone(application.consents_accepted_at)
        self.assertEqual(application.consents_version, "1.0")

    def test_future_birth_date_rejected(self):
        resp = self.client.post(FHA_ENROLL_URL, valid_application(
            child_birth_date="2999-01-01",
        ), format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("child_birth_date", resp.data)

    def test_invalid_phone_rejected(self):
        resp = self.client.post(FHA_ENROLL_URL, valid_application(
            parent1_phone="abc",
        ), format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("parent1_phone", resp.data)

    def test_invalid_email_rejected(self):
        resp = self.client.post(FHA_ENROLL_URL, valid_application(
            parent1_email="not-an-email",
        ), format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("parent1_email", resp.data)

    def test_unknown_french_level_rejected(self):
        resp = self.client.post(FHA_ENROLL_URL, valid_application(
            french_levels=["fluent_native_speaker"],
        ), format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("french_levels", resp.data)

    def test_invalid_available_day_rejected(self):
        resp = self.client.post(FHA_ENROLL_URL, valid_application(
            available_days=[9],
        ), format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("available_days", resp.data)

    def test_honeypot_blocks_bots(self):
        payload = valid_application()
        payload["website"] = "http://spam.example"
        resp = self.client.post(FHA_ENROLL_URL, payload, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(FHAEnrollmentApplication.objects.count(), 0)

    def test_age_is_computed_not_supplied(self):
        resp = self.client.post(FHA_ENROLL_URL, valid_application(
            child_birth_date="2016-05-04",
        ), format="json")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        application = FHAEnrollmentApplication.objects.get()
        today = date.today()
        expected = today.year - 2016 - ((today.month, today.day) < (5, 4))
        self.assertEqual(application.child_age, expected)

    def test_suggested_group_follows_age(self):
        self.client.post(FHA_ENROLL_URL, valid_application(
            child_birth_date="2018-01-01",
        ), format="json")
        app1 = FHAEnrollmentApplication.objects.get()
        self.assertEqual(app1.suggested_group, FHAEnrollmentApplication.GROUP_JUNIOR_ROOTS)

    def test_initial_status_and_history_recorded(self):
        self.client.post(FHA_ENROLL_URL, valid_application(), format="json")
        application = FHAEnrollmentApplication.objects.get()
        self.assertEqual(application.status, FHAEnrollmentApplication.STATUS_FORM_RECEIVED)
        history = application.status_history.all()
        self.assertEqual(history.count(), 1)
        self.assertEqual(history[0].to_status, FHAEnrollmentApplication.STATUS_FORM_RECEIVED)

    def test_confirmation_email_sent_to_parent(self):
        mail.outbox = []
        resp = self.client.post(FHA_ENROLL_URL, valid_application(), format="json")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        recipients = [addr for m in mail.outbox for addr in m.to]
        self.assertIn("marie.doe@example.com", recipients)
        # Le numéro de dossier figure dans l'accusé de réception.
        parent_mail = next(m for m in mail.outbox if "marie.doe@example.com" in m.to)
        self.assertIn(resp.data["reference"], parent_mail.body)


class FHAAdminIsolationTests(TestCase):
    """Boîtes de réception et dossiers strictement séparés par entité."""

    def setUp(self):
        self.fha = School.objects.get(code=School.CODE_FEBA_FHA)
        self.feba = School.objects.filter(code=School.CODE_FEBA).first()
        if self.feba is None:
            self.feba = School.objects.create(
                name="FEBA", address="Cotonou", code=School.CODE_FEBA,
                entity_type="campus",
            )

        self.feba_admin = CustomUser.objects.create_user(
            username="fadm", email="fadm@test.bj", password="Pass1234!",
            role="admin", school=self.feba, first_name="F", last_name="A",
        )
        self.fha_admin = CustomUser.objects.create_user(
            username="hadm", email="hadm@test.com", password="Pass1234!",
            role="admin", school=self.fha, first_name="H", last_name="A",
        )
        self.superadmin = CustomUser.objects.create_user(
            username="sadm", email="sadm@test.bj", password="Pass1234!",
            role="superadmin", first_name="S", last_name="A",
        )

        public = APIClient()
        public.post(FEBA_CONTACT_URL, {
            "name": "Jean", "email": "jean@example.bj", "subject": "FEBA",
            "message": "Bonjour FEBA", "consent": True,
        }, format="json")
        public.post(FHA_CONTACT_URL, {
            "name": "Marie", "email": "marie@example.com", "subject": "FHA",
            "message": "Hello FHA", "consent": True, "category": "enrollment",
        }, format="json")
        public.post(FHA_ENROLL_URL, valid_application(), format="json")

    def test_feba_admin_sees_only_feba_contact_messages(self):
        client = APIClient()
        auth(client, "fadm@test.bj")
        resp = client.get("/api/website/admin/contact-messages/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        subjects = [m["subject"] for m in resp.data.get("results", resp.data)]
        self.assertIn("FEBA", subjects)
        self.assertNotIn("FHA", subjects)

    def test_fha_admin_sees_only_fha_contact_messages(self):
        client = APIClient()
        auth(client, "hadm@test.com")
        resp = client.get("/api/website/admin/contact-messages/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        subjects = [m["subject"] for m in resp.data.get("results", resp.data)]
        self.assertIn("FHA", subjects)
        self.assertNotIn("FEBA", subjects)

    def test_feba_admin_sees_no_fha_applications(self):
        client = APIClient()
        auth(client, "fadm@test.bj")
        resp = client.get("/api/website/admin/fha-applications/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        results = resp.data.get("results", resp.data)
        self.assertEqual(len(results), 0)

    def test_feba_admin_cannot_open_fha_application_by_id(self):
        """Anti-IDOR : modifier l'URL ne donne pas accès à l'autre entité."""
        application = FHAEnrollmentApplication.objects.get()
        client = APIClient()
        auth(client, "fadm@test.bj")
        resp = client.get(f"/api/website/admin/fha-applications/{application.id}/")
        self.assertIn(
            resp.status_code,
            (status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND),
        )

    def test_fha_admin_sees_own_applications(self):
        client = APIClient()
        auth(client, "hadm@test.com")
        resp = client.get("/api/website/admin/fha-applications/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        results = resp.data.get("results", resp.data)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["entity_code"], School.CODE_FEBA_FHA)

    def test_superadmin_can_filter_by_entity(self):
        client = APIClient()
        auth(client, "sadm@test.bj")

        client.post("/api/auth/entity-context/switch/",
                    {"entity_id": self.fha.id}, format="json")
        resp = client.get("/api/website/admin/contact-messages/")
        subjects = [m["subject"] for m in resp.data.get("results", resp.data)]
        self.assertEqual(subjects, ["FHA"])

        client.post("/api/auth/entity-context/switch/",
                    {"entity_id": self.feba.id}, format="json")
        resp = client.get("/api/website/admin/contact-messages/")
        subjects = [m["subject"] for m in resp.data.get("results", resp.data)]
        self.assertEqual(subjects, ["FEBA"])

    def test_status_change_is_recorded_with_author(self):
        application = FHAEnrollmentApplication.objects.get()
        client = APIClient()
        auth(client, "hadm@test.com")
        resp = client.post(
            f"/api/website/admin/fha-applications/{application.id}/change-status/",
            {"status": "test_booked", "reason": "Créneau réservé"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        application.refresh_from_db()
        self.assertEqual(application.status, "test_booked")
        last = application.status_history.first()
        self.assertEqual(last.to_status, "test_booked")
        self.assertEqual(last.changed_by, self.fha_admin)
        self.assertEqual(last.reason, "Créneau réservé")

    def test_invalid_status_rejected(self):
        application = FHAEnrollmentApplication.objects.get()
        client = APIClient()
        auth(client, "hadm@test.com")
        resp = client.post(
            f"/api/website/admin/fha-applications/{application.id}/change-status/",
            {"status": "not_a_status"}, format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_anonymous_cannot_list_applications(self):
        client = APIClient()
        resp = client.get("/api/website/admin/fha-applications/")
        self.assertIn(
            resp.status_code,
            (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN),
        )

    def test_applications_never_exposed_publicly(self):
        """Aucune donnée d'enfant n'est lisible sans authentification."""
        client = APIClient()
        for url in (FHA_ENROLL_URL, "/api/website/fha/program/"):
            resp = client.get(url)
            body = str(resp.data) if hasattr(resp, "data") else ""
            self.assertNotIn("marie.doe@example.com", body)


class FHAProgramInfoTests(TestCase):
    """Les données non validées par la direction ne sont pas inventées."""

    def test_program_endpoint_exposes_only_confirmed_data(self):
        client = APIClient()
        resp = client.get("/api/website/fha/program/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        # Confirmé par les documents de cadrage.
        self.assertEqual(resp.data["short_name"], "FEBA FHA")
        self.assertEqual(
            resp.data["tagline"],
            "From English Speakers to Confident French Speakers",
        )
        self.assertIn("215", resp.data["whatsapp"])

        # NON validé → doit rester null, jamais inventé.
        for key in (
            "annual_fee", "school_year_start_date", "group_schedules",
            "refund_policy", "teacher_names", "payment_provider",
        ):
            self.assertIsNone(resp.data[key], key)


class PreRegistrationVisibilityTests(TestCase):
    """
    P2 — L'onglet « Préinscriptions » de la page Site vitrine concerne les
    préinscriptions FEBA. Une académie EN LIGNE ne doit pas y accéder :
    masquer le bouton ne suffit pas, l'API elle-même doit refuser.
    """

    def setUp(self):
        self.fha = School.objects.get(code=School.CODE_FEBA_FHA)
        self.feba = School.objects.filter(code=School.CODE_FEBA).first()
        if self.feba is None:
            self.feba = School.objects.create(
                name="FEBA", address="Cotonou", code=School.CODE_FEBA,
                entity_type="campus",
            )
        CustomUser.objects.create_user(
            username="prfeba", email="pr.feba@test.io", password="Pass1234!",
            role="admin", school=self.feba, first_name="P", last_name="F",
        )
        CustomUser.objects.create_user(
            username="prfha", email="pr.fha@test.io", password="Pass1234!",
            role="admin", school=self.fha, first_name="P", last_name="H",
        )
        CustomUser.objects.create_user(
            username="prsu", email="pr.su@test.io", password="Pass1234!",
            role="superadmin", first_name="P", last_name="S",
        )

    def test_feba_admin_can_access_preregistrations(self):
        client = APIClient()
        auth(client, "pr.feba@test.io")
        resp = client.get("/api/website/admin/preregistrations/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_online_academy_admin_is_refused(self):
        """L'admin FHA reçoit 403 même en saisissant l'URL à la main."""
        client = APIClient()
        auth(client, "pr.fha@test.io")
        resp = client.get("/api/website/admin/preregistrations/")
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn("Admissions FEBA FHA", str(resp.data))

    def test_superadmin_keeps_access(self):
        client = APIClient()
        auth(client, "pr.su@test.io")
        resp = client.get("/api/website/admin/preregistrations/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_fha_admin_keeps_access_to_its_own_module(self):
        """Le refus ci-dessus ne doit pas priver FHA de ses admissions."""
        client = APIClient()
        auth(client, "pr.fha@test.io")
        resp = client.get("/api/website/admin/fha-applications/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_feba_admin_refused_on_fha_module(self):
        """Symétrie : un admin FEBA ne voit aucun dossier FHA."""
        client = APIClient()
        auth(client, "pr.feba@test.io")
        resp = client.get("/api/website/admin/fha-applications/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data.get("results", resp.data)), 0)
