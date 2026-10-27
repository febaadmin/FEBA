"""
Gabarits multiformats : conversion AUTOMATIQUE par FEBA, de bout en bout.

Chaque test téléverse le fichier D'ORIGINE (DOCX, DOC, ODT, RTF, PPTX, PPT,
ODP, TIFF, WEBP) par l'API, exactement comme l'écran : aucun PDF n'est
préparé à l'avance. FEBA détecte le format, convertit, repère les
marqueurs, vérifie, active, puis produit et délivre un document dont le
PDF est ROUVERT : texte, dimensions, orientation, couleur du fond relevée
par PDFium, image du logo, tableau, absence de marqueur.

LibreOffice est fourni par l'image Docker (backend/Dockerfile.*). Sur un
poste qui ne l'a pas, ces tests sont IGNORÉS avec ce motif — la campagne de
référence les exécute dans le conteneur (voir TEST_REPORT.md).
"""
import io
import os
import tempfile
import unittest
import zipfile

from django.test import TransactionTestCase, override_settings

from apps.documents import conversion
from apps.documents.models import AcademyDocumentTemplate, GeneratedDocument
from apps.students.models import Student, StudentEnrollment
from tests.academy_fixtures import build_academy
from tests.test_academy_document_templates import (
    BASE, BLUE, GREEN, LANDSCAPE_FIELDS, PORTRAIT_FIELDS, RED, YELLOW, TemplateTestBase,
    close, pdf_bytes, pdf_text, pixel_at, png_bytes, upload,
)

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures", "office_templates")
NAVY, PURPLE, GOLD = (30, 58, 110), (106, 27, 154), (176, 138, 46)
OFFICE = unittest.skipUnless(
    conversion.office_available(),
    "LibreOffice absent de cet environnement : test exécuté dans l'image Docker de FEBA.")


#: Zones LIBRES du certificat Word portrait (mesurées sur son rendu) : sous
#: « … certifie que l'élève : », après « … en classe de : », en bas de page.
CERT_DOCX_FIELDS = [
    {"name": "student_name", "x_mm": 30, "y_mm": 78, "width_mm": 150, "height_mm": 12,
     "font": "serif", "font_size_pt": 20, "max_lines": 2, "required": True},
    {"name": "class_name", "x_mm": 100, "y_mm": 94, "width_mm": 90, "height_mm": 8},
    {"name": "document_number", "x_mm": 110, "y_mm": 262, "width_mm": 80, "height_mm": 9},
]


def fixture(name):
    with open(os.path.join(FIXTURES, name), "rb") as handle:
        return handle.read()


def has_image(content):
    """Le PDF final contient-il une image (le logo du gabarit) ?"""
    from pypdf import PdfReader

    found, seen = [], set()

    def walk(resources):
        xobjects = (resources or {}).get("/XObject") or {}
        for _name, ref in xobjects.items():
            key = getattr(ref, "idnum", None) or id(ref)
            if key in seen:  # ressources partagées ou cycliques
                continue
            seen.add(key)
            obj = ref.get_object()
            if obj.get("/Subtype") == "/Image":
                found.append(obj)
            elif obj.get("/Subtype") == "/Form":
                walk(obj.get("/Resources"))
    walk(PdfReader(io.BytesIO(content)).pages[0].get("/Resources"))
    return bool(found)


def conversion_dirs():
    return {n for n in os.listdir(tempfile.gettempdir()) if n.startswith("feba-conversion-")}


