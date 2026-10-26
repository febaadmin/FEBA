"""
Logo actif = source de vérité, partout ; favicons et identité publique.

Défauts reproduits sur le code livré (commit 575d493) :
  - `get_branding().document_logo` prenait l'image statique AVANT le logo
    téléversé et activé : tous les PDF ignoraient le logo activé ;
  - `/schools/branding/active/` répondait 401 sans connexion : le site public
    et la page de connexion n'affichaient jamais le logo activé ;
  - le téléversement acceptait n'importe quel fichier nommé .png et gardait
    le nom d'origine (URL réutilisée, cache) ; plusieurs versions pouvaient
    être actives ; un super administrateur sans académie sélectionnée posait
    le logo sur l'académie envoyée par la page (« la première » ou 1).

Les contrôles PDF lisent les IMAGES réellement incorporées (PyMuPDF).
"""
import datetime
import io
import shutil
import tempfile

import fitz
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from PIL import Image
from rest_framework.test import APIClient

from apps.accounts.models import CustomUser
from apps.schools.branding import STATIC_FILES_DIR, get_branding
from apps.schools.models import School, SchoolBranding


def png_bytes(color, size=(200, 200), fmt="PNG"):
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, format=fmt)
    return buf.getvalue()


def upload(name, data, ctype="image/png"):
    return SimpleUploadedFile(name, data, content_type=ctype)


def dominant_color_of_images(pdf_path):
    """Couleurs moyennes des images incorporées dans la 1re page."""
    doc = fitz.open(pdf_path)
    colors = []
    try:
        for xref, *_ in doc[0].get_images(full=True):
            pix = fitz.Pixmap(doc, xref)
            if pix.n - pix.alpha >= 3:
                img = Image.frombytes("RGB" if not pix.alpha else "RGBA", (pix.width, pix.height), pix.samples)
                colors.append(img.convert("RGB").resize((1, 1), Image.BOX).getpixel((0, 0)))
    finally:
        doc.close()
    return colors


class Base(TestCase):
    def setUp(self):
        self.media = tempfile.mkdtemp()
        self._ov = override_settings(MEDIA_ROOT=self.media)
        self._ov.enable()
        self.feba = School.objects.get_or_create(code="FEBA", defaults={
            "name": "Faith & Excellence Bilingual Academy", "address": "Akpakpa", "entity_type": "campus"})[0]
        self.fha = School.objects.get_or_create(code="FEBA_FHA", defaults={
            "name": "FEBA French Heritage Academy", "address": "En ligne", "entity_type": "online"})[0]
        mk = lambda u, role, school: CustomUser.objects.create_user(  # noqa: E731
            username=u, email=f"{u}@t.bj", password="Pass1234!", role=role, school=school,
            first_name="A", last_name="B")
        self.admin = mk("adm_feba", "admin", self.feba)
        self.admin_fha = mk("adm_fha", "admin", self.fha)
        self.su = mk("su", "superadmin", None)
        self.c = APIClient()
        self.c.force_authenticate(self.admin)

    def tearDown(self):
        self._ov.disable()
        shutil.rmtree(self.media, ignore_errors=True)

    def activate_logo(self, school, color):
        b = SchoolBranding(school=school, label=str(color))
        b.logo.save("logo.png", io.BytesIO(png_bytes(color)), save=True)
        b.activate()
        return b


