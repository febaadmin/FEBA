#!/usr/bin/env bash
# ══════════════════════════════════════════════════════════════════════
# Déploiement de l'application FEBA (backend, worker, Beat, frontend, nginx).
#
#   scripts/deploy_feba.sh              déploie la version présente
#   scripts/deploy_feba.sh --rollback   revient aux images précédentes
#
# Étapes (chacune s'arrête à la première erreur, avec la raison) :
#   1. prérequis (Docker Compose v2, .env.prod présent et protégé, espace disque)
#   2. validation : Compose résolu avec --env-file, puis CONTRÔLE DE
#      PRÉ-DÉMARRAGE exécuté sur la NOUVELLE image avant toute bascule
#   3. certificat TLS présent pour le domaine (sinon : scripts/tls_bootstrap.sh)
#   4. sauvegarde de la base (pg_dump compressé, intégrité vérifiée)
#   5. images actuelles marquées « previous » (retour arrière)
#   6. construction et démarrage
#   7. attente des contrôles de santé, tests de fumée, empreinte de
#      configuration identique sur backend / worker / Beat
#   8. en cas d'échec : retour arrière AUTOMATIQUE vers « previous »
#
# IDEMPOTENT : aucun volume supprimé, aucun secret généré ou modifié, les
# migrations sont celles de la version (additives dans cette livraison).
#
# Variables facultatives (essais, préproduction) :
#   FEBA_ENV_FILE (.env.prod) · FEBA_PROJECT (nom Compose, pile d'essai seulement) ·
#   FEBA_COMPOSE_FILES (« -f docker-compose.prod.yml ») · FEBA_HTTPS_PORT (443) ·
#   FEBA_LETSENCRYPT_DIR (/etc/letsencrypt) · FEBA_BACKUP_DIR (./backups)
# ══════════════════════════════════════════════════════════════════════
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

ENV_FILE="${FEBA_ENV_FILE:-.env.prod}"
# Nom de projet Compose : celui par défaut (dossier), comme le workflow
# .github/workflows/deploy.yml — en imposer un autre créerait une SECONDE pile
# avec des volumes vides. FEBA_PROJECT seulement pour une pile d'essai.
PROJECT="${FEBA_PROJECT:-}"
COMPOSE_FILES="${FEBA_COMPOSE_FILES:--f docker-compose.prod.yml}"
HTTPS_PORT="${FEBA_HTTPS_PORT:-443}"
LE_DIR="${FEBA_LETSENCRYPT_DIR:-/etc/letsencrypt}"
BACKUP_DIR="${FEBA_BACKUP_DIR:-$ROOT/backups}"
ROLLBACK=0
[ "${1:-}" = "--rollback" ] && ROLLBACK=1

# shellcheck disable=SC2086
dc() { docker compose ${PROJECT:+-p "$PROJECT"} --env-file "$ENV_FILE" $COMPOSE_FILES "$@"; }
ok()   { printf '  \033[32mOK\033[0m    %s\n' "$*"; }
step() { printf '\n\033[1m[%s] %s\033[0m\n' "$1" "$2"; }
fail() { printf '  \033[31mÉCHEC\033[0m %s\n' "$*"; exit 1; }
envval() { grep -E "^$1=" "$ENV_FILE" | tail -1 | cut -d= -f2-; }

wait_healthy() {
  local services=(backend-prod celery-prod celery-beat) deadline=$((SECONDS + 420))
  while [ $SECONDS -lt $deadline ]; do
    local all=1
    for s in "${services[@]}"; do
      id="$(dc ps -q "$s" 2>/dev/null)"
      [ -n "$id" ] || { all=0; continue; }
      st="$(docker inspect -f '{{.State.Health.Status}}' "$id" 2>/dev/null || echo absent)"
      [ "$st" = "healthy" ] || all=0
      if [ "$(docker inspect -f '{{.State.Status}}' "$id" 2>/dev/null)" = "exited" ]; then
        echo "  Service $s arrêté — journal :"; docker logs --tail 25 "$id" 2>&1 | sed 's/^/    /'
        return 1
      fi
    done
    [ $all = 1 ] && return 0
    sleep 5
  done
  return 1
}

smoke() {
  local domain; domain="$(envval ALLOWED_HOSTS | cut -d, -f1)"
  local base="https://$domain:$HTTPS_PORT"
  local resolve="--resolve $domain:$HTTPS_PORT:127.0.0.1"
  # shellcheck disable=SC2086
  [ "$(curl -sk $resolve -o /dev/null -w '%{http_code}' "$base/api/health/")" = 200 ] || { echo "  /api/health/ ne répond pas 200"; return 1; }
  ok "/api/health/ via nginx (HTTPS)"
  # shellcheck disable=SC2086
  [ "$(curl -sk $resolve -o /dev/null -w '%{http_code}' "$base/")" = 200 ] || { echo "  page d'accueil ≠ 200"; return 1; }
  ok "page d'accueil"
  # shellcheck disable=SC2086
  [ "$(curl -sk $resolve -o /dev/null -w '%{http_code}' "$base/api/auth/me/")" = 401 ] || { echo "  /api/auth/me/ sans jeton ≠ 401"; return 1; }
  ok "API protégée (401 sans jeton)"
  local fb fc fbeat
  fb="$(dc exec -T backend-prod python manage.py production_preflight --fingerprint </dev/null)"
  fc="$(dc exec -T celery-prod python manage.py production_preflight --fingerprint </dev/null)"
  fbeat="$(dc exec -T celery-beat python manage.py production_preflight --fingerprint </dev/null)"
  [ "$fb" = "$fc" ] && [ "$fb" = "$fbeat" ] || { echo "  configurations différentes : backend $fb, worker $fc, Beat $fbeat"; return 1; }
  ok "même configuration sur backend, worker et Beat ($fb)"
  # Sortie capturée AVANT le filtrage : avec pipefail, « … | grep -q »
  # interrompt celery (SIGPIPE) et ferait échouer un contrôle réussi.
  local pong
  pong="$(dc exec -T celery-prod sh -c 'celery -A feba_project inspect ping -d celery@$HOSTNAME --timeout 10' </dev/null 2>&1 || true)"
  case "$pong" in *pong*) ;; *) echo "  le worker Celery ne répond pas : $pong"; return 1 ;; esac
  ok "worker Celery répond"
}

