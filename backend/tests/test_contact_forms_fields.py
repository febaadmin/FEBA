"""
P5 — Les formulaires de contact conservent TOUT ce que le visiteur saisit.

LE DÉFAUT
---------
Le formulaire de contact FEBA ne demandait pas de numéro WhatsApp, et son
serializer ne le déclarait pas. DRF ignore silencieusement une clé non
déclarée : un navigateur qui l'envoyait voyait la valeur disparaître entre
la requête et la base, sans erreur, sans journal, sans rien.

Côté FEBA FHA, le champ était bien enregistré — mais l'écran
d'administration ne l'affichait pas. Une famille laissait son WhatsApp et
personne ne le voyait jamais.

Ces tests suivent chaque champ sur toute sa chaîne : payload HTTP →
serializer → modèle → base → serializer de lecture → API d'administration.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.schools.models import School
from apps.website.models import ContactMessage

User = get_user_model()


class ContactFormFieldsTests(TestCase):
    """Chaque champ envoyé se retrouve en base, à l'identique."""

    @classmethod
    def setUpTestData(cls):
        School.objects.update_or_create(
            code=School.CODE_FEBA,
            defaults=dict(name="Faith & Excellence Bilingual Academy",
                          address="Akpakpa, Cotonou", city="Cotonou",
                          country="Bénin", currency_code="XOF"),
        )
        School.objects.update_or_create(
            code=School.CODE_FEBA_FHA,
            defaults=dict(name="FEBA French Heritage Academy",
                          address="Programme en ligne", entity_type="online",
                          currency_code="USD"),
        )

    def setUp(self):
        self.client = APIClient()

    def test_le_whatsapp_du_formulaire_feba_arrive_en_base(self):
        response = self.client.post(
            "/api/website/contact/",
            {
                "name": "Adjoa Kponou",
                "email": "adjoa@example.test",
                "phone": "+229 97 00 00 00",
                "whatsapp": "+229 96 11 22 33",
                "subject": "Inscription CM1",
                "message": "Bonjour, je souhaite inscrire ma fille.",
                "consent": True,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)

        message = ContactMessage.objects.get(email="adjoa@example.test")
        self.assertEqual(
            message.whatsapp, "+229 96 11 22 33",
            "Le numéro WhatsApp a disparu entre le formulaire et la base.",
        )
        self.assertEqual(message.phone, "+229 97 00 00 00")
        self.assertEqual(message.entity.code, School.CODE_FEBA)

    def test_tous_les_champs_du_formulaire_fha_arrivent_en_base(self):
        payload = {
            "name": "Marie Dupont",
            "email": "marie@example.test",
            "phone": "+1 215 555 0100",
            "whatsapp": "+1 215 555 0199",
            "country": "United States",
            "state_province": "Pennsylvania",
            "timezone": "America/New_York",
            "preferred_language": "en",
            "category": "enrollment",
            "subject": "French classes for my son",
            "message": "Hello, I would like more information.",
            "consent": True,
        }
        response = self.client.post(
            "/api/website/fha/contact/", payload, format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)

        message = ContactMessage.objects.get(email="marie@example.test")
        for field in ("phone", "whatsapp", "country", "state_province",
                      "timezone", "preferred_language", "category",
                      "subject", "message"):
            with self.subTest(champ=field):
                self.assertEqual(
                    getattr(message, field), payload[field],
                    f"« {field} » ne se retrouve pas en base tel qu'il a été saisi.",
                )
        self.assertEqual(message.entity.code, School.CODE_FEBA_FHA)

    def test_un_message_de_5000_caracteres_est_stocke_entier(self):
        long_message = "Bonjour. " * 600
        long_message = long_message[:5000]
        response = self.client.post(
            "/api/website/contact/",
            {"name": "Test", "email": "long@example.test", "subject": "Long",
             "message": long_message, "consent": True},
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        stored = ContactMessage.objects.get(email="long@example.test").message
        self.assertEqual(len(stored), 5000)
        self.assertEqual(stored, long_message)

    def test_un_message_contenant_du_html_est_stocke_tel_quel(self):
        """
        On ne nettoie PAS le contenu à l'enregistrement.

        Échapper ici détruirait le message d'un visiteur qui parle
        légitimement de code. La protection est à l'affichage, où React
        rend le texte sans jamais l'interpréter (voir LongText.jsx).
        """
        raw = "<script>alert('xss')</script> & <b>gras</b>"
        response = self.client.post(
            "/api/website/contact/",
            {"name": "Test", "email": "html@example.test", "subject": "HTML",
             "message": raw, "consent": True},
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(
            ContactMessage.objects.get(email="html@example.test").message, raw,
        )


class ContactInboxVisibilityTests(TestCase):
    """Un admin ne voit que les messages de SON académie."""

    @classmethod
    def setUpTestData(cls):
        # La migration crée FEBA_FHA ; FEBA n'existe que si une école
        # préexistait. Sur une base de test vierge, on la crée.
        cls.feba, _ = School.objects.update_or_create(
            code=School.CODE_FEBA,
            defaults=dict(name="Faith & Excellence Bilingual Academy",
                          address="Akpakpa, Cotonou", city="Cotonou",
                          country="Bénin", currency_code="XOF"),
        )
        cls.fha, _ = School.objects.update_or_create(
            code=School.CODE_FEBA_FHA,
            defaults=dict(name="FEBA French Heritage Academy",
                          address="Programme en ligne", entity_type="online",
                          currency_code="USD"),
        )

        cls.feba_message = ContactMessage.objects.create(
            entity=cls.feba, name="Parent FEBA", email="p@feba.test",
            subject="Sujet FEBA", message="Message FEBA",
            phone="+229 97 00 00 00", whatsapp="+229 96 11 22 33",
        )
        cls.fha_message = ContactMessage.objects.create(
            entity=cls.fha, name="Parent FHA", email="p@fha.test",
            subject="Sujet FHA", message="Message FHA",
            whatsapp="+1 215 555 0199", country="United States",
        )

        cls.feba_admin = User.objects.create_user(
            username="admin.feba", email="admin.feba@test", password="x",
            role="admin", school=cls.feba,
        )
        cls.fha_admin = User.objects.create_user(
            username="admin.fha", email="admin.fha@test", password="x",
            role="admin", school=cls.fha,
        )
        cls.superadmin = User.objects.create_user(
            username="super", email="super@test", password="x",
            role="superadmin", school=cls.feba,
        )

    def _inbox(self, user):
        client = APIClient()
        client.force_authenticate(user=user)
        response = client.get("/api/website/admin/contact-messages/")
        self.assertEqual(response.status_code, 200, response.data)
        data = response.data
        return data.get("results", data)

    def test_l_admin_feba_ne_voit_pas_les_messages_fha(self):
        emails = {row["email"] for row in self._inbox(self.feba_admin)}
        self.assertIn("p@feba.test", emails)
        self.assertNotIn("p@fha.test", emails)

    def test_l_admin_fha_ne_voit_pas_les_messages_feba(self):
        emails = {row["email"] for row in self._inbox(self.fha_admin)}
        self.assertIn("p@fha.test", emails)
        self.assertNotIn("p@feba.test", emails)

    def test_le_whatsapp_est_expose_a_l_administration(self):
        rows = {row["email"]: row for row in self._inbox(self.feba_admin)}
        self.assertEqual(rows["p@feba.test"]["whatsapp"], "+229 96 11 22 33")

    def test_chaque_ligne_porte_le_code_de_son_academie(self):
        """P5 — indispensable au badge FEBA / FEBA FHA en vue consolidée."""
        for row in self._inbox(self.feba_admin):
            with self.subTest(email=row["email"]):
                self.assertEqual(row["entity_code"], School.CODE_FEBA)
                self.assertTrue(row["entity_short_name"])

    def test_le_superadmin_voit_les_deux_avec_leur_academie(self):
        rows = {row["email"]: row for row in self._inbox(self.superadmin)}
        self.assertIn("p@feba.test", rows)
        self.assertIn("p@fha.test", rows)
        self.assertEqual(rows["p@feba.test"]["entity_code"], School.CODE_FEBA)
        self.assertEqual(rows["p@fha.test"]["entity_code"], School.CODE_FEBA_FHA)

    def test_un_admin_ne_peut_pas_ouvrir_un_message_de_l_autre_academie(self):
        client = APIClient()
        client.force_authenticate(user=self.feba_admin)
        response = client.get(
            f"/api/website/admin/contact-messages/{self.fha_message.pk}/"
        )
        self.assertEqual(
            response.status_code, 404,
            "Un accès direct par identifiant expose un message de l'autre académie.",
        )

    def test_le_contenu_saisi_reste_en_lecture_seule(self):
        """Un message reçu est une pièce, pas un brouillon."""
        client = APIClient()
        client.force_authenticate(user=self.feba_admin)
        response = client.patch(
            f"/api/website/admin/contact-messages/{self.feba_message.pk}/",
            {"message": "réécrit", "whatsapp": "+000", "is_read": True},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.feba_message.refresh_from_db()
        self.assertEqual(self.feba_message.message, "Message FEBA")
        self.assertEqual(self.feba_message.whatsapp, "+229 96 11 22 33")
        self.assertTrue(self.feba_message.is_read)


class FreeformTextIsPreservedTests(TestCase):
    """
    Un texte libre arrive en base EXACTEMENT tel qu'il a été saisi.

    Défaut trouvé en validant l'archive extraite : un message de 7 014
    caractères se terminant par deux retours à la ligne était stocké à
    7 012. `trim_whitespace` vaut True par défaut dans DRF et retire les
    blancs de début et de fin — sans erreur, sans journal, sans que
    personne ne le sache.

    Deux caractères, ici. Mais c'est la même mécanique qui, sur un message
    commençant par une ligne vide voulue ou finissant par un tableau en
    texte, modifie ce que le visiteur a écrit — et l'application affirme
    ensuite ne rien tronquer.
    """

    @classmethod
    def setUpTestData(cls):
        School.objects.update_or_create(
            code=School.CODE_FEBA,
            defaults=dict(name="Faith & Excellence Bilingual Academy",
                          address="Akpakpa, Cotonou", currency_code="XOF"),
        )
        School.objects.update_or_create(
            code=School.CODE_FEBA_FHA,
            defaults=dict(name="FEBA French Heritage Academy",
                          address="Programme en ligne", entity_type="online",
                          currency_code="USD"),
        )

    #: Volontairement encadré de blancs et de retours à la ligne : c'est
    #: exactement ce que le nettoyage par défaut supprimait.
    MESSAGE = "\n\nBonjour,\n\nUn paragraphe.\n\nUn autre.\n\n   \n"

    def _submit(self, url, extra=None):
        payload = {
            "name": "Testeur", "email": "freeform@example.test",
            "subject": "Mise en forme", "message": self.MESSAGE, "consent": True,
        }
        payload.update(extra or {})
        response = APIClient().post(url, payload, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        return ContactMessage.objects.get(email="freeform@example.test")

    def test_le_message_feba_est_stocke_au_caractere_pres(self):
        message = self._submit("/api/website/contact/")
        self.assertEqual(len(message.message), len(self.MESSAGE))
        self.assertEqual(message.message, self.MESSAGE)

    def test_le_message_fha_est_stocke_au_caractere_pres(self):
        message = self._submit("/api/website/fha/contact/",
                               {"category": "general"})
        self.assertEqual(len(message.message), len(self.MESSAGE))
        self.assertEqual(message.message, self.MESSAGE)

    def test_un_message_de_5000_caracteres_ne_perd_rien(self):
        long_message = ("Ligne.\n" * 900)[:5000] + "\n\n"
        response = APIClient().post(
            "/api/website/contact/",
            {"name": "T", "email": "long5000@example.test", "subject": "S",
             "message": long_message, "consent": True}, format="json")
        self.assertEqual(response.status_code, 201)
        stored = ContactMessage.objects.get(email="long5000@example.test").message
        self.assertEqual(len(stored), len(long_message))
        self.assertEqual(stored, long_message)

    def test_les_champs_d_une_ligne_restent_nettoyes(self):
        """
        Le nettoyage garde sa place là où il aide.

        Un espace en fin de nom est une scorie de saisie, pas une
        intention. Désactiver le nettoyage partout produirait des noms et
        des sujets avec des blancs invisibles, triés et affichés de
        travers.
        """
        response = APIClient().post(
            "/api/website/contact/",
            {"name": "  Ana Ba  ", "email": "trim@example.test",
             "subject": "  Sujet  ", "message": "Bonjour", "consent": True},
            format="json")
        self.assertEqual(response.status_code, 201)
        message = ContactMessage.objects.get(email="trim@example.test")
        self.assertEqual(message.name, "Ana Ba")
        self.assertEqual(message.subject, "Sujet")


class FHAFreeformTextTests(TestCase):
    """Les textes libres de la fiche d'inscription suivent la même règle."""

    @classmethod
    def setUpTestData(cls):
        School.objects.update_or_create(
            code=School.CODE_FEBA_FHA,
            defaults=dict(name="FEBA French Heritage Academy",
                          address="Programme en ligne", entity_type="online",
                          currency_code="USD", matricule_prefix="FHA"),
        )

    def test_les_besoins_particuliers_conservent_leur_mise_en_forme(self):
        from tests.test_fha_enrollment_workflow import payload
        from apps.website.models import FHAEnrollmentApplication

        texte = "\n\nSéances courtes.\n\n- pause toutes les 10 min\n\n  \n"
        data = payload(special_needs=texte, availability_notes=texte)
        response = APIClient().post("/api/website/fha/enroll/", data,
                                    format="json")
        self.assertEqual(response.status_code, 201, response.data)
        application = FHAEnrollmentApplication.objects.get(
            reference=response.data["reference"])
        self.assertEqual(application.special_needs, texte)
        self.assertEqual(application.availability_notes, texte)
