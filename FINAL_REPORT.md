# FEBA — Rapport final V13

Version de référence consolidée. C'est celle à déployer.

---

## 1. Source de base

| | |
|---|---|
| Branche finale | `claude/feba-v13-production-final` |
| Base applicative | `claude/serene-ramanujan-wh16c4` (V12, `0123505`) |
| Fusionnée avec | `origin/main` (`ebe8d57`) — le HEAD **réellement en service** sur `/opt/feba/app` |
| Commits en avance sur la production | 16 |
| **Commits de production absents** | **0** |

La branche est un **sur-ensemble strict** de ce qui tourne aujourd'hui.
La déployer n'enlève rien.

---

## 2. Ce que la comparaison a révélé

V12 **n'était pas** un sur-ensemble de la production. Trois commits de
`main` lui manquaient, dont deux qui comptent :

| Apport de `main` | Conséquence si on avait déployé V12 tel quel |
|---|---|
| `ci.yml` — résolution des upstreams Docker | la validation `nginx -t` de la CI aurait été cassée |
| `package.json` — `xlsx` retirée | une dépendance inutilisée, régulièrement signalée par les audits, aurait été réintroduite |
| `package.json` — `react-router-dom` ^6.26.1 → ^6.30.6 | rétrogradation du routeur |

Résolution des huit conflits, un par un :

| Fichier | Retenu | Raison |
|---|---|---|
| `.github/workflows/ci.yml` | **main** | son correctif, absent de V12 |
| `Makefile` | V13 | cible `jitsi-network` conservée |
| `backend/apps/virtualclass/services.py` | V13 | main n'apportait rien |
| `docker-compose.jitsi.prod.yml` | V13 | montage nginx-custom, CSP |
| `scripts/make_final_delivery.sh` | V13 | manifeste étendu |
| `FINAL_REPORT`, `TEST_REPORT`, `KNOWN_LIMITATIONS` | V13 | versions les plus récentes |
| `frontend/package*.json` | **main** | `xlsx` retirée, routeur à jour |

---

## 3. Migrations apportées

| Migration | Effet | Réversible |
|---|---|---|
| `classes.0003_class_language_track` | ajoute `language_track`, défaut `BILINGUAL` | oui |
| `classes.0004_audit_language_tracks` | déduit le parcours des classes FHA de leurs matières réelles | oui |
| `schools.0016_activate_orphan_school_years` | active l'année la plus récente des académies sans année active | oui |
| `virtualclass.0003_virtualroom_target_roles` | ajoute `target_roles`, défaut `[]` | oui |

Aucune ne supprime ni ne réécrit de donnée. `classes.0004` **ne devine
pas** : une classe sans matière garde la valeur par défaut et figure dans
le rapport de migration.

---

## 4. Résultats des tests

| Suite | Résultat |
|---|---|
| Backend PostgreSQL | **1314 passés, 0 échec** |
| Backend SQLite | **1313 passés, 1 ignoré** (documenté) |
| Frontend | **246 passés, 25 fichiers** |
| ESLint | **0 erreur**, 81 avertissements (référence inchangée) |
| Build frontend | **OK** |
| Migrations | **aucun changement détecté** |
| Assemblages Compose | **5 valides** |
| Non-régression FEBA FHA ciblée | **96 tests** |

---

## 5. Infrastructure Jitsi — état réel

### Vérifié depuis l'extérieur

| Contrôle | Résultat | Statut |
|---|---|---|
| DNS `meet.globalfeba.com` | `89.167.63.1` | **PASS VÉRIFIÉ** |
| HTTPS | 200 | **PASS VÉRIFIÉ** |
| Certificat TLS | valide | **PASS VÉRIFIÉ** |
| `external_api.js` | 200, `application/javascript` | **PASS VÉRIFIÉ** |
| `/xmpp-websocket` existe | 200 (≠ 404) | **PASS VÉRIFIÉ** |
| HSTS, `X-Content-Type-Options` | servis | **PASS VÉRIFIÉ** |
| `Referrer-Policy` | **absent** | **EXTERNAL ACTION REQUIRED** |
| `frame-ancestors` | **absent** | **EXTERNAL ACTION REQUIRED** |
| `/.env`, `/.git/config`, `/api/env` | catch-all du SPA, aucune fuite | **PASS VÉRIFIÉ** |
| Aucun repli `meet.jit.si` | vérifié dans le code et le bundle | **PASS VÉRIFIÉ** |

`make production-health` rend aujourd'hui **DEGRADED**, en nommant
exactement les deux en-têtes manquants. C'est le comportement voulu : le
dépôt est correct, le serveur ne l'a pas encore.

### Nginx

La production est servie par le nginx **du conteneur** `jitsi/web` —
prouvé par la signature de ses en-têtes, et confirmé par votre inspection
SSH : `/run/web/config/nginx-custom` absent, `nginx -T` sans les en-têtes
V12. Le fichier `nginx/sites-available/meet.globalfeba.com.conf`
appartient à la topologie « derrière le proxy » et n'est **pas** lu ici.

