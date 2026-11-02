"""Une référence déjà prise est retirée au sort, au lieu de faire échouer l'enregistrement."""
from unittest import mock
from uuid import UUID

from django.test import TestCase

from apps.payments.models import Payment


class ReferencePaiementTests(TestCase):
    def test_collision_retiree(self):
        pris = Payment(reference_number="x")
        with mock.patch("apps.payments.models.uuid.uuid4", side_effect=[UUID(int=0xABCDEF << 104), UUID(int=0x123456 << 104)]), \
                mock.patch.object(Payment.objects, "filter") as filtre:
            filtre.return_value.exists.side_effect = [True, False]
            reference = pris._nouvelle_reference()
        self.assertTrue(reference.endswith("-123456"), reference)
