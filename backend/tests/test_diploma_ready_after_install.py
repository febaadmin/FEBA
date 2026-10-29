"""
P7 — Le diplôme est produisible immédiatement après l'installation.

CE QUI EST TESTÉ, ET POURQUOI
-----------------------------
L'application était livrée avec ce message à la place du diplôme :

    « Le gabarit déclare 1 mention(s) d'exemple à neutraliser, mais le fond
      dérivé n'existe pas encore. Lancez : manage.py document_neutralize »

Le fond neutralisé n'était pas versionné. Il fallait donc, sur chaque
installation, lancer une commande d'atelier pour obtenir un diplôme — et
personne ne le savait avant d'avoir cliqué.

Ces tests parcourent les douze étapes du contrôle demandé : installation
telle qu'elle est livrée, ressources présentes, empreintes conformes,
émission réelle, absence de la mention d'exemple sur le document produit,
et refus explicite dans les deux cas de dégradation (fond absent, fond
altéré).
"""
import hashlib
import json
import os
import shutil
import tempfile

import fitz
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from apps.documents.startup import run_checks
from apps.documents.templates_registry import load_template

TEMPLATE_ID = "diploma_feba"


def _digest(path):
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


class DiplomaShippedReadyTests(SimpleTestCase):
    """Étapes 1 à 7 — l'installation livrée est complète et cohérente."""

    def setUp(self):
        self.template = load_template(TEMPLATE_ID, use_cache=False)

    def test_1_le_fond_original_est_installe(self):
        self.assertTrue(
            self.template.background_installed,
            f"{self.template.background_file} absent de originals/.",
        )

    def test_2_le_fond_neutralise_est_livre_avec_le_projet(self):
        self.assertTrue(
            os.path.exists(self.template.derived_path),
            "Le fond neutralisé n'est pas livré : le diplôme serait bloqué "
            "dès l'installation, exactement comme avant P7.",
        )

    def test_3_le_gabarit_declare_l_empreinte_du_fond_neutralise(self):
        self.assertTrue(
            self.template.derived_sha256,
            "Sans empreinte déclarée, rien ne distingue un fond neutralisé "
            "correct d'un fichier altéré.",
        )

    def test_4_l_empreinte_du_fond_neutralise_est_conforme(self):
        self.assertEqual(_digest(self.template.derived_path),
                         self.template.derived_sha256)

    def test_5_le_fond_neutralise_est_versionne(self):
        """Le fichier doit être suivi par git, pas seulement présent."""
        import subprocess

        from tests.repo_root import repo_root

        repo = repo_root()

        # FAUX POSITIF SILENCIEUX CORRIGÉ.
        #
        # Le répertoire de travail était calculé par une remontée
        # d'arborescence qui, dans le conteneur, désignait « / » — pas un
        # dépôt git. `git check-ignore` y sortait 128 (« not a git
        # repository »), l'assertion « code de sortie ≠ 0 » était donc
        # satisfaite… sans que rien n'ait été vérifié. Le test passait au
        # vert précisément là où il ne pouvait rien voir.
        if not (repo / ".git").exists():
            # Cas légitime, et SANS RAPPORT avec l'arborescence : une
            # archive livrée ne contient pas .git. La question « ce
            # fichier est-il suivi par git ? » ne se pose alors pas. On
            # vérifie ce qui reste vérifiable : le fond est bien là.
            self.assertTrue(
                os.path.exists(self.template.derived_path),
                "Le fond neutralisé est absent de la livraison.")
            self.skipTest(
                f"{repo} n'est pas un dépôt git (archive extraite) : le "
                "suivi git n'a pas de sens ici. La présence du fond a été "
                "vérifiée à la place.")

        # ON INTERROGE GIT SUR LE CHEMIN RELATIF AU DÉPÔT, pas sur le
        # chemin absolu du conteneur.
        #
        # `derived_path` est absolu sous BASE_DIR — « /app/... » dans le
        # conteneur. Le dépôt, lui, est monté sur « /repo ». Ce sont les
        # mêmes fichiers par deux montages, mais git ne peut pas le
        # savoir : il répondait « is outside repository » (code 128), et
        # l'assertion « code ≠ 0 » s'en satisfaisait. Le test passait au
        # vert sans avoir rien vérifié — exactement le genre de silence
        # que cette livraison corrige.
        from django.conf import settings

        relatif = os.path.relpath(self.template.derived_path, settings.BASE_DIR)
        cible = repo / "backend" / relatif
        self.assertTrue(
            cible.exists(),
            f"Le fond neutralisé est introuvable dans le dépôt : {cible}")

        result = subprocess.run(
            ["git", "check-ignore", str(cible)],
            cwd=repo, capture_output=True, text=True,
        )
        # 0 = ignoré, 1 = suivi, 128 = erreur. Distinguer 1 de 128 est tout
        # l'objet du correctif ci-dessus.
        self.assertIn(
            result.returncode, (0, 1),
            f"git check-ignore n'a pas pu répondre (code "
            f"{result.returncode}) : {result.stderr.strip()}")
        self.assertNotEqual(
            result.returncode, 0,
            "Le fond neutralisé est ignoré par git : il ne partirait pas "
            "dans l'archive, et l'installation arriverait à nouveau sans lui.",
        )

    def test_6_aucun_blocage_a_l_emission(self):
        blockers = self.template.issuance_blockers()
        self.assertEqual(
            blockers, [],
            "Le diplôme est bloqué sur une installation telle que livrée :\n  - "
            + "\n  - ".join(blockers),
        )

    def test_7_aucun_message_ne_demande_de_lancer_une_commande(self):
        """
        Le message reproché ne doit plus pouvoir apparaître.

        Il ne suffit pas qu'il ne s'affiche pas aujourd'hui : le texte
        lui-même ne doit plus exister, sans quoi il reviendra à la première
        installation incomplète.
        """
        from apps.documents import templates_registry

        source = open(templates_registry.__file__, encoding="utf-8").read()
        self.assertNotIn(
            "Lancez : manage.py document_neutralize", source,
            "Le moteur demande encore à l'utilisateur de lancer une commande.",
        )

    def test_8_le_controle_de_demarrage_passe(self):
        results = run_checks(include_render=True)
        failures = [f"{r.name} : {r.detail}" for r in results if not r.ok]
        self.assertEqual(failures, [], "\n".join(failures))