La configuration V13 passe donc par le point d'extension de l'image, et
`scripts/deploy_production.sh` **vérifie** qu'il est honoré au lieu de le
supposer : l'image `:stable` déployée peut être plus ancienne que le
gabarit publié par Jitsi.

### JVB

`JVB_ADVERTISE_IPS=89.167.63.1`, `JVB_PORT=10000`, UDP publié en
`0.0.0.0:10000`. **Non modifié** — la valeur est correcte, et le script de
déploiement la vérifie plutôt que de la réécrire.

### Réseau partagé

`feba_jitsi_shared` existe et `app-jitsi-web-1` y est connecté. La cible
`jitsi-network`, dont `jitsi-prod-up` et `jitsi-proxy-up` dépendent
désormais, garantit sa présence de manière idempotente.

---

## 6. JWT et permissions

| Contrôle | Statut |
|---|---|
| Jeton lié à une salle (`room`) | **PASS VÉRIFIÉ** |
| Expiré, altéré, mauvais public, mauvais émetteur, non signé | refusés — **PASS VÉRIFIÉ** |
| Élève jamais modérateur | **PASS VÉRIFIÉ** (rôle par rôle) |
| Escalade `moderator: true` par le client | refusée — **PASS VÉRIFIÉ** |
| Élève d'une autre classe | 403 **avec motif** — **PASS VÉRIFIÉ** |
| Utilisateur d'une autre académie | 404, existence non révélée — **PASS VÉRIFIÉ** |
| Secret hors du bundle | 0 occurrence — **PASS VÉRIFIÉ** |

---

## 7. FEBA FHA et non-régression FEBA

| Règle | Statut |
|---|---|
| FRANCOPHONE : FR ≥ 1, EN = 0 autorisé | **PASS VÉRIFIÉ** |
| ANGLOPHONE : EN ≥ 1, FR = 0 autorisé | **PASS VÉRIFIÉ** |
| BILINGUE : FR ≥ 1 **et** EN ≥ 1 | **PASS VÉRIFIÉ** |
| FEBA : comportement historique inchangé | **PASS VÉRIFIÉ** |
| Bulletins adaptés aux trois parcours | **PASS VÉRIFIÉ** (PDF réels inspectés) |
| Enseignants, classes, salles virtuelles | **PASS VÉRIFIÉ** |

La non-régression de FEBA est **structurelle** : le drapeau
`monolingual_classes` est faux pour une académie de type `campus`, donc le
parcours effectif y vaut toujours `BILINGUAL`, quelle que soit la valeur
stockée.

---

## 8. Actions hors du dépôt

**EXTERNAL ACTION REQUIRED** — aucun accès SSH, Hetzner ni Hostinger
depuis cette session. Vérifié : pas de client `ssh`, port 22 injoignable,
aucun jeton dans l'environnement.

| Action | Où | Document |
|---|---|---|
| Poser `Referrer-Policy` et `frame-ancestors` | serveur Jitsi | `JITSI_PRODUCTION_ACTIONS.md` |
| Ouvrir UDP/10000, TCP/80, TCP/443 ; restreindre SSH | console Hetzner | `PRODUCTION_CHECKLIST.md` |
| Décider et déployer TURN | Hetzner + Hostinger | `TURN_DECISION.md`, `TURN_DEPLOYMENT_GUIDE.md` |

`ufw` est **inactive** sur le serveur : le pare-feu Hetzner est donc le
seul filtre, et sa configuration ne m'est pas accessible.

---

## 9. Limitations

| Point | Statut |
|---|---|
| Réunion à deux participants | **À TESTER EN ENVIRONNEMENT RÉEL** |
| Stabilité 30 minutes | **À TESTER EN ENVIRONNEMENT RÉEL** |
| Poignée de main WebSocket `101` | **À TESTER EN ENVIRONNEMENT RÉEL** |
| Refus d'adhésion anonyme sur l'instance en service | **À TESTER EN ENVIRONNEMENT RÉEL** |
| UDP 10000 depuis Internet | **À TESTER EN ENVIRONNEMENT RÉEL** |
| Pare-feu Hetzner | **EXTERNAL ACTION REQUIRED** |
| TURN | **non déployé**, décision argumentée fournie |
| `docker compose up` complet | **LIMITATION CONNUE** — démon indisponible ici |

**Cette version n'est pas déclarée « production-ready ».** Elle est
déployable et vérifiable ; la validation réelle dépend des tests
ci-dessus.

---

## 10. Déploiement et retour arrière

```
make deploy-check       # ne modifie rien
make deploy-production  # sauvegarde, déploie, VÉRIFIE
make production-health  # READY / DEGRADED / UNAVAILABLE
```

Retour arrière : `bash scripts/deploy_production.sh --rollback`, ou
`ROLLBACK_GUIDE.md` pour les cas particuliers.

Le script s'interrompt **avant** toute modification si un prérequis
manque, sauvegarde `.env*` et le commit courant avant d'agir, et ne lit
jamais la valeur d'un secret.
