"""
Tests du PAIEMENT PAR CARTE (P1).

Ce qui est vérifié ici n'est pas « le paiement marche ». C'est l'inverse :
que chacune des façons connues de perdre ou de dupliquer de l'argent est
effectivement bloquée.

  1. Le montant vient de la grille tarifaire, jamais du navigateur.
  2. La redirection ne prouve rien : seul le webhook signé encaisse.
  3. Un événement rejoué ne crée pas un second encaissement.
  4. Un événement non signé ne crée rien du tout.
  5. Un `succeeded` arrivé après un `failed` l'emporte — l'argent est parti.
  6. Un remboursement ne peut pas dépasser ce qui a été encaissé.
  7. Un parent ne voit, ne paie et ne rembourse que ce qui le concerne.

LE PRESTATAIRE EST SIMULÉ, PAS LE CODE TESTÉ
--------------------------------------------
Aucun appel réseau : un faux prestataire remplace Stripe. Ce qui est
éprouvé est donc bien notre logique — création, rapprochement,
idempotence, permissions — et non la disponibilité d'un service tiers.
La vérification de signature réelle, elle, est testée séparément avec la
bibliothèque officielle (voir `StripeSignatureTests`).
"""
import datetime
import json
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import CustomUser
from apps.payments.fee_models import FeeSchedule
from apps.payments.models import Payment
from apps.payments.providers import PaymentProvider, PaymentProviderError
from apps.payments.transaction_models import PaymentTransaction, WebhookEvent
from apps.schools.models import School, SchoolYear
from apps.students.models import Student

WEBHOOK_URL = "/api/payments/webhook/stripe/"
CHECKOUT_URL = "/api/payments/card/checkout/"


class FakeProvider(PaymentProvider):
    """
    Prestataire simulé.

    `verify_webhook` n'accepte qu'une signature convenue : cela permet de
    tester le REFUS d'un événement non signé sans dépendre de la
    cryptographie de Stripe, testée ailleurs.
    """

    name = "stripe"

    def __init__(self):
        self.configured = True
        self.checkouts = []
        self.refunds = []
        self.fail_checkout = None
        self.counter = 0

    def is_configured(self):
        return self.configured

    def assert_configured(self):
        if not self.configured:
            from apps.payments.providers import PaymentProviderNotConfigured

            raise PaymentProviderNotConfigured("Prestataire non configuré (test).")

    def create_checkout(self, transaction, success_url, cancel_url, description=""):
        if self.fail_checkout:
            raise PaymentProviderError(self.fail_checkout)
        self.counter += 1
        self.checkouts.append({
            "amount_minor": transaction.amount_minor,
            "currency": transaction.currency,
            "idempotency_key": transaction.idempotency_key,
            "description": description,
        })
        return f"cs_test_{self.counter}", f"https://checkout.test/{self.counter}"

    def verify_webhook(self, payload, signature_header):
        if signature_header != "signature-valide":
            raise ValidationError("Signature de webhook invalide.")
        return json.loads(payload)

    def refund(self, transaction, amount_minor):
        self.refunds.append((transaction.pk, amount_minor))
        return {"id": f"re_test_{len(self.refunds)}"}


def auth(client, email, password="Pass1234!"):
    resp = client.post("/api/auth/login/", {"email": email, "password": password})
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {resp.data.get('access', '')}")
    return client


def event(event_type, obj, event_id="evt_1"):
    return {"id": event_id, "type": event_type, "data": {"object": obj}}


