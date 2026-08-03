"""
Ce que la connexion répond quand le compteur de tentatives ne répond plus.

LE DÉFAUT
---------
Le limiteur de débit de `/api/auth/login/` compte dans le cache. Redis
indisponible, l'exception de connexion remontait jusqu'au gestionnaire
d'exceptions de DRF et devenait un **500 « Une erreur interne est
survenue »**.

Refuser était la bonne décision. Le message, non : un 500 dit
« l'application a un défaut », alors que l'application va bien et qu'une
dépendance d'infrastructure est tombée. L'utilisateur rappelle son
école, l'école appelle l'éditeur, l'éditeur cherche un bug qui n'existe
pas — et personne ne redémarre Redis.

CE QUE CES TESTS TIENNENT
-------------------------
Deux situations, et la frontière entre elles :

  1. Cache disponible — la connexion fonctionne, et le limiteur compte
     réellement (une rafale finit par être bloquée).
  2. Cache injoignable — 503, message clair dans la langue négociée,
     `Retry-After`, incident enregistré, et **aucun jeton délivré**.

Le troisième point est le plus important : on vérifie que le refus est
FERMÉ. Un limiteur qui laisse passer quand il ne peut plus compter ouvre
la porte au moment précis où l'on ne voit plus qui entre.
"""
from unittest import mock

from django.core.cache import cache
from django.test import TestCase, override_settings
from redis.exceptions import ConnectionError as RedisConnectionError
from rest_framework.test import APIClient

from apps.accounts.models import CustomUser
from apps.core.ratelimit import MESSAGES, RETRY_AFTER_SECONDS
from apps.incidents.models import TechnicalIncident
from apps.schools.models import School

LOGIN = "/api/auth/login/"
MDP = "MotDePasse@2026"


# LE LIMITEUR EST DÉSACTIVÉ DANS LES RÉGLAGES DE TEST.
#
# `RATELIMIT_ENABLE = False` empêche les autres suites de se bloquer
# elles-mêmes en enchaînant les connexions. Conséquence : sans cette
# surcharge, le limiteur n'est éprouvé par AUCUN test — ni son comptage,
# ni son comportement en panne. On le rallume ici, et seulement ici.
@override_settings(RATELIMIT_ENABLE=True)
class SocleConnexion(TestCase):
    def setUp(self):
        super().setUp()
        cache.clear()
        self.client = APIClient()
        # Un compte sans établissement se voit refuser la connexion en
        # amont du limiteur : le scénario ne testerait plus rien.
        self.academie = School.objects.create(
            name="Académie d'essai", code="RL_TEST", slug="rl-test")
        self.utilisateur = CustomUser.objects.create_user(
            username="rl_user", email="rl@feba.bj", password=MDP,
            role="admin", first_name="Rate", last_name="Limit",
            school=self.academie,
        )

    def tearDown(self):
        cache.clear()
        super().tearDown()

    def connecter(self, **extra):
        return self.client.post(
            LOGIN, {"email": self.utilisateur.email, "password": MDP},
            format="json", **extra,
        )


class CacheDisponibleTests(SocleConnexion):
    """Le chemin normal : le compteur répond, la connexion fonctionne."""

    def test_la_connexion_reussit_et_delivre_un_jeton(self):
        reponse = self.connecter()
        self.assertEqual(reponse.status_code, 200)
        self.assertIn("access", reponse.data)
        self.assertIn("refresh", reponse.data)

    def test_aucun_incident_n_est_ouvert_quand_tout_va_bien(self):
        avant = TechnicalIncident.objects.count()
        self.connecter()
        self.assertEqual(TechnicalIncident.objects.count(), avant)

    def test_le_compteur_compte_reellement(self):
        # Sans ce contrôle, un limiteur débranché passerait pour un
        # limiteur en bon état : les deux laissent passer la première
        # tentative.
        statuts = []
        for _ in range(25):
            statuts.append(self.client.post(
                LOGIN, {"email": self.utilisateur.email, "password": "faux"},
                format="json").status_code)
        self.assertIn(403, statuts,
                      "la rafale n'a jamais été bloquée : le limiteur ne "
                      "compte pas")

    def test_un_mot_de_passe_faux_n_est_pas_une_panne_de_service(self):
        # Le projet répond 400 à une identification refusée (erreur de
        # validation du sérialiseur), et non 401. Ce n'est pas ce que ce
        # test juge : il vérifie qu'une erreur de SAISIE ne se déguise pas
        # en panne d'infrastructure. Confondre les deux ferait chercher un
        # serveur en panne pendant qu'un parent se trompe de mot de passe.
        reponse = self.client.post(
            LOGIN, {"email": self.utilisateur.email, "password": "faux"},
            format="json")
        self.assertEqual(reponse.status_code, 400)
        self.assertNotEqual(reponse.status_code, 503)
        self.assertNotIn("retry_after", reponse.data)


