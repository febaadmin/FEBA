"""
Phase 7 — messagerie interne : dossiers personnels, plusieurs destinataires,
répondre / répondre à tous, pièces jointes multiples, brouillons, recherche,
non-lus. Les permissions sont vérifiées côté API (identifiants devinés compris).
"""
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.messaging.models import BrouillonMessage, Conversation, EtatConversation, Message
from tests.test_audit_messagerie_devoirs_presences import Base

URL = "/api/messages/conversations/"
PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF"


class MessagerieBase(Base):
    def setUp(self):
        self.adm = self.client_de("adm@test.bj")
        self.prof = self.client_de("prof@test.bj")
        self.par = self.client_de("parent@test.bj")

    def ecrire(self, client, ids, objet="Sortie", corps="Bonjour", **extra):
        r = client.post(URL, {"recipient_ids": ids, "subject": objet, "body": corps, **extra}, format="multipart")
        self.assertEqual(r.status_code, 201, getattr(r, "data", r))
        return r.data

    def liste(self, client, **params):
        r = client.get(URL, params)
        self.assertEqual(r.status_code, 200, getattr(r, "data", r))
        return r.data


class DestinatairesEtReponsesTests(MessagerieBase):
    def test_plusieurs_destinataires_une_conversation_de_groupe(self):
        conv = self.ecrire(self.adm, [self.teacher.user_id, self.parent.id], objet="Conseil de classe")
        self.assertEqual({p["id"] for p in conv["participants"]}, {self.admin.id, self.teacher.user_id, self.parent.id})
        self.assertIsNone(Message.objects.get().recipient)                   # message de groupe
        self.assertEqual(self.liste(self.prof)[0]["unread_count"], 1)
        self.assertEqual(self.liste(self.par)[0]["unread_count"], 1)

    def test_un_destinataire_non_autorise_bloque_tout_l_envoi(self):
        r = self.par.post(URL, {"recipient_ids": [self.teacher.user_id, self.autre_eleve.id], "body": "x"}, format="multipart")
        self.assertEqual(r.status_code, 404)
        r = self.adm.post(URL, {"recipient_ids": [self.admin_autre.id], "body": "x"}, format="multipart")
        self.assertEqual(r.status_code, 404)                                  # autre académie
        self.assertFalse(Conversation.objects.exists())

    def test_repondre_a_tous_et_repondre_a_l_expediteur(self):
        conv = self.ecrire(self.adm, [self.teacher.user_id, self.parent.id], objet="Conseil")
        r = self.par.post(f"{URL}{conv['id']}/reply/", {"body": "Merci à tous", "a_tous": "true"}, format="multipart")
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.data["conversation"], conv["id"])
        self.assertEqual(self.liste(self.prof)[0]["unread_count"], 2)
        # « Répondre » seulement à l'expéditeur : tête-à-tête séparé, le groupe ne le voit pas.
        r = self.prof.post(f"{URL}{conv['id']}/reply/", {"body": "Question privée", "a_tous": "false"}, format="multipart")
        self.assertNotEqual(r.data["conversation"], conv["id"])
        prive = Conversation.objects.get(pk=r.data["conversation"])
        self.assertEqual(set(prive.participants.values_list("pk", flat=True)), {self.teacher.user_id, self.parent.id})
        self.assertNotIn(prive.pk, [c["id"] for c in self.liste(self.adm, dossier="reception")])

    def test_conversation_inaccessible_aux_non_participants(self):
        conv = self.ecrire(self.prof, [self.parent.id])
        intrus = self.client_de("eleve@test.bj")
        for methode, chemin, corps in (("get", f"{URL}{conv['id']}/", None), ("post", f"{URL}{conv['id']}/reply/", {"body": "x"}),
                                       ("post", f"{URL}{conv['id']}/deplacer/", {"dossier": "archives"}),
                                       ("post", f"{URL}{conv['id']}/important/", {"important": True}),
                                       ("put", f"{URL}{conv['id']}/mark_read/", None)):
            r = getattr(intrus, methode)(chemin, corps, format="json") if corps else getattr(intrus, methode)(chemin)
            self.assertEqual(r.status_code, 404, (methode, chemin))
        self.assertEqual(self.liste(self.adm), [])                            # l'administrateur ne lit pas les échanges des autres


