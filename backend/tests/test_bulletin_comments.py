"""
Commentaire du Directeur / Principal's Comment — gestion de bout en bout.

Défauts reproduits sur le code livré (FEBA_VERSION_FINALE_VALIDEE_PRODUCTION) :
  - aucun moyen de saisir le commentaire depuis l'interface ; un PATCH sur
    l'API changeait la base mais pas le PDF ;
  - generate / generate-class / generate-all SUPPRIMAIENT le bulletin avant
    de le recréer : le commentaire disparaissait à chaque régénération ;
  - generate_bulletin effaçait l'ancien PDF AVANT de construire le nouveau :
    un échec laissait l'élève sans PDF ;
  - generate-all d'un super administrateur sans académie sélectionnée
    portait sur toutes les académies.

Les vérifications portent sur le PDF RÉELLEMENT produit (texte extrait
avec PyMuPDF), pas sur l'appel du générateur.
"""
import datetime
import shutil
import tempfile
from unittest import mock

import fitz  # PyMuPDF
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.accounts.models import CustomUser
from apps.bulletins.models import Bulletin, BulletinOperation
from apps.classes.models import Class
from apps.grades.models import Grade
from apps.schools.models import Level, School, SchoolYear
from apps.parents.models import Parent, ParentStudent
from apps.students.models import Student, StudentEnrollment
from apps.subjects.models import Subject
from apps.teachers.models import Teacher

NO_COMMENT = "(Aucun commentaire / No comment)"
ANNOTATION = "Ajouter un input box pour ajouter des commentaires"


def pdf_text(bulletin):
    bulletin.refresh_from_db()
    with bulletin.pdf_file.open("rb") as fh:
        content = fh.read()
    doc = fitz.open(stream=content, filetype="pdf")
    try:
        return "".join(page.get_text() for page in doc), doc.page_count
    finally:
        doc.close()


def flat(text):
    return " ".join(text.split())


def run_inline(op_id):
    """Exécute la vraie tâche Celery dans le processus de test."""
    from apps.bulletins.tasks import run_bulletin_operation
    run_bulletin_operation(op_id)


class Academy:
    """Une académie complète : année, classe(s), matières, élèves notés, comptes."""

    def __init__(self, tag, name):
        self.school = School.objects.create(name=name, address="X", matricule_prefix=tag[:4].upper())
        self.year = SchoolYear.objects.create(
            school=self.school, name="2026-2027", start_date=datetime.date(2026, 9, 1),
            end_date=datetime.date(2027, 7, 31), is_current=True)
        level = Level.objects.create(school=self.school, name="CE1", order=1)
        self.cls = Class.objects.create(name=f"CE1-{tag}", level=level, school_year=self.year)
        self.cls_b = Class.objects.create(name=f"CE2-{tag}", level=level, school_year=self.year)
        fr = Subject.objects.create(school=self.school, name="Français", code=f"FR{tag}",
                                    coefficient=2, language="fr")
        en = Subject.objects.create(school=self.school, name="English", code=f"EN{tag}",
                                    coefficient=2, language="en")
        for c in (self.cls, self.cls_b):
            c.subjects.set([fr, en])
        self.admin = CustomUser.objects.create_user(
            username=f"adm{tag}", email=f"adm{tag}@t.bj", password="Pass1234!", role="admin",
            first_name="A", last_name=tag, school=self.school)
        tu = CustomUser.objects.create_user(
            username=f"t{tag}", email=f"t{tag}@t.bj", password="Pass1234!", role="teacher",
            first_name="T", last_name=tag, school=self.school)
        self.teacher = Teacher.objects.create(user=tu)
        self.teacher.classes.add(self.cls)
        self.students = []
        for i, (c, graded) in enumerate([(self.cls, True), (self.cls, True), (self.cls, False),
                                         (self.cls_b, True)]):
            u = CustomUser.objects.create_user(
                username=f"e{tag}{i}", email=f"e{tag}{i}@t.bj", password="Pass1234!",
                role="student", first_name=f"E{i}", last_name=tag, school=self.school)
            s = Student.objects.create(user=u, school=self.school, first_name=f"E{i}",
                                       last_name=tag, current_class=c, school_year=self.year)
            StudentEnrollment.objects.create(student=s, school_year=self.year, class_obj=c)
            if graded:
                Grade.objects.create(student=s, subject=fr, school_year=self.year,
                                     teacher=self.teacher, period="T1", value=14)
                Grade.objects.create(student=s, subject=en, school_year=self.year,
                                     teacher=self.teacher, period="T1", value=12)
            self.students.append(s)
        pu = CustomUser.objects.create_user(
            username=f"p{tag}", email=f"p{tag}@t.bj", password="Pass1234!", role="parent",
            first_name="P", last_name=tag, school=self.school)
        parent = Parent.objects.create(user=pu)
        ParentStudent.objects.create(student=self.students[0], parent=parent)
        self.parent_user = pu


