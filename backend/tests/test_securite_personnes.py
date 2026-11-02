"""IDOR : dans UNE MÊME académie, un compte ne lit pas les données d'une personne sans lien avec lui."""
import datetime
import re

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.attendance.models import Attendance
from apps.bulletins.pdf_generator import generate_bulletin
from apps.classes.models import Class
from apps.grades.models import Grade
from apps.parents.models import Parent, ParentStudent
from apps.payments.models import Payment
from apps.students.models import Student, StudentEnrollment

from .academy_fixtures import TYPES, build_academy
from .isolation_campaign import routes

MARQUE = "VOISINQX"
#: Annuaires autorisés par conception : classes et destinataires de messagerie ne portent pas ces données.
LISTES_LIBRES = re.compile(r"/api/(auth/recipients|messages/recipients)")


class MemeAcademieTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.a = a = build_academy("IDORA", TYPES[0])
        autre = Class.objects.create(name="Classe-Autre", level=a.level, school_year=a.year)
        U = get_user_model()
        u = U.objects.create_user(username="voisin", email="voisin@iso.test", password="Pass1234!", role="student",
                                  first_name=MARQUE, last_name=MARQUE, school=a.school)
        cls.voisin = v = Student.objects.create(user=u, school=a.school, first_name=MARQUE, last_name=MARQUE,
                                                current_class=autre, school_year=a.year, gender="M")
        e = StudentEnrollment.objects.create(student=v, school_year=a.year, class_obj=autre)
        autre.subjects.set(a.subjects)
        cls.note = Grade.objects.create(student=v, subject=a.subjects[0], school_year=a.year, teacher=a.teacher,
                                        period="T1", value=7, enrollment=e, comment=MARQUE)
        pu = U.objects.create_user(username="pv", email="pv@iso.test", password="Pass1234!", role="parent",
                                   first_name=MARQUE, last_name=MARQUE, school=a.school)
        cls.parent_v = Parent.objects.create(user=pu)
        ParentStudent.objects.create(student=v, parent=cls.parent_v)
        cls.paiement = Payment.objects.create(student=v, school_year=a.year, amount="100.00", payment_type="inscription",
                                              payment_method="cash", payment_date=datetime.date(2026, 9, 15), notes=MARQUE)
        cls.absence = Attendance.objects.create(student=v, date=datetime.date(2026, 10, 1), status="absent", school_year=a.year)
        generate_bulletin(v, "T1", a.year)
        cls.bulletin = v.bulletins.first()
        # L'enseignant de la fixture a noté le voisin : on teste un collègue sans lien.
        tu = U.objects.create_user(username="ta", email="ta@iso.test", password="Pass1234!", role="teacher",
                                   first_name="Sans", last_name="Lien", school=a.school)
        from apps.teachers.models import Teacher
        cls.prof = Teacher.objects.create(user=tu)
        cls.prof.classes.add(a.klass)

    def comptes(self):
        return {"student": self.a.student_user, "parent": self.a.parent_user, "teacher": self.prof.user}

    def test_temoin_l_administrateur_voit_bien_la_marque(self):
        """Sans ce témoin, un test qui ne trouve rien ne prouverait rien."""
        c = APIClient(HTTP_HOST="localhost")
        c.force_authenticate(self.a.admin)
        self.assertIn(MARQUE, c.get("/api/students/", {"page_size": 1000}).content.decode().upper())
        self.assertEqual(c.get(f"/api/grades/{self.note.pk}/").status_code, 200)

    def test_listes(self):
        fuites = []
        listes, _ = routes()
        for role, compte in self.comptes().items():
            c = APIClient(HTTP_HOST="localhost")
            c.force_authenticate(compte)
            for chemin in listes:
                if LISTES_LIBRES.match(chemin):
                    continue
                r = c.get(chemin, {"page_size": 1000})
                if r.status_code == 200 and "json" in r.get("Content-Type", "") and MARQUE in r.content.decode("utf-8", "replace").upper():
                    fuites.append(f"{role} {chemin}")
        self.assertEqual(fuites, [], "\n".join(fuites))

    def test_objets_par_identifiant(self):
        objets = {
            f"/api/grades/{self.note.pk}/": ("get", "patch", "delete"),
            f"/api/payments/{self.paiement.pk}/": ("get", "patch", "delete"),
            f"/api/attendance/{self.absence.pk}/": ("get", "patch", "delete"),
            f"/api/bulletins/{self.bulletin.pk}/": ("get", "delete"),
            f"/api/students/{self.voisin.pk}/": ("get", "patch", "delete"),
            f"/api/parents/{self.parent_v.pk}/": ("get", "patch", "delete"),
            f"/api/suivi/eleves/{self.voisin.pk}/fiche/": ("get",),
            f"/api/payments/{self.paiement.pk}/generate-receipt/": ("post",),
        }
        permis = []
        for role, compte in self.comptes().items():
            c = APIClient(HTTP_HOST="localhost")
            c.force_authenticate(compte)
            for chemin, methodes in objets.items():
                for m in methodes:
                    r = getattr(c, m)(chemin, {"reason": "x"} if m == "delete" else {}, format="json")
                    if r.status_code < 300:
                        permis.append(f"{role} {m.upper()} {chemin} -> {r.status_code}")
        self.assertEqual(permis, [], "\n".join(permis))
