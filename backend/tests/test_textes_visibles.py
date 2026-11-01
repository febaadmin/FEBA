"""
Textes du backend montrés aux utilisateurs : aucun tiret cadratin. Le contrôle
lui-même est dans scripts/controle_textes.py, avec les modèles, les gabarits et
les fichiers publics. Restent hors contrôle les commandes d'exploitation, les
migrations, les journaux et les commentaires.
"""
import importlib.util
from pathlib import Path

from django.test import SimpleTestCase

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "controle_textes.py"


def controle():
    spec = importlib.util.spec_from_file_location("controle_textes", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TextesVisiblesTests(SimpleTestCase):
    def test_aucune_occurrence_visible(self):
        self.assertEqual(controle().analyser(), [])

    def test_le_controle_repere_un_ecart(self):
        module = controle()
        self.assertIn(module.TIRET, "Paiement \u2014 reçu")
        self.assertTrue(module.SIGNATURES.search("Lorem ipsum"))
        self.assertFalse(module.SIGNATURES.search("Paiement reçu"))