class DiplomaRendersWithoutPlaceholderTests(SimpleTestCase):
    """Étapes 9 et 10 — le document produit ne montre pas la mention d'exemple."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        from apps.documents.renderer import render_document
        from tests.branding_fixtures import make_branding

        cls.template = load_template(TEMPLATE_ID, use_cache=False)
        cls.pdf = render_document(
            TEMPLATE_ID,
            {
                "student_name": "Élisabeth Ahouéfa Gbêdjissi",
                "issue_date": timezone.now().date(),
                "document_number": "FEBA-DIP-2026-0001",
                "director_name": "—",
                "teacher_name": "—",
            },
            branding=make_branding(),
        )

    def test_9_un_pdf_est_reellement_produit(self):
        self.assertTrue(self.pdf.startswith(b"%PDF"))
        self.assertGreater(len(self.pdf), 100_000)

    def test_10_le_rendu_utilise_le_fond_neutralise(self):
        self.assertEqual(self.template.render_background_path,
                         self.template.derived_path)

    def test_11_la_mention_d_exemple_n_apparait_pas(self):
        """
        Contrôle PIXEL, pas textuel.

        « Nom Prénom » est DESSINÉ dans le fond : il n'existe dans aucune
        couche de texte du PDF. Un test qui chercherait la chaîne passerait
        même avec la mention parfaitement visible.

        On mesure donc l'encre dorée dans la bande de la mention, sur le
        fond neutralisé lui-même — celui que le rendu utilise (test 10).
        """
        import numpy as np
        from PIL import Image

        mask = self.template.masks[0]
        scale = self.template.background_height_px / self.template.page_height_mm
        scale_x = self.template.background_width_px / self.template.page_width_mm
        top = int(mask.box.y_mm * scale)
        bottom = int((mask.box.y_mm + mask.box.height_mm) * scale)
        # La mesure est BORNÉE À LA ZONE DE LA MENTION. Prise sur toute la
        # largeur de la page, elle compterait le filet doré de l'encadrement
        # — présent sur les mêmes lignes, et qui doit évidemment rester.
        left = int(mask.box.x_mm * scale_x)
        right = int((mask.box.x_mm + mask.box.width_mm) * scale_x)

        # Les lignes explicitement PRÉSERVÉES sont exclues de la mesure :
        # la règle d'écriture est dorée elle aussi, et elle doit rester.
        # La compter reviendrait à exiger sa disparition.
        preserved = set()
        for keep in mask.preserve:
            preserved.update(range(int(keep.y_mm * scale),
                                   int((keep.y_mm + keep.height_mm) * scale) + 1))
        rows = [y for y in range(top, bottom) if y not in preserved]

        def gold_pixels(path):
            with Image.open(path) as image:
                full = np.asarray(image.convert("RGB"))
            band = full[rows, left:right, :].astype(int)
            red, green, blue = band[:, :, 0], band[:, :, 1], band[:, :, 2]
            return int((((red > 120) & (green > 90) & (blue < 110)
                         & (red - blue > 55) & (green - blue > 30))).sum())

        # L'original PORTE la mention : c'est la mesure de référence, sans
        # laquelle un seuil trop strict passerait pour une neutralisation.
        before = gold_pixels(self.template.background_path)
        after = gold_pixels(self.template.derived_path)

        self.assertGreater(
            before, 1000,
            "La mention d'exemple n'est pas détectée sur l'original : le "
            "critère de mesure est faux, pas le fond.",
        )
        self.assertEqual(
            after, 0,
            f"{after} pixels dorés subsistent dans la bande de la mention "
            f"d'exemple : « Nom Prénom » apparaîtrait sous le vrai nom.",
        )

    def test_12_le_vrai_nom_est_bien_ecrit_sur_le_document(self):
        """La neutralisation n'a pas emporté la zone du nom avec elle."""
        import numpy as np

        document = fitz.open(stream=self.pdf, filetype="pdf")
        page = document[0]
        pixmap = page.get_pixmap(
            matrix=fitz.Matrix(
                self.template.background_width_px / page.rect.width,
                self.template.background_height_px / page.rect.height),
            alpha=False,
        )
        image = np.frombuffer(pixmap.samples, dtype=np.uint8).reshape(
            pixmap.height, pixmap.width, 3,
        )
        mask = self.template.masks[0]
        scale = self.template.background_height_px / self.template.page_height_mm
        scale_x = self.template.background_width_px / self.template.page_width_mm
        band = image[int(mask.box.y_mm * scale):
                     int((mask.box.y_mm + mask.box.height_mm) * scale),
                     int(mask.box.x_mm * scale_x):
                     int((mask.box.x_mm + mask.box.width_mm) * scale_x), :].astype(int)
        red, green, blue = band[:, :, 0], band[:, :, 1], band[:, :, 2]
        written = int((((red > 120) & (green > 90) & (blue < 110)
                        & (red - blue > 55) & (green - blue > 30))).sum())
        self.assertGreater(
            written, 500,
            "Le nom de l'élève n'apparaît pas : la neutralisation a effacé "
            "la zone au lieu de la préparer.",
        )


