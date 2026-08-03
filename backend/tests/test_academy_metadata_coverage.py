"""
Tests d'IDENTIFICATION DES DONNÉES PAR ACADÉMIE (P2).

Deux exigences, souvent confondues :

  1. IDENTIFIER — en mode « Toutes les Académies », chaque objet renvoyé
     doit dire à quelle académie il appartient. Sans cela, deux élèves
     homonymes de deux académies sont indiscernables à l'écran.

  2. TOTALISER — le total du mode consolidé doit être exactement la somme
     des académies. Ce n'était pas le cas : le filtre « année courante »
     s'écrivait `filter(school=school, is_current=True).first()`, qui
     retourne None quand aucune académie n'est active. Le filtre était
     alors SILENCIEUSEMENT abandonné et la vue consolidée remontait tout
     l'historique — 270 paiements « toutes académies » pour 90 à FEBA et
     0 à FEBA FHA.

Le second point est le plus trompeur : rien à l'écran ne signalait
l'anomalie, les chiffres étaient simplement faux.
"""
import datetime

from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import CustomUser
from apps.classes.models import Class
from apps.grades.models import Grade
from apps.payments.models import Payment
from apps.schools.models import Level, School, SchoolYear
from apps.students.models import Student
from apps.subjects.models import Subject


def auth(client, email, password="Pass1234!"):
    resp = client.post("/api/auth/login/", {"email": email, "password": password})
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {resp.data.get('access', '')}")
    return client


def rows(resp):
    data = resp.data
    if isinstance(data, dict) and "results" in data:
        return data["results"]
    return data


def switch(client, entity_id):
    """`entity_id=""` bascule en mode « Toutes les Académies »."""
    return client.post("/api/auth/entity-context/switch/", {"entity_id": entity_id})


