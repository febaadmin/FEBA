"""
Programme linguistique des académies : français uniquement, anglais
uniquement, bilingue.

Distinct de `default_language` (langue de l'interface). Il décide, CÔTÉ
SERVEUR et pour chaque chemin d'écriture : langues des matières, parcours des
classes, notes (unitaires et en masse), créneaux, et sections du bulletin.

Chaque scénario passe par l'API réelle (création d'académie par le super
administrateur, puis l'administrateur de l'académie), et les bulletins sont
de vrais PDF relus. Les barèmes /10 (primaire) et /20 (secondaire) sont
vérifiés sur le document imprimé.
"""
import datetime
from decimal import Decimal
from io import BytesIO

from django.apps import apps as django_apps
from django.core.management import call_command
from django.test import TestCase
from pypdf import PdfReader
from rest_framework.test import APIClient

from apps.accounts.models import CustomUser
from apps.bulletins.pdf_generator import render_bulletin_pdf
from apps.classes.models import Class
from apps.grades.models import Grade
from apps.schedule.models import ClassSchedule
from apps.schools.curriculum import classify_curriculum
from apps.schools.models import School
from apps.students.models import Student, StudentEnrollment
from apps.subjects.models import Subject
from apps.teachers.models import Teacher

URL = "/api/schools/schools/"
SECTION_FR = "PARTIE FRANÇAISE"
SECTION_EN = "ENGLISH SECTION"
MOY_BI = "Moyenne Bilingue"


def pdf_text(content):
    return "\n".join(p.extract_text() or "" for p in PdfReader(BytesIO(content)).pages)


class Base(TestCase):
    """Trois académies créées par l'écran « Académies » (API), une par mode."""

    @classmethod
    def setUpTestData(cls):
        cls.root = CustomUser.objects.create_user(
            username="root", email="root@curr.test", password="Pass1234!", role="superadmin")
        cls.academies = {}
        for code, academy_type, mode in (
                ("TESTETE_FR", "physical_primary", "french_only"),
                ("TESTETE_EN", "physical_secondary", "english_only"),
                ("TESTETE_BI", "physical_primary", "bilingual"),
                ("TESTETE_BI_ONLINE", "online", "bilingual")):
            client = APIClient()
            client.force_authenticate(cls.root)
            r = client.post(URL, {
                "name": f"Académie Évangélique {code}", "code": code, "academy_type": academy_type,
                "curriculum_language_mode": mode, "address": "Quartier Yimporima", "city": "Natitingou", "country": "Bénin",
                "school_year_name": "2026-2027", "school_year_start": "2026-09-01",
                "school_year_end": "2027-07-31"}, format="json")
            assert r.status_code == 201, r.data
            school = School.objects.get(code=code)
            admin = CustomUser.objects.create_user(
                username=f"adm_{code}".lower(), email=f"adm.{code}@curr.test".lower(),
                password="Pass1234!", role="admin", school=school)
            cls.academies[code] = (school, admin)

    def client_for(self, code):
        client = APIClient()
        client.force_authenticate(self.academies[code][1])
        return client

    def school(self, code):
        return self.academies[code][0]

    def year(self, code):
        return self.school(code).years.get(is_current=True)

    def level(self, code):
        school = self.school(code)
        return (school.levels.exclude(cycle="maternelle").order_by("order").first()
                or school.levels.create(name="Groupe 1", cycle="primaire", order=1))

    def make_class(self, code, track=None, name="Classe A"):
        payload = {"name": name, "level": self.level(code).pk, "school_year": self.year(code).pk,
                   "max_students": 30}
        if track:
            payload["language_track"] = track
        return self.client_for(code).post("/api/classes/", payload, format="json")


