# FEBA — TURN / Coturn : décision technique

**Décision : OUI, TURN est nécessaire pour FEBA French Heritage Academy.**
Il n'est **pas** déployé à ce jour.

Statut : **EXTERNAL ACTION REQUIRED** (installation serveur) —
**À TESTER EN ENVIRONNEMENT RÉEL** (mesure de l'impact).

---

## 1. Pourquoi la question se pose vraiment ici

Sans TURN, un participant établit son flux média en **UDP direct** vers
`89.167.63.1:10000`. Quand ce port sortant est bloqué, le participant
entre dans la salle, voit la liste des présents… et n'entend rien. Le
symptôme est trompeur : la signalisation marche, seul le média manque.

La population de FEBA FHA rend ce cas fréquent plutôt qu'exotique :

| Contexte | UDP sortant vers un port haut |
|---|---|
| Wi-Fi d'école ou d'université | souvent filtré |
| Réseau d'entreprise | fréquemment bloqué |
| Hôtel, aéroport, bibliothèque | portail captif, UDP restreint |
| Certains opérateurs mobiles | NAT symétrique |
| Diaspora derrière un CGNAT | traversée impossible |

FEBA FHA est une **académie en ligne destinée à la diaspora** : ses élèves
se connectent depuis des réseaux que l'établissement ne contrôle pas.
C'est précisément la situation où l'absence de TURN se paie.

Pour FEBA Cotonou, campus présentiel sans visioconférence
(`video_conferencing: False`), la question ne se pose pas.

---

## 2. Ce que TURN change, et ce qu'il ne change pas

TURN est un **relais de dernier recours**. Il n'améliore pas la qualité :
il rend la connexion possible là où elle ne l'était pas. Le média transite
alors par le serveur TURN, ce qui consomme de la bande passante — d'où
l'intérêt de ne l'utiliser qu'en repli, ce que fait ICE naturellement.

Coturn écoutant en **TLS sur 443/tcp** traverse presque tous les réseaux
filtrants, parce qu'un pare-feu qui bloque 443 sortant bloque le web
entier.

---

## 3. Le conflit de port, et comment le résoudre

`meet.globalfeba.com` occupe déjà 443/tcp sur `89.167.63.1`. Coturn ne
peut pas s'y lier simultanément. Trois options :

| Option | Principe | Coût | Recommandation |
|---|---|---|---|
| **A** | Coturn sur une **seconde IP** (IP flottante Hetzner), 443/tcp | ~1 €/mois | **recommandée** |
| B | Coturn sur un port alternatif (5349/tcp) | gratuit | insuffisant : 5349 est souvent bloqué, ce qui vide TURN de son intérêt |
| C | Serveur dédié Coturn | ~4 €/mois | pertinent si le trafic relayé devient significatif |

L'option B mérite d'être écartée explicitement : déployer TURN sur un port
filtré donne l'illusion d'une solution tout en laissant exactement les
mêmes utilisateurs dehors.

---

## 4. Architecture proposée (option A)

```
turn.globalfeba.com  →  IP flottante Hetzner
    443/tcp   TURN over TLS   ← le chemin qui traverse les pare-feu
    443/udp   TURN            ← plus rapide quand l'UDP passe
    3478      STUN/TURN clair ← réseaux ouverts
    49152-65535/udp           ← ports de relais
```

Certificat : le **même** mécanisme ACME que Jitsi, sur `turn.globalfeba.com`.

Authentification : `use-auth-secret` avec un secret partagé, et des
identifiants **éphémères** dérivés par horodatage (RFC 5766 §10.2). Le
navigateur reçoit un couple utilisateur/mot de passe valable quelques
heures, pas le secret lui-même.

> Le secret TURN ne va **jamais** dans le frontend. Prosody le connaît et
> distribue les identifiants éphémères via le protocole XMPP, comme il le
> fait déjà pour le reste de la configuration.

---

## 5. Ce qu'il reste à faire, et par qui

| Étape | Qui | Statut |
|---|---|---|
| Commander une IP flottante Hetzner | vous | **EXTERNAL ACTION REQUIRED** |
| Enregistrement DNS `turn.globalfeba.com` | vous (Hostinger) | **EXTERNAL ACTION REQUIRED** |
| Ouvrir 443/tcp, 443/udp, 3478, 49152-65535/udp sur cette IP | vous (pare-feu Hetzner) | **EXTERNAL ACTION REQUIRED** |
| Déployer Coturn et le raccorder à Prosody | à écrire | **non fait** |
| Mesurer le taux de repli TURN | après déploiement | **À TESTER EN ENVIRONNEMENT RÉEL** |

**Ce qui n'est pas fait est écrit comme non fait.** Livrer un
`docker-compose.turn.yml` non testé, sans IP ni DNS ni pare-feu, donnerait
l'apparence d'une infrastructure prête là où rien ne fonctionnerait — et
c'est exactement le genre d'affirmation que le cahier des charges
interdit.

---

## 6. Comment savoir si TURN est réellement nécessaire chez vous

Avant d'engager la dépense, une mesure vaut mieux qu'une hypothèse.

**Test décisif**, depuis un réseau représentatif (Wi-Fi d'école,
partage de connexion mobile) :

1. rejoindre une salle FEBA depuis ce réseau ;
2. ouvrir `about:webrtc` (Firefox) ou `chrome://webrtc-internals` ;
3. examiner les **candidats ICE** retenus.

| Observation | Conclusion |
|---|---|
| paire `srflx`/`host` sélectionnée, média présent | UDP passe — TURN non requis sur ce réseau |
| aucune paire sélectionnée, ou média absent | **TURN requis** |

Répéter depuis trois ou quatre réseaux différents. Si un seul échoue,
la question est tranchée : les familles concernées n'auront pas d'autre
solution.

**Contrôle complémentaire, sans réunion** — bloquer l'UDP sortant
localement et retenter :

```bash
# macOS, temporaire
sudo pfctl -E
echo "block drop out proto udp to any port 10000" | sudo pfctl -f -
# … tester une réunion, puis :
sudo pfctl -d
```
