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


def routes_detail():
    """Routes GET à un identifiant, avec « {} » à la place de l'identifiant."""
    def parcourir(motifs, prefixe=""):
        for motif in motifs:
            texte = prefixe + str(motif.pattern)
            if isinstance(motif, URLResolver):
                yield from parcourir(motif.url_patterns, texte)
            elif isinstance(motif, URLPattern):
                yield texte

    import re
    vues = set()
    for texte in parcourir(get_resolver().url_patterns):
        if "format" in texte:
            continue
        chemin = re.sub(r"\(\?P<\w*(pk|id)\w*>[^)]*\)|<(int:)?\w*(pk|id)\w*>", "{}", texte)
        chemin = chemin.replace("^", "").replace("$", "").rstrip("\\")
        if not chemin.startswith("api/"):
            continue
        if chemin.count("{}") == 1 and "<" not in chemin and "(" not in chemin:
            vues.add("/" + chemin)
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

    def test_comptes_sans_profil_jamais_d_erreur_serveur(self):
        for role in ("teacher", "student", "parent"):
            user = make_user(f"sans-profil-{role}@t.bj", role, self.a)
            erreurs = [(c, s) for c, s, _ in self.balayer(user) if s >= 500 and s != 503]
            self.assertEqual(erreurs, [], role)

    def test_champs_malformes_jamais_d_erreur_serveur(self):
        # Origine des incidents de notes : un objet reçu à la place d'un texte.
        cles = ("justification", "message", "comment", "body", "subject", "reason", "name", "title",
                "description", "notes", "email", "recipient", "recipient_id", "student", "student_id",
                "class_id", "school_year", "school_year_id", "period", "status", "scope", "kind", "template",
                "values", "copy_from", "ids", "amount", "academy_id", "subject_id", "date", "records")
        c = APIClient()
        c.raise_request_exception = False
        c.force_authenticate(self.admin)
        erreurs = []
        for valeur in ({"objet": 1}, ["liste"], "abc", 123456789):
            charge = {cle: valeur for cle in cles}
            erreurs += [(r, repr(valeur)) for r in routes() if c.post(r, charge, format="json").status_code == 500]
        self.assertEqual(erreurs, [])

    def test_lien_parent_eleve_d_une_autre_academie_intouchable(self):
        lien = ParentStudent.objects.get(student=self.e1)
        admin_b = make_user("admb@t.bj", "admin", self.b)
        c = APIClient()
        c.force_authenticate(admin_b)
        rep = c.post("/api/parents/remove_child/", {"parent_id": lien.parent_id, "student_id": self.e1.pk}, format="json")
        self.assertEqual(rep.status_code, 404)
        self.assertTrue(ParentStudent.objects.filter(pk=lien.pk).exists())
        c.force_authenticate(self.admin)
        rep = c.post("/api/parents/remove_child/", {"parent_id": lien.parent_id, "student_id": self.e1.pk}, format="json")
        self.assertEqual(rep.status_code, 200)
        self.assertFalse(ParentStudent.objects.filter(pk=lien.pk).exists())

    def test_parents_d_un_eleve_illisibles_depuis_une_autre_academie(self):
        admin_b = make_user("admb2@t.bj", "admin", self.b)
        c = APIClient()
        c.force_authenticate(admin_b)
        rep = c.get(self.chemin_parents_eleve(), {"student_id": self.e1.pk})
        self.assertFalse(rep.data["assigned"])
        c.force_authenticate(self.admin)
        self.assertTrue(c.get(self.chemin_parents_eleve(), {"student_id": self.e1.pk}).data["assigned"])
        for user in (self.voisin.user, self.parent, self.prof):
            c.force_authenticate(user)
            self.assertEqual(c.get(self.chemin_parents_eleve(), {"student_id": self.e1.pk}).status_code, 403)

    def chemin_parents_eleve(self):
        return "/api/parents/check_child_assignment/"

    def test_routes_a_identifiant_et_parametres_sans_fuite(self):
        from datetime import date

        from apps.bulletins.models import Bulletin
        from apps.payments.models import Payment

        Payment.objects.create(student=self.voisin, school_year=self.voisin.school_year, amount=10,
                               payment_type="mensualite", payment_method="cash", payment_date=date(2026, 10, 1))
        Bulletin.objects.create(student=self.voisin, school_year=self.voisin.school_year, period="T1",
                                pdf_file="bulletins/v.pdf")
        admin_b = make_user("adm3@t.bj", "admin", self.b)
        identifiants = range(1, 13)
        self.assertGreater(len(routes_detail()), 60)
        for user in (self.e1.user, self.parent, self.prof, admin_b):
            c = APIClient()
            c.raise_request_exception = False
            c.force_authenticate(user)
            fuites = []
            for gabarit in routes_detail():
                for pk in identifiants:
                    rep = c.get(gabarit.format(pk))
                    if rep.status_code == 200 and not getattr(rep, "streaming", False) and b"ZZVOISIN" in rep.content:
                        fuites.append(gabarit)
            params = {"student": self.voisin.pk, "student_id": self.voisin.pk, "school": self.a.pk,
                      "school_id": self.a.pk, "class": self.voisin.current_class_id,
                      "class_id": self.voisin.current_class_id, "academy": self.a.pk}
            for chemin in routes():
                rep = c.get(chemin, params)
                if rep.status_code == 200 and not getattr(rep, "streaming", False) and b"ZZVOISIN" in rep.content:
                    fuites.append(chemin + "?")
            self.assertEqual(sorted(set(fuites)), [], user.email)

    def test_fiches_et_moyennes_de_classe_reservees(self):
        classe = self.e1.current_class
        chemins = (f"/api/classes/{classe.pk}/students/", f"/api/grades/class-averages/?class={classe.pk}")
        c = APIClient()
        for user, attendus in ((self.e1.user, (403,)), (self.parent, (403,)), (self.voisin.user, (403, 404)),
                               (self.prof, (200,)), (self.admin, (200,))):
            c.force_authenticate(user)
            for chemin in chemins:
                self.assertIn(c.get(chemin).status_code, attendus, (user.email, chemin))
        autre_prof = make_user("t2@t.bj", "teacher", self.a)
        Teacher.objects.create(user=autre_prof)
        c.force_authenticate(autre_prof)
        for chemin in chemins:
            self.assertIn(c.get(chemin).status_code, (403, 404), chemin)

    def test_moyennes_d_un_eleve_reservees(self):
        c = APIClient()
        for chemin in ("/api/grades/averages/", "/api/grades/bilingual/", "/api/grades/student-summary/"):
            for user, cible, permis in ((self.voisin.user, self.e1, False), (self.parent, self.voisin, False),
                                        (self.prof, self.voisin, False), (self.e1.user, self.e1, True),
                                        (self.parent, self.e1, True), (self.prof, self.e1, True),
                                        (self.admin, self.voisin, True)):
                c.force_authenticate(user)
                statut = c.get(chemin, {"student": cible.pk}).status_code
                self.assertEqual(statut != 403, permis, (chemin, user.email, statut))

