# ACTIONS EXTERNES REQUISES — à faire hors du dépôt

> **EXTERNAL ACTION REQUIRED**
>
> Ce fichier liste ce qui **n'a pas été fait** et **ne pouvait pas l'être**
> depuis le dépôt : créer un serveur chez un hébergeur, écrire un
> enregistrement DNS, ouvrir un port de pare-feu, poser un secret de
> production. Tout le reste — code, configuration, scripts, contrôles — est
> livré et vérifié.
>
> Aucune de ces actions n'est présentée comme accomplie. Chacune est
> accompagnée de la commande qui permet de **vérifier** qu'elle l'est.

---


## 000. Commentaires des bulletins et visio multi-académies (26/10/2026)

Rien n'a été déployé ni migré en production. Ordre conseillé :

1. Sauvegarde vérifiée de la base (`deploy_feba.sh` en fait une à chaque
   déploiement) ; vérifier l'identité du serveur.
2. `make prod` — applique deux migrations :
   - `bulletins.0006_comments_operations` : additive (deux colonnes
     nullables, une table) ;
   - `schools.0017_enable_video_for_all_academies` : active la visio pour
     toutes les académies, FEBA comprise ; les valeurs d'origine sont
     conservées dans `settings.features_before_0017`.
3. Le worker Celery doit tourner (il exécute les opérations groupées sur
   les bulletins) : `deploy_feba.sh` vérifie déjà qu'il répond.
4. Contrôle : un administrateur FEBA ouvre « Salles virtuelles », crée une
   salle, la rejoint avec un enseignant et un élève ; puis, dans
   « Bulletins », ajoute un commentaire à un élève et ouvre le PDF.
5. Retour arrière : `make prod-rollback` (images précédentes). Les
   migrations peuvent être défaites :
   `python manage.py migrate schools 0016` puis
   `python manage.py migrate bulletins 0005` (supprime l'historique des
   opérations et les dates de modification des commentaires ; les
   commentaires eux-mêmes restent).

## 00. Version finale validée (25/10/2026) — à faire par l'exploitant

Rien de ce qui suit n'a été exécuté sur le serveur de production (accès
SSH refusé, et déploiement direct interdit par la mission). Aucune
migration nouvelle depuis la version plugNmeet/SMS.

1. **Sur le serveur, AVANT tout déploiement** : vérifier l'identité de la
   machine (`hostname`, `ip -4 addr`, `docker ps`) et faire une sauvegarde
   vérifiée de la base (`RESTORE_GUIDE.md`). `deploy_feba.sh` en refait
   une, contrôlée (`gzip -t`), à chaque déploiement.
2. **`.env.prod`** à partir de `.env.prod.example`, `chmod 600`. Ajouter
   les nouvelles variables `DEPLOYMENT_STAGE=production` et
   `PUBLIC_BASE_URL=https://globalfeba.com`. Puis :
   `make prod-preflight` — il doit afficher 0 erreur. Le backend, le
   worker et Beat **refusent de démarrer** sinon (secret faible, DEBUG,
   SMTP de test, plugNmeet ou SMS incomplet…).
3. **Certificat** : `bash scripts/tls_bootstrap.sh` (une fois ; passe le
   renouvellement en mode webroot et teste `renew --dry-run`).
4. **Déploiement** : `make prod` (= `scripts/deploy_feba.sh`). Le script
   construit, contrôle l'image candidate, sauvegarde, étiquette l'image
   précédente `previous`, démarre, vérifie (santé HTTPS, page d'accueil,
   401 sans jeton, configuration identique backend/worker/Beat, ping
   Celery) et **revient automatiquement** à la version précédente en cas
   d'échec. Retour manuel : `make prod-rollback`.
5. **Recette plugNmeet en production** avant de désactiver Jitsi
   (`PLUGNMEET_DEPLOYMENT_GUIDE.md` §§ 6-7) : 1 enseignant + 2 élèves sur
   des réseaux différents, partage d'écran compris. Ne basculer
   `VIDEO_PROVIDER=plugnmeet` et le DNS qu'après cette recette.
