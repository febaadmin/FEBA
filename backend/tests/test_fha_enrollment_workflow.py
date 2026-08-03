"""
P1 — Le parcours d'inscription FEBA FHA, de bout en bout.

Chaque test correspond à une étape du parcours demandé. Ils sont écrits
pour échouer sur le défaut d'origine, pas pour décrire le code : un test
qui se contenterait de vérifier « la vue renvoie 201 » aurait passé avant
comme après, alors que la fiche PDF n'existait pas et que l'e-mail partait
avec `fail_silently=True`.
"""
import datetime
import os
import re

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.notifications.email_models import EmailDelivery
from apps.schools.models import School
from apps.website.models import FHAApplicationStatusHistory, FHAEnrollmentApplication

User = get_user_model()


def payload(**overrides):
    """Une fiche complète et valide, telle qu'un parent la remplirait."""
    data = {
        "child_last_name": "Gbêdjissi",
        "child_first_name": "Élisabeth",
        "child_birth_date": "2015-04-12",
        "child_city": "Philadelphia",
        "child_state_province": "Pennsylvania",
        "child_country": "United States",
        "child_current_school": "Penn Alexander School",
        "child_grade": "4th grade",
        "family_origin_country": "Bénin",
        "home_main_language": "English",
        "other_languages": "Fon, Yoruba",
        "french_speakers_with_child": "Grand-mère",
        "french_speakers_relation": "Grand-mère maternelle",
        "french_levels": ["few_words", "understands_replies_english"],
        "french_level_notes": "Comprend les consignes simples.",
        "previous_courses": True,
        "bilingual_school": False,
        "stay_in_francophone_country": True,
        "certifications_obtained": "Aucune",
        "experience_duration": "6 mois",
        "experience_comments": "Cours du samedi en 2024.",
        "parent_goals": ["grandparents", "african_culture"],
        "parent_goals_other": "Préparer un voyage au Bénin",
        "parent1_last_name": "Gbêdjissi",
        "parent1_first_name": "Ahouéfa",
        "parent1_relation": "Mère",
        "parent1_phone": "+1 215 555 0100",
        "parent1_whatsapp": "+1 215 555 0199",
        "parent1_email": "ahouefa@example.test",
        "parent1_address": "4200 Pine Street",
        "parent1_city": "Philadelphia",
        "parent1_state_province": "Pennsylvania",
        "parent1_country": "United States",
        "parent1_postal_code": "19104",
        "parent1_preferred_language": "fr",
        "parent1_timezone": "America/New_York",
        "parent2_last_name": "Kponou",
        "parent2_first_name": "Jean-Baptiste",
        "parent2_relation": "Père",
        "parent2_phone": "+1 215 555 0111",
        "parent2_whatsapp": "+1 215 555 0122",
        "parent2_email": "jb@example.test",
        "emergency_name": "Marie Dossou",
        "emergency_relation": "Tante",
        "emergency_phone": "+1 215 555 0133",
        "emergency_email": "marie@example.test",
        "emergency_contact_authorized": True,
        "available_days": [3, 6],
        "available_time_slots": [{"start": "16:00", "end": "17:30"}],
        "family_timezone": "America/New_York",
        "weekday_or_weekend": "both",
        "availability_notes": "Pas avant 16 h en semaine.",
        "has_computer": True,
        "has_tablet": True,
        "has_camera": True,
        "has_microphone": True,
        "has_headset": False,
        "has_internet": True,
        "can_print": False,
        "equipment_notes": "Casque à acheter.",
        "special_needs": "Suivi orthophonique en anglais, séances courtes.",
        "consent_rules": True,
        "consent_zoom": True,
        "consent_privacy": True,
        "consent_data_processing": True,
        "consent_photo_video": False,
        "consent_communications": True,
        "consent_payment_policy": True,
        "consent_annual_commitment": True,
        "consent_parental_authorization": True,
    }
    data.update(overrides)
    return data


class EnrollmentBaseTests(TestCase):
    """Socle commun : les deux académies et leurs administrateurs."""

    @classmethod
    def setUpTestData(cls):
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
                          currency_code="USD", matricule_prefix="FHA"),
        )
        cls.fha_admin = User.objects.create_user(
            username="admin.fha", email="admin.fha@test", password="x",
            role="admin", school=cls.fha,
        )
        cls.feba_admin = User.objects.create_user(
            username="admin.feba", email="admin.feba@test", password="x",
            role="admin", school=cls.feba,
        )
        cls.superadmin = User.objects.create_user(
            username="super", email="super@test", password="x",
            role="superadmin", school=cls.feba,
        )

    def submit(self, **overrides):
        client = APIClient()
        return client.post("/api/website/fha/enroll/", payload(**overrides),
                           format="json")


