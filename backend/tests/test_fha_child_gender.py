"""
P0 — Sexe de l'enfant sur la fiche de renseignements FEBA FHA.

Constat : l'étape 1/12 « Informations sur l'enfant » ne demandait pas le
sexe ; il manquait donc au dossier et à la fiche PDF. Ces tests suivent le
parcours entier : saisie validée, enregistrement, API d'administration,
fiche PDF, e-mail aux administrateurs, dossiers antérieurs sans valeur.
"""
import datetime
import importlib

import fitz
from django.core import mail
from django.test import override_settings
from rest_framework.test import APIClient

from apps.website.models import FHAEnrollmentApplication

from .test_fha_enrollment_workflow import EnrollmentBaseTests, payload

ADMIN_URL = "/api/website/admin/fha-applications/"


def pdf_text(application):
    with open(application.sheet_absolute_path, "rb") as handle:
        document = fitz.open(stream=handle.read(), filetype="pdf")
    return "\n".join(page.get_text() for page in document)


class ChildGenderSubmissionTests(EnrollmentBaseTests):

    def test_le_sexe_est_obligatoire_pour_une_nouvelle_fiche(self):
        data = payload()
        del data["child_gender"]
        response = APIClient().post("/api/website/fha/enroll/", data, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(str(response.data["child_gender"][0]),
                         "Le sexe de l'enfant est obligatoire.")
        self.assertEqual(FHAEnrollmentApplication.objects.count(), 0)

    def test_valeur_vide_refusee(self):
        response = self.submit(child_gender="")
        self.assertEqual(response.status_code, 400)
        self.assertIn("child_gender", response.data)

    def test_valeur_inconnue_refusee(self):
        for value in ("X", "female", "1", "f"):
            with self.subTest(valeur=value):
                response = self.submit(child_gender=value)
                self.assertEqual(response.status_code, 400)
                self.assertIn("child_gender", response.data)
        self.assertEqual(FHAEnrollmentApplication.objects.count(), 0)

    def test_feminin_et_masculin_sont_enregistres(self):
        girl = self.submit(child_gender="F")
        boy = self.submit(child_gender="M", child_first_name="Koffi",
                          parent1_email="koffi.parent@test.io")
        self.assertEqual(girl.status_code, 201, girl.data)
        self.assertEqual(boy.status_code, 201, boy.data)
        self.assertEqual(
            FHAEnrollmentApplication.objects.get(reference=girl.data["reference"]).child_gender, "F")
        self.assertEqual(
            FHAEnrollmentApplication.objects.get(reference=boy.data["reference"]).child_gender, "M")


class ChildGenderAdminAndDocumentTests(EnrollmentBaseTests):

    def setUp(self):
        self.girl = FHAEnrollmentApplication.objects.get(
            reference=self.submit(child_gender="F").data["reference"])
        self.boy = FHAEnrollmentApplication.objects.get(
            reference=self.submit(child_gender="M", child_first_name="Koffi",
                                  parent1_email="koffi.parent@test.io").data["reference"])
        self.admin = APIClient()
        self.admin.force_authenticate(user=self.fha_admin)

    def test_l_api_d_administration_renvoie_le_sexe(self):
        detail = self.admin.get(f"{ADMIN_URL}{self.girl.pk}/")
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.data["child_gender"], "F")
        listing = self.admin.get(ADMIN_URL)
        rows = listing.data.get("results", listing.data)
        by_ref = {row["reference"]: row for row in rows}
        self.assertEqual(by_ref[self.girl.reference]["child_gender"], "F")
        self.assertEqual(by_ref[self.boy.reference]["child_gender"], "M")

    def test_un_administrateur_d_une_autre_academie_ne_voit_pas_le_dossier(self):
        other = APIClient()
        other.force_authenticate(user=self.feba_admin)
        self.assertEqual(other.get(f"{ADMIN_URL}{self.girl.pk}/").status_code, 404)

    def test_la_fiche_pdf_porte_le_sexe_enregistre(self):
        girl_text = pdf_text(self.girl)
        boy_text = pdf_text(self.boy)
        self.assertIn("Sexe", girl_text)
        self.assertIn("Féminin", girl_text)
        self.assertNotIn("Masculin", girl_text)
        self.assertIn("Masculin", boy_text)
        self.assertNotIn("Féminin", boy_text)

    def test_correction_du_sexe_puis_regeneration_de_la_fiche(self):
        """La fiche reflète la valeur ENREGISTRÉE, pas un état antérieur."""
        from apps.website.fha_enrollment import generate_and_store_sheet

        self.girl.child_gender = "M"
        self.girl.save(update_fields=["child_gender"])
        generate_and_store_sheet(self.girl)
        self.girl.refresh_from_db()
        text = pdf_text(self.girl)
        self.assertIn("Masculin", text)
        self.assertNotIn("Féminin", text)


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class LegacyApplicationTests(EnrollmentBaseTests):
    """Dossiers reçus AVANT l'ajout du champ : lisibles, jamais complétés à tort."""

    def make_legacy(self):
        return FHAEnrollmentApplication.objects.create(
            entity=self.fha, child_last_name="Ancien", child_first_name="Dossier",
            child_birth_date=datetime.date(2014, 2, 3), parent1_last_name="P",
            parent1_first_name="Q", parent1_phone="+1 215 555 0100",
            parent1_email="ancien@test.io",
        )

    def test_dossier_ancien_sans_sexe_reste_lisible(self):
        legacy = self.make_legacy()
        self.assertEqual(legacy.child_gender, "")
        admin = APIClient()
        admin.force_authenticate(user=self.fha_admin)
        detail = admin.get(f"{ADMIN_URL}{legacy.pk}/")
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.data["child_gender"], "")

    def test_fiche_d_un_dossier_ancien_affiche_non_renseigne(self):
        from apps.website.fha_enrollment import generate_and_store_sheet

        legacy = self.make_legacy()
        generate_and_store_sheet(legacy)
        legacy.refresh_from_db()
        text = pdf_text(legacy)
        self.assertIn("Non renseigné", text)
        self.assertNotIn("Féminin", text)
        self.assertNotIn("Masculin", text)

    def test_la_migration_ajoute_un_champ_vide_sans_rien_inventer(self):
        migration = importlib.import_module(
            "apps.website.migrations.0012_fha_child_gender").Migration
        (operation,) = migration.operations
        self.assertEqual(operation.name, "child_gender")
        self.assertTrue(operation.field.blank)
        self.assertEqual(operation.field.default, "")

    def test_l_alerte_aux_administrateurs_mentionne_le_sexe(self):
        from apps.website.fha_enrollment import admin_alert_bodies

        response = self.submit(child_gender="M")
        application = FHAEnrollmentApplication.objects.get(reference=response.data["reference"])
        _subject, text, html = admin_alert_bodies(application)
        self.assertIn("Masculin", text)
        self.assertIn("Masculin", html)
        self.assertIn("Non renseigné", admin_alert_bodies(self.make_legacy())[1])
        mail.outbox.clear()
