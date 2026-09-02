"""
P1 — Aucun document ne porte l'identité d'une autre académie.

POURQUOI CE FICHIER EXISTE SÉPARÉMENT
-------------------------------------
Les tests de cloisonnement existants vérifient qu'un administrateur ne
VOIT pas les données de l'autre académie. Ce n'est pas la même question.
Ici, l'administrateur a parfaitement le droit d'émettre la pièce ; c'est
la PIÈCE qui porte le mauvais nom.

Trois fuites de cette famille ont été trouvées, l'une après l'autre :

  1. `logo_feba.jpeg` — « Faith & Excellence Bilingual Academy » incrusté
     sous le bouclier, en tête de chaque document de l'académie en ligne.
  2. `cachet_feba.png` — « COMPLEXE SCOLAIRE FAITH & EXCELLENCE BILINGUAL
     ACADEMY » en couronne, sur les certificats.
  3. `cachet_secretariat.png` — la même couronne, apposée par
     `payments/pdf_generator.py` sur CHAQUE REÇU DE PAIEMENT.

Les trois ont été trouvées en OUVRANT l'image, jamais en lisant le code,
et aucune n'était visible à l'extraction de texte : le nom est dans une
matrice de pixels. Les tests textuels existants passaient — à juste titre
— pendant que le nom s'affichait en toutes lettres.

CE QUE CE FICHIER CONTRÔLE
--------------------------
  - la RÈGLE : aucune académie ne déclare une image rattachée à une
    autre. Elle vaut aussi pour l'image qu'on ajoutera le mois prochain ;
  - le FAIT : les octets réellement embarqués dans les PDF produits ne
    sont ceux d'aucune image d'une autre académie ;
  - le TEXTE : le nom, la devise et la ville de l'autre académie
    n'apparaissent pas ;
  - l'ABSENCE ASSUMÉE : sans cachet officiel FEBA FHA, aucun cachet n'est
    apposé, aucun n'est inventé, et la production n'est pas bloquée pour
    autant.
"""
import datetime
import hashlib
import io
import os

import fitz
from django.test import SimpleTestCase, TestCase

from apps.documents.renderer import render_document
from apps.documents.templates_registry import load_template
from apps.schools.branding import (
    ACADEMY_BOUND_ASSETS, ACADEMY_DEFAULTS, GROUP_ASSETS, STATIC_FILES_DIR,
    get_branding_by_code,
)
from apps.schools.models import School

#: Champs d'identité qui désignent une image.
CHAMPS_IMAGE = ("document_logo", "stamp", "director_signature",
                "secretary_stamp")

#: Chaînes qui nomment l'école de Cotonou. Aucune ne doit figurer sur un
#: document de l'académie en ligne.
MENTIONS_FEBA = (
    "Faith & Excellence Bilingual Academy",
    "FAITH & EXCELLENCE BILINGUAL ACADEMY",
    "Complexe scolaire",
    "COMPLEXE SCOLAIRE",
    "Akpakpa",
)

#: Et réciproquement.
MENTIONS_FHA = (
    "French Heritage Academy",
    "FRENCH HERITAGE ACADEMY",
)


#: Distance maximale entre deux signatures visuelles pour conclure « c'est
#: la même image ». Mesurée, pas devinée : une même image ré-encodée en
#: JPEG à 70 % donne 2, réduite à 120 px donne 3 ; le cachet du secrétariat
#: et celui de la direction — pourtant de même couronne et de même
#: dimension — donnent 28, et deux images sans rapport dépassent 90.
DISTANCE_MEME_IMAGE = 12


