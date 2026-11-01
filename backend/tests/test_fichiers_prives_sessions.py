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
from django.test import TestCase, TransactionTestCase, override_settings
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


class TempsReelTests(TestCase):
    def test_le_temps_reel_refuse_un_jeton_d_avant_le_changement_de_mot_de_passe(self):
        from django.contrib.auth.models import AnonymousUser
        from rest_framework_simplejwt.tokens import AccessToken

        from apps.accounts.middleware import utilisateur_du_jeton as get_user

        user = make_user("ws@test.bj", "teacher", make_school())
        jeton = str(AccessToken.for_user(user))
        self.assertEqual(get_user(jeton).pk, user.pk)
        user.set_password(NOUVEAU)
        user.save()
        self.assertIsInstance(get_user(jeton), AnonymousUser)
        nouveau = str(AccessToken.for_user(user))
        user.is_active = False
        user.save()
        self.assertIsInstance(get_user(nouveau), AnonymousUser)


class LiensParRoleTests(TestCase):
    """Chaque rôle reçoit un lien pour ce qu'il a le droit de voir, et rien d'autre."""

    def setUp(self):
        from apps.bulletins.models import Bulletin
        from apps.classes.models import Class
        from apps.parents.models import Parent, ParentStudent
        from apps.schools.models import Level, SchoolYear
        from apps.teachers.models import Teacher

        self.school = make_school()
        year = SchoolYear.objects.create(school=self.school, name="2026-2027", start_date="2026-09-01",
                                         end_date="2027-06-30", is_current=True)
        level = Level.objects.create(school=self.school, name="CM1", order=1, cycle="primaire")
        cls = Class.objects.create(name="A", level=level, school_year=year)
        autre = Class.objects.create(name="B", level=level, school_year=year)

        def eleve(mail, classe):
            return Student.objects.create(user=make_user(mail, "student", self.school), school=self.school,
                                          first_name="E", last_name=mail[:3], current_class=classe, school_year=year)

        self.eleve, self.autre = eleve("el1@test.bj", cls), eleve("el2@test.bj", autre)
        self.parent = make_user("pa1@test.bj", "parent", self.school)
        ParentStudent.objects.create(parent=Parent.objects.create(user=self.parent), student=self.eleve,
                                     relationship="mother")
        self.prof = make_user("pr1@test.bj", "teacher", self.school)
        Teacher.objects.create(user=self.prof).classes.add(cls)
        self.prof_autre = make_user("pr2@test.bj", "teacher", self.school)
        Teacher.objects.create(user=self.prof_autre)
        self.admin = make_user("ad1@test.bj", "admin", self.school)
        self.admin_ailleurs = make_user("ad2@test.bj", "admin", make_school())

        self.bulletin = Bulletin.objects.create(student=self.eleve, school_year=year, period="T1",
                                                pdf_file="bulletins/b.pdf")
        self.paiement = Payment.objects.create(student=self.eleve, school_year=year, amount=1000,
                                               payment_type="mensualite", payment_method="cash",
                                               payment_date=date(2026, 10, 1), receipt_file="receipts/r.pdf")

    def obtenir(self, user, chemin):
        c = APIClient()
        c.force_authenticate(user)
        return c.get(chemin)

    def test_bulletin(self):
        chemin = f"/api/bulletins/{self.bulletin.pk}/"
        for user in (self.eleve.user, self.parent, self.prof, self.admin):
            rep = self.obtenir(user, chemin)
            self.assertEqual(rep.status_code, 200, user.email)
            self.assertIn("/api/files/", rep.data["pdf_url"])
            self.assertIn("/api/files/", rep.data["pdf_file"])
        for user in (self.autre.user, self.prof_autre, self.admin_ailleurs):
            self.assertEqual(self.obtenir(user, chemin).status_code, 404, user.email)

    def test_recu(self):
        chemin = f"/api/payments/{self.paiement.pk}/"
        for user in (self.eleve.user, self.parent, self.admin):
            rep = self.obtenir(user, chemin)
            self.assertEqual(rep.status_code, 200, user.email)
            self.assertIn("/api/files/", rep.data["receipt_url"])
            self.assertIn("/api/files/", rep.data["receipt_file"])
        for user in (self.autre.user, self.prof, self.admin_ailleurs):
            self.assertIn(self.obtenir(user, chemin).status_code, (403, 404), user.email)

    def test_aucune_liste_ne_donne_une_adresse_media_directe(self):
        for user, chemin in ((self.parent, "/api/bulletins/"), (self.admin, "/api/payments/"),
                             (self.eleve.user, "/api/payments/")):
            texte = self.obtenir(user, chemin).content.decode()
            self.assertNotIn("/media/bulletins", texte)
            self.assertNotIn("/media/receipts", texte)