class CacheIndisponibleTests(SocleConnexion):
    """
    Redis tombé. Le cache est remplacé par un objet qui lève exactement ce
    que lève `redis-py` quand le serveur ne répond pas — pas une exception
    inventée pour l'occasion.
    """

    PANNE = RedisConnectionError(
        "Error 111 connecting to localhost:6379. Connection refused.")

    def connecter_sans_cache(self, **extra):
        # La bibliothèque va chercher le cache par `caches[nom]` à chaque
        # appel. On remplace donc la RÉSOLUTION, pas un objet importé une
        # fois — sinon la panne ne serait simulée nulle part.
        casse = mock.MagicMock()
        casse.add.side_effect = self.PANNE
        casse.incr.side_effect = self.PANNE
        casse.get.side_effect = self.PANNE
        with mock.patch.dict("django_ratelimit.core.caches",
                             {"default": casse}, clear=False):
            return self.connecter(**extra)

    def test_la_reponse_est_503_et_non_500(self):
        reponse = self.connecter_sans_cache()
        self.assertEqual(reponse.status_code, 503)

    def test_aucun_jeton_n_est_delivre(self):
        # LE CONTRÔLE QUI COMPTE. Un limiteur qui laisse passer quand il
        # ne peut plus compter est pire qu'absent : il donne l'illusion
        # d'une protection.
        reponse = self.connecter_sans_cache()
        self.assertNotIn("access", reponse.data)
        self.assertNotIn("refresh", reponse.data)

    def test_le_message_dit_ce_qui_se_passe(self):
        reponse = self.connecter_sans_cache()
        detail = reponse.data["detail"]
        self.assertEqual(detail, MESSAGES["fr"])
        self.assertIn("temporairement indisponible", detail)
        # Le message d'erreur interne générique ne doit plus apparaître :
        # c'est lui qui envoyait chercher un défaut applicatif.
        self.assertNotIn("erreur interne", detail.lower())

    def test_le_message_suit_la_langue_negociee(self):
        reponse = self.connecter_sans_cache(HTTP_ACCEPT_LANGUAGE="en")
        self.assertEqual(reponse.data["detail"], MESSAGES["en"])
        self.assertIn("temporarily unavailable", reponse.data["detail"])

    def test_la_reponse_dit_quand_reessayer(self):
        reponse = self.connecter_sans_cache()
        self.assertEqual(reponse["Retry-After"], str(RETRY_AFTER_SECONDS))
        self.assertEqual(reponse.data["retry_after"], RETRY_AFTER_SECONDS)

    def test_la_reponse_nomme_la_dependance_sans_l_exposer(self):
        reponse = self.connecter_sans_cache()
        self.assertEqual(reponse.data["service"], "cache")
        corps = str(reponse.data)
        # Ni adresse, ni port, ni trace : celui qui exploite sait quoi
        # redémarrer, celui qui sonde n'apprend rien.
        self.assertNotIn("6379", corps)
        self.assertNotIn("localhost", corps)
        self.assertNotIn("Traceback", corps)

    def test_un_incident_est_ouvert_pour_le_super_administrateur(self):
        avant = TechnicalIncident.objects.count()
        reponse = self.connecter_sans_cache()
        self.assertEqual(TechnicalIncident.objects.count(), avant + 1)

        incident = TechnicalIncident.objects.order_by("-id").first()
        self.assertIn("ratelimit", (incident.module or "").lower())
        self.assertEqual(incident.status_code, 503)
        self.assertEqual(reponse.data["incident_reference"], incident.reference)

    def test_l_incident_porte_le_chemin_tente(self):
        self.connecter_sans_cache()
        incident = TechnicalIncident.objects.order_by("-id").first()
        self.assertIn(LOGIN, incident.attempted_action or "")

    def test_le_service_repart_des_que_le_cache_revient(self):
        # Une panne de cache ne doit rien laisser derrière elle : pas de
        # verrou, pas d'état à nettoyer à la main.
        self.assertEqual(self.connecter_sans_cache().status_code, 503)
        self.assertEqual(self.connecter().status_code, 200)
