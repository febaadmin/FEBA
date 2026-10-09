# FEBA — Guide de configuration des e-mails

Ce guide couvre **tous** les envois d'e-mails de FEBA : accusés de réception
FEBA FHA, envois groupés par académie (« E-mails groupés »), relances de
paiement, rapports mensuels. Ils passent tous par la même couche
(`backend/apps/notifications/mailer.py`) et laissent tous une trace dans le
journal `EmailDelivery`.

---

## 1. Ce que FEBA garantit — et ce qu'il ne prétend pas

| Statut affiché | Signification exacte |
|---|---|
| **Remis au serveur de messagerie** (`sent`) | Le serveur SMTP a accepté le message sans erreur. |
| **Nouvel essai programmé** (`retry`) | Échec temporaire ; une tâche Celery réessaie à +5 min, +30 min, +3 h. |
| **Échec** (`failed`) | Refus définitif ou 4 tentatives épuisées ; l'erreur SMTP exacte est conservée. |
| **Sans fournisseur** | Backend `console`/`locmem` : le message n'est **pas** parti sur Internet. |

FEBA **ne peut pas** savoir qu'un message est arrivé dans la boîte du
destinataire. « Remis au serveur » est l'état le plus fort constatable.

## 2. Configuration SMTP (production)

Dans `.env.prod` (jamais versionné) :

```
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.votre-fournisseur.com
EMAIL_PORT=587
EMAIL_HOST_USER=noreply@globalfeba.com
EMAIL_HOST_PASSWORD=********
EMAIL_USE_TLS=True
EMAIL_TIMEOUT=10
DEFAULT_FROM_EMAIL=noreply@globalfeba.com
FEBA_FROM_EMAIL=          # expéditeur propre à FEBA (facultatif)
FHA_FROM_EMAIL=           # expéditeur propre à FEBA FHA (facultatif)
EMAIL_REPLY_TO=
```

Aucun de ces secrets n'est exposé au frontend, à une URL ou à une réponse
d'API. Le DNS (Hostinger) doit porter les enregistrements **SPF, DKIM et
DMARC** du fournisseur choisi, faute de quoi les messages risquent d'être
classés en indésirables : c'est une action externe à FEBA.

Vérification après configuration :

```bash
docker compose -f docker-compose.prod.yml --env-file .env.prod exec -T backend-prod python manage.py email_check --to votre.adresse@exemple.com </dev/null
```

## 3. Envois groupés par académie (écran « E-mails groupés »)

Accès : administrateurs (leur académie uniquement) et super-administrateurs
(académie choisie explicitement).

Parcours : académie → types de profil (administrateurs, enseignants,
parents, élèves — seuls les rôles réellement présents sont proposés) et/ou
personnes cochées une à une, exclusions possibles → objet et message →
**aperçu** (nombre réel calculé par le serveur) → **confirmation** → suivi →
rapport par destinataire → « Relancer uniquement les échecs ».

Règles :

- Les destinataires sont **recalculés par le serveur** à partir des règles
  d'audience. Un identifiant d'une autre académie fait échouer la demande
  entière (rien n'est envoyé).
- **Un message individuel par destinataire** : aucune adresse n'est visible
  des autres (ni « À » multiple, ni copie).
- Ignorés et rapportés : compte inactif, adresse absente, adresse invalide,
  adresse en double (comparaison insensible à la casse).
- Le super-administrateur n'est jamais destinataire (rôle plateforme).

Garde-fous configurables :

| Variable | Défaut | Rôle |
|---|---|---|
| `MASS_EMAIL_MAX_RECIPIENTS` | 2000 | Plafond de destinataires par envoi |
| `MASS_EMAIL_MAX_CAMPAIGNS_PER_HOUR` | 10 | Envois groupés par utilisateur et par heure |
| `MASS_EMAIL_BATCH_SIZE` | 50 | Taille des lots traités par le worker |

Plus : aperçu obligatoire, confirmation du **nombre exact** (refus si la
liste a changé depuis l'aperçu), jeton anti double-clic.

Fonctionnement technique : la campagne et ses destinataires sont créés en
base, puis confiés au worker Celery (`notifications.send_campaign`). Le
worker réserve les lignes par lots (`SELECT … FOR UPDATE SKIP LOCKED`) :
deux workers ne prennent jamais le même destinataire. Après un redémarrage
de Celery, la tâche planifiée `notifications.process_pending_campaigns`
(toutes les 5 min) reprend ce qui reste, sans renvoyer ce qui est parti.

## 4. Relances automatiques des échecs

`notifications.retry_due_deliveries` (Celery Beat, toutes les 10 min)
relance les envois en « nouvel essai programmé » dont l'heure est venue.
**Avant cette version, aucune tâche ne relisait ces échéances** : le statut
« nouvel essai programmé » restait indéfiniment affiché sans qu'aucun essai
n'ait lieu.

## 5. Accusés de réception FEBA FHA (écran « Admissions FEBA FHA »)

- Le bouton « Renvoyer l'e-mail de confirmation » d'une ligne n'envoie
  **qu'à cette ligne** ; seul son bouton est occupé pendant l'envoi.
- Deux clics (ou deux requêtes) dans les 30 secondes : un seul envoi.
- Envoi groupé : cases à cocher, « Sélectionner les N dossiers affichés »
  (les dossiers masqués par un filtre ne sont jamais inclus), confirmation,
  résultat sur chaque ligne, « Relancer les échecs ».
- Par défaut, l'envoi groupé ne renvoie pas aux dossiers dont l'accusé est
  déjà parti (case à décocher pour forcer).

## 6. Tests sans envoi réel

- Tests automatisés : backend `locmem` (aucun réseau).
- Test SMTP réel contre **Mailpit** (serveur de test local) :

```bash
docker run -d --rm --name feba_mailpit -p 51025:1025 -p 58025:8025 axllent/mailpit
```

```bash
cd backend && MAILPIT_SMTP_PORT=51025 MAILPIT_API_URL=http://127.0.0.1:58025 DJANGO_SETTINGS_MODULE=feba_project.settings.test_sqlite python -m pytest tests/test_audit_p1_mass_email.py -k Mailpit
```

- Environnement de développement Docker : Mailpit est inclus
  (`http://localhost:8025`).

## 7. Diagnostic

| Symptôme | Où regarder |
|---|---|
| « Sans fournisseur » partout | `EMAIL_BACKEND` vaut `console` : configurer le SMTP |
| Échecs `SMTPAuthenticationError` | identifiants SMTP |
| Échecs `SMTPRecipientsRefused` | adresse du destinataire à corriger |
| « Nouvel essai » qui ne bouge pas | worker ou Beat arrêté : `docker compose ps` (healthchecks) |
| Envoi groupé « En file d'attente » + message Redis | broker indisponible ; la reprise est automatique au retour du service |
