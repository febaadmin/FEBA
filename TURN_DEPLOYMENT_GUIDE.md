# FEBA — Guide de déploiement TURN / Coturn

**TURN n'est PAS déployé.** Ce document est un guide de préparation, pas
la description d'une installation existante. Aucune configuration TURN
n'est incluse dans la livraison : livrer un `docker-compose.turn.yml` non
testé, sans IP ni DNS ni pare-feu, donnerait l'apparence d'une
infrastructure là où rien ne fonctionnerait.

La décision et son argumentaire sont dans `TURN_DECISION.md`.
**Commencez par le test décisif qui s'y trouve** : il dit si la dépense
se justifie pour vos réseaux.

Statut de ce document : **EXTERNAL ACTION REQUIRED**.

---

## 1. Le problème de port, à régler d'abord

`meet.globalfeba.com` occupe déjà 443/tcp sur `89.167.63.1`. Coturn ne
peut pas s'y lier simultanément — et 443/tcp est précisément le port qui
traverse les pare-feu, donc celui qui donne son intérêt à TURN.

| Option | Principe | Coût mensuel | Verdict |
|---|---|---|---|
| **A** | IP flottante Hetzner, Coturn en 443 | ~1 € | **recommandée** |
| B | Coturn sur 5349/tcp, même IP | 0 € | **à écarter** — 5349 est souvent bloqué, ce qui vide TURN de son objet |
| C | Serveur dédié Coturn | ~4 € | si le trafic relayé devient significatif |

L'option B mérite d'être nommée pour être écartée : elle donne
l'apparence d'une solution en laissant exactement les mêmes utilisateurs
dehors.

---

## 2. Architecture visée (option A)

```
turn.globalfeba.com  →  IP flottante Hetzner (à commander)

  443/tcp    TURN over TLS      ← le chemin qui traverse les pare-feu
  443/udp    TURN               ← plus rapide quand l'UDP passe
  3478/udp   STUN/TURN clair    ← réseaux ouverts
  49152-65535/udp               ← ports de relais
```

---

## 3. Ce qu'il faut obtenir avant toute installation

Ces quatre points ne sont pas dans le dépôt et ne peuvent pas l'être.

| # | Action | Où |
|---|---|---|
| 1 | Commander une IP flottante | console Hetzner Cloud → *Floating IPs* |
| 2 | L'attacher au serveur | même écran → *Assign* |
| 3 | Créer `turn.globalfeba.com` → cette IP | Hostinger → DNS → enregistrement A |
| 4 | Ouvrir 443/tcp, 443/udp, 3478/udp, 49152-65535/udp **sur cette IP** | Hetzner → *Firewalls* |

- [ ] Les quatre sont faits avant de passer au §4

---

## 4. Secrets

Coturn et Prosody doivent partager **un** secret. Il ne va jamais dans le
dépôt ni dans le frontend.

```bash
# Sur le serveur, une seule fois :
openssl rand -hex 32
```

À reporter dans `.env.jitsi` :

```
TURN_SECRET=<la valeur générée>
TURN_HOST=turn.globalfeba.com
```

> **Le navigateur ne reçoit jamais ce secret.** Prosody dérive des
> identifiants **éphémères** (RFC 5766 §10.2 : utilisateur =
> horodatage, mot de passe = HMAC du secret) et les transmet par XMPP.
> Un identifiant intercepté expire en quelques heures ; le secret, lui,
> ne quitte pas le serveur.

---

## 5. Certificat TLS

TURN over TLS a besoin d'un certificat valide pour `turn.globalfeba.com`.
Le plus simple est de réutiliser le mécanisme ACME déjà en place :

```bash
certbot certonly --standalone -d turn.globalfeba.com
```

**Attention au conflit :** `--standalone` occupe le port 80. Si Jitsi est
sur la même machine et publie 80, arrêtez-le le temps de la délivrance,
ou utilisez `--webroot` sur le répertoire servi par Jitsi.

---

## 6. Intégration côté Jitsi

Les variables que Prosody attend :

```
TURN_HOST=turn.globalfeba.com
TURN_PORT=443
TURNS_HOST=turn.globalfeba.com
TURNS_PORT=443
TURN_TRANSPORT=tcp
TURN_CREDENTIALS=<TURN_SECRET>
```

Puis, sur le serveur :

```bash
cd /opt/feba/app
docker compose -f docker-compose.jitsi.yml -f docker-compose.jitsi.prod.yml \
  up -d prosody jvb
```

---

## 7. Vérifier que TURN fonctionne VRAIMENT

Un service qui démarre ne prouve pas qu'il relaie.

### 7.1 Le port répond

```bash
# depuis une machine externe
nc -vz turn.globalfeba.com 443
openssl s_client -connect turn.globalfeba.com:443 </dev/null 2>&1 | head -12
```

### 7.2 Des candidats `relay` apparaissent

Le seul contrôle qui compte. Dans une conférence FEBA, ouvrir
`chrome://webrtc-internals` :

| Observation | Conclusion |
|---|---|
| au moins un candidat de type `relay` | **TURN fonctionne** |
| aucun candidat `relay` | TURN n'est pas utilisé — identifiants, port ou pare-feu |

### 7.3 Le test qui justifiait TURN

Refaire le test décisif de `TURN_DECISION.md` §6 depuis le réseau qui
échouait auparavant. S'il passe maintenant, TURN a rempli son office.

- [ ] Réunion établie depuis un réseau bloquant l'UDP sortant

---

## 8. Ce qu'il faut surveiller ensuite

TURN relaie le média : il consomme de la bande passante pour chaque
participant qui en dépend.

```bash
docker compose logs --tail=100 coturn | grep -iE "allocat|refused|error"
```

Si la part des sessions relayées devient importante, l'option C (serveur
dédié) devient pertinente.

---

## 9. Statut de chaque étape

| Étape | Statut |
|---|---|
| Décision argumentée | **fournie** (`TURN_DECISION.md`) |
| Test décisif du besoin | **À TESTER EN ENVIRONNEMENT RÉEL** |
| IP flottante, DNS, pare-feu | **EXTERNAL ACTION REQUIRED** |
| Installation Coturn | **non faite** |
| Vérification du relais | **À TESTER EN ENVIRONNEMENT RÉEL** |

Aucune de ces lignes ne doit être marquée PASS sans preuve.
