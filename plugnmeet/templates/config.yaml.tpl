# ══════════════════════════════════════════════════════════════════════
# plugNmeet-server v2.5.3 — configuration générée par
# scripts/plugnmeet_setup.sh à partir de ce modèle. NE PAS ÉDITER le
# fichier généré (plugnmeet/runtime/config.yaml) : il est réécrit.
#
# Les variables entre « ${ } » viennent de plugnmeet/runtime/plugnmeet.env (secrets
# générés, jamais versionnés). Toute variable manquante fait échouer le
# rendu : aucun fichier n'est produit avec un secret vide.
# ══════════════════════════════════════════════════════════════════════
client:
  port: 8080
  debug: false
  path: "./client/dist"
  # Clé et secret de l'API serveur → serveur. Seul le backend FEBA les
  # connaît (PLUGNMEET_API_KEY / PLUGNMEET_API_SECRET) ; jamais le
  # navigateur.
  api_key: ${PNM_API_KEY}
  secret: ${PNM_API_SECRET}
  # Durée de validité du jeton d'ADHÉSION (usage unique, consommé à
  # l'ouverture de la salle). Une fois connecté, le participant n'en
  # dépend plus.
  token_validity: 10m
  webhook_conf:
    enable: true
    # Pas d'URL globale : FEBA déclare son URL de webhook salle par salle
    # (metadata.webhook_url). Une URL globale EN PLUS enverrait chaque
    # événement deux fois.
    url: ""
    enable_for_per_meeting: true
  prometheus:
    enable: false
    metrics_path: "/metrics"
    username: ""
    password: ""
  proxy_conf:
    enabled: true
    proxy_header: "X-Forwarded-For"
    trusted_proxy_ips: [ "127.0.0.0/8", "10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "::1/128" ]
  copyright_conf:
    display: true
    allow_override: true
    text: 'FEBA — visioconférence'
  bbb_join_host: "${PNM_PUBLIC_URL}"

room_default_settings:
  max_duration: 0
  max_participants: 0
  max_num_breakout_rooms: 6
  max_preloaded_wb_file_size: 10mb

log_settings:
  log_file: "./log/plugNmeet.log"
  maxsize: 20
  maxbackups: 4
  maxage: 14
  log_level: "info"

livekit_info:
  # Adresse de LiveKit pour le SERVEUR et pour le NAVIGATEUR (plugNmeet
  # transmet la même adresse au client). En production : l'URL publique,
  # derrière le proxy TLS. En local : http://host.docker.internal:7880,
  # que plugNmeet réécrit lui-même en http://localhost:7880 pour le
  # navigateur.
  host: "${PNM_LIVEKIT_URL}"
  api_key: ${LIVEKIT_API_KEY}
  secret: ${LIVEKIT_API_SECRET}

livekit_sip_info:
  enabled: false
  trunk_name: "pnm-inbound-trunk"
  phone_numbers: []

redis_info:
  host: pnm-redis:6379
  username: ""
  password: "${PNM_REDIS_PASSWORD}"
  db: 0
  default_ttl: 24h

database_info:
  driver_name: mysql
  host: pnm-db
  port: 3306
  username: plugnmeet
  password: "${PNM_DB_PASSWORD}"
  db: plugnmeet
  prefix: pnm_
  charset: "utf8mb4"
  loc: "UTC"
  conn_max_lifetime: 4m
  max_open_conns: 10

nats_info:
  nats_urls:
    - "nats://pnm-nats:4222"
  # Adresse WebSocket de NATS pour le NAVIGATEUR (chat, tableau blanc,
  # sondages, notes passent par NATS).
  nats_ws_urls:
    - "${PNM_NATS_WS_URL}"
  account: PNM
  nkey: ${NATS_NKEY_PRIVATE_KEY}
  auth_callout_issuer_private: ${NATS_CALLOUT_PRIVATE_KEY}
  auth_callout_xkey_private: ${NATS_XKEY_PRIVATE_KEY}
  num_replicas: 1
  room_stream_name: "pnm-room-stream"
  default_ttl: 24h
  subjects:
    system_api_worker: "sysApiWorker"
    system_js_worker: "sysJsWorker"
    system_core_worker: "sysCoreWorker"
    system_public: "sysPublic"
    system_private: "sysPrivate"
    chat: "chat"
    whiteboard: "whiteboard"
    data_channel: "dataChannel"
  recorder:
    recorder_channel: "recorderChannel"
    recorder_info_kv: "pnm-recorderInfo"
    transcoding_jobs_subject: "pnm-RecorderTranscoderJobs"

upload_file_settings:
  path: "./upload"
  max_size: 50
  max_size_whiteboard_file: 30
  keep_forever: false
  allowed_types: ["jpg","png","jpeg","svg","pdf","docx","txt","xlsx","pptx","odt","ods","odp","mp4","webm","mp3"]

recorder_info:
  # L'ENREGISTREMENT exige le service plugNmeet-recorder (non inclus par
  # défaut : Chrome sans tête + ffmpeg, ~2 vCPU par enregistrement). Sans
  # lui, le bouton d'enregistrement « cloud » ne démarre rien.
  recording_files_path: "./recording_files"
  token_validity: 30m
  ping_timeout: 8s
  enable_del_recording_backup: true
  del_recording_backup_path: "./recording_files/del_backup"
  del_recording_backup_duration: 72h

analytics_settings:
  enabled: true

artifacts_settings:
  storage_path: "./artifacts"
  token_validity: 10m
  enable_del_artifacts_backup: true
  del_artifacts_backup_path: "./artifacts/trash"
  del_artifacts_backup_duration: 72h

# Transcription, traduction, synthèse vocale et résumés IA exigent des
# clés Azure / Google / OpenAI. AUCUNE n'est fournie : les fonctions sont
# DÉSACTIVÉES, et FEBA ne les propose pas (PLUGNMEET_ENABLE_INSIGHTS=False).
insights:
  enabled: false
