#!/usr/bin/env bash
# ============================================================
# FEBA v8 — Vérification automatique Parent ↔ Élève
# Usage : ./scripts/verify_parent_eleve.sh
# Retourne 0 si tout est OK, non-zéro sinon.
# ============================================================
set -euo pipefail

COMPOSE_FILE="docker-compose.yml"
BACKEND="backend-dev"
CSV_OUTPUT="/tmp/incoherences_parent_eleve.csv"
EXIT_CODE=0

log()  { echo -e "\033[1;34m[FEBA]\033[0m $*"; }
ok()   { echo -e "\033[1;32m[  OK]\033[0m $*"; }
fail() { echo -e "\033[1;31m[FAIL]\033[0m $*"; EXIT_CODE=1; }

# ── 1. Build & start ────────────────────────────────────────
log "Démarrage des conteneurs…"
docker-compose -f "$COMPOSE_FILE" up --build -d
sleep 5   # laisser le temps à la DB de démarrer

# ── 2. Migrations ────────────────────────────────────────────
log "Application des migrations…"
if docker-compose -f "$COMPOSE_FILE" exec "$BACKEND" \
      python manage.py migrate --no-input; then
  ok "Migrations appliquées."
else
  fail "Échec des migrations."
fi

# ── 3. Tests ciblés Parent ↔ Élève ───────────────────────────
log "Exécution des tests Parent ↔ Élève…"
if docker-compose -f "$COMPOSE_FILE" exec "$BACKEND" \
      python manage.py test tests.test_parent_student \
        apps.parents apps.students \
        --verbosity=2 2>&1; then
  ok "Tous les tests passent."
else
  fail "Des tests ont échoué."
fi

# ── 4. Détection des incohérences ────────────────────────────
log "Détection des incohérences Parent ↔ Élève…"
if docker-compose -f "$COMPOSE_FILE" exec "$BACKEND" \
      python manage.py detect_incoherences_parent_eleve \
        --output "$CSV_OUTPUT"; then
  ok "Aucune incohérence détectée."
else
  fail "Des incohérences ont été détectées. Voir: $CSV_OUTPUT"
  # Copier le CSV dans le répertoire courant pour inspection
  docker-compose -f "$COMPOSE_FILE" exec "$BACKEND" cat "$CSV_OUTPUT" \
    > incoherences_parent_eleve.csv 2>/dev/null || true
fi

# ── Résumé ───────────────────────────────────────────────────
echo ""
if [ "$EXIT_CODE" -eq 0 ]; then
  ok "════════════════════════════════════════"
  ok "  Toutes les vérifications ont réussi."
  ok "════════════════════════════════════════"
else
  fail "════════════════════════════════════════"
  fail "  Une ou plusieurs vérifications ont échoué."
  fail "  Consultez les logs ci-dessus."
  fail "════════════════════════════════════════"
fi

exit "$EXIT_CODE"
