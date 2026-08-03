"""
P1 — L'outil de mesure est confronté à une vérité connue.

POURQUOI CE TEST EST LE SEUL QUI COMPTE POUR CET OUTIL
------------------------------------------------------
`document_analyze` sert à calibrer un gabarit : il dit à quelle hauteur
se pose le nom de l'élève, où commencent les règles de signature, où
s'inscrit la date. Un outil de mesure qu'on n'a jamais confronté à une
mesure indépendante ne mesure rien — il produit des nombres, ce qui est
autre chose.

Les fonds FEBA ont été calibrés à la main lors d'une itération
précédente, et leurs ancres sont inscrites dans
`diploma_feba_template.json`. Ce test demande à l'outil de les
retrouver SEUL, sans jamais lire ce fichier autrement que pour comparer.

C'est aussi ce test qui a fait corriger deux fois l'algorithme :

  1. la détection ligne par ligne fusionnait les règles DIRECTEUR et
     ENSEIGNANT — situées à la même hauteur, de part et d'autre du sceau
     — en un seul trait de 840 px traversant le décor. Une ancre
     inventée, qui aurait servi à calibrer ;

  2. la même détection perdait entièrement la règle de DATE : à cette
     hauteur, la courbe décorative encre déjà ~400 px par ligne, une
     dizaine de lignes passaient le seuil, se fondaient en un bloc trop
     épais, et le trait disparaissait avec le bloc.

L'algorithme raisonne désormais par tronçons d'encre reliés d'une ligne
à l'autre. Les quatre ancres sont retrouvées.
"""
import json
import os

import pytest
from django.conf import settings

from apps.documents.management.commands.document_analyze import (
    analyze, image_facts,
)

TEMPLATES = os.path.join(settings.BASE_DIR, "document_templates")
DIPLOME = os.path.join(TEMPLATES, "originals", "diplome_feba_2.png")
CERTIFICAT = os.path.join(TEMPLATES, "originals", "certificat_feba_2.png")

#: Tolérance de reconnaissance, en pixels. Une règle dorée s'estompe à
#: ses extrémités : exiger le pixel exact aux deux bouts reviendrait à
#: tester le seuil de luminance, pas la détection.
TOLERANCE_Y = 3
TOLERANCE_X = 30

#: Les ancres mesurées à la main, recopiées ici EXPLICITEMENT plutôt que
#: relues du JSON : si quelqu'un modifie le gabarit, ce test doit
#: échouer et forcer une nouvelle mesure, pas suivre le changement.
ANCRES_DIPLOME = [
    ("règle d'écriture du nom", 692, 386, 1105),
    ("règle DIRECTEUR", 886, 216, 479),
    ("règle ENSEIGNANT", 886, 853, 1010),
    ("règle DATE", 920, 1140, 1314),
]


@pytest.fixture(scope="module")
def mesures():
    return analyze(DIPLOME)


def _trouve(regles, y, x_debut, x_fin):
    """La règle mesurée correspond-elle à une règle détectée ?"""
    for regle in regles:
        if not (regle["y_debut_px"] - TOLERANCE_Y <= y
                <= regle["y_fin_px"] + TOLERANCE_Y):
            continue
        if (abs(regle["x_debut_px"] - x_debut) <= TOLERANCE_X
                and abs(regle["x_fin_px"] - x_fin) <= TOLERANCE_X):
            return regle
    return None


class TestFaitsBruts:

    def test_les_dimensions_sont_celles_du_fichier(self):
        faits = image_facts(DIPLOME)
        assert faits["largeur_px"] == 1492
        assert faits["hauteur_px"] == 1054
        assert faits["orientation"] == "paysage"

    def test_le_ratio_est_calcule(self):
        faits = image_facts(DIPLOME)
        assert faits["ratio"] == pytest.approx(1492 / 1054, abs=1e-4)

    def test_l_empreinte_est_celle_du_gabarit_verrouille(self):
        """
        L'empreinte du fond est l'autorité : elle détecte un fichier
        remplacé, même par une version visuellement identique mais
        ré-encodée — ce qui décalerait silencieusement toutes les
        coordonnées.
        """
        gabarit = json.load(open(
            os.path.join(TEMPLATES, "diploma_feba_template.json"),
            encoding="utf-8"))
        connues = {gabarit["background"]["sha256"]} | {
            v["sha256"] for v in gabarit["background"].get("accepted_variants", [])
        }
        assert image_facts(DIPLOME)["sha256"] in connues

    def test_la_conversion_pixel_millimetre_est_coherente(self, mesures):
        # 297 mm de large pour 1492 px.
        assert mesures["mm_par_px"] == pytest.approx(297.0 / 1492, abs=1e-4)