class SubmissionTests(EnrollmentBaseTests):
    """Étapes 1 à 8 — validation, atomicité, numérotation, stockage."""

    def test_1_la_soumission_est_acceptee(self):
        response = self.submit()
        self.assertEqual(response.status_code, 201, response.data)

    def test_2_le_numero_de_dossier_suit_le_format_attendu(self):
        response = self.submit()
        reference = response.data["reference"]
        self.assertRegex(reference, r"^FHA-\d{4}-\d{4}$")

    def test_3_les_numeros_sont_uniques_et_se_suivent(self):
        first = self.submit().data["reference"]
        second = self.submit(child_first_name="Ana", parent1_email="a@b.test",
                             child_last_name="Ba").data["reference"]
        self.assertNotEqual(first, second)
        self.assertEqual(int(second.rsplit("-", 1)[1]),
                         int(first.rsplit("-", 1)[1]) + 1)

    def test_4_un_double_clic_ne_cree_pas_deux_dossiers(self):
        """Deux soumissions identiques : la seconde est refusée, pas dupliquée."""
        self.assertEqual(self.submit().status_code, 201)
        second = self.submit()
        self.assertEqual(second.status_code, 400)
        self.assertIn("duplicate", second.data)
        self.assertEqual(FHAEnrollmentApplication.objects.count(), 1)

    def test_5_l_academie_est_imposee_par_la_route(self):
        """Un « entity » envoyé par le navigateur est ignoré."""
        response = self.submit(entity=self.feba.pk)
        application = FHAEnrollmentApplication.objects.get(
            reference=response.data["reference"])
        self.assertEqual(application.entity, self.fha)

    def test_6_tous_les_champs_saisis_sont_enregistres(self):
        """
        Le test central de P2, appliqué à l'inscription : CHAQUE clé
        envoyée doit se retrouver en base avec sa valeur.
        """
        sent = payload()
        response = self.submit()
        application = FHAEnrollmentApplication.objects.get(
            reference=response.data["reference"])

        for field, expected in sent.items():
            with self.subTest(champ=field):
                actual = getattr(application, field)
                if field == "child_birth_date":
                    expected = datetime.date.fromisoformat(expected)
                self.assertEqual(
                    actual, expected,
                    f"« {field} » : envoyé {expected!r}, enregistré {actual!r}.",
                )

    def test_7_les_consentements_sont_dates(self):
        response = self.submit()
        application = FHAEnrollmentApplication.objects.get(
            reference=response.data["reference"])
        self.assertIsNotNone(application.consents_accepted_at)
        self.assertTrue(application.consents_version)

    def test_8_l_etat_initial_est_consigne_dans_l_historique(self):
        response = self.submit()
        application = FHAEnrollmentApplication.objects.get(
            reference=response.data["reference"])
        history = FHAApplicationStatusHistory.objects.filter(application=application)
        self.assertEqual(history.count(), 1)
        self.assertEqual(history.first().to_status,
                         FHAEnrollmentApplication.STATUS_FORM_RECEIVED)

    def test_9_le_groupe_suggere_est_calcule_et_non_saisi(self):
        response = self.submit()
        self.assertIn(response.data["suggested_group"],
                      {"junior_roots", "french_explorers", "french_ambassadors"})

    def test_10_une_fiche_invalide_n_ecrit_rien(self):
        """Atomicité : consentement manquant → aucun dossier, aucun historique."""
        response = self.submit(consent_parental_authorization=False)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(FHAEnrollmentApplication.objects.count(), 0)
        self.assertEqual(FHAApplicationStatusHistory.objects.count(), 0)


