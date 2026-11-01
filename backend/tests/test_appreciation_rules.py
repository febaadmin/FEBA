"""
P0 — Appréciations administrables.

Avant : les seuils et les libellés (« PEUT MIEUX FAIRE », « EXCELLENT »…)
étaient codés en dur dans le backend ET recopiés côté React ; aucune
académie ne pouvait les adapter. Les vérifications portent sur le texte
réellement imprimé dans le PDF du bulletin, pas seulement sur l'API.
"""
import shutil
import tempfile
from decimal import Decimal

import fitz
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.accounts.models import CustomUser
from apps.bulletins.models import Bulletin
from apps.bulletins.pdf_generator import generate_bulletin
from apps.grades.models import AppreciationRule, Grade, get_appreciation, get_letter_grade

from .academy_fixtures import build_academy

URL = "/api/grades/appreciations/"


def pdf_text(bulletin):
    bulletin.refresh_from_db()
    with bulletin.pdf_file.open("rb") as fh:
        doc = fitz.open(stream=fh.read(), filetype="pdf")
    try:
        return " ".join(" ".join(page.get_text() for page in doc).split())
    finally:
        doc.close()


def rules_payload(school, cycle=""):
    return [{"id": r.id, "min_percent": str(r.min_percent), "label_fr": r.label_fr,
             "label_en": r.label_en, "is_active": r.is_active}
            for r in AppreciationRule.objects.filter(school=school, cycle=cycle)]


class Base(TestCase):
    def setUp(self):
        self.media = tempfile.mkdtemp()
        self._media = override_settings(MEDIA_ROOT=self.media)
        self._media.enable()
        # Primaire (bulletin /10) et secondaire (bulletin /20) : notes 16 et 12 sur 20.
        self.p = build_academy("PRI", "physical_primary")
        self.s = build_academy("SEC", "physical_secondary")
        self.client = APIClient()
        self.client.force_authenticate(self.p.admin)

    def tearDown(self):
        self._media.disable()
        shutil.rmtree(self.media, ignore_errors=True)

    def put(self, rules, client=None, cycle=""):
        return (client or self.client).put(URL, {"cycle": cycle, "rules": rules}, format="json")


class ReadAndPermissionsTests(Base):

    def test_consultation_du_bareme_de_son_academie(self):
        r = self.client.get(URL)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["academy"]["id"], self.p.school.pk)
        self.assertEqual([x["label_fr"] for x in r.data["rules"]][:3],
                         ["EXCELLENT", "TRÈS SATISFAISANT", "SATISFAISANT"])
        self.assertEqual(r.data["rules"][0]["min_percent"], "95.00")
        self.assertEqual(r.data["effective_origin"], "academy")

    def test_super_administrateur_doit_choisir_une_academie(self):
        su = CustomUser.objects.create_user(username="su", email="su@x.io", password="Pass1234!",
                                            role="superadmin", first_name="S", last_name="U")
        c = APIClient()
        c.force_authenticate(su)
        self.assertEqual(c.get(URL).status_code, 400)
        r = c.get(f"{URL}?school_id={self.s.school.pk}")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["academy"]["id"], self.s.school.pk)

    def test_droits_par_role(self):
        teacher = APIClient(); teacher.force_authenticate(self.p.teacher_user)
        parent = APIClient(); parent.force_authenticate(self.p.parent_user)
        student = APIClient(); student.force_authenticate(self.p.student_user)
        self.assertEqual(teacher.get(URL).status_code, 200)
        self.assertEqual(self.put(rules_payload(self.p.school), client=teacher).status_code, 403)
        for c in (parent, student):
            self.assertEqual(c.get(URL).status_code, 403)
            self.assertEqual(self.put(rules_payload(self.p.school), client=c).status_code, 403)

    def test_un_administrateur_ne_lit_ni_ne_modifie_une_autre_academie(self):
        r = self.client.get(f"{URL}?school_id={self.s.school.pk}")
        self.assertEqual(r.data["academy"]["id"], self.p.school.pk)        # paramètre ignoré
        foreign = rules_payload(self.s.school)
        foreign[0]["label_fr"] = "PIRATÉ"
        r = self.put(foreign)
        self.assertEqual(r.status_code, 404)
        self.assertFalse(AppreciationRule.objects.filter(label_fr="PIRATÉ").exists())
        self.assertEqual(AppreciationRule.objects.filter(school=self.s.school).count(), 9)