class SourceOfTruthTests(Base):
    def test_le_logo_active_prime_dans_les_documents(self):
        default = get_branding(self.feba).document_logo
        self.assertTrue(default.endswith("feba_logo_document.png"))     # logo fourni, en repli
        b = self.activate_logo(self.feba, (255, 0, 0))
        brand = get_branding(self.feba)
        self.assertEqual(brand.logo, b.logo.path)
        self.assertEqual(brand.document_logo, b.logo.path)              # avant : logo_feba.jpeg
        self.assertTrue(brand.logo_is_uploaded)

    def test_logo_documentaire_administre_explicitement_reste_prioritaire(self):
        self.activate_logo(self.feba, (255, 0, 0))
        self.feba.settings = {"branding": {"document_logo": "logo_groupe_feba.png"}}
        self.feba.save(update_fields=["settings"])
        self.assertTrue(get_branding(self.feba).document_logo.endswith("logo_groupe_feba.png"))

    def test_une_academie_n_herite_jamais_du_logo_d_une_autre(self):
        before = get_branding(self.fha).document_logo
        self.activate_logo(self.feba, (255, 0, 0))
        self.assertEqual(get_branding(self.fha).document_logo, before)
        self.assertFalse(get_branding(self.fha).logo_is_uploaded)

    def test_le_bulletin_pdf_incorpore_le_logo_actif(self):
        from datetime import date
        from apps.bulletins.pdf_generator import generate_bulletin
        from apps.classes.models import Class
        from apps.schools.models import Level, SchoolYear
        from apps.students.models import Student
        year = SchoolYear.objects.create(school=self.feba, name="2026-2027", start_date=date(2026, 9, 1),
                                         end_date=date(2027, 7, 31), is_current=True)
        cls = Class.objects.create(name="CE1", level=Level.objects.create(school=self.feba, name="CE1", order=1),
                                   school_year=year)
        st = Student.objects.create(school=self.feba, first_name="E", last_name="L", current_class=cls,
                                    school_year=year)
        self.activate_logo(self.feba, (255, 0, 0))
        b = generate_bulletin(st, "T1", year)
        reds = [c for c in dominant_color_of_images(b.pdf_file.path) if c[0] > 200 and c[1] < 60 and c[2] < 60]
        self.assertTrue(reds, "le logo rouge activé n'est pas dans le PDF")
        # Nouvelle activation : le PDF régénéré change de logo.
        self.activate_logo(self.feba, (0, 0, 255))
        b = generate_bulletin(st, "T1", year)
        colors = dominant_color_of_images(b.pdf_file.path)
        self.assertTrue([c for c in colors if c[2] > 200 and c[0] < 60])
        self.assertFalse([c for c in colors if c[0] > 200 and c[1] < 60 and c[2] < 60])


class UploadTests(Base):
    def post(self, f, client=None, **extra):
        return (client or self.c).post("/api/schools/branding/", {"logo": f, "label": "x", **extra},
                                       format="multipart")

    def test_televersement_valide_active_et_nom_unique(self):
        r1 = self.post(upload("logo.png", png_bytes((10, 200, 10))))
        self.assertEqual(r1.status_code, 201, r1.data)
        r2 = self.post(upload("logo.png", png_bytes((10, 10, 200))))
        self.assertEqual(r2.status_code, 201)
        b1, b2 = SchoolBranding.objects.get(pk=r1.data["id"]), SchoolBranding.objects.get(pk=r2.data["id"])
        self.assertNotEqual(b1.logo.name, b2.logo.name)                 # jamais la même URL
        self.assertNotIn("logo.png", b2.logo.name)
        self.assertEqual(b2.school, self.feba)
        self.assertEqual(SchoolBranding.objects.filter(school=self.feba, is_active=True).get().pk, b2.pk)

    def test_fichiers_invalides_refuses(self):
        cases = [
            upload("faux.png", b"ceci n'est pas une image"),
            upload("svg.png", b'<svg xmlns="http://www.w3.org/2000/svg"></svg>', "image/svg+xml"),
            upload("tout_petit.png", png_bytes((1, 2, 3), size=(10, 10))),
            upload("anim.gif", png_bytes((1, 2, 3), fmt="GIF"), "image/gif"),
        ]
        for f in cases:
            r = self.post(f)
            self.assertEqual(r.status_code, 400, f.name)
        self.assertFalse(SchoolBranding.objects.exists())

    def test_academie_imposee_par_le_contexte(self):
        r = self.post(upload("l.png", png_bytes((1, 200, 1))), school=self.fha.pk)
        self.assertEqual(r.status_code, 400)                             # admin FEBA → logo FHA refusé
        self.assertFalse(SchoolBranding.objects.filter(school=self.fha).exists())
        su = APIClient()
        su.force_authenticate(self.su)
        r = self.post(upload("l.png", png_bytes((1, 200, 1))), client=su)
        self.assertEqual(r.status_code, 400)                             # super admin : académie obligatoire
        r = self.post(upload("l.png", png_bytes((1, 200, 1))), client=su, school=self.fha.pk)
        self.assertEqual(r.status_code, 201)
        self.assertEqual(SchoolBranding.objects.get(pk=r.data["id"]).school, self.fha)

    def test_une_seule_version_active_et_activation_atomique(self):
        a = self.activate_logo(self.feba, (1, 1, 1))
        b = self.activate_logo(self.feba, (2, 2, 2))
        a.refresh_from_db()
        self.assertFalse(a.is_active)
        with self.assertRaises(IntegrityError), transaction.atomic():
            SchoolBranding.objects.filter(pk=a.pk).update(is_active=True)   # contrainte en base
        r = self.c.patch(f"/api/schools/branding/{a.pk}/", {"is_active": True}, format="json")
        a.refresh_from_db()
        self.assertFalse(a.is_active)                                      # champ en lecture seule
        r = self.c.post(f"/api/schools/branding/{a.pk}/activate/")
        self.assertEqual(r.status_code, 200)
        b.refresh_from_db()
        self.assertFalse(b.is_active)

    def test_la_version_active_ne_se_supprime_pas(self):
        a = self.activate_logo(self.feba, (1, 1, 1))
        r = self.c.delete(f"/api/schools/branding/{a.pk}/")
        self.assertEqual(r.status_code, 400)
        self.assertTrue(SchoolBranding.objects.filter(pk=a.pk).exists())

    def test_une_autre_academie_ne_voit_ni_n_active_le_logo(self):
        a = self.activate_logo(self.feba, (1, 1, 1))
        other = APIClient()
        other.force_authenticate(self.admin_fha)
        self.assertEqual(other.post(f"/api/schools/branding/{a.pk}/activate/").status_code, 404)
        data = other.get("/api/schools/branding/").json()
        self.assertNotIn(a.pk, [x["id"] for x in data.get("results", data)])