@OFFICE
class OfficeFormatTests(TemplateTestBase):
    """Un format par test : téléversement direct → document délivré relu."""

    def office_flow(self, filename, *, kind="diploma", band=None, band_at=(148, 22),
                    expect_markers=(), page=(297, 210), fields=None, options=None):
        client = self.client_for(self.A.admin)
        response = client.post(BASE, {"kind": kind, "file": upload(
            filename, fixture(filename), "application/octet-stream")}, format="multipart")
        self.assertEqual(response.status_code, 201, response.data)
        data = response.data
        self.assertEqual(data["source_format"], os.path.splitext(filename)[1].lstrip("."))
        self.assertEqual(data["normalized_format"], "pdf")
        self.assertTrue(data["converted"])
        self.assertEqual(data["conversion"]["engine"], "libreoffice")
        self.assertAlmostEqual(data["page_width_mm"], page[0], delta=1)
        self.assertAlmostEqual(data["page_height_mm"], page[1], delta=1)
        placed = {f["name"] for f in data["fields"]}
        self.assertTrue(set(expect_markers) <= placed, (expect_markers, placed))
        background = client.get(f"{BASE}{data['id']}/background/")
        self.assertEqual(background.status_code, 200)
        self.assertEqual(background["Content-Type"], "image/png")
        if fields is not None or options:
            patch = client.patch(f"{BASE}{data['id']}/", {
                **({"fields": fields} if fields is not None else {}),
                **({"options": options} if options else {})}, format="json")
            self.assertEqual(patch.status_code, 200, patch.data)
        report = client.post(f"{BASE}{data['id']}/validate/").data["report"]
        self.assertTrue(report["ok"], report)
        self.assertEqual(client.post(f"{BASE}{data['id']}/activate/").status_code, 200)

        response, content = self.produce(self.A, kind)
        self.assertEqual(response.data["status"], "issued", getattr(response, "data", None))
        text, reader = pdf_text(content)
        self.assertIn(self.A.student.get_full_name(), text)
        if "document_number" in {f["name"] for f in AcademyDocumentTemplate.objects.get(
                pk=data["id"]).fields}:
            self.assertIn(response.data["number"], text)
        self.assertNotIn("{{", text)
        self.assertNotIn("}}", text)
        self.assertEqual(len(reader.pages), 1)
        box = reader.pages[0].mediabox
        self.assertAlmostEqual(float(box.width) / 72 * 25.4, page[0], delta=1)
        self.assertAlmostEqual(float(box.height) / 72 * 25.4, page[1], delta=1)
        if band:
            colour = pixel_at(content, band_at[0], band_at[1], page[0], page[1])
            self.assertTrue(close(colour, band, 45), (filename, colour))
        template = AcademyDocumentTemplate.objects.get(pk=data["id"])
        self.assertTrue(os.path.exists(template.absolute_path))        # original conservé
        self.assertTrue(os.path.exists(template.render_absolute_path))  # fond normalisé
        with open(template.absolute_path, "rb") as handle:
            self.assertEqual(handle.read(), fixture(filename))          # original intact
        return template, text, content

    DIPLOMA_MARKERS = ("student_name", "school_year", "academy_name", "issue_date", "document_number")

    def test_docx_diplome_paysage_avec_marqueurs(self):
        template, text, content = self.office_flow(
            "diplome_paysage_marqueurs.docx", band=NAVY, expect_markers=self.DIPLOMA_MARKERS)
        self.assertEqual(template.options["markers"]["auto_fields"], 5)
        self.assertIn("DIPLÔME DE FIN D'ÉTUDES", text)          # fond conservé
        self.assertIn("Sceau de l'établissement", text)         # tableau conservé
        self.assertIn(self.A.year.name, text)
        self.assertIn(self.A.school.legal_name or self.A.school.name, text)
        self.assertTrue(has_image(content))                     # logo conservé
        # Bordure de page dorée : relevée le long d'une ligne horizontale
        # dans la marge gauche (double filet, donc pas un pixel au hasard).
        self.assertTrue(any(close(pixel_at(content, x / 2, 105, 297, 210), GOLD, 60)
                            for x in range(6, 36)))

    def test_doc_word_97(self):
        _t, text, content = self.office_flow(
            "diplome_paysage_marqueurs.doc", band=NAVY, expect_markers=self.DIPLOMA_MARKERS)
        self.assertIn("DIPLÔME DE FIN D'ÉTUDES", text)
        self.assertTrue(has_image(content))

    def test_odt(self):
        _t, text, content = self.office_flow(
            "diplome_paysage_marqueurs.odt", band=NAVY, expect_markers=self.DIPLOMA_MARKERS)
        self.assertIn("Sceau de l'établissement", text)
        self.assertTrue(has_image(content))

    def test_rtf(self):
        _t, text, content = self.office_flow(
            "diplome_paysage_marqueurs.rtf", band=NAVY, band_at=(148, 25),
            expect_markers=self.DIPLOMA_MARKERS)
        self.assertIn("DIPLÔME DE FIN D'ÉTUDES", text)
        self.assertTrue(has_image(content))

    PRESENTATION_MARKERS = ("student_name", "academy_name", "school_year", "issue_date")

    def test_pptx(self):
        _t, text, content = self.office_flow(
            "diplome_diapo_marqueurs.pptx", band=PURPLE, band_at=(148, 20),
            expect_markers=self.PRESENTATION_MARKERS)
        self.assertIn("DIPLÔME D'HONNEUR", text)
        self.assertTrue(has_image(content))

    def test_ppt(self):
        _t, text, _c = self.office_flow(
            "diplome_diapo_marqueurs.ppt", band=PURPLE, band_at=(148, 20),
            expect_markers=self.PRESENTATION_MARKERS)
        self.assertIn("DIPLÔME D'HONNEUR", text)

    def test_odp(self):
        _t, text, _c = self.office_flow(
            "diplome_diapo_marqueurs.odp", band=PURPLE, band_at=(148, 20),
            expect_markers=self.PRESENTATION_MARKERS)
        self.assertIn("DIPLÔME D'HONNEUR", text)

    def test_certificat_portrait_sans_marqueur_champs_places_dans_l_editeur(self):
        fields = CERT_DOCX_FIELDS
        template, text, content = self.office_flow(
            "certificat_portrait.docx", kind="certificate", page=(210, 297), fields=fields)
        self.assertEqual(template.fields[0]["name"], "student_name")
        self.assertIsNone(template.options.get("markers"))
        self.assertIn("CERTIFICAT DE SCOLARITÉ", text)
        self.assertIn(self.A.klass.name, text)
        self.assertTrue(has_image(content))

    def test_document_de_deux_pages_la_page_des_marqueurs_est_retenue(self):
        template, text, _c = self.office_flow(
            "deux_pages_marqueurs_page2.docx", kind="certificate", page=(210, 297),
            expect_markers=("student_name", "class_name"))
        self.assertEqual((template.page_count, template.page_index), (2, 1))
        self.assertIn("ATTESTATION", text)
        self.assertNotIn("NOTICE", text)
        # La page reste modifiable dans l'éditeur, page 1 comprise.
        client = self.client_for(self.A.admin)
        dup = client.post(f"{BASE}{template.pk}/duplicate/").data
        response = client.patch(f"{BASE}{dup['id']}/", {"fields": [], "options": {"page_index": 0}},
                                format="json")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["page_index"], 0)

    def test_zone_qui_recouvre_le_texte_du_fond_refusee(self):
        client = self.client_for(self.A.admin)
        data = client.post(BASE, {"kind": "certificate", "file": upload(
            "c.docx", fixture("certificat_portrait.docx"), "")}, format="multipart").data
        over_title = [dict(CERT_DOCX_FIELDS[0], y_mm=45)]  # sur « CERTIFICAT DE SCOLARITÉ »
        client.patch(f"{BASE}{data['id']}/", {"fields": over_title}, format="json")
        report = client.post(f"{BASE}{data['id']}/validate/").data["report"]
        self.assertFalse(report["ok"])
        self.assertTrue(any("recouvre du texte du fond" in e and "CERTIFICAT" in e
                            for e in report["errors"]), report["errors"])
        client.patch(f"{BASE}{data['id']}/", {"fields": CERT_DOCX_FIELDS}, format="json")
        self.assertTrue(client.post(f"{BASE}{data['id']}/validate/").data["report"]["ok"])

    def test_nom_de_fichier_complexe(self):
        client = self.client_for(self.A.admin)
        name = "Diplôme d’État – Promo 2026 (version finale) #2 «A».docx"
        response = client.post(BASE, {"kind": "diploma", "file": upload(
            name, fixture("diplome_paysage_marqueurs.docx"), "")}, format="multipart")
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["original_filename"], "Diplôme d’État – Promo 2026 (version finale) #2 «A».docx")
        template = AcademyDocumentTemplate.objects.get(pk=response.data["id"])
        self.assertRegex(os.path.basename(template.file_path), r"^[0-9a-f]{32}\.docx$")
        original = client.get(f"{BASE}{template.pk}/original/")
        self.assertEqual(original["Content-Type"],
                         "application/vnd.openxmlformats-officedocument.wordprocessingml.document")

    def test_marqueur_inconnu_bloque_la_verification(self):
        import zipfile as zf

        source = fixture("diplome_paysage_marqueurs.docx")
        zin = zf.ZipFile(io.BytesIO(source))
        out = io.BytesIO()
        with zf.ZipFile(out, "w") as z:
            for info in zin.infolist():
                data = zin.read(info.filename)
                if info.filename == "word/document.xml":
                    data = data.replace(b"{{ document_number }}", b"{{ numero_inconnu_xyz }}")
                z.writestr(info, data)
        client = self.client_for(self.A.admin)
        response = client.post(BASE, {"kind": "diploma", "file": upload(
            "d.docx", out.getvalue(), "")}, format="multipart")
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["markers"]["unknown"], ["numero_inconnu_xyz"])
        report = client.post(f"{BASE}{response.data['id']}/validate/").data["report"]
        self.assertFalse(report["ok"])
        self.assertTrue(any("numero_inconnu_xyz" in e for e in report["errors"]))
        self.assertEqual(client.post(f"{BASE}{response.data['id']}/activate/").status_code, 409)


