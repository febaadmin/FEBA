"""
Phase 7 — E-mails groupés devenus un outil de composition : À, Cc, Cci, adresses
saisies, HTML nettoyé, brouillons (avec pièces jointes), signature, recherche des
envois, rejets définitifs.

Confidentialité vérifiée sur les messages RÉELLEMENT produits (en-têtes et
enveloppe SMTP de chaque copie) : une adresse en Cci n'apparaît jamais chez les
autres, et un envoi individuel ne révèle aucune adresse.
"""
import smtplib
from unittest import mock

from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.notifications.campaign_models import BrouillonEmail, EmailCampaign, EmailCampaignRecipient
from apps.notifications.html_securise import en_texte, nettoyer
from tests.test_audit_p1_mass_email import URL, MassEmailBase, token

PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF"


def entetes(message):
    m = message.message()
    return {"to": m.get("To", ""), "cc": m.get("Cc", ""), "bcc": m.get("Bcc", "")}


class ChampsDestinatairesTests(MassEmailBase):
    def test_adresses_saisies_et_comptes_choisis_message_individuel(self):
        r = self.send(self.admin, adresses={"a": ["externe@exemple.org", self.parents[0].id]})
        self.assertEqual(r.status_code, 201, r.content)
        envois = sorted(mail.outbox, key=lambda m: m.to[0])
        self.assertEqual([m.recipients() for m in envois], [["externe@exemple.org"], [self.parents[0].email]])
        for m in envois:     # individuel : chacun ne voit que sa propre adresse
            h = entetes(m)
            self.assertEqual(h["to"], m.to[0])
            self.assertEqual((h["cc"], h["bcc"]), ("", ""))

    def test_message_commun_a_cc_visibles_cci_invisible(self):
        r = self.send(self.admin, mode="commun", adresses={
            "a": ["a1@exemple.org", "a2@exemple.org"], "cc": ["direction@exemple.org"], "cci": ["cache@exemple.org"]})
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(len(mail.outbox), 4)
        for m in mail.outbox:
            # Enveloppe : ce destinataire SEUL (pas de rediffusion à toute la liste).
            self.assertEqual(len(m.recipients()), 1)
            h = entetes(m)
            self.assertEqual(h["to"], "a1@exemple.org, a2@exemple.org")
            self.assertEqual(h["cc"], "direction@exemple.org")
            if m.recipients() != ["cache@exemple.org"]:
                self.assertNotIn("cache@exemple.org", str(m.message()))
        copie_cachee = next(m for m in mail.outbox if m.recipients() == ["cache@exemple.org"])
        self.assertNotIn("cache@exemple.org", entetes(copie_cachee)["to"] + entetes(copie_cachee)["cc"])
        champs = dict(EmailCampaignRecipient.objects.values_list("email", "champ"))
        self.assertEqual(champs["cache@exemple.org"], "cci")
        self.assertEqual(champs["direction@exemple.org"], "cc")

    def test_profils_toujours_individuels_meme_en_message_commun(self):
        self.send(self.admin, mode="commun", roles=["parent"], adresses={"a": ["a1@exemple.org"]})
        parents = [m for m in mail.outbox if m.recipients()[0].startswith("parent")]
        self.assertEqual(len(parents), 4)
        for m in parents:
            self.assertEqual(entetes(m)["to"], m.recipients()[0])
            self.assertNotIn("a1@exemple.org", str(m.message()))

    def test_doublons_entre_champs_une_seule_copie(self):
        r = self.send(self.admin, roles=["parent"], adresses={
            "a": [self.parents[0].email.upper()], "cc": [self.parents[0].id], "cci": ["x@exemple.org", "X@exemple.org"]})
        self.assertEqual(r.status_code, 201, r.content)
        destinataires = [m.recipients()[0].lower() for m in mail.outbox]
        self.assertEqual(destinataires.count(self.parents[0].email.lower()), 1)
        self.assertEqual(destinataires.count("x@exemple.org"), 1)
        self.assertEqual(EmailCampaignRecipient.objects.get(email=self.parents[0].email.lower(), status="sent").champ, "a")
        self.assertEqual(EmailCampaignRecipient.objects.filter(email=self.parents[0].email.lower(), status="skipped_duplicate").count(), 2)

    def test_adresse_invalide_et_compte_d_une_autre_academie_refuses(self):
        r = self.preview(self.admin, adresses={"a": ["pas-une-adresse"]})
        self.assertEqual(r.status_code, 400)
        self.assertIn("invalide", str(r.json()))
        r = self.preview(self.admin, adresses={"cc": [self.fha_parent.id]})
        self.assertEqual(r.status_code, 400)
        self.assertEqual(len(mail.outbox), 0)

    def test_apercu_compte_par_champ(self):
        r = self.preview(self.admin, roles=["student"], adresses={"a": ["a@x.org"], "cci": ["b@x.org"]})
        self.assertEqual(r.json()["par_champ"], {"a": 1, "cci": 1, "groupe": 2})


