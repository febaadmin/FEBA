"""
Gabarits officiels téléversés par académie — diplômes et certificats.

CE QUI EST ÉPROUVÉ ICI, ET COMMENT
----------------------------------
Rien n'est vérifié sur le seul code HTTP. Chaque document produit est
OUVERT (pypdf pour le texte, PDFium pour l'image) :
  - le texte extrait doit contenir le nom, le matricule, l'académie… ;
  - la couleur relevée dans une zone vide de la page doit être celle du
    fond de CETTE académie et de CE type — les quatre fonds de test sont
    de couleurs différentes (A : rouge / vert, B : bleu / jaune) ;
  - la taille de page doit être celle du gabarit (paysage ou portrait).

Les fonds sont fabriqués par le test (PNG, JPEG, PDF vectoriel) : ce sont
des fichiers réels, lus par les mêmes bibliothèques qu'en production.
"""
import io
import os
import shutil
import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.accounts.models import CustomUser
from apps.documents import academy_templates as uploads
from apps.documents.models import (
    AcademyDocumentTemplate, DocumentNumberSequence, GeneratedDocument,
)
from apps.schools.models import School
from apps.students.models import Student, StudentEnrollment
from tests.academy_fixtures import build_academy

RED, GREEN, BLUE, YELLOW = (200, 30, 30), (30, 160, 60), (30, 60, 200), (230, 200, 20)
BASE = "/api/documents/academy-templates/"


# ── Fabrication de fonds réels ────────────────────────────────────────

def png_bytes(color, size=(1754, 1240), fmt="PNG", exif_orientation=None):
    from PIL import Image, ImageDraw

    image = Image.new("RGB", size, color)
    draw = ImageDraw.Draw(image)
    draw.rectangle([15, 15, size[0] - 15, size[1] - 15], outline=(20, 20, 20), width=10)
    out = io.BytesIO()
    if exif_orientation:
        exif = Image.Exif()
        exif[0x0112] = exif_orientation
        image.save(out, fmt, exif=exif)
    else:
        image.save(out, fmt)
    return out.getvalue()


def pdf_bytes(color, *, portrait=False, pages=1, marker="FOND-B"):
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.pdfgen import canvas

    size = A4 if portrait else landscape(A4)
    out = io.BytesIO()
    pdf = canvas.Canvas(out, pagesize=size)
    for index in range(pages):
        pdf.setFillColorRGB(*(c / 255 for c in color))
        pdf.rect(0, 0, size[0], size[1], stroke=0, fill=1)
        pdf.setStrokeColorRGB(0.1, 0.1, 0.1)
        pdf.setLineWidth(6)
        pdf.rect(12, 12, size[0] - 24, size[1] - 24, stroke=1, fill=0)
        pdf.setFillColorRGB(0, 0, 0)
        pdf.setFont("Helvetica", 9)
        pdf.drawString(20, 20, f"{marker}-P{index + 1}")
        pdf.showPage()
    pdf.save()
    return out.getvalue()


def upload(name, content, content_type):
    return SimpleUploadedFile(name, content, content_type=content_type)


LANDSCAPE_FIELDS = [
    {"name": "student_name", "x_mm": 40, "y_mm": 80, "width_mm": 217, "height_mm": 22,
     "font": "serif_italic", "font_size_pt": 30, "min_font_size_pt": 12, "align": "center",
     "color": "#1E3A6E", "max_lines": 2, "required": True},
    {"name": "student_matricule", "x_mm": 40, "y_mm": 108, "width_mm": 100, "height_mm": 10,
     "font": "serif", "font_size_pt": 12, "align": "left", "color": "#000000"},
    {"name": "academy_name", "x_mm": 40, "y_mm": 40, "width_mm": 217, "height_mm": 14,
     "font": "serif", "font_size_pt": 18, "align": "center", "color": "#000000"},
    {"name": "issue_date", "x_mm": 180, "y_mm": 165, "width_mm": 70, "height_mm": 9,
     "font": "sans", "font_size_pt": 11, "align": "center", "color": "#000000"},
    {"name": "document_number", "x_mm": 180, "y_mm": 180, "width_mm": 90, "height_mm": 9,
     "font": "sans", "font_size_pt": 10, "align": "right", "color": "#000000"},
]
PORTRAIT_FIELDS = [
    {"name": "student_name", "x_mm": 20, "y_mm": 120, "width_mm": 170, "height_mm": 20,
     "font": "serif", "font_size_pt": 24, "min_font_size_pt": 10, "align": "center",
     "color": "#000000", "max_lines": 2, "required": True},
    {"name": "certificate_purpose", "x_mm": 20, "y_mm": 150, "width_mm": 170, "height_mm": 12,
     "font": "serif", "font_size_pt": 13, "align": "center", "color": "#000000"},
    {"name": "class_name", "x_mm": 20, "y_mm": 170, "width_mm": 80, "height_mm": 10,
     "font": "serif", "font_size_pt": 12, "align": "left", "color": "#000000"},
    {"name": "school_year", "x_mm": 110, "y_mm": 170, "width_mm": 80, "height_mm": 10,
     "font": "serif", "font_size_pt": 12, "align": "right", "color": "#000000"},
    {"name": "document_number", "x_mm": 110, "y_mm": 260, "width_mm": 80, "height_mm": 9,
     "font": "sans", "font_size_pt": 10, "align": "right", "color": "#000000"},
]


def pdf_text(content):
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(content))
    return " ".join((reader.pages[0].extract_text() or "").split()), reader


def pixel_at(content, x_mm, y_mm, page_w_mm, page_h_mm):
    """Couleur du rendu PDFium à cet endroit de la page."""
    from PIL import Image

    image = Image.open(io.BytesIO(uploads.pdf_to_png(content, 1200))).convert("RGB")
    return image.getpixel((int(x_mm / page_w_mm * image.width),
                           int(y_mm / page_h_mm * image.height)))


def close(color, expected, tolerance=40):
    return all(abs(a - b) <= tolerance for a, b in zip(color, expected))


