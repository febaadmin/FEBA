# Visioconférence FEBA — instance auto-hébergée `meet.globalfeba.com`

Guide de déploiement, d'exploitation et de dépannage de l'instance Jitsi
du groupe FEBA.

> **Ce guide décrit une infrastructure qui n'est pas encore en service.**
> Au moment de la livraison, `meet.globalfeba.com` ne résout pas. Les
> actions à mener hors du dépôt sont listées dans
> [`MANUAL_PRODUCTION_ACTIONS.md`](MANUAL_PRODUCTION_ACTIONS.md).

---

## 1. Pourquoi une instance auto-hébergée

`meet.jit.si` est **refusé par le code**, pas seulement déconseillé :

```python
# backend/feba_project/settings/base.py
JITSI_FORBIDDEN_DOMAINS = ('meet.jit.si', 'jitsi.org', '8x8.vc')
```

Trois raisons, dans l'ordre d'importance :

1. **Protection des mineurs.** Les cours FEBA FHA réunissent des enfants de
   6 à 17 ans. Sur une instance publique, le flux transite chez un tiers et
   **toute personne connaissant le nom de la salle y entre** — sans compte,
   sans invitation, sans trace.
2. **Aucune authentification.** FEBA ne peut vérifier ni qui rejoint, ni
   depuis quelle académie, ni s'il appartient à la classe.
3. **Limite de 5 minutes** sur les appels de démonstration.

Il n'existe donc **aucun repli automatique**. Une configuration incomplète
produit une erreur d'infrastructure explicite (HTTP 503) et un bandeau de
diagnostic — jamais une session publique ouverte en silence.

---

## 2. Architecture

```
Navigateur (parent, élève, enseignant)
   │
   │  1. « Rejoindre » → FEBA vérifie les droits
   ▼
┌─────────────────────────────┐        JITSI_APP_SECRET
│  Django — globalfeba.com    │        (partagé, connu des deux seuls)
│  assert_can_join()          │◄───────────────────────┐
│  build_jitsi_jwt()          │                        │
└──────────────┬──────────────┘                        │
               │  2. jeton signé, 15 min, salle nommée │
               ▼                                       │
┌──────────────────────────────────────────────────────┴──────┐
│  meet.globalfeba.com — serveur Hetzner CPX32, dédié          │
│                                                              │
│   jitsi-web   nginx + interface   :80 :443/tcp               │
│   prosody     XMPP, VALIDE LE JETON (JWT_ALLOW_EMPTY=0)      │
│   jicofo      conférences                                    │
│   jvb         pont audio/vidéo    :10000/udp                 │
└──────────────────────────────────────────────────────────────┘
```

**Le point important :** Django ne fait pas *confiance* au client, et Jitsi
ne fait pas *confiance* à Django sans preuve. Le jeton nomme la salle
(`room`), porte l'académie et le rôle, et expire en 15 minutes. Un jeton
intercepté n'ouvre ni une autre salle, ni un accès durable.

Contrôles appliqués avant émission (`apps/virtualclass/services.py`,
`assert_can_join`) :

1. l'académie de la salle est celle de l'utilisateur — un utilisateur FEBA
   ne rejoint **jamais** une salle FEBA FHA ;
2. l'académie a la fonctionnalité `video_conferencing` ;
3. le compte est actif ;
4. la salle est active et non annulée ;
5. élèves et parents doivent être rattachés à la classe de la salle.

---

## 2 bis. DEUX TOPOLOGIES — choisir avant tout le reste

C'est la décision qui conditionne tout le déploiement, et se tromper ne
se voit qu'au moment où le site principal tombe.

**Le conflit, mesuré sur les fichiers livrés :**

| Service | Fichier | Ports de l'hôte |
|---|---|---|
| `nginx-prod` (site FEBA) | `docker-compose.prod.yml` | **80, 443** |
| `jitsi-web` (serveur dédié) | `docker-compose.jitsi.prod.yml` | **80, 443** |

