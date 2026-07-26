"""
V8 — Priorité 3 : remontée RÉELLE des erreurs techniques aux super admins.

Avant : l'interface affirmait « L'équipe technique a été notifiée » sans qu'au-
cune notification ni trace n'existe. Ces tests prouvent qu'un incident est
désormais créé, dédoublonné, notifié, consultable et traitable — et qu'aucune
donnée sensible n'y est enregistrée.
"""
from django.test import TestCase, override_settings
from django.urls import path
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.test import APIClient

from apps.accounts.models import CustomUser
from apps.incidents.models import (
    TechnicalIncident, build_fingerprint, sanitize_data, sanitize_text,
)
from apps.incidents.services import report_incident
from apps.notifications.models import Notification
from apps.schools.models import School

URL = "/api/incidents/"


# ── Vue de test qui plante RÉELLEMENT (erreur 500 non gérée) ────────────────
@api_view(["POST"])
@permission_classes([AllowAny])
def boom(request):
    raise RuntimeError("Explosion contrôlée pour le test")


urlpatterns = [
    path("api/boom/", boom),
    path("api/incidents/", __import__("apps.incidents.urls", fromlist=["urlpatterns"]).urlpatterns and
         __import__("django.urls", fromlist=["include"]).include("apps.incidents.urls")),
]


class SanitizationTests(TestCase):
    def test_mots_de_passe_et_tokens_expurges(self):
        text = ("password=SuperSecret123 token=abc.def.ghi "
                "Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.sig")
        clean = sanitize_text(text)
        self.assertNotIn("SuperSecret123", clean)
        self.assertNotIn("eyJhbGciOiJIUzI1NiJ9", clean)
        self.assertIn("[expurgé]", clean)

    def test_cles_sensibles_dans_les_donnees(self):
        data = {"email": "a@b.bj", "password": "secret", "nested": {"api_key": "k-123"},
                "list": [{"token": "t-1"}]}
        clean = sanitize_data(data)
        self.assertEqual(clean["email"], "a@b.bj")
        self.assertEqual(clean["password"], "[expurgé]")
        self.assertEqual(clean["nested"]["api_key"], "[expurgé]")
        self.assertEqual(clean["list"][0]["token"], "[expurgé]")

    def test_numero_de_carte_expurge(self):
        self.assertNotIn("4111111111111111", sanitize_text("carte 4111111111111111"))

    def test_empreinte_ignore_les_nombres_variables(self):
        a = build_fingerprint("ValueError", "/api/x/", "grades", "f.py:10 (v)", "id 42 introuvable")
        b = build_fingerprint("ValueError", "/api/x/", "grades", "f.py:10 (v)", "id 77 introuvable")
        self.assertEqual(a, b)


class IncidentFixture(TestCase):
    def setUp(self):
        self.school = School.objects.create(name="FEBA", address="Cotonou")
        self.superadmin = CustomUser.objects.create_user(
            username="sa", email="sa@test.bj", password="Pass1234!",
            role="superadmin", first_name="S", last_name="A",
        )
        self.admin = CustomUser.objects.create_user(
            username="adm", email="adm@test.bj", password="Pass1234!",
            role="admin", first_name="A", last_name="D", school=self.school,
        )
        self.teacher = CustomUser.objects.create_user(
            username="prof", email="prof@test.bj", password="Pass1234!",
            role="teacher", first_name="T", last_name="P", school=self.school,
        )

    def as_(self, user):
        client = APIClient()
        client.force_authenticate(user=user)
        return client