class BulletinCommentBase(TestCase):
    def setUp(self):
        self.media = tempfile.mkdtemp()
        self._override = override_settings(MEDIA_ROOT=self.media)
        self._override.enable()
        self.a = Academy("A", "FEBA")
        self.b = Academy("B", "FEBA French Heritage Academy")
        self.client = APIClient()
        self.client.force_authenticate(self.a.admin)
        patcher = mock.patch("apps.bulletins.tasks.run_bulletin_operation.delay", side_effect=run_inline)
        self.delay = patcher.start()
        self.addCleanup(patcher.stop)

    def tearDown(self):
        self._override.disable()
        shutil.rmtree(self.media, ignore_errors=True)

    def generate(self, student, academy=None, period="T1"):
        from apps.bulletins.pdf_generator import generate_bulletin
        return generate_bulletin(student, period, (academy or self.a).year)

    def comment(self, bulletin, text, **extra):
        return self.client.post(f"/api/bulletins/{bulletin.pk}/comment/",
                                {"comment": text, **extra}, format="json")

    def operation(self, **data):
        payload = {"period": "T1", "school_year_id": self.a.year.pk, "regenerate": True, **data}
        return self.client.post("/api/bulletins/operations/", payload, format="json")


class IndividualCommentTests(BulletinCommentBase):
    def test_ajout_enregistre_et_imprime(self):
        """Scénarios 1, 2, 3, 21 : ajout, base, PDF, lien renouvelé."""
        b = self.generate(self.a.students[0])
        old_url = b.pdf_file.url
        self.assertIn(NO_COMMENT, flat(pdf_text(b)[0]))
        r = self.comment(b, "Excellent trimestre, continuez ainsi.")
        self.assertEqual(r.status_code, 200, r.data)
        b.refresh_from_db()
        self.assertEqual(b.general_comment, "Excellent trimestre, continuez ainsi.")
        self.assertIsNotNone(b.comment_updated_at)
        self.assertEqual(b.comment_updated_by, self.a.admin)
        text = flat(pdf_text(b)[0])
        self.assertIn("Excellent trimestre, continuez ainsi.", text)
        self.assertNotIn(NO_COMMENT, text)
        # Nouveau fichier, nouvelle URL : le navigateur ne peut pas resservir l'ancien.
        self.assertNotEqual(r.data["bulletin"]["pdf_url"], old_url)
        self.assertEqual(r.data["bulletin"]["pdf_url"], b.pdf_file.url)
        self.assertFalse(r.data["bulletin"]["pdf_outdated"])
        self.assertEqual(Bulletin.objects.filter(student=self.a.students[0]).count(), 1)

    def test_modification_remplace_le_texte(self):
        """Scénarios 4, 5, 6."""
        b = self.generate(self.a.students[0])
        self.comment(b, "Premier commentaire du directeur.")
        r = self.comment(b, "Second commentaire, après le conseil de classe.")
        self.assertEqual(r.status_code, 200)
        text = flat(pdf_text(b)[0])
        self.assertIn("Second commentaire, après le conseil de classe.", text)
        self.assertNotIn("Premier commentaire du directeur.", text)

    def test_suppression_revient_au_texte_par_defaut(self):
        """Scénarios 7, 8 : le bulletin et ses notes restent."""
        b = self.generate(self.a.students[0])
        self.comment(b, "À retirer.")
        grades = Grade.objects.filter(student=self.a.students[0]).count()
        r = self.comment(b, "   ")
        self.assertEqual(r.status_code, 200)
        b.refresh_from_db()
        self.assertEqual(b.general_comment, "")
        text = flat(pdf_text(b)[0])
        self.assertIn(NO_COMMENT, text)
        self.assertNotIn("À retirer.", text)
        self.assertTrue(Bulletin.objects.filter(pk=b.pk).exists())
        self.assertEqual(Grade.objects.filter(student=self.a.students[0]).count(), grades)

    def test_regeneration_conserve_le_commentaire(self):
        """Scénario 9 : génération simple, par élève, par classe, pour toute l'académie."""
        b = self.generate(self.a.students[0])
        self.comment(b, "Commentaire durable.")
        s = self.a.students[0]
        self.client.post("/api/bulletins/generate/", {"student_id": s.pk, "period": "T1",
                         "school_year_id": self.a.year.pk}, format="json")
        self.client.post("/api/bulletins/generate-class/", {"class_id": self.a.cls.pk, "period": "T1",
                         "school_year_id": self.a.year.pk}, format="json")
        self.client.post("/api/bulletins/generate-all/", {"period": "T1",
                         "school_year_id": self.a.year.pk}, format="json")
        b2 = Bulletin.objects.get(student=s, school_year=self.a.year, period="T1")
        self.assertEqual(b2.pk, b.pk)            # même bulletin, jamais recréé
        self.assertEqual(b2.general_comment, "Commentaire durable.")
        self.assertIn("Commentaire durable.", flat(pdf_text(b2)[0]))

    def test_echec_de_generation_conserve_bulletin_commentaire_et_pdf(self):
        """Scénario 10."""
        b = self.generate(self.a.students[0])
        self.comment(b, "Version imprimée.")
        b.refresh_from_db()
        old_name, old_generated = b.pdf_file.name, b.generated_at
        storage = b.pdf_file.storage
        with mock.patch("apps.bulletins.pdf_generator._build_standard_pdf",
                        side_effect=RuntimeError("panne simulée")):
            r = self.comment(b, "Nouveau texte.")
        self.assertEqual(r.status_code, 207)
        self.assertEqual(r.data["result"]["failed"], 1)
        self.assertIn("ancien PDF est conservé", r.data["result"]["failures"][0]["reason"])
        b.refresh_from_db()
        self.assertEqual(b.general_comment, "Nouveau texte.")      # commentaire enregistré
        self.assertEqual(b.pdf_file.name, old_name)                # ancien PDF toujours là
        self.assertTrue(storage.exists(old_name))
        self.assertEqual(b.generated_at, old_generated)
        self.assertTrue(b.pdf_outdated)
        self.assertIn("Version imprimée.", flat(pdf_text(b)[0]))
        # Nouvelle tentative réussie : le PDF rattrape le commentaire.
        r = self.client.post("/api/bulletins/generate/", {"student_id": self.a.students[0].pk,
                             "period": "T1", "school_year_id": self.a.year.pk}, format="json")
        self.assertEqual(r.status_code, 201)
        self.assertIn("Nouveau texte.", flat(pdf_text(b)[0]))
        self.assertFalse(storage.exists(old_name))                 # ancien fichier remplacé

    def test_echec_sur_bulletin_absent_ne_cree_rien(self):
        s = self.a.students[1]
        with mock.patch("apps.bulletins.pdf_generator._build_standard_pdf",
                        side_effect=RuntimeError("panne")):
            r = self.client.post("/api/bulletins/generate/", {"student_id": s.pk, "period": "T1",
                                 "school_year_id": self.a.year.pk}, format="json")
        self.assertEqual(r.status_code, 500)
        self.assertFalse(Bulletin.objects.filter(student=s).exists())

    def test_caracteres_speciaux_et_retours_a_la_ligne(self):
        """Scénario 11."""
        b = self.generate(self.a.students[0])
        texte = ("Élève très à l'aise — « bravo » !\nProgrès <nets> & réguliers : 100 %.\n"
                 "Ligne 3 : ç, œ, ü, ß, 你好, emoji ✓")
        r = self.comment(b, texte + "\r\n\r\n\r\n  ")
        self.assertEqual(r.status_code, 200)
        b.refresh_from_db()
        self.assertEqual(b.general_comment, texte)   # espaces et lignes vides en trop retirés
        text = flat(pdf_text(b)[0])
        for fragment in ("Élève très à l'aise", "« bravo »", "<nets> & réguliers", "100 %",
                         "ç, œ, ü, ß"):
            self.assertIn(fragment, text)

    def test_commentaire_long_lisible_sans_debordement(self):
        """Scénario 12 : 1 200 caractères (le maximum) tiennent, rien n'est coupé."""
        b = self.generate(self.a.students[0])
        long = ("Appréciation détaillée du trimestre. " * 40)[:1180] + " FIN-DU-TEXTE"
        r = self.comment(b, long)
        self.assertEqual(r.status_code, 200, r.data)
        text, pages = pdf_text(b)
        self.assertIn("FIN-DU-TEXTE", flat(text))
        doc = fitz.open(b.pdf_file.path)
        try:
            # Ni le commentaire ni la signature du parent ne chevauchent le pied de page.
            last = doc[-1]
            sig = last.search_for("Signature du Parent")
            footer = last.search_for("Généré le")
            fin = [p for p in doc for _ in p.search_for("FIN-DU-TEXTE")]
            self.assertTrue(sig and footer and fin)
            self.assertLess(sig[0].y1, footer[0].y0)
            for page in doc:
                for rect in page.search_for("FIN-DU-TEXTE"):
                    self.assertLess(rect.y1, page.rect.height - 20)
        finally:
            doc.close()

    def test_commentaire_trop_long_refuse_sans_troncature(self):
        b = self.generate(self.a.students[0])
        r = self.comment(b, "x" * 1201)
        self.assertEqual(r.status_code, 400)
        self.assertIn("trop long", r.data["error"])
        b.refresh_from_db()
        self.assertEqual(b.general_comment, "")

    def test_donnees_invalides(self):
        b = self.generate(self.a.students[0])
        self.assertEqual(self.comment(b, {"html": "<b>"}).status_code, 400)
        self.assertEqual(self.comment(b, ["a"]).status_code, 400)

    def test_requetes_repetees_et_modification_concurrente(self):
        b = self.generate(self.a.students[0])
        self.assertEqual(self.comment(b, "Texte A").status_code, 200)
        r = self.comment(b, "Texte A")   # double clic
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["result"]["unchanged"], 1)
        # Un autre administrateur a modifié entre-temps : 409, rien n'est écrasé.
        r = self.comment(b, "Texte B", expected_comment="Texte périmé")
        self.assertEqual(r.status_code, 409)
        self.assertEqual(r.data["current_comment"], "Texte A")
        b.refresh_from_db()
        self.assertEqual(b.general_comment, "Texte A")
        self.assertEqual(self.comment(b, "Texte B", expected_comment="Texte A").status_code, 200)

    def test_bulletin_d_une_annee_passee_reste_modifiable(self):
        """Le filtre « année active » ne s'applique plus au détail."""
        b = self.generate(self.a.students[0])
        SchoolYear.objects.filter(pk=self.a.year.pk).update(is_current=False)
        SchoolYear.objects.create(school=self.a.school, name="2027-2028",
                                  start_date=datetime.date(2027, 9, 1),
                                  end_date=datetime.date(2028, 7, 31), is_current=True)
        self.assertEqual(self.comment(b, "Année passée.").status_code, 200)

    def test_l_annotation_de_la_capture_n_apparait_jamais(self):
        """Scénario 22."""
        b = self.generate(self.a.students[0])
        self.comment(b, "Commentaire réel.")
        self.assertNotIn(ANNOTATION, pdf_text(b)[0])
        self.assertNotIn("input box", pdf_text(b)[0])

    def test_patch_generique_ferme(self):
        b = self.generate(self.a.students[0])
        r = self.client.patch(f"/api/bulletins/{b.pk}/", {"general_comment": "contournement"},
                              format="json")
        self.assertEqual(r.status_code, 405)
        b.refresh_from_db()
        self.assertEqual(b.general_comment, "")


