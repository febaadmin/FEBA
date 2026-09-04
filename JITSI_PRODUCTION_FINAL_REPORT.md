# FEBA — Rapport final Jitsi production

Mission de clôture. Statuts §17 uniquement.

**Cette instance n'est PAS déclarée « production-ready ».** Les tests
réels obligatoires — deux participants, stabilité 30 minutes, WebSocket,
refus d'adhésion anonyme — n'ont pas pu être exécutés depuis cet
environnement. Ce qui reste à faire est écrit comme tel.

---

## 1. Tableau des contrôles

| Contrôle | Résultat | Preuve | Statut |
|---|---|---|---|
| **Configuration servie ≠ configuration du dépôt** | cause identifiée | en-têtes `max-age=63072000`, `x-xss-protection`, `interest-cohort=()` = signature du gabarit `jitsi/web` | **CORRIGÉ ET VÉRIFIÉ** |
| DNS `meet.globalfeba.com` | `89.167.63.1` | `make jitsi-health` | **PASS VÉRIFIÉ** |
| HTTPS | 200 | `curl -I` | **PASS VÉRIFIÉ** |
| Certificat TLS | valide, CN correct | `jitsi_health`, contrôle `tls` | **PASS VÉRIFIÉ** |
| `external_api.js` | 200, `application/javascript` | contrôle `external_api` | **PASS VÉRIFIÉ** |
| Chemin `/xmpp-websocket` existe | 200 (≠ 404) | contrôle `signalisation` | **PASS VÉRIFIÉ** |
| **Poignée de main WebSocket 101** | non mesurable ici | le mandataire ne relaie aucun `Upgrade` ; un service public de test échoue identiquement | **À TESTER EN ENVIRONNEMENT RÉEL** |
| HSTS servi | `max-age=63072000` | `curl -I` | **PASS VÉRIFIÉ** |
| `X-Content-Type-Options` servi | `nosniff` | `curl -I` | **PASS VÉRIFIÉ** |
| **`Referrer-Policy` servi** | **absent** | contrôle `entetes_securite` | **EXTERNAL ACTION REQUIRED** |
| **`frame-ancestors` servi** | **absent** | contrôle `entetes_securite` | **EXTERNAL ACTION REQUIRED** |
| Configuration des en-têtes côté dépôt | écrite et validée | `jitsi/nginx-custom/`, `CSP_HEADER`, 13 tests | **CORRIGÉ ET VÉRIFIÉ** |
| `/.env`, `/.git/config`, `/api/env` | catch-all du SPA, aucune fuite | contenu identique octet pour octet à l'accueil | **PASS VÉRIFIÉ** |
| Listage de répertoire | aucun | sondes `/images/`, `/css/`, `/libs/`, `/static/` | **PASS VÉRIFIÉ** |
| Authentification JWT déclarée | `ENABLE_AUTH=1`, `ENABLE_GUESTS=0`, `JWT_ALLOW_EMPTY=0` | fichiers Compose | **PASS VÉRIFIÉ** |
| **Adhésion anonyme réellement refusée** | non mesurable ici | Chromium n'a aucun accès sortant | **À TESTER EN ENVIRONNEMENT RÉEL** |
| Jeton lié à une salle | revendication `room` | `JetonJitsiTests` | **PASS VÉRIFIÉ** |
| Jeton expiré / altéré / mauvais public / mauvais émetteur | refusés | `VerificationDuJetonTests` | **PASS VÉRIFIÉ** |
| Élève jamais modérateur | rôle par rôle + API | `ModerateursParRoleTests` | **PASS VÉRIFIÉ** |
| Escalade `moderator: true` par le client | refusée | `LeClientNeChoisitPasSonRoleTests` | **PASS VÉRIFIÉ** |
| Élève d'une autre classe | 403 **avec motif** | parcours navigateur 17/17 | **PASS VÉRIFIÉ** |
| Utilisateur d'une autre académie | 404, existence non révélée | `RefusExpliqueDansLAcademieTests` | **PASS VÉRIFIÉ** |
| Cycle de vie React, `dispose()` compté | 1 API, 0 dispose sur 10 rerenders | `JitsiMeeting.test.jsx` §12 | **PASS VÉRIFIÉ** |
| Nouvel onglet, plein écran, aucun layout FEBA | vérifié en navigateur | parcours F1–F5 | **PASS VÉRIFIÉ** |
| Secret hors du bundle | 0 occurrence | `grep` sur `dist/` après build | **PASS VÉRIFIÉ** |
| **Réseau `feba_jitsi_shared` au démarrage production** | les cibles prod ne le créaient pas | `make -n jitsi-prod-up` | **CORRIGÉ ET VÉRIFIÉ** |
| `jitsi_health` ne lève jamais | rattrapage complet | `test_v11_jitsi_health_checks.py` | **CORRIGÉ ET VÉRIFIÉ** |
| **JVB / UDP 10000 depuis l'extérieur** | non mesurable ici | pas d'accès réseau sortant UDP | **À TESTER EN ENVIRONNEMENT RÉEL** |
| **Pare-feu Hetzner** | pas d'accès console | — | **EXTERNAL ACTION REQUIRED** |
| **TURN / Coturn** | nécessaire, non déployé | `TURN_DECISION.md` | **EXTERNAL ACTION REQUIRED** |
| **Deux participants** | non exécutable ici | un seul environnement, pas d'accès média | **À TESTER EN ENVIRONNEMENT RÉEL** |
| **Stabilité 30 minutes** | non exécutable ici | idem | **À TESTER EN ENVIRONNEMENT RÉEL** |
| Non-régression FEBA FHA (§16) | 96 tests ciblés | suites relancées | **PASS VÉRIFIÉ** |