class TestAncresConnues:
    """L'outil retrouve-t-il ce qu'un humain avait mesuré ?"""

    @pytest.mark.parametrize("nom,y,x_debut,x_fin", ANCRES_DIPLOME)
    def test_chaque_ancre_mesuree_a_la_main_est_retrouvee(
            self, mesures, nom, y, x_debut, x_fin):
        regles = mesures["regles_horizontales"]
        trouvee = _trouve(regles, y, x_debut, x_fin)
        assert trouvee is not None, (
            f"« {nom} » (y={y}, x={x_debut}–{x_fin}) n'est pas retrouvée. "
            f"Règles détectées à proximité : "
            f"{[r for r in regles if abs(r['y_debut_px'] - y) <= 10]}"
        )

    def test_la_regle_du_nom_est_retrouvee_au_pixel_pres(self, mesures):
        """
        C'est l'ancre qui positionne le NOM DE L'ÉLÈVE. Une erreur de
        deux millimètres y est visible à l'œil nu sur le papier.
        """
        trouvee = _trouve(mesures["regles_horizontales"], 692, 386, 1105)
        assert trouvee["y_debut_px"] == 692
        assert trouvee["x_debut_px"] == 386
        assert trouvee["x_fin_px"] == 1105

    def test_les_deux_regles_de_signature_restent_distinctes(self, mesures):
        """
        NON-RÉGRESSION. Elles sont à la même hauteur, de part et d'autre
        du sceau. Les fusionner produisait une ancre de 840 px traversant
        le décor — un trait qui n'existe pas.
        """
        a_cette_hauteur = [r for r in mesures["regles_horizontales"]
                           if abs(r["y_debut_px"] - 886) <= 2]
        longues = [r for r in a_cette_hauteur if r["longueur_px"] >= 100]
        assert len(longues) >= 2, longues
        assert all(r["longueur_px"] < 600 for r in longues), (
            "une règle de signature traverse tout le document : les deux "
            "traits ont été fusionnés")

    def test_la_regle_de_date_n_est_pas_avalee_par_le_decor(self, mesures):
        """
        NON-RÉGRESSION. À cette hauteur, la courbe décorative encre déjà
        ~400 px par ligne. Une détection ligne par ligne fondait le trait
        dans le décor et le perdait sans rien signaler.
        """
        trouvee = _trouve(mesures["regles_horizontales"], 920, 1140, 1314)
        assert trouvee is not None
        assert trouvee["longueur_px"] >= 150

    def test_aucune_ancre_ne_traverse_toute_la_largeur(self, mesures):
        """
        Une « règle » aussi large que la page est la bordure décorative,
        pas une ligne d'écriture. S'en servir pour calibrer placerait le
        nom de l'élève sur le cadre.
        """
        largeur = mesures["largeur_px"]
        for regle in mesures["regles_horizontales"]:
            assert regle["longueur_px"] < 0.85 * largeur, regle


class TestSecondFond:
    """Le certificat FEBA : mêmes garanties, autre mise en page."""

    def test_le_certificat_est_analysable(self):
        faits = analyze(CERTIFICAT)
        assert faits["orientation"] == "paysage"
        assert faits["regles_horizontales"], "aucune règle détectée"

    def test_le_certificat_a_une_regle_d_ecriture_large(self):
        faits = analyze(CERTIFICAT)
        largeur = faits["largeur_px"]
        larges = [r for r in faits["regles_horizontales"]
                  if r["longueur_px"] > 0.35 * largeur]
        assert larges, (
            "aucune règle assez large pour recevoir un nom : le gabarit "
            "ne pourrait pas être calibré automatiquement")