class PublicBrandingTests(Base):
    def get(self, url):
        return APIClient().get(url)                                        # sans authentification

    def test_identite_publique_sans_connexion(self):
        r = self.get("/api/schools/public-branding/FEBA/")
        self.assertEqual(r.status_code, 200)
        d = r.json()
        self.assertEqual(d["meeting_title"], "FEBA - Faith & Excellence Bilingual Academy")
        self.assertTrue(d["logo_url"].startswith("/api/schools/public-branding/FEBA/logo/?v="))
        for key in ("settings", "subscription_notes", "plan", "email"):
            self.assertNotIn(key, d)
        self.assertEqual(self.get("/api/schools/public-branding/FEBA_FHA/").json()["meeting_title"],
                         "FEBA FHA - FEBA")
        self.assertEqual(self.get("/api/schools/public-branding/INCONNU/").status_code, 404)

    def test_favicons_fournis_puis_derives_du_logo_active(self):
        provided = open(f"{STATIC_FILES_DIR}/favicon-32x32.png", "rb").read()
        r = self.get("/api/schools/public-branding/FEBA/favicon-32.png")
        self.assertEqual(r.content, provided)                              # favicon fourni, à l'octet près
        v1 = self.get("/api/schools/public-branding/FEBA/").json()["version"]
        self.activate_logo(self.feba, (255, 0, 0))
        d = self.get("/api/schools/public-branding/FEBA/").json()
        self.assertNotEqual(d["version"], v1)                              # nouvelle URL
        fav = Image.open(io.BytesIO(self.get("/api/schools/public-branding/FEBA/favicon-32.png").content))
        self.assertEqual(fav.size, (32, 32))
        self.assertEqual(fav.convert("RGB").getpixel((16, 16)), (255, 0, 0))
        logo = self.get(d["logo_url"])
        self.assertEqual(Image.open(io.BytesIO(logo.content)).convert("RGB").getpixel((5, 5)), (255, 0, 0))
        self.assertIn("immutable", logo["Cache-Control"])

    def test_l_activation_d_une_academie_ne_touche_pas_l_autre(self):
        before = self.get("/api/schools/public-branding/FEBA_FHA/").json()
        fha_fav = self.get("/api/schools/public-branding/FEBA_FHA/favicon-32.png").content
        self.activate_logo(self.feba, (255, 0, 0))
        self.assertEqual(self.get("/api/schools/public-branding/FEBA_FHA/").json()["version"], before["version"])
        self.assertEqual(self.get("/api/schools/public-branding/FEBA_FHA/favicon-32.png").content, fha_fav)
        provided = open(f"{STATIC_FILES_DIR}/favicon-32x32.png", "rb").read()
        self.assertNotEqual(fha_fav, provided)                             # FHA n'a pas le favicon FEBA


