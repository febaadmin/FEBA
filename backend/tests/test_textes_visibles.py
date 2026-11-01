"""
Textes du backend montrés aux utilisateurs : pas de tiret cadratin de
ponctuation. Restent hors contrôle les modèles (changer un libellé y créerait
une migration), les commandes d'exploitation et les journaux.
"""
import ast
from pathlib import Path

from django.test import SimpleTestCase

APPS = Path(__file__).resolve().parents[1] / "apps"
EXCLUS = ("migrations", "management", "__pycache__")


def textes(chemin):
    arbre = ast.parse(chemin.read_text(encoding="utf-8"))
    ignores = set()
    for noeud in ast.walk(arbre):
        if isinstance(noeud, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            if noeud.body and isinstance(noeud.body[0], ast.Expr):
                ignores.add(id(noeud.body[0].value))
        if isinstance(noeud, ast.Expr) and isinstance(noeud.value, ast.Constant):
            ignores.add(id(noeud.value))
        if isinstance(noeud, ast.Call) and isinstance(noeud.func, ast.Attribute) and (
                getattr(noeud.func.value, "id", "") == "logger" or noeud.func.attr in ("compile", "sub", "search", "match")):
            ignores.update(id(n) for n in ast.walk(noeud))
    for noeud in ast.walk(arbre):
        if isinstance(noeud, ast.Constant) and isinstance(noeud.value, str) and id(noeud) not in ignores:
            yield noeud.lineno, noeud.value


def non_conforme(texte):
    return "—" in texte and texte.strip() != "—" and "\n" not in texte


class TextesVisiblesTests(SimpleTestCase):
    def test_aucun_tiret_cadratin_de_ponctuation(self):
        ecarts = []
        for chemin in APPS.rglob("*.py"):
            if any(p in chemin.parts for p in EXCLUS) or chemin.name.endswith("models.py"):
                continue
            ecarts += [f"{chemin.relative_to(APPS)}:{l} {t[:60]}" for l, t in textes(chemin) if non_conforme(t)]
        self.assertEqual(ecarts, [])

    def test_le_controle_repere_un_ecart(self):
        self.assertTrue(non_conforme("Paiement — reçu"))
        self.assertFalse(non_conforme("—"))
