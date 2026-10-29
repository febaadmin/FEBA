#!/usr/bin/env bash
# Bascule de FEBA (production) vers plugNmeet, ou retour à Jitsi.
# À lancer depuis un poste d'administration disposant des deux accès SSH.
#
#   basculer_feba.sh verifier    # plugNmeet joignable depuis FEBA + essai à blanc
#   basculer_feba.sh executer    # sauvegarde de .env.prod, bascule, contrôles
#   basculer_feba.sh retour      # restaure la dernière sauvegarde de .env.prod
#
# Les clés plugNmeet passent du serveur vidéo au serveur FEBA par un tube
# SSH, sans être affichées ni écrites sur ce poste. .env.prod n'est modifié
# qu'en mode « executer », après une sauvegarde horodatée (mode 600).
set -uo pipefail

MODE="${1:-}"
VIDEO="ssh -o BatchMode=yes -i ${VIDEO_KEY:-$HOME/.ssh/feba_jitsi_prod} root@89.167.63.1"
FEBA="ssh -o BatchMode=yes -i ${FEBA_KEY:-$HOME/.ssh/feba_github_actions} deploy@62.238.38.111"
# Adresse publique de plugNmeet (domaine définitif : meet.globalfeba.com).
PNM_URL=${PNM_URL:-https://meet.globalfeba.com}
HOOK=https://globalfeba.com/api/virtual-rooms/webhook/

cles() { $VIDEO 'grep -E "^(PNM_API_KEY|PNM_API_SECRET)=" /opt/feba/pnm/FEBA/plugnmeet/runtime/plugnmeet.env' </dev/null \
  | sed 's/^PNM_API_KEY=/PLUGNMEET_API_KEY=/; s/^PNM_API_SECRET=/PLUGNMEET_API_SECRET=/'; }

# Côté FEBA : écrit le candidat (.env.prod sans réglages vidéo + réglages
# plugNmeet), puis le contrôle de démarrage de production sur ce candidat.
CANDIDAT='set -u; umask 077; cd /opt/feba/app/FEBA
T=$(mktemp ~/.candidat-env.XXXXXX); O=$(mktemp ~/.candidat-compose.XXXXXX.yml)
grep -vE "^(VIDEO_PROVIDER|PLUGNMEET_[A-Z_]+)=" .env.prod > "$T"; cat >> "$T"
printf "VIDEO_PROVIDER=plugnmeet\nPLUGNMEET_SERVER_URL=%s\nPLUGNMEET_WEBHOOK_URL=%s\n" "'"$PNM_URL"'" "'"$HOOK"'" >> "$T"
printf "services:\n  backend-prod:\n    env_file: !override\n      - %s\n" "$T" > "$O"
docker compose --env-file .env.prod -f docker-compose.prod.yml -f "$O" run --rm --no-deps -T backend-prod \
  python manage.py production_preflight --network </dev/null 2>&1 | tail -4
rc=${PIPESTATUS[0]}'

case "$MODE" in
verifier)
  $FEBA "echo \"plugNmeet vu depuis FEBA : \$(curl -s -m 10 $PNM_URL/healthCheck)\"" </dev/null
  cles | $FEBA "$CANDIDAT"'; shred -u "$T" "$O" 2>/dev/null || rm -f "$T" "$O"; exit $rc'
  ;;
executer)
  r=$($FEBA "curl -s -m 10 $PNM_URL/healthCheck" </dev/null)
  [ "$r" = Healthy ] || { echo "ARRÊT : plugNmeet injoignable depuis FEBA ($r)"; exit 1; }
  cles | $FEBA "$CANDIDAT"'
  [ "$rc" -eq 0 ] || { echo "ARRÊT : configuration candidate refusée"; shred -u "$T" "$O"; exit 1; }
  install -d -m 700 ~/sauvegardes-env
  S=~/sauvegardes-env/.env.prod.$(date -u +%Y%m%dT%H%M%SZ); cp -p .env.prod "$S"
  echo "sauvegarde de .env.prod : $S"
  install -m 600 "$T" .env.prod; shred -u "$T" "$O" 2>/dev/null || rm -f "$T" "$O"
  C="docker compose --env-file .env.prod -f docker-compose.prod.yml"
  $C up -d --no-deps --no-build backend-prod celery-prod celery-beat </dev/null 2>&1 | tail -3
  for _ in $(seq 1 40); do [ "$(docker inspect -f "{{.State.Health.Status}}" feba_backend_prod)" = healthy ] && break; sleep 5; done
  $C restart nginx-prod </dev/null 2>&1 | tail -1
  sleep 5
  echo "backend : $(docker inspect -f "{{.State.Health.Status}}" feba_backend_prod)"
  echo "API publique : $(curl -s -m 10 https://globalfeba.com/api/health/)"
  $C exec -T backend-prod python manage.py shell -c "from apps.virtualclass import plugnmeet, meetings; print(\"fournisseur :\", meetings.provider(), \"| plugNmeet :\", plugnmeet.health()[\"status\"])" </dev/null 2>&1 | tail -1'
  ;;
retour)
  $FEBA 'set -u; cd /opt/feba/app/FEBA; S=$(ls -1t ~/sauvegardes-env/.env.prod.* | head -1)
  [ -n "$S" ] || { echo "ARRÊT : aucune sauvegarde"; exit 1; }
  install -m 600 "$S" .env.prod; echo ".env.prod restauré depuis $S"
  C="docker compose --env-file .env.prod -f docker-compose.prod.yml"
  $C up -d --no-deps --no-build backend-prod celery-prod celery-beat 2>&1 | tail -2
  for _ in $(seq 1 40); do [ "$(docker inspect -f "{{.State.Health.Status}}" feba_backend_prod)" = healthy ] && break; sleep 5; done
  $C restart nginx-prod 2>&1 | tail -1
  echo "API publique : $(curl -s -m 10 https://globalfeba.com/api/health/)"' </dev/null
  ;;
*) echo "usage : $0 verifier | executer | retour"; exit 2 ;;
esac
