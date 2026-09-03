"""
P13 — Ce que la configuration Jitsi doit garantir en PRODUCTION.

Le contrôle d'accès aux salles (académie, rôle, classe, IDOR) est déjà
couvert par `test_jitsi_selfhosted.py` et `test_bulk_year_and_jitsi.py`.
Ce fichier couvre ce qui manquait : la CONFIGURATION livrée, le rapport de
santé, et le fait qu'aucun chemin ne ramène vers une instance publique.

POURQUOI TESTER DES FICHIERS DE CONFIGURATION
---------------------------------------------
Le code refusait déjà `meet.jit.si`. Les trois `.env.*.example` livrés le
proposaient pourtant comme valeur par défaut, `.env.prod.example` compris.
Personne ne s'en apercevait : le défaut se manifeste après déploiement, au
moment où un cours doit démarrer. Un test sur un fichier d'exemple n'est
pas excessif — c'est le seul endroit où ce défaut est visible avant la
production.
"""
import os
import re

from django.test import SimpleTestCase, TestCase, override_settings

from apps.virtualclass.services import (
    JitsiNotConfigured, assert_jitsi_configured, build_jitsi_jwt,
    jitsi_domain, jitsi_health, jitsi_probe_url,
)

from tests.repo_root import read_repo_file, repo_file, repo_root

#: Domaine de production de l'instance du groupe.
DOMAINE_PRODUCTION = "meet.globalfeba.com"

#: Instances publiques proscrites.
PUBLIQUES = ("meet.jit.si", "8x8.vc", "jitsi.org")


def _configuree(**extra):
    base = dict(
        JITSI_DOMAIN=DOMAINE_PRODUCTION,
        JITSI_APP_ID="feba_prod",
        JITSI_APP_SECRET="s" * 64,
        JITSI_INTERNAL_URL="",
    )
    base.update(extra)
    return base


class ConfigurationLivreeTests(SimpleTestCase):
    """Ce que contiennent les fichiers effectivement livrés."""

    FICHIERS_ENV = (
        ".env.example", ".env.dev.example", ".env.prod.example",
        ".env.jitsi.example",
    )

    def _affectations(self, chemin):
        """
        Affectations `CLE=valeur` d'un fichier .env, commentaires exclus.

        La distinction compte : ces fichiers EXPLIQUENT pourquoi les
        instances publiques sont proscrites, et doivent continuer de le
        faire. C'est la valeur affectée qui est interdite, pas le sujet.
        """
        valeurs = {}
        with open(chemin, encoding="utf-8") as fichier:
            for ligne in fichier:
                ligne = ligne.strip()
                if not ligne or ligne.startswith("#"):
                    continue
                if "=" in ligne:
                    cle, _, valeur = ligne.partition("=")
                    valeurs[cle.strip()] = valeur.strip()
        return valeurs

    def test_aucun_exemple_ne_propose_une_instance_publique(self):
        coupables = []
        for nom in self.FICHIERS_ENV:
            chemin = repo_file(nom)
            self.assertTrue(
                chemin.exists(),
                f"{nom} manque de la livraison : il est référencé par "
                "l'installation et par la documentation.")
            for cle, valeur in self._affectations(chemin).items():
                if not any(mot in cle for mot in ("DOMAIN", "URL")):
                    continue
                for publique in PUBLIQUES:
                    if publique in valeur:
                        coupables.append(f"{nom}: {cle}={valeur}")
        self.assertEqual(
            coupables, [],
            "Des modèles de configuration proposent encore une instance "
            f"publique : {coupables}")

    def test_le_modele_de_production_vise_l_instance_du_groupe(self):
        chemin = repo_file(".env.prod.example")
        self.assertTrue(os.path.exists(chemin), chemin)
        valeurs = self._affectations(chemin)
        self.assertEqual(valeurs.get("JITSI_DOMAIN"), DOMAINE_PRODUCTION)

    def test_la_surcouche_de_production_existe_et_impose_l_authentification(self):
        chemin = repo_file("docker-compose.jitsi.prod.yml")
        self.assertTrue(os.path.exists(chemin),
                        "La surcouche de production Jitsi est absente.")
        with open(chemin, encoding="utf-8") as fichier:
            contenu = fichier.read()
        # Une surcouche qui oublierait ces lignes ouvrirait l'instance à
        # tout le monde sur le domaine du groupe : pire qu'une instance
        # publique, parce que cela porte le nom de l'établissement.
        for attendu in ("ENABLE_AUTH=1", "ENABLE_GUESTS=0",
                        "AUTH_TYPE=jwt", "JWT_ALLOW_EMPTY=0"):
            with self.subTest(directive=attendu):
                self.assertIn(attendu, contenu)
        # Sans IP annoncée, le son et l'image ne passent pas derrière le NAT.
        self.assertIn("JVB_ADVERTISE_IPS", contenu)
        # TLS réel, pas le certificat auto-signé du développement.
        self.assertIn("ENABLE_LETSENCRYPT=1", contenu)

    def test_les_scripts_de_controle_sont_livres_et_executables(self):
        for nom in ("scripts/jitsi_up.sh", "scripts/jitsi_config_check.sh"):
            chemin = repo_file(nom)
            with self.subTest(script=nom):
                self.assertTrue(os.path.exists(chemin), chemin)
                self.assertTrue(os.access(chemin, os.X_OK),
                                f"{nom} n'est pas exécutable")

    def test_le_makefile_expose_les_cibles_d_exploitation(self):
        with open(repo_file("Makefile"), encoding="utf-8") as f:
            makefile = f.read()
        for cible in ("jitsi-up", "jitsi-down", "jitsi-restart",
                      "jitsi-logs", "jitsi-health", "jitsi-config-check",
                      "jitsi-prod-up"):
            with self.subTest(cible=cible):
                self.assertRegex(makefile, rf"(?m)^{re.escape(cible)}:")


