# FEBA — Limites connues

Ce qui n'a **pas** pu être vérifié dans cet environnement, et pourquoi.
Rien ici n'est présenté comme fonctionnel sans preuve.

---

## 1. Visioconférence — ce qui exige un environnement réel

### 1.1 Réunion à deux participants (§32)

**À TESTER EN ENVIRONNEMENT RÉEL.**

Deux navigateurs distants et un accès média réel sont nécessaires.

*Protocole.* Deux comptes de la même classe, deux machines sur des
réseaux différents, rejoindre la même salle. Vérifier : chacun voit et
entend l'autre ; la liste des participants en compte exactement deux ;
personne n'y apparaît en double.

### 1.2 Stabilité sur 30 minutes (§33)

**À TESTER EN ENVIRONNEMENT RÉEL.**

La cause des déconnexions périodiques est identifiée et corrigée — le
composant était détruit et recréé toutes les 30 secondes par le
`refetchInterval` du parent — et la conférence vit désormais dans un
onglet séparé, hors de portée de ce cycle. Une session longue reste à
observer.

*Protocole.* Réunion à deux, 30 minutes. Surveiller : reconnexions
spontanées, participants fantômes, `docker stats` sur `jvb` et `prosody`,
journaux Prosody.

### 1.3 Poignée de main WebSocket de bout en bout

**À TESTER EN ENVIRONNEMENT RÉEL.**

Le mandataire de cet environnement **ne relaie aucune mise à niveau
WebSocket** — vérifié : un service public de test échoue exactement de la
même façon. Le code obtenu sur `meet.globalfeba.com` n'est donc **ni** une
preuve de panne **ni** une preuve de bon fonctionnement.

Ce qui **est** vérifié : le chemin `/xmpp-websocket` existe et répond
(pas de 404), `config.js` pointe bien `wss://meet.globalfeba.com/xmpp-websocket`,
et le fichier nginx du dépôt traite `Upgrade` pour `/xmpp-websocket` et
`/colibri-ws/`.

*Protocole.* Depuis un poste ordinaire :
`wscat -c wss://meet.globalfeba.com/xmpp-websocket` doit répondre
`101 Switching Protocols`.

### 1.4 Refus d'adhésion anonyme sur l'instance en service

**À TESTER EN ENVIRONNEMENT RÉEL.**

Chromium n'a **aucun accès sortant** depuis cet environnement
(`example.com` échoue également). La configuration
`ENABLE_AUTH=1 / ENABLE_GUESTS=0 / AUTH_TYPE=jwt` est vérifiée dans les
fichiers Compose ; son application effective sur l'instance en service ne
l'est pas.

*Protocole.* Ouvrir `https://meet.globalfeba.com/salle-test-xyz` dans un
navigateur, **sans passer par FEBA**. L'accès doit être refusé. Si une
salle s'ouvre, n'importe qui sur Internet peut créer des salles sur votre
serveur.

### 1.5 ICE / JVB / UDP 10000 (§24)

**À TESTER EN ENVIRONNEMENT RÉEL.**

`JVB_ADVERTISE_IPS` et l'ouverture d'UDP 10000 ne se vérifient que depuis
un client externe. Sans ce port, les participants entrent dans la salle
et ne se voient pas — le symptôme est distinct d'une panne de
signalisation, et c'est ce qui rend le contrôle nécessaire.

*Protocole.* `nc -vzu 89.167.63.1 10000` depuis un réseau externe, puis
une réunion à deux pour confirmer le flux média.

### 1.6 TURN / Coturn (§25)

**À TESTER EN ENVIRONNEMENT RÉEL.**

Aucune infrastructure TURN n'est configurée à ce jour. Elle devient
nécessaire dès qu'un participant se trouve derrière un pare-feu qui
bloque UDP — Wi-Fi scolaire, réseau d'entreprise, NAT restrictif, certains
opérateurs mobiles. C'est une population réelle pour une école en ligne
destinée à la diaspora.

*Ce qui n'est pas fait.* Coturn n'est ni installé ni configuré. Le
déclarer « prêt » sur la foi d'un fichier de configuration serait
exactement le genre d'affirmation que §48 interdit.

*Protocole d'évaluation.* Tenter une réunion depuis un réseau bloquant
l'UDP sortant. Si la connexion échoue, TURN est requis.

---

## 2. Docker

**LIMITATION CONNUE.** Le démon Docker est indisponible dans cet
environnement. `docker compose config` est vérifiable — et a été exécuté,
5 assemblages valides — mais `docker compose up` ne l'est pas.

---

