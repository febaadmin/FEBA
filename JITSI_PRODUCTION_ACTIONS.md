# FEBA — Actions à exécuter sur le serveur Jitsi

**EXTERNAL ACTION REQUIRED.** Cet environnement n'a pas d'accès SSH au
serveur Jitsi. Rien de ce qui suit n'a été exécuté ; ce sont les commandes
exactes à copier-coller.

| | |
|---|---|
| Serveur | `89.167.63.1` (Hetzner) |
| Domaine | `meet.globalfeba.com` |
| Topologie déployée | **serveur dédié** — le nginx du conteneur `jitsi/web` publie 80 et 443 |

---

## 0. Pourquoi ces actions existent

`meet.globalfeba.com` renvoie ces en-têtes :

```
strict-transport-security: max-age=63072000
x-content-type-options: nosniff
x-xss-protection: 1; mode=block
permissions-policy: interest-cohort=()
```

C'est la **signature exacte** du gabarit de l'image `jitsi/web`
(`web/rootfs/defaults/meet.conf`). La production est donc servie par le
nginx **du conteneur**, et le fichier
`nginx/sites-available/meet.globalfeba.com.conf` du dépôt — parfaitement
correct — appartient à l'autre topologie (« derrière le proxy ») et n'est
jamais lu ici.

Ce n'était donc pas une configuration oubliée, mais une configuration
écrite pour une topologie qui n'est pas celle en service.

**Manquent aujourd'hui :** `Referrer-Policy` et
`Content-Security-Policy: frame-ancestors`. Sans le second, n'importe quel
site peut afficher vos cours dans une iframe.

---

## 1. Se connecter et localiser la pile

```bash
ssh root@89.167.63.1
cd /opt/feba          # adapter si le dépôt est ailleurs
docker compose -f docker-compose.jitsi.yml -f docker-compose.jitsi.prod.yml ps
```

**Résultat attendu :** les services `jitsi-web`, `prosody`, `jicofo`, `jvb`
en état `running`.

---

## 2. Sauvegarder avant toute modification

```bash
cd /opt/feba
git rev-parse HEAD > /root/feba-jitsi-avant-$(date +%F).txt
cp .env.jitsi /root/.env.jitsi.bak-$(date +%F)
docker compose -f docker-compose.jitsi.yml -f docker-compose.jitsi.prod.yml \
  config > /root/compose-jitsi-avant-$(date +%F).yml
```

---

## 3. Mettre le dépôt à jour

```bash
cd /opt/feba
git fetch origin
git checkout claude/serene-ramanujan-wh16c4
git pull --ff-only
ls -l jitsi/nginx-custom/feba-security-headers.conf
```

**Résultat attendu :** le fichier existe.

---

## 4. Vérifier que l'image accepte le point d'extension

Cette vérification est **indispensable** : le mécanisme est présent dans
le gabarit de `jitsi/web` sur `master`, mais l'image `:stable` déployée
peut être plus ancienne.

```bash
docker compose -f docker-compose.jitsi.yml -f docker-compose.jitsi.prod.yml \
  exec jitsi-web grep -n "nginx-custom\|CSP_HEADER" /defaults/meet.conf
```

| Sortie | Conclusion |
|---|---|
| les deux lignes apparaissent | passer au §5 |
| `nginx-custom` absent | passer au **§5 bis** |
| `CSP_HEADER` absent | la CSP se pose alors dans le fichier `.conf`, voir §5 bis |

---

## 5. Appliquer (cas normal)

```bash
cd /opt/feba
grep -q '^JITSI_CSP_HEADER=' .env.jitsi || cat >> .env.jitsi <<'EOF'
JITSI_CSP_HEADER=frame-ancestors 'self' https://globalfeba.com https://www.globalfeba.com
EOF

docker compose -f docker-compose.jitsi.yml -f docker-compose.jitsi.prod.yml \
  --env-file .env.jitsi config > /dev/null && echo "assemblage valide"

docker compose -f docker-compose.jitsi.yml -f docker-compose.jitsi.prod.yml \
  --env-file .env.jitsi up -d jitsi-web
```

