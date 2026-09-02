"""
P0 — L'identité des documents vient d'une source unique, par académie.

Deux familles de tests :

1. Un contrôle STATIQUE du code source. Il refuse la réapparition d'un nom
   d'académie, d'une adresse, d'une devise, d'une couleur ou d'un chemin de
   cachet écrits en dur dans un générateur de document. Ce contrôle existe
   parce que la régression est invisible autrement : un reçu portant le nom
   de l'autre académie s'imprime, se signe et se remet sans que rien ne
   signale l'erreur.

2. Des contrôles FONCTIONNELS : deux académies, deux jeux de documents, et
   aucun élément de l'une n'apparaît sur ceux de l'autre.
"""
import os
import re
from datetime import date
from io import BytesIO

import fitz
from django.test import SimpleTestCase, TestCase

from apps.schools.branding import (
    ACADEMY_DEFAULTS, BrandingUnavailable, branding_for, get_branding,
    resolve_academy,
)
from apps.schools.institution import official_phone
from apps.schools.models import School

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

#: Générateurs de documents soumis au contrôle statique.
GENERATORS = [
    "apps/payments/pdf_generator.py",
    "apps/bulletins/pdf_generator.py",
    "apps/documents/renderer.py",
    "apps/documents/services.py",
    "apps/website/fha_pdf.py",
]

#: Chaînes qui désignent UNE académie précise. Aucune n'a sa place dans un
#: générateur : elles doivent venir de `get_branding(academy)`.
FORBIDDEN = [
    (r"Faith\s*&(?:amp;)?\s*Excellence", "nom d'académie"),
    (r"FAITH\s*&(?:amp;)?\s*EXCELLENCE", "nom d'académie"),
    (r"French Heritage Academy", "nom d'académie"),
    (r"\bFCFA\b", "devise"),
    (r"\bCotonou\b", "ville"),
    (r"\bAkpakpa\b", "adresse"),
    (r"\bBénin\b", "pays"),
    (r"GROUPE ÉDUCATIF", "nom de groupe"),
    (r"logo_feba", "logo"),
    (r"cachet_feba", "cachet"),
    (r"cachet_secretariat", "cachet"),
    (r"#1E3A6E|#C9A227|#EEF3FF|#071D49|#D89B16|#F7F2E8",
     "couleur institutionnelle"),
]


def _code_lines(path):
    """Lignes de code du fichier, commentaires et docstrings exclus.

    Un commentaire qui EXPLIQUE le défaut corrigé — « `Cotonou` codé en dur
    apparaissait sur les reçus FHA » — est une documentation utile, pas une
    régression. Seul le code exécuté est contrôlé.
    """
    import ast
    import io
    import tokenize

    source = open(path, encoding="utf-8").read()
    tree = ast.parse(source)

    # Lignes occupées par une docstring de module, classe ou fonction.
    doc_lines = set()
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef,
                                 ast.AsyncFunctionDef)):
            continue
        body = getattr(node, "body", None)
        if not body:
            continue
        first = body[0]
        if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) \
                and isinstance(first.value.value, str):
            doc_lines.update(range(first.lineno, (first.end_lineno or first.lineno) + 1))

    comment_lines = set()
    for token in tokenize.generate_tokens(io.StringIO(source).readline):
        if token.type == tokenize.COMMENT:
            comment_lines.add(token.start[0])

    return [
        (number, text)
        for number, text in enumerate(source.splitlines(), start=1)
        if number not in doc_lines and number not in comment_lines
    ]


class NoHardcodedIdentityTests(SimpleTestCase):
    """Aucun générateur ne connaît le nom, la couleur ou le cachet d'une académie."""

    def test_generateurs_sans_identite_en_dur(self):
        offences = []
        for relative in GENERATORS:
            path = os.path.join(BACKEND_DIR, relative)
            if not os.path.exists(path):
                continue
            for number, text in _code_lines(path):
                for pattern, kind in FORBIDDEN:
                    if re.search(pattern, text):
                        offences.append(f"{relative}:{number} — {kind} : {text.strip()}")

        self.assertEqual(
            offences, [],
            "Identité d'académie codée en dur dans un générateur de document. "
            "Ces valeurs doivent venir de get_branding(academy) :\n  "
            + "\n  ".join(offences),
        )

    def test_le_module_de_branding_est_la_seule_source(self):
        """
        Chaque générateur consulte l'identité, ou la reçoit explicitement.

        `renderer.py` est le seul à ne pas la résoudre lui-même : c'est un
        moteur de rendu, il reçoit `branding` en paramètre. Sans lui, il
        n'appose ni cachet ni signature — jamais ceux d'une autre académie.
        """
        for relative in GENERATORS:
            path = os.path.join(BACKEND_DIR, relative)
            if not os.path.exists(path):
                continue
            source = open(path, encoding="utf-8").read()
            with self.subTest(fichier=relative):
                self.assertTrue(
                    "apps.schools.branding" in source or "branding" in source,
                    f"{relative} produit des documents sans consulter "
                    f"l'identité de l'académie.",
                )


