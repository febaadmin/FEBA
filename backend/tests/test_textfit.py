"""
P0 — Le nom d'un élève tient sur son diplôme, quel qu'il soit.

CE QUI EST ÉPROUVÉ ICI
----------------------
Trois choses, dans cet ordre.

  1. LES MESURES. Le moteur lit les tables du fichier de police. Ses
     largeurs sont confrontées à celles de ReportLab, qui dessinera :
     deux mesures qui divergent d'un dixième de point suffisent à faire
     sortir un nom de sa zone sans que rien ne le signale.

  2. LA COMPOSITION. Espaces normalisés et rien d'autre, coupes sur les
     espaces seulement, équilibre des deux lignes, taille unique,
     refus prouvé et chiffré.

  3. LE RÉSULTAT SUR LE PAPIER. Le document est produit, rastérisé, et
     l'encre du nom est comparée pixel à pixel au même fond sans texte.
     C'est le seul contrôle qui aurait attrapé le défaut d'origine : la
     phrase « Ce diplôme est fièrement décerné à » est DANS L'IMAGE du
     fond. Aucune analyse du PDF ne voit une collision avec elle, parce
     qu'il n'y a rien à quoi se heurter du point de vue du PDF. Trois
     versions successives du repli sur deux lignes ont passé les
     contrôles géométriques et recouvert cette phrase.

CE QUI N'EST PAS ÉPROUVÉ ICI
----------------------------
Que le résultat soit BEAU. Huit rendus ont été ouverts et regardés ; ce
qu'ils ont montré est consigné dans DOCUMENT_TEMPLATE_CALIBRATION.md.
Un test dit qu'un nom ne touche pas une règle, il ne dit pas qu'il est
bien posé.
"""
import datetime
import io
import unittest

import numpy as np
from django.test import SimpleTestCase
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics

from apps.documents.renderer import (
    Layout, RenderError, ensure_fonts, plan_text, render_document,
)
from apps.documents.templates_registry import load_template
from apps.documents.textfit import (
    MM, CompositionRefused, MetricsError, compose, get_ascent_descent,
    get_text_bbox, measure_multiline_block, metrics_for, natural_leading,
    normalize_spaces, split_points,
)

#: Les quatre gabarits qui composent un nom, et l'académie de chacun.
GABARITS = (
    ("diploma_feba", "FEBA"),
    ("certificate_feba", "FEBA"),
    ("diploma_feba_fha", "FEBA_FHA"),
    ("certificate_feba_fha", "FEBA_FHA"),
)

#: Les noms que l'établissement doit pouvoir imprimer. Chacun a été
#: choisi pour ce qu'il casse, pas pour faire nombre.
NOMS = {
    "court": "Élise Kponou",
    "apostrophe_simple": "Jean-Baptiste D'Almeida",
    "apostrophe_typographique": "Jean-Baptiste D’Almeida",
    "esperluette": "Grâce & Excellence Hounkpatin",
    "compose": "Marie-Élisabeth Joséphine Adjovi-Bokô",
    "espaces_multiples": "Marie-Élisabeth   Joséphine    Adjovi-Bokô",
    "tres_long": ("Marie-Élisabeth Joséphine Adjovi-Bokô d'Almeida "
                  "de Souza Hounkpatin Ahouangonou"),
}

POLICE = "FEBA-Script"


def champ_du_nom(template_id):
    gabarit = load_template(template_id)
    return next(f for f in gabarit.fields if f.name == "student_name")


