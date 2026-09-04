"""
Règles métier des parcours linguistiques — cas A à H.

LA CONTRADICTION REPRODUITE
---------------------------
Une classe francophone de FEBA FHA affiche « Configuration complète ✓ —
4 matière(s) FR », puis refuse l'enregistrement avec « Sélectionnez au
moins une matière anglaise. » Deux logiques métier contradictoires
cohabitaient : l'affichage suivait le parcours déclaré, la garde de
soumission appliquait encore la règle bilingue en dur.

CE QUE CES TESTS FIXENT
-----------------------
Les huit cas du cahier des charges, vérifiés là où ils comptent —
l'API, seule autorité. Un test qui ne passerait que par le composant
React laisserait le backend accepter n'importe quoi.
"""
from datetime import date

from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import CustomUser
from apps.classes.models import Class
from apps.schools.models import Level, School, SchoolYear
from apps.subjects.models import Subject


def academy(code, name, entity_type):
    school, _ = School.objects.update_or_create(
        code=code,
        defaults=dict(name=name, currency_code="XOF", address="Cotonou",
                      slug=code.lower().replace("_", "-"),
                      entity_type=entity_type),
    )
    SchoolYear.objects.filter(school=school).delete()
    return school


def annee(school, name="2026-2027"):
    return SchoolYear.objects.create(
        school=school, name=name, start_date=date(2026, 9, 1),
        end_date=date(2027, 7, 31), is_current=True)


def classe(school_year, name, track):
    level, _ = Level.objects.get_or_create(
        school=school_year.school, name="Niveau", defaults={"order": 1})
    return Class.objects.create(name=name, level=level,
                                school_year=school_year, language_track=track)


def matiere(school, name, code, langue):
    return Subject.objects.create(school=school, name=name, code=code,
                                  language=langue, coefficient=1)


def admin_de(school, email):
    return CustomUser.objects.create_user(
        username=email, email=email, password="Pass1234!", role="admin",
        school=school, first_name="A", last_name="D")


class BaseRegles(TestCase):
    """Deux académies, l'une bilingue par construction, l'autre non."""

    @classmethod
    def setUpTestData(cls):
        cls.feba = academy("FEBA", "Faith & Excellence Bilingual Academy", "campus")
        cls.fha = academy("FEBA_FHA", "FEBA French Heritage Academy", "online")
        cls.an_feba = annee(cls.feba)
        cls.an_fha = annee(cls.fha)

        cls.fr_fha = [matiere(cls.fha, f"Français {i}", f"FHAFR{i}", "fr") for i in range(1, 5)]
        cls.en_fha = [matiere(cls.fha, f"English {i}", f"FHAEN{i}", "en") for i in range(1, 4)]
        cls.fr_feba = [matiere(cls.feba, f"Français {i}", f"FEBAFR{i}", "fr") for i in range(1, 3)]
        cls.en_feba = [matiere(cls.feba, f"English {i}", f"FEBAEN{i}", "en") for i in range(1, 3)]

        cls.admin_feba = admin_de(cls.feba, "admin@feba.test")
        cls.admin_fha = admin_de(cls.fha, "admin@fha.test")

    def api(self, u):
        c = APIClient()
        c.force_authenticate(u)
        return c

    def enregistrer(self, user, cls_obj, subject_ids):
        """POST /classes/{id}/subjects/ — le chemin de l'écran Matières."""
        return self.api(user).post(
            f"/api/classes/{cls_obj.id}/subjects/",
            {"subject_ids": subject_ids}, format="json")

    def ids(self, matieres):
        return [m.id for m in matieres]


class CasDuCahierDesChargesTests(BaseRegles):
    """Les huit cas, mot pour mot."""

    def test_A_francophone_4_fr_0_en_est_valide(self):
        """LE BUG DE LA CAPTURE. 4 matières FR, 0 EN → doit s'enregistrer."""
        c = classe(self.an_fha, "Junior Roots", Class.TRACK_FRANCOPHONE)
        r = self.enregistrer(self.admin_fha, c, self.ids(self.fr_fha))
        self.assertEqual(r.status_code, 200, r.content[:300])
        self.assertEqual(c.subjects.count(), 4)

    def test_B_francophone_sans_aucune_matiere_est_invalide(self):
        c = classe(self.an_fha, "Junior Roots", Class.TRACK_FRANCOPHONE)
        r = self.enregistrer(self.admin_fha, c, [])
        self.assertEqual(r.status_code, 400, r.content[:300])
        self.assertIn("français", r.content.decode().lower())

    def test_C_anglophone_0_fr_3_en_est_valide(self):
        c = classe(self.an_fha, "French Ambassadors", Class.TRACK_ANGLOPHONE)
        r = self.enregistrer(self.admin_fha, c, self.ids(self.en_fha))
        self.assertEqual(r.status_code, 200, r.content[:300])
        self.assertEqual(c.subjects.count(), 3)

    def test_D_anglophone_sans_aucune_matiere_est_invalide(self):
        c = classe(self.an_fha, "French Ambassadors", Class.TRACK_ANGLOPHONE)
        r = self.enregistrer(self.admin_fha, c, [])
        self.assertEqual(r.status_code, 400, r.content[:300])
        self.assertIn("anglais", r.content.decode().lower())

    def test_E_bilingue_fr_et_en_est_valide(self):
        c = classe(self.an_fha, "French Explorers", Class.TRACK_BILINGUAL)
        r = self.enregistrer(self.admin_fha, c,
                             self.ids(self.fr_fha[:2] + self.en_fha[:2]))
        self.assertEqual(r.status_code, 200, r.content[:300])

    def test_F_bilingue_sans_anglais_est_invalide(self):
        c = classe(self.an_fha, "French Explorers", Class.TRACK_BILINGUAL)
        r = self.enregistrer(self.admin_fha, c, self.ids(self.fr_fha[:2]))
        self.assertEqual(r.status_code, 400, r.content[:300])
        self.assertIn("anglais", r.content.decode().lower())

    def test_G_bilingue_sans_francais_est_invalide(self):
        c = classe(self.an_fha, "French Explorers", Class.TRACK_BILINGUAL)
        r = self.enregistrer(self.admin_fha, c, self.ids(self.en_fha[:2]))
        self.assertEqual(r.status_code, 400, r.content[:300])
        self.assertIn("français", r.content.decode().lower())

    def test_H_feba_conserve_exactement_son_comportement(self):
        """§3 — l'académie bilingue par construction est inchangée."""
        c = classe(self.an_feba, "CM2-A", Class.TRACK_BILINGUAL)
        ok = self.enregistrer(self.admin_feba, c,
                              self.ids(self.fr_feba[:1] + self.en_feba[:1]))
        self.assertEqual(ok.status_code, 200, ok.content[:300])

        # FEBA exige toujours les deux langues.
        c2 = classe(self.an_feba, "CM2-B", Class.TRACK_BILINGUAL)
        for partiel in (self.ids(self.fr_feba), self.ids(self.en_feba)):
            r = self.enregistrer(self.admin_feba, c2, partiel)
            self.assertEqual(r.status_code, 400, r.content[:300])


