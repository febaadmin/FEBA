#!/usr/bin/env bash
# Domaine public définitif de plugNmeet : meet.globalfeba.com, servi par
# Jitsi jusqu'à la bascule. À lancer sur le serveur vidéo.
#
#   meet_plugnmeet.sh preparer              certificat meet (+ ancien nom pnm),
#                                           plugNmeet reconfiguré pour meet ;
#                                           le public reste servi par Jitsi
#   meet_plugnmeet.sh verifier              contrôles, aucune modification
#   meet_plugnmeet.sh aiguilleur plugnmeet  meet → plugNmeet (rechargement)
#   meet_plugnmeet.sh aiguilleur jitsi      meet → Jitsi (retour arrière)
#   meet_plugnmeet.sh annuler-preparation   plugNmeet revient sur pnm
#
# Un seul service à la fois derrière meet : l'aiguilleur décide, par
# rechargement (sans coupure des connexions en cours). Jitsi, OKX et leurs
# données ne sont jamais modifiés ; Jitsi reste démarré pour le retour.
# Le compte ACME est celui créé par activer_pnm_public.sh (conditions
# acceptées à ce moment-là) : aucune nouvelle inscription ici.
set -uo pipefail

MODE="${1:-}"; CIBLE="${2:-}"
DOMAINE=meet.globalfeba.com
ANCIEN=pnm.globalfeba.com
IP=89.167.63.1
PNM=/opt/feba/pnm/FEBA
EDGE=$PNM/plugnmeet/edge
AVANT=/opt/feba/pnm/runtime-avant-meet.tgz
CERTBOT=certbot/certbot:v5.8.0@sha256:f70ad0adbb7e117f0fe42a63c553f28ea451edabc0148757b6efcd9735acaa20
TS=$(date -u +%Y%m%dT%H%M%SZ)
DIAG=/opt/feba/pnm/diag-meet-$TS
install -d -m 700 "$DIAG"
exec > >(tee -a "$DIAG/journal.log") 2>&1
cd "$PNM" || exit 1

CT() { docker compose -p feba-pnm -f plugnmeet/docker-compose.plugnmeet.yml \
  -f plugnmeet/docker-compose.plugnmeet.limits.yml -f plugnmeet/docker-compose.plugnmeet.turn.yml \
  -f plugnmeet/docker-compose.plugnmeet.edge.yml --env-file plugnmeet/runtime/plugnmeet.env "$@"; }
etat_proteges() {
  local c
  for c in $(docker ps -a --format '{{.Names}}' | grep -E '^(app-|okx-trading-bot|feba-edge)' | sort); do
    docker inspect -f '{{.Name}} {{.RestartCount}} {{.State.StartedAt}} {{.State.Status}}' "$c"
  done
}
domaine_pnm() { grep '^PNM_DOMAIN=' plugnmeet/runtime/plugnmeet.env | cut -d= -f2-; }
# pnm-web directement (sans l'aiguilleur) / à travers l'aiguilleur.
direct() { curl -s -m 8 --connect-to "$DOMAINE:443:127.0.0.1:9443" "$@"; }
public() { curl -s -m 8 --resolve "$DOMAINE:443:127.0.0.1" "$@"; }
ws() { curl -s -o /dev/null -m 3 -w '%{http_code}' --http1.1 -H 'Connection: Upgrade' -H 'Upgrade: websocket' \
  -H 'Sec-WebSocket-Version: 13' -H 'Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==' "$@"; }