class TopologieDeDeploiementTests(SimpleTestCase):
    """
    Les deux topologies possibles, et le conflit de ports entre elles.

    LE DÉFAUT CORRIGÉ
    -----------------
    `docker-compose.jitsi.prod.yml` publie les ports 80 et 443 de l'hôte.
    `docker-compose.prod.yml` (nginx-prod) publie EXACTEMENT LES MÊMES.
    La surcouche supposait un serveur dédié — sans jamais le vérifier —
    alors que globalfeba.com tourne déjà quelque part. Sur ce serveur, la
    pile Jitsi était INDÉPLOYABLE : soit « port is already allocated »,
    soit le site principal qui ne redémarre plus.

    La correction n'est pas de renoncer à l'une des deux : c'est de
    livrer les DEUX topologies, chacune cohérente, et de refuser qu'elles
    se confondent.
    """

    def _compose(self, nom):
        import yaml
        return yaml.safe_load(read_repo_file(nom))

    @staticmethod
    def _ports_hote(service):
        """Ports de l'HÔTE publiés par un service (côté gauche du mapping)."""
        ports = []
        for entree in service.get("ports") or []:
            morceaux = str(entree).split(":")
            if len(morceaux) >= 2:
                ports.append(morceaux[-2])
        return ports

    def test_la_surcouche_dediee_publie_bien_80_et_443(self):
        # Elle reste légitime — sur un serveur dédié. On verrouille son
        # intention pour que le test suivant ait un sens.
        web = self._compose("docker-compose.jitsi.prod.yml")["services"]["jitsi-web"]
        self.assertEqual(sorted(self._ports_hote(web)), ["443", "80"])

    def test_la_topologie_derriere_le_proxy_ne_prend_aucun_port_public(self):
        """
        C'est ce fichier qui rend Jitsi déployable sur le serveur FEBA.
        S'il publiait 80 ou 443, il ne servirait à rien.
        """
        compose = self._compose("docker-compose.jitsi.behind-proxy.yml")
        web = compose["services"]["jitsi-web"]
        entrees = [str(p) for p in (web.get("ports") or [])]
        self.assertTrue(entrees, "jitsi-web ne publie aucun port")
        for entree in entrees:
            with self.subTest(port=entree):
                self.assertTrue(
                    entree.startswith("127.0.0.1:"),
                    f"« {entree} » n'est pas restreint à la boucle locale : "
                    "une instance en clair serait exposée sur Internet.")
                self.assertNotIn(
                    self._ports_hote(web)[0], ("80", "443"),
                    "Le port entrerait en conflit avec nginx-prod.")

    def test_le_conflit_avec_nginx_prod_est_reel_et_documente(self):
        """
        Le conflit n'est pas hypothétique : on le mesure sur les fichiers
        livrés. S'il disparaissait un jour (nginx-prod déplacé, par
        exemple), ce test le signalerait — et la documentation des deux
        topologies devrait être revue.
        """
        nginx = self._compose("docker-compose.prod.yml")["services"]["nginx-prod"]
        jitsi = self._compose("docker-compose.jitsi.prod.yml")["services"]["jitsi-web"]
        communs = set(self._ports_hote(nginx)) & set(self._ports_hote(jitsi))
        self.assertEqual(
            communs, {"80", "443"},
            "Le conflit de ports supposé par la documentation n'est plus "
            f"celui-ci (communs : {communs}). Revoir "
            "JITSI_PRODUCTION_GUIDE.md § topologies.")

    def test_la_topologie_derriere_le_proxy_impose_la_meme_authentification(self):
        # Une seconde topologie qui oublierait l'authentification serait
        # pire qu'une instance publique : elle porterait le nom du groupe.
        contenu = read_repo_file("docker-compose.jitsi.behind-proxy.yml")
        for attendu in ("ENABLE_AUTH=1", "ENABLE_GUESTS=0",
                        "AUTH_TYPE=jwt", "JWT_ALLOW_EMPTY=0"):
            with self.subTest(directive=attendu):
                self.assertIn(attendu, contenu)
        self.assertIn("JVB_ADVERTISE_IPS", contenu)

    def test_derriere_le_proxy_jitsi_ne_demande_pas_de_certificat(self):
        # Deux clients ACME sur le même port 80 se disputeraient la
        # validation HTTP-01. C'est nginx qui termine TLS ici.
        contenu = read_repo_file("docker-compose.jitsi.behind-proxy.yml")
        self.assertIn("ENABLE_LETSENCRYPT=0", contenu)
        self.assertIn("DISABLE_HTTPS=1", contenu)

    def test_le_vhost_est_livre_mais_pas_active(self):
        """
        Activé d'avance, il ferait tomber le site principal : il référence
        un certificat qui n'existe pas encore, et nginx refuse de démarrer
        sur un certificat manquant.
        """
        self.assertTrue(
            repo_file("nginx", "sites-available",
                      "meet.globalfeba.com.conf").exists())
        actifs = list(repo_file("nginx", "sites-enabled").glob("*.conf"))
        self.assertEqual(
            actifs, [],
            f"Un vhost est activé dans la livraison : {actifs}. nginx "
            "refuserait de démarrer sans son certificat — et il sert aussi "
            "globalfeba.com.")

    def test_le_vhost_relaie_la_signalisation_temps_reel(self):
        """
        Sans mise à niveau WebSocket, la salle s'affiche et reste vide :
        les participants se connectent sans jamais se voir. C'est la
        panne la plus déroutante d'un Jitsi derrière un proxy.
        """
        vhost = read_repo_file("nginx", "sites-available",
                               "meet.globalfeba.com.conf")
        for emplacement in ("/xmpp-websocket", "colibri-ws", "/http-bind"):
            with self.subTest(emplacement=emplacement):
                self.assertIn(emplacement, vhost)
        self.assertIn("proxy_set_header Upgrade $http_upgrade;", vhost)
        self.assertIn('proxy_set_header Connection "upgrade";', vhost)
        # Sans X-Forwarded-Proto, Jitsi compose des URL http:// depuis une
        # page https:// : le navigateur les bloque, la salle reste noire.
        self.assertIn("proxy_set_header X-Forwarded-Proto $scheme;", vhost)

    def test_le_vhost_autorise_l_encadrement_par_le_site_feba(self):
        """
        L'application affiche la salle DANS UNE IFRAME. Un
        « X-Frame-Options: DENY » recopié du vhost principal rendrait la
        visioconférence inutilisable depuis l'écran Salles virtuelles.
        """
        vhost = read_repo_file("nginx", "sites-available",
                               "meet.globalfeba.com.conf")
        # On inspecte les DIRECTIVES, pas la prose : le fichier explique
        # justement pourquoi cet en-tête est absent, et cette explication
        # doit pouvoir rester.
        directives = [
            ligne.strip() for ligne in vhost.splitlines()
            if ligne.strip() and not ligne.strip().startswith("#")
        ]
        encadrement = [d for d in directives if "X-Frame-Options" in d]
        self.assertEqual(
            encadrement, [],
            "Le vhost pose X-Frame-Options : la salle ne s'afficherait "
            f"plus dans l'iframe de l'application. {encadrement}")
        csp = [d for d in directives if "frame-ancestors" in d]
        self.assertTrue(csp, "Aucune politique d'encadrement définie.")
        self.assertIn("https://globalfeba.com", csp[0])


