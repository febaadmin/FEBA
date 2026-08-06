# CELERY_JITSI_HEALTH_REPORT.md — P7 & P8, juillet-août 2026

## P8 — Celery toujours unhealthy

### La commande fautive, telle quelle

```yaml
healthcheck:
  test: ["CMD", "celery", "-A", "feba_project", "inspect", "ping", "-d", "celery@$$HOSTNAME"]
```

### Pourquoi elle échoue TOUJOURS, quel que soit l'état réel du worker

`CMD` (forme exec, par opposition à `CMD-SHELL`) exécute le binaire
directement — **sans passer par un shell**. Aucune expansion de variable
n'a jamais lieu. `$$HOSTNAME` (après le passage de `$$` à `$` propre à la
syntaxe docker-compose) devient l'argument littéral `celery@$HOSTNAME`,
chaîne de caractères brute, jamais résolue vers le nom réel du conteneur.
Celery cherche donc un worker nommé EXACTEMENT `celery@$HOSTNAME` — qui
n'a jamais existé, n'existera jamais. `inspect ping -d <destinataire
inexistant>` échoue par construction, systématiquement.

### Correction

```yaml
test: ["CMD", "celery", "-A", "feba_project", "inspect", "ping"]
```

Sans `-d`, la commande interroge TOUS les workers disponibles et réussit
dès qu'un seul répond — exactement la commande de référence donnée dans
la demande d'origine (`docker compose exec -T celery-dev celery -A
feba_project inspect ping`), et suffisante ici puisqu'un seul worker
tourne par conteneur.

### Autres causes possibles, vérifiées et écartées

La demande listait plusieurs pistes à vérifier avant de conclure. Chacune
a été contrôlée directement dans ce sandbox (Redis réel, Django réel) :

| Piste | Vérification | Résultat |
|---|---|---|
| Module Celery mal configuré | `from feba_project.celery import app` | Import propre, aucune erreur |
| Broker inaccessible | `CELERY_BROKER_URL = REDIS_URL`, testé contre Redis réel | Connexion OK |
| Tâches non importées | `app.loader.import_default_modules()` puis liste des tâches | 5 tâches applicatives enregistrées, dont `monthly_reports.send_one` et `monthly_reports.generate_month` |
| Nom du nœud | `-d celery@$$HOSTNAME` | **C'était ça** — voir ci-dessus |

Rien d'autre n'a été trouvé de ce côté — la commande de healthcheck était
la seule et unique cause.

### Vérification finale à faire chez vous

```bash
make ps                                                    # celery-dev : healthy
docker compose exec -T celery-dev celery -A feba_project inspect ping
# attendu : pong

docker compose exec -T backend-dev python manage.py generate_month_reports --dry-run
# ou toute action réelle déclenchant monthly_reports.send_one, pour confirmer
# l'exécution effective d'une tâche, pas seulement la réponse au ping.
```

---

## P7 — Jitsi injoignable depuis le backend

### Le problème à deux niveaux

**Niveau 1 — la mauvaise URL.** `jitsi_health()`
(`backend/apps/virtualclass/services.py`) utilisait `JITSI_DOMAIN` (ex.
`localhost:8443`) pour sonder Jitsi en HTTP. Cette adresse est correcte
pour un NAVIGATEUR (le port 8443 de l'hôte est mappé vers `jitsi-web`).
Depuis l'INTÉRIEUR du conteneur backend, `localhost` désigne ce conteneur
lui-même — jamais Jitsi.

**Niveau 2 — trouvé en creusant, plus grave.** `docker-compose.yml` (pile
principale) et `docker-compose.jitsi.yml` (pile Jitsi) sont deux projets
Docker Compose **indépendants**, chacun avec son réseau Docker par défaut.
Même en corrigeant l'URL, le conteneur backend n'avait **aucun chemin
réseau** vers `jitsi-web` — les deux conteneurs ne pouvaient pas se voir,
quel que soit le nom utilisé.

### Correction, en trois parties

**1. Réseau partagé**, créé dans `docker-compose.yml` et référencé en
`external: true` dans `docker-compose.jitsi.yml` :

```yaml
# docker-compose.yml
networks:
  default:
  feba_jitsi_shared:
    name: feba_jitsi_shared
services:
  backend-dev:
    networks: [default, feba_jitsi_shared]
```

```yaml
# docker-compose.jitsi.yml
networks:
  jitsi:
  feba_jitsi_shared:
    external: true
    name: feba_jitsi_shared
services:
  jitsi-web:
    networks: [jitsi, feba_jitsi_shared]
```

`scripts/jitsi_up.sh` crée ce réseau lui-même s'il n'existe pas encore
(cas où Jitsi serait démarré avant le reste — ordre inversé, toléré).

**2. URL interne distincte**, nouveau réglage `JITSI_INTERNAL_URL` :

```python
# backend/feba_project/settings/base.py
JITSI_INTERNAL_URL = config('JITSI_INTERNAL_URL', default='')
```

Écrit automatiquement par `scripts/bootstrap.sh` :
`JITSI_INTERNAL_URL=http://jitsi-web:80` — le nom du service Docker,
directement, sur le réseau partagé.

**3. `jitsi_health()` sonde l'URL interne**, jamais `JITSI_DOMAIN`, pour
son propre test de joignabilité — `JITSI_DOMAIN` reste utilisé pour la
signature des jetons JWT (doit correspondre à ce que le NAVIGATEUR
utilise, c'est différent par nature).

### Diagnostic amélioré

`make jitsi-health` affiche désormais l'URL réellement testée :

```
État : OPÉRATIONNEL
Configuration : oui
Signature jeton : oui
Instance joignable : oui
URL testée (interne) : http://jitsi-web:80/
```

### Tests (mock HTTP — pas de vrai Jitsi disponible ici)

```python
def test_url_interne_est_utilisee_quand_definie(self):
    ...
    self.assertEqual(captured["url"], "http://jitsi-web:80/")
    self.assertNotIn("localhost", captured["url"])
```

3 tests nouveaux dans `tests/test_jitsi_selfhosted.py`
(`JitsiHealthInternalUrlTests`) : URL interne utilisée quand définie,
repli sur `JITSI_DOMAIN` sinon (compatibilité production), instance
interne injoignable correctement signalée dégradée. 18/18 tests du
fichier verts.

### Vérification finale à faire chez vous

```bash
make jitsi-up
make jitsi-health
# attendu : instance joignable : oui, sans jamais mentionner localhost
# pour le côté backend.

docker compose exec -T backend-dev python -c "
import urllib.request
print(urllib.request.urlopen('http://jitsi-web:80/', timeout=5).status)
"
# attendu : 200 — confirme le réseau partagé fonctionne réellement,
# pas seulement que la configuration est cohérente sur le papier.
```
