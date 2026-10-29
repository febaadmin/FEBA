# Déploiement en production — `globalfeba.com`

---

## 1. Architecture cible

```
                      Internet
                          │
        ┌─────────────────┴─────────────────┐
        │                                   │
  globalfeba.com (62.238.38.111)     meet.globalfeba.com
  serveur applicatif FEBA            visioconférence plugNmeet
        │                            (PLUGNMEET_DEPLOYMENT_GUIDE.md ;
  ┌─────┴──────┐                      Jitsi conservé en retour arrière)
  │ nginx-prod │  TLS, en-têtes, ACME webroot
  │ frontend   │  SPA compilée (npm ci)
  │ backend    │  Django + Gunicorn  ┐
  │ celery     │  worker             ├ UNE image feba-backend:<tag>
  │ celery-beat│  planificateur      ┘
  │ postgres   │  redis
  └────────────┘
```

Le backend, le worker et Beat démarrent tous par
`manage.py production_preflight` : une configuration incomplète ou de
développement (transport e-mail console ou Mailpit, SMS de capture,
`PUBLIC_BASE_URL` en localhost, webhook hors `ALLOWED_HOSTS`, secret
d'exemple…) **refuse le démarrage** avec la liste des corrections.

## 2. Avant de déployer

Actions hors dépôt (serveur, DNS, pare-feu, comptes SMTP / SMS / plugNmeet) :
[`MANUAL_PRODUCTION_ACTIONS.md`](MANUAL_PRODUCTION_ACTIONS.md). **D'abord.**

## 3. Configuration

```bash
cp .env.prod.example .env.prod      # puis renseigner chaque CHANGE_ME
chmod 600 .env.prod
make prod-preflight                 # même contrôle que celui du démarrage
```

| Variable | Valeur | Pourquoi |
|---|---|---|
| `DJANGO_ENV` / `DEPLOYMENT_STAGE` | `prod` / `production` | `staging` (préproduction) tolère Mailpit et la capture SMS |
| `SECRET_KEY` | `python3 -c "import secrets;print(secrets.token_urlsafe(64))"` | refusée si absente ou d'exemple |
| `PUBLIC_BASE_URL` | `https://globalfeba.com` | retours de visioconférence, paiements Stripe |
| `ALLOWED_HOSTS` | `globalfeba.com,www.globalfeba.com` | le PREMIER sert au certificat et aux tests de fumée |
| `CSRF_TRUSTED_ORIGINS` / `CORS_ALLOWED_ORIGINS` | `https://globalfeba.com,https://www.globalfeba.com` | |
| `DATABASE_URL` / `DB_PASSWORD` | même mot de passe | PostgreSQL |
| `REDIS_URL` | `redis://redis-prod:6379/0` | Celery et cache |
| `EMAIL_*`, `DEFAULT_FROM_EMAIL` | SMTP Hostinger, `noreply@globalfeba.com` | `EMAIL_CONFIGURATION_GUIDE.md` |
| `VIDEO_PROVIDER`, `PLUGNMEET_*` | `plugnmeet` | `PLUGNMEET_DEPLOYMENT_GUIDE.md` |
| `SMS_*`, `TWILIO_*` | `SMS_ENABLED=False` tant que `sms_check` n'a pas réussi | `SMS_CONFIGURATION_GUIDE.md` |

`.env.prod` est ignoré par Git et exclu des archives. **Ne jamais le committer.**

## 4. Déploiement

```bash
apt install -y certbot                                   # une fois
scripts/tls_bootstrap.sh --email admin@globalfeba.com    # certificat + renouvellement webroot (idempotent)
make prod                                                # = scripts/deploy_feba.sh
```

`scripts/deploy_feba.sh` : prérequis → composition résolue → **contrôle de
pré-démarrage sur la nouvelle image, avant toute bascule** → certificat →
**sauvegarde de la base vérifiée** (`backups/`) → images actuelles
marquées `previous` → démarrage (migrations et fichiers statiques par
l'entrée du backend) → santé → tests de fumée (HTTPS, API protégée,
même configuration sur backend/worker/Beat, worker joignable) →
**retour arrière automatique** en cas d'échec. Relancer le script est
sans danger : aucun volume supprimé, aucun secret modifié.

Premier déploiement seulement :

```bash
docker compose --env-file .env.prod -f docker-compose.prod.yml exec backend-prod python manage.py init_academies
docker compose --env-file .env.prod -f docker-compose.prod.yml exec backend-prod python manage.py createsuperuser
```

> **Ne pas lancer `seed_demo_data` / `bootstrap_demo` en production** : comptes à mots de passe connus.

## 5. Vérifications après déploiement

Faites par le script (§ 4). En complément :

```bash
curl -sSI https://globalfeba.com/ | grep -iE 'strict-transport|x-frame|x-content|referrer'
curl -sS -o /dev/null -w '%{http_code}\n' http://globalfeba.com/                 # 301
docker compose --env-file .env.prod -f docker-compose.prod.yml exec -T backend-prod python manage.py plugnmeet_health
docker compose --env-file .env.prod -f docker-compose.prod.yml exec -T backend-prod python manage.py email_check --to <adresse de test>
docker compose --env-file .env.prod -f docker-compose.prod.yml exec -T backend-prod python manage.py sms_check
certbot renew --dry-run                                                           # renouvellement TLS
```

## 6. Exploitation courante

| Besoin | Commande |
|---|---|
| Journaux | `make prod-logs` |
| Contrôle de configuration | `make prod-preflight` |
| Retour à la version précédente | `make prod-rollback` |
| Sauvegarde / restauration | `scripts/backup_database.sh`, `RESTORE_GUIDE.md` |
| Tâches planifiées | `docker compose --env-file .env.prod -f docker-compose.prod.yml logs celery-beat \| grep "Sending due task"` |

Toutes les commandes `docker compose` de production prennent
`--env-file .env.prod`.

---

## 6 bis. Vhosts additionnels (`sites-enabled/`)

`nginx.prod.conf` charge `/etc/nginx/sites-enabled/*.conf`. Le répertoire
est **livré vide**, et le comportement par défaut est donc strictement
celui de la V8 : un motif qui ne correspond à aucun fichier n'est pas une
erreur pour nginx.

Il sert à activer `meet.globalfeba.com` en topologie B, sans modifier le
fichier principal. Le vhost prêt à l'emploi est dans
`nginx/sites-available/`, **non activé** : il référence un certificat qui
n'existe pas encore, et nginx refuse de démarrer sur un certificat
manquant — ce nginx servant aussi `globalfeba.com`.

```bash
cp nginx/sites-available/meet.globalfeba.com.conf nginx/sites-enabled/
docker compose -f docker-compose.prod.yml exec nginx-prod nginx -t   # OBLIGATOIRE
docker compose -f docker-compose.prod.yml exec nginx-prod nginx -s reload
```

## 7. Sécurité — à relire avant la mise en service

- [ ] `DEBUG = False` (imposé par `settings/prod.py`)
- [ ] `SECRET_KEY` unique, jamais celui du modèle
- [ ] `ALLOWED_HOSTS` sans `*`
- [ ] `CSRF_TRUSTED_ORIGINS` renseigné avec le schéma `https://`
- [ ] Aucun compte de démonstration
- [ ] Mots de passe PostgreSQL et Redis forts
- [ ] `.env.prod` en `chmod 600`, hors Git
- [ ] SSH limité à une IP d'administration
- [ ] `JITSI_DOMAIN` ≠ toute instance publique
- [ ] Sauvegardes planifiées **et restauration testée**
- [ ] Certificats TLS renouvelés automatiquement