tls_ok() {  # $1 = hôte:port ; certificat vérifié pour $DOMAINE
  echo | openssl s_client -connect "$1" -servername "$DOMAINE" -verify_hostname "$DOMAINE" \
    -verify_return_error 2>/dev/null | grep -q 'Verify return code: 0 (ok)'
}
attendre_sains() {
  local s
  for _ in $(seq 1 40); do
    for s in plugnmeet pnm-livekit pnm-web; do
      [ "$(docker inspect -f '{{.State.Health.Status}}' "feba-pnm-$s-1" 2>/dev/null)" = healthy ] || continue 2
    done
    return 0
  done
  return 1
}
recharger_aiguilleur() {  # nginx -t sur le fichier monté, puis rechargement
  docker exec feba-edge nginx -t -c /etc/nginx/feba/nginx.conf 2>&1 | tail -1 | grep -q successful || return 1
  docker exec feba-edge nginx -s reload -c /etc/nginx/feba/nginx.conf && sleep 2
}
aiguillage_meet() {
  sed -n '/map \$ssl_preread_server_name/,/}/p' "$EDGE/nginx.conf" | awk -v d="$DOMAINE" '$1==d {print $2}' | tr -d ';'
}

controles() {
  echo "== Contrôles ($DOMAINE)"
  echo "plugNmeet configuré pour : $(domaine_pnm)"
  echo "aiguilleur : $DOMAINE → $(aiguillage_meet) (8444 = Jitsi, 9443 = plugNmeet)"
  echo "pnm-web direct /healthCheck : $(direct "https://$DOMAINE/healthCheck")"
  tls_ok 127.0.0.1:9443 && echo "certificat HTTPS de pnm-web : valide pour $DOMAINE" || echo "certificat HTTPS de pnm-web : INVALIDE pour $DOMAINE"
  openssl x509 -in plugnmeet/runtime/certs/fullchain.pem -noout -ext subjectAltName -enddate 2>/dev/null | tr -s ' \n' ' '; echo
  echo "client : $(direct "https://$DOMAINE/assets/config.js" | grep -o "serverUrl: '[^']*'")"
  echo "LiveKit par le proxy : $(direct "https://$DOMAINE/livekit/")"
  echo "WebSocket LiveKit /livekit/rtc (401 attendu sans jeton) : $(ws --connect-to "$DOMAINE:443:127.0.0.1:9443" "https://$DOMAINE/livekit/rtc")"
  echo "WebSocket NATS /ws (101 attendu) : $(ws --connect-to "$DOMAINE:443:127.0.0.1:9443" "https://$DOMAINE/ws")"
  echo "serveur plugNmeet → LiveKit (alias interne) : $(docker exec feba-pnm-plugnmeet-1 curl -s -m 5 "https://$DOMAINE/livekit/")"
  tls_ok 127.0.0.1:5349 && echo "TURN/TLS 5349 : certificat valide pour $DOMAINE" || echo "TURN/TLS 5349 : certificat INVALIDE pour $DOMAINE"
  echo "TURN (livekit.yaml) : $(grep -E '^\s+domain:' plugnmeet/runtime/livekit.yaml | tr -s ' ')"
  echo "public https://$DOMAINE/ : HTTP $(public -o /dev/null -w '%{http_code}' "https://$DOMAINE/") ; healthCheck : $(public "https://$DOMAINE/healthCheck" | head -c 40)"
}

case "$MODE" in
verifier)
  controles
  ;;

