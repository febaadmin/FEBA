"""Tests d'attaque de l'audit de sécurité : ce qu'un compte ne doit jamais pouvoir faire."""
import datetime
import io
import tempfile
from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.core import signing
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from PIL import Image
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIClient

from apps.attendance.serializers import AttendanceSerializer
from apps.core.csv_sur import cellule
from apps.core.fichiers_prives import SEL
from apps.grades.models import Grade
from apps.students.models import Student, StudentEnrollment
from apps.suivi import services
from apps.suivi.models import Objectif

from .academy_fixtures import TYPES, build_academy
from .isolation_campaign import Report, tag_pattern

User = get_user_model()


def client(user=None):
    c = APIClient(HTTP_HOST="localhost")
    if user:
        c.force_authenticate(user)
    return c


def connexion(email, mot="Pass1234!"):
    r = client().post("/api/auth/login/", {"email": email, "password": mot}, format="json")
    assert r.status_code == 200, r.content
    return r.data


class Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.a = build_academy("SECA", TYPES[0])
        cls.b = build_academy("SECB", TYPES[0])


class ElevationTests(Base):
    def test_profil_ne_change_ni_role_ni_academie(self):
        u = self.a.student_user
        r = client(u).patch("/api/auth/me/", {"role": "superadmin", "role_level": 100, "is_staff": True, "is_superuser": True,
                                              "school": self.b.school.pk}, format="json")
        self.assertLess(r.status_code, 500)
        u.refresh_from_db()
        self.assertEqual(u.role, "student")
        self.assertFalse(u.is_staff or u.is_superuser)
        self.assertEqual(u.school_id, self.a.school.pk)

    def test_admin_ne_cree_pas_de_superadmin(self):
        r = client(self.a.admin).post("/api/auth/users/", {
            "email": "pirate@iso.test", "username": "pirate", "first_name": "P", "last_name": "P",
            "password": "Xy7!kPq9#Lm2", "role": "superadmin"}, format="json")
        self.assertFalse(User.objects.filter(email="pirate@iso.test", role="superadmin").exists(), r.content)

    def test_admin_ne_se_promeut_pas(self):
        a = self.a.admin
        client(a).patch(f"/api/auth/users/{a.pk}/", {"role": "superadmin"}, format="json")
        a.refresh_from_db()
        self.assertEqual(a.role, "admin")

    def test_admin_ne_touche_pas_un_compte_d_une_autre_academie(self):
        cible = self.b.student_user
        c = client(self.a.admin)
        self.assertIn(c.patch(f"/api/auth/users/{cible.pk}/", {"first_name": "Volé"}, format="json").status_code, (403, 404))
        self.assertIn(c.post(f"/api/auth/users/{cible.pk}/reset-password/", {"new_password": "Xy7!kPq9#Lm2"}, format="json").status_code, (403, 404))
        self.assertIn(c.post(f"/api/auth/users/{cible.pk}/toggle-active/").status_code, (403, 404))
        cible.refresh_from_db()
        self.assertNotEqual(cible.first_name, "Volé")
        self.assertTrue(cible.is_active)

    def test_roles_inferieurs_sans_gestion_des_comptes(self):
        for u in (self.a.student_user, self.a.parent_user, self.a.teacher_user):
            self.assertEqual(client(u).get("/api/auth/users/").status_code, 403, u.role)
            self.assertEqual(client(u).get("/api/incidents/").status_code, 403, u.role)


