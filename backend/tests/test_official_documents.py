"""
Tests du MOTEUR DOCUMENTAIRE (P2 / P3) — diplômes et certificats.

CE QUI EST ÉPROUVÉ ICI
----------------------
  1. Un fond qui n'est pas l'original est REFUSÉ — dimensions et empreinte.
  2. Le fond est reproduit sans déformation : comparaison pixel à pixel.
  3. Rien n'est émis tant que le gabarit n'est pas calibré.
  4. Un nom trop long n'est pas tronqué : le document échoue.
  5. Un document émis ne se modifie plus ; il se remplace.
  6. Un parent n'accède qu'aux documents de ses enfants.
  7. Aucun fichier n'est accessible sans passer par la vue authentifiée.

POURQUOI UN GABARIT SYNTHÉTIQUE
-------------------------------
Les fonds officiels FEBA ne sont pas versionnés — ce sont des documents
de l'établissement. Ces tests fabriquent donc leur propre image de fond et
leur propre gabarit, avec exactement la même mécanique. Ce qui est vérifié
est le MOTEUR ; l'installation des fonds réels est vérifiée séparément par
« manage.py document_templates_check », dont la sortie figure au rapport.
"""
import hashlib
import json
import os
import shutil
import tempfile

from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import CustomUser
from apps.schools.models import School, SchoolYear
from apps.students.models import Student

#: Racines réelles du registre, capturées AVANT toute surcharge. Les
#: classes de test les restaurent systématiquement, plutôt que de rendre
#: la valeur trouvée à leur entrée.
from apps.documents import templates_registry as _registry  # noqa: E402

PRISTINE_TEMPLATES_ROOT = _registry.TEMPLATES_ROOT
PRISTINE_ORIGINALS_DIR = _registry.ORIGINALS_DIR

#: Dimensions du fond synthétique. Rapport d'aspect volontairement
#: différent de l'A4 paysage, pour éprouver le mode « contain ».
FIXTURE_WIDTH, FIXTURE_HEIGHT = 1492, 1054


def auth(client, email, password="Pass1234!"):
    resp = client.post("/api/auth/login/", {"email": email, "password": password})
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {resp.data.get('access', '')}")
    return client


