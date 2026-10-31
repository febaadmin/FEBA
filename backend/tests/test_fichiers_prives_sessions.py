"""
Fichiers privés par lien signé, fermeture des sessions au changement de mot de
passe, historique des modifications de paiement.
"""
import shutil
import tempfile
from datetime import date

from django.core import signing
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.core.fichiers_prives import DOSSIERS_PRIVES, SEL, est_prive
from apps.payments.models import Payment
from apps.students.models import Student
from tests.test_virtualclass import make_school, make_user

MDP = "Ancien-Mot-2026!"
NOUVEAU = "Nouveau-Mot-2026!"


class FichiersPrivesTests(TestCase):
    def setUp(self):
        self.racine = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.racine, True)
        reglage = override_settings(MEDIA_ROOT=self.racine)
        reglage.enable()
        self.addCleanup(reglage.disable)
        default_storage.__dict__.pop("base_location", None)
        default_storage.__dict__.pop("location", None)
        self.addCleanup(default_storage.__dict__.pop, "location", None)
        self.addCleanup(default_storage.__dict__.pop, "base_location", None)

    def test_chaque_dossier_prive_a_un_lien_signe_et_le_public_reste_public(self):
        for dossier in DOSSIERS_PRIVES:
            self.assertTrue(default_storage.url(f"{dossier}/x.pdf").startswith("/api/files/"), dossier)
        self.assertEqual(default_storage.url("avatars/a.png"), "/media/avatars/a.png")

    def test_nginx_refuse_exactement_les_memes_dossiers(self):
        import re
        from pathlib import Path
        conf = (Path(__file__).resolve().parents[2] / "nginx/nginx.prod.conf")
        if not conf.exists():
            self.skipTest("configuration nginx absente de cette image")
        self.assertEqual(set(re.search(r"\^/media/\(([^)]+)\)/", conf.read_text()).group(1).split("|")),
                         set(DOSSIERS_PRIVES))

    def test_lien_valide_expire_altere(self):
        nom = default_storage.save("bulletins/b.pdf", ContentFile(b"%PDF-1.4"))
        url = default_storage.url(nom)
        rep = self.client.get(url)
        self.assertEqual(rep.status_code, 200)
        self.assertEqual(rep["Cache-Control"], "private, no-store")
        self.assertEqual(b"".join(rep.streaming_content), b"%PDF-1.4")
        self.assertEqual(self.client.get(url[:-3] + "xx/").status_code, 404)
        with override_settings(PRIVATE_FILE_LINK_SECONDS=-1):
            self.assertEqual(self.client.get(url).status_code, 403)

    def test_un_jeton_signe_ne_sort_pas_des_dossiers_prives(self):
        for nom in ("avatars/a.png", "../secret", "bulletins/../../secret"):
            jeton = signing.dumps(nom, salt=SEL)
            self.assertEqual(self.client.get(f"/api/files/{jeton}/").status_code, 404, nom)

    def test_un_html_depose_est_telecharge_jamais_affiche(self):
        nom = default_storage.save("homework/x.html", ContentFile(b"<script>1</script>"))
        rep = self.client.get(default_storage.url(nom))
        self.assertIn("attachment", rep["Content-Disposition"])
        self.assertEqual(rep["X-Content-Type-Options"], "nosniff")

    def test_est_prive(self):
        self.assertTrue(est_prive("receipts/a.pdf"))
        self.assertFalse(est_prive("receiptsx/a.pdf"))


class SessionsTests(TestCase):
    def setUp(self):
        self.user = make_user("session@test.bj", "teacher", make_school())
        self.user.set_password(MDP)
        self.user.save()

    def connexion(self):
        c = APIClient()
        rep = c.post("/api/auth/login/", {"email": "session@test.bj", "password": MDP}, format="json")
        self.assertEqual(rep.status_code, 200, rep.data)
        return rep.data["access"], rep.data["refresh"]

    def profil(self, jeton):
        c = APIClient()
        c.credentials(HTTP_AUTHORIZATION=f"Bearer {jeton}")
        return c.get("/api/auth/me/").status_code

    def test_changer_son_mot_de_passe_ferme_toutes_les_sessions_sauf_ce_poste(self):
        autre_access, autre_refresh = self.connexion()
        access, _ = self.connexion()
        c = APIClient()
        c.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
        rep = c.post("/api/auth/change-password/", {"old_password": MDP, "new_password": NOUVEAU}, format="json")
        self.assertEqual(rep.status_code, 200, rep.data)

        self.assertEqual(self.profil(autre_access), 401)
        self.assertEqual(self.profil(access), 401)
        self.assertEqual(APIClient().post("/api/auth/refresh/", {"refresh": autre_refresh}, format="json").status_code, 401)
        self.assertEqual(self.profil(rep.data["access"]), 200)
        self.assertEqual(APIClient().post("/api/auth/refresh/", {"refresh": rep.data["refresh"]}, format="json").status_code, 200)
        self.assertEqual(APIClient().post("/api/auth/login/", {"email": "session@test.bj", "password": MDP}, format="json").status_code, 400)

    def test_jeton_emis_avant_le_correctif_refuse(self):
        from rest_framework_simplejwt.tokens import RefreshToken
        refresh = RefreshToken.for_user(self.user)
        del refresh["hash_password"]
        self.assertEqual(APIClient().post("/api/auth/refresh/", {"refresh": str(refresh)}, format="json").status_code, 401)

    def test_changement_du_mot_de_passe_hors_api_ferme_aussi_les_sessions(self):
        access, refresh = self.connexion()
        self.user.set_password(NOUVEAU)
        self.user.save()
        self.assertEqual(self.profil(access), 401)
        self.assertEqual(APIClient().post("/api/auth/refresh/", {"refresh": refresh}, format="json").status_code, 401)


class HistoriquePaiementTests(TestCase):
    def setUp(self):
        school = make_school()
        admin = make_user("compta@test.bj", "admin", school)
        self.client_api = APIClient()
        self.client_api.force_authenticate(admin)
        eleve = Student.objects.create(school=school, first_name="A", last_name="B")
        self.paiement = Payment.objects.create(student=eleve, amount=1000, payment_type="mensualite",
                                               payment_method="cash", payment_date=date(2026, 10, 1))

    def patch(self, **donnees):
        return self.client_api.patch(f"/api/payments/{self.paiement.pk}/", donnees, format="json")

    def test_modifier_un_montant_laisse_une_trace(self):
        self.assertEqual(self.patch(amount="2000").status_code, 200)
        trace = self.paiement.history.get(action="update")
        self.assertIn("amount", trace.notes)
        self.assertIn("1000", trace.notes)

    def test_les_etats_ne_passent_pas_par_une_modification_directe(self):
        self.assertEqual(self.patch(is_deleted=True, is_confirmed=False).status_code, 200)
        self.paiement.refresh_from_db()
        self.assertFalse(self.paiement.is_deleted)
        self.assertTrue(self.paiement.is_confirmed)
