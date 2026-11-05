"""
Phase 8 — boîte professionnelle contact@globalfeba.com (Hostinger, IMAP).

Le fournisseur est SIMULÉ par un faux serveur IMAP en mémoire, qui suit le protocole
utilisé par FEBA (LIST avec attributs SPECIAL-USE, SELECT/UIDVALIDITY, UID SEARCH /
FETCH / STORE / COPY, EXPUNGE, APPEND, CREATE). La connexion au vrai compte a été
vérifiée en lecture seule sur le serveur de production (voir le rapport) ; elle n'est
pas rejouée par les tests.
"""
import re
from email.message import EmailMessage
from unittest import mock

from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.accounts.models import CustomUser
from apps.boite_mail.imap import synchroniser_tout
from apps.boite_mail.models import AccesBoiteMail, JournalBoiteMail, MessageMail
from apps.schools.models import School

CONF = dict(MAILBOX_IMAP_HOST="imap.test", MAILBOX_IMAP_USER="contact@globalfeba.com",
            MAILBOX_IMAP_PASSWORD="secret-de-test", MAILBOX_ADDRESS="contact@globalfeba.com")


def brut(sujet, de="Parent Dupont <parent@exemple.org>", a="contact@globalfeba.com", html=None, piece=None, mid=None):
    m = EmailMessage()
    m["Subject"], m["From"], m["To"] = sujet, de, a
    m["Message-ID"] = mid or f"<{sujet.replace(' ', '-')}@exemple.org>"
    m["Date"] = "Wed, 05 Nov 2026 10:00:00 +0100"
    m.set_content(f"Corps de {sujet}")
    if html:
        m.add_alternative(html, subtype="html")
    if piece:
        m.add_attachment(piece[1], maintype="application", subtype="pdf", filename=piece[0])
    return m.as_bytes()


class FauxImap:
    """Boîte en mémoire partagée entre connexions (état du « fournisseur »)."""
    dossiers = {}
    uidvalidity = {}
    prochain = {}
    refus_store = False
    instances = 0

    @classmethod
    def reinitialiser(cls):
        cls.dossiers = {"INBOX": {}, "INBOX.Sent": {}, "INBOX.Trash": {}, "INBOX.Junk": {}, "INBOX.Drafts": {}}
        cls.uidvalidity = {k: 100 for k in cls.dossiers}
        cls.prochain = {k: 1 for k in cls.dossiers}
        cls.refus_store = False

    @classmethod
    def deposer(cls, dossier, donnees, flags=()):
        uid = cls.prochain[dossier]
        cls.prochain[dossier] += 1
        cls.dossiers[dossier][uid] = {"brut": donnees, "flags": set(flags)}
        return uid

    def __init__(self, hote, port, timeout=None):
        FauxImap.instances += 1
        self.courant = None
        self._reponses = {}

    def login(self, u, p):
        if p != "secret-de-test":
            import imaplib
            raise imaplib.IMAP4.error("AUTHENTICATIONFAILED")

    def logout(self):
        pass

    def list(self):
        attr = {"INBOX": "\\HasChildren", "INBOX.Sent": "\\Sent", "INBOX.Trash": "\\Trash", "INBOX.Junk": "\\Junk",
                "INBOX.Drafts": "\\Drafts"}
        return "OK", [f'({attr.get(n, "")}) "." {n}'.encode() for n in self.dossiers]

    def create(self, nom):
        nom = nom.strip('"')
        self.dossiers[nom], self.uidvalidity[nom], self.prochain[nom] = {}, 100, 1
        return "OK", [b""]

    def select(self, nom, readonly=False):
        nom = nom.strip('"')
        if nom not in self.dossiers:
            return "NO", [b""]
        self.courant = nom
        self._reponses["UIDVALIDITY"] = [str(self.uidvalidity[nom]).encode()]
        return "OK", [str(len(self.dossiers[nom])).encode()]

    def response(self, cle):
        return cle, self._reponses.get(cle, [None])

    def expunge(self):
        d = self.dossiers[self.courant]
        for uid in [u for u, v in d.items() if "\\Deleted" in v["flags"]]:
            del d[uid]
        return "OK", [b""]

    def append(self, nom, flags, date, donnees):
        self.deposer(nom.strip('"'), donnees, flags=("\\Seen",))
        return "OK", [b""]

    @staticmethod
    def _uids(spec, existants):
        res = set()
        for morceau in spec.split(","):
            if ":" in morceau:
                a, b = morceau.split(":")
                a, b = int(a), (max(existants) if b == "*" and existants else int(b) if b != "*" else 0)
                res |= {u for u in existants if a <= u <= b}
            else:
                res.add(int(morceau))
        return sorted(u for u in res if u in existants)

    def uid(self, commande, *args):
        d = self.dossiers[self.courant]
        if commande == "SEARCH":
            return "OK", [" ".join(map(str, sorted(d))).encode()]
        if commande == "FETCH":
            spec, quoi = args
            sortie = []
            for u in self._uids(spec, list(d)):
                v = d[u]
                flags = " ".join(sorted(v["flags"]))
                if "BODY.PEEK" in quoi:
                    sortie.append((f"{u} (UID {u} BODY[] {{{len(v['brut'])}}}".encode(), v["brut"]))
                    sortie.append(b")")
                else:
                    sortie.append(f"{u} (UID {u} FLAGS ({flags}) RFC822.SIZE {len(v['brut'])})".encode())
            return "OK", sortie
        if commande == "STORE":
            if self.refus_store:
                return "NO", [b"refus"]
            spec, mode, valeur = args
            drapeaux = set(re.findall(r"\\\w+", valeur))
            for u in self._uids(spec, list(d)):
                if mode.startswith("+"):
                    d[u]["flags"] |= drapeaux
                else:
                    d[u]["flags"] -= drapeaux
            return "OK", [b""]
        if commande == "COPY":
            spec, cible = args
            for u in self._uids(spec, list(d)):
                self.deposer(cible.strip('"'), d[u]["brut"], d[u]["flags"] - {"\\Deleted"})
            return "OK", [b""]
        raise AssertionError(commande)


