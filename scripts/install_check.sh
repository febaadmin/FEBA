#!/usr/bin/env bash
# ══════════════════════════════════════════════════════════════════════
# FEBA — make install-check
#
# Étape 12/12 : l'installation a-t-elle RÉELLEMENT réussi ? Vérifie
# chaque point du scénario final bloquant de la demande d'origine —
# pas seulement « les conteneurs tournent », mais healthy, migré,
# joignable, sans doublon.
# ══════════════════════════════════════════════════════════════════════
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
COMPOSE="docker compose"

BOLD=$'\033[1m'; GREEN=$'\033[32m'; YELLOW=$'\033[33m'; RED=$'\033[31m'; OFF=$'\033[0m'
FAILURES=0
say()  { printf "%s\n" "${BOLD}$*${OFF}"; }
ok()   { printf "%s\n" "${GREEN}  ✓ $*${OFF}"; }
bad()  { printf "%s\n" "${RED}  ✗ $*${OFF}"; FAILURES=$((FAILURES + 1)); }

say "FEBA — make install-check"
echo ""

# ── Services attendus « healthy » ───────────────────────────────────
say "État des conteneurs"
for svc in postgres-dev redis-dev mailpit backend-dev celery-dev celery-beat-dev frontend-dev; do
  status="$($COMPOSE ps --format '{{.Health}}' "$svc" 2>/dev/null | head -1)"
  case "$status" in
    healthy) ok "$svc : healthy" ;;
    "")      bad "$svc : pas de statut de santé (conteneur absent ou sans healthcheck) — voir 'make ps'" ;;
    *)       bad "$svc : $status (attendu : healthy)" ;;
  esac
done
echo ""

# ── Migrations : aucune en attente ──────────────────────────────────
say "Migrations"
if $COMPOSE exec -T backend-dev python manage.py migrate --check --noinput >/tmp/feba_migrate_check.log 2>&1; then
  ok "Aucune migration en attente"
else
  bad "Des migrations sont en attente — voir /tmp/feba_migrate_check.log"
fi
echo ""

# ── Isolation multi-académies ────────────────────────────────────────
say "Isolation multi-académies"
if $COMPOSE exec -T backend-dev python manage.py seed_check >/tmp/feba_seed_check.log 2>&1; then
  ok "seed_check : aucune fuite inter-académies détectée"
else
  bad "seed_check a signalé un problème — voir /tmp/feba_seed_check.log"
fi
echo ""

# ── Documents officiels ──────────────────────────────────────────────
say "Documents officiels"
if $COMPOSE exec -T backend-dev python manage.py documents_ready >/tmp/feba_documents_ready.log 2>&1; then
  ok "Diplômes et certificats produisibles"
else
  bad "documents_ready a échoué — voir /tmp/feba_documents_ready.log"
fi
echo ""

# ── Jitsi ─────────────────────────────────────────────────────────────
say "Jitsi"
if $COMPOSE exec -T backend-dev python manage.py jitsi_health >/tmp/feba_jitsi_health.log 2>&1; then
  ok "Jitsi opérationnel (configuration, signature de jeton, instance joignable)"
else
  bad "jitsi_health a échoué — voir /tmp/feba_jitsi_health.log ou 'make jitsi-health'"
fi
echo ""

# ── Celery ────────────────────────────────────────────────────────────
say "Celery"
if $COMPOSE exec -T celery-dev celery -A feba_project inspect ping >/tmp/feba_celery_ping.log 2>&1; then
  ok "celery inspect ping a répondu"
else
  bad "celery inspect ping n'a pas répondu — voir /tmp/feba_celery_ping.log"
fi
echo ""

# ── Idempotence : rejouer migrate --plan doit rester vide ───────────
say "Idempotence"
PLAN="$($COMPOSE exec -T backend-dev python manage.py migrate --plan 2>&1)"
if echo "$PLAN" | grep -q "No planned migration operations"; then
  ok "migrate --plan : No planned migration operations."
else
  bad "migrate --plan signale des opérations en attente :"
  echo "$PLAN" | sed 's/^/      /'
fi
echo ""

if [ "$FAILURES" -eq 0 ]; then
  say "${GREEN}✅ Installation vérifiée — tous les contrôles sont au vert.${OFF}"
  exit 0
else
  say "${RED}✗ $FAILURES contrôle(s) en échec. 'make repair' peut aider, sinon 'make diagnose'.${OFF}"
  exit 1
fi