class BrandingResolutionTests(TestCase):
    """L'identité résolue est bien celle de l'académie demandée."""

    @classmethod
    def setUpTestData(cls):
        # Les deux académies existent déjà : elles sont créées par les
        # migrations. On les récupère par leur CODE INTERNE STABLE.
        cls.feba, _ = School.objects.update_or_create(
            code=School.CODE_FEBA,
            defaults=dict(
                name="Faith & Excellence Bilingual Academy",
                address="Akpakpa, Cotonou", city="Cotonou", country="Bénin",
                currency_code="XOF", entity_type="campus",
            ),
        )
        cls.fha, _ = School.objects.update_or_create(
            code=School.CODE_FEBA_FHA,
            defaults=dict(
                name="FEBA French Heritage Academy",
                address="Programme 100 % en ligne", city="", country="",
                currency_code="USD", entity_type="online",
            ),
        )

    def test_chaque_academie_a_sa_devise(self):
        self.assertEqual(get_branding(self.feba).currency_code, "XOF")
        self.assertEqual(get_branding(self.fha).currency_code, "USD")
        self.assertEqual(get_branding(self.feba).currency_symbol, "FCFA")
        self.assertEqual(get_branding(self.fha).currency_symbol, "$")

    def test_chaque_academie_a_son_prefixe_documentaire(self):
        self.assertEqual(get_branding(self.feba).document_prefix, "FEBA")
        self.assertEqual(get_branding(self.fha).document_prefix, "FHA")

    def test_les_deux_academies_ne_partagent_pas_la_couleur_secondaire(self):
        self.assertNotEqual(
            get_branding(self.feba).secondary_color,
            get_branding(self.fha).secondary_color,
        )

    def test_l_adresse_de_l_une_n_apparait_pas_chez_l_autre(self):
        self.assertNotIn("Cotonou", get_branding(self.fha).address_line)
        self.assertIn("Cotonou", get_branding(self.feba).address_line)

    def test_reglage_administre_prioritaire_sur_la_valeur_livree(self):
        self.fha.settings = {"branding": {"primary_color": "#123456"}}
        self.fha.save(update_fields=["settings"])
        self.assertEqual(get_branding(self.fha).primary_color, "#123456")
        # Les autres clés livrées restent en place.
        self.assertEqual(
            get_branding(self.fha).document_prefix,
            ACADEMY_DEFAULTS["FEBA_FHA"]["document_prefix"],
        )

    def test_academie_inconnue_refusee(self):
        with self.assertRaises(BrandingUnavailable):
            get_branding(None)

    def test_academie_sans_code_reste_neutre_sans_image_inventee(self):
        autre = School.objects.create(
            name="École partenaire", address="—", currency_code="XOF",
        )
        branding = get_branding(autre)
        self.assertTrue(branding.palette_is_neutral)
        self.assertIsNone(branding.stamp)
        self.assertIsNone(branding.director_signature)

    def test_aucun_repli_vers_la_premiere_academie(self):
        """Un objet sans académie ne prend pas celle d'un autre."""
        class Orphelin:
            pass

        self.assertIsNone(resolve_academy(Orphelin()))
        with self.assertRaises(BrandingUnavailable):
            branding_for(Orphelin())