Contrôle de la syntaxe nginx **dans le conteneur**, avant de conclure :

```bash
docker compose -f docker-compose.jitsi.yml -f docker-compose.jitsi.prod.yml \
  exec jitsi-web nginx -t
```

**Résultat attendu :** `syntax is ok` puis `test is successful`.

---

## 5 bis. Si l'image ne connaît pas `nginx-custom`

Écrire directement dans la configuration montée, puis recharger :

```bash
CONF=$(docker volume inspect feba_jitsi-web-config -f '{{ .Mountpoint }}')
cp "$CONF/nginx/meet.conf" /root/meet.conf.bak-$(date +%F)

sed -i '/add_header X-XSS-Protection/a add_header Referrer-Policy "strict-origin-when-cross-origin" always;\nadd_header Content-Security-Policy "frame-ancestors '"'"'self'"'"' https://globalfeba.com https://www.globalfeba.com" always;' \
  "$CONF/nginx/meet.conf"

docker compose -f docker-compose.jitsi.yml -f docker-compose.jitsi.prod.yml \
  exec jitsi-web nginx -t && \
docker compose -f docker-compose.jitsi.yml -f docker-compose.jitsi.prod.yml \
  exec jitsi-web nginx -s reload
```

> **Attention.** Ce fichier est régénéré à chaque démarrage du conteneur
> depuis le gabarit : la modification sera **perdue** au prochain
> `up`/`restart`. C'est une mesure d'attente, pas une solution. Mettre à
> jour l'image `jitsi/web` pour retrouver le point d'extension.

---

## 6. Vérifier depuis l'extérieur

```bash
curl -sSI https://meet.globalfeba.com/ | grep -iE 'referrer-policy|content-security-policy|strict-transport|x-content-type'
```

**Résultat attendu :**

```
strict-transport-security: max-age=63072000; includeSubDomains
x-content-type-options: nosniff
referrer-policy: strict-origin-when-cross-origin
content-security-policy: frame-ancestors 'self' https://globalfeba.com https://www.globalfeba.com
```

Puis, depuis n'importe quelle machine ayant le dépôt :

```bash
make jitsi-health JITSI_TARGET=meet.globalfeba.com
```

**Résultat attendu :** le contrôle `entetes_securite` passe de **ÉCHEC** à
**OK**.

---

## 7. Vérifier que la conférence marche TOUJOURS

C'est le contrôle qui compte le plus : une CSP mal posée rend Jitsi noir
et muet, et l'erreur n'apparaît que dans la console du navigateur.

1. Ouvrir FEBA, se connecter comme enseignant ;
2. Salles virtuelles → **Rejoindre** ;
3. la conférence doit s'ouvrir dans le nouvel onglet et afficher la vidéo ;
4. ouvrir la console (F12) : **aucune** erreur mentionnant
   `Content Security Policy` ou `frame-ancestors`.

Si la conférence ne s'ouvre plus → §8 immédiatement.

---

## 8. Rollback

```bash
cd /opt/feba
sed -i '/^JITSI_CSP_HEADER=/d' .env.jitsi
docker compose -f docker-compose.jitsi.yml -f docker-compose.jitsi.prod.yml \
  --env-file .env.jitsi up -d jitsi-web
```

Si le §5 bis avait été utilisé :

```bash
CONF=$(docker volume inspect feba_jitsi-web-config -f '{{ .Mountpoint }}')
cp /root/meet.conf.bak-$(date +%F) "$CONF/nginx/meet.conf"
docker compose -f docker-compose.jitsi.yml -f docker-compose.jitsi.prod.yml \
  exec jitsi-web nginx -s reload
```

Vérification du retour arrière :

```bash
curl -sSI https://meet.globalfeba.com/ | head -8
```

---

## 9. WebSocket XMPP (§6)

Non vérifiable depuis l'environnement de développement : son mandataire ne
relaie aucune mise à niveau WebSocket — contrôlé, un service public de
test échoue identiquement.

