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
