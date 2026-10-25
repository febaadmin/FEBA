"""
Limites de débit derrière nginx : chaque client a son propre compteur.

Avant : REMOTE_ADDR = adresse du conteneur nginx pour TOUT le monde ; les
limites « par IP » étaient globales (une famille bloquait les autres).
"""
from django.test import RequestFactory, SimpleTestCase, override_settings

from apps.core.ratelimit import client_ip


class ClientIpTests(SimpleTestCase):
    def request(self, remote, real=None):
        meta = {"REMOTE_ADDR": remote}
        if real is not None:
            meta["HTTP_X_REAL_IP"] = real
        return RequestFactory().get("/", **meta)

    def test_adresse_reelle_transmise_par_nginx(self):
        self.assertEqual(client_ip(self.request("172.18.0.5", "41.85.160.12")), "41.85.160.12")

    def test_deux_familles_derriere_le_meme_proxy_ont_deux_compteurs(self):
        from django_ratelimit.core import _get_ip
        with override_settings(RATELIMIT_IP_META_KEY="apps.core.ratelimit.client_ip"):
            a = _get_ip(self.request("172.18.0.5", "41.85.160.12"))
            b = _get_ip(self.request("172.18.0.5", "102.64.3.7"))
        self.assertNotEqual(a, b)
        # Sans le réglage (ancien comportement) : même compteur pour tous.
        self.assertEqual(_get_ip(self.request("172.18.0.5", "41.85.160.12")),
                         _get_ip(self.request("172.18.0.5", "102.64.3.7")))

    def test_en_tete_ignore_hors_proxy_de_confiance(self):
        self.assertEqual(client_ip(self.request("203.0.113.9", "1.2.3.4")), "203.0.113.9")

    def test_en_tete_absent_ou_invalide(self):
        self.assertEqual(client_ip(self.request("172.18.0.5")), "172.18.0.5")
        self.assertEqual(client_ip(self.request("172.18.0.5", "pas-une-ip")), "172.18.0.5")

    def test_production_utilise_client_ip(self):
        from tests.repo_root import read_repo_file
        self.assertIn("RATELIMIT_IP_META_KEY = 'apps.core.ratelimit.client_ip'",
                      read_repo_file("backend", "feba_project", "settings", "prod.py"))
