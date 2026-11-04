"""
Nombre de requêtes SQL des listes : constant, quel que soit le volume.

Mesuré le 04/11/2026 sur les données de démonstration : /api/teachers/
exécutait 1 099 requêtes (une lecture d'académie, de matières et d'effectif
par classe de chaque enseignant), /api/classes/ 227, my_classes 226.
"""
from django.core.management import call_command
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient

from apps.accounts.models import CustomUser


class PlafondRequetesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo_data", verbosity=0)

    def mesurer(self, role, url):
        u = CustomUser.objects.filter(role=role, is_active=True).order_by("pk").first()
        c = APIClient(SERVER_NAME="localhost")
        c.force_authenticate(u)
        with CaptureQueriesContext(connection) as q:
            r = c.get(url)
        self.assertEqual(r.status_code, 200, url)
        return len(q.captured_queries), r.data

    def test_listes_en_nombre_constant_de_requetes(self):
        for role, url, plafond in (("admin", "/api/teachers/", 12), ("superadmin", "/api/teachers/", 12),
                                   ("parent", "/api/teachers/", 14), ("admin", "/api/classes/", 12),
                                   ("admin", "/api/classes/?all_years=1", 12), ("teacher", "/api/teachers/my_classes/", 10)):
            n, _ = self.mesurer(role, url)
            self.assertLessEqual(n, plafond, f"{role} {url} : {n} requêtes")

    def test_contenu_des_classes_inchange(self):
        _, data = self.mesurer("admin", "/api/classes/?all_years=1")
        from apps.classes.models import Class
        for ligne in data.get("results", data):
            classe = Class.objects.get(pk=ligne["id"])
            self.assertEqual(ligne["fr_subject_count"], classe.get_fr_subjects().count())
            self.assertEqual(ligne["en_subject_count"], classe.get_en_subjects().count())
            self.assertEqual(ligne["has_bilingual"], classe.has_bilingual_subjects())
            self.assertEqual(ligne["missing_languages"], classe.missing_subject_languages())
            self.assertEqual(sorted(ligne["subject_ids"]), sorted(classe.subjects.values_list("id", flat=True)))
            inscrits = classe.enrollments.filter(student__is_active=True).values("student").distinct().count()
            self.assertEqual(ligne["student_count"], inscrits or classe.students.filter(is_active=True).count())