Les deux revendiquent les mêmes ports. Sur le serveur qui sert déjà
`globalfeba.com`, ils ne peuvent pas coexister : soit `jitsi-prod-up`
échoue sur *« Bind for 0.0.0.0:443 failed: port is already allocated »*,
soit — si Jitsi démarre en premier — **c'est le site principal qui ne
redémarre plus**.

### Topologie A — serveur DÉDIÉ à Jitsi

Un second serveur (le CPX32 de `MANUAL_PRODUCTION_ACTIONS.md`), qui ne
sert rien d'autre. Jitsi prend 80/443 et gère lui-même son certificat.

```bash
make jitsi-prod-up          # docker-compose.jitsi.prod.yml
```

*À retenir :* c'est le seul cas où la surcouche `prod` est utilisable.

### Topologie B — MÊME serveur que `globalfeba.com`

Jitsi n'écoute que sur la boucle locale ; le nginx de FEBA termine TLS et
sert `meet.globalfeba.com`. Aucun port public n'est disputé.

```bash
make jitsi-proxy-up         # docker-compose.jitsi.behind-proxy.yml

# puis, côté FEBA, activer le vhost livré :
cp nginx/sites-available/meet.globalfeba.com.conf nginx/sites-enabled/
docker compose -f docker-compose.prod.yml exec nginx-prod nginx -t     # AVANT de recharger
docker compose -f docker-compose.prod.yml exec nginx-prod nginx -s reload
```

Le `nginx -t` n'est pas une formalité : ce nginx sert aussi le site
principal, et un vhost dont le certificat manque l'empêche de démarrer.
C'est précisément pour cela que le vhost est livré **dans
`sites-available/` et non activé** — `sites-enabled/` est vide.

### Ce qui ne change pas d'une topologie à l'autre

`ENABLE_AUTH=1`, `ENABLE_GUESTS=0`, `AUTH_TYPE=jwt`, `JWT_ALLOW_EMPTY=0`
et `JVB_ADVERTISE_IPS`. Une seconde topologie qui relâcherait
l'authentification serait pire qu'une instance publique : elle porterait
le nom de l'établissement.

`UDP/10000` reste publié dans les deux cas — le média ne passe pas par le
proxy HTTP, et aucun autre service FEBA n'utilise ce port.

### Le piège du proxy : la salle qui reste vide

En topologie B, trois emplacements doivent être relayés, faute de quoi
tout le monde entre dans la salle **sans jamais se voir** :

| Emplacement | Rôle |
|---|---|
| `/xmpp-websocket` | signalisation principale |
| `/colibri-ws/…` | WebSocket du pont vidéo |
| `/http-bind` | repli BOSH derrière un pare-feu restrictif |

Les trois exigent `proxy_set_header Upgrade` / `Connection "upgrade"`, et
`X-Forwarded-Proto` — sans lui Jitsi compose des URL `http://` depuis une
page `https://`, que le navigateur bloque : la salle reste noire. Le
vhost livré les pose déjà ; c'est ce que verrouille
`test_le_vhost_relaie_la_signalisation_temps_reel`.

Le vhost n'envoie **pas** `X-Frame-Options: DENY`, contrairement au site
principal : l'application affiche la salle dans une iframe. L'encadrement
est restreint par `frame-ancestors` au lieu d'être interdit.

---

## 3. Prérequis

| Élément | Valeur |
|---|---|
| Serveur | Hetzner **CPX32** — 4 vCPU, 8 Go, 160 Go SSD (topologie A) ; ou le serveur FEBA existant (topologie B) |
| Système | Ubuntu 24.04 LTS |
| Domaine | `meet.globalfeba.com` → enregistrement `A` chez Hostinger |
| Ports | `80/tcp`, `443/tcp`, **`10000/udp`** |
| Logiciels | Docker + Docker Compose v2, `openssl` |

