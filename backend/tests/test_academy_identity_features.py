"""
Capacités liées au site public, calculées par le serveur — jamais par le nom
d'une académie dans le frontend.

  online_admissions / monthly_reports   académie PUBLIC_SITE_ONLINE_ACADEMY_CODE
  public_preregistrations               académie PUBLIC_SITE_CAMPUS_ACADEMY_CODE

Défaut corrigé : le menu « Admissions FEBA FHA » et « Rapports mensuels »
s'affichait pour TOUTE académie en ligne (drapeau `placement_tests`), et un
onglet « Préinscriptions FEBA » pour toute académie présentielle. Une
nouvelle académie (« testete ») voyait donc des écrans d'une autre.
"""
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.accounts.models import CustomUser
from apps.schools.models import School
from apps.website.fha_serializers import get_feba_entity, get_fha_entity


class Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        # Présentes dès les migrations de données sur certaines bases.
        cls.feba, _ = School.objects.get_or_create(code="FEBA", defaults=dict(
            name="Faith & Excellence Bilingual Academy", address="Cotonou", entity_type="campus"))
        cls.fha, _ = School.objects.get_or_create(code="FEBA_FHA", defaults=dict(
            name="FEBA French Heritage Academy", address="En ligne", entity_type="online"))
        cls.testete_online = School.objects.create(
            name="Académie Évangélique Saint-Éloi en ligne", code="TESTETE", address="x",
            entity_type="online")
        cls.testete_campus = School.objects.create(
            name="Lycée Saint-Éloi de Natitingou", code="TESTETE_CAMPUS", address="x",
            entity_type="campus")

    def admin(self, school):
        user = CustomUser.objects.create_user(
            username=f"a_{school.code}".lower(), email=f"a.{school.code}@feat.test".lower(),
            password="Pass1234!", role="admin", school=school)
        client = APIClient()
        client.force_authenticate(user)
        return client


class ComputedFeatureTests(Base):

    def test_capacites_calculees(self):
        expected = {
            "FEBA": (False, False, True),
            "FEBA_FHA": (True, True, False),
            "TESTETE": (False, False, False),         # en ligne, mais sans canal du site
            "TESTETE_CAMPUS": (False, False, False),  # présentielle, mais sans canal du site
        }
        for code, (admissions, reports, prereg) in expected.items():
            with self.subTest(code=code):
                features = School.objects.get(code=code).features
                self.assertEqual(features["online_admissions"], admissions)
                self.assertEqual(features["monthly_reports"], reports)
                self.assertEqual(features["public_preregistrations"], prereg)
        # La fonctionnalité de type reste, elle, liée au type d'entité.
        self.assertTrue(self.testete_online.features["placement_tests"])

    def test_capacite_non_falsifiable_par_les_reglages(self):
        School.objects.filter(pk=self.testete_online.pk).update(
            settings={"features": {"online_admissions": True, "monthly_reports": True}})
        features = School.objects.get(pk=self.testete_online.pk).features
        self.assertFalse(features["online_admissions"])
        self.assertFalse(features["monthly_reports"])

    def test_contexte_d_entite_servi_au_frontend(self):
        ctx = self.admin(self.testete_online).get("/api/auth/entity-context/").data
        self.assertEqual(ctx["active_entity"]["name"], "Académie Évangélique Saint-Éloi en ligne")
        self.assertFalse(ctx["features"]["online_admissions"])
        self.assertFalse(ctx["features"]["monthly_reports"])
        ctx = self.admin(self.fha).get("/api/auth/entity-context/").data
        self.assertTrue(ctx["features"]["online_admissions"])

    @override_settings(PUBLIC_SITE_ONLINE_ACADEMY_CODE="TESTETE", PUBLIC_SITE_CAMPUS_ACADEMY_CODE="TESTETE_CAMPUS")
    def test_le_rattachement_du_site_est_un_reglage(self):
        self.assertTrue(School.objects.get(code="TESTETE").features["online_admissions"])
        self.assertFalse(School.objects.get(code="FEBA_FHA").features["online_admissions"])
        self.assertTrue(School.objects.get(code="TESTETE_CAMPUS").features["public_preregistrations"])
        self.assertEqual(get_fha_entity().code, "TESTETE")
        self.assertEqual(get_feba_entity().code, "TESTETE_CAMPUS")


class ServerGuardTests(Base):

    def test_rapports_mensuels_refuses_a_testete(self):
        r = self.admin(self.testete_online).get("/api/monthly-reports/reports/")
        self.assertEqual(r.status_code, 403)
        self.assertIn("pas activés pour cette académie", str(r.data))
        self.assertNotIn("FEBA", str(r.data))
        self.assertEqual(self.admin(self.fha).get("/api/monthly-reports/reports/").status_code, 200)

    def test_admissions_de_testete_vides_et_sans_acces_aux_dossiers_d_une_autre(self):
        from apps.website.models import FHAEnrollmentApplication

        fields = {f.name for f in FHAEnrollmentApplication._meta.get_fields()}
        self.assertIn("entity", fields)
        r = self.admin(self.testete_online).get("/api/website/admin/fha-applications/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.data.get("results", r.data)), 0)