class PermissionTests(BulletinCommentBase):
    def test_parent_eleve_enseignant_refuses(self):
        """Scénario 18."""
        b = self.generate(self.a.students[0])
        for user in (self.a.parent_user, self.a.students[0].user, self.a.teacher.user):
            c = APIClient()
            c.force_authenticate(user)
            r = c.post(f"/api/bulletins/{b.pk}/comment/", {"comment": "pirate"}, format="json")
            self.assertEqual(r.status_code, 403, user.role)
            r = c.post("/api/bulletins/operations/", {"scope": "academy", "action": "set_comment",
                       "comment": "x", "period": "T1", "school_year_id": self.a.year.pk},
                       format="json")
            self.assertEqual(r.status_code, 403, user.role)
            self.assertEqual(c.get("/api/bulletins/operations/").status_code, 403, user.role)
        b.refresh_from_db()
        self.assertEqual(b.general_comment, "")

    def test_autre_academie_refusee(self):
        """Scénario 19 : bulletin, élève, classe, année d'une autre académie."""
        b_other = self.generate(self.b.students[0], self.b)
        r = self.comment(b_other, "intrusion")
        self.assertEqual(r.status_code, 404)
        b_other.refresh_from_db()
        self.assertEqual(b_other.general_comment, "")
        for data in ({"scope": "student", "student_id": self.b.students[0].pk},
                     {"scope": "class", "class_id": self.b.cls.pk},
                     {"scope": "academy", "school_year_id": self.b.year.pk}):
            r = self.operation(action="set_comment", comment="intrusion", **data)
            self.assertEqual(r.status_code, 404, data)
        self.assertFalse(BulletinOperation.objects.exists())

    def test_superadmin_doit_choisir_une_academie(self):
        """Scénario 20."""
        su = CustomUser.objects.create_user(username="su", email="su@t.bj", password="Pass1234!",
                                            role="superadmin", first_name="S", last_name="U")
        c = APIClient()
        c.force_authenticate(su)
        payload = {"scope": "academy", "action": "set_comment", "comment": "x", "period": "T1",
                   "school_year_id": self.a.year.pk}
        r = c.post("/api/bulletins/operations/", payload, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("académie", r.data["error"])
        r = c.post("/api/bulletins/generate-all/", {"period": "T1",
                   "school_year_id": self.a.year.pk}, format="json")
        self.assertEqual(r.status_code, 400)     # avant : toutes les académies
        self.assertFalse(Bulletin.objects.exists())
        # Avec l'académie choisie, l'opération ne touche que celle-ci.
        r = c.post(f"/api/bulletins/generate-all/?school_id={self.a.school.pk}",
                   {"period": "T1", "school_year_id": self.a.year.pk}, format="json")
        self.assertEqual(r.status_code, 202, r.data)
        self.assertFalse(Bulletin.objects.filter(student__school=self.b.school).exists())
        self.assertTrue(Bulletin.objects.filter(student__school=self.a.school).exists())


class GroupOperationTests(BulletinCommentBase):
    def test_classe_entiere(self):
        """Scénario 13 : tous les bulletins de la classe, et seulement eux."""
        for s in self.a.students:
            if s.grades.exists():
                self.generate(s)
        r = self.operation(scope="class", class_id=self.a.cls.pk, action="set_comment",
                           comment="Bonne dynamique de classe.")
        self.assertEqual(r.status_code, 202, r.data)
        op = BulletinOperation.objects.get(pk=r.data["id"])
        self.assertEqual(op.status, "done")
        self.assertEqual(op.result["targeted"], 3)
        self.assertEqual(op.result["comments_set"], 2)
        self.assertEqual(op.result["pdf_generated"], 2)
        self.assertEqual(op.result["skipped"], 1)    # élève sans bulletin
        for s in self.a.students[:2]:
            b = Bulletin.objects.get(student=s, period="T1")
            self.assertEqual(b.general_comment, "Bonne dynamique de classe.")
            self.assertIn("Bonne dynamique de classe.", flat(pdf_text(b)[0]))
        other = Bulletin.objects.get(student=self.a.students[3])   # autre classe
        self.assertEqual(other.general_comment, "")

    def test_toute_l_academie_seulement(self):
        """Scénario 14."""
        for s in self.a.students + self.b.students:
            if s.grades.exists():
                self.generate(s, self.a if s.school == self.a.school else self.b)
        r = self.operation(scope="academy", action="set_comment", comment="Message de fin d'année.")
        self.assertEqual(r.status_code, 202)
        op = BulletinOperation.objects.get(pk=r.data["id"])
        self.assertEqual(op.result["comments_set"], 3)
        self.assertEqual(Bulletin.objects.filter(student__school=self.a.school,
                                                 general_comment="Message de fin d'année.").count(), 3)
        self.assertFalse(Bulletin.objects.filter(student__school=self.b.school)
                         .exclude(general_comment="").exists())
        # Journal d'audit.
        self.assertEqual(op.created_by, self.a.admin)
        self.assertEqual(op.school, self.a.school)
        self.assertEqual((op.scope, op.period, op.school_year), ("academy", "T1", self.a.year))

    def test_suppression_groupee_garde_notes_et_bulletins(self):
        """Scénario 15."""
        for s in self.a.students[:2]:
            self.generate(s)
        self.operation(scope="class", class_id=self.a.cls.pk, action="set_comment", comment="Temp")
        grades, bulletins = Grade.objects.count(), Bulletin.objects.count()
        r = self.operation(scope="class", class_id=self.a.cls.pk, action="clear_comment")
        op = BulletinOperation.objects.get(pk=r.data["id"])
        self.assertEqual(op.result["comments_cleared"], 2)
        self.assertEqual((Grade.objects.count(), Bulletin.objects.count()), (grades, bulletins))
        for b in Bulletin.objects.all():
            self.assertEqual(b.general_comment, "")
            self.assertIn(NO_COMMENT, flat(pdf_text(b)[0]))

    def test_bulletins_manquants_selon_le_choix(self):
        """Scénario 16 : sans accord, aucun bulletin créé ; avec, seulement les élèves notés."""
        r = self.operation(scope="class", class_id=self.a.cls.pk, action="set_comment", comment="Hello")
        op = BulletinOperation.objects.get(pk=r.data["id"])
        self.assertEqual(op.result["skipped"], 3)
        self.assertFalse(Bulletin.objects.exists())
        self.assertIn("création non demandée", op.result["skipped_items"][0]["reason"])

        r = self.operation(scope="class", class_id=self.a.cls.pk, action="set_comment",
                           comment="Hello", create_missing=True)
        op = BulletinOperation.objects.get(pk=r.data["id"])
        self.assertEqual(op.result["bulletins_created"], 2)
        self.assertEqual(op.result["skipped"], 1)
        self.assertIn("aucune note", op.result["skipped_items"][0]["reason"])
        self.assertFalse(Bulletin.objects.filter(student=self.a.students[2]).exists())
        for s in self.a.students[:2]:
            self.assertIn("Hello", flat(pdf_text(Bulletin.objects.get(student=s))[0]))

    def test_echec_partiel_rapporte(self):
        """Scénario 17 : jamais présenté comme une réussite totale."""
        for s in self.a.students[:2]:
            self.generate(s)
        from apps.bulletins import pdf_generator
        real = pdf_generator._build_standard_pdf
        target = self.a.students[1]

        def flaky(buffer, student, *args, **kwargs):
            if student.pk == target.pk:
                raise RuntimeError("police introuvable")
            return real(buffer, student, *args, **kwargs)

        with mock.patch("apps.bulletins.pdf_generator._build_standard_pdf", side_effect=flaky):
            r = self.operation(scope="class", class_id=self.a.cls.pk, action="set_comment",
                               comment="Partiel")
        op = BulletinOperation.objects.get(pk=r.data["id"])
        self.assertEqual(op.status, "partial")
        self.assertEqual(op.result["pdf_generated"], 1)
        self.assertEqual(op.result["failed"], 1)
        self.assertEqual(op.result["failures"][0]["student_id"], target.pk)
        self.assertIn("police introuvable", op.result["failures"][0]["reason"])
        detail = self.client.get(f"/api/bulletins/operations/{op.pk}/")
        self.assertEqual(detail.data["status"], "partial")

    def test_apercu_avant_confirmation(self):
        self.generate(self.a.students[0])
        self.comment(Bulletin.objects.get(student=self.a.students[0]), "Déjà là")
        r = self.client.post("/api/bulletins/comment-preview/", {
            "scope": "class", "class_id": self.a.cls.pk, "period": "T1",
            "school_year_id": self.a.year.pk}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual((r.data["students"], r.data["existing_bulletins"], r.data["with_comment"],
                          r.data["missing_with_grades"], r.data["missing_without_grades"]),
                         (3, 1, 1, 1, 1))
        self.assertEqual(r.data["academy"]["id"], self.a.school.pk)

    def test_une_seule_operation_a_la_fois(self):
        BulletinOperation.objects.create(school=self.a.school, school_year=self.a.year, period="T1",
                                         scope="academy", action="generate", status="running")
        r = self.operation(scope="academy", action="generate")
        self.assertEqual(r.status_code, 409)

    def test_broker_indisponible_annonce_l_echec(self):
        """Pas de « génération en cours » si aucune tâche n'a été programmée."""
        self.delay.side_effect = ConnectionError("redis down")
        r = self.operation(scope="academy", action="generate")
        self.assertEqual(r.status_code, 503)
        self.assertEqual(r.data["status"], "failed")
        self.assertIn("File d'attente indisponible", r.data["error"])

    def test_la_tache_ne_s_execute_qu_une_fois(self):
        from apps.bulletins.tasks import run_bulletin_operation
        self.generate(self.a.students[0])
        r = self.operation(scope="student", student_id=self.a.students[0].pk,
                           action="set_comment", comment="Une fois")
        run_bulletin_operation(r.data["id"])     # seconde livraison du message
        op = BulletinOperation.objects.get(pk=r.data["id"])
        self.assertEqual(op.result["comments_set"], 1)


class CommentTargetTests(BulletinCommentBase):
    """Un élève, bulletin généré ou non : POST /bulletins/comment-target/ (synchrone)."""

    def target(self, student, text, period="T1", **extra):
        return self.client.post("/api/bulletins/comment-target/", {
            "student_id": student.pk, "school_year_id": self.a.year.pk, "period": period,
            "comment": text, **extra}, format="json")

    def test_avant_generation_ajout_modification_suppression(self):
        s = self.a.students[0]
        r = self.target(s, "Avant génération.", regenerate=False)
        self.assertEqual(r.status_code, 200, r.data)
        b = Bulletin.objects.get(student=s, period="T1")
        self.assertEqual(b.general_comment, "Avant génération.")
        self.assertFalse(b.pdf_file)                                    # brouillon, aucun PDF
        self.assertEqual(self.target(s, "Modifié avant génération.", regenerate=False).status_code, 200)
        self.assertEqual(self.target(s, "", regenerate=False).status_code, 200)
        b.refresh_from_db()
        self.assertEqual(b.general_comment, "")
        self.assertEqual(Bulletin.objects.filter(student=s).count(), 1)
        # Le brouillon est invisible des familles…
        self.target(s, "Repris à la génération.", regenerate=False)
        parent = APIClient()
        parent.force_authenticate(self.a.parent_user)
        listed = parent.get("/api/bulletins/").json()
        self.assertEqual(len(listed.get("results", listed)), 0)
        self.assertEqual(parent.get(f"/api/bulletins/{b.pk}/").status_code, 404)
        # …et la génération ultérieure imprime le commentaire.
        r = self.client.post("/api/bulletins/generate/", {"student_id": s.pk, "period": "T1",
                             "school_year_id": self.a.year.pk}, format="json")
        self.assertEqual(r.status_code, 201)
        self.assertIn("Repris à la génération.", flat(pdf_text(b)[0]))
        self.assertEqual(len(parent.get("/api/bulletins/").json().get("results", [])), 1)

    def test_avant_generation_avec_pdf_immediat_si_notes(self):
        s = self.a.students[0]
        r = self.target(s, "Généré tout de suite.")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["result"]["pdf_generated"], 1)
        self.assertIn("Généré tout de suite.", flat(pdf_text(Bulletin.objects.get(student=s))[0]))

    def test_eleve_sans_note_commentaire_garde_sans_pdf_vide(self):
        s = self.a.students[2]                        # aucune note
        r = self.target(s, "Sans note.")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["result"]["pdf_generated"], 0)
        self.assertIn("aucune note", r.data["result"]["skipped_items"][0]["reason"])
        b = Bulletin.objects.get(student=s)
        self.assertEqual(b.general_comment, "Sans note.")
        self.assertFalse(b.pdf_file)

    def test_cycles_repetes_apres_generation(self):
        """Cinq cycles ajout → modification → suppression, PDF relu à chaque étape."""
        s = self.a.students[1]
        self.generate(s)
        urls = set()
        for i in range(5):
            for text in (f"Ajout {i} — « é à ç »\nligne 2", f"Modification {i}", ""):
                r = self.target(s, text, expected_comment=Bulletin.objects.get(student=s).general_comment)
                self.assertEqual(r.status_code, 200, (i, text, r.data))
                b = Bulletin.objects.get(student=s, period="T1")
                self.assertEqual(b.general_comment, text)
                content = flat(pdf_text(b)[0])
                self.assertIn(flat(text) if text else NO_COMMENT, content)
                urls.add(b.pdf_file.name)
                self.assertTrue(b.pdf_file.storage.exists(b.pdf_file.name))
                self.assertFalse(r.data["bulletin"]["pdf_outdated"])
        self.assertEqual(len(urls), 15)                       # un fichier (une URL) par version
        self.assertEqual(Bulletin.objects.filter(student=s).count(), 1)
        # Les anciens fichiers ont été retirés : seul le dernier subsiste.
        b = Bulletin.objects.get(student=s, period="T1")
        self.assertEqual([n for n in urls if b.pdf_file.storage.exists(n)], [b.pdf_file.name])

    def test_regenerations_successives_conservent_le_commentaire(self):
        s = self.a.students[0]
        self.target(s, "Conservé.")
        for _ in range(4):
            r = self.client.post("/api/bulletins/generate/", {"student_id": s.pk, "period": "T1",
                                 "school_year_id": self.a.year.pk}, format="json")
            self.assertEqual(r.status_code, 201)
        b = Bulletin.objects.get(student=s)
        self.assertEqual(b.general_comment, "Conservé.")
        self.assertIn("Conservé.", flat(pdf_text(b)[0]))

    def test_erreur_de_sauvegarde_n_annonce_pas_de_succes(self):
        s = self.a.students[0]
        self.generate(s)
        with mock.patch("apps.bulletins.models.Bulletin.save", side_effect=RuntimeError("disque plein")):
            r = self.target(s, "Ne doit pas passer.")
        self.assertEqual(r.status_code, 500)
        self.assertNotIn("bulletin", r.data)
        self.assertEqual(Bulletin.objects.get(student=s).general_comment, "")

    def test_requete_repetee_idempotente_et_conflit(self):
        s = self.a.students[0]
        self.assertEqual(self.target(s, "Une fois.").status_code, 200)
        r = self.target(s, "Une fois.")
        self.assertEqual(r.data["result"]["unchanged"], 1)
        self.assertEqual(r.data["result"]["pdf_generated"], 0)       # rien à refaire
        r = self.target(s, "Autre", expected_comment="périmé")
        self.assertEqual(r.status_code, 409)
        self.assertEqual(r.data["current_comment"], "Une fois.")

    def test_isolation_et_permissions(self):
        r = self.target(self.b.students[0], "intrus")
        self.assertEqual(r.status_code, 404)
        self.assertFalse(Bulletin.objects.filter(student=self.b.students[0]).exists())
        for user in (self.a.parent_user, self.a.students[0].user, self.a.teacher.user):
            c = APIClient()
            c.force_authenticate(user)
            r = c.post("/api/bulletins/comment-target/", {"student_id": self.a.students[0].pk,
                       "school_year_id": self.a.year.pk, "period": "T1", "comment": "x"}, format="json")
            self.assertEqual(r.status_code, 403, user.role)

    def test_operation_bloquee_ne_bloque_plus(self):
        from datetime import timedelta
        from django.utils import timezone
        op = BulletinOperation.objects.create(school=self.a.school, school_year=self.a.year, period="T1",
                                              scope="academy", action="generate", status="queued")
        BulletinOperation.objects.filter(pk=op.pk).update(created_at=timezone.now() - timedelta(minutes=30))
        r = self.operation(scope="academy", action="generate")
        self.assertEqual(r.status_code, 202, r.data)
        op.refresh_from_db()
        self.assertEqual(op.status, "failed")
        self.assertIn("interrompue", op.error)


class ConcurrentCommentTests(BulletinCommentBase):
    """Deux enregistrements simultanés (PostgreSQL : verrous de ligne réels)."""

    def test_deux_demandes_simultanees(self):
        import threading
        from django.db import connection
        if connection.vendor != "postgresql":
            self.skipTest("Concurrence réelle : PostgreSQL requis.")
        s = self.a.students[0]
        codes = []

        def send(text):
            c = APIClient()
            c.force_authenticate(self.a.admin)
            r = c.post("/api/bulletins/comment-target/", {"student_id": s.pk, "school_year_id": self.a.year.pk,
                       "period": "T2", "comment": text, "regenerate": False, "expected_comment": ""},
                       format="json")
            codes.append(r.status_code)
            connection.close()

        threads = [threading.Thread(target=send, args=(f"Texte {i}",)) for i in range(2)]
        [t.start() for t in threads]
        [t.join() for t in threads]
        self.assertEqual(Bulletin.objects.filter(student=s, period="T2").count(), 1)
        self.assertEqual(sorted(codes), [200, 409])            # le second voit la modification du premier
        self.assertIn(Bulletin.objects.get(student=s, period="T2").general_comment, ("Texte 0", "Texte 1"))
