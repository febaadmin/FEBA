# LiveKit v1.13.11 (serveur média de plugNmeet) — généré par
# scripts/plugnmeet_setup.sh. Ne pas éditer le fichier généré.
port: 7880
rtc:
  # Ports média. Ils doivent être OUVERTS dans le pare-feu de l'hôte ET
  # dans le pare-feu Hetzner Cloud (console) : 7881/tcp et LIVEKIT_UDP_PORTS.
  tcp_port: 7881
  # Multiplexage UDP (rtc.udp_port ; syntaxe « 7882 » ou « 7882-7885 »,
  # vérifiée dans le code de LiveKit v1.13.9 et v1.13.11 / mediatransportutil
  # f234b534b095 et dd8e31a0adc0, comportement identique) : tous les flux passent par cette petite plage. LiveKit
  # ouvre min(nombre de CPU, nombre de ports) multiplexeurs.
  # Une plage par participant (port_range_start/end, 50000-50500) faisait
  # publier 501 ports par Docker, soit ~1 000 processus docker-proxy
  # (~5 Mo chacun, IPv4 + IPv6) : ~5 Go sur un serveur de 7,6 Go partagé
  # (constaté le 29/10/2026). NE PAS rajouter port_range_start/end : ils
  # l'emporteraient sur udp_port.
  udp_port: ${LIVEKIT_UDP_PORTS}
  use_external_ip: false
  allow_tcp_fallback: true
redis:
  address: pnm-redis:6379
  username: ""
  password: "${PNM_REDIS_PASSWORD}"
  db: 0
room:
  auto_create: true
  enabled_codecs:
    - mime: audio/opus
    - mime: audio/red
    - mime: video/h264
    - mime: video/vp8
    - mime: video/vp9
    - mime: video/av1
logging:
  level: info
  sample: true
keys:
  ${LIVEKIT_API_KEY}: ${LIVEKIT_API_SECRET}
webhook:
  # LiveKit prévient plugNmeet (entrées, sorties, fin de salle), qui
  # prévient FEBA à son tour.
  api_key: ${LIVEKIT_API_KEY}
  urls:
    - "http://plugnmeet:8080/webhook"
turn:
  # TURN intégré : indispensable pour les élèves derrière un pare-feu
  # d'entreprise ou un réseau mobile restrictif. Le port 443 est pris par
  # le proxy web : TURN/TLS écoute sur 5349, TURN/UDP sur 3478.
  #
  # « true » UNIQUEMENT quand le certificat de PNM_TURN_DOMAIN est dans
  # /certs (scripts/plugnmeet_setup.sh --turn on le vérifie avant de
  # rendre ce fichier). À « false », LiveKit ne crée pas le serveur TURN et
  # ne lit pas le certificat (pkg/service/turn.go, v1.13.11) ; ses ports
  # 3478/5349 ne sont publiés que par docker-compose.plugnmeet.turn.yml.
  enabled: ${LIVEKIT_TURN_ENABLED}
  domain: ${PNM_TURN_DOMAIN}
  udp_port: 3478
  tls_port: 5349
  external_tls: false
  cert_file: /certs/fullchain.pem
  key_file: /certs/privkey.pem