**Serveur dédié si possible.** Le pont vidéo sature réseau et CPU pendant
les cours, et une classe en direct ne doit pas pouvoir ralentir la
facturation ou les bulletins. La topologie B reste parfaitement
fonctionnelle — c'est un compromis de coût assumé, pas un défaut de
configuration — mais elle fait partager les ressources.

---

## 4. Déploiement

### 4.1 DNS et pare-feu

Voir `MANUAL_PRODUCTION_ACTIONS.md`, actions 02 et 03. **À faire avant**
tout démarrage : Let's Encrypt valide le domaine par HTTP-01 et échoue si
le DNS ne pointe pas encore le serveur.

```bash
dig +short meet.globalfeba.com     # doit renvoyer l'IP du serveur
```

### 4.2 Secrets

```bash
cp .env.jitsi.example .env.jitsi
JITSI_APP_ID="feba_$(openssl rand -hex 6)"
JITSI_APP_SECRET="$(openssl rand -hex 32)"
```

Renseigner dans `.env.jitsi` :

```ini
JITSI_APP_ID=feba_xxxxxxxxxxxx
JITSI_APP_SECRET=<64 caractères hexadécimaux>
JITSI_DOMAIN=meet.globalfeba.com
JITSI_PUBLIC_URL=https://meet.globalfeba.com
LETSENCRYPT_EMAIL=<adresse réelle et relevée>
JVB_ADVERTISE_IPS=<IP publique du serveur>
JVB_PORT=10000
ENABLE_IPV6=0
```

Puis **les mêmes** `JITSI_APP_ID` / `JITSI_APP_SECRET` dans le `.env.prod`
du serveur applicatif, avec `JITSI_DOMAIN=meet.globalfeba.com`.

```bash
make jitsi-config-check     # vérifie l'égalité des deux côtés, sans réseau
```

### 4.3 Démarrage

```bash
make jitsi-prod-up
```

Le premier démarrage prend quelques minutes : Prosody génère ses
certificats internes et Let's Encrypt délivre le certificat public.

### 4.4 Vérification

```bash
make jitsi-health JITSI_TARGET=meet.globalfeba.com
```

Attendu :

```
État               : OPÉRATIONNEL
Contrôles :
  OK    configuration        Domaine « meet.globalfeba.com », identifiants JWT présents.
  OK    domaine_non_public   « meet.globalfeba.com » n'est pas une instance publique interdite.
  OK    signature_jeton      Un jeton de test a été signé.
  OK    dns                  meet.globalfeba.com → <IP>
  OK    tls                  Certificat valide pour meet.globalfeba.com, expire le …
  OK    http                 HTTP 200 sur https://meet.globalfeba.com/
  OK    endpoint_jitsi       La page servie est celle de Jitsi Meet.
```

Puis **un vrai cours** : deux navigateurs, deux comptes de la même classe,
caméra et micro. Un rapport vert prouve que l'instance répond ; seul un
appel réel prouve que le média passe.

---

## 5. Exploitation

| Commande | Effet |
|---|---|
| `make jitsi-prod-up` | démarre la pile — **serveur dédié** (topologie A) |
| `make jitsi-prod-down` | arrête la pile dédiée |
| `make jitsi-proxy-up` | démarre la pile — **même serveur** (topologie B) |
| `make jitsi-proxy-down` | arrête la pile derrière proxy |
| `make jitsi-proxy-logs` | journaux de la pile derrière proxy |
| `make jitsi-restart` | redémarre **sans** régénérer les secrets |
| `make jitsi-prod-logs` | journaux en continu |
| `make jitsi-health` | contrôle complet (local) |
| `make jitsi-health JITSI_TARGET=meet.globalfeba.com` | contrôle de la production |
| `make jitsi-config-check` | cohérence de configuration, sans réseau |

> **Ne jamais régénérer `JITSI_APP_SECRET` pendant les heures de cours.**
> Les jetons en circulation deviennent invalides instantanément : toutes
> les séances en cours sont coupées. `make jitsi-restart` ne touche pas aux
> secrets, contrairement à une réinitialisation de `.env.jitsi`.

### Rotation des secrets

