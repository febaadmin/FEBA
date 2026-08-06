#!/usr/bin/env bash
# ══════════════════════════════════════════════════════════════════════
# tests/installation/test_clean_docker_install.sh
#
# Teste une installation RÉELLE depuis une archive, sur la machine où ce
# script s'exécute — Linux x86_64, Linux ARM64, et macOS Apple Silicon
# avec Docker Desktop sont couverts par construction : le script n'utilise
# que docker, docker compose, bash et openssl (jamais de python local,
# voir P6), et toutes les images de docker-compose.yml sont multi-arch
# (postgres:16-alpine, redis:7-alpine, jitsi/*:stable, node/python via
# Dockerfile.dev). Il n'y a donc pas de variante par OS à maintenir
# séparément : le même script, sur trois machines différentes, exerce
# trois fois le même chemin réel.
#
# CE QUE CE SCRIPT NE PEUT PAS FAIRE
# -----------------------------------
# Il a besoin d'un démon Docker. Sans lui, il échoue à l'étape 0 avec un
# message clair plutôt qu'en pleine installation. C'est la seule
# dépendance : aucune commande de ce script n'exige Python, Node, ou quoi
# que ce soit d'autre sur la machine hôte.
#
# USAGE
#   ./tests/installation/test_clean_docker_install.sh /chemin/vers/archive.zip
#   ./tests/installation/test_clean_docker_install.sh --in-place   # utilise le dépôt courant
# ══════════════════════════════════════════════════════════════════════
set -uo pipefail

BOLD=$'\033[1m'; GREEN=$'\033[32m'; YELLOW=$'\033[33m'; RED=$'\033[31m'; OFF=$'\033[0m'
FAILURES=0
STEP=0

say()  { STEP=$((STEP + 1)); printf "\n%s\n" "${BOLD}[$STEP] $*${OFF}"; }
ok()   { printf "%s\n" "${GREEN}  ✓ $*${OFF}"; }
bad()  { printf "%s\n" "${RED}  ✗ $*${OFF}"; FAILURES=$((FAILURES + 1)); }
fatal(){ printf "%s\n" "${RED}✗ FATAL : $*${OFF}"; exit 1; }

ARCHIVE="${1:-}"
WORKDIR=""
CLEANUP_WORKDIR=0

# ── 0. Prérequis ─────────────────────────────────────────────────────
say "Prérequis"
command -v docker >/dev/null 2>&1 || fatal "docker introuvable."
docker compose version >/dev/null 2>&1 || fatal "docker compose (plugin v2) introuvable."
docker info >/dev/null 2>&1 || fatal "le démon Docker ne répond pas."
ok "docker $(docker --version | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1) — $(uname -sm)"

# ── 1. Extraction depuis une archive propre ─────────────────────────
say "Préparation de l'arborescence de test"
if [ "$ARCHIVE" = "--in-place" ]; then
  WORKDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
  ok "Mode --in-place : $WORKDIR"
elif [ -n "$ARCHIVE" ] && [ -f "$ARCHIVE" ]; then
  WORKDIR="$(mktemp -d)"
  CLEANUP_WORKDIR=1
  unzip -q "$ARCHIVE" -d "$WORKDIR" || fatal "extraction de $ARCHIVE échouée."
  # Une archive .zip contient en général un dossier racine unique.
  INNER="$(find "$WORKDIR" -mindepth 1 -maxdepth 1 -type d | head -1)"
  [ -n "$INNER" ] && WORKDIR="$INNER"
  ok "Archive extraite dans $WORKDIR"
else
  fatal "Usage : $0 <archive.zip> | --in-place"
fi
cd "$WORKDIR" || fatal "impossible d'entrer dans $WORKDIR"
[ -f "docker-compose.yml" ] || fatal "docker-compose.yml introuvable — mauvaise archive ?"

cleanup() {
  if [ "$CLEANUP_WORKDIR" -eq 1 ] && [ -n "$WORKDIR" ]; then
    (cd "$WORKDIR" && docker compose down -v --remove-orphans >/dev/null 2>&1)
    rm -rf "$WORKDIR"
  fi
}
trap cleanup EXIT

# ── 2. Nettoyage Docker ──────────────────────────────────────────────
say "Nettoyage de tout environnement Docker précédent"
docker compose down -v --remove-orphans >/dev/null 2>&1
ok "Environnement nettoyé (docker compose down -v --remove-orphans)"

# ── 3. Installation ──────────────────────────────────────────────────
say "make install"
if make install; then
  ok "make install a réussi"
else
  bad "make install a échoué"
fi