@override_settings(**CONF)
class BoiteMailTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.ecole = School.objects.create(name="FEBA", address="Cotonou", code="BM-FEBA")
        mk = lambda n, role, school=None: CustomUser.objects.create_user(username=n, email=f"{n}@t.bj", password="x",
                                                                          role=role, school=school, first_name=n, last_name="T")
        cls.sa = mk("sa", "superadmin")
        cls.admin = mk("adm", "admin", cls.ecole)
        cls.admin2 = mk("adm2", "admin", cls.ecole)
        cls.prof = mk("prof", "teacher", cls.ecole)

    def setUp(self):
        FauxImap.reinitialiser()
        p = mock.patch("apps.boite_mail.imap.imaplib.IMAP4_SSL", FauxImap)
        p.start()
        self.addCleanup(p.stop)
        from django.core.cache import cache
        cache.delete("boite_mail:synchro")

    def cli(self, u):
        c = APIClient()
        c.force_authenticate(u)
        return c

    def test_synchronisation_initiale_puis_incrementale_sans_doublon(self):
        FauxImap.deposer("INBOX", brut("Inscription"), flags=("\\Seen",))
        FauxImap.deposer("INBOX", brut("Rendez-vous", piece=("dossier.pdf", b"%PDF-1.4 x")))
        bilan = synchroniser_tout()
        self.assertEqual(bilan["nouveaux"], 2)
        m = MessageMail.objects.get(sujet="Rendez-vous")
        self.assertEqual((m.dossier, m.lu, m.nb_pieces, m.expediteur_email), ("reception", False, 1, "parent@exemple.org"))
        self.assertEqual(m.pieces.get().nom, "dossier.pdf")
        self.assertTrue(MessageMail.objects.get(sujet="Inscription").lu)
        # Lecture sans marquer lu chez le fournisseur (BODY.PEEK).
        self.assertNotIn("\\Seen", FauxImap.dossiers["INBOX"][2]["flags"])
        self.assertEqual(synchroniser_tout()["nouveaux"], 0)
        FauxImap.deposer("INBOX", brut("Nouveau"))
        self.assertEqual(synchroniser_tout()["nouveaux"], 1)
        self.assertEqual(MessageMail.objects.filter(dossier="reception").count(), 3)

    def test_drapeaux_et_suppressions_faits_ailleurs_sont_repris(self):
        uid = FauxImap.deposer("INBOX", brut("A"))
        FauxImap.deposer("INBOX", brut("B"))
        synchroniser_tout()
        FauxImap.dossiers["INBOX"][uid]["flags"] |= {"\\Seen", "\\Flagged"}
        del FauxImap.dossiers["INBOX"][2]
        synchroniser_tout()
        a = MessageMail.objects.get(sujet="A")
        self.assertEqual((a.lu, a.important), (True, True))
        self.assertFalse(MessageMail.objects.filter(sujet="B").exists())

    def test_uidvalidity_change_resynchronise(self):
        FauxImap.deposer("INBOX", brut("A"))
        synchroniser_tout()
        FauxImap.uidvalidity["INBOX"] = 200
        synchroniser_tout()
        self.assertEqual(MessageMail.objects.filter(sujet="A").count(), 1)
        self.assertEqual(MessageMail.objects.get(sujet="A").uidvalidity, 200)

    def test_html_nettoye_et_images_distantes_bloquees_par_defaut(self):
        html = ('<p onclick="x()">Bonjour<script>alert(1)</script><img src="https://pistage.example/p.gif">'
                '<a href="javascript:alert(1)">x</a><iframe src="https://x"></iframe></p>')
        FauxImap.deposer("INBOX", brut("Html", html=html))
        synchroniser_tout()
        m = MessageMail.objects.get(sujet="Html")
        for interdit in ("script", "onclick", "javascript", "iframe", "pistage"):
            self.assertNotIn(interdit, m.html)
        self.assertTrue(m.a_images_distantes)
        r = self.cli(self.sa).get(f"/api/boite-mail/messages/{m.pk}/")
        self.assertNotIn("pistage", r.data["html"])
        r = self.cli(self.sa).get(f"/api/boite-mail/messages/{m.pk}/", {"images": "1"})
        self.assertIn("pistage.example", r.data["html"])
        self.assertNotIn("script", r.data["html"])

    def test_droits_explicites(self):
        FauxImap.deposer("INBOX", brut("A"))
        synchroniser_tout()
        m = MessageMail.objects.get()
        for u in (self.prof, self.admin):
            self.assertEqual(self.cli(u).get("/api/boite-mail/messages/").status_code, 403)
            self.assertEqual(self.cli(u).get(f"/api/boite-mail/messages/{m.pk}/").status_code, 403)
        self.assertFalse(self.cli(self.admin).get("/api/boite-mail/etat/").data["acces"])
        # Le super administrateur accorde la lecture seule à un administrateur.
        r = self.cli(self.sa).put("/api/boite-mail/acces/", {"utilisateur": self.admin.pk, "lire": True}, format="json")
        self.assertEqual(r.status_code, 200)
        c = self.cli(self.admin)
        self.assertEqual(c.get("/api/boite-mail/messages/").data["count"], 1)
        self.assertEqual(c.post(f"/api/boite-mail/messages/{m.pk}/action/", {"action": "corbeille"}, format="json").status_code, 403)
        self.assertEqual(c.post("/api/boite-mail/envoyer/", {"a": ["x@y.org"], "sujet": "s", "texte": "t"}, format="json").status_code, 403)
        self.assertEqual(c.get("/api/boite-mail/acces/").status_code, 403)      # seul le super administrateur gère
        # Un enseignant ne peut jamais recevoir de droit.
        self.assertEqual(self.cli(self.sa).put("/api/boite-mail/acces/", {"utilisateur": self.prof.pk, "lire": True}, format="json").status_code, 404)
        self.assertTrue(JournalBoiteMail.objects.filter(action="droits_modifies").exists())

    def test_actions_appliquees_chez_le_fournisseur_d_abord(self):
        uid = FauxImap.deposer("INBOX", brut("A"))
        synchroniser_tout()
        m = MessageMail.objects.get()
        c = self.cli(self.sa)
        self.assertEqual(c.post(f"/api/boite-mail/messages/{m.pk}/action/", {"action": "lu"}, format="json").status_code, 200)
        self.assertIn("\\Seen", FauxImap.dossiers["INBOX"][uid]["flags"])
        c.post(f"/api/boite-mail/messages/{m.pk}/action/", {"action": "important"}, format="json")
        self.assertIn("\\Flagged", FauxImap.dossiers["INBOX"][uid]["flags"])
        # Refus du fournisseur : aucune modification locale annoncée comme réussie.
        FauxImap.refus_store = True
        r = c.post(f"/api/boite-mail/messages/{m.pk}/action/", {"action": "non_lu"}, format="json")
        self.assertEqual(r.status_code, 502)
        m.refresh_from_db()
        self.assertTrue(m.lu)

    def test_archiver_corbeille_restaurer_supprimer(self):
        FauxImap.deposer("INBOX", brut("A"))
        synchroniser_tout()
        m = MessageMail.objects.get()
        c = self.cli(self.sa)
        c.post(f"/api/boite-mail/messages/{m.pk}/action/", {"action": "archiver"}, format="json")
        self.assertEqual(len(FauxImap.dossiers["INBOX"]), 0)
        self.assertEqual(len(FauxImap.dossiers["INBOX.Archive"]), 1)           # dossier créé à la demande
        synchroniser_tout()
        self.assertEqual(MessageMail.objects.filter(sujet="A").count(), 1)     # rapproché, pas dupliqué
        m = MessageMail.objects.get(sujet="A")
        self.assertEqual((m.dossier, m.uid), ("archives", 1))
        self.assertEqual(c.post(f"/api/boite-mail/messages/{m.pk}/action/", {"action": "supprimer_definitivement"}, format="json").status_code, 400)
        c.post(f"/api/boite-mail/messages/{m.pk}/action/", {"action": "corbeille"}, format="json")
        synchroniser_tout()
        m = MessageMail.objects.get(sujet="A")
        self.assertEqual(m.dossier, "corbeille")
        c.post(f"/api/boite-mail/messages/{m.pk}/action/", {"action": "restaurer"}, format="json")
        synchroniser_tout()
        m = MessageMail.objects.get(sujet="A")
        self.assertEqual(m.dossier, "reception")
        c.post(f"/api/boite-mail/messages/{m.pk}/action/", {"action": "corbeille"}, format="json")
        synchroniser_tout()
        m = MessageMail.objects.get(sujet="A")
        self.assertEqual(c.post(f"/api/boite-mail/messages/{m.pk}/action/", {"action": "supprimer_definitivement"}, format="json").status_code, 200)
        self.assertEqual(len(FauxImap.dossiers["INBOX.Trash"]), 0)
        self.assertFalse(MessageMail.objects.filter(sujet="A").exists())

    def test_repondre_avec_fil_copie_dans_envoyes_et_cci_invisible(self):
        FauxImap.deposer("INBOX", brut("Question", mid="<q1@exemple.org>"))
        synchroniser_tout()
        origine = MessageMail.objects.get()
        r = self.cli(self.sa).post("/api/boite-mail/envoyer/", {
            "mode": "repondre", "origine": origine.pk, "a": ["parent@exemple.org"], "cc": ["direction@exemple.org"],
            "cci": ["archive@exemple.org"], "sujet": "Re: Question", "texte": "Réponse"}, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        envoye = mail.outbox[-1]
        entetes = envoye.message()
        self.assertEqual(entetes["In-Reply-To"], "<q1@exemple.org>")
        self.assertNotIn("archive@exemple.org", str(entetes))                  # Cci absent des en-têtes
        self.assertIn("archive@exemple.org", envoye.recipients())               # mais bien destinataire
        self.assertEqual(entetes["Cc"], "direction@exemple.org")
        self.assertEqual(len(FauxImap.dossiers["INBOX.Sent"]), 1)              # copie chez le fournisseur
        self.assertIn("\\Seen", FauxImap.dossiers["INBOX"][1]["flags"])        # original marqué lu
        synchroniser_tout()
        self.assertEqual(MessageMail.objects.filter(dossier="envoyes", sujet="Re: Question").count(), 1)   # pas de doublon

    def test_transfert_avec_pieces_et_validations(self):
        FauxImap.deposer("INBOX", brut("Dossier", piece=("fiche.pdf", b"%PDF-1.4 y")))
        synchroniser_tout()
        origine = MessageMail.objects.get()
        c = self.cli(self.sa)
        r = c.post("/api/boite-mail/envoyer/", {"mode": "transferer", "origine": origine.pk, "a": ["secretariat@exemple.org"],
                                                "sujet": "Tr: Dossier", "texte": "Pour suite"}, format="json")
        self.assertEqual(r.status_code, 201)
        self.assertEqual([a[0] for a in mail.outbox[-1].attachments], ["fiche.pdf"])
        for corps in ({"a": ["pas-une-adresse"], "sujet": "s", "texte": "t"}, {"a": [], "sujet": "s", "texte": "t"},
                      {"a": ["x@y.org"], "sujet": "", "texte": "t"}, {"a": ["x@y.org"], "sujet": "s", "texte": "  "}):
            self.assertEqual(c.post("/api/boite-mail/envoyer/", corps, format="json").status_code, 400, corps)
        r = c.post("/api/boite-mail/envoyer/", {"a": "x@y.org", "sujet": "s", "texte": "t",
                                                "attachments": [SimpleUploadedFile("v.exe", b"MZ")]}, format="multipart")
        self.assertEqual(r.status_code, 400)

    @override_settings(DEFAULT_FROM_EMAIL="contact@globalfeba.com")
    def test_envois_feba_dans_envoyes_sans_doublon(self):
        from apps.notifications.mailer import send_tracked_email
        send_tracked_email(purpose="test", to_email="famille@exemple.org", subject="Reçu de paiement", text_body="Merci")
        synchroniser_tout()
        synchroniser_tout()
        self.assertEqual(MessageMail.objects.filter(dossier="envoyes", sujet="Reçu de paiement").count(), 1)
        m = MessageMail.objects.get(sujet="Reçu de paiement")
        self.assertEqual((m.source, m.origine, m.a[0]["email"]), ("feba", "test", "famille@exemple.org"))
        # Un envoi d'une AUTRE adresse (noreply@) n'appartient pas à la boîte contact.
        with override_settings(DEFAULT_FROM_EMAIL="noreply@globalfeba.com"):
            send_tracked_email(purpose="test", to_email="x@exemple.org", subject="Autre adresse", text_body="x")
        synchroniser_tout()
        self.assertFalse(MessageMail.objects.filter(sujet="Autre adresse").exists())

    def test_pieces_jointes_reservees_aux_ayants_droit(self):
        FauxImap.deposer("INBOX", brut("Dossier", piece=("fiche.pdf", b"%PDF-1.4 z")))
        synchroniser_tout()
        piece = MessageMail.objects.get().pieces.get()
        self.assertEqual(self.cli(self.prof).get(f"/api/boite-mail/pieces/{piece.pk}/").status_code, 403)
        r = self.cli(self.sa).get(f"/api/boite-mail/pieces/{piece.pk}/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(b"".join(r.streaming_content), b"%PDF-1.4 z")
        self.assertIn("attachment", r["Content-Disposition"])

    def test_recherche_filtres_pagination(self):
        for i in range(55):
            FauxImap.deposer("INBOX", brut(f"Sujet {i}", de=f"P{i} <p{i}@exemple.org>"),
                             flags=("\\Seen",) if i % 2 else ())
        synchroniser_tout()
        c = self.cli(self.sa)
        r = c.get("/api/boite-mail/messages/")
        self.assertEqual((r.data["count"], len(r.data["results"]), r.data["pages"]), (55, 50, 2))
        self.assertEqual(c.get("/api/boite-mail/messages/", {"page": 2}).data["results"].__len__(), 5)
        self.assertEqual(c.get("/api/boite-mail/messages/", {"non_lus": 1}).data["count"], 28)
        self.assertEqual(c.get("/api/boite-mail/messages/", {"expediteur": "p7@"}).data["count"], 1)
        self.assertEqual(c.get("/api/boite-mail/messages/", {"q": "Sujet 4"}).data["count"], 11)
        self.assertEqual(c.get("/api/boite-mail/messages/", {"dossier": "spam"}).status_code, 400)
        self.assertEqual(c.get("/api/boite-mail/etat/").data["non_lus"]["reception"], 28)

    @override_settings(MAILBOX_IMAP_PASSWORD="mauvais")
    def test_fournisseur_indisponible_message_clair_sans_secret(self):
        r = self.cli(self.sa).post("/api/boite-mail/synchroniser/")
        self.assertEqual(r.status_code, 502)
        self.assertIn("fournisseur", r.data["detail"])
        self.assertNotIn("mauvais", str(r.data))

    @override_settings(MAILBOX_IMAP_HOST="")
    def test_non_configuree(self):
        e = self.cli(self.sa).get("/api/boite-mail/etat/").data
        self.assertFalse(e["configuree"])
        self.assertNotIn("secret-de-test", str(e))