def signature_visuelle(image, taille=16):
    """
    Signature perceptuelle d'une image : 256 bits de gradient horizontal.

    POURQUOI PAS UNE EMPREINTE SHA-256 DU FICHIER. C'est ce que faisait la
    première version de ce contrôle, et il ne contrôlait RIEN : ReportLab
    ré-encode chaque image qu'il embarque, si bien qu'aucune empreinte de
    fichier ne coïncide jamais avec celle du flux extrait du PDF. Le test
    passait aussi bien avec le mauvais cachet qu'avec le bon. Il a fallu
    écrire l'assertion inverse — « le reçu de Cotonou porte BIEN son
    cachet » — pour que le vide apparaisse.
    """
    from PIL import Image as PILImage

    image = image.convert("RGBA")
    fond = PILImage.new("RGBA", image.size, (255, 255, 255, 255))
    gris = PILImage.alpha_composite(fond, image).convert("L").resize(
        (taille + 1, taille), PILImage.LANCZOS)
    pixels = list(gris.getdata())
    return "".join(
        "1" if pixels[y * (taille + 1) + x] > pixels[y * (taille + 1) + x + 1]
        else "0"
        for y in range(taille) for x in range(taille))


def distance(a, b):
    return sum(1 for x, y in zip(a, b) if x != y)


def signature_du_fichier(chemin):
    from PIL import Image as PILImage

    with PILImage.open(chemin) as image:
        return signature_visuelle(image)


def empreinte(chemin):
    with open(chemin, "rb") as fichier:
        return hashlib.sha256(fichier.read()).hexdigest()


class SocleDesAcademies(TestCase):
    """
    Les deux académies, en base.

    `get_branding_by_code` lit une ligne : ces contrôles portent sur
    l'identité RÉSOLUE — livrée puis surchargée par ce que
    l'établissement a administré — et non sur la table des valeurs
    livrées. C'est bien celle-là qui finit sur les documents.
    """

    @classmethod
    def setUpTestData(cls):
        cls.feba, _ = School.objects.update_or_create(
            code=School.CODE_FEBA,
            defaults=dict(
                name="Faith & Excellence Bilingual Academy",
                address="Akpakpa, Cotonou", city="Cotonou", country="Bénin",
                currency_code="XOF", entity_type="campus"))
        cls.fha, _ = School.objects.update_or_create(
            code=School.CODE_FEBA_FHA,
            defaults=dict(
                name="FEBA French Heritage Academy",
                address="Programme 100 % en ligne", city="", country="",
                currency_code="USD", entity_type="online"))


class RegleDesRessourcesTests(SimpleTestCase):
    """La règle, avant les faits : qui a le droit d'utiliser quoi."""

    def test_aucune_academie_ne_declare_l_image_d_une_autre(self):
        for code, identite in ACADEMY_DEFAULTS.items():
            for champ in CHAMPS_IMAGE:
                fichier = identite.get(champ)
                if not fichier:
                    continue
                with self.subTest(academie=code, champ=champ):
                    proprietaire = ACADEMY_BOUND_ASSETS.get(fichier)
                    if proprietaire is None:
                        continue        # ressource neutre du groupe
                    self.assertEqual(
                        proprietaire[0], code,
                        f"« {fichier} » porte le nom de {proprietaire[0]} "
                        f"({proprietaire[1]}) et serait apposé sur un "
                        f"document de {code}.")

    def test_chaque_image_rattachee_porte_la_raison_de_son_rattachement(self):
        # Une entrée sans raison écrite est une interdiction qu'on lèvera
        # dans six mois sans savoir ce qu'elle protégeait.
        for fichier, (proprietaire, raison) in ACADEMY_BOUND_ASSETS.items():
            with self.subTest(fichier=fichier):
                self.assertIn(proprietaire, ACADEMY_DEFAULTS)
                self.assertGreater(len(raison), 30)

    def test_les_images_declarees_existent_ou_valent_none(self):
        for fichier in list(ACADEMY_BOUND_ASSETS) + list(GROUP_ASSETS):
            with self.subTest(fichier=fichier):
                self.assertTrue(
                    os.path.exists(os.path.join(STATIC_FILES_DIR, fichier)),
                    f"{fichier} est déclarée mais absente des ressources.")

