"""
Audit multi-académies du 26/10/2026 — défauts trouvés par la campagne
d'isolation (2, 7, 19 académies) et l'audit global, avec leurs tests de
non-régression.
"""
from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import CustomUser

from .academy_fixtures import build_academy


class EmailConfigScopeTests(TestCase):
    """`/api/notifications/email-config/` listait toutes les académies à tout administrateur."""

    def setUp(self):
        self.a = build_academy("CFA", "physical_primary")
        self.b = build_academy("CFB", "online")

    def test_un_administrateur_ne_voit_que_son_expediteur(self):
        c = APIClient()
        c.force_authenticate(self.a.admin)
        senders = c.get("/api/notifications/email-config/").data["academy_senders"]
        self.assertEqual([s["code"] for s in senders], ["AC_CFA"])

    def test_le_super_administrateur_voit_toutes_les_academies(self):
        su = CustomUser.objects.create_user(username="su", email="su@x.io", password="Pass1234!",
                                            role="superadmin", first_name="S", last_name="U")
        c = APIClient()
        c.force_authenticate(su)
        codes = {s["code"] for s in c.get("/api/notifications/email-config/").data["academy_senders"]}
        self.assertTrue({"AC_CFA", "AC_CFB"} <= codes)


class NewAcademyDocumentsIdentityTests(TestCase):
    """Les documents d'une académie créée par l'écran ne portent que SON identité."""

    def setUp(self):
        import tempfile

        from django.test import override_settings

        self._media = override_settings(MEDIA_ROOT=tempfile.mkdtemp())
        self._media.enable()
        self.addCleanup(self._media.disable)
        self.academy = build_academy("NEUVE", "physical_secondary")

    @staticmethod
    def _text(field_file):
        import fitz

        with field_file.open("rb") as fh:
            doc = fitz.open(stream=fh.read(), filetype="pdf")
        return " ".join(" ".join(page.get_text() for page in doc).split())

    # Ni nom, ni adresse, ni numéro institutionnel du groupe FEBA.
    FOREIGN = ("Faith & Excellence", "French Heritage", "FEBA FHA", "Akpakpa", "0160011717")

    def test_bulletin_et_recu(self):
        from apps.bulletins.pdf_generator import generate_bulletin
        from apps.payments.pdf_generator import generate_receipt

        bulletin = generate_bulletin(self.academy.student, "T1", self.academy.year)
        generate_receipt(self.academy.payment)
        self.academy.payment.refresh_from_db()
        for name, text in (("bulletin", self._text(bulletin.pdf_file)),
                           ("reçu", self._text(self.academy.payment.receipt_file))):
            with self.subTest(document=name):
                self.assertIn("NEUVE", text.upper())
                for foreign in self.FOREIGN:
                    self.assertNotIn(foreign, text)

    def test_diplomes_des_autres_academies_refuses(self):
        c = APIClient()
        c.force_authenticate(self.academy.admin)
        data = c.get("/api/documents/templates/").data
        self.assertTrue(data["templates"])
        for template in data["templates"]:
            with self.subTest(gabarit=template["id"]):
                self.assertFalse(template["allowed_for_academy"])
                self.assertFalse(template["can_issue"])


class DemoSeedTests(TestCase):
    """
    Le jeu de démonstration doit s'installer sans erreur. Une valeur posée
    sur le mauvais modèle (le sexe sur une demande de test de placement)
    l'a fait échouer sans qu'aucun test ne le voie : trouvé au démarrage de
    la pile locale.
    """

    def test_seed_demo_data_complet(self):
        import io
        import tempfile

        from django.core.management import call_command
        from django.test import override_settings

        from apps.schools.models import School
        from apps.website.models import FHAEnrollmentApplication

        with override_settings(MEDIA_ROOT=tempfile.mkdtemp()):
            call_command("seed_demo_data", stdout=io.StringIO())
        self.assertTrue(School.objects.filter(code="FEBA").exists())
        self.assertEqual(
            set(FHAEnrollmentApplication.objects.values_list("child_gender", flat=True)), {"F"})
        # FEBA de démonstration mêle primaire et collège : non classée, jamais devinée.
        self.assertIsNone(School.objects.get(code="FEBA").academy_type)
        self.assertEqual(School.objects.get(code="FEBA_FHA").academy_type, "online")
        # Chaque académie de démonstration a SON barème, modifiable à l'écran.
        from apps.grades.models import AppreciationRule
        for code in ("FEBA", "FEBA_FHA"):
            self.assertEqual(AppreciationRule.objects.filter(school__code=code, cycle="").count(), 9)


class InitAcademiesScaleTests(TestCase):

    def test_init_academies_installe_un_bareme_par_academie(self):
        import io

        from django.core.management import call_command

        from apps.grades.models import AppreciationRule
        from apps.schools.models import School

        School.objects.filter(code__in=["FEBA", "FEBA_FHA"]).delete()
        call_command("init_academies", stdout=io.StringIO())
        call_command("init_academies", stdout=io.StringIO())           # idempotent
        for code in ("FEBA", "FEBA_FHA"):
            self.assertEqual(AppreciationRule.objects.filter(school__code=code).count(), 9)


class LogoLessAcademyPublicBrandingTests(TestCase):
    """Académie sans logo : pas d'URL de logo annoncée, favicon monogramme (jamais 404)."""

    def test_payload_et_favicons(self):
        import io as _io

        from PIL import Image

        academy = build_academy("SANSLOGO", "physical_primary").school
        c = APIClient()
        data = c.get(f"/api/schools/public-branding/{academy.code}/").data
        self.assertIsNone(data["logo_url"])
        self.assertEqual(c.get(f"/api/schools/public-branding/{academy.code}/logo/").status_code, 404)
        feba = APIClient().get("/api/schools/public-branding/FEBA/favicon-32.png")
        for size in (16, 32, 180):
            with self.subTest(taille=size):
                r = c.get(f"/api/schools/public-branding/{academy.code}/favicon-{size}.png")
                self.assertEqual(r.status_code, 200)
                body = b"".join(r.streaming_content) if r.streaming else r.content
                self.assertEqual(Image.open(_io.BytesIO(body)).size, (size, size))
                if size == 32 and feba.status_code == 200:
                    feba_body = b"".join(feba.streaming_content) if feba.streaming else feba.content
                    self.assertNotEqual(body, feba_body)