class EditTests(Base):

    def test_ajout_modification_suppression_persistes(self):
        rules = rules_payload(self.p.school)
        rules[0]["label_fr"] = "EXCELLENT !"                       # modification du texte
        rules[1]["min_percent"] = "87.50"                          # modification du seuil
        rules = [r for r in rules if r["label_fr"] != "FAIBLE"]    # suppression (inutilisée)
        rules.append({"min_percent": "99", "label_fr": "PARFAIT", "label_en": "PERFECT"})   # ajout
        r = self.put(rules)
        self.assertEqual(r.status_code, 200, r.data)
        stored = {x.label_fr: x.min_percent for x in AppreciationRule.objects.filter(school=self.p.school)}
        self.assertEqual(stored["PARFAIT"], Decimal("99"))
        self.assertEqual(stored["EXCELLENT !"], Decimal("95"))
        self.assertEqual(stored["TRÈS SATISFAISANT"], Decimal("87.5"))
        self.assertNotIn("FAIBLE", stored)
        self.assertNotIn("EXCELLENT", stored)
        # L'autre académie est intacte.
        self.assertEqual(rules_payload(self.s.school)[0]["label_fr"], "EXCELLENT")

    def test_validations(self):
        base = rules_payload(self.p.school)
        cases = {
            "seuil en double": [dict(base[0]), dict(base[1], min_percent=base[0]["min_percent"])] + base[2:],
            "pas de seuil à 0": [r for r in base if r["min_percent"] != "0.00"],
            "libellé vide": [dict(base[0], label_fr="  ")] + base[1:],
            "seuil > 100": [dict(base[0], min_percent="120")] + base[1:],
            "seuil négatif": base[:-1] + [dict(base[-1], min_percent="-1")],
            "libellé en double": [dict(base[0]), dict(base[1], label_fr="excellent")] + base[2:],
            "trop de décimales": [dict(base[0], min_percent="95.555")] + base[1:],
            "aucune active": [dict(r, is_active=False) for r in base],
        }
        for name, rules in cases.items():
            with self.subTest(cas=name):
                r = self.put(rules)
                self.assertEqual(r.status_code, 400, r.data)
                self.assertTrue(r.data["errors"])
        self.assertEqual(rules_payload(self.p.school), base)          # rien n'a changé

    def test_appreciation_utilisee_protegee_mais_desactivable(self):
        bulletin = generate_bulletin(self.p.student, "T1", self.p.year)
        used = bulletin.appreciation
        rules = rules_payload(self.p.school)
        r = self.put([x for x in rules if x["label_fr"] != used])
        self.assertEqual(r.status_code, 409)
        self.assertIn(used, r.data["errors"][0])
        r = self.put([dict(x, is_active=False) if x["label_fr"] == used else x for x in rules])
        # Désactiver ne doit pas créer de trou : le palier inférieur reprend l'intervalle.
        self.assertEqual(r.status_code, 200, r.data)
        self.assertFalse(AppreciationRule.objects.get(school=self.p.school, label_fr=used).is_active)

    def test_reinitialisation_exige_une_confirmation(self):
        AppreciationRule.objects.filter(school=self.p.school, label_fr="EXCELLENT").update(label_fr="TOP")
        self.assertEqual(self.client.post(f"{URL}reset/", {}, format="json").status_code, 400)
        r = self.client.post(f"{URL}reset/", {"confirm": True}, format="json")
        self.assertEqual(r.status_code, 200)
        labels = set(AppreciationRule.objects.filter(school=self.p.school).values_list("label_fr", flat=True))
        self.assertIn("EXCELLENT", labels)
        self.assertNotIn("TOP", labels)


class ScaleAndBoundaryTests(Base):

    def test_bornes_exactes_sur_20_et_sur_10(self):
        school = self.p.school
        for value, max_value, expected in [
            (19, 20, "EXCELLENT"), (Decimal("18.99"), 20, "TRÈS SATISFAISANT"),
            (Decimal("9.5"), 10, "EXCELLENT"), (Decimal("9.49"), 10, "TRÈS SATISFAISANT"),
            (17, 20, "TRÈS SATISFAISANT"), (Decimal("8.5"), 10, "TRÈS SATISFAISANT"),
            (11, 20, "PEUT MIEUX FAIRE"), (Decimal("5.5"), 10, "PEUT MIEUX FAIRE"),
            (0, 20, "TRÈS FAIBLE"), (20, 20, "EXCELLENT"),
        ]:
            with self.subTest(note=f"{value}/{max_value}"):
                self.assertEqual(get_appreciation(value, max_value, academy=school), expected)

    def test_apercu_identique_pour_un_meme_pourcentage(self):
        a = self.client.post(f"{URL}preview/", {"value": "9.5", "max_value": "10"}, format="json")
        b = self.client.post(f"{URL}preview/", {"value": "19", "max_value": "20"}, format="json")
        self.assertEqual(a.data["label_fr"], "EXCELLENT")
        self.assertEqual(b.data["label_fr"], "EXCELLENT")
        self.assertEqual(a.data["label_en"], "EXCELLENT")
        self.assertEqual(a.data["percent"], "95.00")
        bad = self.client.post(f"{URL}preview/", {"value": "21", "max_value": "20"}, format="json")
        self.assertEqual(bad.status_code, 400)

    def test_apercu_d_un_bareme_non_enregistre(self):
        draft = rules_payload(self.p.school)
        draft[0]["min_percent"] = "90"
        r = self.client.post(f"{URL}preview/", {"value": "18.2", "max_value": "20", "rules": draft},
                             format="json")
        self.assertEqual(r.data["label_fr"], "EXCELLENT")
        self.assertEqual(get_appreciation(Decimal("18.2"), academy=self.p.school), "TRÈS SATISFAISANT")

    def test_libelles_anglais(self):
        self.assertEqual(get_appreciation(12, academy=self.p.school, language="en"), "CAN DO BETTER")
        self.assertEqual(get_appreciation(12, academy=self.p.school), "PEUT MIEUX FAIRE")

    def test_matiere_non_notee_sans_appreciation(self):
        self.assertEqual(get_appreciation(None, academy=self.p.school), "-")


