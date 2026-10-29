"""
Configuration de déploiement plugNmeet / LiveKit (fichiers de livraison).

Constat du 29/10/2026 sur le serveur partagé (7,6 Go, bot OKX, Jitsi) :
Docker y publie chaque port par un processus docker-proxy (≈ 5 Mo, IPv4 +
IPv6). La plage média 50000-50500 en aurait lancé ≈ 1 000, soit ≈ 5 Go.
LiveKit multiplexe désormais le média sur une petite plage (rtc.udp_port),
la pile a des limites mémoire, et TURN ne s'active qu'avec un certificat.
"""
import os
import re
import shutil
import stat
import subprocess
import tempfile
from pathlib import Path

import yaml
from django.test import SimpleTestCase

from tests.repo_root import read_repo_file, repo_file

# Au-delà, le coût en processus docker-proxy redevient significatif.
MAX_UDP_PORTS = 8


def render(template: str, env: dict) -> str:
    """Même rendu que scripts/plugnmeet_setup.sh (substitution ${VAR})."""
    missing = sorted({m for m in re.findall(r"\$\{([A-Z0-9_]+)\}", template) if not env.get(m)})
    assert not missing, f"variables manquantes : {missing}"
    return re.sub(r"\$\{([A-Z0-9_]+)\}", lambda m: env[m.group(1)], template)


def env_example() -> dict:
    env = {}
    for line in read_repo_file("plugnmeet/plugnmeet.env.example").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            env[k] = v
    return env


def port_count(spec: str) -> int:
    start, _, end = spec.partition("-")
    return int(end) - int(start) + 1 if end else 1


def published_ports(compose: dict, service: str) -> list:
    return compose["services"][service].get("ports", [])


class LiveKitUdpMuxTests(SimpleTestCase):
    def setUp(self):
        self.env = env_example()
        self.livekit = yaml.safe_load(render(read_repo_file("plugnmeet/templates/livekit.yaml.tpl"), self.env))

    def test_le_media_passe_par_le_multiplexage_udp(self):
        rtc = self.livekit["rtc"]
        self.assertEqual(str(rtc["udp_port"]), self.env["LIVEKIT_UDP_PORTS"])
        # port_range_start/end l'emporteraient sur udp_port (mediatransportutil).
        self.assertNotIn("port_range_start", rtc)
        self.assertNotIn("port_range_end", rtc)
        self.assertEqual(rtc["tcp_port"], 7881)

    def test_la_plage_udp_reste_courte(self):
        spec = self.env["LIVEKIT_UDP_PORTS"]
        self.assertRegex(spec, r"^\d+(-\d+)?$")
        self.assertLessEqual(port_count(spec), MAX_UDP_PORTS)

    def test_le_script_ne_publie_plus_d_ancienne_plage(self):
        setup = read_repo_file("scripts/plugnmeet_setup.sh")
        for mode in ("UDP_PORTS_PROD", "UDP_PORTS_LOCAL"):
            m = re.search(rf'^{mode}="([^"]+)"', setup, re.M)
            self.assertIsNotNone(m, mode)
            self.assertLessEqual(port_count(m.group(1)), MAX_UDP_PORTS)
        self.assertNotIn('"LIVEKIT_UDP_START":', setup)
        # Les anciennes clés sont RETIRÉES d'un plugnmeet.env existant.
        self.assertIn('"LIVEKIT_UDP_START=", "LIVEKIT_UDP_END=", "LIVEKIT_UDP_PORTS="', setup)
        self.assertNotRegex(read_repo_file("plugnmeet/plugnmeet.env.example"), r"LIVEKIT_UDP_(START|END)=")


class ComposePortsTests(SimpleTestCase):
    def setUp(self):
        self.base = yaml.safe_load(read_repo_file("plugnmeet/docker-compose.plugnmeet.yml"))
        self.turn = yaml.safe_load(read_repo_file("plugnmeet/docker-compose.plugnmeet.turn.yml"))

    def test_livekit_publie_la_meme_plage_que_sa_configuration(self):
        ports = published_ports(self.base, "pnm-livekit")
        udp = [p for p in ports if p.endswith("/udp")]
        self.assertEqual(udp, ["${LIVEKIT_UDP_PORTS:?plage UDP manquante}:${LIVEKIT_UDP_PORTS}/udp"])

    def test_les_ports_turn_ne_sont_publies_qu_avec_le_fichier_turn(self):
        base = published_ports(self.base, "pnm-livekit")
        self.assertFalse(any(p.startswith(("3478", "5349")) for p in base), base)
        self.assertEqual(self.turn["services"].keys(), {"pnm-livekit"})
        self.assertEqual(
            [p.split("#")[0].strip() for p in published_ports(self.turn, "pnm-livekit")],
            ["3478:3478/udp", "5349:5349/tcp"],
        )

    def test_80_et_443_restent_reserves_au_proxy_edge(self):
        for name, svc in self.base["services"].items():
            for p in svc.get("ports", []):
                host = p.split(":")[-2] if p.count(":") >= 2 else p.split(":")[0]
                if host in ("80", "443"):
                    self.assertEqual(svc.get("profiles"), ["edge"], name)

    def test_les_ports_d_administration_restent_locaux(self):
        for svc, port in (("plugnmeet", "8080"), ("pnm-livekit", "7880"), ("pnm-nats", "8222")):
            local = [p for p in published_ports(self.base, svc) if p.endswith(f":{port}")]
            self.assertTrue(local and all(p.startswith("127.0.0.1:") for p in local), (svc, local))