class MetriquesTests(SimpleTestCase):
    """Les mesures viennent du fichier de police, et elles sont justes."""

    def test_la_largeur_mesuree_est_celle_que_reportlab_dessinera(self):
        # LE CONTRÔLE LE PLUS IMPORTANT DU FICHIER. Le moteur décide où
        # écrire à partir de SES mesures ; ReportLab dessine à partir des
        # SIENNES. Si les deux divergent, tout le reste est une fiction
        # cohérente avec elle-même.
        ensure_fonts()
        for cle, nom in NOMS.items():
            for taille in (34.0, 21.5, 14.0):
                with self.subTest(nom=cle, taille=taille):
                    mesure = get_text_bbox(nom, POLICE, taille).advance
                    dessin = pdfmetrics.stringWidth(nom, POLICE, taille)
                    self.assertAlmostEqual(mesure, dessin, places=4)

    def test_la_boite_englobante_est_celle_du_dessin_pas_de_la_fonte(self):
        # C'est là que se joue la place gagnée. La fonte annonce 0,896 em
        # d'ascendante ; les lettres d'un nom montent à 0,766 em au plus.
        metrics = metrics_for(POLICE)
        boite = get_text_bbox("Kponou", POLICE, 100.0)
        self.assertLess(boite.y_max, metrics.ascent * 100.0)
        self.assertGreater(boite.y_max, 0.0)
        # « Kponou » n'a ni capitale accentuée ni hampe montante : son
        # encre plafonne à la hauteur du « K ».
        self.assertAlmostEqual(boite.y_max, 0.5732 * 100.0, delta=0.5)

    def test_une_capitale_accentuee_monte_plus_haut_qu_une_capitale(self):
        haut_e = get_text_bbox("É", POLICE, 100.0).y_max
        haut_e_nu = get_text_bbox("E", POLICE, 100.0).y_max
        self.assertGreater(haut_e, haut_e_nu)

    def test_l_italique_deborde_de_sa_chasse(self):
        # Un nom calé sur la somme des chasses sort de sa zone par les
        # extrémités : le « K » déborde à droite, le « A » à gauche.
        boite = get_text_bbox("K", POLICE, 100.0)
        self.assertGreater(boite.x_max, boite.advance)
        self.assertLess(get_text_bbox("A", POLICE, 100.0).x_min, 0.0)

    def test_les_espaces_ne_font_pas_d_encre_mais_avancent(self):
        un = get_text_bbox("Kponou", POLICE, 34.0)
        deux = get_text_bbox("Kponou ", POLICE, 34.0)
        self.assertGreater(deux.advance, un.advance)
        self.assertAlmostEqual(deux.x_max, un.x_max, places=6)

    def test_les_metriques_nominales_sont_celles_de_la_fonte(self):
        montante, descendante = get_ascent_descent(POLICE, 100.0)
        self.assertAlmostEqual(montante, 89.65, delta=0.1)
        self.assertAlmostEqual(descendante, -21.48, delta=0.1)
        self.assertLess(descendante, 0.0)

    def test_une_police_non_embarquee_est_refusee_avec_son_nom(self):
        with self.assertRaises(MetricsError) as capture:
            get_text_bbox("Kponou", "Helvetica", 34.0)
        self.assertIn("Helvetica", str(capture.exception))

    def test_un_caractere_absent_de_la_police_est_signale(self):
        with self.assertRaises(MetricsError):
            get_text_bbox("Kponou 漢字", POLICE, 34.0)