class ParcoursMonolingueStrictTests(BaseRegles):
    """
    §2.1/§2.2 — un parcours monolingue n'accepte QUE sa langue.

    « Empêcher l'association accidentelle » : sans cette règle, une
    matière anglaise glissée dans une classe francophone ressort dans le
    bulletin, dans les moyennes et dans l'emploi du temps.
    """

    def test_une_classe_francophone_refuse_une_matiere_anglaise(self):
        c = classe(self.an_fha, "Junior Roots", Class.TRACK_FRANCOPHONE)
        r = self.enregistrer(self.admin_fha, c,
                             self.ids(self.fr_fha[:2] + self.en_fha[:1]))
        self.assertEqual(r.status_code, 400, r.content[:300])

    def test_une_classe_anglophone_refuse_une_matiere_francaise(self):
        c = classe(self.an_fha, "French Ambassadors", Class.TRACK_ANGLOPHONE)
        r = self.enregistrer(self.admin_fha, c,
                             self.ids(self.en_fha[:2] + self.fr_fha[:1]))
        self.assertEqual(r.status_code, 400, r.content[:300])


class CloisonnementDesMatieresTests(BaseRegles):
    """
    Les matières d'une autre académie ne s'assignent pas.

    Ni l'endpoint « matières » ni le serializer ne filtraient les
    identifiants reçus par l'académie : il suffisait d'en poster un.
    """

    def test_l_endpoint_matieres_refuse_une_matiere_d_une_autre_academie(self):
        c = classe(self.an_fha, "Junior Roots", Class.TRACK_FRANCOPHONE)
        r = self.enregistrer(self.admin_fha, c,
                             self.ids(self.fr_fha[:1] + self.fr_feba[:1]))
        self.assertEqual(r.status_code, 400, r.content[:300])
        self.assertNotIn(self.fr_feba[0], list(c.subjects.all()))

    def test_le_serializer_refuse_une_matiere_d_une_autre_academie(self):
        c = classe(self.an_fha, "Junior Roots", Class.TRACK_FRANCOPHONE)
        r = self.api(self.admin_fha).patch(
            f"/api/classes/{c.id}/",
            {"subject_ids": self.ids(self.fr_fha[:1] + self.fr_feba[:1])},
            format="json")
        self.assertEqual(r.status_code, 400, r.content[:300])
        self.assertNotIn(self.fr_feba[0], list(c.subjects.all()))


class MemeReglePartoutTests(BaseRegles):
    """
    §4 — une seule source de vérité.

    Les deux chemins d'écriture (écran Matières et formulaire de classe)
    doivent rendre le MÊME verdict. Deux validations divergentes, c'est
    exactement la contradiction qu'on corrige.
    """

    def _par_serializer(self, cls_obj, ids):
        return self.api(self.admin_fha).patch(
            f"/api/classes/{cls_obj.id}/", {"subject_ids": ids}, format="json")

    def test_les_deux_chemins_acceptent_la_meme_configuration(self):
        a = classe(self.an_fha, "Junior Roots A", Class.TRACK_FRANCOPHONE)
        b = classe(self.an_fha, "Junior Roots B", Class.TRACK_FRANCOPHONE)
        ids = self.ids(self.fr_fha)
        self.assertEqual(self.enregistrer(self.admin_fha, a, ids).status_code, 200)
        self.assertIn(self._par_serializer(b, ids).status_code, (200, 202))

    def test_les_deux_chemins_refusent_la_meme_configuration(self):
        a = classe(self.an_fha, "Amb A", Class.TRACK_ANGLOPHONE)
        b = classe(self.an_fha, "Amb B", Class.TRACK_ANGLOPHONE)
        ids = self.ids(self.fr_fha[:1])   # matière FR sur classe anglophone
        self.assertEqual(self.enregistrer(self.admin_fha, a, ids).status_code, 400)
        self.assertEqual(self._par_serializer(b, ids).status_code, 400)
