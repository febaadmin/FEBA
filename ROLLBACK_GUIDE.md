# FEBA — Retour arrière

Un déploiement sans retour arrière n'est pas un déploiement, c'est un
pari. Ce document décrit comment défaire chaque changement, du plus
courant au plus lourd.

---

## 0. Avant tout : que s'est-il cassé ?

```bash
make production-health
```

| Bilan | Ce que cela veut dire | Où aller |
|---|---|---|
| `READY` | rien n'est cassé — cherchez ailleurs | — |
| `DEGRADED` | l'essentiel fonctionne, un point secondaire non | §1 ou §2 |
| `UNAVAILABLE` | un service est hors service | §3 puis §4 |

Ne revenez pas en arrière par réflexe. Un retour arrière sur une panne
qu'il ne cause pas fait perdre le correctif **et** le temps de le
comprendre.

---

## 1. Annuler les en-têtes de sécurité seuls

Le cas le plus fréquent : la conférence ne s'ouvre plus après avoir posé
la CSP.

```bash
cd /opt/feba/app
sed -i '/^JITSI_CSP_HEADER=/d' .env.jitsi
docker compose -f docker-compose.jitsi.yml -f docker-compose.jitsi.prod.yml \
  --env-file .env.jitsi up -d jitsi-web
```

**Vérification :**

```bash
curl -sSI https://meet.globalfeba.com/ | grep -i content-security-policy
```

Aucune ligne ne doit sortir. Réessayez alors d'ouvrir une conférence
depuis FEBA.

> **Cause la plus probable si la CSP casse Jitsi :** `'self'` a été retiré
> de `frame-ancestors`. L'External API crée une iframe sur le domaine de
> Jitsi lui-même ; sans `'self'`, elle est bloquée.

---

## 2. Annuler le montage nginx-custom

```bash
cd /opt/feba/app
docker compose -f docker-compose.jitsi.yml -f docker-compose.jitsi.prod.yml \
  stop jitsi-web
git checkout HEAD~1 -- docker-compose.jitsi.prod.yml
docker compose -f docker-compose.jitsi.yml -f docker-compose.jitsi.prod.yml \
  up -d jitsi-web
```

**Vérification :**

```bash
docker compose -f docker-compose.jitsi.yml -f docker-compose.jitsi.prod.yml \
  exec jitsi-web nginx -t
curl -sSI https://meet.globalfeba.com/ | head -6
```

---

## 3. Retour arrière complet, automatisé

```bash
cd /opt/feba/app
bash scripts/deploy_production.sh --rollback
```

Ce que le script fait, dans cet ordre :

1. reprend la dernière sauvegarde de `/root/feba-sauvegardes/` ;
2. remet le dépôt sur le commit noté avant le déploiement ;
3. restaure `.env`, `.env.jitsi`, `backend/.env` ;
4. redémarre la pile Jitsi.

**Vérification :**

```bash
git rev-parse HEAD          # doit être ebe8d57 si l'on revient à la production actuelle
make jitsi-health JITSI_TARGET=meet.globalfeba.com
```

---

## 4. Retour arrière des migrations

**À ne faire que si le déploiement a appliqué des migrations et que
c'est bien là qu'est le problème.** Les migrations de cette livraison
n'effacent aucune donnée.

```bash
cd /opt/feba/app
docker compose -f docker-compose.prod.yml exec backend-prod \
  python manage.py migrate classes 0002
docker compose -f docker-compose.prod.yml exec backend-prod \
  python manage.py migrate schools 0015
docker compose -f docker-compose.prod.yml exec backend-prod \
  python manage.py migrate virtualclass 0002
```

| Migration annulée | Ce qui est perdu |
|---|---|
| `classes.0004` | les parcours déduits — toutes les classes FHA redeviennent `BILINGUAL` |
| `classes.0003` | le champ `language_track` lui-même |
| `schools.0016` | l'activation des années orphelines |
| `virtualclass.0003` | le ciblage des salles par rôle |

**Conséquence à connaître :** une classe francophone redevenue
`BILINGUAL` redemandera une matière anglaise. C'est le comportement
d'avant la correction, pas un nouveau défaut.

---

## 5. Restauration de la base

**Dernier recours.** À n'utiliser que si des données ont été altérées.

```bash
ls -lt /root/feba-sauvegardes/
bash scripts/restore_backup.sh /root/feba-sauvegardes/<horodatage>
```

Toute donnée saisie **après** la sauvegarde est perdue. Prévenez les
utilisateurs avant, pas après.

---

## 6. Le réseau Docker

Si un démarrage échoue sur :

```
network feba_jitsi_shared declared as external, but could not be found
```

```bash
make jitsi-network
```

Cette cible est idempotente : elle ne fait rien si le réseau existe déjà.
Elle est aussi une dépendance de `jitsi-prod-up` et `jitsi-proxy-up`, donc
ce cas ne devrait plus se présenter par le chemin documenté.

---

## 7. Ce qu'un retour arrière ne défait pas

| Élément | Pourquoi |
|---|---|
| Certificats Let's Encrypt renouvelés | un renouvellement est bénéfique et n'a pas à être annulé |
| Fichiers déposés par les utilisateurs | ils appartiennent aux utilisateurs |
| Règles de pare-feu Hetzner | modifiées à la main, à défaire à la main |
| Enregistrements DNS | idem, chez Hostinger |

---

## 8. Après un retour arrière

1. `make production-health` — confirmer que l'état d'avant est retrouvé ;
2. noter **ce qui a échoué et à quelle heure** — les journaux de cette
   fenêtre sont la seule trace exploitable ;
3. ne pas relancer le même déploiement sans avoir compris la panne.

```bash
docker compose -f docker-compose.jitsi.yml -f docker-compose.jitsi.prod.yml \
  logs --since 30m jitsi-web prosody jvb > /root/incident-$(date +%F-%H%M).log
```
