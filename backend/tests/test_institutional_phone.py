"""
P1 — Le numéro institutionnel imprimé sur les documents officiels.

CE QUE CES TESTS PROUVENT
-------------------------
Un reçu émis en production portait « Tél: 0196697363 ». Le numéro ne
figurait dans aucun fichier source : il venait de `School.phone`, saisi en
base. Un test qui se contenterait de lire le code n'aurait donc rien vu, et
un `grep` sur le dépôt non plus — c'est exactement pour cela que le défaut
a survécu à plusieurs livraisons.

Ces tests GÉNÈRENT DE VRAIS DOCUMENTS, avec une académie dont la base
contient délibérément l'ancien numéro, puis lisent le texte des PDF
produits. C'est la seule preuve qui vaut : elle porte sur ce qui arrive
entre les mains d'une famille, pas sur ce que le code a l'air de faire.

COUVERTURE
----------
  * reçu de paiement            FEBA et FEBA FHA
  * bulletin                    FEBA et FEBA FHA
  * fiche de préinscription     FEBA
  * fiche d'inscription         FEBA FHA
  * certificat et diplôme       FEBA et FEBA FHA
"""
import os
import re

from django.test import TestCase, override_settings

from apps.schools.branding import get_branding
from apps.schools.institution import (
    OFFICIAL_PHONE, RETIRED_INSTITUTIONAL_PHONES, digits, is_retired_phone,
    official_phone, strip_retired_phones,
)
from apps.schools.models import School

RETIRED = RETIRED_INSTITUTIONAL_PHONES[0]


def pdf_text(payload):
    """Texte lisible d'un PDF produit, tel qu'un lecteur l'affiche."""
    import fitz

    document = fitz.open(stream=bytes(payload), filetype="pdf")
    try:
        return " ".join(page.get_text() for page in document)
    finally:
        document.close()


def normalised(text):
    """
    Texte sans césure ni espacement, pour chercher un numéro.

    Un PDF peut couper « 0160011717 » en fragments séparés par des espaces
    de justification. Chercher la chaîne brute laisserait passer un numéro
    pourtant bien présent — et, plus grave, laisserait passer un ancien
    numéro simplement espacé.
    """
    return re.sub(r"[\s.\-/()]", "", text)


# ── Le module d'identité institutionnelle ────────────────────────────────


class InstitutionModuleTests(TestCase):
    """Les garanties du module, indépendamment de tout document."""

    def test_le_numero_officiel_est_celui_de_la_direction(self):
        self.assertEqual(OFFICIAL_PHONE, "0160011717")
        self.assertEqual(official_phone(), "0160011717")

    def test_l_ancien_numero_est_reconnu_meme_reecrit(self):
        # Espacé, pointé, tireté, préfixé de l'indicatif Bénin : c'est le
        # même abonné. Un audit qui ne cherche que la forme compacte
        # déclare propre un document où le numéro est simplement espacé.
        for ecriture in (
            "0196697363", "01 96 69 73 63", "01.96.69.73.63",
            "01-96-69-73-63", "+229 01 96 69 73 63", "0022901966 97363",
        ):
            with self.subTest(ecriture=ecriture):
                self.assertTrue(is_retired_phone(ecriture), ecriture)

    def test_le_numero_officiel_n_est_pas_pris_pour_un_numero_retire(self):
        self.assertFalse(is_retired_phone(OFFICIAL_PHONE))
        self.assertFalse(is_retired_phone("0160011717"))
        self.assertFalse(is_retired_phone("+1 (215) 715-5406"))
        self.assertFalse(is_retired_phone(""))
        self.assertFalse(is_retired_phone(None))

    @override_settings(FEBA_OFFICIAL_PHONE=RETIRED)
    def test_une_configuration_qui_remet_l_ancien_numero_est_refusee(self):
        # Rotation mal renseignée : la variable d'environnement ne doit pas
        # pouvoir remettre en circulation un numéro hors service.
        self.assertEqual(official_phone(), OFFICIAL_PHONE)

    @override_settings(FEBA_OFFICIAL_PHONE="0161020304")
    def test_la_rotation_reste_possible(self):
        # Changer de ligne téléphonique ne doit pas demander de toucher au
        # code : c'est ce qui ferait recopier un numéro en dur ailleurs.
        self.assertEqual(official_phone(), "0161020304")

    def test_le_numero_retire_est_oté_des_champs_libres(self):
        nettoye = strip_retired_phones(
            "Akpakpa, Cotonou, Bénin — Tél: 01 96 69 73 63")
        self.assertNotIn("96697363", normalised(nettoye))
        self.assertIn("Akpakpa", nettoye)
        self.assertIn("Cotonou", nettoye)
        # L'étiquette orpheline ne reste pas derrière le numéro retiré.
        self.assertNotRegex(nettoye, r"(?i)t[ée]l\s*:?\s*$")

    def test_un_champ_libre_sans_numero_retire_est_rendu_intact(self):
        adresse = "Akpakpa, Cotonou, Bénin"
        self.assertEqual(strip_retired_phones(adresse), adresse)
        # Un numéro LÉGITIME dans un champ libre n'est pas emporté.
        avec_officiel = "Cotonou — Tél: 0160011717"
        self.assertEqual(strip_retired_phones(avec_officiel), avec_officiel)

    def test_digits_ignore_la_mise_en_forme(self):
        self.assertEqual(digits("01 60-01.17/17"), "0160011717")