## 3. Écart entre le nginx du dépôt et l'instance en service

**EXTERNAL ACTION REQUIRED.**

Mesuré sur `meet.globalfeba.com` :

| En-tête | Instance en service | Fichier du dépôt |
|---|---|---|
| `Strict-Transport-Security` | `max-age=63072000` | `max-age=31536000; includeSubDomains` |
| `X-Content-Type-Options` | `nosniff` | `nosniff` |
| `Referrer-Policy` | **absent** | `strict-origin-when-cross-origin` |
| `Content-Security-Policy` | **absent** | `frame-ancestors 'self' https://globalfeba.com` |

L'instance en service ne sert donc **pas** la configuration du dépôt. Ce
n'est pas nécessairement un défaut — cette configuration n'a jamais été
déployée, conformément aux consignes — mais toute conclusion sur la
sécurité ou la stabilité doit en tenir compte.

L'absence de `frame-ancestors` est la plus notable : elle laisse
n'importe quel site intégrer la conférence dans une iframe.

---

## 4. Certificat TLS

**PASS VÉRIFIÉ, avec échéance.** Certificat valide pour
`meet.globalfeba.com`. Le renouvellement automatique n'a pas pu être
vérifié depuis cet environnement.

*À vérifier.* Que le renouvellement ACME est en place et que le
`location /.well-known/acme-challenge/` du proxy ne l'empêche pas.

---

## 5. Deux adresses IP distinctes

**Information d'audit.**

```
globalfeba.com       → 62.238.38.111
meet.globalfeba.com  → 89.167.63.1
```

Architecture parfaitement valable — Jitsi gagne à être isolé — mais qui
mérite d'être confirmée comme **voulue**.

---

## 6. Ce qui n'est PAS une limite

Pour éviter toute ambiguïté, ces points sont **vérifiés** :

- la contradiction de la capture est supprimée, à la source, dans les
  deux couches (11/11 en navigateur réel) ;
- le backend valide et refuse en 400 sur les **deux** chemins d'écriture ;
- les matières d'une autre académie sont refusées ;
- les trois bulletins sont conformes, PDF réels inspectés ;
- FEBA ne subit aucune régression, et la garantie est structurelle ;
- un élève d'une autre classe reçoit 403 **avec le motif** ;
- un élève ne peut pas obtenir la modération en la demandant ;
- `JITSI_APP_SECRET` est absent du bundle construit ;
- aucun repli `meet.jit.si` n'existe dans le code ;
- aucune fuite sur `/.env`, `/.git/config`, `/api/env`.

---

## 7. Identité institutionnelle de FEBA French Heritage Academy

Ces deux points ne sont pas des défauts logiciels et ne se corrigent pas
en écrivant du code. Ils étaient documentés dans les livraisons
précédentes et le restent : une limitation qu'on cesse d'écrire redevient
un oubli à la relecture suivante.

### 7.1 Cachet officiel

**Aucun cachet officiel FEBA FHA n'a été fourni ; aucun cachet d'une autre
académie n'est réutilisé.**

Les documents de l'académie en ligne — reçus, certificats, fiches —
sortent donc **sans cachet**. Ce n'est pas un oubli et ce n'est pas
réparable en écrivant du code : le visuel n'existe pas dans les éléments
transmis.

Apposer `cachet_feba.png` à la place serait pire que l'absence : cette
image porte en couronne « COMPLEXE SCOLAIRE FAITH & EXCELLENCE BILINGUAL
ACADEMY ». Sur un certificat de l'académie en ligne, elle y estampille le
nom d'une autre personne morale — sur la pièce qui fait foi. Un document
sans cachet se voit et se corrige ; un document au cachet d'un autre
établissement circule et fait autorité.

**Pour lever cette limitation :** déposer le cachet officiel FHA dans
`backend/feba_project/static_files/` et renseigner son nom dans
`ACADEMY_DEFAULTS["FEBA_FHA"]["stamp"]`
(`backend/apps/schools/branding.py`). Rien d'autre n'est à modifier.

### 7.2 Nom d'établissement sur deux lignes — limitation levée

Cette limitation figurait dans les livraisons précédentes. Elle **est
levée** : un nom d'établissement de **79 caractères est composé sur deux
lignes** sans chevauchement ni troncature, l'interligne étant calculé à
partir de la taille de police au lieu d'être laissé à sa valeur par défaut
(`backend/apps/payments/pdf_generator.py`).

Elle est maintenue dans ce document uniquement pour dire qu'elle n'a plus
lieu d'être : la laisser inscrite ferait renoncer quelqu'un à un service
qui fonctionne.
