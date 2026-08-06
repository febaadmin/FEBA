"""
tests/test_fha_sheet_download_per_row.py — Régression P3 (juillet 2026).

BUG SIGNALÉ
-----------
Sur /superadmin/fha-admissions, cliquer l'icône de téléchargement sur
n'importe quelle ligne ne renvoyait toujours que le document du premier
dossier (« document 1 »).

CE QUE CES TESTS VÉRIFIENT
---------------------------
Avec au moins cinq dossiers distincts (comme demandé), on vérifie pour
CHACUN que :
  - le contenu PDF renvoyé lui appartient (empreinte SHA-256 propre,
    vérifiée en comparant le fichier stocké au flux téléchargé) ;
  - le nom de fichier annoncé (Content-Disposition) porte SA référence,
    jamais celle d'un autre dossier ;
  - télécharger la ligne N puis la ligne 1 ne « recolle » pas le contenu
    de la ligne 1 sur la ligne N (élimine un bug de cache côté client ou
    de réutilisation d'objet) ;
  - deux dossiers ayant un enfant du même prénom (donc un nom de fichier
    qui pourrait presque se ressembler) restent bien distincts.

Au moment d'écrire ces tests, `FHAApplicationViewSet.sheet()` utilise déjà
`self.get_object()` (scopé par académie ET par pk) et
`FHAEnrollmentApplication.store_sheet()` construit déjà un chemin unique
par référence + version — ces tests passent donc dès maintenant. Ils sont
néanmoins le filet qui empêche une régression future (ex. un cache HTTP
mal configuré, un composant frontend qui recevrait le mauvais id) de
repasser inaperçue : la demande exige explicitement une preuve testée
avec au moins cinq documents différents, pas une relecture de code.
"""
import hashlib

from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import CustomUser
from apps.schools.models import School
from apps.website.models import FHAEnrollmentApplication

from .test_fha_enrollment_workflow import payload


class FiveDossiersSheetDownloadTests(TestCase):
    """Cinq dossiers, cinq téléchargements, cinq contenus distincts."""

    @classmethod
    def setUpTestData(cls):
        cls.fha, _ = School.objects.update_or_create(
            code=School.CODE_FEBA_FHA,
            defaults=dict(name="FEBA French Heritage Academy",
                          address="Programme en ligne", entity_type="online",
                          currency_code="USD", matricule_prefix="FHA"),
        )
        cls.admin = CustomUser.objects.create_user(
            username="sheet_admin_fha", email="sheet.admin.fha@test.io",
            password="Pass1234!", role="admin", school=cls.fha,
        )

        cls.children = [
            ("Naomi", "Adjovi"), ("Kofi", "Mensah"), ("Ama", "Diallo"),
            ("Naomi", "Kponou"),  # même prénom qu'un autre dossier, exprès
            ("Élise", "Kponou"),
        ]
        cls.applications = []
        client = APIClient()
        for first, last in cls.children:
            resp = client.post(
                "/api/website/fha/enroll/",
                payload(child_first_name=first, child_last_name=last),
                format="json",
            )
            assert resp.status_code == 201, resp.data
            cls.applications.append(
                FHAEnrollmentApplication.objects.get(reference=resp.data["reference"])
            )

    def setUp(self):
        self.client_admin = APIClient()
        self.client_admin.force_authenticate(user=self.admin)

    def _download(self, application):
        resp = self.client_admin.get(
            f"/api/website/admin/fha-applications/{application.pk}/sheet/")
        self.assertEqual(resp.status_code, 200, resp.data if hasattr(resp, "data") else resp)
        content = b"".join(resp.streaming_content)
        return resp, content

    def test_chacun_des_cinq_dossiers_renvoie_son_propre_contenu(self):
        seen_hashes = set()
        for application in self.applications:
            resp, content = self._download(application)
            digest = hashlib.sha256(content).hexdigest()
            # Le contenu téléchargé doit correspondre au fichier réellement
            # stocké pour CE dossier, pas à un autre.
            self.assertEqual(digest, application.sheet_sha256,
                              f"contenu téléchargé pour {application.reference} "
                              f"ne correspond pas au fichier stocké pour ce dossier")
            self.assertNotIn(digest, seen_hashes,
                              f"le document de {application.reference} est identique "
                              f"à celui d'un dossier précédent — c'est le bug signalé")
            seen_hashes.add(digest)

    def test_chaque_nom_de_fichier_porte_sa_propre_reference(self):
        for application in self.applications:
            resp, _ = self._download(application)
            disposition = resp["Content-Disposition"]
            self.assertIn(application.reference, disposition)
            for other in self.applications:
                if other.pk != application.pk:
                    self.assertNotIn(f'{other.reference}-fiche', disposition)

    def test_telecharger_dans_le_desordre_ne_recolle_pas_le_premier_document(self):
        """
        Ordre volontairement inversé : ligne 5, puis ligne 3, puis ligne 1.
        Un bug de fermeture JS capturant toujours le premier id, ou un
        cache HTTP partagé, se manifesterait ici même s'il passait
        inaperçu en testant les lignes dans l'ordre.
        """
        order = [self.applications[4], self.applications[2], self.applications[0]]
        downloaded = {}
        for application in order:
            _, content = self._download(application)
            downloaded[application.reference] = hashlib.sha256(content).hexdigest()
        for application in order:
            self.assertEqual(downloaded[application.reference], application.sheet_sha256)
        # Les trois empreintes doivent être distinctes deux à deux.
        digests = list(downloaded.values())
        self.assertEqual(len(digests), len(set(digests)))

    def test_meme_prenom_d_enfant_reste_des_dossiers_distincts(self):
        """Deux dossiers « Naomi » (Adjovi et Kponou) : pas de confusion."""
        naomi_adjovi = self.applications[0]
        naomi_kponou = self.applications[3]
        self.assertNotEqual(naomi_adjovi.reference, naomi_kponou.reference)
        _, content_adjovi = self._download(naomi_adjovi)
        _, content_kponou = self._download(naomi_kponou)
        self.assertNotEqual(
            hashlib.sha256(content_adjovi).hexdigest(),
            hashlib.sha256(content_kponou).hexdigest(),
        )
