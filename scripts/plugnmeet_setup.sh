#!/usr/bin/env bash
# ══════════════════════════════════════════════════════════════════════
# Prépare plugNmeet pour FEBA : secrets, configurations, client web.
#
#   scripts/plugnmeet_setup.sh --domain pnm.globalfeba.com --public-ip 89.167.63.1
#   scripts/plugnmeet_setup.sh --local          # pile de test sur ce poste
#
# Produit plugnmeet/runtime/ (JAMAIS versionné, JAMAIS dans une archive) :
#   plugnmeet.env      secrets générés + paramètres (mode 600)
#   config.yaml        plugNmeet-server
#   livekit.yaml       LiveKit
#   nats-server.conf   NATS (clés publiques)
#   client/            client web v2.5.3, empreinte vérifiée
#
# IDEMPOTENT : un plugnmeet.env existant est CONSERVÉ (les secrets ne
# changent pas d'un lancement à l'autre ; les régénérer couperait FEBA de
# son serveur de visioconférence). --rotate-secrets force la régénération.
#
# Ce script ne démarre rien, n'ouvre aucun port, ne touche ni à Jitsi ni
# au DNS. Voir PLUGNMEET_DEPLOYMENT_GUIDE.md pour la suite.
# ══════════════════════════════════════════════════════════════════════
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PNM="$ROOT/plugnmeet"
RUNTIME="$PNM/runtime"
ENV_FILE="$RUNTIME/plugnmeet.env"

CLIENT_VERSION="v2.5.3"
CLIENT_URL="https://github.com/mynaparrot/plugNmeet-client/releases/download/${CLIENT_VERSION}/client.zip"
CLIENT_SHA256="65a89db1335c2c0262e344d1442bd3ed2697a8dd8bb2c158ddd0cdd9569099cc"
NATS_BOX_IMAGE="natsio/nats-box:0.20.0"

DOMAIN=""
PUBLIC_IP=""
# Adresse publique de FEBA, que le client plugNmeet interroge pour l'identité
# de l'académie (titre et favicon de l'onglet). --feba-url ou FEBA_PUBLIC_URL.
FEBA_URL="${FEBA_PUBLIC_URL:-}"
LOCAL=0
ROTATE=0

usage() {
  sed -n '3,8p' "${BASH_SOURCE[0]}"
  exit "${1:-0}"
}

while [ $# -gt 0 ]; do
  case "$1" in
    --domain) DOMAIN="$2"; shift 2 ;;
    --public-ip) PUBLIC_IP="$2"; shift 2 ;;
    --local) LOCAL=1; shift ;;
    --feba-url) FEBA_URL="$2"; shift 2 ;;
    --rotate-secrets) ROTATE=1; shift ;;
    -h|--help) usage 0 ;;
    *) echo "Option inconnue : $1"; usage 1 ;;
  esac
done

if [ "$LOCAL" = 1 ]; then
  DOMAIN="${DOMAIN:-localhost}"
  PUBLIC_IP="${PUBLIC_IP:-127.0.0.1}"
elif [ -z "$DOMAIN" ] || [ -z "$PUBLIC_IP" ]; then
  echo "ÉCHEC : --domain et --public-ip sont obligatoires (ou --local)."
  exit 1
fi

for tool in python3 curl unzip docker; do
  command -v "$tool" >/dev/null || { echo "ÉCHEC : « $tool » est requis."; exit 1; }
done

mkdir -p "$RUNTIME" "$RUNTIME/certs"
chmod 700 "$RUNTIME"

random_key() {  # $1 = longueur ; alphabet sans caractères spéciaux (YAML, URL)
  python3 -c "import secrets,string,sys; a=string.ascii_letters+string.digits; print(''.join(secrets.choice(a) for _ in range(int(sys.argv[1]))))" "$1"
}

nkey() {  # $1 = --account | --user | --curve ; affiche « privée publique »
  docker run --rm "$NATS_BOX_IMAGE" nsc generate nkey "$1" 2>/dev/null | tr -d '\r' | paste -sd' ' -
}

# ── 1. Secrets ────────────────────────────────────────────────────────
if [ -f "$ENV_FILE" ] && [ "$ROTATE" = 0 ]; then
  echo "Secrets existants conservés : $ENV_FILE"
else
  echo "Génération des secrets…"
  read -r CALLOUT_PRIV CALLOUT_PUB <<<"$(nkey --account)"
  read -r NKEY_PRIV NKEY_PUB <<<"$(nkey --user)"
  read -r XKEY_PRIV XKEY_PUB <<<"$(nkey --curve)"
  for v in CALLOUT_PRIV CALLOUT_PUB NKEY_PRIV NKEY_PUB XKEY_PRIV XKEY_PUB; do
    [ -n "${!v:-}" ] || { echo "ÉCHEC : génération des clés NATS ($v vide)."; exit 1; }
  done
  umask 077
  cat > "$ENV_FILE" <<EOF
