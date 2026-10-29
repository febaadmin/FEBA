#!/usr/bin/env bash
# Ouverture publique de plugNmeet sur pnm.globalfeba.com (serveur vidéo).
#
#   activer_pnm_public.sh verifier
#   activer_pnm_public.sh executer --email <adresse> --accepte-cgu-letsencrypt
#
# Préconditions (contrôlées) : aiguilleur feba-edge en place, pile feba-pnm
# saine, DNS pnm.globalfeba.com → IP de ce serveur.
# Étapes : certificat Let's Encrypt (webroot servi par l'aiguilleur), copie
# pour pnm-web et TURN, configuration --turn on, démarrage de pnm-web
# (profil edge) et recréation de LiveKit avec TURN. Aucune action sur Jitsi,
# OKX ni FEBA. Retour arrière : pnm-web arrêté, configuration --turn off,
# LiveKit recréé sans TURN (le certificat obtenu est conservé).
set -uo pipefail

MODE="${1:-}"; shift || true
EMAIL=""; CGU=0
while [ $# -gt 0 ]; do
  case "$1" in
    --email) EMAIL="$2"; shift 2 ;;
    --accepte-cgu-letsencrypt) CGU=1; shift ;;
    *) echo "option inconnue : $1"; exit 2 ;;
  esac
done
DOMAINE=pnm.globalfeba.com
IP=89.167.63.1
PNM=/opt/feba/pnm/FEBA
CERTBOT=certbot/certbot:v5.8.0@sha256:f70ad0adbb7e117f0fe42a63c553f28ea451edabc0148757b6efcd9735acaa20
TS=$(date -u +%Y%m%dT%H%M%SZ)
DIAG=/opt/feba/pnm/diag-public-$TS
install -d -m 700 "$DIAG"
exec > >(tee -a "$DIAG/journal.log") 2>&1
cd "$PNM" || exit 1
C() { docker compose -p feba-pnm -f plugnmeet/docker-compose.plugnmeet.yml \
  -f plugnmeet/docker-compose.plugnmeet.limits.yml --env-file plugnmeet/runtime/plugnmeet.env "$@"; }
CT() { docker compose -p feba-pnm -f plugnmeet/docker-compose.plugnmeet.yml \
  -f plugnmeet/docker-compose.plugnmeet.limits.yml -f plugnmeet/docker-compose.plugnmeet.turn.yml \
  -f plugnmeet/docker-compose.plugnmeet.edge.yml --env-file plugnmeet/runtime/plugnmeet.env "$@"; }
setup() { scripts/plugnmeet_setup.sh --domain "$DOMAINE" --public-ip "$IP" --feba-url https://globalfeba.com "$@" \
  | grep -viE 'secret=|password=|key='; }
etat_proteges() {
  local c
  for c in $(docker ps -a --format '{{.Names}}' | grep -E '^(app-|okx-trading-bot|feba-edge)' | sort); do
    docker inspect -f '{{.Name}} {{.RestartCount}} {{.State.StartedAt}} {{.State.Status}} {{if .State.Health}}{{.State.Health.Status}}{{end}}' "$c"
  done
}

echo "== Préconditions"
ok=1
resolu=$(python3 -c "import socket; print(' '.join(sorted({a[4][0] for a in socket.getaddrinfo('$DOMAINE', 443, socket.AF_INET)})))" 2>/dev/null)
echo "DNS $DOMAINE → ${resolu:-aucune adresse}"; [ "$resolu" = "$IP" ] || ok=0
[ "$(docker inspect -f '{{.State.Health.Status}}' feba-edge 2>/dev/null)" = healthy ] && echo "aiguilleur : sain" || { echo "aiguilleur : ABSENT ou malsain"; ok=0; }
for s in plugnmeet pnm-livekit pnm-db pnm-redis; do
  h=$(docker inspect -f '{{.State.Health.Status}}' "feba-pnm-$s-1" 2>/dev/null); echo "$s : ${h:-absent}"; [ "$h" = healthy ] || ok=0
