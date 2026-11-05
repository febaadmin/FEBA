"""
Phase 7 — paiement par carte via FedaPay (Bénin, XOF).

Les appels HTTP vers FedaPay sont SIMULÉS ici (aucun réseau, aucune clé réelle) :
on simule la réponse documentée de l'API pour éprouver la logique de FEBA. La
validation en bac à sable réel exige un compte marchand et ses clés de test
(voir RAPPORT_VALIDATION_PAIEMENTS.md) ; elle n'est pas prétendue ici.

Cas couverts : accepté, refusé, abandonné, expiré, webhook reçu deux fois,
webhook invalide / périmé, retour navigateur sans confirmation, montant modifié,
devise incorrecte, double soumission, remboursement, devise non prise en charge,
accès d'un autre parent, concurrence (un seul encaissement).
"""
import hashlib
import hmac
import json
import time
from unittest.mock import patch

from django.test import override_settings
from rest_framework.test import APIClient

from apps.payments.card_views import appliquer_etat_prestataire, rapprocher_tentatives
from apps.payments.models import Payment
from apps.payments.providers import FedaPayPaymentProvider, PaymentProviderError
from apps.payments.transaction_models import PaymentTransaction, WebhookEvent
from tests.test_card_payments import CardPaymentBaseTests

SECRET = "wh_sandbox_pour_les_tests"
FEDAPAY = dict(CARD_PAYMENTS_ENABLED=True, PAYMENT_PROVIDER="fedapay", FEDAPAY_SECRET_KEY="sk_sandbox_tests",
               FEDAPAY_WEBHOOK_SECRET=SECRET, FEDAPAY_ENVIRONMENT="sandbox",
               CARD_RETURN_URL="https://feba.test/parent/payments?paiement=retour&transaction={id}")


def signer(corps, t=None, secret=SECRET):
    t = int(time.time()) if t is None else t
    s = hmac.new(secret.encode(), f"{t}.".encode() + corps, hashlib.sha256).hexdigest()
    return f"t={t},s={s}"


class FausseApiFedaPay:
    """Réponses simulées de l'API FedaPay (forme documentée : objet enveloppé « v1/transaction »)."""

    def __init__(self):
        self.appels, self.statut, self.montant, self.devise, self.suivant = [], "pending", 50000, "XOF", 1000

    def __call__(self, provider, methode, chemin, corps=None):
        self.appels.append((methode, chemin, corps))
        if methode == "POST" and chemin == "/transactions":
            self.suivant += 1
            return {"v1/transaction": {"id": self.suivant, "status": "pending", "amount": corps["amount"]}}
        if methode == "POST" and chemin.endswith("/token"):
            return {"token": "tok", "url": f"https://sandbox-checkout.fedapay.com/tok{self.suivant}"}
        if methode == "GET":
            return {"v1/transaction": {"id": int(chemin.rsplit("/", 1)[1]), "status": self.statut,
                                       "amount": self.montant, "currency": {"iso": self.devise}}}
        raise AssertionError(chemin)


