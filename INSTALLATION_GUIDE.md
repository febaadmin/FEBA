# Guide d'installation — FEBA multi-académies

> Remplace l'ancien `INSTALLATION_GUIDE.md` (V6, 20/07/2026), qui référençait
> `make dev`, un fichier `.env` que rien ne charge réellement, et des
> effectifs de tests obsolètes. Voir `CORRECTIONS.md` (P11, P12) pour le
> détail de ce qui a changé et pourquoi.

## 1. Prérequis

- Docker 24+ et le plugin Docker Compose v2 (`docker compose version` doit
  répondre — pas `docker-compose` en v1, séparé par un tiret).
- `openssl` (génération des secrets — présent par défaut sur macOS et Linux).
- Git.

Aucune installation locale de Python ou Node n'est nécessaire : toutes les
commandes officielles passent par Docker. `make doctor` vérifie ces
prérequis avant de démarrer quoi que ce soit.

## 2. Installation

Chaque commande ci-dessous est **une ligne**, à coller telle quelle. Pas de
bloc contenant des commentaires `#` mêlés aux commandes : sur macOS, le
shell par défaut est zsh, qui — contrairement à bash — ne traite pas `#`
comme un commentaire en session interactive et échoue avec
`zsh: command not found: #` si un commentaire est collé avec la commande.

```bash
unzip feba_multi_academies_v9_application.zip
cd feba_multi_academies_v9_application
make install
```

`make install` exécute, dans l'ordre, et s'arrête à la première étape en
échec (voir `scripts/bootstrap.sh`) :

1. Vérification des prérequis (`make doctor`)
2. Préparation de `.env.dev` (généré depuis `.env.dev.example` si absent,
   secrets générés par `openssl rand`)
3. Démarrage de PostgreSQL, Redis, Mailpit
4. Application des migrations par un service dédié (`migrate`), avant tout
   autre service — aucune migration concurrente possible
5. Démarrage du backend, puis de Celery (worker + beat)
6. Initialisation des académies FEBA et FEBA FHA
7. Préparation des gabarits documentaires (diplômes, certificats)
8. Démarrage du frontend
9. Vérification complète (`make install-check`)

À la fin, l'application est accessible sur :

| Service | URL |
|---|---|
| Application (frontend) | http://localhost:5173 |
| API | http://localhost:8000/api/ |
| Admin Django | http://localhost:8000/django-admin/ |
| Mailpit (courrier de développement) | http://localhost:8025 |

## 3. Salles virtuelles (Jitsi)

Optionnel — nécessaire uniquement pour les cours en ligne (FEBA FHA) :

```bash
make jitsi-up
```

Démarre une instance Jitsi auto-hébergée (jamais un service public :
politique de protection des mineurs) et la relie au backend via un réseau
Docker partagé. Vérifier ensuite :

```bash
make jitsi-health
```

Doit afficher `État : OPÉRATIONNEL`, `Instance joignable : oui`.

## 4. Données de démonstration

```bash
make seed
make seed-check
```

`seed-check` échoue si une donnée d'une académie est visible depuis
l'autre — les 20 contrôles d'isolation multi-académies attendus.

## 5. Vérification manuelle

Suivre le démarrage :

```bash
make logs        # tous les services
make ps          # état de santé de chaque conteneur
```

Si un service reste `unhealthy` ou qu'un contrôle échoue :

```bash
make diagnose     # diagnostic détaillé du service en cause
make repair       # remédiation ciblée (migrations, redémarrage, documents)
```

## 6. Réinstallation propre

```bash
docker compose down -v --remove-orphans
make install
```

Doit réussir une seconde fois sans erreur ni doublon — `make install` est
idempotent (voir `TEST_REPORT.md`, section idempotence).

## 7. Variables d'environnement

Un seul fichier fait autorité pour le développement : **`.env.dev`**,
chargé par `docker-compose.yml`. Ne créez pas de `.env` isolé en pensant
qu'il sera pris en compte — `make doctor` le signale explicitement s'il en
trouve un. Partir de `.env.dev.example` (déjà fait automatiquement par
`make install` si `.env.dev` n'existe pas encore).

Les secrets Jitsi vivent séparément dans `.env.jitsi` (généré par
`make install` ou `make jitsi-up`), jamais dans `.env.dev`.

## 8. Tests

```bash
make payments-test                          # tests de paiement (SQLite, rapide)
docker compose exec -T backend-dev python manage.py test tests   # suite complète (Postgres)
cd frontend && npm run lint && npm run build
```

Voir `TEST_REPORT.md` pour les résultats réels de la dernière exécution.