done
install -d -m 755 /var/www/certbot/.well-known/acme-challenge
echo "controle-$TS" > /var/www/certbot/.well-known/acme-challenge/feba-controle
r=$(curl -s -m 8 --resolve "$DOMAINE:80:127.0.0.1" "http://$DOMAINE/.well-known/acme-challenge/feba-controle")
rm -f /var/www/certbot/.well-known/acme-challenge/feba-controle
echo "défis ACME servis par l'aiguilleur : $([ "$r" = "controle-$TS" ] && echo oui || echo "NON ($r)")"; [ "$r" = "controle-$TS" ] || ok=0
[ "$MODE" = executer ] || { [ $ok = 1 ] && echo "PRÊT" || echo "NON PRÊT"; exit 0; }
[ $ok = 1 ] || { echo "ARRÊT : préconditions non remplies"; exit 1; }
[ -n "$EMAIL" ] && [ $CGU = 1 ] || { echo "ARRÊT : --email et --accepte-cgu-letsencrypt sont requis"; exit 2; }

etat_proteges > "$DIAG/proteges-avant.txt"
echo "== Certificat"
docker run --rm --pull missing -v /etc/letsencrypt:/etc/letsencrypt -v /var/www/certbot:/var/www/certbot \
  "$CERTBOT" certonly --webroot -w /var/www/certbot -d "$DOMAINE" --email "$EMAIL" --agree-tos \
  --no-eff-email --non-interactive --keep-until-expiring 2>&1 | tail -6
L=/etc/letsencrypt/live/$DOMAINE
[ -s "$L/fullchain.pem" ] || { echo "ARRÊT : certificat absent"; exit 1; }
install -m 600 "$L/fullchain.pem" plugnmeet/runtime/certs/fullchain.pem
install -m 600 "$L/privkey.pem" plugnmeet/runtime/certs/privkey.pem
openssl x509 -in plugnmeet/runtime/certs/fullchain.pem -noout -subject -issuer -enddate

retour_arriere() {
  echo "== RETOUR ARRIÈRE : $1"
  CT stop pnm-web 2>&1 | tail -1
  setup --turn off >/dev/null
  C up -d --no-build --pull never pnm-livekit 2>&1 | tail -1
  exit 1
}

echo "== TURN et proxy"
setup --turn on >/dev/null || { echo "ARRÊT : configuration TURN refusée"; exit 1; }
CT --profile edge up -d --no-build --pull missing pnm-livekit pnm-web 2>&1 | tail -4 || retour_arriere "démarrage"
for _ in $(seq 1 40); do
  [ "$(docker inspect -f '{{.State.Health.Status}}' feba-pnm-pnm-web-1 2>/dev/null)" = healthy ] && \
  [ "$(docker inspect -f '{{.State.Health.Status}}' feba-pnm-pnm-livekit-1 2>/dev/null)" = healthy ] && break
  sleep 3
done
echo "== Contrôles"
r=$(curl -s -m 8 --resolve "$DOMAINE:443:127.0.0.1" "https://$DOMAINE/healthCheck"); echo "https://$DOMAINE/healthCheck : $r"
[ "$r" = Healthy ] || retour_arriere "plugNmeet injoignable en HTTPS"
echo "TURN/TLS 5349 : $(echo | openssl s_client -connect 127.0.0.1:5349 -servername "$DOMAINE" 2>/dev/null | openssl x509 -noout -subject)"
docker logs --since 5m feba-pnm-pnm-livekit-1 2>&1 | grep -E 'Starting TURN server' | cut -c1-200
echo "meet : HTTP $(curl -s -o /dev/null -m 8 -w '%{http_code}' --resolve meet.globalfeba.com:443:127.0.0.1 https://meet.globalfeba.com/)"
diff "$DIAG/proteges-avant.txt" <(etat_proteges) && echo "Jitsi, OKX et aiguilleur : inchangés" || echo "CHANGEMENT DÉTECTÉ (voir ci-dessus)"
echo "Activation terminée. Journal : $DIAG"
