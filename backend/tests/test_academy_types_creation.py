"""
P0 — Création d'académies typées par le super administrateur.

Avant : aucun écran ne créait d'académie ; l'API acceptait un POST sans
type et sans initialisation (aucun niveau, aucun barème), un DELETE
effaçait en cascade élèves, notes et paiements, le code interne restait
modifiable, et un niveau créé sans cycle dans un lycée devenait
« primaire » — noté sur 10.
"""
import datetime
import importlib

from django.apps import apps as django_apps
from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import CustomUser
from apps.grades.grading import get_grading_scale
from apps.grades.models import AppreciationRule
from apps.payments.models import Payment
from apps.schools.academy_types import classify
from apps.schools.models import Level, School
from apps.students.models import Student
from apps.virtualclass.models import VirtualRoom
from apps.website.models import FHAEnrollmentApplication

URL = "/api/schools/schools/"


def payload(**overrides):
    data = {
        "name": "École Test Parakou", "code": "ecole_parakou", "academy_type": "physical_primary",
        "address": "Quartier Zongo, Parakou", "city": "Parakou", "country": "Bénin",
        "timezone": "Africa/Porto-Novo", "currency_code": "XOF", "default_language": "fr",
    }
    data.update(overrides)
    return data


class Base(TestCase):
    def setUp(self):
        self.su = CustomUser.objects.create_user(
            username="su", email="su@t.io", password="Pass1234!", role="superadmin",
            first_name="S", last_name="U")
        # Les migrations créent déjà les deux académies FEBA : on les reprend.
        self.feba, _ = School.objects.update_or_create(
            code="FEBA", defaults=dict(name="FEBA", address="Cotonou", entity_type="campus",
                                       academy_type=None))
        self.feba.levels.all().delete()
        Level.objects.create(school=self.feba, name="CP1", cycle="primaire", order=1)
        Level.objects.create(school=self.feba, name="6ème", cycle="college", order=7)
        self.fha, _ = School.objects.update_or_create(
            code="FEBA_FHA", defaults=dict(name="FEBA FHA", address="En ligne",
                                           entity_type="online", academy_type="online"))
        self.initial_count = School.objects.count()
        self.admin = CustomUser.objects.create_user(
            username="adm", email="adm@t.io", password="Pass1234!", role="admin",
            school=self.feba, first_name="A", last_name="D")
        self.client = APIClient()
        self.client.force_authenticate(self.su)

    def create(self, **overrides):
        return self.client.post(URL, payload(**overrides), format="json")