def make_background(path, seed=0):
    """
    Fond de test : un dégradé et quelques repères.

    Une image unie ne prouverait rien — un étirement ne s'y verrait pas.
    Le dégradé, lui, décale toutes ses valeurs dès que la géométrie change.
    """
    from PIL import Image, ImageDraw

    image = Image.new("RGB", (FIXTURE_WIDTH, FIXTURE_HEIGHT), (255, 255, 255))
    draw = ImageDraw.Draw(image)
    for x in range(0, FIXTURE_WIDTH, 4):
        shade = (x * 255 // FIXTURE_WIDTH + seed) % 256
        draw.line([(x, 0), (x, FIXTURE_HEIGHT)], fill=(shade, 120, 200 - shade // 2))
    draw.rectangle([20, 20, FIXTURE_WIDTH - 20, FIXTURE_HEIGHT - 20],
                   outline=(10, 30, 90), width=8)
    image.save(path, "PNG")
    return path


def template_payload(template_id, sha256, *, calibrated=True, truncate=False):
    return {
        "id": template_id,
        "version": 1,
        "label": "Gabarit de test",
        "background": {
            "file": f"{template_id}.png",
            "sha256": sha256,
            "width_px": FIXTURE_WIDTH,
            "height_px": FIXTURE_HEIGHT,
        },
        "page": {"width_mm": 297.0, "height_mm": 210.0, "fit": "contain"},
        "origin": "top-left",
        "calibrated": calibrated,
        "calibration": {"tolerance_mm": 0.2},
        "fields": [
            {
                "name": "student_name", "label": "Nom de l'élève", "type": "text",
                "required": True,
                "box": {"x_mm": 48.0, "y_mm": 92.0, "width_mm": 201.0, "height_mm": 16.0},
                "align": "center",
                "font": {"family": "Helvetica-Bold", "size_pt": 30, "min_size_pt": 20},
                "color": "#1E3A6E", "shrink_to_fit": True, "truncate": truncate,
            },
            {
                "name": "issue_date", "label": "Date", "type": "date", "required": True,
                "box": {"x_mm": 40.0, "y_mm": 168.0, "width_mm": 70.0, "height_mm": 8.0},
                "align": "center", "font": {"family": "Helvetica", "size_pt": 11},
            },
            {
                "name": "document_number", "label": "Numéro", "type": "text",
                "required": False,
                "box": {"x_mm": 232.0, "y_mm": 192.0, "width_mm": 55.0, "height_mm": 6.0},
                "align": "right", "font": {"family": "Helvetica", "size_pt": 8},
            },
        ],
        "assets": [],
    }


class DocumentEngineTestCase(TestCase):
    """Socle : gabarit synthétique installé dans un répertoire temporaire."""

    template_id = "testdoc"
    calibrated = True
    truncate = False

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.tmp_root = tempfile.mkdtemp(prefix="feba-doc-templates-")
        cls.private_root = tempfile.mkdtemp(prefix="feba-doc-private-")
        os.makedirs(os.path.join(cls.tmp_root, "originals"), exist_ok=True)

        cls.background_path = os.path.join(
            cls.tmp_root, "originals", f"{cls.template_id}.png",
        )
        make_background(cls.background_path)
        with open(cls.background_path, "rb") as handle:
            cls.background_sha = hashlib.sha256(handle.read()).hexdigest()

        cls.template_path = os.path.join(cls.tmp_root, f"{cls.template_id}_template.json")
        with open(cls.template_path, "w", encoding="utf-8") as handle:
            json.dump(
                template_payload(cls.template_id, cls.background_sha,
                                 calibrated=cls.calibrated, truncate=cls.truncate),
                handle,
            )

        cls.settings_override = override_settings(
            DOCUMENT_TEMPLATES_ROOT=cls.tmp_root,
            PRIVATE_MEDIA_ROOT=cls.private_root,
        )
        cls.settings_override.enable()

        # Le registre lit sa racine au moment de l'import : la surcharge de
        # réglages seule ne suffit pas, il faut la repointer explicitement.
        # La valeur restaurée est celle capturée à l'import du module de
        # test, et non celle trouvée à l'entrée : une classe dont le
        # démontage aurait échoué contaminerait sinon toutes les suivantes.
        from apps.documents import templates_registry

        templates_registry.TEMPLATES_ROOT = cls.tmp_root
        templates_registry.ORIGINALS_DIR = os.path.join(cls.tmp_root, "originals")
        templates_registry.clear_cache()

    @classmethod
    def tearDownClass(cls):
        from apps.documents import templates_registry

        templates_registry.TEMPLATES_ROOT = PRISTINE_TEMPLATES_ROOT
        templates_registry.ORIGINALS_DIR = PRISTINE_ORIGINALS_DIR
        templates_registry.clear_cache()
        cls.settings_override.disable()
        shutil.rmtree(cls.tmp_root, ignore_errors=True)
        shutil.rmtree(cls.private_root, ignore_errors=True)
        super().tearDownClass()

    @classmethod
    def setUpTestData(cls):
        cls.feba = School.objects.create(
            name="FEBA documents", address="Cotonou", entity_type="campus",
            code="DOC-FEBA", currency_code="XOF",
        )
        cls.other = School.objects.create(
            name="FHA documents", address="En ligne", entity_type="online",
            code="DOC-FHA", currency_code="USD",
        )
        cls.year = SchoolYear.objects.create(
            school=cls.feba, name="2025-2026-doc", is_current=True,
            start_date="2025-09-01", end_date="2026-07-01",
        )
        cls.student = Student.objects.create(
            school=cls.feba, school_year=cls.year, first_name="Awa",
            last_name="Kponou", date_of_birth="2012-05-04",
        )
        cls.other_student = Student.objects.create(
            school=cls.other, school_year=None, first_name="Élise",
            last_name="Diallo", date_of_birth="2013-02-02",
        )
        cls.admin = CustomUser.objects.create_user(
            username="doc_admin", email="doc.admin@test.io", password="Pass1234!",
            role="admin", school=cls.feba, first_name="Admin", last_name="FEBA",
        )
        cls.other_admin = CustomUser.objects.create_user(
            username="doc_admin_fha", email="doc.admin.fha@test.io",
            password="Pass1234!", role="admin", school=cls.other,
            first_name="Admin", last_name="FHA",
        )
        cls.parent_user = cls._make_parent(cls.feba, cls.student)
        cls.other_parent = cls._make_parent(cls.other, cls.other_student, suffix="fha")

    @classmethod
    def _make_parent(cls, school, student, suffix="feba"):
        from apps.parents.models import Parent, ParentStudent

        user = CustomUser.objects.create_user(
            username=f"doc_parent_{suffix}", email=f"doc.parent.{suffix}@test.io",
            password="Pass1234!", role="parent", school=school,
            first_name="Parent", last_name=suffix.upper(),
        )
        parent = Parent.objects.create(user=user)
        ParentStudent.objects.create(parent=parent, student=student)
        return user


class BackgroundLockTests(DocumentEngineTestCase):
    """Le fond est verrouillé : rien d'autre n'est accepté."""

    def test_le_fond_conforme_est_accepte(self):
        from apps.documents.templates_registry import load_template

        template = load_template(self.template_id, use_cache=False)
        self.assertEqual(template.verify_background(), self.background_sha)
        self.assertTrue(template.can_issue)

    def test_un_fond_absent_bloque_l_emission(self):
        from apps.documents.templates_registry import BackgroundMissing, load_template

        os.rename(self.background_path, self.background_path + ".bak")
        try:
            template = load_template(self.template_id, use_cache=False)
            with self.assertRaises(BackgroundMissing):
                template.verify_background()
            self.assertFalse(template.can_issue)
        finally:
            os.rename(self.background_path + ".bak", self.background_path)

    def test_un_reexport_du_meme_visuel_est_refuse(self):
        """
        Le point central du verrouillage : mêmes dimensions, visuel presque
        identique, fichier différent. Un ré-export peut décaler les
        ornements de un ou deux pixels — invisible, et jamais corrigé.
        """
        from apps.documents.templates_registry import BackgroundMismatch, load_template

        shutil.copy2(self.background_path, self.background_path + ".bak")
        try:
            make_background(self.background_path, seed=3)
            template = load_template(self.template_id, use_cache=False)
            with self.assertRaises(BackgroundMismatch) as ctx:
                template.verify_background()
            self.assertIn("empreinte", str(ctx.exception).lower())
        finally:
            shutil.move(self.background_path + ".bak", self.background_path)

    def test_un_fond_redimensionne_est_refuse(self):
        from PIL import Image

        from apps.documents.templates_registry import BackgroundMismatch, load_template

        shutil.copy2(self.background_path, self.background_path + ".bak")
        try:
            with Image.open(self.background_path) as image:
                image.resize((FIXTURE_WIDTH - 2, FIXTURE_HEIGHT)).save(
                    self.background_path, "PNG",
                )
            template = load_template(self.template_id, use_cache=False)
            with self.assertRaises(BackgroundMismatch) as ctx:
                template.verify_background()
            self.assertIn("px", str(ctx.exception))
        finally:
            shutil.move(self.background_path + ".bak", self.background_path)


class RenderFidelityTests(DocumentEngineTestCase):
    """Le fond est reproduit sans déformation — mesuré, pas affirmé."""

    def test_la_page_est_un_a4_paysage(self):
        import fitz

        from apps.documents.renderer import render_document

        content = render_document(
            self.template_id, {"student_name": "Awa Kponou",
                               "issue_date": "01/07/2026"},
        )
        document = fitz.open(stream=content, filetype="pdf")
        rect = document[0].rect
        # 297 × 210 mm en points : 841,89 × 595,28.
        self.assertAlmostEqual(rect.width, 841.89, places=1)
        self.assertAlmostEqual(rect.height, 595.28, places=1)
        document.close()

    def test_le_rapport_d_aspect_du_fond_est_preserve(self):
        """
        Le fond mesure 1492×1054 (1,41556) et la page 297×210 (1,41429).
        L'étirer serait invisible et déplacerait tout d'environ 0,1 mm,
        soit la moitié de la tolérance de calibrage.
        """
        from apps.documents.renderer import Layout
        from apps.documents.templates_registry import load_template

        layout = Layout(load_template(self.template_id, use_cache=False))
        rendered_ratio = layout.width_mm / layout.height_mm
        source_ratio = FIXTURE_WIDTH / FIXTURE_HEIGHT
        self.assertAlmostEqual(rendered_ratio, source_ratio, places=4)
        # Le décentrage résiduel reste sous la tolérance.
        self.assertLess(abs(layout.offset_y_mm), 0.2)

    def test_le_fond_est_reproduit_pixel_a_pixel(self):
        """
        Comparaison réelle : le document est rendu sans champ, rastérisé à
        la résolution du fond, puis comparé point par point.
        """
        import fitz
        from PIL import Image, ImageChops

        from apps.documents.renderer import render_document
        from apps.documents.templates_registry import load_template

        # Le gabarit muté doit être celui du CACHE : c'est lui que
        # `render_document` utilisera. Une copie non cachée laisserait les
        # champs obligatoires en place et ferait échouer le rendu à vide.
        template = load_template(self.template_id)
        for field in template.fields:
            field.required = False
        try:
            content = render_document(self.template_id, {})
        finally:
            for field in template.fields:
                field.required = field.name == "student_name"

        document = fitz.open(stream=content, filetype="pdf")
        page = document[0]
        pixmap = page.get_pixmap(
            matrix=fitz.Matrix(FIXTURE_WIDTH / page.rect.width,
                               FIXTURE_HEIGHT / page.rect.height),
            alpha=False,
        )
        rendered = Image.frombytes(
            "RGB", (pixmap.width, pixmap.height), pixmap.samples,
        )
        document.close()

        original = Image.open(self.background_path).convert("RGB")
        if rendered.size != original.size:
            rendered = rendered.resize(original.size, Image.LANCZOS)

        difference = ImageChops.difference(rendered, original)
        total = original.size[0] * original.size[1]
        differing = sum(1 for pixel in difference.getdata() if max(pixel) > 12)
        ratio = differing * 100.0 / total

        # Seuil large : le rééchantillonnage PDF → image produit toujours
        # un bruit de bordure. Un étirement, lui, dépasse largement 1 %.
        self.assertLess(ratio, 1.0, f"{ratio:.4f} % des pixels diffèrent du fond.")

    def test_la_grille_de_calibrage_utilise_le_meme_moteur(self):
        from apps.documents.renderer import render_document

        content = render_document(
            self.template_id, {"student_name": "Awa", "issue_date": "01/07/2026"},
            preview=True, calibration_grid=True,
        )
        self.assertTrue(content.startswith(b"%PDF"))


class FieldRulesTests(DocumentEngineTestCase):
    """Ce que le moteur refuse d'écrire."""

    def test_un_nom_trop_long_reduit_la_police(self):
        from apps.documents.renderer import render_document

        content = render_document(self.template_id, {
            "student_name": "Marie-Christelle Adjovi Hounkpatin",
            "issue_date": "01/07/2026",
        })
        self.assertTrue(content.startswith(b"%PDF"))

    def test_un_nom_qui_ne_tient_pas_fait_echouer_le_rendu(self):
        """
        Tronquer le nom d'un élève sur son propre diplôme produirait un
        document faux qui a l'air correct. Le moteur préfère échouer.
        """
        from apps.documents.renderer import RenderError, render_document

        with self.assertRaises(RenderError) as ctx:
            render_document(self.template_id, {
                "student_name": "Marie" + " Christelle" * 20,
                "issue_date": "01/07/2026",
            })
        self.assertIn("tronqué", str(ctx.exception))

    def test_un_champ_obligatoire_vide_fait_echouer_le_rendu(self):
        from apps.documents.renderer import RenderError, render_document

        with self.assertRaises(RenderError):
            render_document(self.template_id, {"issue_date": "01/07/2026"})

    def test_aucune_signature_n_est_dessinee_a_defaut_de_fichier(self):
        from apps.documents.renderer import resolve_resource
        from tests.branding_fixtures import make_branding

        # Aucun fichier de signature n'est fourni par le projet : la
        # ressource doit rester introuvable plutôt que d'être approchée.
        self.assertIsNone(
            resolve_resource("signature_director", make_branding()))

    def test_sans_academie_aucune_ressource_officielle_n_est_resolue(self):
        """P0 — un rendu sans académie n'appose ni cachet ni signature."""
        from apps.documents.renderer import resolve_resource

        self.assertIsNone(resolve_resource("seal_official"))
        self.assertIsNone(resolve_resource("signature_director"))

    def test_une_zone_hors_page_est_refusee_au_chargement(self):
        """
        Une zone qui déborde produit un texte invisible sans lever
        d'erreur : le document sort « réussi », amputé de son contenu.
        """
        from apps.documents.templates_registry import DocumentTemplate, TemplateError

        payload = template_payload("hors_page", self.background_sha)
        payload["fields"][0]["box"]["x_mm"] = 280.0
        with self.assertRaises(TemplateError) as ctx:
            DocumentTemplate(payload, "test")
        self.assertIn("sort de la page", str(ctx.exception))


class UncalibratedTemplateTests(DocumentEngineTestCase):
    """Un gabarit non calibré ne produit qu'un aperçu."""

    template_id = "testdoc_noncalibre"
    calibrated = False

    def test_l_emission_est_refusee(self):
        from apps.documents.renderer import RenderError, render_document

        with self.assertRaises(RenderError) as ctx:
            render_document(self.template_id, {
                "student_name": "Awa Kponou", "issue_date": "01/07/2026",
            })
        self.assertIn("calibré", str(ctx.exception))

    def test_l_apercu_est_produit_et_filigrane(self):
        import fitz

        from apps.documents.renderer import render_document

        content = render_document(
            self.template_id,
            {"student_name": "Awa Kponou", "issue_date": "01/07/2026"},
            preview=True,
        )
        document = fitz.open(stream=content, filetype="pdf")
        text = document[0].get_text()
        document.close()
        self.assertIn("NON CALIBRÉ", text)
        self.assertIn("NE PAS REMETTRE", text)


class DocumentLifecycleTests(DocumentEngineTestCase):
    """États, numérotation et immuabilité."""

    def _draft(self):
        from apps.documents.services import create_document

        return create_document(
            template_id=self.template_id, student=self.student, user=self.admin,
        )

    def test_un_brouillon_n_a_pas_de_numero(self):
        from apps.documents.models import GeneratedDocument

        document = self._draft()
        self.assertEqual(document.status, GeneratedDocument.DRAFT)
        self.assertEqual(document.number, "")
        self.assertTrue(document.file_sha256)

    def test_l_emission_attribue_un_numero_et_fige_le_document(self):
        from apps.documents.models import GeneratedDocument
        from apps.documents.services import issue_document

        document = issue_document(self._draft(), user=self.admin)
        self.assertEqual(document.status, GeneratedDocument.ISSUED)
        self.assertTrue(document.number.startswith("DOC-FEBA-"))
        self.assertTrue(document.is_frozen)

    def test_les_numeros_sont_sequentiels_et_uniques(self):
        from apps.documents.services import issue_document

        numbers = [issue_document(self._draft(), user=self.admin).number
                   for _ in range(3)]
        self.assertEqual(len(set(numbers)), 3)
        self.assertTrue(numbers[0].endswith("0001"))
        self.assertTrue(numbers[2].endswith("0003"))

    def test_un_document_emis_ne_peut_plus_etre_modifie(self):
        from apps.documents.services import issue_document

        document = issue_document(self._draft(), user=self.admin)
        with self.assertRaises(ValidationError) as ctx:
            document.store_pdf(b"%PDF-faux")
        self.assertIn("ne peut plus changer", str(ctx.exception))

    def test_un_document_emis_se_remplace_sans_disparaitre(self):
        from apps.documents.models import GeneratedDocument
        from apps.documents.services import issue_document, replace_document

        original = issue_document(self._draft(), user=self.admin)
        replacement = replace_document(original, user=self.admin, reason="Faute de frappe")

        original.refresh_from_db()
        self.assertEqual(original.status, GeneratedDocument.REPLACED)
        self.assertEqual(replacement.replaces_id, original.pk)
        self.assertEqual(replacement.status, GeneratedDocument.ISSUED)
        self.assertNotEqual(replacement.number, original.number)
        # L'ancien reste consultable : quelqu'un le détient peut-être.
        self.assertTrue(os.path.exists(original.absolute_path))

    def test_une_revocation_sans_motif_est_refusee(self):
        from apps.documents.models import GeneratedDocument
        from apps.documents.services import issue_document

        document = issue_document(self._draft(), user=self.admin)
        with self.assertRaises(ValidationError):
            document.transition_to(GeneratedDocument.REVOKED, user=self.admin)

    def test_une_transition_interdite_est_refusee(self):
        from apps.documents.models import GeneratedDocument
        from apps.documents.services import issue_document

        document = issue_document(self._draft(), user=self.admin)
        document.transition_to(GeneratedDocument.REVOKED, user=self.admin,
                               reason="Erreur de niveau")
        with self.assertRaises(ValidationError) as ctx:
            document.transition_to(GeneratedDocument.ISSUED, user=self.admin)
        self.assertIn("impossible", str(ctx.exception))

    def test_un_document_ne_franchit_pas_la_frontiere_entre_academies(self):
        from apps.documents.models import GeneratedDocument

        document = GeneratedDocument(
            academy=self.feba, student=self.other_student,
            template_id=self.template_id,
        )
        with self.assertRaises(ValidationError) as ctx:
            document.full_clean(exclude=["number", "file_path", "file_sha256"])
        self.assertIn("autre académie", str(ctx.exception).lower()
                      .replace("n'appartient pas à l'académie émettrice",
                               "autre académie"))

    def test_l_empreinte_du_gabarit_est_conservee(self):
        """
        Des années plus tard, elle permet de dire avec quelle version de
        la mise en page un document a été produit.
        """
        document = self._draft()
        self.assertEqual(len(document.template_fingerprint), 64)
        self.assertEqual(document.background_sha256, self.background_sha)

    def test_chaque_operation_laisse_une_trace(self):
        from apps.documents.services import issue_document

        document = issue_document(self._draft(), user=self.admin)
        actions = list(document.events.values_list("action", flat=True))
        self.assertIn("created", actions)
        self.assertIn("issued", actions)


class DocumentAccessTests(DocumentEngineTestCase):
    """Permissions et anti-IDOR."""

    def setUp(self):
        from apps.documents.services import create_document, issue_document

        self.document = issue_document(
            create_document(template_id=self.template_id, student=self.student,
                            user=self.admin),
            user=self.admin,
        )

    def test_le_fichier_est_hors_du_repertoire_public(self):
        from django.conf import settings

        path = self.document.absolute_path
        self.assertTrue(os.path.exists(path))
        self.assertFalse(path.startswith(str(settings.MEDIA_ROOT)))

    def test_la_reponse_api_n_expose_aucun_chemin_de_fichier(self):
        client = auth(APIClient(), "doc.admin@test.io")
        row = client.get("/api/documents/").data[0]
        serialise = str(row)
        # Ni chemin absolu, ni nom de fichier : le seul accès annoncé est
        # la route authentifiée.
        self.assertNotIn(self.private_root, serialise)
        self.assertNotIn(".pdf", serialise)
        self.assertEqual(row["download_path"], f"/api/documents/{self.document.pk}/download/")

    def test_un_parent_telecharge_le_document_de_son_enfant(self):
        client = auth(APIClient(), "doc.parent.feba@test.io")
        resp = client.get(f"/api/documents/{self.document.pk}/download/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp["Content-Type"], "application/pdf")
        self.assertIn("no-store", resp["Cache-Control"])

    def test_un_parent_n_accede_pas_au_document_d_un_autre_enfant(self):
        client = auth(APIClient(), "doc.parent.fha@test.io")
        resp = client.get(f"/api/documents/{self.document.pk}/download/")
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_un_administrateur_d_une_autre_academie_ne_voit_rien(self):
        client = auth(APIClient(), "doc.admin.fha@test.io")
        resp = client.get(f"/api/documents/{self.document.pk}/download/")
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_un_anonyme_n_accede_a_rien(self):
        resp = APIClient().get(f"/api/documents/{self.document.pk}/download/")
        self.assertIn(resp.status_code,
                      (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN))

    def test_un_parent_ne_peut_pas_produire_un_document(self):
        client = auth(APIClient(), "doc.parent.feba@test.io")
        resp = client.post("/api/documents/", {
            "student": self.student.id, "template": self.template_id,
        }, format="json")
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_un_parent_ne_peut_pas_emettre_un_document(self):
        client = auth(APIClient(), "doc.parent.feba@test.io")
        resp = client.post(f"/api/documents/{self.document.pk}/issue/", {},
                           format="json")
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_un_administrateur_produit_un_document_pour_son_academie(self):
        client = auth(APIClient(), "doc.admin@test.io")
        resp = client.post("/api/documents/", {
            "student": self.student.id, "template": self.template_id,
        }, format="json")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        self.assertEqual(resp.data["status"], "draft")

    def test_un_administrateur_ne_produit_rien_pour_une_autre_academie(self):
        client = auth(APIClient(), "doc.admin@test.io")
        resp = client.post("/api/documents/", {
            "student": self.other_student.id, "template": self.template_id,
        }, format="json")
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_l_historique_est_consultable_par_le_parent(self):
        client = auth(APIClient(), "doc.parent.feba@test.io")
        resp = client.get(f"/api/documents/{self.document.pk}/history/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(any(e["action"] == "issued" for e in resp.data))


class RealTemplatesStateTests(TestCase):
    """
    État des VRAIS gabarits FEBA livrés avec le projet.

    Ces tests ne vérifient pas un rendu — les fonds officiels ne sont pas
    versionnés. Ils vérifient que le projet dit la vérité sur son propre
    état : gabarits lisibles, cohérents, et émission bloquée tant que les
    fonds ne sont pas installés.
    """

    def test_les_deux_gabarits_sont_declares(self):
        from apps.documents.templates_registry import available_templates

        declared = available_templates()
        self.assertIn("diploma_feba", declared)
        self.assertIn("certificate_feba", declared)

    def test_les_gabarits_sont_valides_et_coherents(self):
        from apps.documents.templates_registry import load_template

        for template_id, size in (("diploma_feba", (1492, 1054)),
                                  ("certificate_feba", (1491, 1055))):
            template = load_template(template_id, use_cache=False)
            self.assertEqual(
                (template.background_width_px, template.background_height_px), size,
            )
            self.assertEqual(len(template.background_sha256), 64)
            self.assertEqual(template.page_width_mm, 297.0)
            self.assertEqual(template.page_height_mm, 210.0)
            self.assertEqual(template.tolerance_mm, 0.2)
            self.assertTrue(template.fields)

    def test_l_emission_est_bloquee_tant_que_le_fond_manque(self):
        """
        Les fonds officiels ne sont pas livrés dans le dépôt. Le moteur
        doit le dire, et refuser — pas produire un document approximatif.
        """
        from apps.documents.templates_registry import load_template

        for template_id in ("diploma_feba", "certificate_feba"):
            template = load_template(template_id, use_cache=False)
            if template.background_installed and template.calibrated:
                continue  # instance où les fonds ont été installés
            self.assertFalse(template.can_issue)
            self.assertTrue(template.issuance_blockers())

    def test_la_zone_du_cachet_n_est_jamais_remplie_par_defaut(self):
        """
        « YOUR SEAL » ne doit être recouvert que par un cachet officiel
        existant. Aucun cachet n'est inventé, et la zone n'est pas non
        plus masquée : la mention est le signal que le document n'est pas
        finalisé.
        """
        from apps.documents.templates_registry import load_template

        template = load_template("certificate_feba", use_cache=False)
        seal = next(a for a in template.assets if a.name == "official_seal")
        self.assertFalse(seal.required)
        self.assertEqual(seal.resource, "seal_official")


class InstalledTemplatesTests(TestCase):
    """
    État des VRAIS gabarits une fois les fonds installés.

    Ces tests ne s'exécutent que si les fonds sont présents : sur un clone
    frais, ils sont ignorés plutôt que rouges. Un test qui échoue faute de
    ressource n'apprend rien et finit par être ignoré pour de bon.
    """

    def setUp(self):
        from apps.documents.templates_registry import load_template

        self.load_template = load_template
        self.templates = {}
        for template_id in ("diploma_feba", "certificate_feba"):
            template = load_template(template_id, use_cache=False)
            if not template.background_installed:
                self.skipTest(f"Fond de « {template_id} » non installé.")
            self.templates[template_id] = template

    def test_les_deux_fonds_ont_les_dimensions_declarees(self):
        from PIL import Image

        for template in self.templates.values():
            with Image.open(template.background_path) as image:
                self.assertEqual(
                    image.size,
                    (template.background_width_px, template.background_height_px),
                )

    def test_un_fond_non_original_est_trace_comme_variante(self):
        """
        Le fond peut ne pas être le fichier d'origine — un canal qui
        ré-encode change les pixels. Ce qui ne doit JAMAIS arriver, c'est
        qu'un dérivé passe pour l'original sans que rien ne le dise.
        """
        for template in self.templates.values():
            if template.is_original:
                continue
            variant = template.installed_variant
            self.assertIsNotNone(
                variant,
                f"Le fond de « {template.id} » n'est pas l'original et n'est "
                f"pas déclaré comme variante : il passerait pour authentique.",
            )
            self.assertTrue(variant.reason, "Une variante sans motif est inexploitable.")
            self.assertEqual(len(variant.sha256), 64)

    def test_les_gabarits_sont_calibres_et_peuvent_emettre(self):
        for template in self.templates.values():
            self.assertTrue(template.calibrated, f"{template.id} n'est pas calibré.")
            self.assertEqual(template.tolerance_mm, 0.2)
            self.assertEqual(template.issuance_blockers(), [])

    def test_le_placeholder_du_diplome_est_neutralise(self):
        """
        « Nom Prénom » ne doit subsister nulle part sous le vrai nom. On le
        vérifie sur l'IMAGE : plus aucun pixel doré dans la bande du
        placeholder, alors que la règle d'écriture juste en dessous est
        toujours là.
        """
        import numpy as np
        from PIL import Image

        from django.core.management import call_command

        template = self.templates["diploma_feba"]
        if not template.has_derived:
            # Sur une installation neuve, le dérivé n'existe pas encore :
            # il n'est pas versionné, il se régénère. Le produire ICI
            # éprouve la commande elle-même plutôt que de sauter le test.
            call_command("document_neutralize", template=template.id, verbosity=0)
            template = self.load_template(template.id, use_cache=False)
        self.assertTrue(template.has_derived,
                        "La neutralisation n'a produit aucun fond dérivé.")

        array = np.asarray(Image.open(template.derived_path).convert("RGB")).astype(int)
        red, green, blue = array[..., 0], array[..., 1], array[..., 2]
        gold = (red > 130) & (green > 95) & (blue < green - 25) & (red > blue + 55)

        # Bande du placeholder (px y 615–687) : plus un seul pixel doré.
        self.assertEqual(int(gold[615:688, 400:1100].sum()), 0,
                         "La mention « Nom Prénom » subsiste sur le fond dérivé.")
        # Règle d'écriture (px y 692–693) : toujours présente.
        self.assertGreater(int(gold[692:694, 400:1100].sum()), 500,
                           "La règle d'écriture a été effacée avec le placeholder.")

    def test_le_rendu_ne_deplace_aucune_zone_statique(self):
        """
        Comparaison pixel à pixel réelle, zones variables exclues. C'est la
        seule preuve recevable qu'aucune bordure, aucun ornement n'a bougé.
        """
        import fitz
        import numpy as np
        from PIL import Image, ImageChops, ImageDraw

        from apps.documents.renderer import render_document

        for template in self.templates.values():
            values = {
                field.name: ("01/01/2026" if field.type == "date"
                             else "Exemple Comparaison" if field.name == "student_name"
                             else "—")
                for field in template.fields
            }
            content = render_document(template.id, values)

            document = fitz.open(stream=content, filetype="pdf")
            page = document[0]
            width = template.background_width_px
            height = template.background_height_px
            pixmap = page.get_pixmap(
                matrix=fitz.Matrix(width / page.rect.width, height / page.rect.height),
                alpha=False,
            )
            rendered = Image.frombytes("RGB", (pixmap.width, pixmap.height), pixmap.samples)
            document.close()

            original = Image.open(template.background_path).convert("RGB")
            if rendered.size != original.size:
                rendered = rendered.resize(original.size, Image.LANCZOS)

            page_w, page_h = template.page_width_mm, template.page_height_mm
            ratio = width / height
            if ratio >= page_w / page_h:
                draw_w, draw_h = page_w, page_w / ratio
            else:
                draw_w, draw_h = page_h * ratio, page_h
            off_x, off_y = (page_w - draw_w) / 2, (page_h - draw_h) / 2

            variable = Image.new("L", original.size, 0)
            painter = ImageDraw.Draw(variable)
            for item in template.all_boxes:
                box = item.box
                pad = 1.0 + getattr(item, "bleed_mm", 0.0)
                painter.rectangle([
                    int((box.x_mm - pad - off_x) * width / draw_w),
                    int((box.y_mm - pad - off_y) * height / draw_h),
                    int((box.x_mm + box.width_mm + pad - off_x) * width / draw_w),
                    int((box.y_mm + box.height_mm + pad - off_y) * height / draw_h),
                ], fill=255)

            delta = np.asarray(ImageChops.difference(rendered, original)).max(axis=2)
            delta[np.asarray(variable) > 0] = 0
            differing = int((delta > 16).sum())
            statiques = int((np.asarray(variable) == 0).sum())
            ratio_pct = differing * 100.0 / max(1, statiques)

            self.assertLess(
                ratio_pct, 0.05,
                f"{template.id} : {ratio_pct:.4f} % des pixels STATIQUES "
                f"diffèrent du fond — un ornement a bougé.",
            )

    def test_les_cinq_noms_difficiles_sont_rendus_sans_troncature(self):
        from apps.documents.management.commands.document_samples import SAMPLE_NAMES
        from apps.documents.renderer import render_document

        for template in self.templates.values():
            for key, name in SAMPLE_NAMES:
                values = {"student_name": name, "issue_date": "04/07/2026"}
                content = render_document(template.id, values)
                self.assertTrue(content.startswith(b"%PDF"),
                                f"{template.id} / {key} : rendu invalide.")

    def test_le_sceau_officiel_du_projet_est_disponible(self):
        """
        Le certificat remplace « YOUR SEAL » par le cachet officiel de la
        Direction, déjà utilisé sur les bulletins. Ce test vérifie qu'il
        existe — pas qu'il est joli.
        """
        import os

        from apps.documents.renderer import resolve_resource
        from tests.branding_fixtures import make_branding

        seal = resolve_resource("seal_official", make_branding())
        self.assertIsNotNone(seal, "Aucun sceau officiel dans les ressources.")
        # La version à canal alpha est préférée : l'opaque poserait un
        # carré blanc par-dessus le médaillon doré.
        from PIL import Image

        with Image.open(seal) as image:
            self.assertEqual(image.mode, "RGBA",
                             f"{os.path.basename(seal)} n'a pas de canal alpha.")

    def test_aucune_signature_n_est_inventee(self):
        from apps.documents.renderer import resolve_resource
        from tests.branding_fixtures import make_branding

        self.assertIsNone(
            resolve_resource("signature_director", make_branding()),
            "Une signature a été trouvée : vérifier qu'elle est bien officielle.",
        )
