"""
P11 — Aucun document confidentiel n'est stocké dans un répertoire public.

LE DÉFAUT
---------
La photo de l'enfant partait dans `MEDIA_ROOT`, que nginx publie sous
`/media/` (voir nginx/nginx.prod.conf). La photo d'un mineur était donc
atteignable par une simple URL, sans authentification, pour qui la
devinait ou se la faisait transmettre par mégarde.

Ce test vérifie l'emplacement RÉEL du fichier sur le disque. Un contrôle
qui se contenterait de vérifier qu'aucune vue ne renvoie l'URL passerait
alors même que le fichier reste servi.
"""
import io
import os

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework.test import APIClient

from apps.schools.models import School
from apps.website.models import FHAEnrollmentApplication

User = get_user_model()


def _png_bytes():
    from PIL import Image

    buffer = io.BytesIO()
    Image.new("RGB", (24, 24), (10, 40, 90)).save(buffer, format="PNG")
    return buffer.getvalue()


class PrivateStorageTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.fha, _ = School.objects.update_or_create(
            code=School.CODE_FEBA_FHA,
            defaults=dict(name="FEBA French Heritage Academy",
                          address="Programme en ligne", entity_type="online",
                          currency_code="USD", matricule_prefix="FHA"),
        )
        cls.feba, _ = School.objects.update_or_create(
            code=School.CODE_FEBA,
            defaults=dict(name="Faith & Excellence Bilingual Academy",
                          address="Akpakpa, Cotonou", currency_code="XOF"),
        )
        cls.fha_admin = User.objects.create_user(
            username="a.fha", email="a.fha@test", password="x",
            role="admin", school=cls.fha,
        )
        cls.feba_admin = User.objects.create_user(
            username="a.feba", email="a.feba@test", password="x",
            role="admin", school=cls.feba,
        )

    @staticmethod
    def _multipart(data):
        """
        Encode les champs de type liste pour un envoi multipart.

        Le multipart n'a pas de type « liste » : les champs JSON du modèle
        (niveaux de français, objectifs, créneaux) voyagent donc en chaînes
        JSON. C'est ce que fait tout client qui joint un fichier.
        """
        import json

        return {
            key: (json.dumps(value) if isinstance(value, (list, dict)) else value)
            for key, value in data.items()
        }

    def _submit_with_photo(self):
        from tests.test_fha_enrollment_workflow import payload

        data = self._multipart(payload())
        data["child_photo"] = SimpleUploadedFile(
            "photo.png", _png_bytes(), content_type="image/png",
        )
        # multipart : c'est ainsi que le navigateur envoie un fichier.
        response = APIClient().post("/api/website/fha/enroll/", data,
                                    format="multipart")
        self.assertEqual(response.status_code, 201, response.data)
        return FHAEnrollmentApplication.objects.get(
            reference=response.data["reference"])

    def test_la_photo_de_l_enfant_n_est_pas_dans_le_repertoire_public(self):
        application = self._submit_with_photo()
        self.assertTrue(application.child_photo)

        path = os.path.abspath(application.child_photo.path)
        media = os.path.abspath(str(settings.MEDIA_ROOT))
        self.assertFalse(
            path.startswith(media + os.sep),
            f"La photo d'un mineur est dans le répertoire servi publiquement "
            f"({path}). Une URL suffirait à la récupérer.",
        )

        private = os.path.abspath(str(getattr(
            settings, "PRIVATE_MEDIA_ROOT",
            os.path.join(settings.BASE_DIR, "private_media"),
        )))
        self.assertTrue(path.startswith(private + os.sep))

    def test_la_photo_est_servie_par_une_vue_authentifiee(self):
        application = self._submit_with_photo()
        client = APIClient()
        client.force_authenticate(user=self.fha_admin)
        response = client.get(
            f"/api/website/admin/fha-applications/{application.pk}/photo/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("no-store", response["Cache-Control"])

    def test_un_admin_de_l_autre_academie_n_obtient_pas_la_photo(self):
        application = self._submit_with_photo()
        client = APIClient()
        client.force_authenticate(user=self.feba_admin)
        response = client.get(
            f"/api/website/admin/fha-applications/{application.pk}/photo/")
        self.assertEqual(response.status_code, 404)

    def test_un_visiteur_anonyme_n_obtient_pas_la_photo(self):
        application = self._submit_with_photo()
        response = APIClient().get(
            f"/api/website/admin/fha-applications/{application.pk}/photo/")
        self.assertIn(response.status_code, (401, 403))

    def test_la_fiche_pdf_est_dans_le_stockage_prive(self):
        application = self._submit_with_photo()
        path = os.path.abspath(application.sheet_absolute_path)
        media = os.path.abspath(str(settings.MEDIA_ROOT))
        self.assertFalse(path.startswith(media + os.sep))

    def test_un_fichier_qui_n_est_pas_une_image_est_refuse(self):
        """Un .png qui contient un script n'est pas une image."""
        from tests.test_fha_enrollment_workflow import payload

        data = self._multipart(payload())
        data["child_photo"] = SimpleUploadedFile(
            "piege.png", b"<?php system($_GET['c']); ?>",
            content_type="image/png",
        )
        response = APIClient().post("/api/website/fha/enroll/", data,
                                    format="multipart")
        self.assertEqual(response.status_code, 400)
        self.assertIn("child_photo", response.data)
