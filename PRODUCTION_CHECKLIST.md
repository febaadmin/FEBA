# FEBA — Liste de contrôle de mise en production

Version de référence : **V13**, branche `claude/feba-v13-production-final`.

Cette branche est un **sur-ensemble strict** de `main` : 0 commit de
production n'y manque. La déployer n'enlève rien.

---

## Avant de commencer

| Point | Commande | Attendu |
|---|---|---|
| État actuel du serveur | `make production-health` | noter le bilan de départ |
| Dépôt propre | `git status` | rien en attente |
| Espace disque | `df -h /var/lib/docker` | > 10 Go libres |
| Le déploiement est-il possible ? | `make deploy-check` | aucun échec |

`make deploy-check` **ne modifie rien**. S'il échoue, corrigez avant
d'aller plus loin.

---

## Déploiement

```bash
ssh root@89.167.63.1
cd /opt/feba/app
git fetch origin
git checkout claude/feba-v13-production-final
git pull --ff-only
make deploy-check      # ne modifie rien
make deploy-production # sauvegarde, déploie, VÉRIFIE
```

`deploy-production` s'interrompt **avant** toute modification si un
prérequis manque, et sauvegarde `.env*` + le commit courant avant d'agir.

- [ ] Sauvegarde créée dans `/root/feba-sauvegardes/`
- [ ] Réseau `feba_jitsi_shared` présent
- [ ] Assemblage Compose valide
- [ ] `nginx -t` réussit **dans le conteneur**
- [ ] `nginx -T` montre `Referrer-Policy` dans la configuration **chargée**

> Si la dernière case échoue, l'image `jitsi/web` déployée ne connaît pas
> le point d'extension `nginx-custom`. Le script le dit explicitement.
> Voir `JITSI_PRODUCTION_ACTIONS.md` §5 bis.

---

## Migrations backend

```bash
docker compose -f docker-compose.prod.yml exec backend-prod \
  python manage.py migrate
```

| Migration | Effet | Réversible |
|---|---|---|
| `classes.0003` | ajoute `language_track`, défaut `BILINGUAL` | oui |
| `classes.0004` | déduit le parcours des classes FHA depuis leurs matières | oui |
| `schools.0016` | active l'année la plus récente des académies sans année active | oui |
| `virtualclass.0003` | ajoute `target_roles`, défaut `[]` | oui |

- [ ] Lire la sortie de `classes.0004` : elle imprime les parcours déduits
      **et** les classes laissées à valider
- [ ] Aucune classe FEBA n'apparaît dans cette sortie

---

## Contrôles après déploiement

```bash
make production-health
make jitsi-health JITSI_TARGET=meet.globalfeba.com
```

- [ ] `production-health` : **READY**
- [ ] `jitsi-health` : tous les contrôles OK, y compris `entetes_securite`

```bash
curl -sSI https://meet.globalfeba.com/ | grep -iE 'referrer-policy|content-security-policy'
```

- [ ] `Referrer-Policy` présent
- [ ] `Content-Security-Policy: frame-ancestors …` présent

---

## Vérification fonctionnelle — FEBA FHA

- [ ] Classe **francophone** → Matières → 4 FR, 0 EN → **s'enregistre**
- [ ] Aucun message réclamant une matière anglaise
- [ ] Colonne anglaise grisée et non cochable
- [ ] Rechargement : les matières sont toujours là
- [ ] Classe **anglophone** → symétrique
- [ ] Classe **bilingue** → exige les deux langues
- [ ] Bulletin francophone : **aucune** partie anglaise
- [ ] Bulletin anglophone : **aucune** partie française
- [ ] « Rejoindre » ouvre un **nouvel onglet**, plein écran, sans layout FEBA
- [ ] Un élève d'une autre classe reçoit un refus **expliqué**

## Vérification fonctionnelle — FEBA, non-régression

- [ ] Connexion administrateur
- [ ] Classes, notes, bulletins **inchangés**
- [ ] Une classe FEBA exige toujours français **et** anglais
- [ ] Aucune classe FEBA n'a changé de parcours

---

## Tests réels — obligatoires avant de déclarer la production validée

Aucun ne peut être exécuté depuis le dépôt. Protocole complet dans
`JITSI_REAL_WORLD_TEST_PLAN.md`.

- [ ] **Accès anonyme refusé** — le plus important : si une salle s'ouvre
      sans passer par FEBA, n'importe qui peut créer des salles sur votre
      serveur
- [ ] Réunion à deux participants
- [ ] Stabilité 30 minutes
- [ ] Rafraîchissement du tableau de bord pendant une conférence
- [ ] Redémarrage `docker compose restart`
- [ ] WebSocket : `101 Switching Protocols`
- [ ] UDP 10000 joignable depuis l'extérieur

Tant que ces cases ne sont pas cochées, la mention correcte est
**À TESTER EN ENVIRONNEMENT RÉEL**, pas « production-ready ».

---

## Actions hors du dépôt

**EXTERNAL ACTION REQUIRED** — je n'ai accès ni à Hetzner ni à Hostinger.

### Pare-feu Hetzner Cloud

Console → *Firewalls* → règles **entrantes** :

| Protocole | Port | Source | Raison |
|---|---|---|---|
| TCP | 80 | `0.0.0.0/0`, `::/0` | validation HTTP-01 de Let's Encrypt |
| TCP | 443 | `0.0.0.0/0`, `::/0` | Jitsi Meet |
| **UDP** | **10000** | `0.0.0.0/0`, `::/0` | **flux média — sans lui, on entre et on ne se voit pas** |
| TCP | 22 | vos IP d'administration | à ne PAS laisser ouvert au monde |

- [ ] Les quatre règles sont en place
- [ ] SSH est restreint

> `ufw` est **inactive** sur le serveur : le pare-feu Hetzner est donc le
> seul filtre. Sa configuration ne m'est pas accessible et ne peut pas
> être déduite.

### DNS Hostinger

- [ ] `meet.globalfeba.com` → `89.167.63.1` (déjà en place, vérifié)
- [ ] `turn.globalfeba.com` — **seulement si** TURN est décidé, voir
      `TURN_DEPLOYMENT_GUIDE.md`

---

## Si quelque chose casse

`ROLLBACK_GUIDE.md`, ou directement :

```bash
bash scripts/deploy_production.sh --rollback
```