class DocumentsRefreshTests(Base):
    """Documents courants produits avec un ancien logo : identifiés puis régénérés."""

    def setUp(self):
        super().setUp()
        from datetime import date
        from decimal import Decimal
        from apps.classes.models import Class
        from apps.payments.models import Payment
        from apps.schools.models import Level, SchoolYear
        from apps.students.models import Student
        self.year = SchoolYear.objects.create(school=self.feba, name="2026-2027", start_date=date(2026, 9, 1),
                                              end_date=date(2027, 7, 31), is_current=True)
        cls = Class.objects.create(name="CE1", level=Level.objects.create(school=self.feba, name="CE1", order=1),
                                   school_year=self.year)
        self.st = Student.objects.create(school=self.feba, first_name="E", last_name="L", current_class=cls,
                                         school_year=self.year)
        self.pay = Payment.objects.create(student=self.st, school_year=self.year, amount=Decimal("150000"),
                                          payment_type="tuition", payment_method="cash", received_by=self.admin)

    def run_cmd(self, *args):
        from django.core.management import call_command
        out = io.StringIO()
        call_command("branding_refresh_documents", "--academy", "FEBA", *args, stdout=out)
        return out.getvalue()

    def test_aperçu_puis_application_puis_idempotence(self):
        import os
        import time
        from apps.bulletins.models import Bulletin
        from apps.bulletins.pdf_generator import generate_bulletin
        from apps.payments.pdf_generator import generate_receipt
        b = generate_bulletin(self.st, "T1", self.year)
        Bulletin.objects.filter(pk=b.pk).update(general_comment="Conservé")
        generate_receipt(self.pay)
        self.pay.refresh_from_db()
        old_b, old_r = b.pdf_file.name, self.pay.receipt_file.name
        past = time.time() - 3600
        for path in (b.pdf_file.path, self.pay.receipt_file.path):
            os.utime(path, (past, past))                                   # produits « avant »
        self.activate_logo(self.feba, (255, 0, 0))

        out = self.run_cmd()                                                # aperçu : rien ne change
        self.assertIn("bulletins          1 documents ·     1 antérieurs au logo", out)
        self.assertIn("receipts           1 documents ·     1 antérieurs au logo", out)
        b.refresh_from_db()
        self.assertEqual(b.pdf_file.name, old_b)

        out = self.run_cmd("--apply")
        self.assertIn("1 régénérés · 0 échecs", out)
        b.refresh_from_db()
        self.pay.refresh_from_db()
        self.assertNotEqual(b.pdf_file.name, old_b)
        self.assertNotEqual(self.pay.receipt_file.name, old_r)             # nouvelle URL
        self.assertEqual(b.general_comment, "Conservé")
        for path in (b.pdf_file.path, self.pay.receipt_file.path):
            reds = [c for c in dominant_color_of_images(path) if c[0] > 200 and c[1] < 60 and c[2] < 60]
            self.assertTrue(reds, f"logo actif absent de {path}")
        self.assertFalse(b.pdf_file.storage.exists(old_b))
        self.assertFalse(self.pay.receipt_file.storage.exists(old_r))

        out = self.run_cmd()                                                # idempotent
        self.assertIn("bulletins          1 documents ·     0 antérieurs au logo", out)

    def test_un_echec_conserve_l_ancien_fichier(self):
        import os
        import time
        from unittest import mock
        from django.core.management.base import CommandError
        from apps.bulletins.pdf_generator import generate_bulletin
        b = generate_bulletin(self.st, "T1", self.year)
        past = time.time() - 3600
        os.utime(b.pdf_file.path, (past, past))
        self.activate_logo(self.feba, (255, 0, 0))
        with mock.patch("apps.bulletins.pdf_generator._build_standard_pdf", side_effect=RuntimeError("panne")):
            with self.assertRaises(CommandError):
                self.run_cmd("--apply", "--kinds", "bulletins")
        b2 = type(b).objects.get(pk=b.pk)
        self.assertEqual(b2.pdf_file.name, b.pdf_file.name)
        self.assertTrue(b2.pdf_file.storage.exists(b2.pdf_file.name))


class EmbeddedShieldTests(Base):
    """Diplômes / certificats : blason incrusté dans le fond, remplacé par le logo ACTIVÉ."""

    VALUES = {"student_name": "Naomi Adjovi", "issue_date": datetime.date(2026, 10, 26),
              "director_name": "D", "teacher_name": "T", "document_number": "X-1"}

    def colors(self, pdf):
        path = f"{self.media}/doc.pdf"
        open(path, "wb").write(pdf)
        return dominant_color_of_images(path)

    def test_sans_logo_active_le_fond_officiel_reste_intact(self):
        from apps.documents.renderer import render_document
        pdf = render_document("diploma_feba", self.VALUES, branding=get_branding(self.feba))
        self.assertFalse([c for c in self.colors(pdf) if c[0] > 200 and c[1] < 60 and c[2] < 60])

    def test_logo_active_appose_sur_les_quatre_gabarits(self):
        from apps.documents.renderer import render_document
        self.activate_logo(self.feba, (255, 0, 0))
        self.activate_logo(self.fha, (255, 0, 0))
        for tid, school in (("diploma_feba", self.feba), ("certificate_feba", self.feba),
                            ("diploma_feba_fha", self.fha), ("certificate_feba_fha", self.fha)):
            pdf = render_document(tid, self.VALUES, branding=get_branding(school))
            reds = [c for c in self.colors(pdf) if c[0] > 200 and c[1] < 60 and c[2] < 60]
            self.assertTrue(reds, f"logo activé absent de {tid}")
