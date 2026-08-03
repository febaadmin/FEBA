"""
P0 — Un texte long est rendu INTÉGRALEMENT, dans son cadre, ou pas du tout.

LE DÉFAUT REPRODUIT
-------------------
La fiche d'inscription FEBA FHA se construit avec un tableau à deux
colonnes. ReportLab ne coupe jamais une ligne de tableau entre deux
pages : quand une seule cellule dépassait la hauteur utile d'une page, la
mise en page n'était pas laide, elle **échouait** —

    LayoutError: Flowable <Table 5 rows x 2 cols (tallest row 905)>
    ... tallest cell 905.1 points, too large on page 2

Un parent qui écrivait un message de 5 000 caractères rendait donc la
fiche PDF impossible à produire. Comme l'appel était enveloppé dans un
`try/except`, l'écran n'affichait rien : la demande était enregistrée et
la fiche officielle n'existait pas.

Ces tests soumettent le jeu d'essai exact du cahier des charges :
message de 5 000 caractères, URL très longue, mot de 300 caractères,
plusieurs paragraphes, retours à la ligne, accents, « & < > », et du texte
qui ressemble à du HTML.
"""
import re

import fitz  # PyMuPDF
import pytest
from reportlab.lib.units import cm

from apps.core.pdf_longtext import (
    MIN_READABLE_FONT_SIZE, normalize, pdf_paragraph,
)

# ── Le jeu d'essai ───────────────────────────────────────────────────────

MOT_300 = "M" + "o" * 298 + "T"
URL_LONGUE = (
    "https://feba-academy.example.org/dossiers/inscription/2026/"
    + "segment-tres-long-" * 12
    + "?token=" + "a" * 120
)
MESSAGE_5000 = (
    "Bonjour,\n\n"
    "Notre fille a besoin d'un accompagnement <renforcé> en lecture & en "
    "écriture.\n"
    + "Détail pédagogique. " * 260
    + "\n\nCordialement,\nFamille Adjovi-Bokô"
)
TEXTE_HTML = "<script>alert('x')</script><b>gras</b> & <i>italique</i>"
ACCENTS = "Élève à Cotonou — coût « 25 000 F CFA » ; prénom : Kofí Ọ̀ṣun"

JEU_D_ESSAI = [
    ("message_5000", MESSAGE_5000),
    ("mot_300", MOT_300),
    ("url_longue", URL_LONGUE),
    ("accents", ACCENTS),
    ("entites", "a & b < c > d"),
    ("html", TEXTE_HTML),
    ("paragraphes", "Un.\n\nDeux.\n\nTrois.\n\nQuatre."),
]


def sans_coupures(text):
    """
    Le texte extrait d'un PDF tel qu'un lecteur le copierait.

    Aucun caractère n'est retiré : la fonction existe pour dire
    explicitement qu'il n'y a RIEN à retirer. Une première version de la
    correction semait des espaces de largeur nulle (U+200B) dans les mots
    trop longs ; mesuré sur le document, ReportLab imprimait le caractère
    de remplacement de la police et le mot ressortait ainsi :

        MoooooooooooooooooooIooooooooooooooooooooIooooooooooooo…

    Un « I » parasite tous les vingt caractères sur une pièce officielle.
    La correction a été retirée au profit du `splitLongWords` natif de
    ReportLab, et ces tests mesurent désormais le dépassement réel.
    """
    return text


def texte_du_pdf(content):
    document = fitz.open(stream=content, filetype="pdf")
    try:
        return "".join(page.get_text() for page in document), document.page_count
    finally:
        document.close()


# ── Le module partagé ────────────────────────────────────────────────────


