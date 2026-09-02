# Déploiement en production — `globalfeba.com`

---

## 1. Architecture cible

```
                      Internet
                          │
        ┌─────────────────┴─────────────────┐
        │                                   │
  globalfeba.com                    meet.globalfeba.com
  (serveur applicatif)              (serveur Jitsi dédié, CPX32)
        │                                   │
  ┌─────┴──────┐                     ┌──────┴───────┐
  │ nginx-prod │  TLS, en-têtes      │ jitsi-web    │ :80 :443
  ├────────────┤                     │ prosody      │ JWT
  │ frontend   │  SPA compilée       │ jicofo       │
  │ backend    │  Django + Gunicorn  │ jvb          │ :10000/udp
  │ celery     │  tâches + beat      └──────────────┘
  │ postgres   │
  │ redis      │
  └────────────┘
```

Les deux serveurs sont **séparés**. Le pont vidéo sature réseau et CPU
pendant les cours : une classe en direct ne doit pas pouvoir ralentir la
facturation ou la génération des bulletins.

---

## 2. Avant de déployer

Les actions qui ne peuvent pas être faites depuis le dépôt sont listées
dans [`MANUAL_PRODUCTION_ACTIONS.md`](MANUAL_PRODUCTION_ACTIONS.md) :
serveur Hetzner, DNS Hostinger, pare-feu, secrets. **Les faire d'abord.**

---

## 3. Configuration

```bash
cp .env.prod.example .env.prod
```

Variables sans valeur par défaut acceptable :

| Variable | Valeur | Pourquoi |
|---|---|---|
| `SECRET_KEY` | `openssl rand -base64 64` | signe sessions et jetons |
| `ALLOWED_HOSTS` | `globalfeba.com,www.globalfeba.com` | Django refuse tout autre hôte |
| `CORS_ALLOWED_ORIGINS` | `https://globalfeba.com,https://www.globalfeba.com` | appels du SPA |
| `CSRF_TRUSTED_ORIGINS` | idem | **sans quoi `/django-admin/` est inaccessible** |
| `DATABASE_URL` | `postgresql://feba:<FORT>@postgres-prod:5432/feba` | — |
| `REDIS_URL` | `redis://redis-prod:6379/0` | Celery et cache |
| `JITSI_DOMAIN` | `meet.globalfeba.com` | **jamais une instance publique** |
| `JITSI_APP_ID` / `JITSI_APP_SECRET` | identiques à `.env.jitsi` | signature des jetons |
| `EMAIL_*` | SMTP réel | un backend console ne délivre rien |
| `FEBA_OFFICIAL_PHONE` | *(vide)* | vaut `0160011717` — à ne changer qu'en cas de changement de ligne |

```bash
grep -rnE '^\s*(SECRET_KEY|.*PASSWORD|.*SECRET)=' .env.prod   # relire avant de continuer
chmod 600 .env.prod
```

`.env.prod` est dans `.gitignore`. **Ne jamais le committer.**

---

## 4. Déploiement

```bash
docker compose -f docker-compose.prod.yml --env-file .env.prod build
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d

docker compose -f docker-compose.prod.yml exec backend-prod python manage.py migrate
docker compose -f docker-compose.prod.yml exec backend-prod python manage.py init_academies
docker compose -f docker-compose.prod.yml exec backend-prod python manage.py collectstatic --noinput
docker compose -f docker-compose.prod.yml exec backend-prod python manage.py createsuperuser
```

> **Ne pas lancer `seed_demo_data` en production.** Il crée des comptes à
> mots de passe connus et des données fictives.

### Certificat TLS

```bash
certbot certonly --standalone -d globalfeba.com -d www.globalfeba.com
docker compose -f docker-compose.prod.yml restart nginx-prod
```

---

## 5. Vérifications après déploiement

```bash
# Santé
curl -sS -o /dev/null -w '%{http_code}\n' https://globalfeba.com/api/health/     # 200

# En-têtes de sécurité
curl -sSI https://globalfeba.com/ | grep -iE 'strict-transport|x-frame|x-content|referrer'

# Redirection HTTP → HTTPS
curl -sS -o /dev/null -w '%{http_code}\n' http://globalfeba.com/                 # 301

# Le flyer est une pièce jointe, pas une page HTML
curl -sSI https://globalfeba.com/images/feba-fha/feba-fha-flyer.pdf \
  | grep -iE 'HTTP|content-type|content-disposition'
# 200 · application/pdf · attachment; filename="FEBA-French-Heritage-Academy-flyer.pdf"

# Un fichier absent répond 404 (et non 200 avec la page du SPA)
curl -sS -o /dev/null -w '%{http_code}\n' \
  https://globalfeba.com/images/feba-fha/aucun-fichier.pdf                       # 404

# Visioconférence
make jitsi-health JITSI_TARGET=meet.globalfeba.com

# Réglages Django
docker compose -f docker-compose.prod.yml exec backend-prod python manage.py check --deploy
```

**Vérification manuelle indispensable :** générer un reçu depuis l'écran
Paiements et confirmer qu'il porte `Tél: 0160011717`.

---

## 6. Exploitation courante

| Besoin | Commande |
|---|---|
| Journaux | `docker compose -f docker-compose.prod.yml logs -f backend-prod` |
| Redémarrer | `docker compose -f docker-compose.prod.yml restart backend-prod` |
| Sauvegarde | `bash scripts/backup.sh` |
| Restauration | `bash scripts/restore.sh <archive>` |
| Diagnostic | `bash scripts/diagnose.sh` |
| Tâches Celery | `docker compose -f docker-compose.prod.yml logs -f celery-prod` |

### Mise à jour

```bash
git pull
docker compose -f docker-compose.prod.yml --env-file .env.prod build
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d
docker compose -f docker-compose.prod.yml exec backend-prod python manage.py migrate
docker compose -f docker-compose.prod.yml exec backend-prod python manage.py collectstatic --noinput
```

**Sauvegarder la base avant toute migration.**

---

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