6. **SMTP réel et SMS réel** : actions du § 0 ci-dessous, un seul
   destinataire de test à chaque fois (jamais d'envoi groupé de test).

## 0. Version plugNmeet / SMS / expéditeur (25/10/2026) — actions hors dépôt

Ordre conseillé ; chaque étape est réversible et n'arrête pas Jitsi.

1. **E-mail** — chez Hostinger : boîte `noreply@globalfeba.com`, DKIM actif.
   `.env.prod` : bloc SMTP de `.env.prod.example`. Puis
   `manage.py check` (aucun `notifications.W00x`) et
   `manage.py email_check --to <votre adresse>` ; lire les en-têtes reçus.
2. **SMS** — compte Twilio propriétaire du +1 215 715 5406, Geo permissions
   (Bénin), A2P 10DLC si destinataires américains. `.env.prod` : bloc SMS
   (`SMS_ENABLED=False`), `manage.py sms_check`, puis `sms_check --to
   <votre numéro>`, puis `SMS_ENABLED=True`. Recueillir les consentements
   (Mon profil) ou décision juridique sur `SMS_REQUIRE_EXPLICIT_CONSENT`.
3. **plugNmeet** — `PLUGNMEET_DEPLOYMENT_GUIDE.md` §§ 1-7 (serveur, DNS
   `pnm.globalfeba.com`, pare-feu Hetzner Cloud, certificat, recette, bascule).
4. **Migrations FEBA** (additives) : `manage.py migrate` — accounts 0007,
   notifications 0007, payments 0014, virtualclass 0004. Sauvegarde de la
   base AVANT (`RESTORE_GUIDE.md`).

## État constaté au moment de la livraison

Mesuré, pas supposé :

| Vérification | Commande | Résultat observé |
|---|---|---|
| `globalfeba.com` résout | `getent hosts globalfeba.com` | ✅ `62.238.38.111` |
| Le site répond en HTTPS | `curl -o /dev/null -w '%{http_code}' https://globalfeba.com/` | ✅ `200` |
| L'API répond | `curl -o /dev/null -w '%{http_code}' https://globalfeba.com/api/health/` | ✅ `200` |
| **`meet.globalfeba.com` résout** | `getent hosts meet.globalfeba.com` | ❌ **aucun enregistrement** |

La visioconférence est donc **indisponible en production**, et c'est
exactement ce que l'application affiche. Ce n'est pas un défaut logiciel :
il manque l'infrastructure décrite ci-dessous.

> **Défaut de configuration constaté sur le site en ligne.**
> Toute URL statique inexistante renvoie aujourd'hui `HTTP 200` avec la
> page HTML de l'application, au lieu d'un `404` :
> ```
> curl -sSI https://globalfeba.com/images/feba-fha/definitely-not-here.pdf
> → HTTP/2 200 ; content-type: text/html
> ```
> Un fichier manquant passe donc pour un fichier servi. Les règles Nginx
> livrées corrigent ce point pour le flyer (`try_files $uri =404`) ; le
> déploiement de `nginx/nginx.prod.conf` et `frontend/nginx.prod.conf` est
> ce qui rendra la correction effective.

---

## ACTION EXTERNE 01 — Serveur Jitsi (Hetzner)

**Service :** Hetzner Cloud
**Pourquoi :** l'instance de visioconférence doit être auto-hébergée. Le
backend **refuse** `meet.jit.si` (`JITSI_FORBIDDEN_DOMAINS`) : les cours
concernent des mineurs, et un flux qui transite chez un tiers sans
authentification n'est pas une option de repli.

| Paramètre | Valeur |
|---|---|
| Type | **CPX32** — 4 vCPU, 8 Go RAM, 160 Go SSD |
| Image | Ubuntu 24.04 LTS (ou 26.04) |
| Localisation | au choix ; **Helsinki** ou **Nuremberg** conviennent |
| Réseau | IPv4 publique **obligatoire** (le pont vidéo l'annonce aux navigateurs) |
| Nom suggéré | `feba-jitsi` |

Un CPX32 dimensionne confortablement des groupes de 10 à 15 élèves, la
taille annoncée sur le flyer FEBA FHA.

**Vérification**
```bash
ssh root@<IP_JITSI> 'docker --version && free -g'
```

---

## ACTION EXTERNE 02 — Enregistrement DNS (Hostinger)

**Service :** Hostinger — zone DNS de `globalfeba.com`

| Champ | Valeur |
|---|---|
| Type | `A` |
| Nom / Host | `meet` |
| Valeur | `<IP_PUBLIQUE_DU_SERVEUR_JITSI>` (action 01) |
| TTL | `3600` (300 pendant la mise en place, pour itérer vite) |
| Proxy | **aucun** — le trafic WebRTC ne doit pas être intermédié |

> Ne pas créer d'enregistrement `AAAA` tant que la pile n'est pas démarrée
> avec `ENABLE_IPV6=1` : un `AAAA` qui pointe une pile sans IPv6 fait
> échouer un navigateur sur deux, de façon intermittente — la panne la plus
> longue à diagnostiquer de cette liste.

**Vérification**
```bash
dig +short meet.globalfeba.com          # doit renvoyer l'IP de l'action 01
getent hosts meet.globalfeba.com
```

---

## ACTION EXTERNE 03 — Pare-feu Hetzner

**Service :** Hetzner Cloud → Firewalls, appliqué au serveur `feba-jitsi`.

| # | Protocole | Port | Source | Raison |
|---|---|---|---|---|
| 1 | TCP | `80` | `0.0.0.0/0`, `::/0` | Validation HTTP-01 de Let's Encrypt **et** redirection vers HTTPS. Sans ce port, la délivrance du certificat échoue et le conteneur redémarre en boucle. |
| 2 | TCP | `443` | `0.0.0.0/0`, `::/0` | Interface Jitsi et signalisation (BOSH / WebSocket). |
| 3 | **UDP** | `10000` | `0.0.0.0/0`, `::/0` | **Jitsi Videobridge — flux audio et vidéo.** Fermé, tout le monde se connecte, se voit dans la liste des participants, et **personne n'entend rien**. |
| 4 | TCP | `22` | **IP d'administration uniquement** | SSH. Ne pas ouvrir à `0.0.0.0/0`. |

**Vérification**
```bash
nc -z -w5 meet.globalfeba.com 443 && echo "443 ouvert"
nc -u -z -w5 meet.globalfeba.com 10000 && echo "10000/udp ouvert"
```

---

## ACTION EXTERNE 04 — Secrets de production

**Où :** sur le serveur, dans `.env.jitsi` et `.env.prod`. **Jamais dans Git.**

Les deux fichiers doivent porter **les mêmes valeurs** : c'est le secret
partagé qui fait qu'aucune salle ne s'ouvre sans une autorisation vérifiée
par Django. Un écart et chaque « Rejoindre » est refusé par Prosody, sans
message côté FEBA — la panne la plus déroutante de cette liste.

```bash
JITSI_APP_ID="feba_$(openssl rand -hex 6)"
JITSI_APP_SECRET="$(openssl rand -hex 32)"

# .env.jitsi (serveur Jitsi)          # .env.prod (serveur applicatif)
JITSI_APP_ID=$JITSI_APP_ID            JITSI_APP_ID=$JITSI_APP_ID
JITSI_APP_SECRET=$JITSI_APP_SECRET    JITSI_APP_SECRET=$JITSI_APP_SECRET
JITSI_DOMAIN=meet.globalfeba.com      JITSI_DOMAIN=meet.globalfeba.com
JITSI_PUBLIC_URL=https://meet.globalfeba.com
JVB_ADVERTISE_IPS=<IP_JITSI>          # action 01
LETSENCRYPT_EMAIL=<adresse réelle>
```

`JVB_ADVERTISE_IPS` et `LETSENCRYPT_EMAIL` n'ont **pas** de valeur par
défaut : `docker-compose.jitsi.prod.yml` refuse de démarrer sans elles,
plutôt que de démarrer une instance muette ou sans TLS.

**Vérification**
```bash
make jitsi-config-check     # cohérence des deux fichiers, sans réseau
```

---

## ACTION EXTERNE 05 — Démarrage de l'instance

```bash
# Sur le serveur Jitsi, dans le dépôt :
make jitsi-prod-up
# équivaut à :
#   docker compose -f docker-compose.jitsi.yml \
#                  -f docker-compose.jitsi.prod.yml \
#                  --env-file .env.jitsi up -d
```

**Vérification — depuis n'importe quelle machine :**
```bash
make jitsi-health JITSI_TARGET=meet.globalfeba.com
```

Le rapport nomme chaque contrôle séparément (configuration, domaine non
public, signature de jeton, DNS, TLS, HTTP, page Jitsi). Il doit finir par
`État : OPÉRATIONNEL`. Tant que l'action 02 n'est pas faite, il affiche
aujourd'hui :

```
 ÉCHEC  dns   Le domaine « meet.globalfeba.com » ne résout pas […].
               Créez l'enregistrement DNS A vers l'IP du serveur Jitsi
               (voir MANUAL_PRODUCTION_ACTIONS.md).
```

---

## ACTION EXTERNE 06 — Déploiement de l'application corrigée

Les correctifs P1 (numéro institutionnel) et P2 (flyer) sont dans le code ;
ils ne prennent effet qu'une fois déployés sur `globalfeba.com`.

```bash
git pull
docker compose -f docker-compose.prod.yml build frontend-prod backend-prod
docker compose -f docker-compose.prod.yml up -d
docker compose -f docker-compose.prod.yml exec backend-prod \
    python manage.py migrate          # applique schools.0015
docker compose -f docker-compose.prod.yml exec backend-prod \
    python manage.py init_academies   # aligne la colonne de gestion
docker compose -f docker-compose.prod.yml restart nginx-prod
```

`schools.0015_retire_legacy_institutional_phone` retire de la base le
numéro hors service. Ce n'est pas ce qui corrige les documents — ils ne
lisent plus cette colonne — mais l'écran « Paramètres » l'affiche encore.

**Vérification**
```bash
# Le flyer est servi en pièce jointe, et non en HTML :
curl -sSI https://globalfeba.com/images/feba-fha/feba-fha-flyer.pdf \
  | grep -iE 'HTTP|content-type|content-disposition'
# attendu : 200 · application/pdf · attachment; filename="FEBA-French-Heritage-Academy-flyer.pdf"

# Un fichier absent doit désormais répondre 404, et non 200 :
curl -sS -o /dev/null -w '%{http_code}\n' \
  https://globalfeba.com/images/feba-fha/definitely-not-here.pdf
# attendu : 404
```

Puis, dans l'application : générer un reçu et vérifier qu'il porte
`0160011717`.

---

## Récapitulatif

| # | Action | Prestataire | Faite ? |
|---|---|---|---|
| 01 | Serveur CPX32 | Hetzner | ⬜ **EXTERNAL ACTION REQUIRED** |
| 02 | DNS `A meet` | Hostinger | ⬜ **EXTERNAL ACTION REQUIRED** |
| 03 | Pare-feu 80/443 TCP + 10000 UDP | Hetzner | ⬜ **EXTERNAL ACTION REQUIRED** |
| 04 | Secrets JWT partagés | Serveur | ⬜ **EXTERNAL ACTION REQUIRED** |
| 05 | Démarrage de la pile | Serveur | ⬜ **EXTERNAL ACTION REQUIRED** |
| 06 | Déploiement de l'application corrigée | Serveur | ⬜ **EXTERNAL ACTION REQUIRED** |

Aucune de ces cases n'est cochée. Aucune ne peut l'être depuis ce dépôt.