class SheetTests(EnrollmentBaseTests):
    """Étapes 9 à 12 — la fiche PDF, produite et rangée en privé."""

    def setUp(self):
        self.response = self.submit()
        self.application = FHAEnrollmentApplication.objects.get(
            reference=self.response.data["reference"])

    def test_la_fiche_est_produite_a_la_soumission(self):
        self.assertTrue(
            self.application.has_sheet,
            "Aucune fiche PDF n'a été produite : l'administration n'a rien à ouvrir.",
        )
        self.assertTrue(self.response.data["sheet_generated"])

    def test_la_fiche_porte_une_empreinte_et_une_taille(self):
        self.assertEqual(len(self.application.sheet_sha256), 64)
        self.assertGreater(self.application.sheet_size, 3000)

    def test_la_fiche_est_hors_du_stockage_public(self):
        """
        Une fiche contient l'adresse et les besoins d'un mineur : elle ne
        doit pas se trouver sous MEDIA_ROOT, que le serveur web publie.
        """
        from django.conf import settings

        path = os.path.abspath(self.application.sheet_absolute_path)
        media = os.path.abspath(str(settings.MEDIA_ROOT))
        self.assertFalse(
            path.startswith(media + os.sep),
            f"La fiche est dans le stockage public ({path}).",
        )

    def test_la_fiche_contient_toutes_les_sections(self):
        import fitz

        with open(self.application.sheet_absolute_path, "rb") as handle:
            document = fitz.open(stream=handle.read(), filetype="pdf")
        text = "\n".join(page.get_text() for page in document)

        from apps.website.fha_pdf import build_sections

        for title, _rows in build_sections(self.application):
            with self.subTest(section=title):
                self.assertIn(title.upper(), text.upper())

    def test_la_fiche_contient_les_donnees_sensibles_saisies(self):
        import fitz

        with open(self.application.sheet_absolute_path, "rb") as handle:
            document = fitz.open(stream=handle.read(), filetype="pdf")
        text = "\n".join(page.get_text() for page in document)

        for expected in ("+1 215 555 0199",          # WhatsApp responsable 1
                         "Suivi orthophonique",       # besoins particuliers
                         "America/New_York",          # fuseau
                         "4200 Pine Street",          # adresse
                         "Marie Dossou"):             # contact d'urgence
            with self.subTest(valeur=expected):
                self.assertIn(expected, text)

    def test_la_fiche_porte_l_identite_de_l_academie_en_ligne(self):
        import fitz

        with open(self.application.sheet_absolute_path, "rb") as handle:
            document = fitz.open(stream=handle.read(), filetype="pdf")
        text = "\n".join(page.get_text() for page in document)

        self.assertIn("FEBA French Heritage Academy", text)
        self.assertNotIn("Faith & Excellence", text)

    def test_le_nom_de_fichier_est_stable_et_deductible(self):
        from apps.website.fha_pdf import sheet_filename

        self.assertEqual(
            sheet_filename(self.application),
            f"{self.application.reference}-fiche-inscription.pdf",
        )

    def test_une_regeneration_conserve_l_ancienne_version(self):
        from apps.website.fha_enrollment import generate_and_store_sheet

        first_path = self.application.sheet_absolute_path
        generate_and_store_sheet(self.application)
        self.application.refresh_from_db()
        self.assertNotEqual(self.application.sheet_absolute_path, first_path)
        self.assertTrue(
            os.path.exists(first_path),
            "L'ancienne version a été écrasée : une copie a peut-être déjà "
            "été envoyée par e-mail.",
        )