class BlocTests(SimpleTestCase):
    """La hauteur d'un bloc est mesurée, jamais estimée."""

    def test_la_hauteur_est_l_interligne_plus_l_encre_pas_le_corps(self):
        lignes = ["Élise", "Kponou"]
        bloc = measure_multiline_block(lignes, POLICE, 34.0, 34.0)
        haut = get_text_bbox("Élise", POLICE, 34.0).y_max
        bas = get_text_bbox("Kponou", POLICE, 34.0).y_min
        self.assertAlmostEqual(bloc.height, 34.0 + haut - bas, places=6)
        # L'estimation qu'on a bannie : « hauteur = corps × 0,75 ».
        self.assertNotAlmostEqual(bloc.height, 34.0 * 0.75 * 2, delta=1.0)

    def test_l_origine_est_la_derniere_ligne_de_base(self):
        bloc = measure_multiline_block(["Élise", "Kponou"], POLICE, 20.0, 20.0)
        self.assertEqual(bloc.baselines, (20.0, 0.0))
        self.assertGreater(bloc.top, 0.0)
        self.assertLess(bloc.bottom, 0.0)

    def test_le_blanc_entre_lignes_est_mesure_sur_l_encre(self):
        bloc = measure_multiline_block(["Kpoj", "Élise"], POLICE, 100.0, 100.0)
        attendu = (100.0 + get_text_bbox("Kpoj", POLICE, 100.0).y_min
                   - get_text_bbox("Élise", POLICE, 100.0).y_max)
        self.assertAlmostEqual(bloc.interline_gap, attendu, places=6)

    def test_une_seule_ligne_n_a_pas_de_blanc_interligne(self):
        bloc = measure_multiline_block(["Élise"], POLICE, 34.0, 34.0)
        self.assertIsNone(bloc.interline_gap)

    def test_l_interligne_s_ecarte_quand_l_encre_l_exige(self):
        # « j » descend, « É » monte : à interligne serré les deux se
        # croiseraient. Le moteur relève l'interligne au lieu de laisser
        # faire.
        boites = tuple(get_text_bbox(t, POLICE, 100.0) for t in ("Kpoj", "Élise"))
        serre = natural_leading(boites, 100.0, 0.50, 0.0)
        self.assertGreater(serre, 50.0)
        bloc = measure_multiline_block(["Kpoj", "Élise"], POLICE, 100.0, serre)
        self.assertGreaterEqual(bloc.interline_gap, -1e-6)


class NormalisationTests(SimpleTestCase):
    """Ce qu'un parent a écrit sur un acte de naissance n'est pas édité."""

    def test_les_espaces_multiples_sont_reduits_a_un_seul(self):
        self.assertEqual(
            normalize_spaces("Marie-Élisabeth   Joséphine    Adjovi-Bokô"),
            "Marie-Élisabeth Joséphine Adjovi-Bokô")

    def test_les_espaces_des_extremites_disparaissent(self):
        self.assertEqual(normalize_spaces("  Élise Kponou \n"), "Élise Kponou")

    def test_l_espace_insecable_est_un_espace(self):
        self.assertEqual(normalize_spaces("Élise Kponou"), "Élise Kponou")

    def test_rien_d_autre_n_est_touche(self):
        for original in ("Jean-Baptiste D'Almeida", "Jean-Baptiste D’Almeida",
                         "Grâce & Excellence", "Adjovi-Bokô", "N'Diaye"):
            with self.subTest(nom=original):
                self.assertEqual(normalize_spaces(original), original)

    def test_les_coupes_ne_tombent_que_sur_des_espaces(self):
        for haut, bas in split_points("Jean-Baptiste D'Almeida de Souza"):
            with self.subTest(coupe=(haut, bas)):
                self.assertEqual(f"{haut} {bas}",
                                 "Jean-Baptiste D'Almeida de Souza")
                # Ni au milieu d'un mot, ni après un trait d'union.
                self.assertFalse(haut.endswith("-"))
                self.assertFalse(bas.startswith("-"))

    def test_un_nom_d_un_seul_mot_n_a_aucune_coupe(self):
        self.assertEqual(split_points("Ahouangonou"), [])