# ── L'identité servie aux générateurs ────────────────────────────────────


class BrandingPhoneTests(TestCase):
    """
    `get_branding()` est le point de passage de TOUS les générateurs.
    Ce qu'il retourne est ce qui s'imprime.
    """

    def setUp(self):
        from django.core.management import call_command
        call_command("init_academies", verbosity=0)

    def _academie(self, code):
        return School.objects.get(code=code)

    def test_le_numero_en_base_ne_decide_plus_de_ce_qui_s_imprime(self):
        for code in (School.CODE_FEBA, School.CODE_FEBA_FHA):
            with self.subTest(code=code):
                academie = self._academie(code)
                # Exactement la situation de production : la colonne
                # contient l'ancien numéro.
                academie.phone = RETIRED
                academie.save(update_fields=["phone"])

                brand = get_branding(academie)
                self.assertEqual(brand.phone, OFFICIAL_PHONE)
                self.assertIn(OFFICIAL_PHONE, brand.address_line)
                self.assertNotIn(
                    digits(RETIRED), normalised(brand.address_line))

    def test_un_numero_retire_recopie_dans_l_adresse_ne_ressort_pas(self):
        academie = self._academie(School.CODE_FEBA)
        academie.address = "Akpakpa, Cotonou, Bénin — Tél 01 96 69 73 63"
        academie.save(update_fields=["address"])

        ligne = get_branding(academie).address_line
        self.assertNotIn(digits(RETIRED), normalised(ligne))
        self.assertIn(OFFICIAL_PHONE, ligne)
        self.assertIn("Akpakpa", ligne)

    def test_les_deux_academies_portent_le_meme_numero(self):
        # C'est la règle : le numéro est celui du GROUPE, pas de l'entité.
        numeros = {
            get_branding(self._academie(code)).phone
            for code in (School.CODE_FEBA, School.CODE_FEBA_FHA)
        }
        self.assertEqual(numeros, {OFFICIAL_PHONE})

    def test_la_commande_d_initialisation_repare_la_colonne_de_gestion(self):
        from django.core.management import call_command

        academie = self._academie(School.CODE_FEBA)
        academie.phone = RETIRED
        academie.save(update_fields=["phone"])

        call_command("init_academies", verbosity=0)

        academie.refresh_from_db()
        # L'écran « Paramètres » ne doit pas continuer d'afficher une ligne
        # qui ne répond plus.
        self.assertEqual(academie.phone, OFFICIAL_PHONE)


# ── Les documents réellement produits ────────────────────────────────────