class EmailTests(EnrollmentBaseTests):
    """Étapes 13 à 16 — l'e-mail, ses états explicites et sa relance."""

    def test_un_accuse_de_reception_est_envoye_au_parent(self):
        self.submit()
        recipients = [address for message in mail.outbox for address in message.to]
        self.assertIn("ahouefa@example.test", recipients)

    def test_l_accuse_porte_la_fiche_en_piece_jointe(self):
        response = self.submit()
        reference = response.data["reference"]
        parent_mail = next(m for m in mail.outbox
                           if "ahouefa@example.test" in m.to)
        names = [name for name, _content, _mime in parent_mail.attachments]
        self.assertIn(f"{reference}-fiche-inscription.pdf", names)

    def test_l_accuse_existe_en_texte_et_en_html(self):
        self.submit()
        parent_mail = next(m for m in mail.outbox
                           if "ahouefa@example.test" in m.to)
        self.assertTrue(parent_mail.body.strip())
        types = [mimetype for _content, mimetype in parent_mail.alternatives]
        self.assertIn("text/html", types)

    def test_l_accuse_suit_la_langue_declaree_par_le_parent(self):
        self.submit()   # parent1_preferred_language = "fr"
        french = next(m for m in mail.outbox if "ahouefa@example.test" in m.to)
        self.assertIn("Bonjour", french.body)

        mail.outbox.clear()
        self.submit(parent1_email="english@example.test",
                    parent1_preferred_language="en",
                    child_first_name="Ana", child_last_name="Ba")
        english = next(m for m in mail.outbox if "english@example.test" in m.to)
        self.assertIn("Hello", english.body)

    def test_chaque_envoi_laisse_une_ligne_de_journal(self):
        response = self.submit()
        reference = response.data["reference"]
        deliveries = EmailDelivery.objects.filter(subject_reference=reference)
        self.assertGreaterEqual(deliveries.count(), 2)
        self.assertTrue(
            deliveries.filter(purpose="fha_enrollment_ack").exists())
        self.assertTrue(
            deliveries.filter(purpose="fha_enrollment_admin_alert").exists())

    def test_l_envoi_porte_un_identifiant_de_suivi(self):
        response = self.submit()
        self.assertTrue(response.data["email"]["tracking_id"])
        parent_mail = next(m for m in mail.outbox
                           if "ahouefa@example.test" in m.to)
        self.assertIn("X-FEBA-Tracking-Id", parent_mail.extra_headers)

    def test_les_admins_de_l_academie_et_les_super_admins_sont_prevenus(self):
        self.submit()
        recipients = {address for message in mail.outbox for address in message.to}
        self.assertIn("admin.fha@test", recipients)
        self.assertIn("super@test", recipients)
        self.assertNotIn(
            "admin.feba@test", recipients,
            "L'administrateur de l'autre académie a été prévenu d'un dossier "
            "qui ne le concerne pas.",
        )

    def test_une_notification_interne_est_creee(self):
        from apps.notifications.models import Notification

        response = self.submit()
        reference = response.data["reference"]
        self.assertTrue(
            Notification.objects.filter(
                user=self.fha_admin, title__contains=reference).exists())

    @override_settings(EMAIL_BACKEND="tests.test_fha_enrollment_workflow.BrokenBackend")
    def test_un_echec_d_envoi_ne_fait_pas_perdre_l_inscription(self):
        """
        Le point le plus important de P1.

        `fail_silently=True` transformait un serveur injoignable en succès
        muet. Maintenant l'échec est visible — et l'inscription, elle,
        reste enregistrée.
        """
        response = self.submit()
        self.assertEqual(response.status_code, 201)
        self.assertEqual(FHAEnrollmentApplication.objects.count(), 1)

        self.assertFalse(response.data["email"]["accepted"])
        self.assertIn(response.data["email"]["status"],
                      {EmailDelivery.RETRY, EmailDelivery.FAILED})

    @override_settings(EMAIL_BACKEND="tests.test_fha_enrollment_workflow.BrokenBackend")
    def test_l_ecran_public_ne_promet_pas_un_e_mail_qui_n_est_pas_parti(self):
        response = self.submit()
        self.assertNotIn("Un e-mail de confirmation vient de vous être envoyé",
                         response.data["detail"])
        self.assertIn("n'a pas pu être effectué", response.data["detail"])
        # Le numéro de dossier, lui, est acquis : il doit être mis en avant.
        self.assertIn(response.data["reference"], response.data["detail"])

    @override_settings(EMAIL_BACKEND="tests.test_fha_enrollment_workflow.BrokenBackend")
    def test_l_erreur_exacte_du_fournisseur_est_conservee(self):
        response = self.submit()
        delivery = EmailDelivery.objects.get(
            purpose="fha_enrollment_ack",
            subject_reference=response.data["reference"])
        self.assertIn("BrokenBackend", delivery.last_error)

    def test_l_ecran_annonce_l_e_mail_quand_il_est_bien_parti(self):
        response = self.submit()
        self.assertTrue(response.data["email"]["accepted"])
        self.assertIn("ahouefa@example.test", response.data["detail"])