class CreationByTypeTests(Base):

    def test_creation_des_trois_types(self):
        expected = {
            "online": ("online", []),
            "physical_primary": ("campus", ["maternelle", "maternelle"] + ["primaire"] * 6),
            "physical_secondary": ("campus", ["college"] * 4 + ["lycee"] * 3),
        }
        for index, (academy_type, (entity_type, cycles)) in enumerate(expected.items()):
            with self.subTest(type=academy_type):
                r = self.create(name=f"Académie {index}", code=f"AC_{index}", academy_type=academy_type)
                self.assertEqual(r.status_code, 201, r.data)
                school = School.objects.get(pk=r.data["id"])
                self.assertEqual(school.academy_type, academy_type)
                self.assertEqual(school.entity_type, entity_type)
                self.assertEqual(school.code, f"AC_{index}")
                self.assertEqual(list(school.levels.order_by("order").values_list("cycle", flat=True)),
                                 cycles)
                self.assertEqual(r.data["setup_status"]["academy_id"], school.pk)

    def test_fonctionnalites_selon_le_type(self):
        online = School.objects.get(pk=self.create(code="ON", name="On", academy_type="online").data["id"])
        primary = School.objects.get(pk=self.create(code="PR", name="Pr").data["id"])
        self.assertTrue(online.has_feature("placement_tests"))
        self.assertTrue(online.has_feature("online_lessons"))
        self.assertFalse(primary.has_feature("placement_tests"))
        self.assertTrue(primary.has_feature("payments"))

    def test_bareme_d_appreciations_copie_et_independant(self):
        a = School.objects.get(pk=self.create(code="AA", name="AA").data["id"])
        b = School.objects.get(pk=self.create(code="BB", name="BB").data["id"])
        self.assertEqual(AppreciationRule.objects.filter(school=a).count(), 9)
        self.assertEqual(AppreciationRule.objects.filter(school=b).count(), 9)
        AppreciationRule.objects.filter(school=a, label_fr="EXCELLENT").update(label_fr="REMARQUABLE")
        self.assertTrue(AppreciationRule.objects.filter(school=b, label_fr="EXCELLENT").exists())
        self.assertFalse(AppreciationRule.objects.filter(school=b, label_fr="REMARQUABLE").exists())

    def test_aucune_donnee_operationnelle_n_est_copiee(self):
        before = {
            "students": Student.objects.count(), "payments": Payment.objects.count(),
            "fha": FHAEnrollmentApplication.objects.count(), "rooms": VirtualRoom.objects.count(),
            "users": CustomUser.objects.count(),
        }
        r = self.create(academy_type="online", code="NEW_ONLINE", name="Nouvelle en ligne")
        school = School.objects.get(pk=r.data["id"])
        after = {
            "students": Student.objects.count(), "payments": Payment.objects.count(),
            "fha": FHAEnrollmentApplication.objects.count(), "rooms": VirtualRoom.objects.count(),
            "users": CustomUser.objects.count(),
        }
        self.assertEqual(before, after)
        self.assertFalse(school.years.exists())       # aucune année inventée
        self.assertFalse(school.branding_versions.exists())   # aucun logo d'une autre académie

    def test_premiere_annee_scolaire_facultative(self):
        r = self.create(school_year_name="2026-2027", school_year_start="2026-09-01",
                        school_year_end="2027-07-31")
        self.assertEqual(r.status_code, 201, r.data)
        year = School.objects.get(pk=r.data["id"]).years.get()
        self.assertTrue(year.is_current)
        self.assertEqual(year.start_date, datetime.date(2026, 9, 1))

    def test_les_academies_existantes_ne_changent_pas(self):
        levels = list(self.feba.levels.values_list("id", "cycle"))
        self.create()
        self.assertEqual(list(self.feba.levels.values_list("id", "cycle")), levels)
        self.feba.refresh_from_db()
        self.assertIsNone(self.feba.academy_type)

    def test_la_nouvelle_academie_est_proposee_au_super_administrateur(self):
        new_id = self.create().data["id"]
        ctx = self.client.get("/api/auth/entity-context/").data
        self.assertIn(new_id, [e["id"] for e in ctx["entities"]])
        self.assertEqual({e["id"]: e["academy_type"] for e in ctx["entities"]}[new_id], "physical_primary")
        r = self.client.post("/api/auth/entity-context/switch/", {"entity_id": new_id}, format="json")
        self.assertEqual(r.status_code, 200)
        levels = self.client.get("/api/schools/levels/").data
        rows = levels.get("results", levels)
        self.assertEqual(len(rows), 8)
        self.assertTrue(all(row["school"] == new_id for row in rows))