class DiplomaDegradedInstallTests(SimpleTestCase):
    """Étape 12 — les deux dégradations sont refusées, jamais contournées."""

    def setUp(self):
        self.template = load_template(TEMPLATE_ID, use_cache=False)
        self.backup = tempfile.NamedTemporaryFile(suffix=".png", delete=False).name
        shutil.copy2(self.template.derived_path, self.backup)

    def tearDown(self):
        shutil.copy2(self.backup, self.template.derived_path)
        os.unlink(self.backup)

    def test_fond_neutralise_absent_bloque_l_emission(self):
        os.remove(self.template.derived_path)
        template = load_template(TEMPLATE_ID, use_cache=False)
        blockers = template.issuance_blockers()
        self.assertTrue(blockers)
        self.assertIn("absent de l'installation", " ".join(blockers))
        # Et surtout : on ne retombe PAS sur l'original.
        self.assertEqual(template.render_background_path, template.derived_path)

    def test_fond_neutralise_altere_bloque_l_emission(self):
        with open(self.template.derived_path, "ab") as handle:
            handle.write(b"octets ajoutes")
        template = load_template(TEMPLATE_ID, use_cache=False)
        blockers = template.issuance_blockers()
        self.assertTrue(blockers)
        self.assertIn("ne correspond pas à son empreinte", " ".join(blockers))

    def test_la_regeneration_est_deterministe(self):
        """
        Réparer une installation abîmée rend EXACTEMENT le même fichier.

        C'est ce qui autorise à empreindre le dérivé : si la neutralisation
        variait d'une exécution à l'autre, l'empreinte déclarée ne pourrait
        rien vérifier.
        """
        expected = _digest(self.template.derived_path)
        os.remove(self.template.derived_path)
        call_command("document_neutralize", template=TEMPLATE_ID, verbosity=0)
        self.assertEqual(_digest(self.template.derived_path), expected)


class DiplomaIssuedFromTheInterfaceTests(TestCase):
    """Le parcours complet : un élève, un diplôme émis, un fichier stocké."""

    @classmethod
    def setUpTestData(cls):
        from apps.classes.models import Class
        from apps.schools.models import Level, School, SchoolYear
        from apps.students.models import Student

        cls.school, _ = School.objects.update_or_create(
            code=School.CODE_FEBA,
            defaults=dict(name="Faith & Excellence Bilingual Academy",
                          address="Akpakpa, Cotonou", city="Cotonou",
                          country="Bénin", currency_code="XOF"),
        )
        cls.year, _ = SchoolYear.objects.get_or_create(
            school=cls.school, name="2025-2026",
            defaults=dict(start_date="2025-09-01", end_date="2026-07-31",
                          is_current=True),
        )
        level = Level.objects.create(school=cls.school, name="CM2", order=9)
        klass = Class.objects.create(name="CM2-A", level=level, school_year=cls.year)
        cls.student = Student.objects.create(
            school=cls.school, first_name="Ana", last_name="Ba",
            current_class=klass, school_year=cls.year,
        )

    def test_le_diplome_est_emis_sans_commande_prealable(self):
        from apps.documents.services import create_document, issue_document

        document = create_document(template_id=TEMPLATE_ID, student=self.student)
        issue_document(document)
        document.refresh_from_db()

        self.assertEqual(document.status, "issued")
        self.assertTrue(document.number.startswith("FEBA-DIP-"))
        self.assertTrue(document.file_sha256)
        self.assertGreater(document.file_size, 100_000)