# ── 4. Services healthy ──────────────────────────────────────────────
say "État des services"
for svc in postgres-dev redis-dev mailpit backend-dev celery-dev celery-beat-dev frontend-dev; do
  status="$(docker compose ps --format '{{.Health}}' "$svc" 2>/dev/null | head -1)"
  if [ "$status" = "healthy" ]; then
    ok "$svc : healthy"
  else
    bad "$svc : ${status:-absent} (attendu healthy)"
  fi
done

# ── 5. Migrations : aucune en attente ────────────────────────────────
say "Migrations"
PLAN="$(docker compose exec -T backend-dev python manage.py migrate --plan 2>&1)"
if echo "$PLAN" | grep -q "No planned migration operations"; then
  ok "migrate --plan : No planned migration operations."
else
  bad "migrations en attente :"
  echo "$PLAN" | sed 's/^/      /'
fi

# ── 6. Seed + isolation multi-académies ─────────────────────────────
say "Données de démonstration et isolation"
if make seed >/dev/null 2>&1; then ok "make seed a réussi"; else bad "make seed a échoué"; fi
if make seed-check >/dev/null 2>&1; then
  ok "make seed-check : aucune fuite inter-académies"
else
  bad "make seed-check a signalé un problème d'isolation"
fi

# ── 7. Documents officiels ───────────────────────────────────────────
say "Documents officiels"
if make documents-ready >/dev/null 2>&1; then
  ok "documents-ready : diplômes et certificats produisibles"
else
  bad "documents-ready a échoué"
fi
if make branding-check >/dev/null 2>&1; then
  ok "branding-check : identité des académies cohérente"
else
  bad "branding-check a échoué"
fi

# ── 8. Frontend réellement joignable ─────────────────────────────────
say "Frontend"
if curl -fsS -o /dev/null --max-time 10 http://localhost:5173/; then
  ok "http://localhost:5173/ répond"
else
  bad "http://localhost:5173/ ne répond pas"
fi

# ── 9. API réellement joignable ──────────────────────────────────────
say "API"
API_STATUS="$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 http://localhost:8000/api/ || echo 000)"
if [ "$API_STATUS" != "000" ]; then
  ok "http://localhost:8000/api/ répond (HTTP $API_STATUS)"
else
  bad "http://localhost:8000/api/ ne répond pas"
fi

# ── 10. Celery ────────────────────────────────────────────────────────
say "Celery"
if docker compose exec -T celery-dev celery -A feba_project inspect ping >/dev/null 2>&1; then
  ok "celery inspect ping a répondu"
else
  bad "celery inspect ping n'a pas répondu"
fi

# ── 11. Mailpit ───────────────────────────────────────────────────────
say "Mailpit"
if curl -fsS -o /dev/null --max-time 10 http://localhost:8025/; then
  ok "http://localhost:8025/ (interface Mailpit) répond"
else
  bad "Mailpit ne répond pas sur http://localhost:8025/"
fi

# ── 12. Jitsi (si démarré) ───────────────────────────────────────────
say "Jitsi"
if docker compose exec -T backend-dev python manage.py jitsi_health >/tmp/feba_ci_jitsi.log 2>&1; then
  ok "jitsi_health : opérationnel"
elif grep -q "n'est pas configuré" /tmp/feba_ci_jitsi.log 2>/dev/null; then
  echo "  · Jitsi non démarré (make jitsi-up non exécuté) — ignoré, pas un échec de ce test."
else
  bad "jitsi_health a échoué — voir /tmp/feba_ci_jitsi.log"
fi

# ── 13. Idempotence : réinstaller ne doit rien casser ────────────────
say "Idempotence — second make install"
if make install >/tmp/feba_ci_second_install.log 2>&1; then
  ok "Second make install réussi sans erreur"
else
  bad "Le second make install a échoué — voir /tmp/feba_ci_second_install.log"
fi
PLAN2="$(docker compose exec -T backend-dev python manage.py migrate --plan 2>&1)"
if echo "$PLAN2" | grep -q "No planned migration operations"; then
  ok "Toujours aucune migration en attente après réinstallation"
else
  bad "Des migrations sont réapparues après réinstallation — doublon probable"
fi

# ── Résumé ────────────────────────────────────────────────────────────
echo ""
echo "══════════════════════════════════════════════════════"
if [ "$FAILURES" -eq 0 ]; then
  echo "${GREEN}${BOLD}✅ Installation propre validée sur $(uname -sm) — $STEP étapes, 0 échec.${OFF}"
  exit 0
else
  echo "${RED}${BOLD}✗ $FAILURES échec(s) sur $(uname -sm). Voir le détail ci-dessus.${OFF}"
  exit 1
fi
