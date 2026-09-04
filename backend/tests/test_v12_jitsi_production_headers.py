"""
En-têtes de sécurité de l'instance Jitsi — dépôt ET production.

CE QUE CE FICHIER DISTINGUE
---------------------------
Une configuration correcte dans le dépôt ne prouve RIEN sur ce que le
serveur renvoie. Le dépôt porte deux topologies Jitsi, et elles ne
servent pas par le même nginx :

    docker-compose.jitsi.prod.yml         → 80:80, 443:443 publiés
                                             directement : le nginx DU
                                             CONTENEUR répond.
    docker-compose.jitsi.behind-proxy.yml → 127.0.0.1:8443 : un nginx
                                             HÔTE répond, avec
                                             nginx/sites-available/.

`meet.globalfeba.com` renvoie « max-age=63072000 », « x-xss-protection »
et « permissions-policy: interest-cohort=() » — la signature exacte du
gabarit de `jitsi/web`. La production tourne donc sur la PREMIÈRE
topologie, et le fichier `nginx/sites-available/meet.globalfeba.com.conf`,
parfaitement correct, n'y est jamais lu.

Ces tests fixent la configuration du DÉPÔT. Ce que la production sert
réellement est mesuré par `make jitsi-health`, contrôle
« entetes_securite ».
"""
from django.test import SimpleTestCase

from tests.repo_root import read_repo_file

SNIPPET = "jitsi/nginx-custom/feba-security-headers.conf"


class SnippetConteneurTests(SimpleTestCase):
    """Le point d'extension du conteneur porte ce qu'il doit porter."""

    def setUp(self):
        self.contenu = read_repo_file(SNIPPET)
        # Les commentaires citent volontairement les valeurs À NE PAS
        # écrire (« camera=() couperait la caméra ») : les inclure dans
        # l'analyse ferait échouer le test sur sa propre explication.
        self.directives = "\n".join(
            l for l in self.contenu.splitlines()
            if l.strip() and not l.strip().startswith("#")
        )

    def test_referrer_policy_est_pose(self):
        # Une URL de salle contient le nom du cours : elle n'a pas à
        # voyager vers un site tiers.
        self.assertIn("Referrer-Policy", self.contenu)
        self.assertIn("strict-origin-when-cross-origin", self.contenu)

    def test_les_entetes_valent_aussi_pour_les_pages_d_erreur(self):
        """
        Le gabarit de l'image pose ses en-têtes SANS `always`, donc
        uniquement sur les réponses 2xx/3xx. Une page 4xx en était
        dépourvue.
        """
        for ligne in self.directives.splitlines():
            if ligne.strip().startswith("add_header"):
                self.assertIn("always", ligne,
                              f"en-tête sans `always` : {ligne.strip()}")

    def test_la_camera_et_le_micro_restent_autorises(self):
        """
        `camera=()` couperait la caméra de la conférence. Désactiver la
        fonctionnalité n'est pas la sécuriser.
        """
        self.assertIn("camera=(self)", self.directives)
        self.assertIn("microphone=(self)", self.directives)
        self.assertNotIn("camera=()", self.directives)
        self.assertNotIn("microphone=()", self.directives)

    def test_aucune_csp_complete_dans_le_snippet(self):
        """
        Jitsi a besoin de `eval`, de scripts en ligne, de blobs et de
        workers. Une CSP « propre » rend l'instance noire et muette. Seul
        `frame-ancestors` est utile, et il passe par CSP_HEADER.
        """
        self.assertNotIn("script-src", self.directives)
        self.assertNotIn("default-src", self.directives)

    def test_les_fichiers_de_configuration_ne_sont_pas_servis(self):
        self.assertIn("/\\.(env|git)", self.directives)


