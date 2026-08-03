"""
Audit global — aucune vue n'expose une académie sans restriction.

POURQUOI CE TEST EXISTE
-----------------------
Les tests de cloisonnement écrits jusqu'ici vérifient les vues auxquelles
on a PENSÉ. Celui-ci part du routeur : il voit toutes les vues, y compris
celle qu'on ajoutera la semaine prochaine sans écrire de test.

Il ne prouve pas qu'une vue filtre CORRECTEMENT — une vue peut mentionner
« school » et se tromper. Il prouve qu'aucune vue ne l'ignore
complètement, ce qui est le défaut le plus facile à commettre et le plus
silencieux : la table entière sort, et rien ne le signale.
"""
from django.test import SimpleTestCase

from apps.core.management.commands.academy_scope_audit import (
    EXEMPTIONS, analyser,
)


class AcademyScopeAuditTests(SimpleTestCase):

    def test_aucune_vue_n_expose_une_academie_sans_restriction(self):
        problemes, examinees, _ = analyser()
        self.assertGreater(examinees, 0,
                           "l'audit n'a examiné aucune vue : il ne prouve rien")
        details = "\n".join(
            f"  · {p['vue']} ({p['modele']}) — {p['motif']} [{p['chemin']}]"
            for p in problemes)
        self.assertEqual(problemes, [], f"\n{details}")

    def test_chaque_exemption_porte_une_raison_ecrite(self):
        """
        Une exemption sans raison est une omission oubliée, pas un choix.
        C'est la seule chose qui distingue les deux, six mois plus tard.
        """
        for vue, raison in EXEMPTIONS.items():
            with self.subTest(vue=vue):
                self.assertTrue(raison.strip(),
                                f"« {vue} » est exemptée sans raison écrite.")
                self.assertGreater(
                    len(raison.strip()), 25,
                    f"La raison donnée pour « {vue} » est trop courte pour "
                    f"être vérifiable.")
