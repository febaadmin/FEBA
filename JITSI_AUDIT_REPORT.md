# FEBA — Audit de la visioconférence (V10)

Instance auto-hébergée `meet.globalfeba.com`. **Aucun repli vers
`meet.jit.si` n'existe dans le code** — vérifié dans les sources, dans le
bundle construit et dans le navigateur.

---

## 1. Le défaut principal : déconnexions et identités multiples

Un participant était renvoyé à l'écran « Rejoindre la réunion » toutes les
30 secondes environ, en laissant derrière lui une identité Jitsi de plus à
chaque passage.

Ce n'était ni le réseau, ni le JWT, ni Jitsi. C'était une ligne :

```js
}, [roomName, domain, displayName, subject, jwt, onClose]);
//                                             ^^^^^^^
```

`onClose` était passé en fonction fléchée par le parent : **une nouvelle
identité à chaque rendu**. Et le parent se rendait tout seul toutes les
30 secondes, à cause du `refetchInterval` de la liste des salles. Donc
toutes les 30 secondes : effet nettoyé → `dispose()` → nouvelle
`JitsiMeetExternalAPI`. La conférence était détruite et recréée **pendant
qu'on parlait dedans**, et chaque recréation ouvrait une participation de
plus.

**Statut : CORRIGÉ ET VÉRIFIÉ.** Les rappels vivent dans des refs ;
l'effet ne dépend que de ce qui définit la conférence
(`[roomName, domain, jwt]`). 12 tests dans
`frontend/src/components/JitsiMeeting.test.jsx` ; en remettant les
dépendances d'origine, 5 échouent.

---

## 2. Suppression de l'architecture modale (§11)

Corriger le composant ne suffisait pas. Tant que la conférence vit dans
l'arbre React du tableau de bord, elle reste à la merci de tout ce qui s'y
passe : un poll, une invalidation de cache, une navigation.

La conférence occupe désormais **un onglet entier**, sur une route montée
à la racine du routeur : `/virtual-room/:id/join`.

| Vérification | Statut | Preuve |
|---|---|---|
| Le clic ouvre un NOUVEL onglet | **PASS VÉRIFIÉ** | parcours F |
| L'onglet pointe la route plein écran | **PASS VÉRIFIÉ** | parcours F2 |
| Aucune barre latérale / en-tête / tableau de bord | **PASS VÉRIFIÉ** | parcours F4 : `{nav:0, aside:0, header:0}` |
| Plus aucune conférence montée dans la liste des salles | **PASS VÉRIFIÉ** | `VirtualRooms.test.jsx` |

### Bloqueur de fenêtres surgissantes (§13)

`window.open` est appelé **synchronement** dans le gestionnaire de clic,
avant tout appel réseau : c'est la seule façon qu'un navigateur considère
l'ouverture comme voulue par l'utilisateur. Ouvrir après un `await` fait
bloquer l'onglet, silencieusement.

Quand l'ouverture est tout de même bloquée, le message dit **la cause et
le remède** — pas seulement que cela a échoué. **PASS VÉRIFIÉ** (test
dédié, avec `window.open` renvoyant `null`).

---

## 3. Sécurité du jeton (§12)

| Exigence | Statut | Preuve |
|---|---|---|
| `JITSI_APP_SECRET` reste exclusivement backend | **PASS VÉRIFIÉ** | 0 occurrence dans `src/`, 0 dans `dist/` après build |
| Aucune variable Vite liée au secret | **PASS VÉRIFIÉ** | aucune référence `import.meta.env` + Jitsi |
| Le JWT ne transite pas par l'URL | **PASS VÉRIFIÉ** | parcours F3 ; l'URL ne porte que l'identifiant de salle |
| Le JWT n'est pas stocké dans `localStorage` | **PASS VÉRIFIÉ** | gardé en mémoire du composant |
| Le JWT est demandé par l'onglet lui-même | **PASS VÉRIFIÉ** | `virtualAPI.join()` en session same-origin |

### Forme du jeton émis (mesurée)

```
entête  : {"alg": "HS256", "typ": "JWT"}
iss     : feba                      (JITSI_APP_ID)
aud     : jitsi
sub     : meet.globalfeba.com
room    : feba-fha-cours-en-direct-french-ambassa-2e175dbc8b
exp     : présent
context : moderator = true (administrateur)
```