class DomaineDeProductionTests(SimpleTestCase):
    """Le domaine retenu, et le refus des instances publiques."""

    def test_le_domaine_de_production_est_accepte(self):
        with override_settings(**_configuree()):
            self.assertEqual(jitsi_domain(), DOMAINE_PRODUCTION)
            assert_jitsi_configured()

    def test_chaque_instance_publique_est_refusee(self):
        for publique in PUBLIQUES:
            with self.subTest(domaine=publique):
                with override_settings(**_configuree(JITSI_DOMAIN=publique)):
                    with self.assertRaises(JitsiNotConfigured):
                        jitsi_domain()

    def test_une_instance_publique_avec_un_port_reste_refusee(self):
        # Contourner la liste noire en ajoutant « :443 » ne doit pas
        # suffire : c'est l'hôte qui est comparé, pas la chaîne entière.
        with override_settings(**_configuree(JITSI_DOMAIN="meet.jit.si:443")):
            with self.assertRaises(JitsiNotConfigured):
                jitsi_domain()

    def test_une_instance_publique_en_majuscules_reste_refusee(self):
        with override_settings(**_configuree(JITSI_DOMAIN="MEET.JIT.SI")):
            with self.assertRaises(JitsiNotConfigured):
                jitsi_domain()

    def test_un_domaine_sans_secret_ne_signe_aucun_jeton(self):
        # Une salle ouverte sans jeton est une salle non protégée : mieux
        # vaut une erreur d'infrastructure qu'un cours accessible à tous.
        with override_settings(**_configuree(JITSI_APP_SECRET="")):
            with self.assertRaises(JitsiNotConfigured):
                assert_jitsi_configured()

    def test_l_url_sondee_est_en_https_pour_le_domaine_de_production(self):
        with override_settings(**_configuree()):
            self.assertEqual(
                jitsi_probe_url(), f"https://{DOMAINE_PRODUCTION}/")

    def test_l_url_interne_prime_quand_elle_est_definie(self):
        with override_settings(
                **_configuree(JITSI_INTERNAL_URL="http://jitsi-web:80")):
            self.assertEqual(jitsi_probe_url(), "http://jitsi-web:80/")


