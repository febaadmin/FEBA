"""
Tests P3 — « Inscrire mon enfant » et « Réserver un test » sont DISTINCTS.

Les deux boutons ouvraient le même formulaire. Ce sont pourtant deux
étapes différentes : réserver un test précède l'admission et ne l'engage
pas. Ces tests garantissent que la séparation est réelle — modèles,
numérotations, boîtes de réception et notifications distincts.
"""
from django.core import mail
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import CustomUser
from apps.schools.models import School
from apps.website.models import (
    FHAEnrollmentApplication, FHAPlacementTestRequest,
)

ENROLL_URL = "/api/website/fha/enroll/"
PLACEMENT_URL = "/api/website/fha/placement-test/"


def auth(client, email, password="Pass1234!"):
    resp = client.post("/api/auth/login/", {"email": email, "password": password})
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {resp.data.get('access', '')}")
    return client


def placement_payload(**overrides):
    payload = {
        "child_first_name": "Naomi",
        "child_last_name": "Adjovi",
        "child_birth_date": "2015-03-12",
        "child_country": "United States",
        "child_state_province": "PA",
        "parent_first_name": "Sylvie",
        "parent_last_name": "Adjovi",
        "parent_email": "sylvie@example.com",
        "parent_phone": "+1 215 555 0142",
        "parent_timezone": "America/New_York",
        "preferred_language": "en",
        "estimated_level": "few_words",
        "consent_video": True,
    }
    payload.update(overrides)
    return payload


class PlacementTestIsSeparateJourneyTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_placement_request_creates_no_enrollment(self):
        """
        EXIGENCE CENTRALE : réserver un test ne crée PAS d'inscription.
        """
        resp = self.client.post(PLACEMENT_URL, placement_payload(), format="json")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        self.assertEqual(FHAPlacementTestRequest.objects.count(), 1)
        self.assertEqual(
            FHAEnrollmentApplication.objects.count(), 0,
            "Une réservation de test ne doit jamais créer d'inscription.",
        )

    def test_placement_reference_is_distinct_from_enrollment(self):
        """Les deux parcours ont des numérotations SÉPARÉES."""
        resp = self.client.post(PLACEMENT_URL, placement_payload(), format="json")
        reference = resp.data["reference"]
        self.assertIn("TEST", reference, "Le dossier de test doit être identifiable.")

        request = FHAPlacementTestRequest.objects.get()
        self.assertTrue(request.reference.startswith(f"{request.entity.matricule_prefix}-TEST-"))

    def test_placement_is_bound_to_fha_entity_server_side(self):
        self.client.post(PLACEMENT_URL, placement_payload(), format="json")
        request = FHAPlacementTestRequest.objects.get()
        self.assertEqual(request.entity.code, School.CODE_FEBA_FHA)

    def test_client_supplied_entity_is_ignored(self):
        feba = School.objects.filter(code=School.CODE_FEBA).first()
        if feba is None:
            feba = School.objects.create(
                name="FEBA", address="Cotonou", code=School.CODE_FEBA,
                entity_type="campus",
            )
        payload = placement_payload(entity=feba.id)
        payload["entity_id"] = feba.id
        resp = self.client.post(PLACEMENT_URL, payload, format="json")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        self.assertEqual(FHAPlacementTestRequest.objects.get().entity.code, School.CODE_FEBA_FHA)

    def test_initial_status_is_requested_not_enrolled(self):
        self.client.post(PLACEMENT_URL, placement_payload(), format="json")
        self.assertEqual(FHAPlacementTestRequest.objects.get().status, "requested")

    def test_video_consent_is_required(self):
        resp = self.client.post(
            PLACEMENT_URL, placement_payload(consent_video=False), format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("consent_video", resp.data)
        self.assertEqual(FHAPlacementTestRequest.objects.count(), 0)

    def test_duplicate_active_request_refused(self):
        self.client.post(PLACEMENT_URL, placement_payload(), format="json")
        resp = self.client.post(PLACEMENT_URL, placement_payload(), format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("duplicate", resp.data)
        self.assertEqual(FHAPlacementTestRequest.objects.count(), 1)

    def test_past_preferred_date_refused(self):
        resp = self.client.post(
            PLACEMENT_URL, placement_payload(preferred_date="2020-01-01"), format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("preferred_date", resp.data)

    def test_age_computed_and_group_suggested(self):
        self.client.post(
            PLACEMENT_URL, placement_payload(child_birth_date="2018-06-01"), format="json",
        )
        request = FHAPlacementTestRequest.objects.get()
        self.assertEqual(request.suggested_group, FHAEnrollmentApplication.GROUP_JUNIOR_ROOTS)

    def test_confirmation_email_sent_with_reference(self):
        mail.outbox = []
        resp = self.client.post(PLACEMENT_URL, placement_payload(), format="json")
        recipients = [addr for m in mail.outbox for addr in m.to]
        self.assertIn("sylvie@example.com", recipients)
        parent_mail = next(m for m in mail.outbox if "sylvie@example.com" in m.to)
        self.assertIn(resp.data["reference"], parent_mail.body)


class PlacementTestAdminTests(TestCase):
    """Boîte de réception séparée et cloisonnée par académie."""

    def setUp(self):
        self.fha = School.objects.get(code=School.CODE_FEBA_FHA)
        self.feba = School.objects.filter(code=School.CODE_FEBA).first()
        if self.feba is None:
            self.feba = School.objects.create(
                name="FEBA", address="Cotonou", code=School.CODE_FEBA,
                entity_type="campus",
            )
        self.fha_admin = CustomUser.objects.create_user(
            username="pha", email="pha@test.io", password="Pass1234!",
            role="admin", school=self.fha, first_name="P", last_name="A",
        )
        self.feba_admin = CustomUser.objects.create_user(
            username="pfa", email="pfa@test.io", password="Pass1234!",
            role="admin", school=self.feba, first_name="P", last_name="F",
        )
        APIClient().post(PLACEMENT_URL, placement_payload(), format="json")

    def test_fha_admin_sees_placement_requests(self):
        client = auth(APIClient(), "pha@test.io")
        resp = client.get("/api/website/admin/fha-placement-tests/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        results = resp.data.get("results", resp.data)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["entity_code"], School.CODE_FEBA_FHA)

    def test_feba_admin_sees_no_placement_requests(self):
        client = auth(APIClient(), "pfa@test.io")
        resp = client.get("/api/website/admin/fha-placement-tests/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data.get("results", resp.data)), 0)

    def test_feba_admin_cannot_open_request_by_id(self):
        request = FHAPlacementTestRequest.objects.get()
        client = auth(APIClient(), "pfa@test.io")
        resp = client.get(f"/api/website/admin/fha-placement-tests/{request.id}/")
        self.assertIn(
            resp.status_code,
            (status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND),
        )

    def test_scheduling_stores_utc_and_notifies(self):
        request = FHAPlacementTestRequest.objects.get()
        client = auth(APIClient(), "pha@test.io")
        mail.outbox = []
        resp = client.post(
            f"/api/website/admin/fha-placement-tests/{request.id}/schedule/",
            {"scheduled_at": "2026-09-15T14:00:00-04:00"}, format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        request.refresh_from_db()
        self.assertEqual(request.status, "scheduled")
        self.assertIsNotNone(request.scheduled_at)
        # Stocké en UTC : 14 h à New York (UTC-4) = 18 h UTC.
        self.assertEqual(request.scheduled_at.hour, 18)
        self.assertTrue(any("sylvie@example.com" in m.to for m in mail.outbox))

    def test_recording_result_completes_the_test(self):
        request = FHAPlacementTestRequest.objects.get()
        client = auth(APIClient(), "pha@test.io")
        resp = client.post(
            f"/api/website/admin/fha-placement-tests/{request.id}/record-result/",
            {
                "listening": 2, "speaking": 1, "vocabulary": 2,
                "reading": 1, "writing": 0, "confidence": 3,
                "recommended_group": FHAEnrollmentApplication.GROUP_FRENCH_EXPLORERS,
                "starting_level": "beginner",
                "priority_objectives": "Conversation familiale",
            },
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        request.refresh_from_db()
        self.assertEqual(request.status, "completed")
        self.assertEqual(request.result.starting_level, "beginner")
        self.assertEqual(request.result.assessed_by, self.fha_admin)

    def test_out_of_range_score_refused(self):
        request = FHAPlacementTestRequest.objects.get()
        client = auth(APIClient(), "pha@test.io")
        resp = client.post(
            f"/api/website/admin/fha-placement-tests/{request.id}/record-result/",
            {"listening": 9}, format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_anonymous_cannot_list_requests(self):
        resp = APIClient().get("/api/website/admin/fha-placement-tests/")
        self.assertIn(
            resp.status_code,
            (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN),
        )
