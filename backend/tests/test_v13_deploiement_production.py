"""
Scripts de déploiement et de contrôle de production.

CE QUE CES TESTS PROTÈGENT
--------------------------
Un script de déploiement qui affirme au lieu de vérifier est pire que pas
de script : il donne une confiance qu'il ne mérite pas. Ceux-ci fixent
les propriétés qui font la différence — sauvegarder avant de modifier,
vérifier après avoir agi, et savoir revenir en arrière.

La topologie visée est celle RÉELLEMENT en service sur le serveur :
projet Compose « app » dans /opt/feba/app, Jitsi Web publiant 80 et 443
directement, JVB en UDP/10000 annonçant 89.167.63.1.
"""
from django.test import SimpleTestCase

from tests.repo_root import read_repo_file

DEPLOIEMENT = "scripts/deploy_production.sh"
SANTE = "scripts/production_health.sh"


class ScriptDeDeploiementTests(SimpleTestCase):

    def setUp(self):
        self.script = read_repo_file(DEPLOIEMENT)

    def test_il_sauvegarde_avant_de_modifier(self):
        # Une production fonctionnelle ne s'écrase pas sans filet.
        self.assertIn("Sauvegarde avant modification", self.script)
        self.assertIn("git rev-parse HEAD", self.script)

    def test_il_sauvegarde_les_fichiers_d_environnement(self):
        for f in (".env", ".env.jitsi", "backend/.env"):
            self.assertIn(f, self.script)

    def test_il_ne_lit_jamais_la_valeur_d_un_secret(self):
        """
        Les `.env` sont COPIÉS, jamais affichés. Un script qui journalise
        un secret le répand dans les historiques de terminal et les
        journaux de CI.
        """
        for interdit in ("cat .env", "echo $JITSI_APP_SECRET", "grep -h JITSI_APP_SECRET"):
            self.assertNotIn(interdit, self.script)

    def test_il_offre_un_mode_qui_ne_modifie_rien(self):
        self.assertIn("--check", self.script)

    def test_il_offre_un_retour_arriere(self):
        self.assertIn("--rollback", self.script)

    def test_il_cree_le_reseau_partage_de_maniere_idempotente(self):
        self.assertIn("docker network inspect feba_jitsi_shared", self.script)
        self.assertIn("docker network create feba_jitsi_shared", self.script)

    def test_il_vise_la_topologie_reellement_deployee(self):
        # Les deux fichiers Compose utilisés par le serveur, pas une
        # topologie théorique.
        self.assertIn("docker-compose.jitsi.yml", self.script)
        self.assertIn("docker-compose.jitsi.prod.yml", self.script)

    def test_il_verifie_le_point_d_extension_au_lieu_de_le_supposer(self):
        """
        LE CONTRÔLE CENTRAL.

        Toute la configuration des en-têtes repose sur
        `include /run/web/config/nginx-custom/*.conf` du gabarit de
        jitsi/web. Ce point d'extension existe dans le gabarit publié par
        Jitsi, mais l'image `:stable` déployée peut être plus ancienne.
        Le script doit REGARDER, pas parier.
        """
        self.assertIn("/run/web/config/nginx-custom", self.script)
        self.assertIn("/defaults/meet.conf", self.script)
        self.assertIn("nginx -T", self.script)

    def test_il_controle_la_reponse_reelle_de_l_instance(self):
        # Une configuration correcte dans le dépôt ne prouve rien sur ce
        # que le serveur renvoie.
        self.assertIn("curl -sSI", self.script)
        self.assertIn("referrer-policy", self.script)

    def test_il_preserve_l_ip_annoncee_verifiee_en_production(self):
        self.assertIn("89.167.63.1", self.script)

    def test_il_s_interrompt_avant_de_modifier_si_un_prerequis_manque(self):
        self.assertIn("déploiement interrompu, rien n'a été modifié", self.script)


class ScriptDeSanteProductionTests(SimpleTestCase):

    def setUp(self):
        self.script = read_repo_file(SANTE)

    def test_il_distingue_trois_etats(self):
        # « Tout va bien » et « rien ne marche » ne suffisent pas : un
        # service dégradé se traite autrement qu'un service éteint.
        for etat in ("READY", "DEGRADED", "UNAVAILABLE"):
            self.assertIn(etat, self.script)

    def test_il_ne_leve_jamais_sur_un_service_injoignable(self):
        """
        `curl` renvoie 000 quand il ne peut pas se connecter. Le script
        doit le traiter comme un diagnostic, pas planter dessus.
        """
        self.assertIn('echo "000"', self.script)
        self.assertIn("000)", self.script)

    def test_il_controle_l_application_ET_la_visioconference(self):
        self.assertIn("globalfeba.com", self.script)
        self.assertIn("external_api.js", self.script)
        self.assertIn("xmpp-websocket", self.script)

    def test_un_404_sur_l_api_n_est_pas_traite_comme_une_panne(self):
        """
        Aucune vue n'est montée sur la racine de l'API : un 404 y prouve
        que Django répond, au contraire d'un serveur statique.
        """
        self.assertIn("Django répond", self.script)

    def test_seul_404_signale_l_absence_de_regle_websocket(self):
        """
        400, 426 et 501 sont des réponses NORMALES à un GET sans en-têtes
        de mise à niveau. Les traiter comme des pannes ferait chercher un
        problème inexistant.
        """
        self.assertIn("une règle de proxy existe", self.script)

    def test_il_refuse_une_instance_publique(self):
        self.assertIn("meet\\.jit\\.si", self.script)
