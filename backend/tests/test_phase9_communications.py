"""
Phase 9 — communications.

A. « Répondre par email » sur un message du site vitrine : la réponse part DEPUIS FEBA
   (service d'envoi existant, adresse officielle), est enregistrée dans la boîte
   contact (« Envoyés ») et reliée au message d'origine ; « envoyé » n'est annoncé
   (201) que si le serveur d'envoi l'a accepté.
C. Compteur « Messages » du menu : une seule règle (conversations non lues hors
   archives / corbeille), identique pour les cinq profils.
   Signalement des erreurs d'interface (version périmée après un déploiement).

Envois : backend locmem (aucun e-mail réel), destinataires fictifs @exemple.org.
"""
from unittest import mock

from django.core import mail
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.accounts.models import CustomUser
from apps.boite_mail.models import MessageMail
from apps.incidents.models import TechnicalIncident
from apps.schools.models import School
from apps.website.models import ContactMessage
from tests.test_messagerie_phase7 import URL as URL_CONV, MessagerieBase

CONF = dict(MAILBOX_IMAP_HOST="", MAILBOX_ADDRESS="contact@globalfeba.com", DEFAULT_FROM_EMAIL="contact@globalfeba.com",
            EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")


@override_settings(**CONF)
class ReponseMessageSiteTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.feba = School.objects.create(name="FEBA", address="Cotonou", code="P9-FEBA")
        cls.autre = School.objects.create(name="Autre", address="Porto-Novo", code="P9-AUT")
        mk = lambda n, role, school=None: CustomUser.objects.create_user(
            username=n, email=f"{n}@t.bj", password="x", role=role, school=school, first_name=n.title(), last_name="T")
        cls.sa = mk("sa9", "superadmin")
        cls.admin = mk("adm9", "admin", cls.feba)
        cls.admin_autre = mk("adm9b", "admin", cls.autre)
        cls.prof = mk("prof9", "teacher", cls.feba)
        cls.msg = ContactMessage.objects.create(entity=cls.feba, name="Awa Dossou", email="awa@exemple.org",
                                                subject="Inscription CE1", message="Bonjour, des informations ?")

    def cli(self, u):
        c = APIClient()
        c.force_authenticate(u)
        return c

    def url(self, m=None):
        return f"/api/website/admin/contact-messages/{(m or self.msg).pk}/reponses/"

    def repondre(self, u, **extra):
        donnees = {"a": ["awa@exemple.org"], "sujet": "Re: Inscription CE1", "texte": "Bonjour Awa, voici les informations.", **extra}
        return self.cli(u).post(self.url(), donnees, format="multipart")

    def test_reponse_envoyee_depuis_feba_enregistree_et_reliee(self):
        r = self.repondre(self.admin)
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data["statut"], "sent")
        self.assertEqual(len(mail.outbox), 1)
        e = mail.outbox[0]
        self.assertEqual(e.to, ["awa@exemple.org"])
        self.assertIn("contact@globalfeba.com", e.from_email)
        self.assertEqual(e.subject, "Re: Inscription CE1")
        m = MessageMail.objects.get(pk=r.data["id"])
        self.assertEqual((m.dossier, m.origine, m.message_site_id, m.envoye_par_id), ("envoyes", "site_vitrine", self.msg.pk, self.admin.pk))
        self.msg.refresh_from_db()
        self.assertTrue(self.msg.is_read)
        # Historique visible depuis le message d'origine, et compteur dans la liste.
        h = self.cli(self.admin).get(self.url())
        self.assertEqual([x["id"] for x in h.data], [m.pk])
        self.assertEqual(h.data[0]["par"], "Adm9 T")
        lst = self.cli(self.admin).get("/api/website/admin/contact-messages/")
        lignes = lst.data["results"] if isinstance(lst.data, dict) else lst.data
        self.assertEqual(next(x for x in lignes if x["id"] == self.msg.pk)["nb_reponses"], 1)

    def test_piece_jointe_cc_et_cci(self):
        pdf = SimpleUploadedFile("tarifs.pdf", b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF", content_type="application/pdf")
        r = self.repondre(self.admin, cc=["pere@exemple.org"], cci=["archive@exemple.org"], attachments=[pdf])
        self.assertEqual(r.status_code, 201, r.data)
        e = mail.outbox[0]
        self.assertEqual(sorted(e.recipients()), ["archive@exemple.org", "awa@exemple.org", "pere@exemple.org"])
        self.assertNotIn("archive@exemple.org", str(e.message()["Cc"] or ""))
        self.assertEqual(len(e.attachments), 1)
        self.assertEqual(r.data["nb_pieces"], 1)

    def test_validations(self):
        self.assertEqual(self.repondre(self.admin, texte="").status_code, 400)
        self.assertEqual(self.repondre(self.admin, a=[]).status_code, 400)
        self.assertEqual(self.repondre(self.admin, sujet="").status_code, 400)
        self.assertEqual(len(mail.outbox), 0)
        self.assertFalse(MessageMail.objects.exists())

    def test_echec_du_fournisseur_n_est_pas_annonce_comme_envoye(self):
        from apps.notifications.mailer import deliver as vrai

        def en_panne(envoi, *a, **k):
            with mock.patch("django.core.mail.backends.locmem.EmailBackend.send_messages", side_effect=OSError("Connexion refusée")):
                return vrai(envoi, *a, **k)
        with mock.patch("apps.notifications.mailer.deliver", side_effect=en_panne):
            r = self.repondre(self.admin)
        self.assertEqual(r.status_code, 202, r.data)
        self.assertNotIn(r.data["statut"], ("sent", "accepted"))
        self.assertTrue(r.data["erreur"])
        self.assertEqual(MessageMail.objects.get().message_site_id, self.msg.pk)

    def test_cloisonnement_et_roles(self):
        self.assertEqual(self.repondre(self.admin_autre).status_code, 404)
        self.assertEqual(self.cli(self.admin_autre).get(self.url()).status_code, 404)
        self.assertEqual(self.repondre(self.prof).status_code, 403)
        self.assertEqual(APIClient().post(self.url(), {}).status_code, 401)
        self.assertEqual(len(mail.outbox), 0)
        self.assertEqual(self.repondre(self.sa).status_code, 201)

    def test_creation_de_message_par_l_administration_toujours_refusee(self):
        r = self.cli(self.admin).post("/api/website/admin/contact-messages/", {"name": "x", "email": "x@exemple.org"}, format="json")
        self.assertEqual(r.status_code, 405)
        self.assertEqual(ContactMessage.objects.count(), 1)


class CompteurMenuTests(MessagerieBase):
    """Le badge « Messages » : même règle pour les cinq profils, recalculé après lecture."""

    def compte(self, client):
        r = client.get(f"{URL_CONV}unread_count/")
        self.assertEqual(r.status_code, 200)
        return r.data["count"]

    def test_cinq_profils_meme_regle(self):
        sa = CustomUser.objects.create_user(username="sa9c", email="sa9c@test.bj", password="Pass1234!", role="superadmin",
                                            first_name="S", last_name="A")
        c_sa = APIClient()
        c_sa.force_authenticate(sa)
        eleve = self.client_de("eleve@test.bj")
        for c in (c_sa, self.adm, self.prof, self.par, eleve):
            self.assertEqual(self.compte(c), 0)
        conv = self.ecrire(self.adm, [self.parent.id, self.teacher.user_id, self.eleve.id, sa.id], objet="Info")
        # Deux messages dans la même conversation = UNE conversation non lue (comme la colonne « Réception »).
        self.adm.post(f"{URL_CONV}{conv["id"]}/reply/", {"body": "Précision"}, format="multipart")
        for c in (c_sa, self.prof, self.par, eleve):
            self.assertEqual(self.compte(c), 1)
            self.assertEqual(c.get(f"{URL_CONV}unread_count/").data["messages"], 2)
            self.assertEqual(c.get(f"{URL_CONV}compteurs/").data["reception_non_lus"], 1)
        self.assertEqual(self.compte(self.adm), 0)                    # ses propres messages ne comptent pas
        self.par.put(f"{URL_CONV}{conv['id']}/mark_read/")
        self.assertEqual(self.compte(self.par), 0)
        self.assertEqual(self.compte(self.prof), 1)                   # lecture mesurée par personne

    def test_archives_et_corbeille_exclues_sans_rien_supprimer(self):
        conv = self.ecrire(self.prof, [self.parent.id])
        self.assertEqual(self.compte(self.par), 1)
        self.par.post(f"{URL_CONV}{conv['id']}/deplacer/", {"dossier": "archives"}, format="json")
        self.assertEqual(self.compte(self.par), 0)
        self.par.post(f"{URL_CONV}{conv['id']}/deplacer/", {"dossier": "reception"}, format="json")
        self.assertEqual(self.compte(self.par), 1)                    # toujours non lu : rien n'a été marqué lu
        self.par.post(f"{URL_CONV}{conv['id']}/deplacer/", {"dossier": "corbeille"}, format="json")
        self.assertEqual(self.compte(self.par), 0)
        from apps.messaging.models import Message
        self.assertEqual(Message.objects.filter(conversation_id=conv["id"], is_read=False).count(), 1)


class SignalementInterfaceTests(TestCase):
    URL = "/api/incidents/frontend/"

    @classmethod
    def setUpTestData(cls):
        cls.u = CustomUser.objects.create_user(username="p9i", email="p9i@t.bj", password="x", role="parent")

    def setUp(self):
        cache.clear()
        self.c = APIClient()
        self.c.force_authenticate(self.u)

    def test_version_perimee_regroupee_en_un_incident(self):
        for nom in ("index-CnWUVqyn.js", "index-DO0mM_KK.js"):
            r = self.c.post(self.URL, {"type": "chunk", "route": "/superadmin/academies",
                                        "message": f"Failed to fetch dynamically imported module: /assets/{nom}"}, format="json")
            self.assertEqual(r.status_code, 201)
            self.assertTrue(r.data["enregistre"])
        self.assertEqual(TechnicalIncident.objects.filter(module="frontend").count(), 1)

    def test_anonyme_refuse_et_debit_limite(self):
        self.assertEqual(APIClient().post(self.URL, {"type": "rendu"}, format="json").status_code, 401)
        for _ in range(20):
            self.assertEqual(self.c.post(self.URL, {"type": "rendu", "message": "x"}, format="json").status_code, 201)
        self.assertEqual(self.c.post(self.URL, {"type": "rendu", "message": "x"}, format="json").status_code, 429)

    def test_liste_des_incidents_reste_reservee(self):
        self.assertEqual(self.c.get("/api/incidents/").status_code, 403)