class TestModulePartage:

    def test_les_entites_xml_sont_echappees(self):
        """
        ReportLab lit un paragraphe comme du mini-XML. Sans échappement,
        « a & b » lève une erreur d'analyse et « <plus de 3 ans> »
        disparaît silencieusement — le fragment le plus important du
        message est celui qui s'efface.
        """
        para = pdf_paragraph("a & b < c > d")
        assert "&amp;" in para.text
        assert "&lt;" in para.text and "&gt;" in para.text

    def test_le_texte_ressemblant_a_du_html_reste_litteral(self):
        para = pdf_paragraph(TEXTE_HTML)
        # Aucune balise <script> ou <b> réelle : tout est échappé.
        assert "<script>" not in para.text
        assert "&lt;script&gt;" in para.text
        assert "&lt;b&gt;" in para.text

    def test_les_retours_a_la_ligne_deviennent_des_sauts_reels(self):
        para = pdf_paragraph("Un.\nDeux.\r\nTrois.\rQuatre.")
        assert para.text.count("<br/>") == 3

    def test_les_br_poses_ne_sont_pas_echappes_a_leur_tour(self):
        """
        L'ordre compte : échapper APRÈS avoir posé les `<br/>` les
        transformerait en `&lt;br/&gt;` visibles à l'écran.
        """
        para = pdf_paragraph("Un.\nDeux.")
        assert "&lt;br/&gt;" not in para.text

    def test_le_mot_long_traverse_le_paragraphe_sans_alteration(self):
        """
        Aucun caractère ajouté, aucun retiré. La coupure d'un mot trop
        large est faite par ReportLab AU MOMENT DU RENDU, sans toucher au
        contenu — c'est ce qui permet de le recopier depuis le PDF.
        """
        rendu = pdf_paragraph(MOT_300).text
        assert MOT_300 in rendu
        assert len(re.search(r"Mo+T", rendu).group(0)) == 300

    def test_aucun_caractere_invisible_n_est_injecte(self):
        """
        Test de non-régression d'une correction ÉCARTÉE : semer des U+200B
        pour forcer le repli imprimait un « I » parasite tous les vingt
        caractères, les polices de base d'un PDF n'ayant pas de glyphe
        pour ce caractère.
        """
        for _, valeur in JEU_D_ESSAI:
            rendu = pdf_paragraph(valeur).text
            for invisible in ("\u200b", "\u00ad", "\ufeff", "\u2060"):
                assert invisible not in rendu, (
                    f"caractère invisible {invisible!r} injecté dans le PDF"
                )

    def test_la_coupure_des_mots_longs_reste_active(self):
        """
        `splitLongWords` est ce qui empêche une URL de sortir de la page.
        Un style hérité peut l'éteindre sans qu'aucune erreur ne soit
        levée : le symptôme serait alors un texte hors cadre, muet.
        """
        assert pdf_paragraph(URL_LONGUE).style.splitLongWords == 1

    def test_une_police_illisible_est_refusee(self):
        """
        Faire tenir un texte long en le rapetissant n'est pas de la mise en
        page : c'est de la dissimulation. Le texte est là, personne ne peut
        le lire, et le document passe pour complet.
        """
        with pytest.raises(ValueError, match="lisible"):
            pdf_paragraph("texte", fontSize=MIN_READABLE_FONT_SIZE - 0.5)

    def test_la_police_minimale_reste_acceptee(self):
        assert pdf_paragraph("texte", fontSize=MIN_READABLE_FONT_SIZE) is not None

    def test_normalize_supprime_les_caracteres_invisibles(self):
        assert normalize("a b") == "a b"
        assert normalize("a﻿b") == "ab"
        assert normalize(None) == ""

    def test_normalize_uniformise_les_fins_de_ligne(self):
        assert normalize("a\r\nb\rc") == "a\nb\nc"

    def test_aucun_repli_ne_perd_de_caractere_significatif(self):
        for nom, valeur in JEU_D_ESSAI:
            rendu = sans_coupures(pdf_paragraph(valeur).text)
            # On recompose le texte source tel que ReportLab l'a reçu.
            attendu = normalize(valeur)
            visible = (
                rendu.replace("<br/>", "\n")
                .replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
            )
            assert visible == attendu, f"texte altéré pour le cas {nom}"


# ── La fiche d'inscription FEBA FHA ──────────────────────────────────────