class AcademyMetadataCoverageTests(TestCase):
    """Deux académies peuplées, mêmes types de données de chaque côté."""

    #: Endpoints qui doivent TOUS porter les métadonnées d'académie.
    ENDPOINTS = [
        "/api/students/",
        "/api/auth/users/",
        "/api/classes/",
        "/api/subjects/",
        "/api/teachers/",
        "/api/grades/",
        "/api/payments/",
        "/api/schools/years/",
        "/api/schools/levels/",
    ]

    @classmethod
    def setUpTestData(cls):
        cls.feba = School.objects.create(
            name="FEBA Cotonou", address="Akpakpa", entity_type="campus", code="META-FEBA",
        )
        cls.fha = School.objects.create(
            name="FEBA French Heritage Academy", address="En ligne",
            entity_type="online", code="META-FHA",
        )

        for key, school, count in (("feba", cls.feba, 3), ("fha", cls.fha, 2)):
            # Une année PASSÉE en plus de l'année courante : c'est elle qui
            # remontait à tort dans la vue consolidée.
            SchoolYear.objects.create(
                school=school, name=f"2024-2025-{key}", is_current=False,
                start_date="2024-09-01", end_date="2025-07-01",
            )
            year = SchoolYear.objects.create(
                school=school, name=f"2025-2026-{key}", is_current=True,
                start_date="2025-09-01", end_date="2026-07-01",
            )
            level = Level.objects.create(school=school, name=f"Niveau {key}", order=1)
            klass = Class.objects.create(school_year=year, level=level, name=f"Classe {key}")
            subject = Subject.objects.create(school=school, name=f"Français {key}", code=f"FR{key}")
            teacher_user = CustomUser.objects.create_user(
                username=f"meta_teacher_{key}", email=f"meta.teacher.{key}@test.io",
                password="Pass1234!", role="teacher", school=school,
                first_name="Prof", last_name=key.upper(),
            )
            from apps.teachers.models import Teacher
            teacher = Teacher.objects.create(user=teacher_user)
            CustomUser.objects.create_user(
                username=f"meta_admin_{key}", email=f"meta.admin.{key}@test.io",
                password="Pass1234!", role="admin", school=school,
                first_name="Admin", last_name=key.upper(),
            )
            for index in range(count):
                student = Student.objects.create(
                    school=school, school_year=year, current_class=klass,
                    first_name=f"Eleve{index}", last_name=key.upper(),
                    date_of_birth=datetime.date(2014, 1, 1 + index),
                )
                Grade.objects.create(
                    student=student, subject=subject, teacher=teacher,
                    school_year=year, period="T1", value=15,
                )
                Payment.objects.create(
                    student=student, school_year=year, amount=1000,
                    payment_type="mensualite", payment_method="cash",
                    payment_date=datetime.date(2025, 10, 1),
                )
                # La même donnée sur l'année PASSÉE : elle ne doit apparaître
                # ni par académie, ni en mode consolidé.
                past = SchoolYear.objects.get(school=school, name=f"2024-2025-{key}")
                Payment.objects.create(
                    student=student, school_year=past, amount=900,
                    payment_type="mensualite", payment_method="cash",
                    payment_date=datetime.date(2024, 10, 1),
                )

        cls.superadmin = CustomUser.objects.create_user(
            username="meta_super", email="meta.super@test.io", password="Pass1234!",
            role="superadmin", first_name="Super", last_name="Admin",
        )

    # ── 1. Chaque objet dit à quelle académie il appartient ──────────────

    def test_tous_les_endpoints_exposent_les_metadonnees_d_academie(self):
        client = auth(APIClient(), "meta.super@test.io")
        switch(client, self.feba.id)

        for endpoint in self.ENDPOINTS:
            with self.subTest(endpoint=endpoint):
                data = rows(client.get(endpoint))
                self.assertTrue(data, f"{endpoint} ne renvoie aucune donnée à tester")
                first = data[0]
                for field in ("academy_id", "academy_code", "academy_name", "academy_short_name"):
                    self.assertIn(field, first, f"{endpoint} n'expose pas {field}")

    def test_le_nom_court_est_exploitable_dans_un_tableau(self):
        """
        « FEBA French Heritage Academy » ne tient pas dans une colonne :
        sans version courte, les deux académies devenaient indiscernables
        une fois tronquées.
        """
        client = auth(APIClient(), "meta.admin.fha@test.io")
        row = rows(client.get("/api/students/"))[0]
        self.assertEqual(row["academy_name"], "FEBA French Heritage Academy")
        self.assertEqual(row["academy_short_name"], "META-FHA")
        self.assertLess(len(row["academy_short_name"]), len(row["academy_name"]))

    def test_en_mode_consolide_les_deux_academies_sont_distinguables(self):
        client = auth(APIClient(), "meta.super@test.io")
        switch(client, "")
        codes = {row["academy_code"] for row in rows(client.get("/api/students/"))}
        self.assertEqual(codes, {"META-FEBA", "META-FHA"})

    def test_un_objet_sans_academie_reste_signale_et_non_masque(self):
        """
        Le superadmin est un rôle plateforme : il n'appartient à aucune
        académie. Renvoyer `null` permet à l'interface d'afficher
        « Sans académie » — le faire disparaître de la liste serait pire.
        """
        client = auth(APIClient(), "meta.super@test.io")
        switch(client, "")
        sans_academie = [
            row for row in rows(client.get("/api/auth/users/"))
            if row["academy_code"] is None
        ]
        self.assertEqual([row["email"] for row in sans_academie], ["meta.super@test.io"])

    # ── 2. Le total consolidé est la somme des académies ─────────────────

    def _totaux(self, client, endpoint):
        switch(client, self.feba.id)
        a = len(rows(client.get(endpoint)))
        switch(client, self.fha.id)
        b = len(rows(client.get(endpoint)))
        switch(client, "")
        total = len(rows(client.get(endpoint)))
        return a, b, total

    def test_le_total_consolide_est_la_somme_des_academies(self):
        client = auth(APIClient(), "meta.super@test.io")
        for endpoint in ["/api/students/", "/api/classes/", "/api/subjects/",
                         "/api/grades/", "/api/schools/levels/"]:
            with self.subTest(endpoint=endpoint):
                a, b, total = self._totaux(client, endpoint)
                self.assertEqual(total, a + b, f"{endpoint} : {total} ≠ {a} + {b}")

    def test_le_mode_consolide_n_ajoute_pas_les_annees_passees(self):
        """
        Régression exacte du symptôme : le filtre « année courante »
        disparaissait faute d'académie active, et l'historique remontait.
        """
        client = auth(APIClient(), "meta.super@test.io")
        a, b, total = self._totaux(client, "/api/payments/")
        self.assertEqual(a, 3)   # année courante FEBA seulement
        self.assertEqual(b, 2)   # année courante FHA seulement
        self.assertEqual(total, 5)
        # Sans le correctif, on obtenait 10 : les deux années des deux académies.
        self.assertNotEqual(total, 10)

    def test_l_historique_reste_accessible_a_la_demande(self):
        """Le filtre par défaut ne doit pas rendre l'historique inatteignable."""
        client = auth(APIClient(), "meta.super@test.io")
        switch(client, "")
        total = len(rows(client.get("/api/payments/", {"all_years": "1"})))
        self.assertEqual(total, 10)