@override_settings(PRIVATE_MEDIA_ROOT=tempfile.mkdtemp(prefix="feba-tpl-"))
class TemplateTestBase(TestCase):
    """Deux académies A et B, chacune avec administrateur et élève noté."""

    @classmethod
    def setUpTestData(cls):
        cls.A = build_academy("TPLA", "physical_secondary", grades=(16, 12))
        cls.B = build_academy("TPLB", "online", grades=(8, 6))
        cls.superadmin = CustomUser.objects.create_user(
            username="super.tpl", email="super.tpl@iso.test", password="Pass1234!",
            role="superadmin", school=cls.A.school)

    @classmethod
    def tearDownClass(cls):
        from django.conf import settings

        super().tearDownClass()
        shutil.rmtree(settings.PRIVATE_MEDIA_ROOT, ignore_errors=True)

    def client_for(self, user, academy=None):
        if user.is_superadmin():
            user.active_organization = academy
            user.save(update_fields=["active_organization"])
        client = APIClient()
        client.force_authenticate(user=user)
        return client

    def ready_template(self, built, kind, content, name, ctype, fields, *, options=None,
                       client=None, page_format="auto"):
        """Téléverse, configure, vérifie et active — par l'API, comme l'écran."""
        client = client or self.client_for(built.admin)
        response = client.post(BASE, {"kind": kind, "page_format": page_format,
                                      "file": upload(name, content, ctype)},
                               format="multipart")
        self.assertEqual(response.status_code, 201, response.data)
        pk = response.data["id"]
        self.assertEqual(response.data["status"], "draft")
        patch = {"options": options or {}}
        if fields is not None:  # None : on garde les champs placés aux marqueurs
            patch["fields"] = fields
        response = client.patch(f"{BASE}{pk}/", patch, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        response = client.post(f"{BASE}{pk}/validate/")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertTrue(response.data["report"]["ok"], response.data["report"])
        response = client.post(f"{BASE}{pk}/activate/")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["status"], "active")
        return AcademyDocumentTemplate.objects.get(pk=pk)

    def produce(self, built, kind, *, client=None, student=None, values=None, issue=True):
        client = client or self.client_for(built.admin)
        student = student or built.student
        response = client.post("/api/documents/", {"student": student.pk, "kind": kind,
                                                   "values": values or {}}, format="json")
        if response.status_code != 201 or not issue:
            return response, None
        document_id = response.data["id"]
        response = client.post(f"/api/documents/{document_id}/issue/")
        self.assertEqual(response.status_code, 200, response.data)
        download = client.get(f"/api/documents/{document_id}/download/")
        self.assertEqual(download.status_code, 200)
        return response, b"".join(download.streaming_content)

    def install_four(self):
        self.tpl_a_dip = self.ready_template(
            self.A, "diploma", png_bytes(RED), "diplome.png", "image/png", LANDSCAPE_FIELDS)
        self.tpl_a_cer = self.ready_template(
            self.A, "certificate", png_bytes(GREEN, fmt="JPEG"), "certificat.jpg",
            "image/jpeg", LANDSCAPE_FIELDS)
        self.tpl_b_dip = self.ready_template(
            self.B, "diploma", pdf_bytes(BLUE, marker="FOND-B-DIPLOME"), "diplome.pdf",
            "application/pdf", LANDSCAPE_FIELDS)
        self.tpl_b_cer = self.ready_template(
            self.B, "certificate", pdf_bytes(YELLOW, portrait=True, marker="FOND-B-CERTIF"),
            "certificat.pdf", "application/pdf", PORTRAIT_FIELDS,
            options={"certificate_purpose": "Certificat de scolarité délivré pour servir et valoir"})