class SessionsTests(Base):
    def test_compte_desactive_coupe_acces_et_renouvellement(self):
        u = self.a.teacher_user
        jetons = connexion(u.email)
        c = client()
        c.credentials(HTTP_AUTHORIZATION=f"Bearer {jetons['access']}")
        self.assertEqual(c.get("/api/auth/me/").status_code, 200)
        User.objects.filter(pk=u.pk).update(is_active=False)
        self.assertEqual(c.get("/api/auth/me/").status_code, 401)
        self.assertEqual(client().post("/api/auth/refresh/", {"refresh": jetons["refresh"]}, format="json").status_code, 401)

    def test_changer_son_mot_de_passe_revoque_les_autres_sessions(self):
        u = self.a.teacher_user
        volee = connexion(u.email)
        c = client(u)
        r = c.post("/api/auth/change-password/", {"old_password": "Pass1234!", "new_password": "Xy7!kPq9#Lm2", "confirm_password": "Xy7!kPq9#Lm2"}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(client().post("/api/auth/refresh/", {"refresh": volee["refresh"]}, format="json").status_code, 401)

    def test_connexion_met_a_jour_la_derniere_connexion(self):
        u = self.a.teacher_user
        User.objects.filter(pk=u.pk).update(last_login=None)
        connexion(u.email)
        u.refresh_from_db()
        self.assertIsNotNone(u.last_login)

    def test_echec_ne_met_pas_a_jour_la_derniere_connexion(self):
        u = self.a.teacher_user
        User.objects.filter(pk=u.pk).update(last_login=None)
        client().post("/api/auth/login/", {"email": u.email, "password": "faux"}, format="json")
        u.refresh_from_db()
        self.assertIsNone(u.last_login)

    def test_compte_desactive_annonce_seulement_avec_le_bon_mot_de_passe(self):
        u = self.a.teacher_user
        User.objects.filter(pk=u.pk).update(is_active=False)
        bon = client().post("/api/auth/login/", {"email": u.email, "password": "Pass1234!"}, format="json")
        self.assertEqual(bon.status_code, 400)
        self.assertIn("désactivé", str(bon.data))
        mauvais = client().post("/api/auth/login/", {"email": u.email, "password": "faux"}, format="json")
        self.assertNotIn("désactivé", str(mauvais.data))

    def test_refresh_deconnecte_refuse(self):
        u = self.a.teacher_user
        j = connexion(u.email)
        self.assertEqual(client(u).post("/api/auth/logout/", {"refresh": j["refresh"]}, format="json").status_code, 200)
        self.assertEqual(client().post("/api/auth/refresh/", {"refresh": j["refresh"]}, format="json").status_code, 401)

    def test_erreur_de_connexion_ne_dit_pas_si_le_compte_existe(self):
        c = client()
        existant = c.post("/api/auth/login/", {"email": self.a.teacher_user.email, "password": "faux"}, format="json")
        inconnu = c.post("/api/auth/login/", {"email": "personne@iso.test", "password": "faux"}, format="json")
        self.assertEqual(existant.status_code, inconnu.status_code)
        self.assertEqual(existant.data, inconnu.data)


class ObjetsTests(Base):
    def test_note_d_une_autre_academie_inaccessible(self):
        note = Grade.objects.filter(student=self.b.student).first()
        self.assertIsNotNone(note)
        for u in (self.a.admin, self.a.teacher_user):
            c = client(u)
            self.assertEqual(c.get(f"/api/grades/{note.pk}/").status_code, 404, u.role)
            self.assertIn(c.patch(f"/api/grades/{note.pk}/", {"value": 1}, format="json").status_code, (403, 404))
            self.assertIn(c.delete(f"/api/grades/{note.pk}/", {"reason": "x"}, format="json").status_code, (403, 404))
        valeur = note.value
        note.refresh_from_db()
        self.assertEqual(note.value, valeur)

    def test_eleve_et_parent_sans_ecriture_de_notes(self):
        note = Grade.objects.filter(student=self.a.student).first()
        for u in (self.a.student_user, self.a.parent_user):
            c = client(u)
            self.assertEqual(c.patch(f"/api/grades/{note.pk}/", {"value": 20}, format="json").status_code, 403, u.role)
            self.assertEqual(c.delete(f"/api/grades/{note.pk}/").status_code, 403, u.role)

    def test_parametres_d_academie_ignores_pour_un_non_superadmin(self):
        c = client(self.a.admin)
        for params in ({"school_id": self.b.school.pk}, {"school": self.b.school.pk}):
            r = c.get("/api/students/", {**params, "page_size": 1000})
            self.assertEqual(r.status_code, 200)
            self.assertNotIn("SECB", r.content.decode().upper())
        r = client(self.a.admin).get("/api/students/", HTTP_X_ACADEMY_SCOPE=str(self.b.school.pk))
        self.assertNotIn("SECB", r.content.decode().upper())

    def test_ecriture_avec_un_objet_d_une_autre_academie_refusee(self):
        r = client(self.a.admin).post("/api/grades/", {
            "student": self.b.student.pk, "value": 20, "date": datetime.date(2026, 10, 1).isoformat()}, format="json")
        self.assertIn(r.status_code, (400, 403, 404), r.content)


class EntreesTests(Base):
    def test_injection_sql_dans_la_recherche_sans_effet(self):
        r = client(self.a.admin).get("/api/students/", {"search": "' OR 1=1; DROP TABLE students_student; --"})
        self.assertLess(r.status_code, 500)
        self.assertTrue(User.objects.filter(pk=self.a.admin.pk).exists())

    def test_lien_de_fichier_falsifie_refuse(self):
        c = client()
        self.assertEqual(c.get("/api/files/bulletins.xxxxx/").status_code, 404)
        self.assertEqual(c.get("/api/files/..%2F..%2F.env/").status_code, 404)


@override_settings(MEDIA_ROOT=tempfile.mkdtemp(prefix="feba-sec-"))
class AvatarTests(Base):
    def depose(self, nom, contenu, type_mime):
        return client(self.a.student_user).post(
            "/api/auth/avatar/", {"avatar": SimpleUploadedFile(nom, contenu, content_type=type_mime)}, format="multipart")

    def test_html_et_svg_refuses(self):
        script = b"<html><script>alert(document.domain)</script></html>"
        for nom, contenu, mime in (
            ("x.html", script, "text/html"),
            ("x.svg", b'<svg xmlns="http://www.w3.org/2000/svg" onload="alert(1)"/>', "image/svg+xml"),
            ("x.png", script, "image/png"),
            ("x.html.png", script, "image/png"),
        ):
            self.assertEqual(self.depose(nom, contenu, mime).status_code, 400, nom)
        self.a.student_user.refresh_from_db()
        self.assertFalse(self.a.student_user.avatar)

    def test_vraie_image_acceptee_sous_un_nom_sur(self):
        tampon = io.BytesIO()
        Image.new("RGB", (8, 8)).save(tampon, "PNG")
        r = self.depose("mon portrait.html", tampon.getvalue(), "text/html")
        self.assertEqual(r.status_code, 200, r.content)
        self.a.student_user.refresh_from_db()
        self.assertTrue(self.a.student_user.avatar.name.endswith(".png"))

    def test_image_trop_lourde_refusee(self):
        self.assertEqual(self.depose("g.png", b"0" * (6 * 1024 * 1024), "image/png").status_code, 400)


@override_settings(MEDIA_ROOT=tempfile.mkdtemp(prefix="feba-sec-"))
class PiecesJointesTests(Base):
    def test_annonce_refuse_un_fichier_actif(self):
        r = client(self.a.admin).post("/api/announcements/", {
            "title": "T", "content": "C", "target_roles": '["all"]',
            "attachment": SimpleUploadedFile("x.html", b"<script>1</script>", content_type="text/html")}, format="multipart")
        self.assertEqual(r.status_code, 400, r.content)

    def test_justificatif_refuse_un_fichier_actif(self):
        s = AttendanceSerializer()
        with self.assertRaises(ValidationError):
            s.validate_justification_file(SimpleUploadedFile("x.html", b"<script>1</script>", content_type="text/html"))


class CoherenceTests(Base):
    def test_note_supprimee_absente_des_tableaux_de_bord(self):
        note = Grade.objects.filter(student=self.a.student).first()
        Grade.objects.filter(pk=note.pk).update(is_deleted=True)
        for u in (self.a.student_user, self.a.teacher_user):
            r = client(u).get("/api/dashboard/" + ("student/" if u.role == "student" else "teacher/"))
            self.assertEqual(r.status_code, 200, r.content)
            ids = [g.get("id") for g in r.data.get("recent_grades", [])]
            self.assertNotIn(note.pk, ids)

    def test_objectif_archive_hors_du_calcul(self):
        o = Objectif.objects.create(school=self.a.school, student=self.a.student, titre="O", statut="atteint", archive_le=timezone.now())
        self.assertFalse(services._objectifs(self.a.student)["has_data"])
        Objectif.objects.filter(pk=o.pk).update(archive_le=None)
        self.assertEqual(services._objectifs(self.a.student)["taux_atteinte"], 100.0)


class DetecteurDeFuiteTests(TestCase):
    """Anomalie A1 : le détecteur ne doit ni crier au hasard ni rater une vraie fuite."""

    def _reponse(self, jeton):
        return SimpleNamespace(status_code=200, get=lambda *a: "application/json",
                               content=f'{{"pdf_url": "/api/files/{jeton}/"}}'.encode())

    def _jeton_avec(self, etiquette):
        for i in range(5_000_000):
            jeton = signing.dumps(f"bulletins/ACT07Z-{i}.pdf", salt=SEL)
            if etiquette.lower() in jeton.lower():
                return jeton
        self.fail("aucun jeton trouvé")

    def test_etiquette_formee_par_hasard_dans_un_jeton_ignoree(self):
        rapport = Report()
        rapport.check_body("T07Z/admin", "/x/", self._reponse(self._jeton_avec("T14")), [("T14", tag_pattern("T14"))])
        self.assertEqual(rapport.leaks, [])

    def test_vraie_fuite_dans_le_fichier_d_un_jeton_detectee(self):
        rapport = Report()
        jeton = signing.dumps("bulletins/bulletin_ACT14Z-26-0001.pdf", salt=SEL)
        rapport.check_body("T07Z/admin", "/x/", self._reponse(jeton), [("T14Z", tag_pattern("T14Z"))])
        self.assertEqual(len(rapport.leaks), 1)

    def test_vraie_fuite_en_clair_detectee(self):
        rapport = Report()
        reponse = SimpleNamespace(status_code=200, get=lambda *a: "application/json", content=b'{"nom": "Eleve T14Z"}')
        rapport.check_body("T07Z/admin", "/x/", reponse, [("T14Z", tag_pattern("T14Z"))])
        self.assertEqual(len(rapport.leaks), 1)


class CsvTests(TestCase):
    def test_formule_neutralisee_nombres_gardes(self):
        self.assertEqual(cellule('=HYPERLINK("x")'), '\'=HYPERLINK("x")')
        self.assertEqual(cellule("@cmd"), "'@cmd")
        self.assertEqual(cellule("+229 97 00 00 00"), "+229 97 00 00 00")
        self.assertEqual(cellule("-5"), "-5")
        self.assertEqual(cellule(12), 12)


class VolumeTests(TestCase):
    """Le nombre de requêtes d'une liste ne doit pas croître avec son nombre de lignes."""

    def _compte(self, compte, chemin):
        c = client(compte)
        with CaptureQueriesContext(connection) as requetes:
            self.assertEqual(c.get(chemin, {"page_size": 1000}).status_code, 200)
        return len(requetes)

    def test_notes_et_comptes_sans_n_plus_un(self):
        a = build_academy("VOLA", TYPES[0])
        avant_notes = self._compte(a.admin, "/api/grades/")
        avant_comptes = self._compte(a.admin, "/api/auth/users/")
        for i in range(10):
            u = User.objects.create_user(username=f"v{i}", email=f"v{i}@iso.test", password="x", role="student",
                                         first_name="E", last_name="X", school=a.school)
            s = Student.objects.create(user=u, school=a.school, first_name="E", last_name="X",
                                       current_class=a.klass, school_year=a.year, gender="F")
            e = StudentEnrollment.objects.create(student=s, school_year=a.year, class_obj=a.klass)
            for matiere in a.subjects:
                Grade.objects.create(student=s, subject=matiere, school_year=a.year, teacher=a.teacher,
                                     period="T1", value=10, enrollment=e)
        self.assertLessEqual(self._compte(a.admin, "/api/grades/"), avant_notes + 2)
        self.assertLessEqual(self._compte(a.admin, "/api/auth/users/"), avant_comptes + 2)


@override_settings(MEDIA_ROOT=tempfile.mkdtemp(prefix="feba-bul-"))
class AuteurBulletinTests(Base):
    def test_auteur_conserve_et_non_modifiable(self):
        from apps.bulletins.models import Bulletin
        r = client(self.a.admin).post("/api/bulletins/generate/", {
            "student_id": self.a.student.pk, "student": self.a.student.pk, "period": "T1",
            "school_year_id": self.a.year.pk, "school_year": self.a.year.pk}, format="json")
        self.assertIn(r.status_code, (200, 201), r.content)
        b = Bulletin.objects.get(student=self.a.student, period="T1", school_year=self.a.year)
        self.assertEqual(b.generated_by_id, self.a.admin.pk)
        client(self.a.admin).patch(f"/api/bulletins/{b.pk}/", {"generated_by": self.a.teacher_user.pk}, format="json")
        b.refresh_from_db()
        self.assertEqual(b.generated_by_id, self.a.admin.pk)