class JetonDeProductionTests(TestCase):
    """Le jeton émis pour le domaine de production."""

    @classmethod
    def setUpTestData(cls):
        from apps.accounts.models import CustomUser
        cls.user = CustomUser.objects.create_user(
            username="prof", email="p@feba.bj", password="Pass1234!",
            role="teacher", first_name="A", last_name="B")

    def _decode(self, token, **kwargs):
        import jwt
        return jwt.decode(token, "s" * 64, algorithms=["HS256"],
                          audience="jitsi", **kwargs)

    def test_le_jeton_vise_le_domaine_de_production(self):
        with override_settings(**_configuree()):
            token = build_jitsi_jwt(self.user, "salle-cm2", moderator=True)
        payload = self._decode(token)
        self.assertEqual(payload["sub"], DOMAINE_PRODUCTION)
        self.assertEqual(payload["room"], "salle-cm2")
        self.assertTrue(payload["moderator"])

    def test_le_jeton_expire(self):
        # Un jeton intercepté ne doit pas ouvrir un accès permanent.
        with override_settings(**_configuree()):
            token = build_jitsi_jwt(self.user, "salle-cm2", ttl_seconds=900)
        payload = self._decode(token)
        self.assertLessEqual(payload["exp"] - payload["iat"], 900)

    def test_un_jeton_expire_est_rejete(self):
        import jwt
        with override_settings(**_configuree()):
            token = build_jitsi_jwt(self.user, "salle-cm2", ttl_seconds=-60)
        with self.assertRaises(jwt.ExpiredSignatureError):
            self._decode(token)

    def test_le_jeton_nomme_la_salle_donc_n_est_pas_rejouable_ailleurs(self):
        # C'est Prosody qui applique la règle ; on vérifie ici que le
        # backend lui donne bien de quoi le faire.
        with override_settings(**_configuree()):
            token = build_jitsi_jwt(self.user, "salle-a")
        self.assertEqual(self._decode(token)["room"], "salle-a")

    def test_aucun_jeton_n_est_signe_sans_instance_configuree(self):
        with override_settings(**_configuree(JITSI_DOMAIN="")):
            with self.assertRaises(JitsiNotConfigured):
                build_jitsi_jwt(self.user, "salle-cm2")