class BulletinRenderingTests(Base):

    def test_le_bulletin_imprime_le_libelle_configure(self):
        before = generate_bulletin(self.s.student, "T1", self.s.year)
        old_label, old_average = before.appreciation, before.average
        old_text = pdf_text(before)
        self.assertIn(old_label, old_text)
        # Moyenne pondérée (16×2 + 12×1) / 3 = 14,67/20 → 73,3 % → ACCEPTABLE.
        self.assertEqual(old_average, Decimal("14.67"))
        self.assertEqual(old_label, "ACCEPTABLE")

        rules = rules_payload(self.s.school)
        for rule in rules:
            if rule["label_fr"] == "ACCEPTABLE":
                rule["label_fr"] = "BIEN - EN PROGRÈS"
        client = APIClient()
        client.force_authenticate(self.s.admin)
        self.assertEqual(self.put(rules, client=client).status_code, 200)

        after = generate_bulletin(self.s.student, "T1", self.s.year)
        text = pdf_text(after)
        self.assertEqual(after.appreciation, "BIEN - EN PROGRÈS")
        self.assertIn("BIEN - EN PROGRÈS", text)
        # Notes, moyennes et lettres inchangées : seul le libellé a changé.
        self.assertEqual(after.average, old_average)
        self.assertEqual(get_letter_grade(after.average), get_letter_grade(old_average))
        self.assertIn("14.67/20", text)
        self.assertEqual(Grade.objects.filter(student=self.s.student).count(), 2)

    def test_primaire_sur_10_et_secondaire_sur_20(self):
        primary = pdf_text(generate_bulletin(self.p.student, "T1", self.p.year))
        secondary = pdf_text(generate_bulletin(self.s.student, "T1", self.s.year))
        self.assertIn("Moy. /10", primary)
        self.assertIn("8.00/10", primary)          # 16/20 affiché sur 10
        self.assertNotIn("Moy. /10", secondary)
        self.assertIn("Moy. /20", secondary)
        self.assertIn("16.00/20", secondary)
        # Même note, même pourcentage, même appréciation, quel que soit le barème.
        self.assertIn("SATISFAISANT", primary)
        self.assertIn("SATISFAISANT", secondary)

    def test_bareme_propre_a_un_cycle(self):
        """Un barème « lycée » s'applique au lycée, pas au collège."""
        rules = [dict(r, id=None, label_fr=f"LYC {r['label_fr']}") for r in rules_payload(self.s.school)]
        for r in rules:
            r.pop("id")
        client = APIClient()
        client.force_authenticate(self.s.admin)
        self.assertEqual(self.put(rules, client=client, cycle="lycee").status_code, 200)
        college = generate_bulletin(self.s.student, "T1", self.s.year)       # niveau 6ème : collège
        self.assertEqual(college.appreciation, "ACCEPTABLE")
        lycee_level = self.s.school.levels.get(name="Seconde")
        self.s.klass.level = lycee_level
        self.s.klass.save(update_fields=["level"])
        lycee = generate_bulletin(self.s.student, "T1", self.s.year)
        self.assertEqual(lycee.appreciation, "LYC ACCEPTABLE")
        self.assertIn("LYC ACCEPTABLE", pdf_text(lycee))

    def test_un_bulletin_deja_emis_garde_son_libelle(self):
        issued = generate_bulletin(self.p.student, "T1", self.p.year)
        label = issued.appreciation
        rules = rules_payload(self.p.school)
        for rule in rules:
            if rule["label_fr"] == label:
                rule["label_fr"] = "NOUVEAU LIBELLÉ"
        self.assertEqual(self.put(rules).status_code, 200)
        issued.refresh_from_db()
        self.assertEqual(issued.appreciation, label)
        self.assertIn(label, pdf_text(issued))
        self.assertEqual(Bulletin.objects.filter(student=self.p.student).count(), 1)

    def test_l_api_des_notes_suit_le_bareme_de_l_academie(self):
        AppreciationRule.objects.filter(school=self.p.school, label_fr="TRÈS SATISFAISANT").update(
            label_fr="TRÈS BIEN")
        rows = self.client.get("/api/grades/").data
        rows = rows.get("results", rows)
        by_value = {Decimal(str(r["value"])): r["appreciation"] for r in rows}
        self.assertEqual(by_value[Decimal("16")], "SATISFAISANT")    # 80 %
        self.assertEqual(by_value[Decimal("12")], "PEUT MIEUX FAIRE")  # 60 %
        AppreciationRule.objects.filter(school=self.p.school, label_fr="SATISFAISANT").update(
            label_fr="BIEN")
        rows = self.client.get("/api/grades/").data
        rows = rows.get("results", rows)
        self.assertIn("BIEN", [r["appreciation"] for r in rows])