class ImagesResoluesTests(SocleDesAcademies):
    def test_les_deux_academies_n_ont_aucune_image_nominative_en_commun(self):
        images = {}
        for code in (School.CODE_FEBA, School.CODE_FEBA_FHA):
            marque = get_branding_by_code(code)
            images[code] = {
                os.path.basename(getattr(marque, champ))
                for champ in CHAMPS_IMAGE if getattr(marque, champ)}
        commun = images[School.CODE_FEBA] & images[School.CODE_FEBA_FHA]
        for fichier in commun:
            with self.subTest(fichier=fichier):
                self.assertIn(
                    fichier, GROUP_ASSETS,
                    f"« {fichier} » est partagée par les deux académies sans "
                    f"figurer parmi les ressources du groupe.")


class CachetAbsentTests(SocleDesAcademies):
    """
    Aucun cachet officiel FEBA FHA n'a été fourni.

    Ce n'est pas un défaut du logiciel, c'est une donnée institutionnelle
    manquante. Ce qui suit décrit exactement ce qui est fait de cette
    absence : rien n'est réutilisé, rien n'est inventé, rien n'est bloqué.
    """

    def test_aucun_cachet_n_est_declare_pour_l_academie_en_ligne(self):
        marque = get_branding_by_code(School.CODE_FEBA_FHA)
        self.assertIsNone(marque.stamp)
        self.assertIsNone(marque.secretary_stamp)

    def test_le_cachet_de_l_autre_academie_n_est_pas_reutilise(self):
        marque = get_branding_by_code(School.CODE_FEBA_FHA)
        cotonou = get_branding_by_code(School.CODE_FEBA)
        self.assertIsNotNone(cotonou.stamp)
        self.assertNotEqual(marque.stamp, cotonou.stamp)
        self.assertNotEqual(marque.secretary_stamp, cotonou.secretary_stamp)

    def test_l_absence_de_cachet_ne_bloque_pas_la_production(self):
        # Un document sans cachet se remet, se voit et se corrige. Refuser
        # de produire priverait l'académie de ses diplômes en attendant un
        # fichier qui ne dépend pas d'elle.
        marque = get_branding_by_code(School.CODE_FEBA_FHA)
        for template_id in ("diploma_feba_fha", "certificate_feba_fha"):
            with self.subTest(gabarit=template_id):
                octets = render_document(
                    template_id,
                    {"student_name": "Élise Kponou",
                     "issue_date": datetime.date(2026, 7, 12),
                     "director_name": "Chris M. Hounsou",
                     "teacher_name": "A. Dossou",
                     "signatory_name": "Chris M. Hounsou",
                     "document_number": "FHA-2026-0001"},
                    branding=marque)
                self.assertTrue(octets.startswith(b"%PDF"))

    def test_la_zone_de_validation_du_recu_reste_en_place_sans_cachet(self):
        # Le reçu de paiement pose le cachet du secrétariat. Sans lui, la
        # zone « Le Secrétariat » et sa mention légale doivent subsister :
        # c'est elle qui porte la signature manuscrite.
        from apps.payments import pdf_generator

        source = pdf_generator.__file__
        with open(source, encoding="utf-8") as fichier:
            code = fichier.read()
        self.assertIn('stamp_cell = ""', code)
        self.assertIn("Le Secrétariat", code)

    def test_le_moteur_n_invente_aucun_cachet(self):
        from apps.documents.renderer import resolve_resource

        marque = get_branding_by_code(School.CODE_FEBA_FHA)
        self.assertIsNone(resolve_resource("seal_official", marque))
        self.assertIsNone(resolve_resource("seal_secretariat", marque))


def _images_embarquees(octets):
    """Signatures visuelles des images réellement présentes dans un PDF."""
    from PIL import Image as PILImage

    document = fitz.open("pdf", octets)
    try:
        signatures = []
        for numero in range(document.page_count):
            for image in document[numero].get_images(full=True):
                brut = document.extract_image(image[0])["image"]
                with PILImage.open(io.BytesIO(brut)) as ouverte:
                    signatures.append(signature_visuelle(ouverte))
        return signatures
    finally:
        document.close()


