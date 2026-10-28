# ══════════════════════════════════════════════════════════════════════
# Proxy HTTPS de plugNmeet (${PNM_DOMAIN}) — généré par
# scripts/plugnmeet_setup.sh. Rôle tenu par HAProxy dans l'installateur
# officiel ; ici nginx, dans son propre conteneur (profil « edge »).
#
#   /          → plugnmeet:8080   API, client web, téléchargements
#   /livekit   → pnm-livekit:7880 signalisation WebRTC (WebSocket)
#   /ws        → pnm-nats:8222    temps réel : chat, tableau blanc, sondages
#
# Le MÉDIA ne passe pas par ici : UDP 50000-50500, TCP 7881 et TURN
# (3478/udp, 5349/tcp) sont publiés directement par LiveKit.
# ══════════════════════════════════════════════════════════════════════
map $http_upgrade $connection_upgrade {
    default upgrade;
    ''      close;
}

server {
    listen 80;
    server_name ${PNM_DOMAIN};

    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }
    location / {
        return 301 https://$host$request_uri;
    }
}

server {
    listen 443 ssl;
    http2 on;
    server_name ${PNM_DOMAIN};

    ssl_certificate     /etc/letsencrypt/live/${PNM_DOMAIN}/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/${PNM_DOMAIN}/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;

    add_header Strict-Transport-Security "max-age=31536000" always;
    add_header X-Content-Type-Options nosniff always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    # Le jeton d'adhésion est dans l'URL (usage unique, 10 min) : il ne
    # doit pas partir vers un autre site dans l'en-tête Referer.
    add_header Permissions-Policy "camera=(self), microphone=(self), display-capture=(self)" always;

    # Fichiers du tableau blanc et du chat (upload_file_settings.max_size).
    client_max_body_size 50m;
    proxy_read_timeout 3600s;
    proxy_send_timeout 3600s;

    location /livekit/ {
        proxy_pass http://pnm-livekit:7880/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection $connection_upgrade;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_buffering off;
    }

    location /ws {
        proxy_pass http://pnm-nats:8222;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection $connection_upgrade;
        proxy_set_header Host $host;
        proxy_buffering off;
    }

    location / {
        proxy_pass http://plugnmeet:8080;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection $connection_upgrade;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
    }
}