---

## 2. La question centrale : dépôt ou production ?

`meet.globalfeba.com` renvoie exactement :

```
strict-transport-security: max-age=63072000
x-content-type-options: nosniff
x-xss-protection: 1; mode=block
permissions-policy: interest-cohort=()
```

C'est la signature du gabarit `web/rootfs/defaults/meet.conf` de l'image
`jitsi/web`. **Conclusion : le nginx du conteneur répond directement.**

Le dépôt porte deux topologies :

| Fichier | Ports | nginx qui répond |
|---|---|---|
| `docker-compose.jitsi.prod.yml` | `80:80`, `443:443` | **celui du conteneur** |
| `docker-compose.jitsi.behind-proxy.yml` | `127.0.0.1:8443` | un nginx **hôte**, avec `nginx/sites-available/` |

La production tourne sur la **première**. Le fichier
`nginx/sites-available/meet.globalfeba.com.conf` — correct, validé par
`nginx -t` en V9 — appartient à la **seconde** et n'y est jamais lu.

Ce n'était donc pas une configuration oubliée, mais une configuration
écrite pour une topologie qui n'est pas celle en service. Le rapport V11
signalait l'écart sans en identifier la cause ; c'est fait.

---

## 3. Ce que j'ai corrigé dans le dépôt

| Élément | Effet |
|---|---|
| `jitsi/nginx-custom/feba-security-headers.conf` | `Referrer-Policy`, `Permissions-Policy` adaptée, `always` sur les en-têtes, blocage de `/.env*` et `/.git*` |
| `docker-compose.jitsi.prod.yml` | monte ce fichier sur le point d'extension de l'image ; pose `CSP_HEADER` |
| `.env.jitsi.example` | `JITSI_CSP_HEADER` documenté, avec la raison de chaque terme |
| `Makefile` | cible `jitsi-network`, dont dépendent `jitsi-prod-up` et `jitsi-proxy-up` |
| `apps/virtualclass/services.py` | contrôle `entetes_securite` : mesure ce que l'instance sert VRAIMENT |

### Pourquoi la CSP se limite à `frame-ancestors`

Jitsi Meet a besoin de `eval`, de scripts en ligne, de blobs et de
workers. Une CSP « propre » rend l'instance **noire et muette**. Seule
`frame-ancestors` répond à la question posée — qui a le droit d'embarquer
la conférence — sans toucher à l'exécution du code.

`'self'` y est **obligatoire** : l'External API crée une iframe sur le
domaine de Jitsi lui-même. Le retirer casserait l'ouverture de la
conférence, y compris depuis FEBA. Un test le vérifie.

Même raisonnement pour `Permissions-Policy` : `camera=()` couperait la
caméra de la conférence. Désactiver la fonctionnalité n'est pas la
sécuriser.

---

## 4. Le défaut de démarrage trouvé en chemin

`scripts/jitsi_up.sh` créait `feba_jitsi_shared` — mais seulement pour le
démarrage de **développement**. `make jitsi-prod-up` et
`make jitsi-proxy-up` ne passent pas par ce script : sur un serveur où la
pile FEBA n'a jamais tourné, ou après un `docker network prune`, ils
échouaient sur :

```
network feba_jitsi_shared declared as external, but could not be found
```

C'est-à-dire exactement l'erreur que §14 interdit de laisser subsister —
et au pire endroit, la production. Corrigé par une cible `jitsi-network`
idempotente, dont les deux démarrages dépendent. En retirant la
dépendance, le test tombe.

---

## 5. Ce qui vous revient

Dans l'ordre d'importance.

1. **Vérifier que l'adhésion anonyme est refusée.** Si une salle s'ouvre
   sans passer par FEBA, n'importe qui sur Internet peut créer des salles
   sur votre serveur. → `JITSI_REAL_WORLD_TEST_PLAN.md`, test 5.
2. **Poser les deux en-têtes manquants.** →
   `JITSI_PRODUCTION_ACTIONS.md`, §4 à §8. Commandes copier-collables,
   avec vérification et retour arrière.
3. **UDP 10000 depuis l'extérieur**, sinon les participants entrent et ne
   se voient pas. → §10 du même document.
4. **Décider pour TURN.** → `TURN_DECISION.md`, avec un test décisif qui
   dit si la dépense est justifiée chez vous.
5. **Réunion à deux et session de 30 minutes.** → plan de test,
   fiche de relevé à renvoyer.

---

## 6. Ce que je n'affirme pas

Une suite verte ne prouve ni la stabilité du JVB, ni le WebSocket, ni
l'UDP, ni TURN, ni une réunion de 30 minutes, ni ce que le serveur sert
réellement. C'est pourquoi le contrôle `entetes_securite` interroge
l'instance plutôt que le dépôt — et c'est pourquoi il est **en échec**
aujourd'hui, alors que la configuration du dépôt est correcte.

Les deux affirmations ne se confondent pas, et ce rapport ne les confond
pas.