class CreationTests(Base):

    def test_programme_enregistre_et_expose_par_l_api(self):
        for code, mode in (("TESTETE_FR", "french_only"), ("TESTETE_EN", "english_only"),
                           ("TESTETE_BI", "bilingual")):
            with self.subTest(code=code):
                self.assertEqual(self.school(code).curriculum_language_mode, mode)
                ctx = self.client_for(code).get("/api/auth/entity-context/").data["active_entity"]
                self.assertEqual(ctx["curriculum_language_mode"], mode)
        fr = self.client_for("TESTETE_FR").get("/api/auth/entity-context/").data["active_entity"]
        self.assertEqual(fr["subject_languages"], ["fr"])
        self.assertEqual(fr["class_tracks"], [Class.TRACK_FRANCOPHONE])
        en = self.client_for("TESTETE_EN").get("/api/auth/entity-context/").data["active_entity"]
        self.assertEqual(en["subject_languages"], ["en"])
        self.assertEqual(en["class_tracks"], [Class.TRACK_ANGLOPHONE])
        bi = self.client_for("TESTETE_BI").get("/api/auth/entity-context/").data["active_entity"]
        self.assertEqual(bi["subject_languages"], ["fr", "en", "bilingual"])
        # Académie présentielle bilingue : parcours monolingues non permis.
        self.assertEqual(bi["class_tracks"], [Class.TRACK_BILINGUAL])
        online = self.client_for("TESTETE_BI_ONLINE").get("/api/auth/entity-context/").data["active_entity"]
        self.assertEqual(online["class_tracks"],
                         [Class.TRACK_BILINGUAL, Class.TRACK_FRANCOPHONE, Class.TRACK_ANGLOPHONE])

    def test_programme_obligatoire_et_valeur_inconnue_refusee(self):
        client = APIClient()
        client.force_authenticate(self.root)
        count = School.objects.count()
        base = {"name": "Sans programme", "code": "SANS_PROG", "academy_type": "physical_primary", "city": "X", "country": "Bénin",
                "address": "X"}
        r = client.post(URL, base, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("programme linguistique est obligatoire", str(r.data["curriculum_language_mode"][0]))
        r = client.post(URL, {**base, "curriculum_language_mode": "spanish_only"}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertEqual(School.objects.count(), count)

    def test_l_administrateur_d_academie_ne_change_pas_le_programme(self):
        school, _ = self.academies["TESTETE_FR"]
        r = self.client_for("TESTETE_FR").patch(f"{URL}{school.pk}/", {"curriculum_language_mode": "bilingual"},
                                                format="json")
        self.assertIn(r.status_code, (200, 403))
        school.refresh_from_db()
        self.assertEqual(school.curriculum_language_mode, "french_only")


class SubjectTests(Base):

    def post(self, code, language, name="Matière"):
        return self.client_for(code).post("/api/subjects/", {
            "school": self.school(code).pk, "name": name, "code": f"{language}-{name}"[:20],
            "coefficient": 2, "language": language}, format="json")

    def test_langues_admises_par_mode(self):
        cases = {
            "TESTETE_FR": {"fr": 201, "en": 400, "bilingual": 400},
            "TESTETE_EN": {"fr": 400, "en": 201, "bilingual": 400},
            "TESTETE_BI": {"fr": 201, "en": 201, "bilingual": 201},
        }
        for code, expected in cases.items():
            for language, status_code in expected.items():
                with self.subTest(code=code, language=language):
                    r = self.post(code, language, name=f"M {language}")
                    self.assertEqual(r.status_code, status_code, r.data)
                    if status_code == 400:
                        self.assertIn("n'y est pas admise", str(r.data))
        self.assertFalse(Subject.objects.filter(school=self.school("TESTETE_FR")).exclude(language="fr").exists())
        self.assertFalse(Subject.objects.filter(school=self.school("TESTETE_EN")).exclude(language="en").exists())

    def test_changement_de_langue_refuse_si_une_classe_ne_l_enseigne_pas(self):
        r = self.post("TESTETE_BI_ONLINE", "fr", name="Lecture")
        subject = Subject.objects.get(pk=r.data["id"])
        klass = self.make_class("TESTETE_BI_ONLINE", Class.TRACK_FRANCOPHONE).data
        Class.objects.get(pk=klass["id"]).subjects.add(subject)
        r = self.client_for("TESTETE_BI_ONLINE").patch(f"/api/subjects/{subject.pk}/", {"language": "en"},
                                                       format="json")
        self.assertEqual(r.status_code, 400)
        subject.refresh_from_db()
        self.assertEqual(subject.language, "fr")


class ClassTrackTests(Base):

    def test_parcours_par_defaut_et_parcours_refuses(self):
        r = self.make_class("TESTETE_FR")
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(Class.objects.get(pk=r.data["id"]).language_track, Class.TRACK_FRANCOPHONE)
        self.assertEqual(self.make_class("TESTETE_FR", Class.TRACK_BILINGUAL, "B").status_code, 400)
        self.assertEqual(self.make_class("TESTETE_FR", Class.TRACK_ANGLOPHONE, "C").status_code, 400)

        r = self.make_class("TESTETE_EN")
        self.assertEqual(Class.objects.get(pk=r.data["id"]).language_track, Class.TRACK_ANGLOPHONE)
        self.assertEqual(self.make_class("TESTETE_EN", Class.TRACK_FRANCOPHONE, "B").status_code, 400)

        # Bilingue présentiel : monolingue interdit (politique de l'académie).
        self.assertEqual(self.make_class("TESTETE_BI").data["language_track"], Class.TRACK_BILINGUAL)
        r = self.make_class("TESTETE_BI", Class.TRACK_FRANCOPHONE, "B")
        self.assertEqual(r.status_code, 400)
        self.assertIn("non admis", str(r.data))
        # Bilingue en ligne : la politique de l'académie autorise le monolingue.
        self.assertEqual(self.make_class("TESTETE_BI_ONLINE", Class.TRACK_FRANCOPHONE).status_code, 201)

    def test_copie_d_annee_conserve_le_parcours(self):
        """Défaut corrigé : les classes copiées devenaient toutes bilingues."""
        code = "TESTETE_BI_ONLINE"
        source = self.year(code)
        klass = self.make_class(code, Class.TRACK_ANGLOPHONE, "Junior EN").data
        target = self.school(code).years.create(name="2027-2028", start_date=datetime.date(2027, 9, 1),
                                                end_date=datetime.date(2028, 7, 31))
        r = self.client_for(code).post("/api/classes/copy-from-year/",
                                       {"source_year_id": source.pk, "target_year_id": target.pk},
                                       format="json")
        self.assertIn(r.status_code, (200, 201), r.data)
        copy = Class.objects.get(school_year=target, name="Junior EN")
        self.assertEqual(copy.language_track, Class.TRACK_ANGLOPHONE)
        self.assertNotEqual(copy.pk, klass["id"])


class GradeFixture(Base):
    """Élève, classe et matières (créées par l'API) dans une académie."""

    def setup_pupil(self, code, subjects, track=None):
        client = self.client_for(code)
        created = []
        for name, language, coefficient in subjects:
            r = client.post("/api/subjects/", {"school": self.school(code).pk, "name": name,
                                               "code": name[:20], "coefficient": coefficient,
                                               "language": language}, format="json")
            assert r.status_code == 201, r.data
            created.append(Subject.objects.get(pk=r.data["id"]))
        klass = Class.objects.get(pk=self.make_class(code, track, name=f"Classe {code}").data["id"])
        klass.subjects.set(created)
        school, year = self.school(code), self.year(code)
        teacher_user = CustomUser.objects.create_user(
            username=f"t_{code}".lower(), email=f"t.{code}@curr.test".lower(), password="Pass1234!",
            role="teacher", school=school)
        teacher = Teacher.objects.create(user=teacher_user)
        pupil = Student.objects.create(school=school, first_name="Zoé-Hélène", last_name="Œuvray",
                                       current_class=klass, school_year=year, gender="F")
        StudentEnrollment.objects.create(student=pupil, school_year=year, class_obj=klass)
        return pupil, klass, created, teacher

    def grade(self, code, pupil, subject, value, period="T1"):
        return self.client_for(code).post("/api/grades/", {
            "student": pupil.pk, "subject": subject.pk, "school_year": self.year(code).pk,
            "period": period, "value": value}, format="json")


class GradeWriteTests(GradeFixture):

    def test_note_refusee_hors_programme_meme_si_la_matiere_existe_deja(self):
        """Matière anglaise ANTÉRIEURE (créée avant le programme) : plus de nouvelle note."""
        pupil, klass, (fr,), _ = self.setup_pupil("TESTETE_FR", [("Français", "fr", 2)])
        legacy_en = Subject.objects.create(school=self.school("TESTETE_FR"), name="Reading",
                                           code="RD", coefficient=1, language="en")
        self.assertEqual(self.grade("TESTETE_FR", pupil, fr, 14).status_code, 201)
        r = self.grade("TESTETE_FR", pupil, legacy_en, 14)
        self.assertEqual(r.status_code, 400)
        self.assertIn("n'y est pas admise", str(r.data))
        # En masse : refus par ligne, rien d'enregistré pour la ligne fautive.
        r = self.client_for("TESTETE_FR").post("/api/grades/bulk_save/", {"grades": [
            {"student": pupil.pk, "subject": legacy_en.pk, "school_year": self.year("TESTETE_FR").pk,
             "period": "T1", "value": 12},
            {"student": pupil.pk, "subject": fr.pk, "school_year": self.year("TESTETE_FR").pk,
             "period": "T1", "value": 16}]}, format="json")
        self.assertEqual(r.data["saved"], 1, r.data)
        self.assertEqual(len(r.data["errors"]), 1)
        self.assertFalse(Grade.objects.filter(subject=legacy_en).exists())

    def test_note_refusee_si_la_classe_n_enseigne_pas_la_langue(self):
        code = "TESTETE_BI_ONLINE"
        pupil, klass, (fr, en), _ = self.setup_pupil(
            code, [("Français oral", "fr", 2), ("English oral", "en", 1)], track=Class.TRACK_FRANCOPHONE)
        self.assertEqual(self.grade(code, pupil, fr, 15).status_code, 201)
        r = self.grade(code, pupil, en, 15)
        self.assertEqual(r.status_code, 400)
        self.assertIn("n'enseigne pas de matière anglaise", str(r.data))

    def test_creneau_refuse_hors_programme(self):
        code = "TESTETE_FR"
        pupil, klass, (fr,), teacher = self.setup_pupil(code, [("Français", "fr", 2)])
        legacy_en = Subject.objects.create(school=self.school(code), name="Reading", code="RD",
                                           coefficient=1, language="en")
        payload = {"cls": klass.pk, "school_year": self.year(code).pk, "day_of_week": 1,
                   "start_time": "08:00", "end_time": "09:00"}
        client = self.client_for(code)
        r = client.post("/api/schedule/", {**payload, "subject": legacy_en.pk}, format="json")
        self.assertEqual(r.status_code, 400, r.data)
        self.assertFalse(ClassSchedule.objects.filter(subject=legacy_en).exists())
        r = client.post("/api/schedule/", {**payload, "subject": fr.pk}, format="json")
        self.assertEqual(r.status_code, 201, r.data)


class BulletinTests(GradeFixture):
    """Vrais PDF, relus : sections, moyennes, barèmes /10 et /20."""

    def test_francais_uniquement_primaire_sur_10(self):
        code = "TESTETE_FR"
        pupil, klass, (fr, maths, chant), _ = self.setup_pupil(
            code, [("Lecture", "fr", 3), ("Mathématiques", "fr", 2), ("Chant", "fr", 1)])
        self.grade(code, pupil, fr, 16)      # /20 interne → 8/10
        self.grade(code, pupil, maths, 12)   # → 6/10 ; « Chant » sans note
        avg = Grade.calculate_average(pupil, self.year(code), "T1")
        self.assertEqual(Decimal(avg), Decimal("14.40"))   # (16×3 + 12×2) / 5 ; note absente ignorée
        bilingual = Grade.calculate_bilingual_averages(pupil, self.year(code), "T1")
        self.assertIsNone(bilingual["en_average"])
        self.assertEqual(Decimal(bilingual["bilingual_average"]), Decimal(bilingual["fr_average"]))  # pas de 60/40
        text = pdf_text(render_bulletin_pdf(pupil, "T1", self.year(code))[0])
        self.assertIn(SECTION_FR, text)
        self.assertNotIn(SECTION_EN, text)
        self.assertNotIn(MOY_BI, text)
        self.assertNotIn("60%", text)
        self.assertIn("7.20/10", text)       # 14,40/20 imprimé sur 10

    def test_anglais_uniquement_secondaire_sur_20(self):
        code = "TESTETE_EN"
        pupil, klass, (eng, sci), _ = self.setup_pupil(code, [("English", "en", 4), ("Science", "en", 2)])
        self.grade(code, pupil, eng, 15)
        self.grade(code, pupil, sci, 9)
        self.assertEqual(Decimal(Grade.calculate_average(pupil, self.year(code), "T1")), Decimal("13.00"))
        text = pdf_text(render_bulletin_pdf(pupil, "T1", self.year(code))[0])
        self.assertIn(SECTION_EN, text)
        self.assertNotIn(SECTION_FR, text)
        self.assertNotIn(MOY_BI, text)
        self.assertIn("13.00/20", text)

    def test_bilingue_60_40_et_matiere_commune_comptee_une_fois(self):
        code = "TESTETE_BI"
        pupil, klass, (fr, en, common), _ = self.setup_pupil(
            code, [("Dictée", "fr", 2), ("Spelling", "en", 2), ("Éducation physique", "bilingual", 1)])
        self.assertEqual(self.grade(code, pupil, fr, 15).status_code, 201)
        self.assertEqual(self.grade(code, pupil, en, 10).status_code, 201)
        self.assertEqual(self.grade(code, pupil, common, 20).status_code, 201)
        year = self.year(code)
        bilingual = Grade.calculate_bilingual_averages(pupil, year, "T1")
        self.assertEqual(Decimal(bilingual["fr_average"]), Decimal("15"))
        self.assertEqual(Decimal(bilingual["en_average"]), Decimal("10"))
        self.assertEqual(Decimal(bilingual["bilingual_average"]), Decimal("13.00"))   # 15×0,6 + 10×0,4
        # Moyenne générale : la matière commune compte UNE fois (15×2 + 10×2 + 20×1) / 5.
        self.assertEqual(Decimal(Grade.calculate_average(pupil, year, "T1")), Decimal("14.00"))
        text = pdf_text(render_bulletin_pdf(pupil, "T1", year)[0])
        self.assertIn(SECTION_FR, text)
        self.assertIn(SECTION_EN, text)
        self.assertIn(MOY_BI, text)
        self.assertIn("Éducation physique", text)
        self.assertEqual(text.count("Éducation physique"), 1)   # une seule ligne, pas de double comptage


class ModeChangeTests(GradeFixture):

    def patch(self, code, **data):
        client = APIClient()
        client.force_authenticate(self.root)
        return client.patch(f"{URL}{self.school(code).pk}/", data, format="json")

    def test_diagnostic_puis_confirmation_sans_suppression(self):
        code = "TESTETE_BI_ONLINE"
        pupil, klass, (fr, en), _ = self.setup_pupil(code, [("Dictée", "fr", 2), ("Spelling", "en", 1)])
        self.grade(code, pupil, en, 12)
        client = APIClient()
        client.force_authenticate(self.root)
        diag = client.get(f"{URL}{self.school(code).pk}/language-diagnostic/", {"mode": "french_only"}).data
        self.assertFalse(diag["ok"])
        self.assertEqual([s["name"] for s in diag["subjects"]], ["Spelling"])
        self.assertEqual(diag["grades"], 1)
        self.assertEqual(diag["classes"][0]["name"], klass.name)

        r = self.patch(code, curriculum_language_mode="french_only")
        self.assertEqual(r.status_code, 400)
        self.assertIn("Rien n'a été modifié", str(r.data["curriculum_language_mode"]))
        self.assertEqual(str(r.data["diagnostic"]["grades"]), "1")
        self.assertNotIn("ok", r.data["diagnostic"])
        self.assertEqual(School.objects.get(code=code).curriculum_language_mode, "bilingual")

        r = self.patch(code, curriculum_language_mode="french_only", confirm_curriculum_change=True)
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(School.objects.get(code=code).curriculum_language_mode, "french_only")
        # Rien de supprimé ni de converti ; le parcours stocké est aligné.
        self.assertTrue(Subject.objects.filter(pk=en.pk, language="en").exists())
        self.assertEqual(Grade.objects.filter(subject=en, is_deleted=False).count(), 1)
        klass.refresh_from_db()
        self.assertEqual(klass.language_track, Class.TRACK_FRANCOPHONE)
        self.assertIn(en, klass.subjects.all())
        # Et plus de nouvelle note anglaise.
        self.assertEqual(self.grade(code, pupil, en, 14).status_code, 400)

    def test_retour_a_vide_refuse_et_mode_inconnu_refuse(self):
        self.assertEqual(self.patch("TESTETE_FR", curriculum_language_mode=None).status_code, 400)
        client = APIClient()
        client.force_authenticate(self.root)
        r = client.get(f"{URL}{self.school('TESTETE_FR').pk}/language-diagnostic/", {"mode": "x"})
        self.assertEqual(r.status_code, 400)
        r = self.client_for("TESTETE_FR").get(
            f"{URL}{self.school('TESTETE_FR').pk}/language-diagnostic/", {"mode": "bilingual"})
        self.assertEqual(r.status_code, 403)      # réservé au super administrateur

    def test_changement_sans_conflit_direct(self):
        r = self.patch("TESTETE_FR", curriculum_language_mode="bilingual")
        self.assertEqual(r.status_code, 200, r.data)


class LegacyAndMigrationTests(TestCase):
    """Académies antérieures : classement d'après les données, jamais deviné."""

    def test_regle_de_classement(self):
        # Parcours tels que STOCKÉS (Class.TRACK_*).
        B, F, A = Class.TRACK_BILINGUAL, Class.TRACK_FRANCOPHONE, Class.TRACK_ANGLOPHONE
        self.assertEqual(classify_curriculum(["fr", "en"], [B], False)[0], "bilingual")
        self.assertEqual(classify_curriculum(["fr", "bilingual"], [], False)[0], "bilingual")
        self.assertEqual(classify_curriculum(["fr", "fr"], [F, F], True)[0], "french_only")
        self.assertEqual(classify_curriculum(["en"], [A], True)[0], "english_only")
        # Ambigus : laissés « à configurer », avec un motif.
        for languages, tracks, allowed in ((["fr"], [B], True), ([], [], True),
                                           (["fr"], [], True), (["fr"], [F], False),
                                           (["en"], [A, B], True), (["fr"], [A], True)):
            with self.subTest(languages=languages, tracks=tracks, allowed=allowed):
                mode, reason = classify_curriculum(languages, tracks, allowed)
                self.assertIsNone(mode)
                self.assertTrue(reason)

    def test_migration_classe_les_donnees_existantes(self):
        from importlib import import_module

        migration = import_module("apps.schools.migrations.0021_curriculum_language_mode")
        year = datetime.date(2026, 9, 1), datetime.date(2027, 7, 31)

        def academy(code, entity_type, subjects, tracks):
            school = School.objects.create(name=code, code=code, address="x", entity_type=entity_type)
            sy = school.years.create(name="2026-2027", start_date=year[0], end_date=year[1])
            level = school.levels.create(name="N1", cycle="primaire", order=1)
            for i, language in enumerate(subjects):
                Subject.objects.create(school=school, name=f"S{i}", code=f"S{i}", coefficient=1,
                                       language=language)
            for i, track in enumerate(tracks):
                Class.objects.create(name=f"C{i}", level=level, school_year=sy, language_track=track)
            return school

        bi = academy("LEG_BI", "campus", ["fr", "en"], ["BILINGUAL"])
        fr = academy("LEG_FR", "online", ["fr"], ["FRANCOPHONE"])
        ambiguous = academy("LEG_AMB", "campus", ["fr"], ["BILINGUAL"])
        empty = academy("LEG_VIDE", "online", [], [])
        configured = academy("LEG_CONF", "campus", ["fr", "en"], ["BILINGUAL"])
        School.objects.filter(pk=configured.pk).update(curriculum_language_mode="english_only")

        migration.classify_existing(django_apps, None)
        modes = dict(School.objects.filter(code__startswith="LEG_").values_list("code", "curriculum_language_mode"))
        self.assertEqual(modes, {"LEG_BI": "bilingual", "LEG_FR": "french_only", "LEG_AMB": None,
                                 "LEG_VIDE": None, "LEG_CONF": "english_only"})   # jamais écrasé
        del bi, fr, ambiguous, empty

    def test_academie_non_configuree_garde_son_fonctionnement(self):
        school = School.objects.create(name="Ancienne", code="ANCIENNE", address="x", entity_type="campus")
        sy = school.years.create(name="2026-2027", start_date=datetime.date(2026, 9, 1),
                                 end_date=datetime.date(2027, 7, 31))
        level = school.levels.create(name="CM1", cycle="primaire", order=1)
        klass = Class.objects.create(name="CM1 A", level=level, school_year=sy)
        fr = Subject.objects.create(school=school, name="Fr", code="FR", coefficient=1, language="fr")
        en = Subject.objects.create(school=school, name="En", code="EN", coefficient=1, language="en")
        klass.subjects.set([fr, en])
        self.assertEqual(klass.expected_subject_languages(), ("fr", "en"))
        self.assertNotIn("bilingual", klass.allowed_subject_languages())

    def test_init_academies_complete_seulement_un_programme_vide(self):
        call_command("init_academies", stdout=BytesIOText())
        self.assertEqual(School.objects.get(code="FEBA").curriculum_language_mode, "bilingual")
        self.assertEqual(School.objects.get(code="FEBA_FHA").curriculum_language_mode, "bilingual")
        School.objects.filter(code="FEBA_FHA").update(curriculum_language_mode="french_only")
        call_command("init_academies", stdout=BytesIOText())
        self.assertEqual(School.objects.get(code="FEBA_FHA").curriculum_language_mode, "french_only")


class BytesIOText:
    def write(self, *_args, **_kwargs):
        pass

    def flush(self):
        pass