# Généré par scripts/plugnmeet_setup.sh le $(date -u +%Y-%m-%dT%H:%M:%SZ).
# SECRETS — ne jamais versionner, ne jamais copier dans une archive.
PNM_API_KEY=API$(random_key 13)
PNM_API_SECRET=$(random_key 40)
LIVEKIT_API_KEY=LK$(random_key 14)
LIVEKIT_API_SECRET=$(random_key 40)
PNM_DB_ROOT_PASSWORD=$(random_key 32)
PNM_DB_PASSWORD=$(random_key 32)
PNM_REDIS_PASSWORD=$(random_key 32)
NATS_CALLOUT_PRIVATE_KEY=$CALLOUT_PRIV
NATS_CALLOUT_PUBLIC_KEY=$CALLOUT_PUB
NATS_NKEY_PRIVATE_KEY=$NKEY_PRIV
NATS_NKEY_PUBLIC_KEY=$NKEY_PUB
NATS_XKEY_PRIVATE_KEY=$XKEY_PRIV
NATS_XKEY_PUBLIC_KEY=$XKEY_PUB
EOF
fi

# ── 2. Paramètres non secrets (réécrits à chaque lancement) ──────────
python3 - "$ENV_FILE" "$DOMAIN" "$PUBLIC_IP" "$LOCAL" <<'PY'
import sys
path, domain, ip, local = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4] == "1"
keep = [l for l in open(path).read().splitlines() if not l.startswith((
    "PNM_DOMAIN=", "PNM_PUBLIC_IP=", "PNM_PUBLIC_URL=", "PNM_LIVEKIT_URL=", "PNM_NATS_WS_URL=",
    "PNM_TURN_DOMAIN=", "LIVEKIT_TURN_ENABLED=", "LIVEKIT_UDP_START=", "LIVEKIT_UDP_END=",
    "PNM_HTTP_HOST_PORT=", "PNM_LIVEKIT_HOST_PORT=", "PNM_NATS_WS_HOST_PORT=", "# --- paramètres"))]
if local:
    params = {
        "PNM_DOMAIN": domain, "PNM_PUBLIC_IP": ip,
        "PNM_PUBLIC_URL": "http://localhost:18080",
        # plugNmeet remplace host.docker.internal par localhost pour le navigateur.
        "PNM_LIVEKIT_URL": "http://host.docker.internal:7880",
        "PNM_NATS_WS_URL": "http://localhost:18222",
        "PNM_TURN_DOMAIN": "localhost", "LIVEKIT_TURN_ENABLED": "false",
        "LIVEKIT_UDP_START": "50000", "LIVEKIT_UDP_END": "50020",
        "PNM_HTTP_HOST_PORT": "18080", "PNM_LIVEKIT_HOST_PORT": "7880", "PNM_NATS_WS_HOST_PORT": "18222",
    }
else:
    params = {
        "PNM_DOMAIN": domain, "PNM_PUBLIC_IP": ip,
        "PNM_PUBLIC_URL": f"https://{domain}",
        "PNM_LIVEKIT_URL": f"https://{domain}/livekit",
        "PNM_NATS_WS_URL": f"https://{domain}/ws",
        "PNM_TURN_DOMAIN": domain, "LIVEKIT_TURN_ENABLED": "true",
        "LIVEKIT_UDP_START": "50000", "LIVEKIT_UDP_END": "50500",
        "PNM_HTTP_HOST_PORT": "8080", "PNM_LIVEKIT_HOST_PORT": "7880", "PNM_NATS_WS_HOST_PORT": "8222",
    }
keep.append("# --- paramètres (réécrits à chaque lancement)")
keep += [f"{k}={v}" for k, v in params.items()]
open(path, "w").write("\n".join(keep) + "\n")
PY
chmod 600 "$ENV_FILE"

# ── 3. Rendu des modèles : toute variable manquante est une erreur ───
python3 - "$ENV_FILE" "$PNM/templates" "$RUNTIME" <<'PY'
import re, sys, pathlib
env = {}
for line in open(sys.argv[1]):
    line = line.strip()
    if line and not line.startswith("#") and "=" in line:
        k, v = line.split("=", 1)
        env[k] = v
src, dst = pathlib.Path(sys.argv[2]), pathlib.Path(sys.argv[3])
for tpl in sorted(src.glob("*.tpl")):
    text = tpl.read_text()
    missing = sorted({m for m in re.findall(r"\$\{([A-Z0-9_]+)\}", text) if not env.get(m)})
    if missing:
        sys.exit(f"ÉCHEC : variables manquantes pour {tpl.name} : {', '.join(missing)}")
    out = re.sub(r"\$\{([A-Z0-9_]+)\}", lambda m: env[m.group(1)], text)
    target = dst / tpl.name[:-4]
    target.write_text(out)
    target.chmod(0o600)
    print(f"  rendu : {target.relative_to(dst.parent.parent)}")
PY
# Les conteneurs lisent ces fichiers sous un autre utilisateur.
chmod 644 "$RUNTIME/nats-server.conf" "$RUNTIME/livekit.yaml" "$RUNTIME/config.yaml" "$RUNTIME/pnm-web.conf"