class CreationValidationTests(Base):

    def test_champs_obligatoires(self):
        for field, message in [("academy_type", "Le type d'académie est obligatoire."),
                               ("name", "Le nom de l'académie est obligatoire."),
                               ("code", "Le code interne est obligatoire."),
                               ("address", "L'adresse est obligatoire.")]:
            with self.subTest(champ=field):
                data = payload()
                del data[field]
                r = self.client.post(URL, data, format="json")
                self.assertEqual(r.status_code, 400)
                self.assertEqual(str(r.data[field][0]), message)
        self.assertEqual(School.objects.count(), self.initial_count)

    def test_type_inconnu_refuse(self):
        r = self.create(academy_type="university")
        self.assertEqual(r.status_code, 400)
        self.assertIn("academy_type", r.data)

    def test_code_en_double_refuse_sans_tenir_compte_de_la_casse(self):
        r = self.create(code="feba_fha")
        self.assertEqual(r.status_code, 400)
        self.assertIn("déjà utilisé", str(r.data["code"][0]))

    def test_code_invalide_refuse(self):
        for code in ("a", "avec espace", "é_accent", "X" * 40, "-DEBUT"):
            with self.subTest(code=code):
                self.assertEqual(self.create(code=code).status_code, 400)

    def test_nom_en_double_refuse(self):
        self.assertEqual(self.create(name="feba", code="AUTRE").status_code, 400)

    def test_fuseau_et_annee_incoherents_refuses(self):
        self.assertEqual(self.create(timezone="Mars/Olympus").status_code, 400)
        self.assertEqual(self.create(school_year_name="2026-2027").status_code, 400)
        self.assertEqual(self.create(school_year_name="X", school_year_start="2027-01-01",
                                     school_year_end="2026-01-01").status_code, 400)
        self.assertEqual(School.objects.count(), self.initial_count)

    def test_seul_le_super_administrateur_cree(self):
        for role in ("admin", "teacher", "parent", "student"):
            with self.subTest(role=role):
                user = CustomUser.objects.create_user(
                    username=f"x{role}", email=f"x{role}@t.io", password="Pass1234!", role=role,
                    school=self.feba, first_name="X", last_name="Y")
                c = APIClient()
                c.force_authenticate(user)
                self.assertEqual(c.post(URL, payload(code=f"C_{role}"), format="json").status_code, 403)
        self.assertEqual(School.objects.count(), self.initial_count)


