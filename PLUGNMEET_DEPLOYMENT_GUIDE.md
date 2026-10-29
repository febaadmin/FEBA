# FEBA — Déployer plugNmeet sur Hetzner (remplacement de Jitsi)

**État au 25/10/2026.** L'intégration FEBA ↔ plugNmeet est écrite, testée
contre une **instance plugNmeet réelle** (v2.5.3, locale), et vérifiée dans
un navigateur avec deux participants. **Rien n'est déployé sur Hetzner** :
l'accès SSH au serveur (`root@89.167.63.1`, clé `feba_jitsi_prod`) a été
refusé (« Permission denied (publickey) »). Ce guide décrit exactement ce qui
reste à exécuter. Jitsi n'est ni arrêté ni modifié.

Versions figées (toutes publiées depuis plus de deux semaines) :

| Composant | Image / version |
|---|---|
| plugNmeet-server | `mynaparrot/plugnmeet-server:v2.5.3` |
| client web | `plugNmeet-client` v2.5.3 (SHA-256 vérifié par le script) |
| LiveKit | `livekit/livekit-server:v1.13.9` |
| NATS | `nats:2.15.0-alpine` |
| Redis | `redis:7.4.10-alpine` |
| MariaDB | `mariadb:11.4.12` |
| Proxy HTTPS | `nginx:1.27.5-alpine` |

---

## 1. Choisir la topologie

Relevés publics (DNS-over-HTTPS, 25/10/2026) : `meet.globalfeba.com` →
`89.167.63.1` (serveur Jitsi DÉDIÉ) ; `globalfeba.com` → `62.238.38.111`
(application FEBA). Sur 89.167.63.1, le conteneur `jitsi/web` occupe déjà
80/443 : l'installateur officiel plugNmeet (HAProxy sur 80/443, réseau hôte)
**ne peut pas y être lancé tel quel**.

**A. Recommandée — un serveur Hetzner neuf pour plugNmeet** (CPX31 :
4 vCPU / 8 Go, Ubuntu 24.04). Aucun conflit de ports, Jitsi intact
jusqu'à la bascule, retour arrière = remettre l'ancien enregistrement DNS.

**B. Même serveur que Jitsi.** Possible uniquement en arrêtant `jitsi/web`
au moment de la bascule (les deux ne peuvent pas tenir 443 ensemble) et si
la machine a la capacité des deux pendant la validation (vérifier
`nproc`, `free -g` : LiveKit ≈ 1 vCPU pour 30-40 flux vidéo). Le choix ne
peut se faire qu'après inspection du serveur, impossible d'ici.

## 2. Préparer (serveur plugNmeet)

```bash
apt update && apt install -y docker.io docker-compose-plugin python3 curl unzip certbot
git clone <dépôt FEBA> /opt/feba && cd /opt/feba        # ou extraire l'archive livrée
scripts/plugnmeet_setup.sh --domain pnm.globalfeba.com --public-ip <IP_DU_SERVEUR> --turn off
```

`--turn off` tant que le certificat de `pnm.globalfeba.com` n'existe pas
(§ 3) : LiveKit démarre alors sans serveur TURN et sans lire de certificat.
`--turn on` refuse de rendre la configuration si le certificat manque,
expire sous 7 jours, ne couvre pas le domaine ou ne correspond pas à la clé.

Le script : génère les secrets (`plugnmeet/runtime/plugnmeet.env`, mode
600, jamais versionné), les clés NATS (outil officiel `nats-box`), rend les
configurations, télécharge le client v2.5.3 et **refuse** une archive dont
l'empreinte diffère. Relancé, il conserve les secrets.

## 3. DNS, pare-feu, certificat

1. **DNS** (chez le registraire de globalfeba.com) : `A pnm.globalfeba.com →
   <IP_DU_SERVEUR>` (validation). La bascule finale change `meet`.
2. **Pare-feu Hetzner Cloud** (console) ET hôte (`ufw`) :

   | Port | Protocole | Usage |
   |---|---|---|
   | 80, 443 | TCP | HTTPS, ACME |
   | 7881 | TCP | WebRTC sur TCP (réseaux filtrants) |
   | 7882-7885 | UDP | média WebRTC (multiplexage `rtc.udp_port`) |
   | 3478 | UDP | TURN (seulement après `--turn on`) |
   | 5349 | TCP | TURN/TLS (seulement après `--turn on`) |

   Pourquoi 4 ports UDP et non une plage par participant : Docker publie
   chaque port par un processus `docker-proxy` (≈ 5 Mo, IPv4 et IPv6) ;
   50000-50500 en aurait lancé ≈ 1 000. LiveKit ouvre
   min(nombre de CPU, nombre de ports) multiplexeurs : 4 sur 4 vCPU.

