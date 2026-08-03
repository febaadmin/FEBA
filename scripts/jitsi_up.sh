#!/usr/bin/env bash
# ══════════════════════════════════════════════════════════════════════
# make jitsi-up — démarre l'instance Jitsi AUTO-HÉBERGÉE.
#
# Contrairement à la version précédente, ce script ne s'arrête plus en
# demandant à l'utilisateur de copier un fichier et de générer des secrets
# à la main : il fait les deux. La seule action manuelle restante en
# production est le pointage DNS, impossible à automatiser depuis
# l'application (voir DEPLOYMENT_GUIDE.md).
# ══════════════════════════════════════════════════════════════════════
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

GREEN=$'\033[32m'; YELLOW=$'\033[33m'; RED=$'\033[31m'; BOLD=$'\033[1m'; OFF=$'\033[0m'
JITSI_ENV="$ROOT/.env.jitsi"

command -v docker >/dev/null 2>&1 || { echo "${RED}Docker est requis.${OFF}"; exit 1; }
docker info >/dev/null 2>&1 || { echo "${RED}Le démon Docker ne répond pas.${OFF}"; exit 1; }
command -v openssl >/dev/null 2>&1 || { echo "${RED}openssl est requis.${OFF}"; exit 1; }

# ── Secrets : générés s'ils manquent, JAMAIS régénérés s'ils existent ──
# Régénérer invaliderait les jetons en circulation et couperait les cours
# en cours de séance.
if [ ! -f "$JITSI_ENV" ]; then
  printf '# Secrets Jitsi générés automatiquement — NE PAS COMMITTER\n' > "$JITSI_ENV"
  echo "${YELLOW}Création de .env.jitsi${OFF}"
fi

add_secret() {
  local key="$1" len="$2"
  grep -qE "^${key}=.+" "$JITSI_ENV" 2>/dev/null && return 0
  printf '%s=%s\n' "$key" "$(openssl rand -hex "$len")" >> "$JITSI_ENV"
  echo "  + $key généré"
}

grep -qE '^JITSI_APP_ID=.+' "$JITSI_ENV" 2>/dev/null || \
  printf 'JITSI_APP_ID=feba_%s\n' "$(openssl rand -hex 6)" >> "$JITSI_ENV"

add_secret JITSI_APP_SECRET 32
add_secret JICOFO_COMPONENT_SECRET 16
add_secret JICOFO_AUTH_PASSWORD 16
add_secret JVB_AUTH_PASSWORD 16
add_secret JIGASI_XMPP_PASSWORD 16
add_secret JIBRI_RECORDER_PASSWORD 16
add_secret JIBRI_XMPP_PASSWORD 16
add_secret TURN_SECRET 16

PORT="${JITSI_HTTP_PORT:-8443}"
grep -qE '^JITSI_HTTP_PORT=' "$JITSI_ENV" || printf 'JITSI_HTTP_PORT=%s\n' "$PORT" >> "$JITSI_ENV"
grep -qE '^JITSI_HTTPS_PORT=' "$JITSI_ENV" || printf 'JITSI_HTTPS_PORT=8444\n' >> "$JITSI_ENV"
grep -qE '^JITSI_PUBLIC_URL=' "$JITSI_ENV" || printf 'JITSI_PUBLIC_URL=http://localhost:%s\n' "$PORT" >> "$JITSI_ENV"
# IPv6 désactivé par défaut : nginx boucle au démarrage sur les hôtes
# sans pile IPv6 (le conteneur paraît « running » mais ne répond jamais).
grep -qE '^ENABLE_IPV6=' "$JITSI_ENV" || printf 'ENABLE_IPV6=0\n' >> "$JITSI_ENV"
chmod 600 "$JITSI_ENV"

PORT="$(grep -E '^JITSI_HTTP_PORT=' "$JITSI_ENV" | head -1 | cut -d= -f2-)"

echo "${BOLD}Démarrage de la pile Jitsi auto-hébergée…${OFF}"
docker compose -f docker-compose.jitsi.yml --env-file "$JITSI_ENV" up -d

# ── Attente d'une VRAIE réponse HTTP ──────────────────────────────────
echo -n "Attente de l'instance"
READY=0
for _ in $(seq 1 60); do
  if curl -fsS -o /dev/null "http://localhost:${PORT}/" 2>/dev/null; then READY=1; break; fi
  echo -n "."
  sleep 2
done
echo

if [ "$READY" -ne 1 ]; then
  echo "${RED}✗ L'instance n'a pas répondu.${OFF}"
  echo "  Diagnostic : make jitsi-logs"
  echo "  Cause fréquente : hôte sans IPv6 → vérifiez ENABLE_IPV6=0 dans .env.jitsi."
  exit 1
fi

APP_ID="$(grep -E '^JITSI_APP_ID=' "$JITSI_ENV" | head -1 | cut -d= -f2-)"
cat <<EOF
${GREEN}${BOLD}✅ Instance Jitsi auto-hébergée opérationnelle${OFF}

  URL           http://localhost:${PORT}
  APP_ID        ${APP_ID}
  Authentification  JWT obligatoire (allow_empty_token = false)

  Le backend lit ces mêmes valeurs depuis .env. Vérification :
      make jitsi-health
EOF