class ModificationTests(Base):

    def test_le_code_interne_est_immuable(self):
        r = self.client.patch(f"{URL}{self.fha.pk}/", {"code": "FEBA", "name": "FHA renommée"},
                              format="json")
        self.assertEqual(r.status_code, 200)
        self.fha.refresh_from_db()
        self.assertEqual(self.fha.code, "FEBA_FHA")
        self.assertEqual(self.fha.name, "FHA renommée")

    def test_academie_mixte_non_classee_avec_motif(self):
        data = self.client.get(f"{URL}{self.feba.pk}/").data
        self.assertIsNone(data["academy_type"])
        self.assertIsNone(data["classification"]["suggested_type"])
        self.assertIn("primaire ET de secondaire", data["classification"]["reason"])

    def test_classement_refuse_si_des_niveaux_le_contredisent(self):
        r = self.client.patch(f"{URL}{self.feba.pk}/", {"academy_type": "physical_primary"}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("6ème", str(r.data["academy_type"]))
        self.feba.refresh_from_db()
        self.assertIsNone(self.feba.academy_type)

    def test_classement_accepte_quand_les_niveaux_le_permettent(self):
        self.feba.levels.filter(cycle="college").delete()
        r = self.client.patch(f"{URL}{self.feba.pk}/", {"academy_type": "physical_primary"}, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        self.feba.refresh_from_db()
        self.assertEqual(self.feba.academy_type, "physical_primary")

    def test_type_et_entity_type_ne_peuvent_pas_se_contredire(self):
        r = self.client.patch(f"{URL}{self.fha.pk}/", {"entity_type": "campus"}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertEqual(self.client.patch(f"{URL}{self.fha.pk}/", {"academy_type": None},
                                           format="json").status_code, 400)

    def test_l_administrateur_ne_change_pas_le_type(self):
        c = APIClient()
        c.force_authenticate(self.admin)
        c.patch(f"{URL}{self.feba.pk}/", {"academy_type": "online"}, format="json")
        self.feba.refresh_from_db()
        self.assertIsNone(self.feba.academy_type)

    def test_desactivation_conserve_tout(self):
        r = self.client.patch(f"{URL}{self.feba.pk}/", {"is_active": False}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(School.objects.filter(pk=self.feba.pk, is_active=False).exists())


class DeletionTests(Base):

    def test_academie_avec_donnees_non_supprimable(self):
        r = self.client.delete(f"{URL}{self.feba.pk}/")
        self.assertEqual(r.status_code, 409)
        self.assertIn("utilisateurs", r.data["blockers"])
        self.assertTrue(School.objects.filter(pk=self.feba.pk).exists())

    def test_academie_vide_supprimable(self):
        new_id = self.create(code="ERREUR", name="Créée par erreur").data["id"]
        self.assertEqual(self.client.delete(f"{URL}{new_id}/").status_code, 204)
        self.assertFalse(School.objects.filter(pk=new_id).exists())


class LevelCycleRulesTests(Base):

    def setUp(self):
        super().setUp()
        self.secondary = School.objects.get(pk=self.create(
            code="LYCEE", name="Lycée", academy_type="physical_secondary").data["id"])
        self.primary = School.objects.get(pk=self.create(code="PRIM", name="Primaire").data["id"])

    def level(self, school, **data):
        return self.client.post(f"/api/schools/levels/?school_id={school.pk}", data, format="json")

    def test_un_niveau_sans_cycle_dans_un_lycee_est_au_college(self):
        r = self.level(self.secondary, name="Terminale bis")
        self.assertEqual(r.status_code, 201, r.data)
        level = Level.objects.get(pk=r.data["id"])
        self.assertEqual(level.cycle, "college")
        self.assertEqual(get_grading_scale(level), 20)

    def test_cycle_incompatible_refuse(self):
        self.assertEqual(self.level(self.secondary, name="CP", cycle="primaire").status_code, 400)
        self.assertEqual(self.level(self.primary, name="2nde", cycle="lycee").status_code, 400)
        level = self.primary.levels.first()
        r = self.client.patch(f"/api/schools/levels/{level.pk}/?school_id={self.primary.pk}",
                              {"cycle": "college"}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_baremes_des_niveaux_initialises(self):
        for level in self.secondary.levels.all():
            self.assertEqual(get_grading_scale(level), 20, level.name)
        for level in self.primary.levels.all():
            self.assertEqual(get_grading_scale(level), 10, level.name)

    def test_academie_non_classee_garde_tous_les_cycles(self):
        r = self.level(self.feba, name="Seconde", cycle="lycee")
        self.assertEqual(r.status_code, 201, r.data)


class MigrationClassificationTests(TestCase):

    def test_regle_de_classement(self):
        self.assertEqual(classify("online", {"primaire"})[0], "online")
        self.assertEqual(classify("campus", {"maternelle", "primaire"})[0], "physical_primary")
        self.assertEqual(classify("campus", {"college", "lycee"})[0], "physical_secondary")
        self.assertIsNone(classify("campus", {"primaire", "college"})[0])
        self.assertIsNone(classify("campus", set())[0])

    def test_la_migration_classe_d_apres_les_donnees(self):
        online = School.objects.create(name="O", code="O1", address="x", entity_type="online")
        primary = School.objects.create(name="P", code="P1", address="x")
        Level.objects.create(school=primary, name="CE1", cycle="primaire")
        mixed = School.objects.create(name="M", code="M1", address="x")
        Level.objects.create(school=mixed, name="CE1", cycle="primaire")
        Level.objects.create(school=mixed, name="6e", cycle="college")
        empty = School.objects.create(name="E", code="E1", address="x")
        migration = importlib.import_module("apps.schools.migrations.0020_academy_type")
        migration.classify_existing(django_apps, None)
        types = dict(School.objects.values_list("code", "academy_type"))
        self.assertEqual(types["O1"], "online")
        self.assertEqual(types["P1"], "physical_primary")
        self.assertIsNone(types["M1"])
        self.assertIsNone(types["E1"])
        for school in (online, primary, mixed, empty):
            school.refresh_from_db()
        self.assertEqual(mixed.entity_type, "campus")