À faire hors des heures de cours, dans cet ordre :

1. générer le nouveau couple ;
2. l'écrire dans `.env.jitsi` **et** `.env.prod` ;
3. `make jitsi-prod-down && make jitsi-prod-up` ;
4. redémarrer le backend applicatif ;
5. `make jitsi-config-check` puis `make jitsi-health JITSI_TARGET=…`.

---

## 6. Dépannage

| Symptôme | Cause la plus fréquente | Geste |
|---|---|---|
| Bandeau « instance FEBA non configurée » | `JITSI_DOMAIN` / `JITSI_APP_*` absents côté **backend** | renseigner `.env.prod`, redémarrer le backend |
| `jitsi-health` : `ÉCHEC dns` | l'enregistrement `A` n'existe pas | action 02 de `MANUAL_PRODUCTION_ACTIONS.md` |
| `jitsi-health` : `ÉCHEC tls` | certificat expiré, ou port 443 fermé | `make jitsi-prod-logs`, vérifier le pare-feu |
| `jitsi-health` : `ÉCHEC endpoint_jitsi` | un autre vhost répond sur le domaine | vérifier le reverse proxy |
| **Tout le monde se voit, personne ne s'entend** | **`10000/udp` fermé, ou `JVB_ADVERTISE_IPS` absent** | action 03 ; vérifier la variable |
| « Rejoindre » refusé sans message | `JITSI_APP_SECRET` différent entre les deux fichiers | `make jitsi-config-check` |
| Le conteneur `jitsi-web` redémarre en boucle | échec Let's Encrypt (port 80 fermé) ou IPv6 sans pile | ouvrir `80/tcp` ; `ENABLE_IPV6=0` |
| `port is already allocated` sur 80 ou 443 | topologie A lancée sur le serveur qui sert déjà globalfeba.com | passer en topologie B : `make jitsi-proxy-up` |
| **Le site principal ne redémarre plus** | Jitsi a pris 80/443 avant nginx-prod | `make jitsi-prod-down`, redémarrer nginx-prod, puis topologie B |
| nginx refuse de démarrer après activation du vhost | certificat `meet.globalfeba.com` absent | émettre le certificat, ou retirer le fichier de `sites-enabled/` |
| Tout le monde entre, personne ne se voit | WebSocket non relayé par le proxy (topologie B) | vérifier `/xmpp-websocket` et `/colibri-ws/` dans le vhost |
| HTTP 503 sur `/api/virtual-rooms/<id>/join/` | **comportement voulu** : instance indisponible | `make jitsi-health` pour la cause exacte |

Le 503 n'est pas une panne à contourner : c'est le refus explicite de
basculer un cours vers un service public.

---

## 7. Sauvegarde

Jitsi ne stocke aucune donnée pédagogique : ni notes, ni élèves, ni
enregistrements (Jibri n'est pas déployé). Une reconstruction complète du
serveur ne perd donc **aucune donnée FEBA**.

À sauvegarder malgré tout :

```bash
cp .env.jitsi /chemin/sauvegarde/env.jitsi.$(date +%F)   # secrets
docker run --rm -v jitsi-prosody-config:/c -v "$PWD":/b alpine \
    tar czf /b/prosody-config.tgz -C /c .                # certificats internes
```

Le script `scripts/backup_jitsi.sh` fourni couvre ces éléments.

Perdre `.env.jitsi` n'est pas dramatique : il suffit de régénérer les
secrets **des deux côtés** (§5) et de redémarrer.

---

## 8. Mise à jour

```bash
docker compose -f docker-compose.jitsi.yml -f docker-compose.jitsi.prod.yml \
               --env-file .env.jitsi pull
make jitsi-prod-up
make jitsi-health JITSI_TARGET=meet.globalfeba.com
```

Les images sont épinglées sur `stable`. Faire la mise à jour hors des
heures de cours et vérifier par un appel réel : une montée de version de
`jvb` peut demander un ajustement de `JVB_ADVERTISE_IPS`.
