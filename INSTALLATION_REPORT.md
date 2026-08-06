# INSTALLATION_REPORT.md — P5, P6, P9, P10, P11, P12

## P5 — Collision de migrations, cause exacte

```
scripts/bootstrap.sh, étape 6 :
    docker compose up -d backend-dev
    → retourne immédiatement (mode détaché)
    → backend-dev/entrypoint.dev.py migre AUTOMATIQUEMENT au démarrage

scripts/bootstrap.sh, étape 9 (plus loin dans le même script) :
    docker compose exec -T backend-dev python manage.py migrate --noinput
    → une SECONDE migration, potentiellement EN PARALLÈLE de la première
```

Deux processus `manage.py migrate --noinput` concurrents sur une base
neuve : chacun tente de créer les mêmes tables. Le premier à atteindre
`schedule.0003_onlinesessionschedule_and_more` gagne ; le second échoue
avec `relation "schedule_onlinesessionschedule" already exists` — sauf que
lequel des deux « gagne » dépend du timing, donc le bug n'est pas
systématiquement reproductible, ce qui correspond bien à un rapport de bug
intermittent.

### Correction — un service dédié, propriétaire unique

```yaml
migrate:
  build: {context: ./backend, dockerfile: Dockerfile.dev}
  env_file: .env.dev
  depends_on:
    postgres-dev: {condition: service_healthy}
  command: python manage.py migrate --noinput
  restart: "no"

backend-dev:
  depends_on:
    migrate: {condition: service_completed_successfully}
    ...
```

`celery-dev` et `celery-beat-dev` dépendent aussi de `migrate`
(`service_completed_successfully`) — ils utilisent la même base et ne
doivent pas non plus démarrer avant qu'elle soit prête.

`entrypoint.dev.py` ne migre plus — il **vérifie** (`migrate --check`) et
échoue avec un message explicite si le service `migrate` n'a pas fait son
travail, plutôt que de le refaire.

`scripts/bootstrap.sh` ne relance plus `migrate` à l'étape 9 — il vérifie
également (`migrate --check --noinput`), en confiance dans la garantie
`depends_on` de l'étape 6.

### Preuve, dans les limites de ce qui est vérifiable sans Docker

```bash
$ python manage.py migrate --noinput     # contre PostgreSQL réel
... (toutes les migrations s'appliquent sans erreur)

$ python manage.py migrate --plan
Planned operations:
  No planned migration operations.
```

La collision elle-même — deux PROCESSUS DOCKER concurrents — ne peut être
reproduite que sous Docker. Ce qui est garanti ici, c'est qu'il n'existe
plus qu'un seul point d'entrée possible pour `migrate` dans tout le
pipeline (`docker-compose.yml` en fait le seul et unique service qui migre).

---

## P6 — Makefile, dépendance Python locale

### Cibles corrigées (9)

`documents-ready`, `branding-check`, `payments-check`,
`payments-webhook-check`, `documents-check`, `documents-install`,
`documents-calibrate`, `documents-compare`, `init-academies` — toutes
réécrites de `cd backend && python manage.py ...` vers
`docker compose exec -T backend-dev python manage.py ...`, via une
variable `MANAGE` unique.

### Exception assumée : `payments-setup`

Cette commande est interactive et écrit directement sur le système de
fichiers de l'HÔTE (`.env.dev`, volontairement non monté dans le
conteneur — un secret de paiement Stripe n'a rien à faire dans une image
Docker). Elle reste en Python local, mais échoue maintenant avec :

```
✗ python3 est requis pour cette commande (elle écrit directement sur votre poste, hors Docker).
  Installez Python 3, ou éditez .env.dev à la main (voir .env.dev.example).
```

au lieu de l'opaque `python: command not found`.

---

## P9 — Installation en étapes contrôlées

Trois nouvelles commandes, en plus du pipeline `bootstrap.sh` déjà en
place :

- **`make doctor`** — prérequis (Docker, Compose v2, démon actif, openssl)
  ET cohérence de `.env.dev` (fichier réellement utilisé, `DATABASE_URL`/
  `REDIS_URL` qui ne pointent pas vers `localhost` depuis un conteneur,
  `EMAIL_BACKEND` cohérent avec Mailpit, `JITSI_INTERNAL_URL` distinct de
  `localhost`, permissions du fichier de secrets). Peut être lancé seul, à
  tout moment, sans rien démarrer.