def _contient(signatures, chemin_image):
    """Cette image est-elle dans le document ?"""
    attendue = signature_du_fichier(chemin_image)
    return any(distance(attendue, vue) <= DISTANCE_MEME_IMAGE
               for vue in signatures)


def _texte(octets):
    document = fitz.open("pdf", octets)
    try:
        return "\n".join(document[n].get_text()
                         for n in range(document.page_count))
    finally:
        document.close()


class DocumentsProduitsTests(SocleDesAcademies):
    """
    Les documents réellement produits, pas les intentions du code.

    Les images sont comparées par le CONTENU, pas par le nom de fichier :
    une copie de `cachet_feba.png` renommée passerait tout contrôle portant
    sur les chemins.
    """

    VALEURS = {
        "student_name": "Élise Kponou",
        "issue_date": datetime.date(2026, 7, 12),
        "director_name": "Chris M. Hounsou",
        "teacher_name": "A. Dossou",
        "signatory_name": "Chris M. Hounsou",
        "document_number": "TEST-2026-0001",
    }

    GABARITS = {
        School.CODE_FEBA: ("diploma_feba", "certificate_feba"),
        School.CODE_FEBA_FHA: ("diploma_feba_fha", "certificate_feba_fha"),
    }

    @staticmethod
    def _images_rattachees_a(code, egal=True):
        """Chemins des images nominatives d'une académie, ou des autres."""
        chemins = []
        for fichier, (proprietaire, _) in ACADEMY_BOUND_ASSETS.items():
            if (proprietaire == code) != egal:
                continue
            chemin = os.path.join(STATIC_FILES_DIR, fichier)
            if os.path.exists(chemin):
                chemins.append(chemin)
        return chemins

    def test_aucun_document_n_embarque_l_image_d_une_autre_academie(self):
        for code, gabarits in self.GABARITS.items():
            marque = get_branding_by_code(code)
            interdites = self._images_rattachees_a(code, egal=False)
            self.assertTrue(interdites or code != School.CODE_FEBA_FHA)
            for template_id in gabarits:
                vues = _images_embarquees(
                    render_document(template_id, self.VALEURS,
                                    branding=marque))
                for chemin in interdites:
                    with self.subTest(academie=code, gabarit=template_id,
                                      image=os.path.basename(chemin)):
                        self.assertFalse(
                            _contient(vues, chemin),
                            f"« {os.path.basename(chemin)} » porte le nom "
                            f"d'une autre académie et figure sur ce document.")

    def test_aucun_document_en_ligne_ne_nomme_l_ecole_de_cotonou(self):
        marque = get_branding_by_code(School.CODE_FEBA_FHA)
        for template_id in self.GABARITS[School.CODE_FEBA_FHA]:
            octets = render_document(template_id, self.VALEURS,
                                     branding=marque)
            texte = _texte(octets)
            for mention in MENTIONS_FEBA:
                with self.subTest(gabarit=template_id, mention=mention):
                    self.assertNotIn(mention, texte)

    def test_aucun_document_de_cotonou_ne_nomme_l_academie_en_ligne(self):
        marque = get_branding_by_code(School.CODE_FEBA)
        for template_id in self.GABARITS[School.CODE_FEBA]:
            octets = render_document(template_id, self.VALEURS,
                                     branding=marque)
            texte = _texte(octets)
            for mention in MENTIONS_FHA:
                with self.subTest(gabarit=template_id, mention=mention):
                    self.assertNotIn(mention, texte)

    def test_chaque_gabarit_dessine_le_fond_de_son_academie(self):
        # Le nom de l'académie est dans le FOND, en pixels. Le contrôle
        # porte donc sur l'empreinte du fond effectivement dessiné.
        fonds = {}
        for code, gabarits in self.GABARITS.items():
            for template_id in gabarits:
                gabarit = load_template(template_id)
                fonds.setdefault(code, set()).add(
                    empreinte(gabarit.render_background_path))
        self.assertFalse(fonds[School.CODE_FEBA]
                         & fonds[School.CODE_FEBA_FHA])

    def test_un_gabarit_ne_s_ouvre_pas_a_l_autre_academie(self):
        for code, gabarits in self.GABARITS.items():
            autre = (School.CODE_FEBA_FHA if code == School.CODE_FEBA
                     else School.CODE_FEBA)
            for template_id in gabarits:
                with self.subTest(gabarit=template_id):
                    self.assertNotIn(autre,
                                     load_template(template_id).academies)