**Depuis votre Mac :**

```bash
brew install websocat 2>/dev/null || true
websocat -v wss://meet.globalfeba.com/xmpp-websocket
```

**Résultat attendu :** `101 Switching Protocols`, puis la connexion
**reste ouverte**. Une fermeture immédiate indique un `proxy_read_timeout`
trop court ou un `Upgrade` non transmis.

Variante sans installation :

```bash
curl -sS -i --http1.1 -N \
  -H "Connection: Upgrade" -H "Upgrade: websocket" \
  -H "Sec-WebSocket-Version: 13" -H "Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==" \
  https://meet.globalfeba.com/xmpp-websocket | head -12
```

**Attendu :** `HTTP/1.1 101 Switching Protocols`.

**Depuis le serveur**, si le résultat est mauvais :

```bash
docker compose -f docker-compose.jitsi.yml -f docker-compose.jitsi.prod.yml \
  logs --tail=100 prosody
docker compose -f docker-compose.jitsi.yml -f docker-compose.jitsi.prod.yml \
  exec jitsi-web grep -n "xmpp-websocket" -A 8 /config/nginx/meet.conf
```

---

## 10. JVB et UDP 10000 (§7)

**Depuis le serveur — port publié :**

```bash
docker compose -f docker-compose.jitsi.yml -f docker-compose.jitsi.prod.yml \
  port jvb 10000/udp
ss -lunp | grep 10000
```

**Attendu :** `0.0.0.0:10000`.

**IP annoncée :**

```bash
docker compose -f docker-compose.jitsi.yml -f docker-compose.jitsi.prod.yml \
  exec jvb printenv JVB_ADVERTISE_IPS
```

**Attendu :** `89.167.63.1`. Une valeur vide ou une adresse `172.x` fait
que les participants entrent dans la salle **et ne se voient pas**.

**Pare-feu système :**

```bash
ufw status | grep 10000 || iptables -L -n | grep 10000
```

**Depuis un réseau EXTERNE (votre Mac) :**

```bash
nc -vzu 89.167.63.1 10000
```

**Pare-feu Hetzner :** cette vérification demande la console Hetzner
Cloud → *Firewalls*. Je n'y ai pas accès. Vérifier qu'une règle entrante
autorise **UDP/10000** depuis `0.0.0.0/0`, ainsi que TCP/80 et TCP/443.

**Candidats ICE, pendant une réunion :**

```bash
docker compose -f docker-compose.jitsi.yml -f docker-compose.jitsi.prod.yml \
  logs --tail=200 jvb | grep -iE "candidate|harvest|advertise"
```

---

## 11. Redémarrage (§14)

```bash
cd /opt/feba
docker compose -f docker-compose.jitsi.yml -f docker-compose.jitsi.prod.yml restart
sleep 30
make jitsi-health JITSI_TARGET=meet.globalfeba.com
```

Puis un vrai redémarrage machine :

```bash
reboot
# attendre, puis :
ssh root@89.167.63.1 'cd /opt/feba && docker compose -f docker-compose.jitsi.yml -f docker-compose.jitsi.prod.yml ps'
```

**Sur le réseau partagé.** L'erreur historique
« network feba_jitsi_shared declared as external, but could not be found »
ne peut plus bloquer un démarrage par le chemin documenté :
`docker-compose.yml` **possède** le réseau et le crée, la pile Jitsi le
déclare `external` et le **rejoint**, et `scripts/jitsi_up.sh` le crée si
Jitsi démarre en premier. Si la pile Jitsi est démarrée seule et
manuellement, sans passer par `make jitsi-up` :

```bash
docker network inspect feba_jitsi_shared >/dev/null 2>&1 || \
  docker network create feba_jitsi_shared
```

---

## 12. Ce qui reste hors de portée

| Action | Où |
|---|---|
| Pare-feu Hetzner (UDP/10000, TCP/80, TCP/443) | console Hetzner Cloud |
| Enregistrement DNS | Hostinger |
| Décision et déploiement TURN | voir `TURN_DECISION.md` |