@override_settings(**FEDAPAY)
class FedaPayTests(CardPaymentBaseTests):
    def setUp(self):
        # Pas de FakeProvider : le vrai fournisseur FedaPay, réseau simulé.
        self.api = FausseApiFedaPay()
        p = patch.object(FedaPayPaymentProvider, "_requete", lambda prov, *a, **k: self.api(prov, *a, **k))
        p.start()
        self.addCleanup(p.stop)
        self.parent = APIClient()
        self.parent.force_authenticate(self.parents["feba"])

    def payer(self, client=None, eleve=None):
        r = (client or self.parent).post("/api/payments/card/checkout/",
                                         {"student": (eleve or self.students["feba"]).pk, "payment_type": "mensualite",
                                          "amount": "1"}, format="json")
        return r

    def webhook(self, nom, fedapay_id, corps=None, signature=None):
        brut = json.dumps(corps or {"id": f"evt-{nom}-{fedapay_id}-{time.time_ns()}", "name": nom,
                                    "entity": {"id": fedapay_id, "status": "approved"}}).encode()
        return APIClient().post("/api/payments/webhook/fedapay/", brut, content_type="application/json",
                                HTTP_X_FEDAPAY_SIGNATURE=signature or signer(brut))

    def test_creation_montant_du_tarif_jamais_celui_du_navigateur(self):
        r = self.payer()
        self.assertEqual(r.status_code, 201, r.data)
        self.assertTrue(r.data["checkout_url"].startswith("https://sandbox-checkout.fedapay.com/"))
        _, chemin, corps = self.api.appels[0]
        self.assertEqual((chemin, corps["amount"], corps["currency"]), ("/transactions", 50000, {"iso": "XOF"}))
        tx = PaymentTransaction.objects.get()
        self.assertEqual((tx.provider, tx.provider_intent_id, tx.status), ("fedapay", "1001", "pending"))
        self.assertIn(f"transaction={tx.pk}", corps["callback_url"])
        self.assertEqual(corps["custom_metadata"]["transaction_id"], str(tx.pk))
        # Double soumission : même tentative, aucun second appel de création.
        r2 = self.payer()
        self.assertTrue(r2.data["reused"])
        self.assertEqual(PaymentTransaction.objects.count(), 1)

    def test_paiement_accepte_par_webhook_puis_rejoue(self):
        self.payer()
        self.api.statut = "approved"
        r = self.webhook("transaction.approved", 1001, corps={"id": "evt-1", "name": "transaction.approved",
                                                              "entity": {"id": 1001}})
        self.assertEqual((r.status_code, r.data["handled"]), (200, True))
        tx = PaymentTransaction.objects.get()
        self.assertEqual(tx.status, "succeeded")
        p = Payment.objects.get()
        self.assertEqual((p.amount_minor, p.payment_method, p.student_id), (50000, "card", self.students["feba"].pk))
        # Même événement rejoué : ignoré, aucun second encaissement.
        r = self.webhook("transaction.approved", 1001, corps={"id": "evt-1", "name": "transaction.approved",
                                                              "entity": {"id": 1001}})
        self.assertTrue(r.data["duplicate"])
        # Autre événement « approuvé » pour la même transaction : idempotent.
        self.webhook("transaction.approved", 1001)
        self.assertEqual(Payment.objects.count(), 1)

    def test_le_webhook_designe_le_serveur_verifie(self):
        """Un événement « approuvé » alors que FedaPay dit « en attente » ne crée rien."""
        self.payer()
        self.api.statut = "pending"
        self.webhook("transaction.approved", 1001)
        self.assertEqual(PaymentTransaction.objects.get().status, "pending")
        self.assertFalse(Payment.objects.exists())
        self.assertEqual(self.api.appels[-1][0], "GET")

    def test_webhook_invalide_ou_perime_refuse(self):
        self.payer()
        self.api.statut = "approved"
        brut = json.dumps({"id": "e", "name": "transaction.approved", "entity": {"id": 1001}}).encode()
        for signature in ("", "t=abc,s=00", signer(brut, secret="mauvais"), signer(brut, t=int(time.time()) - 3600)):
            r = APIClient().post("/api/payments/webhook/fedapay/", brut, content_type="application/json",
                                 HTTP_X_FEDAPAY_SIGNATURE=signature)
            self.assertEqual(r.status_code, 400, signature)
        self.assertFalse(Payment.objects.exists())
        self.assertFalse(WebhookEvent.objects.exists())

    def test_refuse_abandonne_expire(self):
        for statut, attendu in (("declined", "failed"), ("canceled", "cancelled")):
            PaymentTransaction.objects.all().delete()
            self.payer()
            self.api.statut = statut
            self.webhook(f"transaction.{statut}", self.api.suivant)
            self.assertEqual(PaymentTransaction.objects.get().status, attendu)
        self.assertFalse(Payment.objects.exists())
        # Expiration : tentative restée « en attente » au-delà du délai.
        PaymentTransaction.objects.all().delete()
        self.payer()
        self.api.statut = "pending"
        from datetime import timedelta
        from django.utils import timezone
        PaymentTransaction.objects.update(created_at=timezone.now() - timedelta(hours=30))
        bilan = rapprocher_tentatives()
        self.assertEqual((bilan["verifiees"], bilan["expirees"]), (1, 1))
        self.assertEqual(PaymentTransaction.objects.get().status, "expired")

    def test_retour_navigateur_sans_confirmation_puis_verification_serveur(self):
        tx_id = self.payer().data["transaction_id"]
        # Le navigateur revient, FedaPay n'a rien confirmé : rien n'est encaissé.
        r = self.parent.post(f"/api/payments/card/{tx_id}/verifier/")
        self.assertEqual((r.status_code, r.data["status"]), (200, "pending"))
        self.assertFalse(Payment.objects.exists())
        self.api.statut = "approved"
        r = self.parent.post(f"/api/payments/card/{tx_id}/verifier/")
        self.assertEqual(r.data["status"], "succeeded")
        self.assertEqual(Payment.objects.count(), 1)
        # Un autre parent ne peut ni vérifier ni deviner la transaction.
        autre = APIClient()
        autre.force_authenticate(self.parents["fha"])
        self.assertEqual(autre.post(f"/api/payments/card/{tx_id}/verifier/").status_code, 404)

    def test_montant_ou_devise_modifies_aucun_encaissement(self):
        for montant, devise in ((1, "XOF"), (50000, "USD")):
            PaymentTransaction.objects.all().delete()
            self.payer()
            self.api.statut, self.api.montant, self.api.devise = "approved", montant, devise
            self.webhook("transaction.approved", self.api.suivant)
            tx = PaymentTransaction.objects.get()
            self.assertEqual(tx.status, "failed", (montant, devise))
            self.assertIn("vérification manuelle", tx.failure_reason)
        self.assertFalse(Payment.objects.exists())

    def test_un_seul_encaissement_meme_appele_plusieurs_fois(self):
        tx_id = self.payer().data["transaction_id"]
        etat = {"statut": "approved", "montant": 50000, "devise": "XOF"}
        for origine in ("webhook", "retour", "rapprochement"):
            appliquer_etat_prestataire(tx_id, etat, origine)
        self.assertEqual(Payment.objects.count(), 1)

    def test_devise_non_prise_en_charge_usd(self):
        client = APIClient()
        client.force_authenticate(self.parents["fha"])
        r = client.post("/api/payments/card/checkout/", {"student": self.students["fha"].pk, "payment_type": "mensualite"},
                        format="json")
        self.assertEqual(r.status_code, 409)
        self.assertIn("USD", r.data["detail"])
        self.assertEqual(self.api.appels, [])
        cfg = client.get("/api/payments/card/config/").data
        self.assertFalse(cfg["enabled"])
        self.assertIn("USD", cfg["reason"])

    def test_eleve_d_un_autre_parent_introuvable(self):
        client = APIClient()
        client.force_authenticate(self.parents["fha"])
        r = self.payer(client=client, eleve=self.students["feba"])
        self.assertEqual(r.status_code, 404)

    def test_remboursement_constate_hors_ligne_par_l_administration(self):
        tx_id = self.payer().data["transaction_id"]
        appliquer_etat_prestataire(tx_id, {"statut": "approved", "montant": 50000, "devise": "XOF"}, "webhook")
        admin = APIClient()
        from apps.accounts.models import CustomUser
        admin.force_authenticate(CustomUser.objects.get(email="card.admin.feba@test.io"))
        r = admin.post(f"/api/payments/card/{tx_id}/refund/", {"amount": "20000"}, format="json")
        self.assertEqual(r.status_code, 409)                                  # pas d'API de remboursement
        self.assertIn("tableau de bord FedaPay", r.data["detail"])
        r = admin.post(f"/api/payments/card/{tx_id}/refund/", {"amount": "20000", "rembourse_chez_prestataire": True}, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        tx = PaymentTransaction.objects.get()
        self.assertEqual((tx.status, tx.amount_refunded_minor), ("partially_refunded", 20000))
        # Le graphique du tableau de bord déduit le remboursement (un paiement compté une fois).
        from apps.payments.tableau_bord import calculer
        from datetime import date, timedelta
        jour = date.today()
        ind = calculer([self.feba], "perso", jour - timedelta(days=30), jour + timedelta(days=30))["devises"][0]["indicateurs"]
        self.assertEqual((ind["encaisse_minor"], ind["nb_paiements"], ind["rembourse_minor"]), (30000, 1, 20000))

    def test_prestataire_injoignable_au_webhook_rejeu_possible(self):
        self.payer()

        def panne(*a, **k):
            raise PaymentProviderError("injoignable")
        with patch.object(FedaPayPaymentProvider, "fetch", panne):
            r = self.webhook("transaction.approved", 1001, corps={"id": "evt-x", "name": "transaction.approved", "entity": {"id": 1001}})
        self.assertEqual(r.status_code, 503)
        self.assertFalse(WebhookEvent.objects.filter(event_id="evt-x").exists())   # le rejeu sera traité
        self.api.statut = "approved"
        r = self.webhook("transaction.approved", 1001, corps={"id": "evt-x", "name": "transaction.approved", "entity": {"id": 1001}})
        self.assertEqual(r.data["handled"], True)
        self.assertEqual(Payment.objects.count(), 1)


class FedaPaySansConfigurationTests(CardPaymentBaseTests):
    def setUp(self):
        pass

    @override_settings(CARD_PAYMENTS_ENABLED=True, PAYMENT_PROVIDER="fedapay", FEDAPAY_SECRET_KEY="", FEDAPAY_WEBHOOK_SECRET="")
    def test_aucun_bouton_trompeur_ni_webhook_accepte(self):
        client = APIClient()
        client.force_authenticate(self.parents["feba"])
        self.assertFalse(client.get("/api/payments/card/config/").data["enabled"])
        r = client.post("/api/payments/card/checkout/", {"student": self.students["feba"].pk, "payment_type": "mensualite"}, format="json")
        self.assertEqual(r.status_code, 503)
        r = APIClient().post("/api/payments/webhook/fedapay/", b"{}", content_type="application/json", HTTP_X_FEDAPAY_SIGNATURE="t=1,s=0")
        self.assertEqual(r.status_code, 503)