class RecuDePaiementTests(TestCase):
    """
    Le reçu, parce que c'est lui qui portait la troisième fuite.

    Le cachet du secrétariat n'apparaissait sur aucun diplôme ; il est
    apposé sur CHAQUE reçu. Un contrôle qui ne regardait que les documents
    officiels ne pouvait pas le voir — et n'a rien vu pendant deux
    itérations.

    Le reçu est produit ici pour de bon, en base, par le même chemin que
    celui de la caisse. Un montage en objets factices aurait sauté
    précisément la partie qui fuyait : la résolution de l'identité depuis
    l'académie du paiement.
    """

    @classmethod
    def setUpTestData(cls):
        from decimal import Decimal

        from apps.accounts.models import CustomUser
        from apps.classes.models import Class, Level
        from apps.payments.models import Payment
        from apps.schools.models import SchoolYear
        from apps.students.models import Student

        cls.recus = {}
        for code, nom, devise in (
            (School.CODE_FEBA, "Faith & Excellence Bilingual Academy", "XOF"),
            (School.CODE_FEBA_FHA, "FEBA French Heritage Academy", "USD"),
        ):
            ecole, _ = School.objects.update_or_create(
                code=code, defaults=dict(name=nom, currency_code=devise))
            annee = SchoolYear.objects.create(
                school=ecole, name="2025-2026", start_date="2025-09-01",
                end_date="2026-07-31", is_current=True)
            niveau = Level.objects.create(school=ecole, name="CM2", order=11)
            classe = Class.objects.create(name="CM2-A", level=niveau,
                                          school_year=annee)
            eleve = Student.objects.create(
                school=ecole, first_name="Élise", last_name="Kponou",
                current_class=classe, school_year=annee)
            caissier = CustomUser.objects.create_user(
                username=f"caisse-{code}", email=f"c{code}@test.bj",
                password="Pass1234!", role="admin", first_name="C",
                last_name="A", school=ecole)
            paiement = Payment.objects.create(
                student=eleve, school_year=annee, amount=Decimal("150000"),
                payment_type="tuition", payment_method="cash",
                received_by=caissier)
            cls.recus[code] = paiement.pk

    def _recu(self, code):
        from apps.payments.models import Payment
        from apps.payments.pdf_generator import generate_receipt

        paiement = Payment.objects.get(pk=self.recus[code])
        generate_receipt(paiement)
        paiement.refresh_from_db()
        return paiement.receipt_file.read()

    def test_le_recu_en_ligne_ne_porte_aucun_cachet_de_cotonou(self):
        vues = _images_embarquees(self._recu(School.CODE_FEBA_FHA))
        for fichier, (proprietaire, _) in ACADEMY_BOUND_ASSETS.items():
            chemin = os.path.join(STATIC_FILES_DIR, fichier)
            if proprietaire != School.CODE_FEBA or not os.path.exists(chemin):
                continue
            with self.subTest(image=fichier):
                self.assertFalse(
                    _contient(vues, chemin),
                    f"le reçu de l'académie en ligne porte « {fichier} »")

    def test_le_recu_de_cotonou_porte_bien_son_cachet(self):
        # Le contraire du test précédent, et il compte autant : retirer le
        # cachet des deux académies ferait passer l'autre contrôle sans
        # rien régler.
        vues = _images_embarquees(self._recu(School.CODE_FEBA))
        self.assertTrue(_contient(
            vues, os.path.join(STATIC_FILES_DIR, "cachet_secretariat.png")))

    def test_le_recu_en_ligne_ne_nomme_pas_l_ecole_de_cotonou(self):
        texte = _texte(self._recu(School.CODE_FEBA_FHA))
        for mention in MENTIONS_FEBA:
            with self.subTest(mention=mention):
                self.assertNotIn(mention, texte)

    def test_la_zone_le_secretariat_subsiste_sans_cachet(self):
        # L'absence de cachet ne fait pas disparaître la zone : c'est elle
        # qui porte la signature manuscrite et la mention légale.
        texte = " ".join(_texte(self._recu(School.CODE_FEBA_FHA)).split())
        self.assertIn("Le Secrétariat", texte)
        self.assertIn("valoir ce que de droit", texte)