class DocumentsPortentLeNumeroOfficielTests(TestCase):
    """
    La preuve matérielle : on lit le texte des PDF émis.

    Chaque académie est volontairement placée dans l'état de la base de
    production — ancien numéro dans `phone` ET recopié dans `address` —
    avant de produire le document. Les objets sont créés en base et les
    documents passent par le MÊME chemin que la caisse et le secrétariat :
    un montage en objets factices sauterait précisément la partie qui
    fuyait, la résolution de l'identité depuis l'académie.
    """

    @classmethod
    def setUpTestData(cls):
        from decimal import Decimal

        from django.core.management import call_command

        from apps.accounts.models import CustomUser
        from apps.classes.models import Class, Level
        from apps.payments.models import Payment
        from apps.schools.models import SchoolYear
        from apps.students.models import Student

        call_command("init_academies", verbosity=0)

        cls.paiements = {}
        cls.eleves = {}
        cls.annees = {}
        for code in (School.CODE_FEBA, School.CODE_FEBA_FHA):
            academie = School.objects.get(code=code)
            # ÉTAT EXACT DE LA BASE DE PRODUCTION : l'ancien numéro est
            # dans la colonne, et recopié dans l'adresse libre.
            academie.phone = RETIRED
            academie.address = f"{academie.address} — Tél {RETIRED}"
            academie.save(update_fields=["phone", "address"])

            annee = SchoolYear.objects.create(
                school=academie, name="2025-2026", start_date="2025-09-01",
                end_date="2026-07-31", is_current=True)
            niveau = Level.objects.create(school=academie, name="CM2", order=11)
            classe = Class.objects.create(
                name="CM2-A", level=niveau, school_year=annee)
            eleve = Student.objects.create(
                school=academie, first_name="Élise", last_name="Kponou",
                current_class=classe, school_year=annee)
            caissier = CustomUser.objects.create_user(
                username=f"caisse-{code}", email=f"c{code}@test.bj",
                password="Pass1234!", role="admin", first_name="C",
                last_name="A", school=academie)
            paiement = Payment.objects.create(
                student=eleve, school_year=annee, amount=Decimal("150000"),
                payment_type="tuition", payment_method="cash",
                received_by=caissier)
            cls.paiements[code] = paiement.pk
            cls.eleves[code] = eleve.pk
            cls.annees[code] = annee.pk

    def _verifier(self, texte, contexte, exiger_officiel=True):
        """Le numéro officiel est là ; aucun numéro retiré ne l'est."""
        compact = normalised(texte)
        for retire in RETIRED_INSTITUTIONAL_PHONES:
            self.assertNotIn(
                digits(retire), compact,
                f"{contexte} : le numéro hors service {retire} est encore "
                f"imprimé sur le document.")
        if exiger_officiel:
            self.assertIn(
                digits(OFFICIAL_PHONE), compact,
                f"{contexte} : le numéro institutionnel {OFFICIAL_PHONE} "
                f"est absent du document.")

    # ── Reçus de paiement ────────────────────────────────────────────────

    def _recu(self, code):
        from apps.payments.models import Payment
        from apps.payments.pdf_generator import generate_receipt

        paiement = Payment.objects.get(pk=self.paiements[code])
        generate_receipt(paiement)
        paiement.refresh_from_db()
        return paiement.receipt_file.read()

    def test_recu_de_paiement_feba(self):
        self._verifier(pdf_text(self._recu(School.CODE_FEBA)), "Reçu FEBA")

    def test_recu_de_paiement_feba_fha(self):
        self._verifier(
            pdf_text(self._recu(School.CODE_FEBA_FHA)), "Reçu FEBA FHA")

    # ── Bulletins ────────────────────────────────────────────────────────

    def _bulletin(self, code):
        from apps.bulletins.pdf_generator import generate_bulletin
        from apps.schools.models import SchoolYear
        from apps.students.models import Student

        eleve = Student.objects.get(pk=self.eleves[code])
        annee = SchoolYear.objects.get(pk=self.annees[code])
        # `generate_bulletin` range le PDF et renvoie l'objet Bulletin :
        # on relit le fichier réellement écrit, pas un tampon intermédiaire.
        bulletin = generate_bulletin(eleve, "T1", annee)
        bulletin.pdf_file.open("rb")
        try:
            return bulletin.pdf_file.read()
        finally:
            bulletin.pdf_file.close()

    def test_bulletin_feba(self):
        self._verifier(
            pdf_text(self._bulletin(School.CODE_FEBA)), "Bulletin FEBA")

    def test_bulletin_feba_fha(self):
        self._verifier(
            pdf_text(self._bulletin(School.CODE_FEBA_FHA)),
            "Bulletin FEBA FHA")

    # ── Fiche de préinscription FEBA ─────────────────────────────────────

    def test_fiche_de_preinscription_feba(self):
        from apps.website.feba_prereg_pdf import generate_prereg_sheet
        from apps.website.models import PreRegistration

        demande = PreRegistration.objects.create(
            entity=School.objects.get(code=School.CODE_FEBA),
            parent_name="Awa Ahouandjinou", phone="+229 90 11 22 33",
            email="parent@example.bj", child_name="Liam Ahouandjinou",
            desired_level="CM2",
        )
        self._verifier(
            pdf_text(generate_prereg_sheet(demande)),
            "Fiche de préinscription FEBA")


class DocumentsSansCoordonneesTests(TestCase):
    """
    Certificats et diplômes : AUCUN numéro ne doit y apparaître.

    Ces pièces sont composées sur un fond officiel fourni par
    l'établissement ; le moteur n'y imprime que le nom, la date, le
    signataire et le numéro de pièce. La garantie attendue est donc
    l'ABSENCE de tout numéro hors service — exiger la présence du numéro
    institutionnel y serait faux : ces documents n'en portent pas.
    """

    @classmethod
    def setUpTestData(cls):
        from django.core.management import call_command
        call_command("init_academies", verbosity=0)
        for academie in School.objects.all():
            academie.phone = RETIRED
            academie.save(update_fields=["phone"])

    def _rendre(self, template_id, code):
        from apps.documents.renderer import render_document
        from apps.schools.branding import get_branding

        return render_document(
            template_id,
            {
                "student_name": "Élise Kponou",
                "issue_date": "12/07/2026",
                "signatory_name": "La Direction",
                "director_name": "La Direction",
                "teacher_name": "M. Adjovi",
                "document_number": "FEBA-2026-0001",
            },
            branding=get_branding(School.objects.get(code=code)),
        )

    def test_aucun_numero_hors_service_sur_les_pieces_officielles(self):
        gabarits = (
            ("certificate_feba", School.CODE_FEBA),
            ("certificate_feba_fha", School.CODE_FEBA_FHA),
            ("diploma_feba", School.CODE_FEBA),
            ("diploma_feba_fha", School.CODE_FEBA_FHA),
        )
        for template_id, code in gabarits:
            with self.subTest(gabarit=template_id):
                texte = normalised(pdf_text(self._rendre(template_id, code)))
                for retire in RETIRED_INSTITUTIONAL_PHONES:
                    self.assertNotIn(digits(retire), texte)