class CompositionTests(SimpleTestCase):
    """Le moteur, éprouvé sur une zone connue et indépendante d'un gabarit."""

    #: Zone d'essai : 140 mm de large, 17 mm de haut. Proche du diplôme
    #: FEBA, mais fixée ici pour que ce test ne change pas quand un
    #: gabarit est recalibré.
    LARGE = 140 * MM
    HAUTE = 17 * MM

    def composer(self, texte, **extra):
        options = dict(font_family=POLICE, size_pt=34.0, min_size_pt=14.0,
                       max_lines=2, available_width_pt=self.LARGE,
                       zone_height_pt=self.HAUTE)
        options.update(extra)
        return compose(texte, **options)

    def test_un_nom_court_reste_a_la_taille_nominale_sur_une_ligne(self):
        resultat = self.composer(NOMS["court"])
        self.assertEqual(resultat.lines, (NOMS["court"],))
        self.assertEqual(resultat.size_pt, 34.0)

    def test_les_apostrophes_ne_changent_pas_le_nom(self):
        for cle in ("apostrophe_simple", "apostrophe_typographique"):
            with self.subTest(cle=cle):
                self.assertEqual(self.composer(NOMS[cle]).lines,
                                 (NOMS[cle],))

    def test_l_esperluette_est_imprimee_telle_quelle(self):
        resultat = self.composer(NOMS["esperluette"])
        self.assertIn("&", resultat.lines[0])
        self.assertNotIn("&amp;", resultat.lines[0])

    def test_un_nom_compose_ne_se_coupe_pas_sur_le_trait_d_union(self):
        resultat = self.composer(NOMS["tres_long"])
        self.assertEqual(len(resultat.lines), 2)
        self.assertFalse(resultat.lines[0].endswith("-"))
        self.assertIn("Adjovi-Bokô", " ".join(resultat.lines))

    def test_les_espaces_multiples_sont_normalises_avant_composition(self):
        resultat = self.composer(NOMS["espaces_multiples"])
        self.assertEqual(resultat.lines, (NOMS["compose"],))

    def test_le_repli_sur_deux_lignes_est_automatique(self):
        court = self.composer(NOMS["court"])
        long = self.composer(NOMS["tres_long"])
        self.assertEqual(len(court.lines), 1)
        self.assertEqual(len(long.lines), 2)
        # Rien n'est perdu : les deux lignes recomposent le nom.
        self.assertEqual(" ".join(long.lines), NOMS["tres_long"])

    def test_les_deux_lignes_ont_la_meme_taille(self):
        resultat = self.composer(NOMS["tres_long"])
        self.assertEqual(resultat.block.size_pt, resultat.size_pt)
        largeurs = [b.size_pt for b in resultat.block.boxes]
        self.assertEqual(set(largeurs), {resultat.size_pt})

    def test_la_coupe_retenue_est_la_plus_equilibree(self):
        resultat = self.composer(NOMS["tres_long"])
        haut, bas = (b.ink_width for b in resultat.block.boxes)
        retenu = abs(haut - bas)
        for autre_haut, autre_bas in split_points(NOMS["tres_long"]):
            bloc = measure_multiline_block(
                [autre_haut, autre_bas], POLICE, resultat.size_pt,
                resultat.leading_pt)
            if (bloc.ink_width <= self.LARGE
                    and bloc.top <= self.HAUTE - 0.23 * resultat.size_pt):
                ecart = abs(bloc.boxes[0].ink_width - bloc.boxes[1].ink_width)
                self.assertLessEqual(retenu, ecart + 1e-6)

    def test_deux_lignes_valent_mieux_qu_une_ligne_minuscule(self):
        # Le défaut trouvé en relisant la première version : le moteur
        # épuisait toutes les tailles sur une ligne avant d'essayer deux.
        # Un nom de 73 caractères sortait sur UNE ligne à 14,75 pt, alors
        # que deux tenaient à 20 pt.
        resultat = compose(NOMS["tres_long"], font_family=POLICE,
                           size_pt=34.0, min_size_pt=14.0, max_lines=2,
                           available_width_pt=200 * MM,
                           zone_height_pt=self.HAUTE)
        self.assertEqual(len(resultat.lines), 2)
        self.assertGreater(resultat.size_pt, 16.0)

    def test_a_taille_egale_une_ligne_est_preferee(self):
        resultat = self.composer(NOMS["compose"])
        self.assertEqual(len(resultat.lines), 1)

    def test_le_corps_ne_depend_pas_des_lettres_du_nom(self):
        # Sans hauteur de référence, « Élise Kponou » sortirait plus
        # petit que « Jean Dossou » sur le même document : l'accent monte
        # plus haut que toute lettre du second. Deux diplômes remis le
        # même jour, deux tailles de nom.
        etroite = dict(zone_height_pt=11 * MM)
        with_accent = self.composer("Élise Kponou", **etroite)
        sans_accent = self.composer("Jean Dossou", **etroite)
        self.assertEqual(with_accent.size_pt, sans_accent.size_pt)

    def test_le_bloc_reste_dans_la_zone(self):
        for cle, nom in NOMS.items():
            with self.subTest(nom=cle):
                resultat = self.composer(nom)
                reserve = 0.23 * resultat.size_pt
                self.assertLessEqual(resultat.block.top,
                                     self.HAUTE - reserve + 1e-6)
                self.assertLessEqual(-resultat.block.bottom, reserve + 1e-6)
                self.assertLessEqual(resultat.block.ink_width,
                                     self.LARGE + 1e-6)

    def test_les_lignes_ne_se_croisent_jamais(self):
        for cle, nom in NOMS.items():
            resultat = self.composer(nom)
            if resultat.block.interline_gap is None:
                continue
            with self.subTest(nom=cle):
                self.assertGreaterEqual(resultat.block.interline_gap, -1e-6)

    def test_un_texte_vide_est_refuse(self):
        with self.assertRaises(CompositionRefused):
            self.composer("   ")

    def test_le_refus_est_prouve_et_chiffre(self):
        # Un seul mot, plus long que la zone, sans aucune coupe possible :
        # c'est le seul cas où refuser est la bonne réponse.
        with self.assertRaises(CompositionRefused) as capture:
            self.composer("A" * 200)
        message = str(capture.exception)
        self.assertIn("200 caractères", message)
        self.assertIn("14.0 pt", message)
        self.assertTrue(capture.exception.trials)
        self.assertFalse(any(e["accepte"] for e in capture.exception.trials))

    def test_chaque_essai_est_consigne(self):
        resultat = self.composer(NOMS["tres_long"])
        self.assertTrue(resultat.trials)
        # Le dernier essai n'est PAS forcément celui qu'on retient : à la
        # taille qui convient, toutes les coupes sont mesurées, et c'est
        # la plus équilibrée qui gagne — pas la dernière essayée.
        acceptes = [e for e in resultat.trials if e["accepte"]]
        self.assertTrue(acceptes)
        self.assertEqual({e["taille_pt"] for e in acceptes},
                         {round(resultat.size_pt, 2)})
        for essai in resultat.trials:
            self.assertIn("montee_reelle_pt", essai)
            self.assertIn("plafond_pt", essai)