rollback() {
  step "R" "Retour arrière vers les images précédentes"
  docker image inspect feba-backend:previous >/dev/null 2>&1 || fail "Aucune image « previous » : retour arrière impossible."
  docker tag feba-backend:previous feba-backend:current
  docker tag feba-frontend:previous feba-frontend:current
  FEBA_IMAGE_TAG=current dc up -d --no-build
  dc exec -T nginx-prod nginx -s reload </dev/null >/dev/null 2>&1 || true
  wait_healthy && ok "version précédente rétablie" || fail "la version précédente ne redevient pas saine : intervention requise"
}

if [ $ROLLBACK = 1 ]; then rollback; exit 0; fi

step 1 "Prérequis"
docker compose version >/dev/null 2>&1 || fail "Docker Compose v2 requis."
[ -f "$ENV_FILE" ] || fail "$ENV_FILE absent : copiez .env.prod.example et renseignez-le."
chmod 600 "$ENV_FILE"; ok "$ENV_FILE présent (mode 600)"
free_gb=$(df -Pk "$ROOT" | awk 'NR==2 {print int($4/1048576)}')
[ "$free_gb" -ge 5 ] || fail "espace disque insuffisant (${free_gb} Go < 5 Go)"
ok "espace disque : ${free_gb} Go libres"

step 2 "Validation de la configuration"
dc config --quiet || fail "composition invalide avec $ENV_FILE"
ok "composition résolue"
FEBA_IMAGE_TAG=candidate dc build backend-prod frontend-prod
FEBA_IMAGE_TAG=candidate dc run --rm --no-deps -T backend-prod python manage.py production_preflight </dev/null \
  || fail "contrôle de pré-démarrage refusé (voir ci-dessus) : rien n'a été modifié."
ok "contrôle de pré-démarrage accepté sur la nouvelle image"

step 3 "Certificat TLS"
domain="$(envval ALLOWED_HOSTS | cut -d, -f1)"
[ -s "$LE_DIR/live/$domain/fullchain.pem" ] || fail "certificat absent pour $domain : lancez scripts/tls_bootstrap.sh"
ok "certificat présent pour $domain"
mkdir -p /var/www/certbot 2>/dev/null || true

step 4 "Sauvegarde de la base"
mkdir -p "$BACKUP_DIR"
if [ -n "$(dc ps -q postgres-prod 2>/dev/null)" ]; then
  file="$BACKUP_DIR/feba-$(date -u +%Y%m%d-%H%M%S).sql.gz"
  dc exec -T postgres-prod pg_dump -U feba_user feba_prod </dev/null | gzip > "$file"
  gzip -t "$file" && [ "$(gzip -dc "$file" | head -c 100000 | grep -c 'PostgreSQL database dump')" -ge 1 ] \
    || fail "sauvegarde illisible : déploiement interrompu"
  chmod 600 "$file"; ok "sauvegarde vérifiée : $file"
else
  ok "aucune base en service (premier déploiement) : rien à sauvegarder"
fi

step 5 "Images de retour arrière"
if docker image inspect feba-backend:current >/dev/null 2>&1; then
  docker tag feba-backend:current feba-backend:previous
  docker tag feba-frontend:current feba-frontend:previous
  ok "images actuelles marquées « previous »"
else
  ok "premier déploiement : pas d'image précédente"
fi

step 6 "Démarrage de la nouvelle version"
docker tag feba-backend:candidate feba-backend:current
docker tag feba-frontend:candidate feba-frontend:current
FEBA_IMAGE_TAG=current dc up -d --no-build
# nginx résout les conteneurs à chaque requête (resolver Docker) ; un
# rechargement en plus ne coûte rien et couvre un nginx.conf modifié.
dc exec -T nginx-prod nginx -s reload </dev/null >/dev/null 2>&1 || true

step 7 "Contrôles de santé et tests de fumée"
if wait_healthy && smoke; then
  printf '\n\033[32mDéploiement réussi.\033[0m Retour arrière possible : scripts/deploy_feba.sh --rollback\n'
else
  echo "  Les contrôles ont échoué."
  docker image inspect feba-backend:previous >/dev/null 2>&1 && rollback
  exit 1
fi