class LimitationDocumenteeTests(SimpleTestCase):
    """
    L'absence de cachet FEBA FHA est une donnée institutionnelle manquante,
    pas un défaut logiciel. Elle doit donc être ÉCRITE, dans les termes
    convenus, et le rester.

    Un test sur un fichier de documentation peut sembler excessif. Il ne
    l'est pas ici : cette phrase est la seule chose qui distingue « nous
    n'avons pas reçu le cachet » de « nous avons oublié le cachet ». Sans
    elle, la prochaine relecture conclura au second.
    """

    #: Formulation retenue, mot pour mot.
    PHRASE = ("Aucun cachet officiel FEBA FHA n'a été fourni ; aucun cachet "
              "d'une autre académie n'est réutilisé.")

    @staticmethod
    def _chemin_limitations():
        """
        Retrouve KNOWN_LIMITATIONS.md, quel que soit l'endroit d'exécution.

        Le fichier vit à la racine du dépôt. Mais les tests tournent aussi
        DANS le conteneur backend, où seul `./backend` est monté (sur
        /app) : la racine du dépôt n'y existe pas. Une livraison
        précédente avait résolu le problème en dupliquant le fichier dans
        `backend/` — deux copies d'un document dont tout l'intérêt est
        d'être la référence unique, et qui ont aussitôt divergé.

        On remonte donc l'arborescence jusqu'à le trouver.
        docker-compose.yml monte le fichier de la racine dans le
        conteneur, ce qui rend cette recherche fructueuse des deux côtés.
        """
        dossier = os.path.dirname(os.path.abspath(__file__))
        while True:
            candidat = os.path.join(dossier, "KNOWN_LIMITATIONS.md")
            if os.path.exists(candidat):
                return candidat
            parent = os.path.dirname(dossier)
            if parent == dossier:
                return None
            dossier = parent

    def _limitations(self):
        chemin = self._chemin_limitations()
        self.assertIsNotNone(
            chemin,
            "KNOWN_LIMITATIONS.md est introuvable en remontant depuis "
            f"{os.path.dirname(os.path.abspath(__file__))}. Dans le "
            "conteneur backend, il est monté par docker-compose.yml.")
        with open(chemin, encoding="utf-8") as fichier:
            return fichier.read()

    def test_l_absence_de_cachet_est_documentee_dans_les_termes_convenus(self):
        texte = self._limitations().replace("**", "")
        # Les retours à la ligne de la mise en forme ne comptent pas.
        aplati = " ".join(texte.split())
        self.assertIn(self.PHRASE, aplati)

    def test_le_nom_sur_deux_lignes_n_est_plus_une_limitation(self):
        # Il l'était dans les livraisons précédentes. Le laisser inscrit
        # ferait renoncer quelqu'un à un service qui fonctionne.
        aplati = " ".join(self._limitations().replace("**", "").split())
        self.assertIn("est levée", aplati)
        self.assertIn("79 caractères est composé sur deux lignes", aplati)