class GabaritsReelsTests(SimpleTestCase):
    """Les quatre gabarits livrés, avec leurs zones mesurées sur le fond."""

    def test_les_quatre_gabarits_declarent_une_zone_mesuree(self):
        for template_id, _ in GABARITS:
            with self.subTest(gabarit=template_id):
                champ = champ_du_nom(template_id)
                self.assertIsNotNone(champ.safe_zone)
                zone = champ.safe_zone
                self.assertGreater(zone.height_mm, 0)
                self.assertGreater(zone.width_mm, 0)
                self.assertIsNotNone(zone.engraved_phrase_bottom_mm)
                self.assertIsNotNone(zone.writing_rule_top_mm)

    def test_la_zone_tient_entre_la_phrase_gravee_et_la_regle(self):
        for template_id, _ in GABARITS:
            with self.subTest(gabarit=template_id):
                zone = champ_du_nom(template_id).safe_zone
                self.assertGreater(zone.y_top_mm, zone.engraved_phrase_bottom_mm)
                self.assertLess(zone.y_bottom_mm, zone.writing_rule_top_mm)

    def test_les_deux_lignes_sont_autorisees_partout(self):
        for template_id, _ in GABARITS:
            with self.subTest(gabarit=template_id):
                self.assertGreaterEqual(champ_du_nom(template_id).max_lines, 2)

    def test_le_nom_de_76_caracteres_tient_sur_les_quatre_gabarits(self):
        nom = NOMS["tres_long"]
        self.assertGreaterEqual(len(nom), 76)
        for template_id, _ in GABARITS:
            with self.subTest(gabarit=template_id):
                lignes, taille, interligne, base = plan_text(
                    champ_du_nom(template_id), nom)
                self.assertEqual(len(lignes), 2)
                self.assertEqual(" ".join(lignes), nom)
                self.assertGreaterEqual(taille, 14.0)

    def test_aucun_nom_n_est_tronque_ni_refuse(self):
        for template_id, _ in GABARITS:
            champ = champ_du_nom(template_id)
            for cle, nom in NOMS.items():
                with self.subTest(gabarit=template_id, nom=cle):
                    lignes, _, _, _ = plan_text(champ, nom)
                    self.assertEqual(" ".join(lignes), normalize_spaces(nom))
                    self.assertNotIn("…", " ".join(lignes))

    def test_l_encre_reste_dans_la_zone_sur_chaque_gabarit(self):
        for template_id, _ in GABARITS:
            champ = champ_du_nom(template_id)
            zone = champ.safe_zone
            for cle, nom in NOMS.items():
                with self.subTest(gabarit=template_id, nom=cle):
                    lignes, taille, interligne, base = plan_text(champ, nom)
                    bloc = measure_multiline_block(lignes, champ.font_family,
                                                   taille, interligne)
                    haut_mm = base - bloc.top / MM
                    bas_mm = base - bloc.bottom / MM
                    self.assertGreaterEqual(haut_mm, zone.y_top_mm - 1e-6)
                    self.assertLessEqual(bas_mm, zone.y_bottom_mm + 1e-6)
                    self.assertLessEqual(bloc.ink_width / MM,
                                         zone.width_mm + 1e-6)

    def test_le_nom_est_centre_dans_sa_zone(self):
        for template_id, _ in GABARITS:
            champ = champ_du_nom(template_id)
            with self.subTest(gabarit=template_id):
                self.assertEqual(champ.align, "center")
                centre_boite = champ.box.x_mm + champ.box.width_mm / 2
                zone = champ.safe_zone
                centre_zone = (zone.x_left_mm + zone.x_right_mm) / 2
                self.assertAlmostEqual(centre_boite, centre_zone, places=2)

    def test_le_nom_reste_a_l_interieur_de_sa_regle_d_ecriture(self):
        # La règle est le trait sur lequel le nom est écrit. Un nom plus
        # large que son trait dépasse visuellement du support prévu — les
        # deux gabarits FEBA FHA avaient hérité de la largeur du fond de
        # Cotonou, plus large que la leur de 11 mm.
        largeurs = {
            "diploma_feba": (76.64, 220.36),
            "certificate_feba": (67.19, 229.81),
            "diploma_feba_fha": (84.00, 215.58),
            "certificate_feba_fha": (77.04, 219.96),
        }
        for template_id, (gauche, droite) in largeurs.items():
            with self.subTest(gabarit=template_id):
                zone = champ_du_nom(template_id).safe_zone
                self.assertGreaterEqual(zone.x_left_mm, gauche)
                self.assertLessEqual(zone.x_right_mm, droite)