- **`make install-check`** — vérifie qu'une installation a RÉELLEMENT
  réussi : tous les services `healthy`, `migrate --check` propre,
  `seed_check` (isolation multi-académies), `documents_ready`,
  `jitsi_health`, `celery inspect ping`, et `migrate --plan` idempotent.
- **`make repair`** — remédiation ciblée et NON destructive (rejoue
  `migrate`, redémarre les services en échec, régénère les documents si
  besoin) — délibérément sans `-v` : ce n'est pas `make reset`.

`make install` enchaîne désormais : `doctor` (avertissement, non
bloquant) → `bootstrap.sh` (le pipeline complet) → `install-check`
(rapport final).

---

## P10 — Suite de test d'installation réelle

`tests/installation/test_clean_docker_install.sh` — un script unique
(voir son en-tête pour le raisonnement : aucune commande utilisée n'est
spécifique à une architecture, toutes les images Docker du projet sont
multi-arch — `postgres:16-alpine`, `redis:7-alpine`, `jitsi/*:stable`,
Dockerfiles maison basés sur des images officielles Python/Node
multi-plateformes). Le même script, lancé sur trois machines différentes,
exerce trois fois le même chemin réel — pas trois scripts à maintenir en
parallèle qui pourraient diverger entre eux.

13 vérifications : services healthy, migrations, seed + isolation,
documents officiels, identité des académies, frontend joignable, API
joignable, Celery, Mailpit, Jitsi (si démarré), et idempotence via un
second `make install` suivi d'un second `migrate --plan`.

```bash
./tests/installation/test_clean_docker_install.sh /chemin/vers/archive.zip
# ou, depuis un dépôt déjà extrait :
make test-install
```

**Non exécuté ici** (pas de Docker) — validé uniquement par lecture
(`bash -n`, syntaxe correcte). C'est le script à lancer, sur Linux
x86_64, Linux ARM64, et macOS Apple Silicon avec Docker Desktop, pour la
validation finale réellement demandée.

---

## P11 — Convention `.env` unique

### La contradiction trouvée, en creusant P5

```bash
$ grep env_file docker-compose.yml
    env_file: .env.dev        # (× 3, sur backend-dev, celery-dev, celery-beat-dev)

$ grep 'APP_ENV=' scripts/bootstrap.sh    # (avant correction)
APP_ENV="$ROOT/.env"
```

Sur une installation VRAIMENT neuve — aucun fichier `.env.dev`
préexistant, aucun `.env` non plus — `bootstrap.sh` écrivait secrets et
configuration dans `.env`, un fichier qu'AUCUN service Docker Compose ne
charge. Selon la version de Docker Compose, `env_file: .env.dev` pointant
vers un fichier absent peut faire échouer `docker compose up` purement et
simplement, ou être silencieusement ignoré — dans les deux cas, une
installation cassée par une simple divergence de nom de fichier.

### Correction

Une seule convention : **`.env.dev`** pour tout ce que Docker Compose
charge en développement. `bootstrap.sh` corrigé, `Makefile`
(`payments-setup`) corrigé, `.env.example` annoté pour éviter la même
confusion à l'avenir, `make doctor` qui détecte et signale explicitement
un `.env` isolé si quelqu'un en recrée un par habitude.

---

## P12 — Documentation compatible macOS/zsh

`INSTALLATION_GUIDE.md` entièrement réécrit. L'ancien portait l'en-tête
« INSTALL_V6.md (20/07/2026) » et était doublement obsolète :

- Références factuelles fausses : `make dev` (n'existe plus tel quel),
  `.env` (voir P11), nom de zip `feba_v1_v6_complet.zip`, effectifs de
  tests « 300 passed, 1 skipped » — contre 887 tests réels aujourd'hui.
- Un bloc de commandes mélangeant lignes de commentaire (`# Backend
  (SQLite de développement)`) et commandes shell dans le même bloc à
  copier-coller — exactement le motif qui produit
  `zsh: command not found: #` sur macOS, où zsh (shell par défaut depuis
  Catalina) ne traite pas `#` comme un commentaire en session interactive,
  contrairement à bash.

Le nouveau guide : chaque commande sur sa propre ligne, aucun commentaire
mêlé à une commande à coller, reflète le pipeline `make install` réel tel
qu'il existe maintenant dans le Makefile.