class AuditDesGenerateursTests(TestCase):
    """
    Audit de chaîne sur le CODE des générateurs (P12).

    Complément indispensable aux tests de rendu : ceux-ci prouvent que les
    documents produits AUJOURD'HUI sont corrects. Celui-ci refuse qu'un
    numéro institutionnel soit un jour réintroduit en dur dans un
    générateur, y compris dans un chemin de rendu qu'aucun test n'exerce.
    """

    RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    #: Le module d'identité DÉCLARE les numéros retirés : c'est son rôle.
    EXCEPTIONS = {
        os.path.join("apps", "schools", "institution.py"),
    }

    def _fichiers_python(self):
        for racine, dossiers, fichiers in os.walk(
                os.path.join(self.RACINE, "apps")):
            dossiers[:] = [
                d for d in dossiers
                if d not in {"__pycache__", "migrations"}
            ]
            for nom in fichiers:
                if nom.endswith(".py"):
                    yield os.path.join(racine, nom)

    @staticmethod
    def _litteraux(source):
        """
        Chaînes et nombres du CODE EXÉCUTABLE, commentaires et docstrings
        exclus.

        La distinction n'est pas un détail de commodité. Un numéro cité
        dans un commentaire — « un reçu est sorti avec 0196697363 » — est
        la trace écrite du défaut : c'est ce qui empêche la prochaine
        relecture de croire à une valeur arbitraire, et l'effacer pour
        satisfaire un audit reviendrait à effacer la mémoire de l'incident.
        Un numéro dans un littéral, lui, s'imprime. Seul le second est une
        faute.
        """
        import ast

        arbre = ast.parse(source)
        docstrings = set()
        for noeud in ast.walk(arbre):
            if isinstance(noeud, (ast.Module, ast.ClassDef,
                                  ast.FunctionDef, ast.AsyncFunctionDef)):
                corps = getattr(noeud, "body", None) or []
                if (corps and isinstance(corps[0], ast.Expr)
                        and isinstance(corps[0].value, ast.Constant)
                        and isinstance(corps[0].value.value, str)):
                    docstrings.add(id(corps[0].value))

        valeurs = []
        for noeud in ast.walk(arbre):
            if isinstance(noeud, ast.Constant) and id(noeud) not in docstrings:
                if isinstance(noeud.value, (str, int)):
                    valeurs.append(str(noeud.value))
        return valeurs

    def test_aucun_numero_retire_en_dur_dans_le_code_applicatif(self):
        coupables = []
        for chemin in self._fichiers_python():
            relatif = os.path.relpath(chemin, self.RACINE)
            if relatif in self.EXCEPTIONS:
                continue
            with open(chemin, encoding="utf-8") as fichier:
                litteraux = self._litteraux(fichier.read())
            for valeur in litteraux:
                if is_retired_phone(valeur):
                    coupables.append(f"{relatif} → {valeur!r}")
        self.assertEqual(
            coupables, [],
            f"Numéros hors service écrits en dur : {coupables}")

    def test_aucun_numero_institutionnel_en_dur_hors_du_module_d_identite(self):
        # Y compris le BON numéro : recopié dans un générateur, il
        # deviendrait une seconde source d'autorité — et c'est précisément
        # ce mécanisme qui a produit le défaut d'origine.
        coupables = []
        for chemin in self._fichiers_python():
            relatif = os.path.relpath(chemin, self.RACINE)
            if relatif in self.EXCEPTIONS:
                continue
            with open(chemin, encoding="utf-8") as fichier:
                litteraux = self._litteraux(fichier.read())
            for valeur in litteraux:
                if digits(valeur) and digits(valeur) == digits(OFFICIAL_PHONE):
                    coupables.append(f"{relatif} → {valeur!r}")
        self.assertEqual(
            coupables, [],
            "Le numéro institutionnel est recopié en dur dans : "
            f"{coupables}. Il doit être lu depuis "
            "apps.schools.institution.official_phone().")