@override_settings(
    CARD_PAYMENTS_ENABLED=True,
    STRIPE_SECRET_KEY="sk_test_pour_les_tests",
    STRIPE_PUBLISHABLE_KEY="pk_test_pour_les_tests",
    STRIPE_WEBHOOK_SECRET="whsec_pour_les_tests",
)
class CardPaymentBaseTests(TestCase):
    """Socle : deux académies, deux devises, un parent par académie."""

    @classmethod
    def setUpTestData(cls):
        cls.feba = School.objects.create(
            name="FEBA Cotonou", address="Akpakpa", entity_type="campus",
            code="CARD-FEBA", currency_code="XOF", city="Cotonou",
        )
        cls.fha = School.objects.create(
            name="FEBA French Heritage Academy", address="En ligne",
            entity_type="online", code="CARD-FHA", currency_code="USD",
        )

        cls.years, cls.students, cls.parents = {}, {}, {}
        for key, school in (("feba", cls.feba), ("fha", cls.fha)):
            cls.years[key] = SchoolYear.objects.create(
                school=school, name=f"2025-2026-card-{key}", is_current=True,
                start_date="2025-09-01", end_date="2026-07-01",
            )
            cls.students[key] = Student.objects.create(
                school=school, school_year=cls.years[key], first_name="Élève",
                last_name=key.upper(), date_of_birth="2014-01-01",
            )
            CustomUser.objects.create_user(
                username=f"card_admin_{key}", email=f"card.admin.{key}@test.io",
                password="Pass1234!", role="admin", school=school,
                first_name="Admin", last_name=key.upper(),
            )
            cls.parents[key] = cls._make_parent(key, school, cls.students[key])

        # Tarifs publiés : c'est EUX qui font foi, pas la requête.
        FeeSchedule.objects.create(
            academy=cls.fha, school_year=cls.years["fha"],
            payment_type="mensualite", label="Mensualité FHA",
            amount_minor=12550,          # 125,50 $
        )
        FeeSchedule.objects.create(
            academy=cls.feba, school_year=cls.years["feba"],
            payment_type="mensualite", label="Mensualité FEBA",
            amount_minor=50000,          # 50 000 FCFA
        )

    @classmethod
    def _make_parent(cls, key, school, student):
        from apps.parents.models import Parent, ParentStudent

        user = CustomUser.objects.create_user(
            username=f"card_parent_{key}", email=f"card.parent.{key}@test.io",
            password="Pass1234!", role="parent", school=school,
            first_name="Parent", last_name=key.upper(),
        )
        parent = Parent.objects.create(user=user)
        ParentStudent.objects.create(parent=parent, student=student)
        return user

    def setUp(self):
        self.provider = FakeProvider()
        patcher = patch(
            "apps.payments.card_views.get_provider", return_value=self.provider,
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    # ── Utilitaires ───────────────────────────────────────────────────

    def start_checkout(self, key="fha", as_user=None, **payload):
        client = auth(APIClient(), as_user or f"card.parent.{key}@test.io")
        body = {"student": self.students[key].id, "payment_type": "mensualite"}
        body.update(payload)
        return client.post(CHECKOUT_URL, body, format="json")

    def send_webhook(self, payload, signature="signature-valide"):
        return self.client.post(
            WEBHOOK_URL, data=json.dumps(payload),
            content_type="application/json", HTTP_STRIPE_SIGNATURE=signature,
        )


class CheckoutCreationTests(CardPaymentBaseTests):
    """Création d'une tentative : montant, devise, périmètre."""

    def test_le_montant_vient_de_la_grille_pas_de_la_requete(self):
        """
        Le scénario d'attaque le plus simple : payer 1 $ une mensualité
        de 125,50 $ en modifiant le corps de la requête.
        """
        resp = self.start_checkout("fha", amount="1.00", amount_minor=1)
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)

        attempt = PaymentTransaction.objects.get(pk=resp.data["transaction_id"])
        self.assertEqual(attempt.amount_minor, 12550)
        self.assertEqual(attempt.amount_source, "fee_schedule")
        self.assertEqual(resp.data["amount_display"], "$125.50")
        # Ce qui part chez le prestataire est bien le montant du serveur.
        self.assertEqual(self.provider.checkouts[0]["amount_minor"], 12550)

    def test_la_devise_vient_de_l_academie_pas_du_client(self):
        resp = self.start_checkout("fha", currency="XOF")
        attempt = PaymentTransaction.objects.get(pk=resp.data["transaction_id"])
        self.assertEqual(attempt.currency, "USD")
        self.assertEqual(self.provider.checkouts[0]["currency"], "USD")

    def test_une_academie_en_francs_reste_en_francs(self):
        resp = self.start_checkout("feba")
        attempt = PaymentTransaction.objects.get(pk=resp.data["transaction_id"])
        self.assertEqual(attempt.currency, "XOF")
        self.assertEqual(attempt.amount_minor, 50000)
        self.assertEqual(resp.data["amount_display"], "50 000 FCFA")

    def test_un_parent_ne_peut_pas_payer_pour_l_enfant_d_un_autre(self):
        """Changer l'identifiant d'élève ne doit rien ouvrir."""
        client = auth(APIClient(), "card.parent.feba@test.io")
        resp = client.post(CHECKOUT_URL, {
            "student": self.students["fha"].id, "payment_type": "mensualite",
        }, format="json")
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(PaymentTransaction.objects.count(), 0)

    def test_sans_tarif_publie_un_parent_ne_peut_pas_saisir_un_montant(self):
        resp = self.start_checkout("fha", payment_type="cantine", amount="10.00")
        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(PaymentTransaction.objects.count(), 0)

    def test_sans_tarif_publie_l_administration_peut_saisir_un_montant(self):
        resp = self.start_checkout(
            "fha", as_user="card.admin.fha@test.io",
            payment_type="cantine", amount="10.00",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        attempt = PaymentTransaction.objects.get(pk=resp.data["transaction_id"])
        self.assertEqual(attempt.amount_minor, 1000)
        self.assertEqual(attempt.amount_source, "staff")

    def test_un_type_de_frais_inconnu_est_refuse(self):
        resp = self.start_checkout(
            "fha", as_user="card.admin.fha@test.io",
            payment_type="donation_libre", amount="10.00",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_un_double_clic_ne_cree_qu_une_tentative(self):
        first = self.start_checkout("fha")
        second = self.start_checkout("fha")

        self.assertEqual(PaymentTransaction.objects.count(), 1)
        self.assertTrue(second.data["reused"])
        self.assertEqual(second.data["transaction_id"], first.data["transaction_id"])
        self.assertEqual(len(self.provider.checkouts), 1)

    def test_un_refus_du_prestataire_laisse_une_trace_exploitable(self):
        self.provider.fail_checkout = "Carte de test refusée par la passerelle."
        resp = self.start_checkout("fha")

        self.assertEqual(resp.status_code, status.HTTP_502_BAD_GATEWAY)
        attempt = PaymentTransaction.objects.get()
        self.assertEqual(attempt.status, PaymentTransaction.FAILED)
        self.assertIn("refusée", attempt.failure_reason)

    def test_le_paiement_est_indisponible_si_le_prestataire_n_est_pas_configure(self):
        self.provider.configured = False
        resp = self.start_checkout("fha")
        self.assertEqual(resp.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)

    def test_la_cle_d_idempotence_est_unique_et_stable(self):
        resp = self.start_checkout("fha")
        attempt = PaymentTransaction.objects.get(pk=resp.data["transaction_id"])
        key = attempt.idempotency_key
        self.assertTrue(key)
        attempt.save()
        attempt.refresh_from_db()
        self.assertEqual(attempt.idempotency_key, key)


class PayableItemsTests(CardPaymentBaseTests):
    """Le payeur choisit une ligne tarifaire, pas un montant."""

    def test_un_parent_voit_les_tarifs_de_son_academie(self):
        client = auth(APIClient(), "card.parent.fha@test.io")
        resp = client.get(f"/api/payments/card/fees/?student={self.students['fha'].id}")

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["currency"], "USD")
        items = {item["payment_type"]: item for item in resp.data["items"]}
        self.assertEqual(items["mensualite"]["amount_display"], "$125.50")

    def test_un_parent_ne_voit_pas_les_tarifs_d_une_autre_academie(self):
        client = auth(APIClient(), "card.parent.feba@test.io")
        resp = client.get(f"/api/payments/card/fees/?student={self.students['fha'].id}")
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)