class RapportDeSanteTests(SimpleTestCase):
    """Le rapport doit nommer le contrôle en échec, pas seulement échouer."""

    def _noms(self, rapport):
        return {c["name"] for c in rapport["checks"]}

    def test_une_instance_non_configuree_est_indisponible(self):
        with override_settings(**_configuree(JITSI_DOMAIN="")):
            rapport = jitsi_health(timeout=1)
        self.assertEqual(rapport["status"], "unavailable")
        self.assertFalse(rapport["configured"])
        self.assertIn("configuration", self._noms(rapport))

    def test_une_instance_publique_est_refusee_par_le_rapport(self):
        with override_settings(**_configuree(JITSI_DOMAIN="meet.jit.si")):
            rapport = jitsi_health(timeout=1)
        self.assertEqual(rapport["status"], "unavailable")
        self.assertIn("PUBLIQUE", rapport["detail"])

    def test_un_domaine_qui_ne_resout_pas_est_nomme_comme_tel(self):
        # Le cas EXACT de meet.globalfeba.com tant que le DNS n'existe
        # pas : le rapport doit envoyer chez l'hébergeur DNS, pas faire
        # chercher une panne de service.
        with override_settings(
                **_configuree(JITSI_DOMAIN="jitsi-inexistant.globalfeba.com")):
            rapport = jitsi_health(timeout=3)
        self.assertNotEqual(rapport["status"], "operational")
        dns = [c for c in rapport["checks"] if c["name"] == "dns"]
        self.assertTrue(dns, "le contrôle DNS n'apparaît pas dans le rapport")
        self.assertFalse(dns[0]["ok"])
        self.assertIn("DNS", rapport["detail"])

    def test_le_rapport_ne_leve_jamais(self):
        # C'est la page de diagnostic qui l'affiche : elle doit survivre à
        # la panne qu'elle sert à expliquer.
        for domaine in ("", "meet.jit.si", "hote-invalide.invalid",
                        DOMAINE_PRODUCTION):
            with self.subTest(domaine=domaine):
                with override_settings(**_configuree(JITSI_DOMAIN=domaine)):
                    rapport = jitsi_health(timeout=2)
                self.assertIn(rapport["status"],
                              ("operational", "degraded", "unavailable"))