class UploadTests(TemplateTestBase):

    def test_televerser_un_diplome_png_valide(self):
        client = self.client_for(self.A.admin)
        response = client.post(BASE, {"kind": "diploma",
                                      "file": upload("Diplôme officiel.png", png_bytes(RED), "image/png")},
                               format="multipart")
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["status"], "draft")
        self.assertEqual(response.data["file_format"], "png")
        self.assertEqual((response.data["page_width_mm"], response.data["page_height_mm"]),
                         (297.0, 210.0))
        self.assertEqual(response.data["original_filename"], "Diplôme officiel.png")
        template = AcademyDocumentTemplate.objects.get(pk=response.data["id"])
        self.assertEqual(template.academy, self.A.school)
        # Jamais « prêt » au seul téléversement.
        summary = client.get(BASE).data["kinds"]["diploma"]
        self.assertEqual(summary["state"], "uploaded")
        self.assertIsNone(summary["active"])

    def test_televerser_un_certificat_pdf_valide(self):
        client = self.client_for(self.A.admin)
        response = client.post(BASE, {"kind": "certificate",
                                      "file": upload("certificat.pdf", pdf_bytes(GREEN, portrait=True),
                                                     "application/pdf")}, format="multipart")
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["kind"], "certificate")
        self.assertEqual(response.data["page_count"], 1)
        self.assertEqual(response.data["orientation"], "portrait")
        self.assertAlmostEqual(response.data["page_width_mm"], 210.0, places=0)

    def assertRefused(self, name, content, ctype, needle):
        client = self.client_for(self.A.admin)
        response = client.post(BASE, {"kind": "diploma", "file": upload(name, content, ctype)},
                               format="multipart")
        self.assertEqual(response.status_code, 400, response.data)
        self.assertIn(needle.lower(), response.data["detail"].lower())
        self.assertFalse(AcademyDocumentTemplate.objects.filter(academy=self.A.school).exists())

    def test_format_non_pris_en_charge(self):
        # Refus EXPLIQUÉ : la cause est dite, pas un message générique.
        self.assertRefused("fond.gif", b"GIF89a" + b"\0" * 2000, "image/gif", "utilisez PNG ou JPEG")
        self.assertRefused("fond.txt", b"bonjour", "text/plain", "non pris en charge")
        self.assertRefused("fond.xlsx", b"PK\x03\x04" + b"\0" * 200, "application/octet-stream",
                           "classeurs Excel")
        self.assertRefused("modele.docm", b"PK\x03\x04" + b"\0" * 200, "application/octet-stream",
                           "macros")

    def test_docx_corrompu_refuse_avec_explication(self):
        # Les DOCX sont désormais ACCEPTÉS et convertis (test_template_conversion.py) ;
        # un faux DOCX reste refusé, avec la raison.
        self.assertRefused("modele.docx", b"PK\x03\x04" + b"\0" * 2000,
                           "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                           "corrompu")

    def test_fichiers_corrompus(self):
        self.assertRefused("fond.pdf", b"%PDF-1.7\n" + b"\x00garbage" * 300, "application/pdf",
                           "PDF")
        broken_png = png_bytes(RED)[:3000]
        self.assertRefused("fond.png", broken_png, "image/png", "illisible")

    def test_fichier_trop_volumineux(self):
        big = b"%PDF-1.4\n" + b"0" * (uploads.MAX_TEMPLATE_BYTES + 10)
        self.assertRefused("fond.pdf", big, "application/pdf", "trop volumineux")

    def test_extension_falsifiee(self):
        self.assertRefused("fond.png", pdf_bytes(RED), "image/png", "ne correspond pas")
        self.assertRefused("fond.pdf", png_bytes(RED), "application/pdf", "ne correspond pas")
        self.assertRefused("fond.jpg", png_bytes(RED), "image/jpeg", "ne correspond pas")

    def test_type_mime_incoherent(self):
        self.assertRefused("fond.png", png_bytes(RED), "application/pdf", "incompatible")

    def test_pdf_actif_refuse(self):
        content = pdf_bytes(RED).replace(b"/Type /Catalog",
                                         b"/Type /Catalog /OpenAction << /S /JavaScript /JS (app.alert(1)) >>")
        self.assertRefused("fond.pdf", content, "application/pdf", "contenu actif")

    def test_pdf_trop_de_pages_et_image_trop_petite(self):
        self.assertRefused("fond.pdf", pdf_bytes(RED, pages=11), "application/pdf", "pages")
        self.assertRefused("fond.png", png_bytes(RED, size=(400, 300)), "image/png", "trop petite")

    def test_jpeg_oriente_par_exif_est_redresse(self):
        client = self.client_for(self.A.admin)
        content = png_bytes(RED, size=(1240, 1754), fmt="JPEG", exif_orientation=6)
        response = client.post(BASE, {"kind": "diploma", "file": upload("photo.jpg", content, "image/jpeg")},
                               format="multipart")
        self.assertEqual(response.status_code, 201, response.data)
        # 1240 × 1754 tourné de 90° : l'image affichée est en paysage.
        self.assertEqual((response.data["image_width_px"], response.data["image_height_px"]),
                         (1754, 1240))
        template = AcademyDocumentTemplate.objects.get(pk=response.data["id"])
        self.assertTrue(template.render_path.endswith(".normalise.png"))
        self.assertEqual(template.source_format, "jpeg")
        self.assertEqual(template.file_format, "png")
        self.assertTrue(os.path.exists(template.render_absolute_path))

    def test_stockage_prive_nom_aleatoire_et_range_par_academie(self):
        from django.conf import settings

        tpl = self.ready_template(self.A, "diploma", png_bytes(RED), "diplome.png",
                                  "image/png", LANDSCAPE_FIELDS)
        self.assertTrue(tpl.absolute_path.startswith(str(settings.PRIVATE_MEDIA_ROOT)))
        self.assertFalse(tpl.absolute_path.startswith(str(settings.MEDIA_ROOT)))
        self.assertIn(os.path.join(str(self.A.school.pk), "diploma"), tpl.file_path)
        self.assertNotIn("diplome", os.path.basename(tpl.file_path))
        self.assertRegex(os.path.basename(tpl.file_path), r"^[0-9a-f]{32}\.png$")
        payload = self.client_for(self.A.admin).get(f"{BASE}{tpl.pk}/").data
        self.assertNotIn(tpl.file_path, str(payload))

    def test_persistance_le_gabarit_est_relu_depuis_la_base_et_le_disque(self):
        tpl = self.ready_template(self.A, "diploma", png_bytes(RED), "diplome.png",
                                  "image/png", LANDSCAPE_FIELDS)
        # Ce que voit un nouveau processus : rien en mémoire, tout relu.
        fresh = AcademyDocumentTemplate.objects.get(pk=tpl.pk)
        content = uploads.render(fresh, uploads._sample_values(fresh))
        text, _ = pdf_text(content)
        self.assertIn("Marie-Éléonore", text)

    def test_le_fond_et_l_original_sont_servis_sans_cache(self):
        tpl = self.ready_template(self.A, "diploma", png_bytes(RED), "diplome.png",
                                  "image/png", LANDSCAPE_FIELDS)
        client = self.client_for(self.A.admin)
        background = client.get(f"{BASE}{tpl.pk}/background/")
        self.assertEqual(background.status_code, 200)
        self.assertEqual(background["Content-Type"], "image/png")
        self.assertIn("no-store", background["Cache-Control"])
        original = client.get(f"{BASE}{tpl.pk}/original/")
        self.assertEqual(original.status_code, 200)
        self.assertEqual(b"".join(original.streaming_content), png_bytes(RED))


class ConfigurationTests(TemplateTestBase):

    def setUp(self):
        self.client_a = self.client_for(self.A.admin)
        response = self.client_a.post(BASE, {"kind": "diploma",
                                             "file": upload("d.png", png_bytes(RED), "image/png")},
                                      format="multipart")
        self.pk = response.data["id"]

    def patch(self, fields, options=None):
        return self.client_a.patch(f"{BASE}{self.pk}/", {"fields": fields, "options": options or {}},
                                   format="json")

    def test_champs_qui_se_chevauchent_refuses(self):
        fields = [dict(LANDSCAPE_FIELDS[0]), dict(LANDSCAPE_FIELDS[1], y_mm=85)]
        response = self.patch(fields)
        self.assertEqual(response.status_code, 400)
        self.assertIn("se chevauchent", response.data["detail"])

    def test_champ_hors_page_refuse(self):
        response = self.patch([dict(LANDSCAPE_FIELDS[0], x_mm=200)])
        self.assertEqual(response.status_code, 400)
        self.assertIn("dépasse de la page", response.data["detail"])

    def test_champ_etranger_au_type_refuse(self):
        response = self.patch([LANDSCAPE_FIELDS[0],
                               {"name": "certificate_purpose", "x_mm": 10, "y_mm": 10,
                                "width_mm": 50, "height_mm": 10}])
        self.assertEqual(response.status_code, 400)
        self.assertIn("n'est pas un champ disponible", response.data["detail"])

    def test_validation_exige_le_nom_de_l_eleve(self):
        self.patch([LANDSCAPE_FIELDS[1]])
        report = self.client_a.post(f"{BASE}{self.pk}/validate/").data["report"]
        self.assertFalse(report["ok"])
        self.assertIn("Le nom de l'élève n'est pas placé sur le gabarit.", report["errors"])
        self.assertEqual(AcademyDocumentTemplate.objects.get(pk=self.pk).status, "invalid")
        response = self.client_a.post(f"{BASE}{self.pk}/activate/")
        self.assertEqual(response.status_code, 409)

    def test_texte_fixe_place_sans_valeur_bloque_la_validation(self):
        self.patch([LANDSCAPE_FIELDS[0],
                    {"name": "signatory_title", "x_mm": 40, "y_mm": 150, "width_mm": 80,
                     "height_mm": 10}])
        report = self.client_a.post(f"{BASE}{self.pk}/validate/").data["report"]
        self.assertFalse(report["ok"])
        self.assertTrue(any("Fonction du signataire" in e for e in report["errors"]))

    def test_modifier_une_version_validee_la_ramene_au_brouillon(self):
        self.patch(LANDSCAPE_FIELDS)
        self.client_a.post(f"{BASE}{self.pk}/validate/")
        self.assertEqual(AcademyDocumentTemplate.objects.get(pk=self.pk).status, "validated")
        self.patch(LANDSCAPE_FIELDS[:2])
        self.assertEqual(AcademyDocumentTemplate.objects.get(pk=self.pk).status, "draft")

    def test_la_version_active_n_est_plus_modifiable(self):
        self.patch(LANDSCAPE_FIELDS)
        self.client_a.post(f"{BASE}{self.pk}/validate/")
        self.client_a.post(f"{BASE}{self.pk}/activate/")
        response = self.patch(LANDSCAPE_FIELDS[:2])
        self.assertEqual(response.status_code, 400)
        self.assertIn("nouvelle version", response.data["detail"])
        duplicate = self.client_a.post(f"{BASE}{self.pk}/duplicate/")
        self.assertEqual(duplicate.status_code, 201, duplicate.data)
        self.assertEqual(duplicate.data["version"], 2)
        self.assertEqual(duplicate.data["status"], "draft")
        self.assertEqual(len(duplicate.data["fields"]), len(LANDSCAPE_FIELDS))

    def test_apercu_de_configuration_filigrane_sans_document(self):
        self.patch(LANDSCAPE_FIELDS)
        before = GeneratedDocument.objects.count()
        response = self.client_a.post(f"{BASE}{self.pk}/preview/", {"frames": True}, format="json")
        self.assertEqual(response.status_code, 200)
        text, _ = pdf_text(response.content)
        self.assertIn("APERÇU", text)
        self.assertIn("Marie-Éléonore", text)
        png = self.client_a.post(f"{BASE}{self.pk}/preview/", {"format": "png"}, format="json")
        self.assertEqual(png["Content-Type"], "image/png")
        self.assertEqual(GeneratedDocument.objects.count(), before)

    def test_page_choisie_d_un_pdf_multipage(self):
        response = self.client_a.post(BASE, {"kind": "certificate",
                                             "file": upload("c.pdf", pdf_bytes(BLUE, pages=3, marker="MULTI"),
                                                            "application/pdf")}, format="multipart")
        pk = response.data["id"]
        self.assertEqual(response.data["page_count"], 3)
        response = self.client_a.patch(f"{BASE}{pk}/", {"fields": [PORTRAIT_FIELDS[0] | {"x_mm": 40, "y_mm": 60}],
                                                        "options": {"page_index": 2}}, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        template = AcademyDocumentTemplate.objects.get(pk=pk)
        content = uploads.render(template, uploads._sample_values(template))
        text, reader = pdf_text(content)
        self.assertEqual(len(reader.pages), 1)  # une seule page dans le document remis
        self.assertIn("MULTI-P3", text)
        self.assertNotIn("MULTI-P1", text)
        response = self.client_a.patch(f"{BASE}{pk}/", {"options": {"page_index": 5}}, format="json")
        self.assertEqual(response.status_code, 400)


class GenerationTests(TemplateTestBase):

    def setUp(self):
        self.install_four()

    def test_les_quatre_combinaisons_utilisent_le_bon_fond(self):
        cases = [
            (self.A, "diploma", RED, 297, 210), (self.A, "certificate", GREEN, 297, 210),
            (self.B, "diploma", BLUE, 297, 210), (self.B, "certificate", YELLOW, 210, 297),
        ]
        for built, kind, color, page_w, page_h in cases:
            with self.subTest(academy=built.tag, kind=kind):
                response, content = self.produce(built, kind)
                self.assertEqual(response.data["status"], "issued")
                self.assertEqual(response.data["academy_code"], built.school.code)
                self.assertEqual(response.data["template_source"], "uploaded")
                text, reader = pdf_text(content)
                self.assertIn(built.student.get_full_name(), text)
                self.assertNotIn("{{", text)
                page = reader.pages[0]
                self.assertAlmostEqual(float(page.mediabox.width) / 72 * 25.4, page_w, delta=0.6)
                self.assertAlmostEqual(float(page.mediabox.height) / 72 * 25.4, page_h, delta=0.6)
                # Zone vide de la page : la couleur du fond de CETTE académie.
                self.assertTrue(close(pixel_at(content, 25, 60, page_w, page_h), color),
                                pixel_at(content, 25, 60, page_w, page_h))
                self.assertIn(response.data["number"], text)
                other = self.B if built is self.A else self.A
                self.assertNotIn(other.school.name, text)
                self.assertNotIn(other.student.get_full_name(), text)

    def test_donnees_reelles_de_l_eleve_et_de_l_academie(self):
        self.A.student.refresh_from_db()
        response, content = self.produce(self.A, "diploma")
        text, _ = pdf_text(content)
        self.assertIn(self.A.student.matricule, text)
        self.assertTrue(self.A.student.matricule)
        self.assertIn(self.A.school.legal_name or self.A.school.name, text)
        self.assertRegex(response.data["number"], r"-DIP-\d{4}-\d{4}$")
        document = GeneratedDocument.objects.get(pk=response.data["id"])
        self.assertEqual(document.academy_template, self.tpl_a_dip)
        self.assertEqual(document.template_version, 1)
        self.assertEqual(document.background_sha256, self.tpl_a_dip.file_sha256)

    def test_certificat_objet_classe_et_annee(self):
        response, content = self.produce(self.B, "certificate")
        text, _ = pdf_text(content)
        self.assertIn("Certificat de scolarité délivré pour servir et valoir", text)
        self.assertIn(self.B.klass.name, text)
        self.assertIn(self.B.year.name, text)
        self.assertRegex(response.data["number"], r"-CER-\d{4}-\d{4}$")

    def test_le_pdf_genere_s_ouvre_dans_deux_moteurs(self):
        import pypdfium2 as pdfium

        _response, content = self.produce(self.B, "diploma")
        document = pdfium.PdfDocument(content)
        self.assertEqual(len(document), 1)
        document.close()
        text, _ = pdf_text(content)
        # Le dessin vectoriel du fond B est conservé, texte compris.
        self.assertIn("FOND-B-DIPLOME-P1", text)

    def test_accents_et_caracteres_francais(self):
        student = self.A.student
        student.first_name, student.last_name = "Zoé-Hélène", "N'Guessan Çaëlle Œuvray"
        student.save()
        _response, content = self.produce(self.A, "diploma")
        text, _ = pdf_text(content)
        self.assertIn("Zoé-Hélène N'Guessan Çaëlle Œuvray", text)

    def test_caractere_hors_police_standard_refuse_clairement(self):
        self.A.student.first_name = "Ağça"
        self.A.student.save()
        tpl = self.tpl_a_dip
        content = uploads.render  # noqa: F841 — la police « sans » ne couvre pas « ğ »
        values = uploads._sample_values(tpl) | {"issue_date": "Ağça"}
        from apps.documents.renderer import RenderError
        with self.assertRaisesMessage(RenderError, "ne sait pas écrire"):
            uploads.render(tpl, values)

    def test_nom_long_sur_deux_lignes_puis_refus_sans_troncature(self):
        student = self.A.student
        student.first_name = "Marie-Éléonore Christabelle Adjoua"
        student.last_name = "Kpossou-Gbénou de la Fontaine-Ahouangonou"
        student.save()
        _response, content = self.produce(self.A, "diploma")
        text, _ = pdf_text(content)
        squeezed = text.replace(" ", "")
        self.assertIn(student.get_full_name().replace(" ", ""), squeezed)

        # Zone étroite et corps minimal élevé : un nom de 200 caractères
        # (le maximum enregistrable) ne peut plus tenir.
        client = self.client_for(self.A.admin)
        dup = client.post(f"{BASE}{self.tpl_a_dip.pk}/duplicate/").data
        narrow = [dict(LANDSCAPE_FIELDS[0], width_mm=90, min_font_size_pt=16)]
        client.patch(f"{BASE}{dup['id']}/", {"fields": narrow}, format="json")
        self.assertTrue(client.post(f"{BASE}{dup['id']}/validate/").data["report"]["ok"])
        client.post(f"{BASE}{dup['id']}/activate/")
        student.first_name = ("Marie-Éléonore " * 7)[:100]
        student.last_name = ("Kpossou-Gbénou " * 7)[:100]
        student.save()
        before = GeneratedDocument.objects.count()
        response, _ = self.produce(self.A, "diploma")
        self.assertEqual(response.status_code, 400)
        self.assertIn("ne tient pas", response.data["detail"])
        self.assertIn("jamais tronqué", response.data["detail"])
        self.assertEqual(GeneratedDocument.objects.count(), before)

    def test_champ_obligatoire_manquant_signale_avant_production(self):
        fields = [dict(f) for f in LANDSCAPE_FIELDS]
        fields[1]["required"] = True  # matricule
        client = self.client_for(self.A.admin)
        dup = client.post(f"{BASE}{self.tpl_a_dip.pk}/duplicate/").data
        client.patch(f"{BASE}{dup['id']}/", {"fields": fields}, format="json")
        client.post(f"{BASE}{dup['id']}/validate/")
        client.post(f"{BASE}{dup['id']}/activate/")
        Student.objects.filter(pk=self.A.student.pk).update(matricule="")
        check = client.post("/api/documents/check/", {"student": self.A.student.pk, "kind": "diploma"},
                            format="json")
        self.assertEqual(check.status_code, 200)
        self.assertFalse(check.data["can_produce"])
        self.assertIn("Matricule", check.data["missing"])
        response, _ = self.produce(self.A, "diploma")
        self.assertEqual(response.status_code, 400)
        self.assertIn("Matricule", response.data["detail"])

    def test_champ_facultatif_vide_est_signale_et_laisse_vide(self):
        client = self.client_for(self.A.admin)
        Student.objects.filter(pk=self.A.student.pk).update(matricule="")
        check = client.post("/api/documents/check/", {"student": self.A.student.pk, "kind": "diploma"},
                            format="json").data
        self.assertTrue(check["can_produce"])
        self.assertTrue(any("Matricule" in w for w in check["warnings"]))

    def test_apercu_par_eleve_ne_cree_rien_et_ne_consomme_aucun_numero(self):
        client = self.client_for(self.A.admin)
        before = (GeneratedDocument.objects.count(), DocumentNumberSequence.objects.count())
        response = client.post("/api/documents/preview/", {"student": self.A.student.pk,
                                                            "kind": "diploma"}, format="json")
        self.assertEqual(response.status_code, 200)
        text, _ = pdf_text(response.content)
        self.assertIn("APERÇU", text)
        self.assertIn(self.A.student.get_full_name(), text)
        self.assertEqual((GeneratedDocument.objects.count(), DocumentNumberSequence.objects.count()),
                         before)

    def test_historique_et_telechargement(self):
        response, content = self.produce(self.A, "certificate")
        client = self.client_for(self.A.admin)
        history = client.get(f"/api/documents/{response.data['id']}/history/").data
        self.assertEqual([e["action"] for e in history][::-1], ["created", "issued"])
        self.assertIn("v1", history[0]["detail"])
        listing = client.get("/api/documents/").data
        self.assertTrue(any(d["id"] == response.data["id"] for d in listing))
        import hashlib
        self.assertEqual(hashlib.sha256(content).hexdigest(), response.data["file_sha256"])

    def test_remplacement_du_gabarit_conserve_les_documents_emis(self):
        import hashlib

        response, before_content = self.produce(self.A, "diploma")
        issued = GeneratedDocument.objects.get(pk=response.data["id"])
        sha_before = issued.file_sha256

        new = self.ready_template(self.A, "diploma", png_bytes(YELLOW), "v2.png", "image/png",
                                  LANDSCAPE_FIELDS)
        self.assertEqual(new.version, 2)
        self.tpl_a_dip.refresh_from_db()
        self.assertEqual(self.tpl_a_dip.status, "archived")

        issued.refresh_from_db()
        self.assertEqual(issued.file_sha256, sha_before)
        client = self.client_for(self.A.admin)
        again = b"".join(client.get(f"/api/documents/{issued.pk}/download/").streaming_content)
        self.assertEqual(hashlib.sha256(again).hexdigest(), sha_before)
        self.assertTrue(close(pixel_at(again, 25, 60, 297, 210), RED))

        _r, after = self.produce(self.A, "diploma")
        self.assertTrue(close(pixel_at(after, 25, 60, 297, 210), YELLOW))
        # Une version qui a servi ne se supprime pas.
        delete = client.delete(f"{BASE}{self.tpl_a_dip.pk}/")
        self.assertEqual(delete.status_code, 409)
        self.assertTrue(AcademyDocumentTemplate.objects.filter(pk=self.tpl_a_dip.pk).exists())

    def test_brouillon_sur_une_version_remplacee_ne_se_delivre_pas(self):
        client = self.client_for(self.A.admin)
        draft = client.post("/api/documents/", {"student": self.A.student.pk, "kind": "diploma"},
                            format="json").data
        self.ready_template(self.A, "diploma", png_bytes(YELLOW), "v2.png", "image/png",
                            LANDSCAPE_FIELDS)
        response = client.post(f"/api/documents/{draft['id']}/issue/")
        self.assertEqual(response.status_code, 409)
        self.assertIn("n'est plus en service", response.data["detail"])

    def test_desactivation_bloque_la_production_sans_toucher_aux_documents(self):
        response, _ = self.produce(self.A, "certificate")
        client = self.client_for(self.A.admin)
        self.assertEqual(client.post(f"{BASE}{self.tpl_a_cer.pk}/disable/").status_code, 200)
        summary = client.get(BASE).data["kinds"]["certificate"]
        self.assertEqual(summary["state"], "disabled")
        refused, _ = self.produce(self.A, "certificate")
        self.assertEqual(refused.status_code, 400)
        self.assertIn("Aucun gabarit de certificat actif", refused.data["detail"])
        document = GeneratedDocument.objects.get(pk=response.data["id"])
        self.assertEqual(document.status, "issued")
        self.assertTrue(os.path.exists(document.absolute_path))
        self.assertEqual(client.post(f"{BASE}{self.tpl_a_cer.pk}/reactivate/").status_code, 200)
        ok, _ = self.produce(self.A, "certificate")
        self.assertEqual(ok.data["status"], "issued")

    def test_suppression_de_la_version_active_exige_confirmation(self):
        client = self.client_for(self.B.admin)
        response = client.delete(f"{BASE}{self.tpl_b_dip.pk}/")
        self.assertEqual(response.status_code, 409)
        self.assertIn("Confirmez", response.data["detail"])
        path = self.tpl_b_dip.absolute_path
        response = client.delete(f"{BASE}{self.tpl_b_dip.pk}/?confirm=1")
        self.assertEqual(response.status_code, 204)
        self.assertFalse(os.path.exists(path))
        # Élèves, inscriptions et notes intacts.
        self.assertTrue(Student.objects.filter(pk=self.B.student.pk).exists())
        self.assertTrue(StudentEnrollment.objects.filter(student=self.B.student).exists())
        self.assertTrue(self.B.student.grades.exists())

    def test_fichier_disparu_du_stockage_erreur_claire_sans_document(self):
        os.remove(self.tpl_a_dip.absolute_path)
        before = GeneratedDocument.objects.count()
        response, _ = self.produce(self.A, "diploma")
        self.assertEqual(response.status_code, 400)
        self.assertIn("absent du stockage", response.data["detail"])
        self.assertEqual(GeneratedDocument.objects.count(), before)

    def test_numeros_uniques_sur_une_serie(self):
        numbers = set()
        for _ in range(5):
            response, _ = self.produce(self.A, "diploma")
            numbers.add(response.data["number"])
        self.assertEqual(len(numbers), 5)

    def test_deux_versions_actives_impossibles_en_base(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            AcademyDocumentTemplate.objects.filter(pk=self.tpl_a_dip.pk).update(version=99)
            copy = AcademyDocumentTemplate.objects.get(pk=self.tpl_a_dip.pk)
            copy.pk = None
            copy.version = 100
            copy.save()


class EligibilityTests(TemplateTestBase):

    def test_diplome_sur_moyenne_annuelle(self):
        # A : (16×2 + 12) / 3 = 14,67/20 ; B : (8×2 + 6) / 3 = 7,33/20.
        options = {"eligibility": {"rule": "annual_average", "min_average": 10}}
        fields = LANDSCAPE_FIELDS + [
            {"name": "result_mention", "x_mm": 40, "y_mm": 125, "width_mm": 120, "height_mm": 10},
            {"name": "annual_average", "x_mm": 170, "y_mm": 125, "width_mm": 80, "height_mm": 10},
        ]
        self.ready_template(self.A, "diploma", png_bytes(RED), "d.png", "image/png", fields,
                            options=options)
        self.ready_template(self.B, "diploma", pdf_bytes(BLUE), "d.pdf", "application/pdf", fields,
                            options=options)
        response, content = self.produce(self.A, "diploma")
        self.assertEqual(response.data["status"], "issued")
        text, _ = pdf_text(content)
        self.assertIn("14.67/20", text)
        from apps.grades.appreciations import appreciation_for
        self.assertIn(appreciation_for(14.67, 20, academy=self.A.school), text)

        before = GeneratedDocument.objects.count()
        refused, _ = self.produce(self.B, "diploma")
        self.assertEqual(refused.status_code, 400)
        self.assertIn("inférieure au seuil", refused.data["detail"])
        self.assertEqual(GeneratedDocument.objects.count(), before)
        # Les notes ne sont pas touchées pour rendre la délivrance possible.
        self.assertEqual(sorted(float(g.value) for g in self.B.student.grades.all()), [6.0, 8.0])

    def test_diplome_sans_note_refuse(self):
        self.A.student.grades.all().delete()
        self.ready_template(self.A, "diploma", png_bytes(RED), "d.png", "image/png",
                            LANDSCAPE_FIELDS,
                            options={"eligibility": {"rule": "annual_average", "min_average": 10}})
        response, _ = self.produce(self.A, "diploma")
        self.assertEqual(response.status_code, 400)
        self.assertIn("Aucune note enregistrée", response.data["detail"])

    def test_certificat_d_inscription_refuse_a_un_eleve_sorti(self):
        self.ready_template(self.A, "certificate", png_bytes(GREEN), "c.png", "image/png",
                            LANDSCAPE_FIELDS)  # règle par défaut : élève inscrit
        Student.objects.filter(pk=self.A.student.pk).update(is_active=False)
        response, _ = self.produce(self.A, "certificate")
        self.assertEqual(response.status_code, 400)
        self.assertIn("n'est plus inscrit", response.data["detail"])

    def test_decision_administrative_par_defaut_pour_un_diplome(self):
        tpl = self.ready_template(self.A, "diploma", png_bytes(RED), "d.png", "image/png",
                                  LANDSCAPE_FIELDS)
        self.assertEqual(tpl.options["eligibility"], {"rule": "admin_decision"})

    def test_regle_reverifiee_a_la_delivrance(self):
        self.ready_template(self.A, "certificate", png_bytes(GREEN), "c.png", "image/png",
                            LANDSCAPE_FIELDS)
        client = self.client_for(self.A.admin)
        draft = client.post("/api/documents/", {"student": self.A.student.pk, "kind": "certificate"},
                            format="json").data
        Student.objects.filter(pk=self.A.student.pk).update(is_active=False)
        response = client.post(f"/api/documents/{draft['id']}/issue/")
        self.assertEqual(response.status_code, 409)
        self.assertIn("n'est plus inscrit", response.data["detail"])

    def test_date_d_obtention_saisie_jamais_inventee(self):
        fields = LANDSCAPE_FIELDS + [{"name": "award_date", "x_mm": 40, "y_mm": 165,
                                      "width_mm": 60, "height_mm": 9, "required": True}]
        self.ready_template(self.A, "diploma", png_bytes(RED), "d.png", "image/png", fields)
        refused, _ = self.produce(self.A, "diploma")
        self.assertEqual(refused.status_code, 400)
        self.assertIn("Date d'obtention", refused.data["detail"])
        response, content = self.produce(self.A, "diploma", values={"award_date": "2027-06-30"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("30/06/2027", pdf_text(content)[0])


class BatchTests(TemplateTestBase):

    def test_lot_par_classe_chaque_eleve_sur_son_gabarit(self):
        self.install_four()
        second = Student.objects.create(school=self.A.school, first_name="Second", last_name="Lot",
                                        current_class=self.A.klass, school_year=self.A.year)
        StudentEnrollment.objects.create(student=second, school_year=self.A.year, class_obj=self.A.klass)
        left = Student.objects.create(school=self.A.school, first_name="Sorti", last_name="Lot",
                                      current_class=self.A.klass, school_year=self.A.year,
                                      is_active=False)
        StudentEnrollment.objects.create(student=left, school_year=self.A.year, class_obj=self.A.klass)
        client = self.client_for(self.A.admin)
        response = client.post("/api/documents/batch/", {"kind": "certificate",
                                                          "class_id": self.A.klass.pk}, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual((response.data["created"], response.data["refused"]), (2, 1))
        refused = [r for r in response.data["results"] if not r["ok"]][0]
        self.assertEqual(refused["student"], "Sorti Lot")
        ids = [r["document"]["id"] for r in response.data["results"] if r["ok"]]
        issued = client.post("/api/documents/batch-issue/", {"ids": ids}, format="json")
        self.assertEqual(issued.data["issued"], 2)
        for document in GeneratedDocument.objects.filter(pk__in=ids):
            self.assertEqual(document.academy_template, self.tpl_a_cer)
            with open(document.absolute_path, "rb") as handle:
                self.assertTrue(close(pixel_at(handle.read(), 25, 60, 297, 210), GREEN))

    def test_lot_sur_la_classe_d_une_autre_academie_introuvable(self):
        self.install_four()
        client = self.client_for(self.A.admin)
        response = client.post("/api/documents/batch/", {"kind": "diploma",
                                                          "class_id": self.B.klass.pk}, format="json")
        self.assertEqual(response.status_code, 404)
        issue = client.post("/api/documents/batch-issue/", {"ids": [999999]}, format="json")
        self.assertEqual(issue.data["issued"], 0)


class PermissionAndIsolationTests(TemplateTestBase):

    def setUp(self):
        self.install_four()

    def test_roles_non_administratifs_refuses(self):
        for user in (self.A.teacher_user, self.A.parent_user, self.A.student_user):
            client = self.client_for(user)
            with self.subTest(role=user.role):
                self.assertEqual(client.get(BASE).status_code, 403)
                self.assertEqual(client.post(BASE, {"kind": "diploma",
                                                    "file": upload("d.png", png_bytes(RED), "image/png")},
                                             format="multipart").status_code, 403)
                self.assertEqual(client.get(f"{BASE}{self.tpl_a_dip.pk}/background/").status_code, 403)
                self.assertEqual(client.post("/api/documents/", {"student": self.A.student.pk,
                                                                  "kind": "diploma"},
                                             format="json").status_code, 403)
                self.assertEqual(client.post("/api/documents/preview/", {"student": self.A.student.pk,
                                                                          "kind": "diploma"},
                                             format="json").status_code, 403)

    def test_acces_croise_par_identifiant_manipule(self):
        client = self.client_for(self.A.admin)
        foreign = [self.tpl_b_dip, self.tpl_b_cer]
        for tpl in foreign:
            with self.subTest(template=tpl.pk):
                for method, url in (("get", f"{BASE}{tpl.pk}/"), ("get", f"{BASE}{tpl.pk}/background/"),
                                    ("get", f"{BASE}{tpl.pk}/original/"),
                                    ("post", f"{BASE}{tpl.pk}/preview/"),
                                    ("post", f"{BASE}{tpl.pk}/validate/"),
                                    ("post", f"{BASE}{tpl.pk}/disable/"),
                                    ("post", f"{BASE}{tpl.pk}/duplicate/"),
                                    ("patch", f"{BASE}{tpl.pk}/"), ("delete", f"{BASE}{tpl.pk}/?confirm=1")):
                    response = getattr(client, method)(url, {}, format="json")
                    self.assertEqual(response.status_code, 404, (method, url))
                tpl.refresh_from_db()
                self.assertEqual(tpl.status, "active")
                self.assertTrue(os.path.exists(tpl.absolute_path))
        # Ni l'élève ni la classe de B ne sont atteignables depuis A.
        for url in ("/api/documents/", "/api/documents/check/", "/api/documents/preview/"):
            response = client.post(url, {"student": self.B.student.pk, "kind": "diploma"}, format="json")
            self.assertEqual(response.status_code, 404, url)
        # Aperçu d'un gabarit de A avec l'élève de B : refusé.
        response = client.post(f"{BASE}{self.tpl_a_dip.pk}/preview/", {"student": self.B.student.pk},
                               format="json")
        self.assertEqual(response.status_code, 404)
        # Le corps de la requête ne déplace pas un téléversement vers B.
        response = client.post(BASE, {"kind": "diploma", "academy": self.B.school.pk,
                                      "school": self.B.school.pk,
                                      "file": upload("d.png", png_bytes(RED), "image/png")},
                               format="multipart")
        self.assertEqual(AcademyDocumentTemplate.objects.get(pk=response.data["id"]).academy,
                         self.A.school)
        response = client.get(BASE + f"?school_id={self.B.school.pk}")
        self.assertEqual(response.data["academy"]["code"], self.A.school.code)

    def test_document_d_une_autre_academie_introuvable(self):
        response, _ = self.produce(self.B, "diploma")
        client = self.client_for(self.A.admin)
        for suffix in ("download/", "history/", "issue/"):
            method = client.get if suffix != "issue/" else client.post
            self.assertEqual(method(f"/api/documents/{response.data['id']}/{suffix}").status_code, 404)

    def test_le_service_refuse_un_gabarit_d_une_autre_academie(self):
        from django.core.exceptions import ValidationError

        from apps.documents.services import create_from_academy_template
        with self.assertRaisesMessage(ValidationError, "frontière"):
            create_from_academy_template(template=self.tpl_b_dip, student=self.A.student)

    def test_super_administrateur_suit_l_academie_selectionnee(self):
        none = self.client_for(self.superadmin, None)
        self.assertEqual(none.get(BASE).status_code, 400)
        on_a = self.client_for(self.superadmin, self.A.school)
        self.assertEqual(on_a.get(BASE).data["kinds"]["diploma"]["active"]["id"], self.tpl_a_dip.pk)
        self.assertEqual(on_a.get(f"{BASE}{self.tpl_b_dip.pk}/").status_code, 404)
        on_b = self.client_for(self.superadmin, self.B.school)
        self.assertEqual(on_b.get(BASE).data["kinds"]["diploma"]["active"]["id"], self.tpl_b_dip.pk)
        self.assertEqual(on_b.get(f"{BASE}{self.tpl_a_dip.pk}/").status_code, 404)
        # En mode consolidé, l'élève détermine l'académie et donc le fond.
        response, content = self.produce(self.B, "certificate", client=none)
        self.assertEqual(response.data["academy_code"], self.B.school.code)
        self.assertTrue(close(pixel_at(content, 25, 60, 210, 297), YELLOW))

    def test_meme_nom_de_fichier_dans_deux_academies(self):
        client_a, client_b = self.client_for(self.A.admin), self.client_for(self.B.admin)
        a = client_a.post(BASE, {"kind": "diploma", "file": upload("officiel.png", png_bytes(RED), "image/png")},
                          format="multipart").data
        b = client_b.post(BASE, {"kind": "diploma", "file": upload("officiel.png", png_bytes(BLUE), "image/png")},
                          format="multipart").data
        ta = AcademyDocumentTemplate.objects.get(pk=a["id"])
        tb = AcademyDocumentTemplate.objects.get(pk=b["id"])
        self.assertNotEqual(ta.absolute_path, tb.absolute_path)
        self.assertNotEqual(ta.file_sha256, tb.file_sha256)


class ManyAcademiesIsolationTests(TemplateTestBase):
    """Cinq académies, cinq fonds de couleurs distinctes, accès croisés."""

    def test_cinq_academies(self):
        palette = [(200, 30, 30), (30, 160, 60), (30, 60, 200), (230, 200, 20), (150, 40, 160)]
        built = [self.A, self.B] + [build_academy(f"TPL{i}", t) for i, t in
                                    zip("CDE", ("physical_primary", "physical_secondary", "online"))]
        templates = []
        for academy, color in zip(built, palette):
            templates.append(self.ready_template(academy, "diploma", png_bytes(color), "officiel.png",
                                                 "image/png", LANDSCAPE_FIELDS))
        for academy, color in zip(built, palette):
            response, content = self.produce(academy, "diploma")
            self.assertEqual(response.data["status"], "issued")
            self.assertTrue(close(pixel_at(content, 25, 60, 297, 210), color))
            text, _ = pdf_text(content)
            for other in built:
                if other is not academy:
                    self.assertNotIn(other.student.get_full_name(), text)
            client = self.client_for(academy.admin)
            for tpl in templates:
                expected = 200 if tpl.academy_id == academy.school.pk else 404
                self.assertEqual(client.get(f"{BASE}{tpl.pk}/").status_code, expected)


class ResolutionTests(TestCase):
    """Le gabarit téléversé actif prime sur le gabarit intégré — et lui seul."""

    def test_feba_garde_son_gabarit_integre_tant_qu_aucun_televerse_n_est_actif(self):
        feba, _ = School.objects.update_or_create(
            code=School.CODE_FEBA, defaults={"name": "FEBA", "address": "Cotonou"})
        source, template = uploads.resolve_template(feba, "diploma")
        self.assertEqual(source, "builtin")
        self.assertEqual(template.id, "diploma_feba")
        other = School.objects.create(name="Autre", code="AUTRE_TPL", address="x")
        self.assertEqual(uploads.resolve_template(other, "diploma"), (None, None))

    def test_la_cle_de_numerotation_est_celle_du_gabarit_integre(self):
        feba, _ = School.objects.update_or_create(
            code=School.CODE_FEBA_FHA, defaults={"name": "FHA", "address": "En ligne"})
        template = AcademyDocumentTemplate(academy=feba, kind="certificate")
        self.assertEqual(template.sequence_key, "certificate_feba_fha")


class EmptyAcademyDeletionTests(TemplateTestBase):

    def test_supprimer_une_academie_vide_supprime_aussi_les_fichiers_de_ses_gabarits(self):
        from apps.schools.academy_setup import create_academy

        empty = create_academy({"name": "Académie vide", "code": "AC_VIDE_TPL",
                                "academy_type": "online", "address": "x", "city": "Lomé",
                                "country": "Togo", "timezone": "Africa/Lome"},
                               created_by=self.superadmin)
        client = self.client_for(self.superadmin, empty)
        response = client.post(BASE, {"kind": "diploma",
                                      "file": upload("d.png", png_bytes(RED), "image/png")},
                               format="multipart")
        self.assertEqual(response.status_code, 201, response.data)
        path = AcademyDocumentTemplate.objects.get(pk=response.data["id"]).absolute_path
        self.assertTrue(os.path.exists(path))
        self.client_for(self.superadmin, self.A.school)  # quitte l'académie à supprimer
        deleted = client.delete(f"/api/schools/schools/{empty.pk}/")
        self.assertEqual(deleted.status_code, 204, getattr(deleted, "data", None))
        self.assertFalse(AcademyDocumentTemplate.objects.filter(academy_id=empty.pk).exists())
        self.assertFalse(os.path.exists(path))


@override_settings(PRIVATE_MEDIA_ROOT=tempfile.mkdtemp(prefix="feba-tpl-conc-"))
class ConcurrencyTests(__import__("django.test", fromlist=["TransactionTestCase"]).TransactionTestCase):
    """
    Demandes SIMULTANÉES (PostgreSQL : verrous réels, connexions distinctes).
    Délivrances : numéros tous distincts. Activations : une seule version
    active. Téléversements : numéros de version distincts.
    """

    def setUp(self):
        from django.db import connection
        if connection.vendor != "postgresql":
            self.skipTest("Concurrence réelle : PostgreSQL requis.")
        self.A = build_academy("CONC", "physical_secondary")
        self.students = [self.A.student] + [
            Student.objects.create(school=self.A.school, first_name=f"Eleve{i}", last_name="Conc",
                                   current_class=self.A.klass, school_year=self.A.year)
            for i in range(5)]
        for s in self.students[1:]:
            StudentEnrollment.objects.create(student=s, school_year=self.A.year, class_obj=self.A.klass)

    def ready(self, color):
        tpl = uploads.create_version(academy=self.A.school, kind="diploma",
                                     uploaded_file=upload("d.png", png_bytes(color), "image/png"))
        uploads.save_configuration(tpl, fields=LANDSCAPE_FIELDS)
        self.assertTrue(uploads.validate(tpl)["ok"])
        return tpl

    def run_threads(self, targets):
        import threading
        from django.db import connection

        results = []

        def wrap(fn):
            try:
                results.append(("ok", fn()))
            except Exception as exc:  # noqa: BLE001 — le résultat est inspecté
                import traceback
                results.append(("error", repr(exc) + "\n" + traceback.format_exc()[-1500:]))
            finally:
                connection.close()

        threads = [threading.Thread(target=wrap, args=(fn,)) for fn in targets]
        [t.start() for t in threads]
        [t.join() for t in threads]
        return results

    def test_delivrances_simultanees_numeros_distincts(self):
        from apps.documents.services import create_for_kind, issue_document

        uploads.activate(self.ready(RED))
        drafts = [create_for_kind(kind="diploma", student=s) for s in self.students]

        def issuer(pk):
            return lambda: issue_document(GeneratedDocument.objects.get(pk=pk)).number

        results = self.run_threads([issuer(d.pk) for d in drafts])
        numbers = [value for status, value in results if status == "ok"]
        self.assertEqual(len(numbers), len(drafts), results)
        self.assertEqual(len(set(numbers)), len(drafts), numbers)

    def test_activations_simultanees_une_seule_active(self):
        first, second = self.ready(RED), self.ready(BLUE)
        self.run_threads([lambda: uploads.activate(first), lambda: uploads.activate(second)])
        self.assertEqual(AcademyDocumentTemplate.objects.filter(
            academy=self.A.school, kind="diploma", status="active").count(), 1)

    def test_televersements_simultanes_versions_distinctes(self):
        results = self.run_threads([
            (lambda c=c: uploads.create_version(
                academy=self.A.school, kind="certificate",
                uploaded_file=upload("c.png", png_bytes(c), "image/png")).version)
            for c in (RED, GREEN, BLUE)])
        versions = sorted(v for status, v in results if status == "ok")
        self.assertEqual(versions, [1, 2, 3], results)


class ConcurrentRenderingTests(TestCase):
    """
    Rendus simultanés dans un même processus. ReportLab partage l'objet
    d'une police TrueType entre documents et son découpage n'est pas sûr
    entre fils : sans le verrou du moteur, des rendus échouaient
    (IndexError dans ttfonts.makeSubset — trouvé par la campagne lancée
    depuis l'archive, puis reproduit à 12 fils).
    """

    def test_douze_fils_quinze_tours_aucun_echec(self):
        import threading

        from PIL import Image

        root = tempfile.mkdtemp(prefix="feba-render-")
        try:
            with override_settings(PRIVATE_MEDIA_ROOT=root):
                os.makedirs(os.path.join(root, "academy_templates", "1"))
                Image.new("RGB", (1754, 1240), RED).save(
                    os.path.join(root, "academy_templates", "1", "fond.png"))
                template = AcademyDocumentTemplate(
                    kind="diploma", file_format="png", file_path="1/fond.png", render_path="",
                    page_width_mm=297, page_height_mm=210, image_width_px=1754,
                    image_height_px=1240, options={})
                template.fields = uploads.normalize_fields(template, LANDSCAPE_FIELDS)
                errors = []

                def run(index):
                    try:
                        values = uploads._sample_values(template)
                        values["student_name"] = f"Élève {index} Ñandú Œuvray-Çaëlle"
                        content = uploads.render(template, values)
                        if f"Élève {index}" not in pdf_text(content)[0]:
                            errors.append(f"texte absent ({index})")
                    except Exception as exc:  # noqa: BLE001 — l'échec est compté
                        errors.append(repr(exc))

                for _round in range(15):
                    threads = [threading.Thread(target=run, args=(i,)) for i in range(12)]
                    [t.start() for t in threads]
                    [t.join() for t in threads]
                self.assertEqual(errors, [])
        finally:
            shutil.rmtree(root, ignore_errors=True)
