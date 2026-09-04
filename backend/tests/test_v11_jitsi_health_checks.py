"""
Les contrôles de santé Jitsi (§35), avec le réseau simulé.

POURQUOI CES DEUX CONTRÔLES MANQUAIENT
--------------------------------------
`jitsi_health` savait dire que l'hôte répond et que la page servie est
bien celle de Jitsi. Deux pannes fréquentes passaient pourtant au vert :

  1. `external_api.js` non servi — le navigateur ne peut alors ouvrir
     aucune conférence, alors que la page d'accueil répond 200 ;
  2. aucune règle de reverse proxy pour `/xmpp-websocket` — c'est la
     panne classique où « tout le monde entre dans la salle et personne
     ne se voit ».

Un diagnostic qui dit « opérationnel » dans ces deux cas envoie chercher
la panne ailleurs.
"""
from unittest.mock import patch

from django.test import SimpleTestCase, override_settings

from apps.virtualclass.services import jitsi_health

DOMAINE = "meet.globalfeba.com"
PAGE_JITSI = "<html><title>Jitsi Meet</title><body>lib-jitsi-meet</body></html>"


class FausseReponse:
    """Réponse HTTP minimale, utilisable en gestionnaire de contexte."""

    def __init__(self, status=200, body=b"", content_type="text/html"):
        self.status = status
        self._body = body
        self.headers = {"Content-Type": content_type}

    def read(self, n=None):
        return self._body[:n] if n else self._body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def reponses(mapping, defaut=None):
    """Aiguille `urlopen` selon l'URL demandée."""
    def _urlopen(request, timeout=None):
        url = request.full_url if hasattr(request, "full_url") else str(request)
        for fragment, reponse in mapping.items():
            if fragment in url:
                if isinstance(reponse, Exception):
                    raise reponse
                return reponse
        if defaut is None:
            raise AssertionError(f"URL non simulée : {url}")
        return defaut
    return _urlopen


@override_settings(JITSI_DOMAIN=DOMAINE, JITSI_APP_ID="feba",
                   JITSI_APP_SECRET="s" * 40)
class ControlesDeSanteTests(SimpleTestCase):

    def _rapport(self, mapping):
        # DNS et TLS sont neutralisés : ces tests portent sur les contrôles
        # applicatifs, pas sur la résolution de noms de l'environnement.
        with patch("socket.getaddrinfo", return_value=[(2, 1, 6, "", ("89.167.63.1", 443))]), \
             patch("socket.create_connection", side_effect=OSError("TLS hors périmètre de ce test")), \
             patch("urllib.request.urlopen", side_effect=reponses(mapping)):
            return jitsi_health(timeout=1)

    def _controle(self, rapport, nom):
        for c in rapport["checks"]:
            if c["name"] == nom:
                return c
        return None

    def test_tout_sert_correctement_donne_operationnel(self):
        r = self._rapport({
            "/external_api.js": FausseReponse(200, b"var x=1;" * 100,
                                              "application/javascript"),
            "/xmpp-websocket": FausseReponse(200, b""),
            DOMAINE: FausseReponse(200, PAGE_JITSI.encode()),
        })
        self.assertEqual(r["status"], "operational", r["detail"])
        self.assertTrue(self._controle(r, "external_api")["ok"])
        self.assertTrue(self._controle(r, "signalisation")["ok"])

    def test_external_api_absent_degrade_le_diagnostic(self):
        r = self._rapport({
            "/external_api.js": FausseReponse(404, b"Not Found"),
            "/xmpp-websocket": FausseReponse(200, b""),
            DOMAINE: FausseReponse(200, PAGE_JITSI.encode()),
        })
        self.assertEqual(r["status"], "degraded")
        controle = self._controle(r, "external_api")
        self.assertFalse(controle["ok"])
        # Le message doit dire la CONSÉQUENCE, pas seulement le code HTTP.
        self.assertIn("conférence", controle["detail"])

    def test_external_api_servi_en_html_est_detecte(self):
        """Un 200 ne suffit pas : une page d'erreur HTML répond 200 aussi."""
        r = self._rapport({
            "/external_api.js": FausseReponse(200, b"<html>oops</html>", "text/html"),
            "/xmpp-websocket": FausseReponse(200, b""),
            DOMAINE: FausseReponse(200, PAGE_JITSI.encode()),
        })
        self.assertEqual(r["status"], "degraded")
        self.assertFalse(self._controle(r, "external_api")["ok"])

    def test_absence_de_regle_websocket_est_signalee(self):
        r = self._rapport({
            "/external_api.js": FausseReponse(200, b"var x=1;" * 100,
                                              "application/javascript"),
            "/xmpp-websocket": FausseReponse(404, b"Not Found"),
            DOMAINE: FausseReponse(200, PAGE_JITSI.encode()),
        })
        self.assertEqual(r["status"], "degraded")
        controle = self._controle(r, "signalisation")
        self.assertFalse(controle["ok"])
        # Le symptôme que l'exploitant observera, nommé explicitement.
        self.assertIn("sans jamais se voir", controle["detail"])

    def test_un_code_inattendu_sur_le_websocket_ne_declenche_pas_de_fausse_alerte(self):
        """
        Seul 404 prouve l'absence de règle.

        400, 426 ou 501 sont des réponses NORMALES à une requête GET sans
        en-têtes de mise à niveau : les traiter comme des pannes ferait
        chercher un problème inexistant.
        """
        for code in (400, 426, 501):
            with self.subTest(code=code):
                r = self._rapport({
                    "/external_api.js": FausseReponse(200, b"var x=1;" * 100,
                                                      "application/javascript"),
                    "/xmpp-websocket": FausseReponse(code, b""),
                    DOMAINE: FausseReponse(200, PAGE_JITSI.encode()),
                })
                self.assertTrue(self._controle(r, "signalisation")["ok"])
                self.assertEqual(r["status"], "operational")