def _fond_seul(template):
    """
    Le même fond, posé par le même calcul, sans un seul champ.

    Sert de référence au contrôle de pixels. Reproduire le placement
    plutôt que retirer le texte d'un PDF existant n'est pas un détour :
    les deux pages passent par `drawImage` avec la même transformation,
    donc le rastériseur produit exactement les mêmes pixels de fond. Leur
    différence est, au pixel près, ce que le moteur a ajouté.
    """
    from reportlab.pdfgen import canvas

    layout = Layout(template)
    tampon = io.BytesIO()
    pdf = canvas.Canvas(tampon, pagesize=(template.page_width_mm * mm,
                                          template.page_height_mm * mm))
    x_pt, y_pt = layout.to_pdf(layout.offset_x_mm,
                               layout.offset_y_mm + layout.height_mm)
    pdf.drawImage(template.render_background_path, x_pt, y_pt,
                  width=layout.width_mm * mm, height=layout.height_mm * mm,
                  preserveAspectRatio=True, anchor="c")
    pdf.showPage()
    pdf.save()
    return tampon.getvalue()


def _raster(octets, dpi):
    import fitz

    document = fitz.open("pdf", octets)
    try:
        pixmap = document[0].get_pixmap(dpi=dpi)
        image = np.frombuffer(pixmap.samples, dtype=np.uint8)
        return image.reshape(pixmap.height, pixmap.width, pixmap.n)[:, :, :3]
    finally:
        document.close()