3. **Certificat, puis activation de TURN** (le port 80 de `pnm` doit
   servir `/.well-known/acme-challenge/` depuis `/var/www/certbot`) :
   ```bash
   mkdir -p /var/www/certbot
   docker run --rm -v /etc/letsencrypt:/etc/letsencrypt -v /var/www/certbot:/var/www/certbot \
     certbot/certbot certonly --webroot -w /var/www/certbot -d pnm.globalfeba.com \
     --email <adresse> --agree-tos --no-eff-email
   install -m 600 /etc/letsencrypt/live/pnm.globalfeba.com/fullchain.pem plugnmeet/runtime/certs/fullchain.pem
   install -m 600 /etc/letsencrypt/live/pnm.globalfeba.com/privkey.pem   plugnmeet/runtime/certs/privkey.pem
   scripts/plugnmeet_setup.sh --domain pnm.globalfeba.com --public-ip <IP> --turn on
   docker compose -p feba-pnm -f plugnmeet/docker-compose.plugnmeet.yml \
     -f plugnmeet/docker-compose.plugnmeet.limits.yml -f plugnmeet/docker-compose.plugnmeet.turn.yml \
     --env-file plugnmeet/runtime/plugnmeet.env up -d pnm-livekit
   ```
   Renouvellement : `certbot renew` (même image, minuteur quotidien) avec un
   *deploy hook* qui recopie les deux fichiers puis redémarre `pnm-livekit`
   (TURN ne lit le certificat qu'au démarrage : les réunions en cours sont
   coupées, d'où un horaire de nuit) et recharge `pnm-web`.

## 4. Démarrer et vérifier

```bash
C="docker compose -p feba-pnm -f plugnmeet/docker-compose.plugnmeet.yml \
   -f plugnmeet/docker-compose.plugnmeet.limits.yml --env-file plugnmeet/runtime/plugnmeet.env"
$C up -d                       # sans TURN ni proxy ; ajouter -f …turn.yml après --turn on
$C ps                          # tout « healthy »
$C --profile edge up -d pnm-web   # proxy HTTPS, une fois 80/443 disponibles
curl -fsS https://pnm.globalfeba.com/healthCheck
```

Redémarrage automatique : `restart: unless-stopped` sur chaque service.
Journaux : `docker compose … logs -f plugnmeet pnm-livekit` (rotation
20 Mo × 5) ; journal applicatif dans le volume `pnm_logs`.

## 5. Raccorder FEBA (serveur FEBA, `.env.prod`)

```
VIDEO_PROVIDER=plugnmeet
PLUGNMEET_SERVER_URL=https://pnm.globalfeba.com
PLUGNMEET_API_KEY=<PNM_API_KEY de plugnmeet/runtime/plugnmeet.env>
PLUGNMEET_API_SECRET=<PNM_API_SECRET>
PLUGNMEET_WEBHOOK_URL=https://globalfeba.com/api/virtual-rooms/webhook/
```

Puis, sur le serveur FEBA :

```bash
docker compose -f docker-compose.prod.yml --env-file .env.prod exec -T backend-prod python manage.py migrate
docker compose -f docker-compose.prod.yml --env-file .env.prod exec -T backend-prod python manage.py check
```

`check` signale (`virtualclass.W001`) un hôte de webhook absent
d'ALLOWED_HOSTS — cas rencontré pendant l'essai réel : les webhooks
étaient refusés (400) et les présences incomplètes. L'écran « Salles
virtuelles » affiche l'état réel (bandeau si dégradé) ; diagnostic
détaillé : `GET /api/virtual-rooms/health/` (enseignants et plus).

## 6. Recette avant bascule (obligatoire)

Sur `pnm.globalfeba.com`, avec de vrais postes (dont un réseau mobile) :
1. enseignant + 2 élèves, caméra et micro ; 2. partage d'écran ; 3. tableau
blanc avec un PDF ; 4. sondage ; 5. sous-groupes puis retour ; 6. salle
d'attente ; 7. fermeture par l'enseignant depuis FEBA ; 8. présences dans
FEBA (« Participants ») ; 9. réunion de 60 minutes sans déconnexion FEBA ;
10. élève derrière un réseau restrictif (TURN).

## 7. Bascule (une fois la recette signée)

1. Option A : `A meet.globalfeba.com → <IP plugNmeet>` ; générer le
   certificat de `meet.globalfeba.com`, relancer
   `scripts/plugnmeet_setup.sh --domain meet.globalfeba.com --public-ip …`,
   redémarrer ; `PLUGNMEET_SERVER_URL=https://meet.globalfeba.com` côté FEBA.
2. Laisser Jitsi en marche (arrêté seulement après une période
   d'observation) : c'est le retour arrière.

## 8. Retour arrière

- **Immédiat (FEBA)** : `VIDEO_PROVIDER=jitsi` dans `.env.prod`, puis
  redémarrage du backend. Le code Jitsi est conservé à cette seule fin ;
  ses tests restent dans la suite.
- **DNS** : remettre `meet.globalfeba.com → 89.167.63.1`.
- **Version précédente de FEBA** : les migrations de cette version sont
  additives (colonnes avec valeur par défaut en base, nouvelles tables) ;
  l'ancienne version fonctionne sur le schéma migré.
- Ne JAMAIS supprimer les volumes `pnm_*` ni ceux de Jitsi pendant ces
  opérations.

## 9. Sauvegarde, rétention

- Données utiles : volume `pnm_db` (salles, enregistrements, analyses) →
  `docker compose … exec pnm-db mariadb-dump -uroot -p"$PNM_DB_ROOT_PASSWORD" plugnmeet > pnm-$(date +%F).sql`
  (quotidien, conservé hors du serveur) ; `plugnmeet/runtime/plugnmeet.env`
  (secrets) dans le coffre de l'établissement.
- Enregistrements (si activés, §10) : volume `pnm_recordings`. Politique
  à décider par l'administration (durée de conservation des cours filmés
  de mineurs) ; plugNmeet garde 72 h une copie des fichiers supprimés.
- Fichiers de chat/tableau : `keep_forever: false` (supprimés avec la salle).

## 10. Fonctions — ce qui est réellement disponible

Légende : **N** natif et activé ; **C** nécessite une configuration ;
**S** nécessite un service supplémentaire ; **I** indisponible.

| Fonction | Statut | Vérification |
|---|---|---|
| Audio, vidéo | N | navigateur : connexion WebRTC établie, pistes publiées par un participant (événement `track_published` reçu) |
| Partage d'écran | N (élèves : verrouillé jusqu'à autorisation) | cadenas visible côté élève |
| Chat + fichiers | N | message élève → enseignante reçu |
| Tableau blanc, PDF/Office sur le tableau | N | tableau affiché chez l'élève (PDF non testé) |
| Annotations | N (outils du tableau blanc) | non testé en réel |
| Notes partagées | N (natif en v2.5, sans Etherpad) | texte synchronisé en temps réel |
| Sous-groupes | N | menu présent ; non éprouvé en réel ; présences des sous-groupes comptées (test automatisé) |
| Sondages / quiz | N | menu présent ; non éprouvé en réel |
| Lever la main, modération, verrous, salle d'attente | N | salle d'attente : admission réelle ; menu de modération présent |
| Vidéo externe, lien externe | N (modérateurs) | menu présent |
| Présences / événements | N (webhooks signés) | événements réels reçus et vérifiés |
| Enregistrement + consultation sécurisée | S : `plugnmeet-recorder` (Chrome sans tête, ffmpeg) | **désactivé** ; code et tests prêts (`PLUGNMEET_RECORDING_ENABLED`) |
| Diffusion RTMP | S : recorder | **désactivée** (`PLUGNMEET_RTMP_ENABLED`) |
| Flux entrant (ingress) | S : `livekit-ingress` | désactivé |
| Sous-titres, transcription, traduction, résumés IA | S : clés Azure / Google / OpenAI | **désactivés** ; aucune simulation |
| Appel téléphonique (SIP) | S : `livekit-sip` + numéro | désactivé |
| Chiffrement de bout en bout | C | désactivé (incompatible avec les fonctions d'IA audio) |

Toute fonction désactivée est **déclarée** désactivée à la création de la
salle : vérifié sur l'instance réelle, une fonction omise y est activée par
défaut (RTMP, ingress, blocs IA), ce qui afficherait des boutons inopérants.