class DossiersTests(MessagerieBase):
    def test_archiver_important_corbeille_restaurer_supprimer_definitivement(self):
        conv = self.ecrire(self.prof, [self.parent.id])
        cid = conv["id"]
        ids = lambda **p: [c["id"] for c in self.liste(self.par, **p)]
        self.assertEqual(ids(), [cid])
        self.assertEqual(ids(dossier="envoyes"), [])
        self.assertEqual([c["id"] for c in self.liste(self.prof, dossier="envoyes")], [cid])
        self.par.post(f"{URL}{cid}/important/", {"important": True}, format="json")
        self.assertEqual(ids(dossier="importants"), [cid])
        self.par.post(f"{URL}{cid}/deplacer/", {"dossier": "archives"}, format="json")
        self.assertEqual((ids(), ids(dossier="archives")), ([], [cid]))
        # L'archivage est personnel : l'enseignant garde la conversation.
        self.assertEqual([c["id"] for c in self.liste(self.prof, dossier="envoyes")], [cid])
        self.assertEqual(self.par.post(f"{URL}{cid}/supprimer_definitivement/").status_code, 400)
        self.par.post(f"{URL}{cid}/deplacer/", {"dossier": "corbeille"}, format="json")
        self.assertEqual((ids(dossier="archives"), ids(dossier="corbeille"), ids(dossier="importants")), ([], [cid], []))
        self.par.post(f"{URL}{cid}/deplacer/", {"dossier": "reception"}, format="json")           # restaurer
        self.assertEqual(ids(), [cid])
        self.par.post(f"{URL}{cid}/deplacer/", {"dossier": "corbeille"}, format="json")
        self.assertEqual(self.par.post(f"{URL}{cid}/supprimer_definitivement/").status_code, 200)
        self.assertEqual(ids(dossier="corbeille"), [])
        self.assertTrue(Conversation.objects.filter(pk=cid).exists())                          # rien n'est effacé
        self.assertEqual(self.prof.get(f"{URL}{cid}/").status_code, 200)
        # Une nouvelle réponse ramène la conversation chez le parent.
        self.prof.post(f"{URL}{cid}/reply/", {"body": "Relance"}, format="multipart")
        self.assertEqual(ids(), [cid])
        self.assertEqual(self.par.post(f"{URL}{cid}/deplacer/", {"dossier": "poubelle"}, format="json").status_code, 400)

    def test_lu_non_lu_et_compteurs(self):
        conv = self.ecrire(self.prof, [self.parent.id])
        cid = conv["id"]
        self.assertEqual(self.par.get(f"{URL}compteurs/").data["reception_non_lus"], 1)
        self.par.put(f"{URL}{cid}/mark_read/")
        self.assertEqual(self.liste(self.par)[0]["unread_count"], 0)
        self.assertEqual(self.liste(self.par, non_lus=1), [])
        self.par.post(f"{URL}{cid}/marquer/", {"lu": False}, format="json")
        self.assertEqual(self.liste(self.par)[0]["unread_count"], 1)
        self.assertEqual(self.par.get(f"{URL}unread_count/").data["count"], 1)
        # Groupe : lecture mesurée par participant.
        g = self.ecrire(self.adm, [self.teacher.user_id, self.parent.id], objet="Groupe")
        self.par.put(f"{URL}{g['id']}/mark_read/")
        prof_groupe = next(c for c in self.liste(self.prof) if c["id"] == g["id"])
        self.assertEqual(prof_groupe["unread_count"], 1)                     # le parent a lu, pas l'enseignant

    def test_recherche_et_filtres(self):
        self.ecrire(self.prof, [self.parent.id], objet="Sortie au musée", corps="Prévoir un pique-nique")
        self.ecrire(self.adm, [self.parent.id], objet="Frais", corps="Rappel")
        objets = lambda **p: sorted(c["subject"] for c in self.liste(self.par, **p))
        self.assertEqual(objets(q="musée"), ["Sortie au musée"])
        self.assertEqual(objets(q="pique"), ["Sortie au musée"])
        self.assertEqual(objets(correspondant=self.admin.id), ["Frais"])
        self.assertEqual(objets(du="2000-01-01"), ["Frais", "Sortie au musée"])
        self.assertEqual(self.par.get(URL, {"du": "hier"}).status_code, 400)
        self.assertEqual(self.par.get(URL, {"dossier": "spam"}).status_code, 400)
        correspondants = {u["id"] for u in self.par.get(f"{URL}correspondants/").data}
        self.assertEqual(correspondants, {self.admin.id, self.teacher.user_id})

    def test_liste_sans_requete_par_conversation(self):
        for i in range(6):
            self.ecrire(self.adm, [self.parent.id], objet=f"Sujet {i}")
        with CaptureQueriesContext(connection) as ctx:
            self.liste(self.par)
        avec6 = len(ctx.captured_queries)
        for i in range(6, 12):
            self.ecrire(self.adm, [self.parent.id], objet=f"Sujet {i}")
        with CaptureQueriesContext(connection) as ctx:
            self.assertEqual(len(self.liste(self.par)), 12)
        self.assertEqual(len(ctx.captured_queries), avec6)


