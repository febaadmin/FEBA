# FEBA — Sécurité, RGPD & Reprise d'activité (v35)

## 1. Sécurité

### Authentification & permissions
- JWT (SimpleJWT) : accès 60 min (30 min conseillé en prod), refresh 7 j, **rotation + blacklist** des refresh tokens.
- Rôles hiérarchisés (superadmin 100 > admin 80 > enseignant 50 > parent 30 > élève 10) appliqués endpoint par endpoint ; tests anti-escalade de privilèges inclus dans la suite.
- Multi-tenant : chaque requête est confinée à l'établissement (`get_request_school` + `IsSameTenant`), avec tests de régression dédiés.
- Visioconférence : **JWT Jitsi signés par le backend** (HS256, secret partagé `JITSI_APP_SECRET`) — aucune salle de l'instance auto-hébergée ne s'ouvre sans passer par la vérification de permissions Django ; enseignants/admins reçoivent le rôle modérateur ; expiration 3 h ; codes de salles non énumérables (uuid).

### Réseau
- Production : HTTPS obligatoire (Let's Encrypt), HSTS/secure cookies activés par `settings/prod.py` ; seuls 80/443 exposés (+ UDP 10000 pour le pont vidéo Jitsi) ; PostgreSQL/Redis/Gunicorn non exposés (réseaux Docker internes).
- Piles isolées : FEBA (`docker-compose.prod.yml`) et Jitsi (`docker-compose.jitsi.yml`) sont des services **indépendants** sur des réseaux Docker distincts.

### Secrets
- Aucune clé dans le code : `SECRET_KEY`, mots de passe DB, `JITSI_APP_SECRET`, etc. proviennent exclusivement des fichiers d'environnement (`.env.prod`, `.env.jitsi`, non versionnés — seuls les `.example` le sont). Génération : `openssl rand -hex 32`.
- `settings/prod.py` refuse de démarrer sans `SECRET_KEY` explicite ; `DEBUG=False` imposé.

## 2. Conformité RGPD

### Cartographie des données personnelles
| Catégorie | Données | Base de traitement |
|---|---|---|
| Élèves | identité, date de naissance, photo, scolarité (notes, absences, décisions), présence aux cours virtuels | exécution de la mission d'enseignement |
| Parents | identité, coordonnées, profession, liens familiaux, paiements | gestion administrative et financière |
| Personnels | identité, coordonnées, affectations | gestion RH |
| Techniques | journaux applicatifs, historiques d'audit (notes, paiements) | intérêt légitime (sécurité, traçabilité) |
Aucun flux vidéo n'est enregistré par défaut (Jitsi auto-hébergé = flux temps réel uniquement).

### Droits des personnes — mise en œuvre dans FEBA
- **Accès / portabilité** : exports Excel/PDF par élève (dossier annuel via `GET /students/{id}/history/`).
- **Rectification** : édition par les administrateurs sur toutes les fiches.
- **Effacement** : stratégie graduée conforme — retrait d'une inscription annuelle, désactivation réversible (soft delete), suppression définitive **bloquée tant que des dépendances existent** puis effaçant en cascade ; comptes utilisateurs désactivables.
- **Limitation de conservation** : politique recommandée — données pédagogiques conservées la scolarité + durée légale locale, puis purge via suppression définitive ; sauvegardes en rotation bornée (7 j / 4 sem / 12 mois — voir §3), donc effacement effectif des copies au plus tard 12 mois après purge.
- **Journalisation** : historiques immuables des notes (GradeHistory) et paiements (PaymentHistory) ; journaux serveur horodatés.
- **Sous-traitance / hébergement** : héberger dans une juridiction adéquate ; l'instance Jitsi auto-hébergée évite tout transfert de flux vers un tiers (contrairement à meet.jit.si, proscrit en production).

## 3. Reprise d'activité (Disaster Recovery)

### Sauvegardes automatisées (scripts fournis dans `scripts/`)
| Script | Contenu | Fréquence conseillée (cron) |
|---|---|---|
| `backup_database.sh` | Dump PostgreSQL complet (utilisateurs, élèves, parents, années, notes, paiements, absences…) + checksum | `0 2 * * *` |
| `backup_files.sh` | Médias (photos, documents, bulletins, reçus, justificatifs) | `15 2 * * *` |
| `backup_jitsi.sh` | Volumes de configuration Jitsi (web, **prosody/JWT**, jicofo, jvb) + `.env.jitsi` | `30 2 * * 0` |
Rotation automatique : **7 quotidiennes, 4 hebdomadaires, 12 mensuelles**. Copie hors site obligatoire : variable `RCLONE_REMOTE` (S3 compatible, NAS, serveur secondaire) — les sauvegardes ne restent jamais uniquement sur le serveur principal.

Installation cron (exemple) :
```
0 2 * * *  cd /opt/feba && RCLONE_REMOTE=s3feba:feba-backups ./scripts/backup_database.sh /backups/feba >> /var/log/feba-backup.log 2>&1
15 2 * * * cd /opt/feba && RCLONE_REMOTE=s3feba:feba-backups ./scripts/backup_files.sh    /backups/feba >> /var/log/feba-backup.log 2>&1
30 2 * * 0 cd /opt/feba && RCLONE_REMOTE=s3feba:feba-backups ./scripts/backup_jitsi.sh    /backups/feba >> /var/log/feba-backup.log 2>&1
```

### Restauration
- **Base** : `./scripts/restore_backup.sh db <dump.sql.gz>` — vérifie le checksum, arrête backend/celery, recrée la base, importe, redémarre. Vérifications post-restauration : `/api/health/`, connexion, un parcours élève.
- **Médias** : `./scripts/restore_backup.sh media <archive.tar.gz>`.
- **Serveur complet** : réinstaller Docker → cloner le dépôt → restaurer `.env.prod` / `.env.jitsi` (depuis le gestionnaire de secrets) → `docker compose up -d` (FEBA puis Jitsi) → restaurer base + médias + volumes Jitsi → re-émettre les certificats (`certbot`) → dérouler la check-list de validation (§11 du guide d'installation).

### Tests de restauration (obligatoires)
Mensuellement : restaurer le dernier dump sur un environnement jetable (`docker compose -f docker-compose.yml`), contrôler le checksum (`sha256sum -c`), dérouler 5 scénarios de la check-list, consigner succès/échec. Une sauvegarde non testée n'est pas une sauvegarde.