class DocumentsPortentLeurAcademieTests(TestCase):
    """Deux académies, deux reçus : aucun élément ne traverse."""

    def _receipt_text(self, academy_code, name, currency):
        from apps.classes.models import Class
        from apps.payments.models import Payment
        from apps.payments.pdf_generator import generate_receipt
        from apps.schools.models import Level, SchoolYear
        from apps.students.models import Student

        school, _ = School.objects.update_or_create(
            code=academy_code,
            defaults=dict(
                name=name, address="Adresse " + academy_code,
                city="Ville " + academy_code, country="Pays " + academy_code,
                currency_code=currency,
            ),
        )
        year, _ = SchoolYear.objects.get_or_create(
            school=school, name="2025-2026",
            defaults=dict(start_date=date(2025, 9, 1), end_date=date(2026, 7, 31),
                          is_current=True),
        )
        level = Level.objects.create(school=school, name="N1", order=1)
        klass = Class.objects.create(name="C1", level=level, school_year=year)
        student = Student.objects.create(
            school=school, first_name="Ana", last_name="Ba",
            current_class=klass, school_year=year,
        )
        payment = Payment.objects.create(
            student=student, school_year=year, amount="100.00",
            payment_type="inscription", payment_method="cash",
            payment_date=date(2025, 9, 15),
        )
        generate_receipt(payment)
        payment.refresh_from_db()
        with payment.receipt_file.open("rb") as handle:
            data = handle.read()
        doc = fitz.open(stream=BytesIO(data).getvalue(), filetype="pdf")
        return "\n".join(page.get_text() for page in doc)

    def test_le_recu_de_chaque_academie_ne_nomme_que_la_sienne(self):
        feba_text = self._receipt_text(
            School.CODE_FEBA, "Faith & Excellence Bilingual Academy", "XOF",
        )
        fha_text = self._receipt_text(
            School.CODE_FEBA_FHA, "FEBA French Heritage Academy", "USD",
        )

        self.assertIn("Faith & Excellence Bilingual Academy", feba_text)
        self.assertNotIn("French Heritage", feba_text)

        self.assertIn("FEBA French Heritage Academy", fha_text)
        self.assertNotIn("Faith & Excellence", fha_text)

    def test_la_devise_du_recu_est_celle_de_l_academie(self):
        feba_text = self._receipt_text(
            School.CODE_FEBA, "Faith & Excellence Bilingual Academy", "XOF",
        )
        fha_text = self._receipt_text(
            School.CODE_FEBA_FHA, "FEBA French Heritage Academy", "USD",
        )
        self.assertIn("FCFA", feba_text)
        self.assertNotIn("FCFA", fha_text)
        self.assertIn("$", fha_text)

    def test_la_ville_du_recu_est_celle_de_l_academie(self):
        feba_text = self._receipt_text(
            School.CODE_FEBA, "Faith & Excellence Bilingual Academy", "XOF",
        )
        self.assertIn("Ville FEBA", feba_text)
        self.assertNotIn("Ville FEBA_FHA", feba_text)


class AddressLineTests(TestCase):
    """
    L'adresse imprimée ne répète pas ce qu'elle contient déjà.

    Défaut trouvé en inspectant les documents produits depuis l'archive :
    l'en-tête affichait « Akpakpa, Cotonou, Bénin, Cotonou, Bénin ».
    `School.address` est un champ libre et contient le plus souvent déjà la
    ville et le pays ; les recoller sans regarder les imprimait deux fois.

    Pour l'académie en ligne, c'était pire : une ville qui n'est pas la
    sienne apparaissait deux fois sur ses reçus.
    """

    def _branding(self, **fields):
        academy = School(
            name="Académie de test", code=None, currency_code="XOF", **fields,
        )
        return get_branding(academy)

    #: Le numéro institutionnel est désormais TOUJOURS présent sur la ligne
    #: d'identité, quelle que soit l'académie (voir
    #: apps/schools/institution.py). Ces tests portent sur la COMPOSITION de
    #: l'adresse — ville non répétée, point final retiré, aucun séparateur
    #: orphelin — pas sur le numéro : ils l'isolent donc pour continuer à
    #: vérifier exactement ce qu'ils vérifiaient avant.
    def _lieu(self, line):
        """Partie « adresse » de la ligne, sans le bloc téléphone/e-mail."""
        return line.split(" | Tél:")[0]

    def test_la_ville_deja_dans_l_adresse_n_est_pas_repetee(self):
        line = self._branding(
            address="Akpakpa, Cotonou, Bénin", city="Cotonou", country="Bénin",
        ).address_line
        self.assertEqual(self._lieu(line), "Akpakpa, Cotonou, Bénin")
        self.assertEqual(line.lower().count("cotonou"), 1)
        self.assertEqual(line.lower().count("bénin"), 1)

    def test_la_ville_absente_de_l_adresse_est_ajoutee(self):
        line = self._branding(
            address="12 rue des Cocotiers", city="Cotonou", country="Bénin",
        ).address_line
        self.assertEqual(self._lieu(line), "12 rue des Cocotiers, Cotonou, Bénin")

    def test_le_point_final_d_une_adresse_libre_est_retire(self):
        line = self._branding(
            address="Programme 100 % en ligne — depuis Cotonou, Bénin.",
            city="Cotonou", country="Bénin", phone="+229 97 00 00 00",
        ).address_line
        self.assertNotIn("Bénin. |", line)
        # Le numéro imprimé est celui du GROUPE, pas celui saisi sur
        # l'entité : c'est la règle posée par le correctif P1.
        self.assertIn(f"| Tél: {official_phone()}", line)
        self.assertNotIn("+229 97 00 00 00", line)
        self.assertEqual(line.lower().count("cotonou"), 1)

    def test_une_academie_sans_adresse_n_imprime_pas_de_separateur_vide(self):
        line = self._branding(address="", city="", country="",
                              email="contact@exemple.test").address_line
        self.assertEqual(line, f"Tél: {official_phone()} | contact@exemple.test")
        # Le vrai objet du test : aucun séparateur orphelin, ni en tête, ni
        # doublé, ni en fin de ligne.
        self.assertFalse(line.startswith("|"))
        self.assertFalse(line.endswith("|"))
        self.assertNotIn("|  |", line)
        self.assertNotIn(" |  ", line)
