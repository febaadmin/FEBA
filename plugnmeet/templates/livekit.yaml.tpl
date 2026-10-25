# LiveKit v1.13.9 (serveur média de plugNmeet) — généré par
# scripts/plugnmeet_setup.sh. Ne pas éditer le fichier généré.
port: 7880
rtc:
  # Ports média. Ils doivent être OUVERTS dans le pare-feu de l'hôte ET
  # dans le pare-feu Hetzner Cloud (console) : 7881/tcp et la plage UDP.
  tcp_port: 7881
  port_range_start: ${LIVEKIT_UDP_START}
  port_range_end: ${LIVEKIT_UDP_END}
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
  enabled: ${LIVEKIT_TURN_ENABLED}
  domain: ${PNM_TURN_DOMAIN}
  udp_port: 3478
  tls_port: 5349
  external_tls: false
  cert_file: /certs/fullchain.pem
  key_file: /certs/privkey.pem