class ComposeImagesTests(SimpleTestCase):
    def test_chaque_image_est_epinglee_par_tag_et_empreinte(self):
        base = yaml.safe_load(read_repo_file("plugnmeet/docker-compose.plugnmeet.yml"))
        for name, svc in base["services"].items():
            self.assertRegex(svc["image"], r"^[a-z0-9./-]+:[A-Za-z0-9._-]+@sha256:[0-9a-f]{64}$", name)

    def test_livekit_inclut_le_durcissement_turn_de_v1_13_10(self):
        """v1.13.10 : relais TURN TCP refusés, relais vers l'hôte limités aux ports média."""
        image = yaml.safe_load(read_repo_file("plugnmeet/docker-compose.plugnmeet.yml"))["services"]["pnm-livekit"]["image"]
        version = tuple(int(x) for x in re.search(r":v(\d+)\.(\d+)\.(\d+)@", image).groups())
        self.assertGreaterEqual(version, (1, 13, 10))


class SecretsHorsArgumentsTests(SimpleTestCase):
    """Un argument de processus est lisible par tout compte de l'hôte (ps)."""

    SECRETS = re.compile(r"PASSWORD|SECRET|_KEY\b|PRIVATE")

    def test_aucun_secret_dans_les_commandes_ni_les_controles_de_sante(self):
        base = yaml.safe_load(read_repo_file("plugnmeet/docker-compose.plugnmeet.yml"))
        for name, svc in base["services"].items():
            for champ in ("command", "entrypoint"):
                valeur = svc.get(champ) or []
                texte = " ".join(valeur) if isinstance(valeur, list) else str(valeur)
                self.assertNotRegex(texte, self.SECRETS, f"{name}.{champ}")
            test = " ".join((svc.get("healthcheck") or {}).get("test") or [])
            self.assertNotRegex(test, self.SECRETS, f"{name}.healthcheck")
            self.assertNotRegex(test, r"redis-cli[^|]*\s-a\s", f"{name}.healthcheck")

    def test_redis_lit_son_mot_de_passe_dans_un_fichier_rendu(self):
        tpl = read_repo_file("plugnmeet/templates/redis.conf.tpl")
        self.assertRegex(tpl, r"(?m)^requirepass \$\{PNM_REDIS_PASSWORD\}$")
        self.assertRegex(tpl, r"(?m)^appendonly yes$")
        redis = yaml.safe_load(read_repo_file("plugnmeet/docker-compose.plugnmeet.yml"))["services"]["pnm-redis"]
        self.assertIn("./runtime/redis.conf:/usr/local/etc/redis/redis.conf:ro", redis["volumes"])
        self.assertEqual(redis["environment"], {"REDISCLI_AUTH": "${PNM_REDIS_PASSWORD:?secret manquant}"})