class PiecesEtBrouillonsTests(MessagerieBase):
    def test_plusieurs_pieces_jointes_liens_signes_pour_les_participants(self):
        conv = self.ecrire(self.prof, [self.parent.id], attachments=[
            SimpleUploadedFile("a.pdf", PDF, content_type="application/pdf"),
            SimpleUploadedFile("b.pdf", PDF, content_type="application/pdf")])
        detail = self.par.get(f"{URL}{conv['id']}/").data
        pieces = detail["messages"][0]["pieces"]
        self.assertEqual([p["nom"] for p in pieces], ["a.pdf", "b.pdf"])
        self.assertTrue(all(p["url"].startswith("/api/files/") for p in pieces))
        self.assertEqual(self.client_de("eleve@test.bj").get(f"{URL}{conv['id']}/").status_code, 404)
        trop = [SimpleUploadedFile(f"{i}.pdf", PDF, content_type="application/pdf") for i in range(6)]
        r = self.prof.post(URL, {"recipient_ids": [self.parent.id], "body": "x", "attachments": trop}, format="multipart")
        self.assertEqual(r.status_code, 400)

    def test_brouillons_prives_et_envoi(self):
        r = self.prof.post("/api/messages/brouillons/", {"destinataires": [self.parent.id], "objet": "Devoir",
                                                         "corps": "Bonjour"}, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        bid = r.data["id"]
        self.assertEqual(r.data["destinataires_detail"][0]["id"], self.parent.id)
        self.assertEqual(self.prof.patch(f"/api/messages/brouillons/{bid}/", {"corps": "Bonjour à vous"}, format="json").data["corps"],
                         "Bonjour à vous")
        self.assertEqual(self.par.get(f"/api/messages/brouillons/{bid}/").status_code, 404)
        self.assertEqual(self.par.get("/api/messages/brouillons/").data, [])
        self.assertEqual(self.prof.get(f"{URL}compteurs/").data["brouillons"], 1)
        self.ecrire(self.prof, [self.parent.id], objet="Devoir", corps="Bonjour à vous", brouillon_id=bid)
        self.assertFalse(BrouillonMessage.objects.filter(pk=bid).exists())
        r = self.prof.post("/api/messages/brouillons/", {"destinataires": "x"}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_etat_personnel_cree_a_la_demande(self):
        conv = self.ecrire(self.prof, [self.parent.id])
        self.assertFalse(EtatConversation.objects.filter(utilisateur=self.parent).exists())
        self.par.post(f"{URL}{conv['id']}/important/", {"important": True}, format="json")
        self.assertTrue(EtatConversation.objects.get(utilisateur=self.parent).important)