@pytest.mark.django_db
class TestFichePdfFha:
    """La reproduction du défaut, puis sa disparition, sur le document réel."""

    @pytest.fixture
    def application(self):
        from datetime import date

        from apps.schools.models import School
        from apps.website.models import FHAEnrollmentApplication

        entity, _ = School.objects.update_or_create(
            code=School.CODE_FEBA_FHA,
            defaults=dict(name="FEBA French Heritage Academy",
                          address="Programme en ligne", entity_type="online",
                          currency_code="USD"),
        )
        return FHAEnrollmentApplication.objects.create(
            entity=entity,
            child_first_name="Amélie", child_last_name="Adjovi-Bokô",
            child_birth_date=date(2015, 4, 12),
            parent1_first_name="Chris", parent1_last_name="Adjovi",
            parent1_email="chris@example.org", parent1_phone="+229 01 02 03 04",
            # Chaque champ libre du modèle reçoit une valeur du jeu d'essai :
            # c'est la seule façon de vérifier qu'AUCUN d'eux ne casse la
            # mise en page ni ne perd de caractères.
            experience_comments=MESSAGE_5000,
            parent_goals_other=URL_LONGUE[:255],
            certifications_obtained="Certification DELF A2",
            special_needs=TEXTE_HTML,
            french_level_notes=URL_LONGUE,
            availability_notes=ACCENTS + "\n\n" + MOT_300,
            other_languages="Fon, yoruba, anglais",
            equipment_notes="Un.\n\nDeux.\n\nTrois.\n\nFin du contrôle.",
        )

    def test_la_fiche_est_produite_malgre_un_message_de_5000_caracteres(
            self, application):
        """
        C'EST LE TEST DE NON-RÉGRESSION DU DÉFAUT.

        Avant correction, cet appel levait `LayoutError` et la fiche
        n'existait pas.
        """
        from apps.website.fha_pdf import generate_enrollment_sheet

        content = generate_enrollment_sheet(application)
        assert content[:5] == b"%PDF-", "aucun PDF produit"
        assert len(content) > 3000

    def test_la_fiche_s_etale_sur_autant_de_pages_qu_il_faut(self, application):
        from apps.website.fha_pdf import generate_enrollment_sheet

        _, pages = texte_du_pdf(generate_enrollment_sheet(application))
        assert pages >= 2, (
            "Un message de 5 000 caractères tient sur plus d'une page : "
            "une fiche d'une seule page signifie que la fin a disparu."
        )

    def test_la_fin_du_message_long_est_bien_imprimee(self, application):
        """Une troncature silencieuse se voit à la disparition de la fin."""
        from apps.website.fha_pdf import generate_enrollment_sheet

        texte, _ = texte_du_pdf(generate_enrollment_sheet(application))
        plat = sans_coupures(texte.replace("\n", ""))
        assert "Famille Adjovi-Bokô" in plat

    def test_aucun_texte_ne_sort_du_cadre(self, application):
        """
        Mesure réelle : on relit la position de CHAQUE mot dans le PDF
        produit et on vérifie qu'aucun ne dépasse la marge droite.
        """
        from apps.website.fha_pdf import generate_enrollment_sheet

        content = generate_enrollment_sheet(application)
        document = fitz.open(stream=content, filetype="pdf")
        try:
            marge_droite = document[0].rect.width - 1.6 * cm
            debordements = [
                (page.number + 1, mot[4], mot[2] - marge_droite)
                for page in document
                for mot in page.get_text("words")
                if mot[2] > marge_droite + 0.5
            ]
        finally:
            document.close()
        assert not debordements, (
            f"{len(debordements)} mot(s) sortent du cadre, dont "
            f"{debordements[:3]}"
        )

    def test_l_url_longue_est_presente_en_entier(self, application):
        from apps.website.fha_pdf import generate_enrollment_sheet

        texte, _ = texte_du_pdf(generate_enrollment_sheet(application))
        plat = sans_coupures(texte.replace("\n", ""))
        assert "token=" + "a" * 120 in plat

    def test_le_mot_de_300_caracteres_est_present_en_entier(self, application):
        from apps.website.fha_pdf import generate_enrollment_sheet

        texte, _ = texte_du_pdf(generate_enrollment_sheet(application))
        plat = sans_coupures(texte.replace("\n", ""))
        trouve = re.search(r"Mo+T", plat)
        assert trouve and len(trouve.group(0)) == 300

    def test_les_accents_survivent_a_l_impression(self, application):
        from apps.website.fha_pdf import generate_enrollment_sheet

        texte, _ = texte_du_pdf(generate_enrollment_sheet(application))
        plat = sans_coupures(texte.replace("\n", ""))
        assert "Élève à Cotonou" in plat
        assert "Adjovi-Bokô" in plat

    def test_le_texte_html_reste_litteral_dans_le_pdf(self, application):
        """
        Le PDF doit contenir les caractères `<script>` comme du texte, pas
        les interpréter — et surtout ne pas les avaler.
        """
        from apps.website.fha_pdf import generate_enrollment_sheet

        texte, _ = texte_du_pdf(generate_enrollment_sheet(application))
        plat = sans_coupures(texte.replace("\n", ""))
        assert "alert('x')" in plat
        assert "italique" in plat

    def test_aucune_page_n_est_vide(self, application):
        """
        Une coupure mal placée produit des pages blanches au milieu du
        document — signe qu'un bloc a été poussé sans être rendu.
        """
        from apps.website.fha_pdf import generate_enrollment_sheet

        content = generate_enrollment_sheet(application)
        document = fitz.open(stream=content, filetype="pdf")
        try:
            vides = [p.number + 1 for p in document if not p.get_text().strip()]
        finally:
            document.close()
        assert not vides, f"pages vides : {vides}"

    def test_aucun_texte_ne_se_superpose(self, application):
        """
        Deux blocs qui se chevauchent donnent un document illisible sans
        qu'aucune erreur ne soit levée. On compare les rectangles des
        lignes de texte deux à deux.
        """
        from apps.website.fha_pdf import generate_enrollment_sheet

        content = generate_enrollment_sheet(application)
        document = fitz.open(stream=content, filetype="pdf")
        try:
            chevauchements = []
            for page in document:
                lignes = [
                    fitz.Rect(ligne["bbox"])
                    for bloc in page.get_text("dict")["blocks"]
                    for ligne in bloc.get("lines", [])
                ]
                for i, a in enumerate(lignes):
                    for b in lignes[i + 1:]:
                        inter = a & b
                        if inter.is_empty or not inter.is_valid:
                            continue
                        aire = inter.get_area()
                        # Une intersection marginale (crénage, accents
                        # débordants) n'est pas une superposition.
                        if aire > 0.4 * min(a.get_area(), b.get_area()):
                            chevauchements.append((page.number + 1, tuple(a), tuple(b)))
        finally:
            document.close()
        assert not chevauchements, f"texte superposé : {chevauchements[:3]}"

    def test_la_police_reste_lisible_partout(self, application):
        from apps.website.fha_pdf import generate_enrollment_sheet

        content = generate_enrollment_sheet(application)
        document = fitz.open(stream=content, filetype="pdf")
        try:
            tailles = {
                round(span["size"], 1)
                for page in document
                for bloc in page.get_text("dict")["blocks"]
                for ligne in bloc.get("lines", [])
                for span in ligne.get("spans", [])
                if span["text"].strip()
            }
        finally:
            document.close()
        trop_petites = [s for s in tailles if s < MIN_READABLE_FONT_SIZE]
        assert not trop_petites, (
            f"tailles de police en dessous du lisible : {trop_petites}"
        )


