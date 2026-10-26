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

    FOREIGN = ("Faith & Excellence", "French Heritage", "FEBA FHA", "Akpakpa")

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