class AdminActionsTests(EnrollmentBaseTests):
    """Étapes 17 et 18 — ce que l'administration peut faire du dossier."""

    def setUp(self):
        self.response = self.submit()
        self.application = FHAEnrollmentApplication.objects.get(
            reference=self.response.data["reference"])
        self.client_fha = APIClient()
        self.client_fha.force_authenticate(user=self.fha_admin)
        self.client_feba = APIClient()
        self.client_feba.force_authenticate(user=self.feba_admin)

    def test_l_admin_fha_telecharge_la_fiche(self):
        response = self.client_fha.get(
            f"/api/website/admin/fha-applications/{self.application.pk}/sheet/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertIn(f"{self.application.reference}-fiche-inscription.pdf",
                      response["Content-Disposition"])

    def test_la_fiche_n_est_pas_mise_en_cache_partage(self):
        response = self.client_fha.get(
            f"/api/website/admin/fha-applications/{self.application.pk}/sheet/")
        self.assertIn("no-store", response["Cache-Control"])

    def test_un_admin_de_l_autre_academie_ne_peut_pas_telecharger(self):
        """Anti-IDOR : deviner l'identifiant ne donne rien."""
        response = self.client_feba.get(
            f"/api/website/admin/fha-applications/{self.application.pk}/sheet/")
        self.assertEqual(response.status_code, 404)

    def test_un_visiteur_non_authentifie_ne_peut_pas_telecharger(self):
        response = APIClient().get(
            f"/api/website/admin/fha-applications/{self.application.pk}/sheet/")
        self.assertIn(response.status_code, (401, 403))

    def test_la_liste_indique_l_etat_de_l_e_mail_et_de_la_fiche(self):
        response = self.client_fha.get("/api/website/admin/fha-applications/")
        rows = response.data.get("results", response.data)
        row = next(r for r in rows if r["reference"] == self.application.reference)
        self.assertTrue(row["has_sheet"])
        self.assertIn("status", row["confirmation_email"])
        self.assertEqual(row["entity_code"], School.CODE_FEBA_FHA)

    def test_le_detail_expose_tous_les_champs_saisis(self):
        response = self.client_fha.get(
            f"/api/website/admin/fha-applications/{self.application.pk}/")
        data = response.data
        for field in ("parent1_whatsapp", "parent2_whatsapp", "special_needs",
                      "emergency_phone", "available_time_slots",
                      "family_timezone", "equipment_notes",
                      "consent_photo_video", "parent1_address"):
            with self.subTest(champ=field):
                self.assertIn(field, data)
        self.assertEqual(data["parent1_whatsapp"], "+1 215 555 0199")

    def test_le_detail_traduit_les_codes_en_libelles(self):
        response = self.client_fha.get(
            f"/api/website/admin/fha-applications/{self.application.pk}/")
        labels = response.data["labels"]
        self.assertIn("Comprend quelques mots", labels["french_levels"])
        self.assertIn("Mercredi", labels["available_days"])

    def test_l_administration_peut_relancer_l_accuse_de_reception(self):
        mail.outbox.clear()
        response = self.client_fha.post(
            f"/api/website/admin/fha-applications/{self.application.pk}"
            f"/resend-confirmation/")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertTrue(response.data["accepted"])
        self.assertIn("ahouefa@example.test",
                      [a for m in mail.outbox for a in m.to])

    def test_l_administration_peut_regenerer_la_fiche(self):
        response = self.client_fha.post(
            f"/api/website/admin/fha-applications/{self.application.pk}"
            f"/regenerate-sheet/")
        self.assertEqual(response.status_code, 200, response.data)
        self.application.refresh_from_db()
        self.assertEqual(self.application.sheet_version, 2)


class ExportTests(EnrollmentBaseTests):
    """L'export CSV est complet et ne fuit pas d'une académie à l'autre."""

    def setUp(self):
        self.response = self.submit()
        self.application = FHAEnrollmentApplication.objects.get(
            reference=self.response.data["reference"])

    def _csv(self, user):
        client = APIClient()
        client.force_authenticate(user=user)
        response = client.get("/api/website/admin/fha-applications/export/")
        self.assertEqual(response.status_code, 200)
        return response.content.decode("utf-8")

    def test_l_export_contient_toutes_les_colonnes_du_modele(self):
        content = self._csv(self.fha_admin)
        header = content.splitlines()[0]
        skipped = {"id", "entity", "child_photo", "submitted_ip",
                   "sheet_path", "sheet_sha256"}
        for field in FHAEnrollmentApplication._meta.fields:
            if field.name in skipped:
                continue
            with self.subTest(colonne=field.name):
                label = (field.verbose_name if field.verbose_name != field.name
                         else field.name)
                self.assertIn(str(label), header)

    def test_l_export_contient_les_valeurs_saisies(self):
        content = self._csv(self.fha_admin)
        for expected in ("+1 215 555 0199", "Suivi orthophonique",
                         "America/New_York", "4200 Pine Street"):
            with self.subTest(valeur=expected):
                self.assertIn(expected, content)

    def test_l_export_d_un_admin_feba_ne_contient_aucun_dossier_fha(self):
        content = self._csv(self.feba_admin)
        self.assertNotIn(self.application.reference, content)
        self.assertNotIn("ahouefa@example.test", content)

    def test_l_export_commence_par_un_bom_utf8(self):
        content = self._csv(self.fha_admin)
        self.assertTrue(content.startswith("﻿"))
        self.assertIn("Gbêdjissi", content)


class BrokenBackend:
    """
    Backend d'envoi qui échoue, pour éprouver le chemin d'erreur.

    Il lève au lieu d'avaler : c'est exactement ce que faisait un vrai
    serveur SMTP injoignable, et que `fail_silently=True` masquait.
    """

    def __init__(self, *args, **kwargs):
        pass

    def open(self):
        return True

    def close(self):
        return None

    def send_messages(self, messages):
        raise ConnectionRefusedError(
            "BrokenBackend : connexion refusée par le serveur d'envoi.")