class TopologieServeurDedieTests(SimpleTestCase):
    """La surcouche « serveur dédié » — celle réellement déployée."""

    def setUp(self):
        self.compose = read_repo_file("docker-compose.jitsi.prod.yml")

    def test_le_point_d_extension_est_monte(self):
        self.assertIn("/run/web/config/nginx-custom", self.compose)
        # Lecture seule : le conteneur n'a aucune raison d'y écrire.
        self.assertIn("nginx-custom:ro", self.compose)

    def test_frame_ancestors_est_pose_par_variable(self):
        self.assertIn("CSP_HEADER", self.compose)
        self.assertIn("frame-ancestors", self.compose)

    def test_self_est_present_dans_frame_ancestors(self):
        """
        L'External API de Jitsi crée une iframe sur son PROPRE domaine.
        Retirer `'self'` casserait l'ouverture de la conférence, y
        compris depuis FEBA.
        """
        ligne = next(l for l in self.compose.splitlines() if "CSP_HEADER" in l)
        self.assertIn("'self'", ligne)

    def test_globalfeba_peut_embarquer_la_conference(self):
        ligne = next(l for l in self.compose.splitlines() if "CSP_HEADER" in l)
        self.assertIn("https://globalfeba.com", ligne)

    def test_la_politique_n_est_pas_ouverte_a_tous(self):
        ligne = next(l for l in self.compose.splitlines() if "CSP_HEADER" in l)
        self.assertNotIn("frame-ancestors *", ligne)
        self.assertNotIn("frame-ancestors 'none'", ligne,
                         "'none' casserait l'External API")


class ActionsProductionDocumenteesTests(SimpleTestCase):
    """
    Ce qui appartient au serveur est écrit, avec des commandes exactes.

    Le dépôt ne peut pas modifier une instance à laquelle il n'a pas
    accès. Ce qu'il peut faire, c'est ne pas laisser croire que c'est
    fait.
    """

    def setUp(self):
        self.actions = read_repo_file("JITSI_PRODUCTION_ACTIONS.md")

    def test_le_document_existe_et_nomme_le_serveur(self):
        self.assertIn("89.167.63.1", self.actions)
        self.assertIn("meet.globalfeba.com", self.actions)

    def test_chaque_etape_a_sa_commande_de_retour_arriere(self):
        self.assertIn("rollback", self.actions.lower())

    def test_la_verification_est_fournie_avec_la_modification(self):
        # Une action sans commande de contrôle laisse croire qu'elle a
        # marché.
        self.assertIn("curl", self.actions)
        self.assertIn("docker compose", self.actions)


class ReseauPartageAuDemarrageTests(SimpleTestCase):
    """
    §14 — le réseau partagé ne peut plus bloquer un démarrage.

    LE DÉFAUT CORRIGÉ
    -----------------
    `feba_jitsi_shared` est POSSÉDÉ par `docker-compose.yml` et REJOINT
    par la pile Jitsi, qui le déclare `external`. Démarrer Jitsi sur une
    machine où la pile FEBA n'a jamais tourné — ou après un
    `docker network prune` — échouait donc sur :

        network feba_jitsi_shared declared as external,
        but could not be found

    `scripts/jitsi_up.sh` le créait déjà, mais UNIQUEMENT pour le
    démarrage de développement. Les cibles de PRODUCTION ne passent pas
    par ce script : elles tombaient sur l'erreur, sur le serveur, au pire
    moment.
    """

    def setUp(self):
        self.makefile = read_repo_file("Makefile")

    def test_une_cible_dediee_cree_le_reseau(self):
        self.assertIn("jitsi-network:", self.makefile)
        self.assertIn("docker network create feba_jitsi_shared", self.makefile)

    def test_la_creation_est_idempotente(self):
        """Un `create` inconditionnel échouerait au second démarrage."""
        bloc = self.makefile.split("jitsi-network:", 1)[1].split("\n\n", 1)[0]
        self.assertIn("docker network inspect", bloc)
        self.assertIn("||", bloc)

    def test_les_demarrages_de_production_en_dependent(self):
        for cible in ("jitsi-prod-up", "jitsi-proxy-up"):
            ligne = next(l for l in self.makefile.splitlines()
                         if l.startswith(f"{cible}:"))
            self.assertIn("jitsi-network", ligne,
                          f"« {cible} » peut encore échouer sur le réseau absent")

    def test_le_demarrage_de_developpement_le_cree_aussi(self):
        script = read_repo_file("scripts/jitsi_up.sh")
        self.assertIn("docker network create feba_jitsi_shared", script)
