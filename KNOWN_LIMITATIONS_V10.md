# FEBA — Limites connues V10

Ce qui n'a **pas** pu être vérifié dans l'environnement de développement,
et pourquoi. Rien ici n'est présenté comme fonctionnel sans preuve.

---

## 1. Visioconférence — ce qui exige un environnement réel

### 1.1 Réunion à deux participants (§31)

**Statut : À TESTER EN ENVIRONNEMENT RÉEL.**

Deux navigateurs distants et un accès média réel sont nécessaires. Les
mécanismes qui échouaient sont couverts par des tests
(identité stable des rappels, adhésion unique, départ unique), mais la
qualité audio/vidéo d'une réunion à deux ne se déduit pas d'un test
unitaire.

**À vérifier sur place :** les deux participants se voient et
s'entendent ; aucun ne réapparaît en double dans la liste.

### 1.2 Stabilité sur 30 minutes (§32)

**Statut : À TESTER EN ENVIRONNEMENT RÉEL.**

La cause des déconnexions périodiques est identifiée et corrigée : le
composant était détruit et recréé toutes les 30 secondes par le
`refetchInterval` du parent. La conférence vit désormais dans un onglet
séparé, hors de portée de ce cycle. Une session longue reste à observer.

**À vérifier sur place :** aucune reconnexion spontanée, aucune identité
supplémentaire après 30 minutes.

### 1.3 Poignée de main WebSocket

**Statut : À TESTER EN ENVIRONNEMENT RÉEL.**

Le mandataire de l'environnement d'audit **ne relaie aucune mise à niveau
WebSocket** — vérifié : un service public de test échoue exactement de la
même façon. Le `501` obtenu sur `meet.globalfeba.com` n'est donc **pas**
imputable au serveur, et n'est pas non plus une preuve que tout va bien.

Ce qui **est** vérifié : `config.js` de l'instance pointe bien
`wss://meet.globalfeba.com/xmpp-websocket`, et le fichier nginx du dépôt
traite correctement `Upgrade` pour `/xmpp-websocket` et `/colibri-ws/`.

**À vérifier sur place :** `wss://meet.globalfeba.com/xmpp-websocket`
répond `101 Switching Protocols`.

### 1.4 Refus d'adhésion anonyme sur l'instance en service

**Statut : À TESTER EN ENVIRONNEMENT RÉEL.**

Chromium n'a **aucun accès sortant** depuis cet environnement
(`example.com` échoue également). La configuration
`ENABLE_AUTH=1 / ENABLE_GUESTS=0 / AUTH_TYPE=jwt` est vérifiée dans les
fichiers Compose du dépôt ; son application effective sur l'instance en
service ne l'est pas.

**À vérifier sur place :** ouvrir `https://meet.globalfeba.com/salle-test`
dans un navigateur sans passer par FEBA. L'accès doit être **refusé**.

---

## 2. Docker

**Statut : LIMITATION CONNUE.**

Le démon Docker est indisponible dans cet environnement. `docker compose
config` reste vérifiable (validation de syntaxe et de résolution des
variables) et a été exécuté ; `docker compose up` ne l'est pas.

---

## 3. Écart entre le nginx du dépôt et l'instance en service

**Statut : EXTERNAL ACTION REQUIRED.**

Les en-têtes renvoyés par `meet.globalfeba.com` (`X-Request-Id`,
`Access-Control-*`) ne correspondent pas à
`nginx/sites-available/meet.globalfeba.com.conf`. L'instance en service
ne sert donc vraisemblablement **pas** la configuration du dépôt.

Ce n'est pas nécessairement un défaut — la configuration du dépôt n'a
jamais été déployée, conformément aux consignes. Mais toute conclusion
sur la stabilité des réunions doit tenir compte de cet écart.

**À faire :** identifier quel proxy sert réellement
`meet.globalfeba.com`, et décider s'il doit être aligné sur le fichier du
dépôt.

---

## 4. Certificat TLS

**Statut : PASS VÉRIFIÉ, avec échéance.**

Le certificat de `meet.globalfeba.com` (ZeroSSL ECC DV) est valide
**jusqu'au 2026-12-02**. Le renouvellement automatique n'a pas pu être
vérifié depuis cet environnement.

**À vérifier sur place :** que le renouvellement ACME est en place, et
qu'il n'est pas empêché par le `location /.well-known/acme-challenge/` du
proxy.

---

## 5. Deux adresses IP distinctes

**Statut : information d'audit.**

```
globalfeba.com       → 62.238.38.111
meet.globalfeba.com  → 89.167.63.1
```

Deux hôtes différents. C'est une architecture parfaitement valable
(Jitsi est gourmand et gagne à être isolé), mais elle mérite d'être
confirmée comme **voulue** plutôt que subie.

---

## 6. Ce qui n'est PAS une limite

Pour éviter toute ambiguïté, ces points sont **vérifiés**, pas reportés :

- les quatre bugs signalés sont corrigés et prouvés par des tests **et**
  par des parcours navigateur réels ;
- `JITSI_APP_SECRET` est absent du bundle construit (0 occurrence) ;
- le JWT ne transite pas par l'URL ;
- aucun repli vers `meet.jit.si` n'existe dans le code ;
- FEBA ne subit aucune régression ;
- l'application se comporte correctement quand la visioconférence est
  indisponible : elle le dit, avec le motif.
