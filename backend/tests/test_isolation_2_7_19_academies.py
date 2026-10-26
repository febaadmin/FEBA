"""
P0 — Isolation stricte avec 2, 7 et 19 académies de types différents.

Les académies sont créées par le service réel (`create_academy`) et
peuplées (élève noté, parent, enseignant, paiement, bulletin). Voir
tests/isolation_campaign.py pour la méthode. Aucune fuite tolérée, aucune
erreur serveur tolérée, aucune écriture croisée tolérée.
"""
import shutil
import tempfile

from django.test import TestCase, override_settings

from apps.bulletins.pdf_generator import generate_bulletin
from apps.grades.models import AppreciationRule
from apps.schools.models import School

from .academy_fixtures import TYPES, build_academy
from .isolation_campaign import run_cross_writes, run_list_and_detail

MEDIA = tempfile.mkdtemp(prefix="feba-iso-")


@override_settings(MEDIA_ROOT=MEDIA)
class _Campaign(TestCase):
    N = 0
    ROLE_SAMPLE = 0

    @classmethod
    def setUpTestData(cls):
        cls.academies = []
        for i in range(cls.N):
            academy = build_academy(f"T{i + 1:02d}Z", TYPES[i % len(TYPES)],
                                    grades=(10 + i % 9, 8 + i % 11))
            generate_bulletin(academy.student, "T1", academy.year)
            cls.academies.append(academy)

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA, ignore_errors=True)

    def test_types_varies_et_configuration_propre(self):
        types = {a.school.academy_type for a in self.academies}
        self.assertEqual(types, set(TYPES[:min(self.N, 3)]))
        rule_ids = [set(AppreciationRule.objects.filter(school=a.school).values_list("id", flat=True))
                    for a in self.academies]
        for i, ids in enumerate(rule_ids):
            self.assertEqual(len(ids), 9)
            for other in rule_ids[i + 1:]:
                self.assertFalse(ids & other, "barème partagé entre deux académies")
        self.assertEqual(School.objects.filter(code__startswith="AC_T").count(), self.N)

    def test_listes_et_details_sans_fuite(self):
        report = run_list_and_detail(self.academies, role_sample=self.ROLE_SAMPLE)
        self.assertGreater(report.requests, 100, "la campagne n'a presque rien vérifié")
        self.assertEqual(report.errors, [], "\n".join(report.errors[:40]))
        self.assertEqual(report.leaks, [], "\n".join(report.leaks[:40]))
        print(f"\n[isolation N={self.N}] {report.requests} requêtes vérifiées, "
              f"0 fuite, 0 erreur serveur")

    def test_ecritures_croisees_refusees(self):
        count = len(self.academies)
        pairs = [(self.academies[i], self.academies[(i + 1) % count]) for i in range(count)]
        breaches = []
        for attacker, victim in pairs:
            breaches += [f"{attacker.tag} → {victim.tag} : {b}" for b in run_cross_writes(attacker, victim)]
        self.assertEqual(breaches, [], "\n".join(breaches))


class TwoAcademiesIsolationTests(_Campaign):
    N = 2
    ROLE_SAMPLE = 2


class SevenAcademiesIsolationTests(_Campaign):
    N = 7
    ROLE_SAMPLE = 3


class NineteenAcademiesIsolationTests(_Campaign):
    N = 19
    ROLE_SAMPLE = 3


del _Campaign
