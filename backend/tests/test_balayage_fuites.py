"""
Balayage de toutes les routes GET sans paramètre de l'API : une donnée d'une
autre académie, ou d'un autre élève, ne doit apparaître dans aucune réponse.
"""
from django.test import TestCase
from django.urls import get_resolver
from django.urls.resolvers import URLPattern, URLResolver
from rest_framework.test import APIClient

from apps.classes.models import Class
from apps.parents.models import Parent, ParentStudent
from apps.schools.models import Level, School, SchoolYear
from apps.students.models import Student
from apps.teachers.models import Teacher
from tests.test_virtualclass import make_user

PUBLIC = (
    "/api/website/", "/api/health/", "/api/schema", "/api/docs", "/api/redoc",
)


def routes():
    def parcourir(motifs, prefixe=""):
        for motif in motifs:
            texte = prefixe + str(motif.pattern)
            if isinstance(motif, URLResolver):
                yield from parcourir(motif.url_patterns, texte)
            elif isinstance(motif, URLPattern):
                yield texte

    vues = set()
    for texte in parcourir(get_resolver().url_patterns):
        chemin = texte.replace("^", "").replace("$", "")
        if not chemin.startswith("api/") or "<" in chemin or "(?P" in chemin or ".(" in chemin or "format" in chemin:
            continue
        vues.add("/" + chemin.rstrip("\\"))
    return sorted(vues)


class BalayageTests(TestCase):
    def academie(self, code, marque):
        school = School.objects.create(name=f"Ecole{marque}", code=code, email=f"{code}@t.bj", phone="1",
                                       address="x", slug=code.lower())
        annee = SchoolYear.objects.create(school=school, name=f"An{marque}", start_date="2026-09-01",
                                          end_date="2027-06-30", is_current=True)
        niveau = Level.objects.create(school=school, name=f"Niv{marque}", order=1, cycle="primaire")
        return school, annee, niveau

    def setUp(self):
        self.a, an, niv = self.academie("AAA", "ZZAAA")
        self.b, bn, nib = self.academie("BBB", "ZZBBB")
        ca = Class.objects.create(name="ClasseA", level=niv, school_year=an)
        cc = Class.objects.create(name="ClasseC", level=niv, school_year=an)
        cb = Class.objects.create(name="ClasseZZBBB", level=nib, school_year=bn)

        def eleve(ecole, classe, nom, mail):
            u = make_user(mail, "student", ecole)
            return Student.objects.create(user=u, school=ecole, first_name=nom, last_name=nom,
                                          current_class=classe, school_year=classe.school_year)

        self.e1 = eleve(self.a, ca, "Moi", "e1@t.bj")
        self.voisin = eleve(self.a, cc, "ZZVOISIN", "voisin@t.bj")
        self.etranger = eleve(self.b, cb, "ZZETRANGER", "etr@t.bj")
        self.parent = make_user("p1@t.bj", "parent", self.a)
        ParentStudent.objects.create(parent=Parent.objects.create(user=self.parent), student=self.e1,
                                     relationship="mother")
        self.prof = make_user("t1@t.bj", "teacher", self.a)
        Teacher.objects.create(user=self.prof).classes.add(ca)
        self.admin = make_user("ad@t.bj", "admin", self.a)

    def balayer(self, user):
        c = APIClient()
        if user:
            c.force_authenticate(user)
        for chemin in routes():
            try:
                rep = c.get(chemin)
            except Exception as exc:
                yield chemin, 599, repr(exc)[:120]
                continue
            contenu = rep.content.decode(errors="ignore") if not getattr(rep, "streaming", False) else ""
            yield chemin, rep.status_code, contenu

    def test_sans_connexion_rien_de_prive(self):
        ouvertes = [c for c, st, _ in self.balayer(None) if st == 200 and not c.startswith(PUBLIC)]
        self.assertEqual(ouvertes, [])

    def test_aucune_fuite_entre_academies(self):
        for user in (self.e1.user, self.parent, self.prof, self.admin):
            fuites = [c for c, st, t in self.balayer(user) if st == 200 and ("ZZETRANGER" in t or "ZZBBB" in t)]
            self.assertEqual(fuites, [], user.email)

    def test_famille_sans_les_donnees_d_un_autre_eleve(self):
        for user in (self.e1.user, self.parent):
            fuites = [c for c, st, t in self.balayer(user) if st == 200 and "ZZVOISIN" in t]
            self.assertEqual(fuites, [], user.email)

    def test_aucune_erreur_serveur(self):
        for user in (None, self.e1.user, self.parent, self.prof, self.admin):
            erreurs = [(c, s) for c, s, _ in self.balayer(user) if s >= 500 and s != 503]
            self.assertEqual(erreurs, [], getattr(user, "email", "anonyme"))

    def test_le_balayage_voit_bien_les_donnees(self):
        # Sans ce témoin, un balayage qui n'atteint rien passerait pour réussi.
        self.assertGreater(len(routes()), 100)
        admin_b = make_user("adb@t.bj", "admin", self.b)
        vues = [c for c, st, t in self.balayer(admin_b) if st == 200 and "ZZETRANGER" in t]
        self.assertTrue(vues)
        self.assertIn("/api/students/", vues)

    def test_ecritures_ouvertes_aux_familles_et_enseignants(self):
        # Un POST vide répond 400 quand le droit est accordé : toute route qui
        # s'ouvre à ces rôles doit figurer ici, délibérément.
        commun = {
            "/api/auth/avatar/", "/api/auth/change-password/", "/api/auth/login/", "/api/auth/logout/",
            "/api/auth/refresh/", "/api/messages/conversations/", "/api/payments/card/checkout/",
            "/api/payments/webhook/stripe/", "/api/user-files/", "/api/website/contact/",
            "/api/website/fha/contact/", "/api/website/fha/enroll/", "/api/website/fha/placement-test/",
            "/api/website/preregistrations/",
        }
        enseignant = commun | {
            "/api/attendance/", "/api/attendance/bulk/", "/api/grades/", "/api/grades/appreciations/preview/",
            "/api/grades/bulk-create/", "/api/grades/bulk_save/", "/api/homework/", "/api/virtual-rooms/",
            "/api/virtual-rooms/bulk-delete/",
        }
        for user, permis in ((self.e1.user, commun), (self.parent, commun), (self.prof, enseignant)):
            c = APIClient()
            c.force_authenticate(user)
            ouvertes = {r for r in routes() if c.post(r, {}, format="json").status_code not in (401, 403, 404, 405)}
            self.assertEqual(ouvertes - permis, set(), user.email)
