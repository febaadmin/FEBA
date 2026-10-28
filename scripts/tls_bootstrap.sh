#!/usr/bin/env bash
# ══════════════════════════════════════════════════════════════════════
# Certificat Let's Encrypt de FEBA — obtention initiale et renouvellement.
#
#   scripts/tls_bootstrap.sh --email admin@globalfeba.com [--env .env.prod]
#
# 1. Si le certificat du premier domaine d'ALLOWED_HOSTS existe : rien à
#    obtenir (idempotent).
# 2. Sinon, obtention en mode « standalone » : le port 80 doit être libre
#    (avant le premier démarrage de nginx).
# 3. Dans tous les cas, le RENOUVELLEMENT est réglé en mode webroot
#    (/var/www/certbot, servi par nginx sur le port 80) avec rechargement
#    de nginx : « certbot renew » (timer systemd du paquet certbot)
#    fonctionne alors nginx en marche.
# ══════════════════════════════════════════════════════════════════════
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$ROOT/.env.prod"
EMAIL=""
while [ $# -gt 0 ]; do
  case "$1" in
    --email) EMAIL="$2"; shift 2 ;;
    --env) ENV_FILE="$2"; shift 2 ;;
    *) echo "Option inconnue : $1"; exit 1 ;;
  esac
done
command -v certbot >/dev/null || { echo "Installez certbot (apt install certbot)."; exit 1; }
[ -f "$ENV_FILE" ] || { echo "$ENV_FILE absent."; exit 1; }
HOSTS="$(grep -E '^ALLOWED_HOSTS=' "$ENV_FILE" | cut -d= -f2-)"
DOMAIN="${HOSTS%%,*}"
ARGS=()
IFS=',' read -ra LIST <<<"$HOSTS"
for h in "${LIST[@]}"; do [ -n "$h" ] && [ "$h" != localhost ] && ARGS+=(-d "$h"); done
mkdir -p /var/www/certbot

if [ -s "/etc/letsencrypt/live/$DOMAIN/fullchain.pem" ]; then
  echo "Certificat présent pour $DOMAIN."
else
  [ -n "$EMAIL" ] || { echo "--email requis pour la première obtention."; exit 1; }
  if ss -ltn 2>/dev/null | grep -q ':80 '; then
    echo "Le port 80 est occupé : arrêtez nginx le temps de l'obtention initiale, ou obtenez le certificat en webroot."
    exit 1
  fi
  certbot certonly --standalone --non-interactive --agree-tos -m "$EMAIL" --cert-name "$DOMAIN" "${ARGS[@]}"
fi

# Renouvellement en webroot, nginx en marche, puis rechargement de nginx.
certbot reconfigure --cert-name "$DOMAIN" --webroot -w /var/www/certbot \
  --deploy-hook "docker exec feba_nginx_prod nginx -s reload" --non-interactive
certbot renew --dry-run --cert-name "$DOMAIN" \
  && echo "Renouvellement automatique vérifié (essai à blanc réussi)."