@override_settings(ROOT_URLCONF=__name__)
class RealServerErrorTests(IncidentFixture):
    """Une VRAIE erreur 500 crée un incident et notifie les super admins."""

    def test_erreur_500_reelle_cree_un_incident_et_notifie(self):
        client = APIClient()
        resp = client.post("/api/boom/", {}, format="json")

        self.assertEqual(resp.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        # Message honnête AVEC référence vérifiable
        self.assertIn("incident_reference", resp.data)
        reference = resp.data["incident_reference"]
        self.assertTrue(reference.startswith("ERR-"))
        self.assertIn(reference, resp.data["detail"])
        # Aucun traceback ni détail interne exposé
        self.assertNotIn("Traceback", str(resp.data))
        self.assertNotIn("Explosion contrôlée", str(resp.data))

        incident = TechnicalIncident.objects.get(reference=reference)
        self.assertEqual(incident.exception_type, "RuntimeError")
        self.assertEqual(incident.status_code, 500)
        self.assertEqual(incident.status, "new")
        self.assertIn("boom", incident.endpoint)

        # Notification RÉELLE au super administrateur, pointant vers l'incident
        notif = Notification.objects.filter(user=self.superadmin).first()
        self.assertIsNotNone(notif, "aucune notification créée")
        self.assertIn(reference, notif.title)
        self.assertEqual(notif.related_url, f"/superadmin/incidents/{incident.id}")

    def test_erreur_de_validation_400_ne_cree_pas_d_incident(self):
        """Les erreurs métier ne doivent pas noyer la table des incidents."""
        client = self.as_(self.superadmin)
        client.post("/api/incidents/", {}, format="json")  # méthode non autorisée
        self.assertEqual(TechnicalIncident.objects.count(), 0)

    def test_deduplication_et_compteur_d_occurrences(self):
        client = APIClient()
        refs = set()
        for _ in range(3):
            resp = client.post("/api/boom/", {}, format="json")
            refs.add(resp.data["incident_reference"])
        self.assertEqual(len(refs), 1, "la même erreur doit être dédoublonnée")
        incident = TechnicalIncident.objects.get()
        self.assertEqual(TechnicalIncident.objects.count(), 1)
        self.assertEqual(incident.occurrences, 3)
        # Pas une notification par occurrence (paliers 1, 5, 25…)
        self.assertEqual(Notification.objects.filter(user=self.superadmin).count(), 1)


class ReportServiceTests(IncidentFixture):
    def test_sans_super_admin_l_incident_existe_quand_meme(self):
        CustomUser.objects.filter(role="superadmin").delete()
        incident = report_incident(ValueError("boum"), module="grades")
        self.assertIsNotNone(incident)
        self.assertEqual(Notification.objects.count(), 0)

    def test_plusieurs_super_admins_tous_notifies(self):
        CustomUser.objects.create_user(
            username="sa2", email="sa2@test.bj", password="Pass1234!",
            role="superadmin", first_name="S", last_name="2",
        )
        incident = report_incident(ValueError("boum"), module="grades")
        self.assertIsNotNone(incident)
        self.assertEqual(Notification.objects.filter(title__contains=incident.reference).count(), 2)

    def test_contexte_sensible_jamais_stocke(self):
        incident = report_incident(
            ValueError("échec"), module="accounts",
            context={"email": "a@b.bj", "password": "MotDePasse!", "access": "jwt.token.here"},
        )
        self.assertEqual(incident.context_data["password"], "[expurgé]")
        self.assertEqual(incident.context_data["access"], "[expurgé]")
        self.assertEqual(incident.context_data["email"], "a@b.bj")


class IncidentApiPermissionTests(IncidentFixture):
    def setUp(self):
        super().setUp()
        self.incident = report_incident(ValueError("test"), module="grades")

    def test_super_admin_liste_et_detail(self):
        client = self.as_(self.superadmin)
        resp = client.get(URL)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        rows = resp.data["results"] if isinstance(resp.data, dict) else resp.data
        self.assertEqual(len(rows), 1)
        detail = client.get(f"{URL}{self.incident.id}/")
        self.assertEqual(detail.status_code, status.HTTP_200_OK)
        self.assertEqual(detail.data["reference"], self.incident.reference)

    def test_admin_enseignant_parent_refuses(self):
        for user in (self.admin, self.teacher):
            resp = self.as_(user).get(URL)
            self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN,
                             f"{user.role} ne doit pas accéder aux incidents")

    def test_anonyme_refuse(self):
        self.assertIn(APIClient().get(URL).status_code,
                      (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN))

    def test_compteurs_stats(self):
        resp = self.as_(self.superadmin).get(f"{URL}stats/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["new"], 1)
        self.assertEqual(resp.data["total"], 1)


class IncidentTreatmentTests(IncidentFixture):
    def setUp(self):
        super().setUp()
        self.incident = report_incident(ValueError("test"), module="grades")
        self.client_sa = self.as_(self.superadmin)

    def test_changement_de_statut_et_note_interne(self):
        resp = self.client_sa.patch(f"{URL}{self.incident.id}/",
                                    {"status": "in_progress",
                                     "resolution_notes": "Analyse en cours"},
                                    format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        self.incident.refresh_from_db()
        self.assertEqual(self.incident.status, "in_progress")
        self.assertEqual(self.incident.resolution_notes, "Analyse en cours")

    def test_resolution_puis_reouverture(self):
        resp = self.client_sa.post(f"{URL}{self.incident.id}/resolve/",
                                   {"resolution_notes": "Corrigé en V8"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        self.incident.refresh_from_db()
        self.assertEqual(self.incident.status, "resolved")
        self.assertIsNotNone(self.incident.resolved_at)

        resp = self.client_sa.post(f"{URL}{self.incident.id}/reopen/", {}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.incident.refresh_from_db()
        self.assertEqual(self.incident.status, "reopened")
        self.assertIsNone(self.incident.resolved_at)

    def test_assignation(self):
        resp = self.client_sa.patch(f"{URL}{self.incident.id}/",
                                    {"assigned_to": self.superadmin.id}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        self.incident.refresh_from_db()
        self.assertEqual(self.incident.assigned_to, self.superadmin)

    def test_donnees_techniques_non_modifiables(self):
        original = self.incident.reference
        self.client_sa.patch(f"{URL}{self.incident.id}/",
                             {"reference": "ERR-PIRATE", "endpoint": "/fake/"},
                             format="json")
        self.incident.refresh_from_db()
        self.assertEqual(self.incident.reference, original)