preparer)
  echo "== Préconditions"
  ok=1
  resolu=$(python3 -c "import socket; print(' '.join(sorted({a[4][0] for a in socket.getaddrinfo('$DOMAINE', 443, socket.AF_INET)})))" 2>/dev/null)
  echo "DNS $DOMAINE → ${resolu:-aucune adresse}"; [ "$resolu" = "$IP" ] || ok=0
  [ "$(aiguillage_meet)" = 127.0.0.1:8444 ] && echo "aiguilleur : $DOMAINE → Jitsi" || { echo "aiguilleur : état inattendu"; ok=0; }
  grep -q 'try_files $uri @jitsi' "$EDGE/nginx.conf" || { echo "aiguilleur : défis ACME de meet absents de nginx.conf (dépôt à jour ?)"; ok=0; }
  for s in plugnmeet pnm-livekit pnm-db pnm-redis pnm-web; do
    h=$(docker inspect -f '{{.State.Health.Status}}' "feba-pnm-$s-1" 2>/dev/null); echo "$s : ${h:-absent}"; [ "$h" = healthy ] || ok=0
  done
  [ $ok = 1 ] || { echo "ARRÊT : préconditions non remplies"; exit 1; }
  etat_proteges > "$DIAG/proteges-avant.txt"

  echo "== Aiguilleur : défis ACME de meet servis localement, le reste toujours à Jitsi"
  recharger_aiguilleur || { echo "ARRÊT : configuration de l'aiguilleur refusée par nginx -t"; exit 1; }
  install -d -m 755 /var/www/certbot/.well-known/acme-challenge
  echo "controle-$TS" > /var/www/certbot/.well-known/acme-challenge/feba-controle
  r=$(curl -s -m 8 -H "Host: $DOMAINE" "http://127.0.0.1/.well-known/acme-challenge/feba-controle")
  rm -f /var/www/certbot/.well-known/acme-challenge/feba-controle
  echo "défi ACME servi : $([ "$r" = "controle-$TS" ] && echo oui || echo "NON ($r)")"; [ "$r" = "controle-$TS" ] || exit 1
  echo "Jitsi public : HTTP $(public -o /dev/null -w '%{http_code}' "https://$DOMAINE/")"

  echo "== Certificat $DOMAINE (+ $ANCIEN)"
  docker run --rm --pull missing -v /etc/letsencrypt:/etc/letsencrypt -v /var/www/certbot:/var/www/certbot \
    "$CERTBOT" certonly --webroot -w /var/www/certbot --cert-name "$DOMAINE" -d "$DOMAINE" -d "$ANCIEN" \
    --non-interactive --keep-until-expiring 2>&1 | tail -4
  L=/etc/letsencrypt/live/$DOMAINE
  [ -s "$L/fullchain.pem" ] || { echo "ARRÊT : certificat absent"; exit 1; }

  echo "== plugNmeet reconfiguré pour $DOMAINE"
  [ -s "$AVANT" ] || { tar czf "$AVANT" --exclude runtime/client -C "$PNM/plugnmeet" runtime && chmod 600 "$AVANT"; }
  echo "configuration précédente : $AVANT"
  install -m 600 "$L/fullchain.pem" plugnmeet/runtime/certs/fullchain.pem
  install -m 600 "$L/privkey.pem" plugnmeet/runtime/certs/privkey.pem
  scripts/plugnmeet_setup.sh --domain "$DOMAINE" --public-ip "$IP" --feba-url https://globalfeba.com --turn on \
    | grep -viE 'secret=|password=|key=' | tail -3
  [ "$(domaine_pnm)" = "$DOMAINE" ] || { echo "ARRÊT : configuration non réécrite"; exit 1; }
  # pnm-web recréé (alias réseau = nouveau domaine) ; LiveKit et plugNmeet
  # relisent leur configuration au démarrage.
  CT --profile edge up -d --no-build --pull never pnm-livekit plugnmeet pnm-web 2>&1 | tail -3
  CT --profile edge restart pnm-livekit plugnmeet pnm-web 2>&1 | tail -3
  attendre_sains || echo "ATTENTION : services non sains après 2 minutes"
  controles
  diff "$DIAG/proteges-avant.txt" <(etat_proteges) && echo "Jitsi, OKX et aiguilleur : inchangés" || echo "CHANGEMENT DÉTECTÉ (voir ci-dessus)"
  [ "$(direct "https://$DOMAINE/healthCheck")" = Healthy ] && tls_ok 127.0.0.1:9443 \
    && echo "PRÉPARATION TERMINÉE : plugNmeet prêt pour $DOMAINE, public toujours sur Jitsi. Journal : $DIAG" \
    || { echo "ÉCHEC des contrôles : lancer « annuler-preparation »"; exit 1; }
  ;;

aiguilleur)
  case "$CIBLE" in
  plugnmeet)
    [ "$(domaine_pnm)" = "$DOMAINE" ] || { echo "ARRÊT : plugNmeet n'est pas configuré pour $DOMAINE (preparer)"; exit 1; }
    [ "$(direct "https://$DOMAINE/healthCheck")" = Healthy ] && tls_ok 127.0.0.1:9443 \
      || { echo "ARRÊT : plugNmeet injoignable ou certificat invalide en direct"; exit 1; }
    cp -p "$EDGE/nginx.conf" "$DIAG/nginx.avant.conf"
    cat "$EDGE/nginx.plugnmeet.conf" > "$EDGE/nginx.conf"
    if ! recharger_aiguilleur; then
      cat "$DIAG/nginx.avant.conf" > "$EDGE/nginx.conf"; echo "ARRÊT : nginx -t refuse l'état plugNmeet ; aiguilleur inchangé"; exit 1
    fi
    r=$(public "https://$DOMAINE/healthCheck")
    echo "public https://$DOMAINE/healthCheck : $r"
    if [ "$r" != Healthy ]; then
      cat "$DIAG/nginx.avant.conf" > "$EDGE/nginx.conf"; recharger_aiguilleur
      echo "ÉCHEC : retour de l'aiguilleur sur Jitsi"; exit 1
    fi
    echo "AIGUILLEUR : $DOMAINE → plugNmeet"
    ;;
  jitsi)
    cp -p "$EDGE/nginx.conf" "$DIAG/nginx.avant.conf"
    git -C "$PNM" show HEAD:plugnmeet/edge/nginx.conf > "$DIAG/nginx.jitsi.conf" || exit 1
    grep -q "$DOMAINE  127.0.0.1:8444" "$DIAG/nginx.jitsi.conf" || { echo "ARRÊT : état Jitsi introuvable dans le dépôt"; exit 1; }
    cat "$DIAG/nginx.jitsi.conf" > "$EDGE/nginx.conf"
    if ! recharger_aiguilleur; then
      cat "$DIAG/nginx.avant.conf" > "$EDGE/nginx.conf"; echo "ARRÊT : nginx -t refuse l'état Jitsi"; exit 1
    fi
    echo "public https://$DOMAINE/ : HTTP $(public -o /dev/null -w '%{http_code}' "https://$DOMAINE/"), $(public "https://$DOMAINE/" | grep -oi '<title>[^<]*' | head -1)"
    echo "AIGUILLEUR : $DOMAINE → Jitsi"
    ;;
  *) echo "usage : $0 aiguilleur plugnmeet|jitsi"; exit 2 ;;
  esac
  ;;