Le jeton est **lié à une salle précise** par la revendication `room` : il
ne peut pas être rejoué sur une autre salle.

### Refus plutôt que dégradation

Sans `JITSI_APP_ID` / `JITSI_APP_SECRET`, le backend répond **503** :

> « JITSI_APP_ID / JITSI_APP_SECRET manquants : aucun jeton ne peut être
> signé, donc aucune salle ne peut être protégée. »

Il ne sert pas une salle non protégée, et ne bascule vers aucun service
public. **PASS VÉRIFIÉ.**

---

## 4. Contrôle d'accès côté backend (§18)

Vérifié dans `apps/virtualclass/services.py` (`assert_can_join`) et couvert
par `IdorParLApiTests` :

| Règle | Statut |
|---|---|
| Une salle d'une autre académie → 403 | **PASS VÉRIFIÉ** |
| Une académie sans visio activée → 403 | **PASS VÉRIFIÉ** |
| Ciblage par profil (`target_roles`) → 403 hors cible | **PASS VÉRIFIÉ** |
| Élève hors du groupe de la salle → 403 | **PASS VÉRIFIÉ** |
| Parent sans enfant dans le groupe → 403 | **PASS VÉRIFIÉ** |
| **Enseignant non affecté à la classe → 403** | **PASS VÉRIFIÉ** |

Le dernier point était une faille réelle : le contrôle ne portait que sur
les élèves et les parents, donc **tout enseignant de l'académie pouvait
entrer dans le cours d'une classe qui ne lui est pas confiée**. Le
créateur de la salle y garde accès — il l'a ouverte pour une classe qu'il
encadre ponctuellement.

Le ciblage est **appliqué par le backend**, pas seulement masqué dans
l'interface : un identifiant posté directement est refusé.

---

## 5. Idempotence adhésion / départ (§14)

| Vérification | Statut |
|---|---|
| Une seule adhésion, même sous StrictMode | **PASS VÉRIFIÉ** |
| Un seul départ quand Jitsi émet `videoConferenceLeft` puis `readyToClose` | **PASS VÉRIFIÉ** |
| Un seul départ si on raccroche puis ferme l'onglet | **PASS VÉRIFIÉ** |
| Départ signalé à la fermeture de l'onglet (`pagehide`) | **PASS VÉRIFIÉ** |
| Un départ refusé par le backend ne casse pas l'écran | **PASS VÉRIFIÉ** |

Sans ces gardes, le backend enregistrait deux participations pour une
seule personne — le « participant en double » observé en réunion — et les
participations restaient « en cours » indéfiniment, faussant les durées.

---

## 6. Jamais d'écran noir muet

Trois chemins d'échec, trois messages :

| Situation | Ce que voit l'utilisateur | Statut |
|---|---|---|
| Backend indisponible (503) | « La visioconférence est momentanément indisponible : l'instance FEBA n'est pas joignable. » | **PASS VÉRIFIÉ** (navigateur) |
| `external_api.js` injoignable | « Visioconférence indisponible — Impossible de charger l'interface Jitsi depuis meet.globalfeba.com. » | **PASS VÉRIFIÉ** (navigateur) |
| Accès refusé (403) | le motif exact du backend, ex. « Cette classe ne vous est pas affectée. » | **PASS VÉRIFIÉ** |

Sur le dernier point : `extractApiError` répond « Vous n'avez pas la
permission d'effectuer cette action » à tout 403 — utile là où
l'utilisateur peut revenir en arrière. L'onglet de conférence est un
cul-de-sac : un enseignant y apprend désormais **pourquoi**. Le
contournement est local à cette page ; le comportement global est
inchangé.

Lors de l'échec du chargement de Jitsi, `leave` est appelé
automatiquement : la participation est close, pas laissée ouverte.
**Observé en navigateur.**

---

## 7. Audit réseau et TLS (§19–§27)

Mesuré depuis l'environnement d'audit, le 2026-09-04 :

