#!/usr/bin/env bash
# Renouvellement du certificat de pnm.globalfeba.com (minuteur
# feba-pnm-certificat.timer). Webroot servi par l'aiguilleur feba-edge.
# Si le certificat a changé : copie pour pnm-web et TURN, rechargement de
# pnm-web (sans coupure) et redémarrage de LiveKit (TURN ne relit son
# certificat qu'au démarrage : à 03:30, hors des cours).
set -uo pipefail
PNM=/opt/feba/pnm/FEBA
CERTBOT=certbot/certbot:v5.8.0@sha256:f70ad0adbb7e117f0fe42a63c553f28ea451edabc0148757b6efcd9735acaa20
L=/etc/letsencrypt/live/pnm.globalfeba.com
docker run --rm --pull missing -v /etc/letsencrypt:/etc/letsencrypt -v /var/www/certbot:/var/www/certbot \
  "$CERTBOT" renew --webroot -w /var/www/certbot --non-interactive 2>&1 | tail -3
if ! cmp -s "$L/fullchain.pem" "$PNM/plugnmeet/runtime/certs/fullchain.pem"; then
  install -m 600 "$L/fullchain.pem" "$PNM/plugnmeet/runtime/certs/fullchain.pem"
  install -m 600 "$L/privkey.pem" "$PNM/plugnmeet/runtime/certs/privkey.pem"
  docker exec feba-pnm-pnm-web-1 nginx -s reload
  docker restart feba-pnm-pnm-livekit-1 >/dev/null
  echo "certificat pnm renouvelé : $(openssl x509 -in "$L/fullchain.pem" -noout -enddate)"
else
  echo "certificat pnm inchangé : $(openssl x509 -in "$L/fullchain.pem" -noout -enddate)"
fi