class AiguilleurTests(SimpleTestCase):
    """Aiguilleur 80/443 : Jitsi et plugNmeet sur une seule adresse IPv4."""

    def test_le_routage_tls_ne_vise_que_la_boucle_locale(self):
        conf = read_repo_file("plugnmeet/edge/nginx.conf")
        cibles = re.findall(r"^\s+(\S+)\s+(127\.0\.0\.1:\d+);", conf, re.M)
        self.assertEqual(dict(cibles), {"meet.globalfeba.com": "127.0.0.1:8444",
                                        "pnm.globalfeba.com": "127.0.0.1:9443",
                                        "default": "127.0.0.1:8444"})
        self.assertIn("ssl_preread on;", conf)
        self.assertNotIn("ssl_certificate", conf)          # aucune clé privée côté aiguilleur
        self.assertIn("proxy_pass http://127.0.0.1:8443;", conf)  # défis ACME de Jitsi

    @staticmethod
    def charger_compose(texte):
        """yaml.safe_load qui accepte les étiquettes Compose !override / !reset."""
        class Chargeur(yaml.SafeLoader):
            pass
        for tag in ("!override", "!reset"):
            Chargeur.add_constructor(tag, lambda l, n: l.construct_sequence(n) if isinstance(n, yaml.SequenceNode)
                                     else l.construct_mapping(n) if isinstance(n, yaml.MappingNode) else l.construct_scalar(n))
        return yaml.load(texte, Loader=Chargeur)

    def test_les_surcharges_ne_publient_qu_en_boucle_locale(self):
        for chemin in ("docker-compose.jitsi.edge.yml", "plugnmeet/docker-compose.plugnmeet.edge.yml"):
            # Sans !override, Compose AJOUTERAIT ces ports aux 80/443 publics.
            self.assertIn("ports: !override", read_repo_file(chemin), chemin)
        jitsi = self.charger_compose(read_repo_file("docker-compose.jitsi.edge.yml"))
        self.assertEqual(set(jitsi["services"]), {"jitsi-web"})
        pnm = self.charger_compose(read_repo_file("plugnmeet/docker-compose.plugnmeet.edge.yml"))
        self.assertEqual(set(pnm["services"]), {"pnm-web"})
        for svc in (jitsi["services"]["jitsi-web"], pnm["services"]["pnm-web"]):
            self.assertTrue(all(p.startswith("127.0.0.1:") for p in svc["ports"]), svc["ports"])

    def test_l_aiguilleur_est_epingle_et_limite(self):
        edge = yaml.safe_load(read_repo_file("plugnmeet/edge/docker-compose.edge.yml"))["services"]["edge"]
        self.assertRegex(edge["image"], r"@sha256:[0-9a-f]{64}$")
        self.assertEqual(edge["network_mode"], "host")
        self.assertEqual(edge["mem_limit"], edge["memswap_limit"])
        self.assertIn("./nginx.conf:/etc/nginx/nginx.conf:ro", edge["volumes"])


class ComposeLimitsTests(SimpleTestCase):
    def test_chaque_service_a_une_limite_sans_echange(self):
        base = yaml.safe_load(read_repo_file("plugnmeet/docker-compose.plugnmeet.yml"))
        limits = yaml.safe_load(read_repo_file("plugnmeet/docker-compose.plugnmeet.limits.yml"))
        self.assertEqual(set(limits["services"]), set(base["services"]))
        for name, svc in limits["services"].items():
            self.assertIn("mem_limit", svc, name)
            self.assertEqual(svc["mem_limit"], svc["memswap_limit"], name)

    def test_le_total_tient_dans_la_marge_du_serveur_partage(self):
        limits = yaml.safe_load(read_repo_file("plugnmeet/docker-compose.plugnmeet.limits.yml"))
        to_mib = {"m": 1, "g": 1024}
        total = sum(int(s["mem_limit"][:-1]) * to_mib[s["mem_limit"][-1]] for s in limits["services"].values())
        self.assertLessEqual(total, 2560)


class TurnActivationTests(SimpleTestCase):
    def test_turn_desactive_ne_reference_aucun_port_publie(self):
        env = env_example() | {"LIVEKIT_TURN_ENABLED": "false"}
        conf = yaml.safe_load(render(read_repo_file("plugnmeet/templates/livekit.yaml.tpl"), env))
        self.assertIs(conf["turn"]["enabled"], False)

    def test_turn_active_sans_certificat_echoue_avant_tout_rendu(self):
        """--turn on sans certificat : échec, AUCUN fichier de configuration rendu."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for part in ("scripts", "plugnmeet"):
                shutil.copytree(repo_file(part), root / part, ignore=shutil.ignore_patterns("runtime"))
            # Outils exigés par le script : présents mais inertes (le contrôle
            # TURN doit échouer avant tout appel à docker ou curl).
            fake = root / "bin"
            fake.mkdir()
            for tool in ("docker", "curl", "unzip", "openssl"):
                f = fake / tool
                f.write_text("#!/bin/sh\necho appel inattendu >&2\nexit 99\n")
                f.chmod(f.stat().st_mode | stat.S_IEXEC)
            result = subprocess.run(
                ["bash", str(root / "scripts/plugnmeet_setup.sh"),
                 "--domain", "pnm.example.org", "--public-ip", "203.0.113.10", "--turn", "on"],
                capture_output=True, text=True, timeout=60,
                env={**os.environ, "PATH": f"{fake}:{os.environ['PATH']}"},
            )
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertIn("--turn on sans certificat", result.stdout)
            self.assertNotIn("appel inattendu", result.stderr)
            self.assertFalse((root / "plugnmeet/runtime/livekit.yaml").exists())
            self.assertFalse((root / "plugnmeet/runtime/plugnmeet.env").exists())

    def test_option_turn_invalide_refusee(self):
        result = subprocess.run(
            ["bash", str(repo_file("scripts/plugnmeet_setup.sh")),
             "--domain", "x", "--public-ip", "203.0.113.10", "--turn", "peut-etre"],
            capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("--turn vaut", result.stdout)