@OFFICE
class OfficeErrorTests(TemplateTestBase):

    def stored_files(self):
        from apps.documents.models import academy_templates_root

        root = os.path.join(academy_templates_root(), str(self.A.school.pk))
        return {os.path.join(d, f) for d, _s, files in os.walk(root) for f in files}

    def refused(self, name, content, needle, mime=""):
        before = conversion_dirs()
        files_before = self.stored_files()
        client = self.client_for(self.A.admin)
        response = client.post(BASE, {"kind": "diploma", "file": upload(name, content, mime)},
                               format="multipart")
        self.assertEqual(response.status_code, 400, getattr(response, "data", None))
        self.assertIn(needle.lower(), response.data["detail"].lower())
        self.assertFalse(AcademyDocumentTemplate.objects.filter(academy=self.A.school).exists())
        self.assertEqual(self.stored_files(), files_before)  # aucun fichier orphelin
        self.assertEqual(conversion_dirs() - before, set())  # aucun répertoire temporaire restant
        return response

    def zip_with(self, source, replace=None, add=None):
        zin = zipfile.ZipFile(io.BytesIO(source))
        out = io.BytesIO()
        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
            for info in zin.infolist():
                data = zin.read(info.filename)
                if replace and info.filename in replace:
                    data = replace[info.filename]
                z.writestr(info, data)
            for name, data in (add or {}).items():
                z.writestr(name, data)
        return out.getvalue()

    def test_docx_avec_macros_refuse(self):
        content = self.zip_with(fixture("diplome_paysage_marqueurs.docx"),
                                add={"word/vbaProject.bin": b"\x00" * 64})
        self.refused("macro.docx", content, "macros")

    def test_extension_falsifiee(self):
        self.refused("faux.docx", pdf_bytes(RED), "ne correspond pas")
        self.refused("faux.odt", fixture("diplome_paysage_marqueurs.docx"), "ne correspond pas")
        self.refused("faux.doc", fixture("diplome_diapo_marqueurs.ppt"), "ne correspond pas")

    def test_docx_tronque_refuse(self):
        data = fixture("diplome_paysage_marqueurs.docx")
        self.refused("tronque.docx", data[: len(data) // 2], "corrompu")

    def test_conversion_impossible_xml_invalide(self):
        content = self.zip_with(fixture("diplome_paysage_marqueurs.docx"),
                                replace={"word/document.xml": b"<<< pas du xml >>>" * 50})
        self.refused("illisible.docx", content, "conversion de ce document a échoué")

    def test_archive_piegee_refusee(self):
        out = io.BytesIO()
        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
            for info in zipfile.ZipFile(io.BytesIO(fixture("diplome_paysage_marqueurs.docx"))).infolist():
                z.writestr(info, zipfile.ZipFile(io.BytesIO(fixture(
                    "diplome_paysage_marqueurs.docx"))).read(info.filename))
            z.writestr("word/media/bombe.bin", b"\x00" * (300 * 1024 * 1024))
        self.assertLess(len(out.getvalue()), 2 * 1024 * 1024)
        self.refused("bombe.docx", out.getvalue(), "démesuré")

    @override_settings(DOCUMENT_CONVERSION_TIMEOUT=1)
    def test_delai_de_conversion_depasse(self):
        self.refused("lent.docx", fixture("diplome_paysage_marqueurs.docx"), "délai maximal")

    def test_rtf_avec_objet_ole_refuse(self):
        self.refused("objet.rtf", b"{\\rtf1\\ansi {\\object\\objemb{\\*\\objdata 0105}}}", "objets incorporés")

    def test_pdf_sans_page_refuse(self):
        empty = (b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
                 b"2 0 obj<</Type/Pages/Kids[]/Count 0>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF")
        client = self.client_for(self.A.admin)
        response = client.post(BASE, {"kind": "diploma", "file": upload("vide.pdf", empty, "application/pdf")},
                               format="multipart")
        self.assertEqual(response.status_code, 400)
        self.assertRegex(response.data["detail"], "aucune page|lisible")

    def test_pdf_contenant_des_marqueurs_ne_peut_pas_etre_active(self):
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.pdfgen import canvas

        out = io.BytesIO()
        pdf = canvas.Canvas(out, pagesize=landscape(A4))
        pdf.drawString(100, 300, "Nom : {{ student_name }}")
        pdf.save()
        tpl = self.ready_template_or_report(out.getvalue())
        self.assertFalse(tpl["ok"])
        self.assertTrue(any("resteraient visibles (student_name)" in e for e in tpl["errors"]),
                        tpl["errors"])

    def ready_template_or_report(self, content):
        client = self.client_for(self.A.admin)
        data = client.post(BASE, {"kind": "diploma", "file": upload("m.pdf", content, "application/pdf")},
                           format="multipart").data
        client.patch(f"{BASE}{data['id']}/", {"fields": LANDSCAPE_FIELDS}, format="json")
        return client.post(f"{BASE}{data['id']}/validate/").data["report"]


class ImageFormatTests(TemplateTestBase):
    """TIFF et WEBP : normalisés par Pillow (aucun LibreOffice requis)."""

    def image_flow(self, name, content, color):
        client = self.client_for(self.A.admin)
        data = client.post(BASE, {"kind": "diploma", "file": upload(name, content, "")},
                           format="multipart").data
        self.assertIn("id", data, data)
        self.ready = data
        client.patch(f"{BASE}{data['id']}/", {"fields": LANDSCAPE_FIELDS}, format="json")
        self.assertTrue(client.post(f"{BASE}{data['id']}/validate/").data["report"]["ok"])
        client.post(f"{BASE}{data['id']}/activate/")
        response, pdf = self.produce(self.A, "diploma")
        self.assertEqual(response.data["status"], "issued")
        self.assertTrue(close(pixel_at(pdf, 25, 60, 297, 210), color))
        self.assertIn(self.A.student.get_full_name(), pdf_text(pdf)[0])
        return data

    def test_tiff(self):
        data = self.image_flow("fond.tif", png_bytes(GREEN, fmt="TIFF"), GREEN)
        self.assertEqual((data["source_format"], data["normalized_format"]), ("tiff", "png"))

    def test_webp(self):
        data = self.image_flow("fond.webp", png_bytes(BLUE, fmt="WEBP"), BLUE)
        self.assertEqual((data["source_format"], data["normalized_format"]), ("webp", "png"))

    def test_tiff_de_plusieurs_pages_devient_un_pdf_a_page_choisie(self):
        from PIL import Image

        out = io.BytesIO()
        pages = [Image.new("RGB", (1754, 1240), c) for c in (RED, YELLOW)]
        pages[0].save(out, "TIFF", save_all=True, append_images=pages[1:])
        client = self.client_for(self.A.admin)
        data = client.post(BASE, {"kind": "diploma", "file": upload("deux.tiff", out.getvalue(), "image/tiff")},
                           format="multipart").data
        self.assertEqual((data["normalized_format"], data["page_count"]), ("pdf", 2))
        client.patch(f"{BASE}{data['id']}/", {"fields": LANDSCAPE_FIELDS, "options": {"page_index": 1}},
                     format="json")
        self.assertTrue(client.post(f"{BASE}{data['id']}/validate/").data["report"]["ok"])
        client.post(f"{BASE}{data['id']}/activate/")
        _r, pdf = self.produce(self.A, "diploma")
        page_w, page_h = data["page_width_mm"], data["page_height_mm"]
        self.assertTrue(close(pixel_at(pdf, 25, 60, page_w, page_h), YELLOW))


@OFFICE
class MultiAcademyMultiFormatTests(TemplateTestBase):
    """
    A : diplôme DOCX + certificat PDF.  B : diplôme PNG + certificat DOCX.
    Téléversés directement ; documents des deux académies produits et relus.
    """

    def test_quatre_documents_bons_fonds_bonnes_donnees_acces_croises_refuses(self):
        a_dip = self.ready_template(self.A, "diploma", fixture("diplome_paysage_marqueurs.docx"),
                                    "diplome.docx", "", None)  # champs placés aux marqueurs
        a_cer = self.ready_template(self.A, "certificate", pdf_bytes(YELLOW, portrait=True),
                                    "certificat.pdf", "application/pdf", PORTRAIT_FIELDS,
                                    options={"certificate_purpose": "Pour servir et valoir"})
        b_dip = self.ready_template(self.B, "diploma", png_bytes(RED), "diplome.png", "image/png",
                                    LANDSCAPE_FIELDS)
        b_cer = self.ready_template(self.B, "certificate", fixture("certificat_portrait.docx"),
                                    "certificat.docx", "", CERT_DOCX_FIELDS,
                                    options={"certificate_purpose": "Pour servir et valoir"})
        self.assertEqual((a_dip.source_format, b_cer.source_format), ("docx", "docx"))

        _r, a1 = self.produce(self.A, "diploma")
        _r, a2 = self.produce(self.A, "certificate")
        _r, b1 = self.produce(self.B, "diploma")
        _r, b2 = self.produce(self.B, "certificate")
        texts = {k: pdf_text(v)[0] for k, v in {"a1": a1, "a2": a2, "b1": b1, "b2": b2}.items()}
        self.assertIn("DIPLÔME DE FIN D'ÉTUDES", texts["a1"])
        self.assertTrue(close(pixel_at(a2, 25, 60, 210, 297), YELLOW))
        self.assertTrue(close(pixel_at(b1, 25, 60, 297, 210), RED))
        self.assertIn("CERTIFICAT DE SCOLARITÉ", texts["b2"])
        for key, built, other in (("a1", self.A, self.B), ("a2", self.A, self.B),
                                  ("b1", self.B, self.A), ("b2", self.B, self.A)):
            self.assertIn(built.student.get_full_name(), texts[key])
            self.assertNotIn(other.student.get_full_name(), texts[key])
        numbers = GeneratedDocument.objects.values_list("number", flat=True)
        self.assertEqual(len(set(numbers)), 4)

        client = self.client_for(self.A.admin)
        for tpl in (b_dip, b_cer):
            for suffix in ("", "background/", "original/"):
                self.assertEqual(client.get(f"{BASE}{tpl.pk}/{suffix}").status_code, 404)
            self.assertEqual(client.post(f"{BASE}{tpl.pk}/disable/").status_code, 404)
        self.assertEqual(client.get(BASE).data["kinds"]["certificate"]["active"]["id"], a_cer.pk)

    def test_gabarit_remplace_pendant_une_production(self):
        self.ready_template(self.A, "diploma", fixture("diplome_paysage_marqueurs.docx"),
                            "v1.docx", "", None)
        _r, issued = self.produce(self.A, "diploma")
        client = self.client_for(self.A.admin)
        draft = client.post("/api/documents/", {"student": self.A.student.pk, "kind": "diploma"},
                            format="json").data
        self.ready_template(self.A, "diploma", fixture("diplome_paysage_marqueurs.odt"),
                            "v2.odt", "", None)
        response = client.post(f"/api/documents/{draft['id']}/issue/")
        self.assertEqual(response.status_code, 409)
        self.assertIn("n'est plus en service", response.data["detail"])
        first = GeneratedDocument.objects.filter(status="issued").first()
        with open(first.absolute_path, "rb") as handle:
            self.assertEqual(handle.read(), issued)


@OFFICE
@override_settings(PRIVATE_MEDIA_ROOT=tempfile.mkdtemp(prefix="feba-conv-conc-"))
class ConcurrentConversionTests(TransactionTestCase):
    """Conversions simultanées : profils LibreOffice isolés, versions distinctes."""

    def test_trois_conversions_simultanees(self):
        import threading

        from django.db import connection
        if connection.vendor != "postgresql":
            self.skipTest("Concurrence réelle : PostgreSQL requis.")
        from apps.documents import academy_templates as uploads

        academy = build_academy("CONV", "physical_secondary").school
        results = []

        def run(name):
            try:
                tpl = uploads.create_version(
                    academy=academy, kind="diploma",
                    uploaded_file=upload(name, fixture(name), ""))
                results.append(("ok", tpl.version, tpl.source_format))
            except Exception as exc:  # noqa: BLE001
                results.append(("error", repr(exc)))
            finally:
                connection.close()

        names = ["diplome_paysage_marqueurs.docx", "diplome_paysage_marqueurs.odt",
                 "diplome_diapo_marqueurs.pptx"]
        threads = [threading.Thread(target=run, args=(n,)) for n in names]
        [t.start() for t in threads]
        [t.join() for t in threads]
        self.assertTrue(all(r[0] == "ok" for r in results), results)
        self.assertEqual(sorted(r[1] for r in results), [1, 2, 3])
        self.assertEqual(sorted(r[2] for r in results), ["docx", "odt", "pptx"])


def char_span(content, word):
    """(gauche, droite) en points du premier mot `word` dans le PDF, ou None."""
    import pypdfium2 as pdfium

    document = pdfium.PdfDocument(content)
    try:
        textpage = document[0].get_textpage()
        searcher = textpage.search(word, match_case=True)
        hit = searcher.get_next()
        if hit is None:
            return None
        start, length = hit
        boxes = [textpage.get_charbox(i) for i in range(start, start + length)]
        searcher.close()
        textpage.close()
        return min(b[0] for b in boxes), max(b[2] for b in boxes)
    finally:
        document.close()


class MarkerIsolationUnitTests(unittest.TestCase):
    """Isolement des marqueurs dans le XML OpenDocument (sans LibreOffice)."""

    def test_marqueur_decoupe_entre_plusieurs_portions(self):
        xml = ('<office:automatic-styles></office:automatic-styles>'
               '<text:p text:style-name="P1">Élève : <text:span text:style-name="T1">{{ stu</text:span>'
               '<text:span text:style-name="T2">dent_name }}</text:span> fin</text:p>')
        result, count = conversion._isolate_in_xml(xml)
        self.assertEqual(count, 1)
        self.assertIn('<text:span text:style-name="FebaMarqueur">{{ student_name }}</text:span>', result)
        self.assertIn("Élève : ", result)
        self.assertIn(" fin</text:p>", result)
        self.assertNotIn("dent_name }}</text:span> fin", result)
        self.assertIn('style:name="FebaMarqueur"', result)

    def test_plusieurs_marqueurs_et_paragraphes_imbriques(self):
        xml = ('<office:automatic-styles/><text:p>A {{ a }} B {{ b }}'
               '<draw:frame><draw:text-box><text:p>{{ c }}</text:p></draw:text-box></draw:frame></text:p>')
        result, count = conversion._isolate_in_xml(xml)
        self.assertEqual(count, 3)
        for name in ("a", "b", "c"):
            self.assertIn(f'<text:span text:style-name="FebaMarqueur">{{{{ {name} }}}}</text:span>', result)

    def test_sans_marqueur_rien_ne_change(self):
        xml = "<office:automatic-styles/><text:p>Diplôme {{ pas un marqueur</text:p>"
        self.assertEqual(conversion._isolate_in_xml(xml), (xml, 0))


@OFFICE
class MarkerLayoutTests(TemplateTestBase):
    """Le fond ne bouge pas quand les marqueurs sont retirés : aucune superposition."""

    def produce_with(self, filename, content=None):
        client = self.client_for(self.A.admin)
        data = client.post(BASE, {"kind": "diploma", "file": upload(
            filename, content or fixture(filename), "")}, format="multipart").data
        self.assertTrue(client.post(f"{BASE}{data['id']}/validate/").data["report"]["ok"])
        client.post(f"{BASE}{data['id']}/activate/")
        _r, pdf = self.produce(self.A, "diploma")
        return data, pdf

    def test_docx_la_valeur_suit_le_texte_qui_la_precede(self):
        _d, pdf = self.produce_with("diplome_paysage_marqueurs.docx")
        scolaire = char_span(pdf, "scolaire")
        annee = char_span(pdf, self.A.year.name)
        self.assertIsNotNone(scolaire)
        self.assertIsNotNone(annee)
        self.assertGreaterEqual(annee[0], scolaire[1] - 0.5, (scolaire, annee))

    def test_pptx_la_date_suit_delivre_le(self):
        from django.utils import timezone

        _d, pdf = self.produce_with("diplome_diapo_marqueurs.pptx")
        libelle = char_span(pdf, "Délivré le")
        date = char_span(pdf, timezone.localdate().strftime("%d/%m/%Y"))
        self.assertGreaterEqual(date[0], libelle[1] - 0.5, (libelle, date))

    def test_marqueur_coupe_entre_deux_portions_word(self):
        source = fixture("diplome_paysage_marqueurs.docx")
        zin = zipfile.ZipFile(io.BytesIO(source))
        out = io.BytesIO()
        with zipfile.ZipFile(out, "w") as z:
            for info in zin.infolist():
                data = zin.read(info.filename)
                if info.filename == "word/document.xml":
                    self.assertIn(b"{{ issue_date }}", data)
                    data = data.replace(b"{{ issue_date }}",
                                        b"{{ issue</w:t></w:r><w:r><w:rPr><w:b/></w:rPr><w:t>_date }}")
                z.writestr(info, data)
        data, pdf = self.produce_with("coupe.docx", out.getvalue())
        self.assertIn("issue_date", {f["name"] for f in data["fields"]})
        self.assertNotIn("{{", pdf_text(pdf)[0])


@OFFICE
class MarkerNeighbourTests(MarkerLayoutTests):
    """La zone d'un marqueur s'arrête au texte du fond qui le suit."""

    def test_pptx_le_nom_de_l_academie_ne_recouvre_pas_le_tiret(self):
        data, pdf = self.produce_with("diplome_diapo_marqueurs.pptx")
        academy = next(f for f in data["fields"] if f["name"] == "academy_name")
        tiret = char_span(pdf, "—")
        self.assertIsNotNone(tiret)
        self.assertLessEqual(academy["x_mm"] + academy["width_mm"], tiret[0] / 72 * 25.4)
        nom = char_span(pdf, self.A.school.legal_name or self.A.school.name)
        self.assertLessEqual(nom[1], tiret[0] + 0.5, (nom, tiret))