class HtmlSecuriseTests(MassEmailBase):
    def test_nettoyage_liste_blanche(self):
        propre = nettoyer('<p onclick="x()">Bonjour <b>tous</b><script>alert(1)</script>'
                          '<img src="https://pistage.example/p.gif"><a href="javascript:alert(1)">piège</a>'
                          '<a href="https://feba.example">site</a><iframe src="x"></iframe></p>')
        self.assertNotIn("script", propre)
        self.assertNotIn("onclick", propre)
        self.assertNotIn("img", propre)
        self.assertNotIn("javascript", propre)
        self.assertNotIn("iframe", propre)
        self.assertIn('<a href="https://feba.example" rel="noopener noreferrer">site</a>', propre)
        self.assertIn("<b>tous</b>", propre)

    def test_version_texte(self):
        t = en_texte(nettoyer("<p>Bonjour,</p><ul><li>un</li><li>deux</li></ul><p>Voir <a href='https://x.org'>le site</a></p>"))
        self.assertEqual(t, "Bonjour,\n\n- un\n- deux\n\nVoir le site (https://x.org)")

    def test_envoi_html_nettoye_avec_alternative_texte(self):
        r = self.send(self.admin, body_format="html", body="ignoré",
                      body_html="<p>Réunion <strong>lundi</strong></p><script>vol()</script>",
                      adresses={"a": ["a@x.org"]})
        self.assertEqual(r.status_code, 201, r.content)
        m = mail.outbox[0]
        html_part = m.alternatives[0][0]
        self.assertIn("<strong>lundi</strong>", html_part)
        self.assertNotIn("vol()", html_part)
        self.assertIn("Réunion lundi", m.body)
        c = EmailCampaign.objects.get()
        self.assertEqual((c.body_format, c.body), ("html", "Réunion lundi"))

    def test_html_vide_refuse(self):
        r = self.send(self.admin, body_format="html", body_html="<script>x</script>", adresses={"a": ["a@x.org"]},
                      expected=1)
        self.assertEqual(r.status_code, 400)


class BrouillonsTests(MassEmailBase):
    def test_cycle_complet_brouillon_pieces_envoi(self):
        c = self.client_for(self.admin)
        r = c.post(f"{URL}/brouillons/", {"objet": "Sortie", "corps": "Bonjour", "format": "texte",
                                          "audience": {"adresses": {"a": ["a@x.org"], "cci": [self.parents[1].id]}}},
                   format="json")
        self.assertEqual(r.status_code, 201, r.content)
        bid = r.json()["id"]
        r = c.post(f"{URL}/brouillons/{bid}/pieces/", {"attachments": [SimpleUploadedFile("programme.pdf", PDF)]},
                   format="multipart")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual([p["nom"] for p in r.json()["pieces"]], ["programme.pdf"])
        r = c.post(f"{URL}/brouillons/{bid}/pieces/", {"attachments": [SimpleUploadedFile("faux.pdf", b"MZ\x90\x00")]},
                   format="multipart")
        self.assertEqual(r.status_code, 400)                                    # contenu ≠ extension
        r = c.patch(f"{URL}/brouillons/{bid}/", {"objet": "Sortie scolaire"}, format="json")
        self.assertEqual((r.json()["objet"], r.json()["audience"]["adresses"]["a"]), ("Sortie scolaire", ["a@x.org"]))
        self.assertEqual(len(c.get(f"{URL}/brouillons/").json()["results"]), 1)
        # Envoi depuis le brouillon : ses pièces partent, le brouillon disparaît.
        r = self.send(self.admin, subject="Sortie scolaire", body="Bonjour", brouillon_id=bid,
                      adresses={"a": ["a@x.org"], "cci": [self.parents[1].id]})
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(len(mail.outbox), 2)
        self.assertEqual([a[0] for a in mail.outbox[0].attachments], ["programme.pdf"])
        self.assertFalse(BrouillonEmail.objects.filter(pk=bid).exists())

    def test_brouillon_prive_a_son_auteur(self):
        b = BrouillonEmail.objects.create(academy=self.feba, auteur=self.admin, objet="secret")
        autre = self.client_for(self.admin_fha)
        self.assertIn(autre.get(f"{URL}/brouillons/{b.pk}/").status_code, (403, 404))
        self.assertIn(autre.delete(f"{URL}/brouillons/{b.pk}/").status_code, (403, 404))
        self.assertTrue(BrouillonEmail.objects.filter(pk=b.pk).exists())
        self.assertEqual(self.client_for(self.teachers[0]).get(f"{URL}/brouillons/").status_code, 403)
        r = self.send(self.admin_fha, brouillon_id=b.pk, adresses={"a": ["z@x.org"]})
        self.assertEqual(r.status_code, 400)

    def test_signature(self):
        c = self.client_for(self.admin)
        self.assertEqual(c.get(f"{URL}/signature/").json(), {"texte": ""})
        self.assertEqual(c.put(f"{URL}/signature/", {"texte": "La direction"}, format="json").json()["texte"], "La direction")
        self.assertEqual(self.client_for(self.admin_fha).get(f"{URL}/signature/").json(), {"texte": ""})