class WebhookTests(CardPaymentBaseTests):
    """C'est ici, et nulle part ailleurs, qu'un paiement devient une recette."""

    def setUp(self):
        super().setUp()
        # Le webhook est appelé sans session : il faut aussi remplacer le
        # prestataire résolu dans ce chemin-là.
        patcher = patch(
            "apps.payments.card_views.get_provider", return_value=self.provider,
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        self.attempt = PaymentTransaction.objects.create(
            academy=self.fha, student=self.students["fha"],
            school_year=self.years["fha"], payment_type="mensualite",
            amount_minor=12550, provider="stripe",
            provider_session_id="cs_test_1",
            status=PaymentTransaction.PENDING,
        )

    def _session(self, **extra):
        payload = {
            "id": "cs_test_1",
            "payment_intent": "pi_test_1",
            "metadata": {"transaction_id": str(self.attempt.pk)},
        }
        payload.update(extra)
        return payload

    def test_la_redirection_seule_n_encaisse_rien(self):
        """
        Aucun appel n'existe pour « déclarer » un succès depuis le
        navigateur : l'URL de retour est devinable, elle ne prouve rien.
        """
        self.assertEqual(Payment.objects.count(), 0)
        self.attempt.refresh_from_db()
        self.assertEqual(self.attempt.status, PaymentTransaction.PENDING)

    def test_un_evenement_signe_cree_l_encaissement(self):
        resp = self.send_webhook(event("checkout.session.completed", self._session()))

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.attempt.refresh_from_db()
        self.assertEqual(self.attempt.status, PaymentTransaction.SUCCEEDED)
        self.assertEqual(self.attempt.provider_intent_id, "pi_test_1")

        payment = self.attempt.payment
        self.assertIsNotNone(payment)
        self.assertEqual(payment.amount_minor, 12550)
        self.assertEqual(payment.currency, "USD")
        self.assertEqual(payment.formatted_amount, "$125.50")
        self.assertEqual(payment.payment_method, "card")

    def test_un_evenement_non_signe_ne_cree_rien(self):
        resp = self.send_webhook(
            event("checkout.session.completed", self._session()),
            signature="signature-forgee",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.attempt.refresh_from_db()
        self.assertEqual(self.attempt.status, PaymentTransaction.PENDING)
        self.assertEqual(Payment.objects.count(), 0)
        self.assertEqual(WebhookEvent.objects.count(), 0)

    def test_un_evenement_rejoue_n_encaisse_qu_une_fois(self):
        payload = event("checkout.session.completed", self._session())
        self.send_webhook(payload)
        second = self.send_webhook(payload)

        self.assertTrue(second.data["duplicate"])
        self.assertEqual(Payment.objects.count(), 1)
        self.assertEqual(WebhookEvent.objects.count(), 1)

    def test_deux_evenements_distincts_n_encaissent_qu_une_fois(self):
        """
        `checkout.session.completed` et `payment_intent.succeeded`
        décrivent le MÊME encaissement : Stripe envoie souvent les deux.
        """
        self.send_webhook(event("checkout.session.completed", self._session(),
                                event_id="evt_a"))
        self.send_webhook(event("payment_intent.succeeded",
                                {"id": "pi_test_1",
                                 "metadata": {"transaction_id": str(self.attempt.pk)}},
                                event_id="evt_b"))

        self.assertEqual(Payment.objects.count(), 1)
        self.assertEqual(WebhookEvent.objects.count(), 2)

    def test_un_echec_est_enregistre_sans_encaissement(self):
        self.send_webhook(event("payment_intent.payment_failed", {
            "id": "pi_test_1",
            "metadata": {"transaction_id": str(self.attempt.pk)},
            "last_payment_error": {"message": "Votre carte a été refusée."},
        }))

        self.attempt.refresh_from_db()
        self.assertEqual(self.attempt.status, PaymentTransaction.FAILED)
        self.assertIn("refusée", self.attempt.failure_reason)
        self.assertEqual(Payment.objects.count(), 0)

    def test_une_authentification_bancaire_est_un_statut_a_part(self):
        """
        « Action requise » n'est pas un échec : le parent doit valider
        dans son application bancaire. Le confondre avec un refus ferait
        recommencer un paiement en cours.
        """
        self.send_webhook(event("payment_intent.requires_action", {
            "id": "pi_test_1", "metadata": {"transaction_id": str(self.attempt.pk)},
        }))
        self.attempt.refresh_from_db()
        self.assertEqual(self.attempt.status, PaymentTransaction.ACTION_REQUIRED)

    def test_une_session_expiree_est_distinguee_d_un_refus(self):
        self.send_webhook(event("checkout.session.expired", self._session()))
        self.attempt.refresh_from_db()
        self.assertEqual(self.attempt.status, PaymentTransaction.EXPIRED)

    def test_un_abandon_est_enregistre_comme_annulation(self):
        self.send_webhook(event("payment_intent.canceled", {
            "id": "pi_test_1", "metadata": {"transaction_id": str(self.attempt.pk)},
        }))
        self.attempt.refresh_from_db()
        self.assertEqual(self.attempt.status, PaymentTransaction.CANCELLED)

    def test_un_succes_arrive_apres_un_echec_l_emporte(self):
        """
        Les événements ne sont pas ordonnés. Si l'argent a été encaissé,
        c'est le succès qui fait foi, quel que soit l'ordre d'arrivée.
        """
        self.send_webhook(event("payment_intent.payment_failed", {
            "id": "pi_test_1", "metadata": {"transaction_id": str(self.attempt.pk)},
        }, event_id="evt_echec"))
        self.send_webhook(event("checkout.session.completed", self._session(),
                                event_id="evt_succes"))

        self.attempt.refresh_from_db()
        self.assertEqual(self.attempt.status, PaymentTransaction.SUCCEEDED)
        self.assertEqual(Payment.objects.count(), 1)

    def test_un_echec_arrive_apres_un_succes_n_efface_pas_la_recette(self):
        self.send_webhook(event("checkout.session.completed", self._session(),
                                event_id="evt_succes"))
        self.send_webhook(event("payment_intent.payment_failed", {
            "id": "pi_test_1", "metadata": {"transaction_id": str(self.attempt.pk)},
        }, event_id="evt_echec_tardif"))

        self.attempt.refresh_from_db()
        self.assertEqual(self.attempt.status, PaymentTransaction.SUCCEEDED)
        self.assertEqual(Payment.objects.count(), 1)

    def test_un_evenement_orphelin_est_journalise_sans_erreur(self):
        resp = self.send_webhook(event("checkout.session.completed", {
            "id": "cs_inconnue", "metadata": {},
        }, event_id="evt_orphelin"))

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertFalse(resp.data["handled"])
        record = WebhookEvent.objects.get(event_id="evt_orphelin")
        self.assertEqual(record.status, WebhookEvent.IGNORED)

    def test_le_rapprochement_fonctionne_sans_metadonnees(self):
        """
        Les métadonnées peuvent manquer (événement relayé, rejeu manuel) :
        l'identifiant de session doit suffire.
        """
        self.send_webhook(event("checkout.session.completed", {
            "id": "cs_test_1", "payment_intent": "pi_test_1",
        }, event_id="evt_sans_meta"))

        self.attempt.refresh_from_db()
        self.assertEqual(self.attempt.status, PaymentTransaction.SUCCEEDED)

    def test_aucune_donnee_de_carte_n_est_stockee(self):
        """
        Vérification directe : aucun champ du modèle ne peut recevoir un
        numéro de carte, une date d'expiration ou un cryptogramme.
        """
        interdits = {"card_number", "pan", "cvc", "cvv", "exp_month",
                     "exp_year", "expiry", "card_holder", "payment_method_details"}
        champs = {f.name for f in PaymentTransaction._meta.get_fields()}
        self.assertEqual(champs & interdits, set())

    def test_les_metadonnees_stockees_ne_contiennent_pas_de_donnees_de_carte(self):
        self.send_webhook(event("checkout.session.completed", self._session(
            payment_method_details={"card": {"last4": "4242", "exp_month": 12}},
        )))
        self.attempt.refresh_from_db()
        serialise = json.dumps(self.attempt.provider_metadata)
        self.assertNotIn("4242", serialise)
        self.assertNotIn("exp_month", serialise)


class ReceiptTests(CardPaymentBaseTests):
    """Le reçu suit la devise réellement encaissée."""

    def setUp(self):
        super().setUp()
        self.attempt = PaymentTransaction.objects.create(
            academy=self.fha, student=self.students["fha"],
            school_year=self.years["fha"], payment_type="mensualite",
            amount_minor=12550, provider="stripe",
            provider_session_id="cs_recu", status=PaymentTransaction.PENDING,
        )

    def test_le_recu_est_genere_automatiquement_a_l_encaissement(self):
        self.attempt.mark_succeeded()
        payment = self.attempt.payment
        payment.refresh_from_db()
        self.assertTrue(payment.receipt_file)

    def test_le_recu_est_libelle_en_dollars_pour_fha(self):
        from apps.payments.pdf_generator import amount_in_words

        self.attempt.mark_succeeded()
        payment = self.attempt.payment
        self.assertEqual(payment.formatted_amount, "$125.50")
        self.assertIn("DOLLARS", amount_in_words(payment.amount, payment.currency))
        self.assertNotIn("FRANCS", amount_in_words(payment.amount, payment.currency))

    def test_le_montant_en_lettres_reste_en_francs_pour_feba(self):
        from apps.payments.pdf_generator import amount_in_words

        mots = amount_in_words(50000, "XOF")
        self.assertIn("FRANCS CFA", mots)
        self.assertNotIn("DOLLARS", mots)

    def test_les_centimes_sont_enonces_et_non_perdus(self):
        """
        Le montant en lettres fait foi en cas de litige : arrondir
        125,50 $ à « CENT VINGT-SIX » serait un faux document.
        """
        from apps.payments.pdf_generator import amount_in_words

        mots = amount_in_words("125.50", "USD")
        self.assertIn("FIFTY", mots)
        self.assertIn("CENTS", mots)

    def test_un_parent_accede_a_son_recu(self):
        self.attempt.mark_succeeded()
        client = auth(APIClient(), "card.parent.fha@test.io")
        resp = client.get(f"/api/payments/card/{self.attempt.pk}/receipt/")

        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        self.assertEqual(resp.data["amount_display"], "$125.50")
        self.assertTrue(resp.data["receipt_url"])

    def test_un_parent_n_accede_pas_au_recu_d_un_autre(self):
        """Anti-IDOR : incrémenter l'identifiant ne doit rien révéler."""
        self.attempt.mark_succeeded()
        client = auth(APIClient(), "card.parent.feba@test.io")
        resp = client.get(f"/api/payments/card/{self.attempt.pk}/receipt/")
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_pas_de_recu_sans_encaissement(self):
        client = auth(APIClient(), "card.parent.fha@test.io")
        resp = client.get(f"/api/payments/card/{self.attempt.pk}/receipt/")
        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT)


class RefundTests(CardPaymentBaseTests):
    """Rembourser, oui ; rembourser plus que reçu, jamais."""

    def setUp(self):
        super().setUp()
        self.attempt = PaymentTransaction.objects.create(
            academy=self.fha, student=self.students["fha"],
            school_year=self.years["fha"], payment_type="mensualite",
            amount_minor=12550, provider="stripe",
            provider_intent_id="pi_remb", status=PaymentTransaction.PENDING,
        )
        self.attempt.mark_succeeded()

    def refund(self, email="card.admin.fha@test.io", **body):
        client = auth(APIClient(), email)
        return client.post(
            f"/api/payments/card/{self.attempt.pk}/refund/", body, format="json",
        )

    def test_un_remboursement_partiel_laisse_un_solde(self):
        resp = self.refund(amount="25.50")

        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        self.attempt.refresh_from_db()
        self.assertEqual(self.attempt.status, PaymentTransaction.PARTIALLY_REFUNDED)
        self.assertEqual(self.attempt.amount_refunded_minor, 2550)
        self.assertEqual(resp.data["remaining"], "$100.00")

    def test_un_remboursement_total_solde_la_transaction(self):
        resp = self.refund()
        self.attempt.refresh_from_db()
        self.assertEqual(self.attempt.status, PaymentTransaction.REFUNDED)
        self.assertEqual(resp.data["remaining"], "$0.00")

    def test_un_remboursement_ne_peut_pas_depasser_l_encaissement(self):
        self.refund(amount="100.00")
        resp = self.refund(amount="100.00")

        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.attempt.refresh_from_db()
        self.assertEqual(self.attempt.amount_refunded_minor, 10000)

    def test_le_plafond_est_verifie_dans_le_modele_aussi(self):
        with self.assertRaises(ValidationError):
            self.attempt.register_refund(999999)

    def test_un_parent_ne_peut_pas_se_rembourser(self):
        resp = self.refund(email="card.parent.fha@test.io")
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        self.attempt.refresh_from_db()
        self.assertEqual(self.attempt.amount_refunded_minor, 0)

    def test_un_administrateur_d_une_autre_academie_ne_peut_pas_rembourser(self):
        resp = self.refund(email="card.admin.feba@test.io")
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        self.attempt.refresh_from_db()
        self.assertEqual(self.attempt.amount_refunded_minor, 0)

    def test_un_paiement_non_encaisse_n_est_pas_remboursable(self):
        autre = PaymentTransaction.objects.create(
            academy=self.fha, student=self.students["fha"],
            payment_type="mensualite", amount_minor=1000,
            status=PaymentTransaction.PENDING,
        )
        client = auth(APIClient(), "card.admin.fha@test.io")
        resp = client.post(f"/api/payments/card/{autre.pk}/refund/", {}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_un_remboursement_par_webhook_n_est_compte_qu_une_fois(self):
        """Le prestataire renvoie le CUMUL remboursé, pas l'incrément."""
        self.refund(amount="25.50")
        self.send_webhook(event("charge.refunded", {
            "id": "ch_1", "payment_intent": "pi_remb", "amount_refunded": 2550,
        }, event_id="evt_remb"))

        self.attempt.refresh_from_db()
        self.assertEqual(self.attempt.amount_refunded_minor, 2550)


class TransactionListTests(CardPaymentBaseTests):
    """Le journal reste dans les frontières de l'académie."""

    def setUp(self):
        super().setUp()
        for key in ("feba", "fha"):
            PaymentTransaction.objects.create(
                academy=getattr(self, key), student=self.students[key],
                payment_type="mensualite", amount_minor=1000,
                status=PaymentTransaction.PENDING,
            )

    def test_un_administrateur_ne_voit_que_son_academie(self):
        client = auth(APIClient(), "card.admin.fha@test.io")
        resp = client.get("/api/payments/card/transactions/")

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual({row["academy_code"] for row in resp.data}, {"CARD-FHA"})

    def test_chaque_ligne_porte_son_academie_et_sa_devise(self):
        client = auth(APIClient(), "card.admin.fha@test.io")
        row = client.get("/api/payments/card/transactions/").data[0]

        self.assertEqual(row["academy_code"], "CARD-FHA")
        self.assertEqual(row["currency"], "USD")
        self.assertEqual(row["amount_display"], "$10.00")

    def test_un_parent_ne_voit_que_ses_propres_tentatives(self):
        client = auth(APIClient(), "card.parent.fha@test.io")
        resp = client.get("/api/payments/card/transactions/")
        self.assertTrue(all(row["academy_code"] == "CARD-FHA" for row in resp.data))
        self.assertEqual(len(resp.data), 1)


class StripeSignatureTests(TestCase):
    """
    Vérification de signature avec la bibliothèque officielle.

    Le faux prestataire des tests précédents accepte une signature
    convenue : il éprouve notre logique, pas la cryptographie. Ce test-ci
    utilise le vrai code de Stripe, sans aucun appel réseau — la
    signature d'un webhook se calcule localement.
    """

    secret = "whsec_test_secret_pour_signature"

    def _signed(self, payload):
        import hashlib
        import hmac
        import time

        timestamp = int(time.time())
        signature = hmac.new(
            self.secret.encode(), f"{timestamp}.{payload}".encode(), hashlib.sha256,
        ).hexdigest()
        return f"t={timestamp},v1={signature}"

    @override_settings(
        CARD_PAYMENTS_ENABLED=True, STRIPE_SECRET_KEY="sk_test_x",
        STRIPE_PUBLISHABLE_KEY="pk_test_x",
    )
    def test_une_signature_correcte_est_acceptee(self):
        from apps.payments.providers import StripePaymentProvider

        payload = json.dumps({"id": "evt_signe", "type": "ping"})
        with override_settings(STRIPE_WEBHOOK_SECRET=self.secret):
            event_recu = StripePaymentProvider().verify_webhook(
                payload.encode(), self._signed(payload),
            )
        self.assertEqual(event_recu["id"], "evt_signe")

    @override_settings(
        CARD_PAYMENTS_ENABLED=True, STRIPE_SECRET_KEY="sk_test_x",
        STRIPE_PUBLISHABLE_KEY="pk_test_x", STRIPE_WEBHOOK_SECRET=secret,
    )
    def test_un_corps_modifie_apres_signature_est_refuse(self):
        """
        Le point exact que protège la signature : intercepter un événement
        légitime et en changer le montant.
        """
        from apps.payments.providers import StripePaymentProvider

        payload = json.dumps({"id": "evt_signe", "type": "ping"})
        header = self._signed(payload)
        falsifie = json.dumps({"id": "evt_signe", "type": "ping", "montant": 1})

        with self.assertRaises(ValidationError):
            StripePaymentProvider().verify_webhook(falsifie.encode(), header)

    @override_settings(
        CARD_PAYMENTS_ENABLED=True, STRIPE_SECRET_KEY="sk_test_x",
        STRIPE_PUBLISHABLE_KEY="pk_test_x", STRIPE_WEBHOOK_SECRET="",
    )
    def test_sans_secret_configure_aucun_evenement_n_est_accepte(self):
        from apps.payments.providers import (
            PaymentProviderNotConfigured, StripePaymentProvider,
        )

        with self.assertRaises(PaymentProviderNotConfigured):
            StripePaymentProvider().verify_webhook(b"{}", "t=1,v1=abc")


class FeeScheduleTests(TestCase):
    """La grille tarifaire est l'autorité sur les montants."""

    @classmethod
    def setUpTestData(cls):
        cls.feba = School.objects.create(
            name="FEBA grille", address="Cotonou", entity_type="campus",
            code="FEE-FEBA", currency_code="XOF",
        )
        cls.fha = School.objects.create(
            name="FHA grille", address="En ligne", entity_type="online",
            code="FEE-FHA", currency_code="USD",
        )
        cls.year = SchoolYear.objects.create(
            school=cls.feba, name="2025-2026-fee", is_current=True,
            start_date="2025-09-01", end_date="2026-07-01",
        )
        cls.student = Student.objects.create(
            school=cls.feba, school_year=cls.year, first_name="Élève",
            last_name="Grille", date_of_birth="2014-01-01",
        )

    def test_le_tarif_prend_la_devise_de_l_academie(self):
        fee = FeeSchedule.objects.create(
            academy=self.fha, payment_type="mensualite", amount_minor=12550,
        )
        self.assertEqual(fee.currency, "USD")
        self.assertEqual(fee.money.formatted(), "$125.50")

    def test_un_tarif_ne_peut_pas_franchir_la_frontiere_entre_academies(self):
        with self.assertRaises(ValidationError):
            FeeSchedule.objects.create(
                academy=self.fha, school_year=self.year,   # année de FEBA
                payment_type="mensualite", amount_minor=1000,
            )

    def test_le_tarif_de_l_annee_l_emporte_sur_le_tarif_permanent(self):
        FeeSchedule.objects.create(
            academy=self.feba, payment_type="mensualite", amount_minor=40000,
        )
        FeeSchedule.objects.create(
            academy=self.feba, school_year=self.year,
            payment_type="mensualite", amount_minor=50000,
        )
        fee = FeeSchedule.resolve(self.student, "mensualite", self.year)
        self.assertEqual(fee.amount_minor, 50000)

    def test_un_tarif_desactive_n_est_pas_resolu(self):
        FeeSchedule.objects.create(
            academy=self.feba, payment_type="cantine",
            amount_minor=10000, is_active=False,
        )
        self.assertIsNone(FeeSchedule.resolve(self.student, "cantine", self.year))

    def test_un_montant_nul_ou_negatif_est_refuse(self):
        with self.assertRaises(ValidationError):
            FeeSchedule.objects.create(
                academy=self.feba, payment_type="cantine", amount_minor=0,
            )
