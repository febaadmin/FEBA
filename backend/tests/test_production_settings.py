"""
P15 — Réglages destinés à https://globalfeba.com.

POURQUOI CES TESTS EXISTENT
---------------------------
`settings/prod.py` n'est chargé par aucun test : la suite tourne sous
`test_sqlite` ou `test_postgres`. Une erreur y reste donc invisible
jusqu'au déploiement — et certaines n'apparaissent même pas au
déploiement.

`CSRF_TRUSTED_ORIGINS` en est l'exemple exact. Il manquait. L'API
s'authentifiant par jeton JWT sans cookie, rien ne se voyait : le site
répondait, les élèves se connectaient, les reçus sortaient. Le seul
symptôme était qu'un administrateur ne pouvait plus entrer dans
/django-admin/ — exposé par nginx — avec un message parlant d'« origin
checking » qui ne désigne pas sa cause.

Ces tests chargent le VRAI module de production, avec un environnement
minimal, et vérifient ce qui doit y être vrai.
"""
import importlib
import os
import unittest
from unittest import mock

from django.test import SimpleTestCase

from tests.repo_root import read_repo_file

ENVIRONNEMENT_MINIMAL = {
    "SECRET_KEY": "x" * 64,
    "ALLOWED_HOSTS": "globalfeba.com,www.globalfeba.com",
    "DATABASE_URL": "postgresql://u:p@db:5432/feba",
    "REDIS_URL": "redis://redis:6379/0",
    "CORS_ALLOWED_ORIGINS": "https://globalfeba.com",
}


def charger_prod(**surcharges):
    """
    Charge `feba_project.settings.prod` avec un environnement donné.

    Le module est rechargé à chaque appel : `python-decouple` lit
    l'environnement à l'import, et un module déjà en cache renverrait les
    valeurs du premier chargement.
    """
    env = dict(ENVIRONNEMENT_MINIMAL)
    env.update(surcharges)
    with mock.patch.dict(os.environ, env, clear=False):
        import feba_project.settings.prod as prod
        return importlib.reload(prod)


class ReglagesDeProductionTests(SimpleTestCase):

    def test_les_origines_csrf_sont_definies(self):
        prod = charger_prod(
            CSRF_TRUSTED_ORIGINS="https://globalfeba.com,https://www.globalfeba.com")
        self.assertIn("https://globalfeba.com", prod.CSRF_TRUSTED_ORIGINS)
        self.assertIn("https://www.globalfeba.com", prod.CSRF_TRUSTED_ORIGINS)

    def test_les_origines_csrf_sont_deduites_si_la_variable_manque(self):
        # Une installation existante qui met simplement le code à jour ne
        # doit pas se retrouver avec un back-office inaccessible.
        prod = charger_prod(CSRF_TRUSTED_ORIGINS="")
        self.assertIn("https://globalfeba.com", prod.CSRF_TRUSTED_ORIGINS)

    def test_chaque_origine_csrf_porte_un_schema(self):
        # Django REFUSE une origine sans schéma, au démarrage.
        prod = charger_prod(CSRF_TRUSTED_ORIGINS="")
        for origine in prod.CSRF_TRUSTED_ORIGINS:
            with self.subTest(origine=origine):
                self.assertTrue(origine.startswith("https://"), origine)

    def test_aucune_origine_vide_dans_les_listes(self):
        # `"".split(",")` vaut `[""]`, pas `[]` : une chaîne vide dans
        # CORS_ALLOWED_ORIGINS fait échouer la validation de django-cors.
        prod = charger_prod(CORS_ALLOWED_ORIGINS="", CSRF_TRUSTED_ORIGINS="")
        self.assertNotIn("", prod.CORS_ALLOWED_ORIGINS)
        self.assertNotIn("", prod.CSRF_TRUSTED_ORIGINS)

    def test_le_mode_debug_est_desactive(self):
        self.assertFalse(charger_prod().DEBUG)

    def test_les_cookies_ne_partent_qu_en_https(self):
        prod = charger_prod()
        self.assertTrue(prod.SESSION_COOKIE_SECURE)
        self.assertTrue(prod.CSRF_COOKIE_SECURE)
        self.assertEqual(prod.SESSION_COOKIE_SAMESITE, "Lax")
        self.assertEqual(prod.CSRF_COOKIE_SAMESITE, "Lax")

    def test_l_en_tete_du_proxy_tls_est_pris_en_compte(self):
        # Sans lui, Django croit servir en clair derrière le reverse proxy
        # et boucle sur sa propre redirection HTTPS.
        prod = charger_prod()
        self.assertEqual(prod.SECURE_PROXY_SSL_HEADER,
                         ("HTTP_X_FORWARDED_PROTO", "https"))

    def test_les_protections_d_entete_sont_actives(self):
        prod = charger_prod()
        self.assertTrue(prod.SECURE_SSL_REDIRECT)
        self.assertGreaterEqual(prod.SECURE_HSTS_SECONDS, 31536000)
        self.assertTrue(prod.SECURE_HSTS_INCLUDE_SUBDOMAINS)
        self.assertTrue(prod.SECURE_CONTENT_TYPE_NOSNIFF)
        self.assertEqual(prod.X_FRAME_OPTIONS, "DENY")

    def test_les_hotes_autorises_ne_sont_pas_ouverts_a_tous(self):
        prod = charger_prod()
        self.assertNotIn("*", prod.ALLOWED_HOSTS)
        self.assertIn("globalfeba.com", prod.ALLOWED_HOSTS)

    def test_le_modele_de_production_documente_les_variables_requises(self):
        # CE TEST NE S'IGNORE PLUS.
        #
        # Il était gardé par un `skipUnless` sur l'existence du fichier,
        # donc systématiquement ignoré dans le conteneur, où la racine du
        # dépôt n'est pas montée. Le modèle que suit un exploitant pour
        # écrire son .env.prod n'était vérifié nulle part, et l'omission
        # de CSRF_TRUSTED_ORIGINS — corrigée en V8 — aurait pu y revenir
        # sans que rien ne l'annonce.
        contenu = read_repo_file(".env.prod.example")
        for variable in ("ALLOWED_HOSTS", "CORS_ALLOWED_ORIGINS",
                         "CSRF_TRUSTED_ORIGINS", "JITSI_DOMAIN",
                         "JITSI_APP_SECRET", "DATABASE_URL", "REDIS_URL"):
            with self.subTest(variable=variable):
                self.assertRegex(contenu, rf"(?m)^{variable}=")