| Vérification | Résultat | Statut |
|---|---|---|
| DNS `meet.globalfeba.com` | `89.167.63.1` | **PASS VÉRIFIÉ** |
| HTTPS | `200` | **PASS VÉRIFIÉ** |
| Certificat | `CN=meet.globalfeba.com`, ZeroSSL ECC DV, valide du 2026-09-03 au **2026-12-02** | **PASS VÉRIFIÉ** |
| Chaîne de confiance | ZeroSSL → Sectigo Public Server Authentication Root E46 | **PASS VÉRIFIÉ** |
| HSTS | `max-age=63072000` | **PASS VÉRIFIÉ** |
| `external_api.js` | `200`, 97 310 octets, `application/javascript` | **PASS VÉRIFIÉ** |
| L'instance est bien Jitsi Meet | titre et ressources Jitsi Meet | **PASS VÉRIFIÉ** |
| `config.js` → WebSocket | `wss://meet.globalfeba.com/xmpp-websocket` | **PASS VÉRIFIÉ** |
| `config.js` → BOSH (repli) | `https://meet.globalfeba.com/http-bind` | **PASS VÉRIFIÉ** |

### Ce qui n'a PAS pu être vérifié ici

| Point | Statut | Pourquoi |
|---|---|---|
| Poignée de main WebSocket de bout en bout | **À TESTER EN ENVIRONNEMENT RÉEL** | Le mandataire du bac à sable ne relaie aucune mise à niveau WebSocket — vérifié : `ws.postman-echo.com` échoue de la même façon. Le `501` obtenu sur `meet.globalfeba.com` n'est donc **pas** imputable au serveur. |
| Adhésion anonyme réellement refusée | **À TESTER EN ENVIRONNEMENT RÉEL** | Chromium n'a aucun accès sortant depuis cet environnement (`example.com` échoue aussi). La configuration `ENABLE_AUTH=1 / ENABLE_GUESTS=0 / AUTH_TYPE=jwt` est vérifiée dans les fichiers Compose ; son application sur l'instance en service ne l'est pas. |
| Réunion à 2 participants (§31) | **À TESTER EN ENVIRONNEMENT RÉEL** | Deux navigateurs distants requis. |
| Stabilité sur 30 minutes (§32) | **À TESTER EN ENVIRONNEMENT RÉEL** | Même raison. |

**Ces points ne sont pas déclarés PASS.** Ils sont nommés, avec la raison
exacte pour laquelle l'environnement d'audit ne peut pas trancher.

### Configuration Compose (fichiers du dépôt)

```
ENABLE_AUTH=1
ENABLE_GUESTS=0
AUTH_TYPE=jwt
JWT_APP_ID=${JITSI_APP_ID:?JITSI_APP_ID est requis}
JWT_APP_SECRET=${JITSI_APP_SECRET:?JITSI_APP_SECRET est requis}
JWT_ACCEPTED_ISSUERS=${JITSI_APP_ID}
JWT_ACCEPTED_AUDIENCES=jitsi
```

La syntaxe `:?` fait **échouer le démarrage** si le secret manque, plutôt
que de lancer une instance ouverte. **PASS VÉRIFIÉ.**

### Nginx du dépôt

`nginx/sites-available/meet.globalfeba.com.conf` traite les trois
emplacements qui distinguent un proxy Jitsi qui marche d'un proxy où
« tout le monde entre et personne ne se voit » :

- `= /xmpp-websocket` — `Upgrade` + `Connection "upgrade"`, `proxy_http_version 1.1`, délais 900 s
- `~ ^/colibri-ws/` — idem, pour le pont vidéo
- `= /http-bind` — BOSH, repli quand un pare-feu bloque le WebSocket

Chacun transmet `X-Real-IP`, `X-Forwarded-For` et `X-Forwarded-Proto`.
**PASS VÉRIFIÉ** (lecture du fichier ; validé par `nginx -t` en V9).

> **EXTERNAL ACTION REQUIRED.** Les en-têtes renvoyés par l'instance en
> service (`X-Request-Id`, `Access-Control-*`) ne correspondent pas à
> cette configuration : `meet.globalfeba.com` ne sert donc
> vraisemblablement **pas** le fichier du dépôt. Vérifier quel proxy est
> réellement en place avant de conclure sur la stabilité des réunions.