class SuiviEnvoisTests(MassEmailBase):
    def test_recherche_et_filtres_des_envois(self):
        self.send(self.admin, subject="Réunion parents", adresses={"a": ["a@x.org"]})
        self.send(self.admin, subject="Cantine", adresses={"a": ["cantine@x.org"]})
        c = self.client_for(self.admin)
        sujets = lambda **p: [x["subject"] for x in c.get(f"{URL}/campaigns/", p).json()["results"]]
        self.assertEqual(sujets(q="réunion"), ["Réunion parents"])
        self.assertEqual(sujets(q="cantine@x"), ["Cantine"])
        self.assertEqual(sorted(sujets(statut="done")), ["Cantine", "Réunion parents"])
        self.assertEqual(sujets(statut="failed"), [])
        self.assertEqual(c.get(f"{URL}/campaigns/", {"statut": "livre"}).status_code, 400)
        self.assertEqual(c.get(f"{URL}/campaigns/", {"du": "hier"}).status_code, 400)
        self.assertEqual(self.client_for(self.admin_fha).get(f"{URL}/campaigns/", {"q": "réunion"}).json()["results"], [])
        detail = c.get(f"{URL}/campaigns/{EmailCampaign.objects.get(subject='Cantine').pk}/").json()
        self.assertEqual(detail["recipients"][0]["champ"], "a")
        self.assertEqual(detail["status_display"], "Envoyé au fournisseur")        # jamais « délivré »

    def test_rejet_definitif_apres_les_nouveaux_essais(self):
        from apps.notifications.mailer import MAX_ATTEMPTS, retry_due
        refus = smtplib.SMTPRecipientsRefused({"inconnu@x.org": (550, b"No such user")})
        with mock.patch("django.core.mail.EmailMultiAlternatives.send", side_effect=refus):
            r = self.send(self.admin, adresses={"a": ["inconnu@x.org"]})
            self.assertEqual(r.status_code, 201, r.content)
            dest = EmailCampaignRecipient.objects.get()
            self.assertEqual(dest.status, "retry")                       # nouvel essai programmé
            for _ in range(MAX_ATTEMPTS - 1):
                from apps.notifications.campaigns import sync_recipient
                dest.refresh_from_db()
                sync_recipient(dest, retry_due(dest.delivery))
        dest.refresh_from_db()
        self.assertEqual((dest.status, dest.delivery.status), ("rejected", "failed"))
        self.assertEqual(dest.get_status_display(), "Rejeté par le serveur d'envoi")
        from apps.notifications.campaigns import refresh_campaign_status
        refresh_campaign_status(EmailCampaign.objects.get())
        self.assertEqual(EmailCampaign.objects.get().status, "failed")
        # Un rejet reste relançable à la main (adresse corrigée côté destinataire).
        self.assertIn("rejected", EmailCampaignRecipient.RETRYABLE)

    def test_double_soumission_un_seul_envoi(self):
        jeton = token()
        self.send(self.admin, client_token=jeton, adresses={"a": ["a@x.org"]})
        self.send(self.admin, client_token=jeton, adresses={"a": ["a@x.org"]})
        self.assertEqual(EmailCampaign.objects.count(), 1)
        self.assertEqual(len(mail.outbox), 1)
