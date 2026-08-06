#!/usr/bin/env bash
# ══════════════════════════════════════════════════════════════════════
# FEBA — make repair
#
# Remédiation ciblée pour une installation qui a démarré mais dont
# « make install-check » signale un échec. Ne réinitialise PAS les
# données (pas de -v) : c'est « make reset » qui fait ça, et c'est
# destructif. Idempotent — relancer ne fait pas de mal.
# ══════════════════════════════════════════════════════════════════════
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
COMPOSE="docker compose"

BOLD=$'\033[1m'; GREEN=$'\033[32m'; OFF=$'\033[0m'
say() { printf "%s\n" "${BOLD}$*${OFF}"; }
ok()  { printf "%s\n" "${GREEN}  ✓ $*${OFF}"; }

say "FEBA — make repair"
echo ""

say "1/5 · Ré-application des migrations (service dédié « migrate »)"
$COMPOSE up migrate
ok "Migrations rejouées (idempotent : aucun changement si déjà à jour)"

say "2/5 · Redémarrage des services en échec"
# `docker compose up -d` ne redémarre QUE ce qui n'est pas déjà « up » à
# l'identique — un service déjà sain n'est pas perturbé.
$COMPOSE up -d postgres-dev redis-dev mailpit backend-dev celery-dev celery-beat-dev frontend-dev
ok "Services relancés"

say "3/5 · Réparation des documents officiels si nécessaire"
if ! $COMPOSE exec -T backend-dev python manage.py documents_ready --fast >/dev/null 2>&1; then
  $COMPOSE exec -T backend-dev python manage.py document_neutralize --template diploma_feba --force
  $COMPOSE exec -T backend-dev python manage.py document_neutralize --template certificate_feba --force
  $COMPOSE exec -T backend-dev python manage.py documents_ready
fi
ok "Documents officiels vérifiés"

say "4/5 · Vérification de l'identité des académies"
$COMPOSE exec -T backend-dev python manage.py branding_check || true

say "5/5 · Nouvelle vérification complète"
bash "$ROOT/scripts/install_check.sh"
