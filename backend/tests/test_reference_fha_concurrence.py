"""
Deux familles déposent leur dossier FHA au même instant : chacune calcule
« dernier numéro + 1 » avant que l'autre n'ait enregistré le sien, donc le même
numéro. La référence étant unique, le second dépôt échouait en erreur 500.
Le dépôt doit réussir pour les deux, avec deux références distinctes.
"""
from datetime import date
from unittest import mock

from django.test import TestCase

from apps.schools.models import School
from apps.website.models import FHAEnrollmentApplication, FHAPlacementTestRequest


class ReferenceConcurrenteTests(TestCase):
    def setUp(self):
        self.fha, _ = School.objects.update_or_create(
            code=School.CODE_FEBA_FHA,
            defaults=dict(name="FEBA French Heritage Academy", address="En ligne", entity_type="online", currency_code="USD"))

    def dossier(self, prenom):
        return FHAEnrollmentApplication(
            entity=self.fha, child_first_name=prenom, child_last_name="Adjovi", child_birth_date=date(2015, 4, 12),
            parent1_first_name="Chris", parent1_last_name="Adjovi", parent1_email="c@example.org", parent1_phone="+22901020304")

    def test_inscriptions_simultanees(self):
        premier = self.dossier("Amélie")
        numero_calcule_trop_tot = premier.generate_reference()
        self.dossier("Bruno").save()  # l'autre famille enregistre entre-temps
        # Le premier dépôt reprend avec la référence calculée avant l'autre.
        with mock.patch.object(FHAEnrollmentApplication, "generate_reference",
                               side_effect=[numero_calcule_trop_tot, FHAEnrollmentApplication.generate_reference(premier)]):
            premier.save()
        refs = list(FHAEnrollmentApplication.objects.values_list("reference", flat=True))
        self.assertEqual(len(refs), 2)
        self.assertEqual(len(set(refs)), 2)

    def test_tests_de_placement_simultanes(self):
        def demande(prenom):
            return FHAPlacementTestRequest(entity=self.fha, child_first_name=prenom, child_last_name="Smith",
                                           child_birth_date=date(2016, 3, 2), parent_email="p@x.com",
                                           parent_first_name="Paul", parent_last_name="Smith", parent_phone="+15550000000")
        premiere = demande("Ben")
        trop_tot = premiere.generate_reference()
        demande("Zoé").save()
        with mock.patch.object(FHAPlacementTestRequest, "generate_reference",
                               side_effect=[trop_tot, FHAPlacementTestRequest.generate_reference(premiere)]):
            premiere.save()
        refs = list(FHAPlacementTestRequest.objects.values_list("reference", flat=True))
        self.assertEqual(len(set(refs)), 2)

    def test_reference_fournie_jamais_reecrite(self):
        d = self.dossier("Chloé")
        d.reference = "FHA-2026-9000"
        d.save()
        self.assertEqual(FHAEnrollmentApplication.objects.get(pk=d.pk).reference, "FHA-2026-9000")