# ── Le bulletin de notes ─────────────────────────────────────────────────


class TestBulletinTextesLibres(__import__(
        "tests.test_bug_fixes_v45", fromlist=["BaseSchoolSetup"]).BaseSchoolSetup):
    """
    P0 — DEUXIÈME DÉFAUT, TROUVÉ EN AUDITANT LE RENDU DES TEXTES LONGS.

    Le générateur de bulletins enveloppait bien ses cellules dans des
    `Paragraph` (le repli fonctionnait), mais SANS ÉCHAPPER le texte.
    ReportLab lit un paragraphe comme du mini-XML.

    Vérifié en remettant l'ancien code : le test
    `test_un_fragment_entre_chevrons_n_est_plus_avale` échoue, les quatre
    autres passent. Autrement dit le défaut n'était pas visible sur tous
    les caractères — une esperluette isolée passait — et c'est ce qui l'a
    laissé vivre : il ne cassait rien, il effaçait.
    """

    def _bulletin_avec_commentaire(self, commentaire):
        from apps.bulletins.pdf_generator import generate_bulletin

        bulletin = generate_bulletin(self.s1, "T1", self.year)
        bulletin.general_comment = commentaire
        bulletin.save(update_fields=["general_comment"])
        return generate_bulletin(self.s1, "T1", self.year)

    def _texte(self, bulletin):
        bulletin.pdf_file.open("rb")
        try:
            content = bulletin.pdf_file.read()
        finally:
            bulletin.pdf_file.close()
        document = fitz.open(stream=content, filetype="pdf")
        try:
            return "".join(page.get_text() for page in document)
        finally:
            document.close()

    def test_une_esperluette_ne_casse_plus_le_bulletin(self):
        bulletin = self._bulletin_avec_commentaire(
            "Bon élève & travailleur, progrès nets ce trimestre.")
        assert bulletin.pdf_file.size > 1000

    def test_un_fragment_entre_chevrons_n_est_plus_avale(self):
        """Le fragment le plus important est celui qui disparaissait."""
        bulletin = self._bulletin_avec_commentaire(
            "Progrès <très nets> en lecture.")
        plat = self._texte(bulletin).replace("\n", "")
        assert "<très nets>" in plat

    def test_un_commentaire_tres_long_ne_fait_pas_echouer_le_bulletin(self):
        bulletin = self._bulletin_avec_commentaire(MESSAGE_5000)
        assert bulletin.pdf_file.size > 1000

    def test_la_fin_d_un_commentaire_long_reste_imprimee(self):
        bulletin = self._bulletin_avec_commentaire(
            "Début du commentaire. " + "Détail. " * 200 + "FIN-DU-COMMENTAIRE")
        plat = self._texte(bulletin).replace("\n", "")
        assert "FIN-DU-COMMENTAIRE" in plat

    def test_les_accents_du_commentaire_survivent(self):
        bulletin = self._bulletin_avec_commentaire(
            "Élève très à l'aise ; félicitations à la famille Adjovi-Bokô.")
        plat = self._texte(bulletin).replace("\n", "")
        assert "Adjovi-Bokô" in plat