# ── 4. Client web, version figée, empreinte vérifiée ─────────────────
if [ -f "$RUNTIME/client/.version" ] && [ "$(cat "$RUNTIME/client/.version")" = "$CLIENT_VERSION" ]; then
  echo "Client $CLIENT_VERSION déjà installé."
else
  tmp="$(mktemp -d)"
  trap 'rm -rf "$tmp"' EXIT
  echo "Téléchargement du client $CLIENT_VERSION…"
  curl -fsSL --max-time 300 -o "$tmp/client.zip" "$CLIENT_URL"
  got="$(python3 -c "import hashlib,sys; print(hashlib.sha256(open(sys.argv[1],'rb').read()).hexdigest())" "$tmp/client.zip")"
  if [ "$got" != "$CLIENT_SHA256" ]; then
    echo "ÉCHEC : empreinte du client inattendue ($got). Rien n'est installé."
    exit 1
  fi
  unzip -q "$tmp/client.zip" -d "$tmp"
  rm -rf "$RUNTIME/client"
  mv "$tmp/client" "$RUNTIME/client"
  echo "$CLIENT_VERSION" > "$RUNTIME/client/.version"
fi
PUBLIC_URL="$(grep '^PNM_PUBLIC_URL=' "$ENV_FILE" | cut -d= -f2-)"
cp "$RUNTIME/client/dist/assets/config_sample.js" "$RUNTIME/client/dist/assets/config.js"
python3 - "$RUNTIME/client/dist/assets/config.js" "$PUBLIC_URL" <<'PY'
import re, sys
p, url = sys.argv[1], sys.argv[2]
s = open(p).read()
s, n = re.subn(r"serverUrl:\s*'[^']*'", f"serverUrl: '{url}'", s, count=1)
if n != 1:
    sys.exit("ÉCHEC : serverUrl introuvable dans config.js du client.")
open(p, "w").write(s)
PY

# ── Identité FEBA de l'onglet (titre exact et favicon par académie) ─────
# Le client plugNmeet impose le nom de la salle comme titre d'onglet ; le
# script FEBA, recopié dans le client et référencé par son index.html, le
# remplace par l'identité de l'académie de la salle (vérifiée par FEBA à
# partir du jeton signé). Reconstruit à chaque exécution : rien n'est
# modifié à la main dans un conteneur.
if [ -z "$FEBA_URL" ]; then
  FEBA_URL="$(grep '^FEBA_PUBLIC_URL=' "$ENV_FILE" 2>/dev/null | cut -d= -f2- || true)"
fi
if [ -z "$FEBA_URL" ]; then
  if [ "$LOCAL" = 1 ]; then FEBA_URL="http://localhost:5173"; else FEBA_URL="https://globalfeba.com"; fi
fi
grep -q '^FEBA_PUBLIC_URL=' "$ENV_FILE" || echo "FEBA_PUBLIC_URL=$FEBA_URL" >> "$ENV_FILE"
mkdir -p "$RUNTIME/client/dist/assets/feba"
cp "$PNM/client-branding/feba-branding.js" "$RUNTIME/client/dist/assets/feba/feba-branding.js"
python3 - "$RUNTIME/client/dist/index.html" "$FEBA_URL" <<'PY'
import html, re, sys
p, feba = sys.argv[1], sys.argv[2]
s = open(p).read()
s = re.sub(r"\n?\s*<!-- feba-branding:start -->.*?<!-- feba-branding:end -->", "", s, flags=re.S)
block = ('\n    <!-- feba-branding:start -->\n'
         f'    <script src="./assets/feba/feba-branding.js" data-feba-api="{html.escape(feba, quote=True)}"></script>\n'
         '    <!-- feba-branding:end -->')
s, n = re.subn(r"(<title>[^<]*</title>)", lambda m: m.group(1) + block, s, count=1)
if n != 1:
    sys.exit("ÉCHEC : <title> introuvable dans index.html du client.")
open(p, "w").write(s)
PY
echo "Identité FEBA de l'onglet installée (API : $FEBA_URL)."
# Le serveur plugNmeet garde index.html en mémoire depuis son démarrage : un
# conteneur déjà lancé doit être redémarré pour servir le client modifié.
for c in $(docker ps --format '{{.Names}}' 2>/dev/null | grep -E 'plugnmeet-1$|pnm-plugnmeet' || true); do
  docker restart "$c" >/dev/null && echo "Conteneur $c redémarré (client personnalisé servi)."
done

cat <<EOF

Prêt. Paramètres pour le backend FEBA (.env.prod) — sans les recopier
ailleurs que dans ce fichier :
  VIDEO_PROVIDER=plugnmeet
  PLUGNMEET_SERVER_URL=$PUBLIC_URL
  PLUGNMEET_API_KEY=<PNM_API_KEY de $ENV_FILE>
  PLUGNMEET_API_SECRET=<PNM_API_SECRET de $ENV_FILE>

Démarrage :
  docker compose -p feba-pnm -f plugnmeet/docker-compose.plugnmeet.yml --env-file plugnmeet/runtime/plugnmeet.env up -d
EOF