class ChiffresTests(TestCase):
    def setUp(self):
        self.school = make_school()
        self.admin = make_user("chiffres@test.bj", "admin", self.school)
        self.c = APIClient()
        self.c.force_authenticate(self.admin)

    def test_historique_de_l_eleve_sans_paiement_supprime_ni_annule(self):
        from apps.schools.models import SchoolYear
        from apps.students.models import StudentEnrollment
        annee = SchoolYear.objects.create(school=self.school, name="2026-2027", start_date="2026-09-01",
                                          end_date="2027-06-30", is_current=True)
        eleve = Student.objects.create(school=self.school, first_name="A", last_name="B", school_year=annee)
        StudentEnrollment.objects.create(student=eleve, school_year=annee)
        for montant, etat in ((1000, {}), (200, {"is_deleted": True}), (30, {"is_confirmed": False})):
            Payment.objects.create(student=eleve, school_year=annee, amount=montant, payment_type="mensualite",
                                   payment_method="cash", payment_date=date(2026, 10, 1), **etat)
        stats = self.c.get(f"/api/students/{eleve.pk}/history/").data[0]["stats"]
        self.assertEqual((stats["payments_count"], stats["payments_total"]), (1, 1000.0))

    def test_resume_vide_dans_la_devise_de_l_academie(self):
        self.school.currency_code = "USD"
        self.school.save()
        self.assertEqual(self.c.get("/api/payments/summary/").data["consolidated_total"]["currency"],
                         self.school.currency_code)


@override_settings(CHANNEL_LAYERS={"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}})
class ConnexionsOuvertesTests(TransactionTestCase):
    def setUp(self):
        self.school = make_school()
        self.moi = make_user("ws1@test.bj", "admin", self.school)
        self.autre = make_user("ws2@test.bj", "parent", self.school)

    async def relier(self, consommateur, chemin, user, **kwargs):
        # asgiref : channels.testing exige daphne, absent des dépendances.
        from asgiref.testing import ApplicationCommunicator
        comm = ApplicationCommunicator(consommateur.as_asgi(), {
            "type": "websocket", "path": chemin, "user": user, "url_route": {"kwargs": kwargs},
            "headers": [], "subprotocols": [],
        })
        await comm.send_input({"type": "websocket.connect"})
        reponse = await comm.receive_output(timeout=3)
        return comm, reponse["type"] == "websocket.accept"

    def test_un_salon_ne_s_ouvre_qu_a_ses_participants(self):
        from asgiref.sync import async_to_sync
        from apps.messaging.consumers import ChatConsumer

        async def scenario():
            _, ouvert = await self.relier(ChatConsumer, "/ws/chat/x/", self.autre,
                                          room_id=f"{self.moi.pk}-999999")
            return ouvert
        self.assertFalse(async_to_sync(scenario)())

    def test_changement_de_mot_de_passe_ferme_la_connexion(self):
        from asgiref.sync import async_to_sync, sync_to_async
        from apps.accounts.views import revoquer_sessions
        from apps.notifications.consumers import NotificationConsumer

        async def scenario():
            comm, ouvert = await self.relier(NotificationConsumer, "/ws/notifications/", self.moi)
            self.assertTrue(ouvert)
            await sync_to_async(revoquer_sessions, thread_sensitive=False)(self.moi)
            sortie = await comm.receive_output(timeout=3)
            await comm.send_input({"type": "websocket.disconnect", "code": 1000})
            await comm.wait()
            return sortie
        sortie = async_to_sync(scenario)()
        self.assertEqual((sortie["type"], sortie["code"]), ("websocket.close", 4401))

    def test_message_refuse_apres_changement_et_hors_regle(self):
        from asgiref.sync import async_to_sync, sync_to_async
        from apps.messaging.consumers import ChatConsumer
        from apps.messaging.models import Message

        def changer():
            self.moi_bis = type(self.moi).objects.get(pk=self.moi.pk)
            self.moi_bis.set_password(NOUVEAU)
            self.moi_bis.save()

        async def scenario():
            comm, _ = await self.relier(ChatConsumer, "/ws/chat/x/", self.moi, room_id=f"{self.moi.pk}-1")
            await sync_to_async(changer, thread_sensitive=False)()
            await comm.send_input({"type": "websocket.receive",
                                   "text": '{"message":"x","recipient_id":%d}' % self.autre.pk})
            sortie = await comm.receive_output(timeout=3)
            await comm.send_input({"type": "websocket.disconnect", "code": 1000})
            await comm.wait()
            return sortie
        sortie = async_to_sync(scenario)()
        self.assertEqual(sortie["code"], 4401)
        self.assertEqual(Message.objects.count(), 0)