annuler-preparation)
  [ "$(aiguillage_meet)" = 127.0.0.1:8444 ] || { echo "ARRÊT : remettre d'abord l'aiguilleur sur Jitsi"; exit 1; }
  [ -s "$AVANT" ] || { echo "ARRÊT : $AVANT absent"; exit 1; }
  tar xzf "$AVANT" -C "$PNM/plugnmeet" || exit 1   # certificats et configuration de pnm
  # Le client web (config.js) n'est pas dans l'archive : nouveau rendu pour pnm.
  scripts/plugnmeet_setup.sh --domain "$ANCIEN" --public-ip "$IP" --feba-url https://globalfeba.com --turn on \
    | grep -viE 'secret=|password=|key=' | tail -2
  CT --profile edge up -d --no-build --pull never pnm-livekit plugnmeet pnm-web 2>&1 | tail -3
  CT --profile edge restart pnm-livekit plugnmeet pnm-web 2>&1 | tail -3
  attendre_sains
  echo "plugNmeet configuré pour : $(domaine_pnm) ; https://$ANCIEN/healthCheck : $(curl -s -m 8 --resolve "$ANCIEN:443:127.0.0.1" "https://$ANCIEN/healthCheck")"
  ;;

*) echo "usage : $0 preparer | verifier | aiguilleur plugnmeet|jitsi | annuler-preparation"; exit 2 ;;
esac
