#!/bin/bash
# FEBA v29 — Script de diagnostic
# Usage: bash scripts/diagnose.sh
# (ou: make diagnose)
#
# À lancer en PREMIER dès qu'un conteneur ne démarre pas ou disparaît
# de `docker compose ps`. Affiche tout ce qu'il faut pour comprendre
# la cause réelle en un seul coup d'œil.

set -uo pipefail
COMPOSE="docker compose -f docker-compose.yml"

echo "========================================================="
echo "  FEBA v29 — Diagnostic"
echo "========================================================="

echo ""
echo ">>> État de tous les conteneurs (y compris arrêtés) :"
$COMPOSE ps -a

echo ""
echo ">>> Code de sortie du conteneur backend-dev (si arrêté) :"
docker inspect feba_backend_dev --format 'Status: {{.State.Status}} | ExitCode: {{.State.ExitCode}} | Error: {{.State.Error}}' 2>&1 || echo "  Conteneur feba_backend_dev introuvable (jamais démarré ?)"

echo ""
echo "========================================================="
echo "  Logs backend-dev (les 150 dernières lignes)"
echo "  -> C'est ICI que se trouve la cause réelle d'un crash."
echo "========================================================="
$COMPOSE logs --tail=150 backend-dev 2>&1

echo ""
echo "========================================================="
echo "  Logs celery-dev (les 50 dernières lignes)"
echo "========================================================="
$COMPOSE logs --tail=50 celery-dev 2>&1

echo ""
echo ">>> Test de connexion PostgreSQL :"
$COMPOSE exec -T postgres-dev pg_isready -U feba_user -d feba_dev 2>&1 || echo "  PostgreSQL non accessible."

echo ""
echo ">>> Test de connexion Redis :"
$COMPOSE exec -T redis-dev redis-cli ping 2>&1 || echo "  Redis non accessible."

echo ""
echo ">>> Variables d'environnement chargées par backend-dev (DATABASE_URL masqué) :"
$COMPOSE exec -T backend-dev env 2>&1 | grep -E "^(DJANGO_ENV|ALLOWED_HOSTS|REDIS_URL)" || echo "  Impossible de lire l'environnement (conteneur probablement arrêté)."

echo ""
echo "========================================================="
echo "  Fin du diagnostic."
echo "  Si le problème persiste, copiez TOUTE cette sortie."
echo "========================================================="