class EncreDuNomTests(SimpleTestCase):
    """
    L'ENCRE, SUR LE PAPIER. Le seul contrôle qui voyait le défaut.

    La phrase « Ce diplôme est fièrement décerné à » est un dessin dans
    le fond, pas un objet du PDF. Aucune analyse de la structure du
    document ne peut constater qu'un nom la recouvre. Il faut regarder
    les pixels — ou ouvrir le fichier, ce qu'aucune suite ne fait toute
    seule.
    """

    DPI = 200

    #: Ce que le nom a le droit de dépasser de sa zone. Zéro. La tolérance
    #: porte sur la MESURE, pas sur le résultat : un pixel à 200 dpi vaut
    #: 0,127 mm, et l'anticrénelage étale l'encre d'un pixel de chaque
    #: côté.
    TOLERANCE_MM = 0.15

    def _encre_ajoutee(self, template_id, nom):
        """Masque des pixels que le moteur a ajoutés au fond."""
        gabarit = load_template(template_id)
        valeurs = {
            "student_name": nom,
            "issue_date": datetime.date(2026, 7, 12),
            "director_name": "Chris M. Hounsou",
            "teacher_name": "A. Dossou",
            "signatory_name": "Chris M. Hounsou",
            "document_number": "TEST-2026-0001",
        }
        avec = _raster(render_document(template_id, valeurs), self.DPI)
        sans = _raster(_fond_seul(gabarit), self.DPI)
        self.assertEqual(avec.shape, sans.shape)
        ecart = np.abs(avec.astype(int) - sans.astype(int)).sum(axis=2)
        return ecart > 40, gabarit

    def _bandes_du_nom(self, masque, gabarit, zone):
        """Lignes encrées, en millimètres, dans la colonne du nom."""
        hauteur, largeur = masque.shape
        mm_par_px_y = gabarit.page_height_mm / hauteur
        mm_par_px_x = gabarit.page_width_mm / largeur
        x0 = int(zone.x_left_mm / mm_par_px_x)
        x1 = int(zone.x_right_mm / mm_par_px_x)
        colonne = masque[:, x0:x1]
        lignes = np.where(colonne.any(axis=1))[0]
        return lignes, mm_par_px_y, colonne

    def test_l_encre_du_nom_reste_entierement_dans_la_zone_autorisee(self):
        for template_id, _ in GABARITS:
            zone = champ_du_nom(template_id).safe_zone
            for cle in ("court", "esperluette", "tres_long"):
                with self.subTest(gabarit=template_id, nom=cle):
                    masque, gabarit = self._encre_ajoutee(
                        template_id, NOMS[cle])
                    lignes, pas, _ = self._bandes_du_nom(masque, gabarit, zone)
                    # On ne garde que les lignes de la région du nom : la
                    # date et les signatures sont ajoutées elles aussi,
                    # bien plus bas.
                    haut = zone.engraved_phrase_bottom_mm - 3
                    bas = zone.writing_rule_top_mm + 3
                    dedans = [y * pas for y in lignes
                              if haut <= y * pas <= bas]
                    self.assertTrue(dedans, "aucune encre : le nom n'a pas "
                                            "été écrit")
                    self.assertGreaterEqual(
                        min(dedans), zone.y_top_mm - self.TOLERANCE_MM)
                    self.assertLessEqual(
                        max(dedans), zone.y_bottom_mm + self.TOLERANCE_MM)

    def test_aucune_encre_ne_touche_la_phrase_gravee_ni_la_regle(self):
        for template_id, _ in GABARITS:
            zone = champ_du_nom(template_id).safe_zone
            with self.subTest(gabarit=template_id):
                masque, gabarit = self._encre_ajoutee(
                    template_id, NOMS["tres_long"])
                lignes, pas, _ = self._bandes_du_nom(masque, gabarit, zone)
                mms = [y * pas for y in lignes]
                # Entre la phrase et le haut de la zone : rien.
                self.assertFalse(
                    [y for y in mms
                     if zone.engraved_phrase_bottom_mm - 3 <= y
                     < zone.y_top_mm - self.TOLERANCE_MM],
                    "le nom mord sur la phrase gravée dans le fond")
                # Entre le bas de la zone et la règle : rien.
                self.assertFalse(
                    [y for y in mms
                     if zone.y_bottom_mm + self.TOLERANCE_MM < y
                     <= zone.writing_rule_top_mm + 1],
                    "le nom touche ou traverse la règle d'écriture")

    def test_le_nom_est_optiquement_centre_sur_le_rendu(self):
        for template_id, _ in GABARITS:
            zone = champ_du_nom(template_id).safe_zone
            with self.subTest(gabarit=template_id):
                masque, gabarit = self._encre_ajoutee(
                    template_id, NOMS["tres_long"])
                hauteur, largeur = masque.shape
                pas_y = gabarit.page_height_mm / hauteur
                pas_x = gabarit.page_width_mm / largeur
                y0 = int((zone.y_top_mm - 1) / pas_y)
                y1 = int((zone.y_bottom_mm + 1) / pas_y)
                colonnes = np.where(masque[y0:y1].any(axis=0))[0]
                self.assertTrue(colonnes.size)
                centre = (colonnes.min() + colonnes.max() + 1) / 2 * pas_x
                attendu = (zone.x_left_mm + zone.x_right_mm) / 2
                self.assertAlmostEqual(centre, attendu, delta=1.0)

    def test_le_nom_long_occupe_bien_deux_lignes_sur_le_rendu(self):
        for template_id, _ in GABARITS:
            zone = champ_du_nom(template_id).safe_zone
            with self.subTest(gabarit=template_id):
                masque, gabarit = self._encre_ajoutee(
                    template_id, NOMS["tres_long"])
                lignes, pas, _ = self._bandes_du_nom(masque, gabarit, zone)
                dans_zone = sorted(
                    y for y in lignes
                    if zone.y_top_mm - 1 <= y * pas <= zone.y_bottom_mm + 1)
                # Deux paquets de lignes encrées séparés par du blanc.
                paquets = 1
                for precedent, suivant in zip(dans_zone, dans_zone[1:]):
                    if suivant - precedent > 1:
                        paquets += 1
                self.assertGreaterEqual(paquets, 2)


class IdentiteDesGabaritsTests(SimpleTestCase):
    """Un gabarit compose sur SON fond, pour SON académie."""

    def test_chaque_gabarit_est_reserve_a_son_academie(self):
        for template_id, code in GABARITS:
            with self.subTest(gabarit=template_id):
                self.assertEqual(load_template(template_id).academies, [code])

    def test_les_deux_academies_n_ont_aucun_fond_en_commun(self):
        fonds = {}
        for template_id, code in GABARITS:
            gabarit = load_template(template_id)
            fonds.setdefault(code, set()).add(gabarit.render_background_path)
        self.assertFalse(fonds["FEBA"] & fonds["FEBA_FHA"])

    def test_les_zones_different_parce_que_les_fonds_different(self):
        # Si les quatre zones étaient identiques, ce serait le signe qu'on
        # a copié un calibrage au lieu de mesurer chaque fond. Elles ne le
        # sont pas : le certificat FEBA FHA n'a que 10,94 mm de bande
        # utile là où le diplôme FEBA en a 16,92.
        hauteurs = {t: round(champ_du_nom(t).safe_zone.height_mm, 2)
                    for t, _ in GABARITS}
        self.assertEqual(len(set(hauteurs.values())), 4, hauteurs)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
