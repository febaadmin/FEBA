# ACTIONS EXTERNES REQUISES — à faire hors du dépôt

> **EXTERNAL ACTION REQUIRED**
>
> Ce fichier liste ce qui **n'a pas été fait** et **ne pouvait pas l'être**
> depuis le dépôt : créer un serveur chez un hébergeur, écrire un
> enregistrement DNS, ouvrir un port de pare-feu, poser un secret de
> production. Tout le reste — code, configuration, scripts, contrôles — est
> livré et vérifié.
>
> Aucune de ces actions n'est présentée comme accomplie. Chacune est
> accompagnée de la commande qui permet de **vérifier** qu'elle l'est.

---


## 000000000. Audit du 28/10/2026 : bulletin sur une page, dépendances, CI/CD

**Rien n'a été déployé.** L'accès en lecture à la production (SSH Hetzner, sondes du domaine) a été refusé par la politique de permissions de la session. La fusion dans `main` **déclenche automatiquement** le déploiement (`.github/workflows/deploy.yml`) : elle ne doit être faite qu'avec votre accord explicite, après les contrôles ci-dessous.

### Avant la fusion (à faire par l'exploitant, sur le serveur)

1. Version en service : `cd /opt/feba/app/FEBA && git rev-parse HEAD`. L'audit suppose `main` = `d3bc137`.
2. Sauvegarde Restic récente et lisible : `sudo restic snapshots --repo /opt/feba/backups/restic-repository --password-file /root/.feba-restic-password --latest 3`. Le workflow en crée une neuve et vérifie qu'elle existe avant tout changement.
3. Restauration de la base testée sur une copie isolée : `scripts/restore_backup.sh`, voir `RESTORE_GUIDE.md`. **Jamais par-dessus la production.**
4. Comptages de référence, en lecture seule, sur la production : `docker compose --env-file .env.prod -f docker-compose.prod.yml exec -T backend-prod python manage.py shell < scripts/audit/data_counts.py > /root/counts_avant.txt`.
5. Secret Jitsi : `JITSI_APP_SECRET` d'au moins 32 caractères, si la visio Jitsi est utilisée (HMAC-SHA256, RFC 7518).

### Recommandé dans GitHub (réglages du dépôt, à faire par un administrateur)

- Protéger `main` : pull request obligatoire, contrôles « CI » exigés (Backend, Frontend, Sécurité des dépendances, Images Docker, Configuration).
- Créer un environnement GitHub `production` avec approbation requise, et y rattacher le job `deploy`. Aujourd'hui, toute fusion déploie sans validation humaine.
- Remplacer `ssh-keyscan` (confiance au premier contact) par une empreinte d'hôte enregistrée en secret (`SERVER_KNOWN_HOSTS`).
- Le dépôt est **public** : vérifier que c'est voulu.

### Migrations de cette version (depuis `main`)

96 migrations, aucune destructive (pas de `RemoveField`, `DeleteModel`, `RunSQL`). Elles ont été appliquées sur une copie peuplée par `main` : effectifs, empreintes des identifiants et sommes (notes, paiements) sont identiques avant et après (`scripts/audit/data_counts.py`).

### Retour arrière sans restauration de la base

Les migrations sont **compatibles avec l'ancien code**. Les colonnes NOT NULL ajoutées ont une valeur par défaut en base (migrations `notifications 0008`, `payments 0015`, `website 0013`). Avec le code `main` sur le schéma migré, la création d'élève, de note, de paiement, de matière et d'école a été vérifiée (`scripts/audit/rollback_columns_check.py` → `RISKY []`).

Procédure :
1. `cd /opt/feba/app/FEBA && git reset --hard "$(cat .previous_deploy_sha)"` : le commit précédent est enregistré par le workflow à chaque déploiement.
2. `docker compose --env-file .env.prod -f docker-compose.prod.yml up -d --build --remove-orphans`.
3. `curl -fsS https://globalfeba.com/api/health/`.

Ne **pas** défaire les migrations (`migrate <app> <précédente>`) sans analyse : les données saisies depuis le déploiement seraient perdues dans les colonnes retirées. La restauration Restic est le **dernier recours**, et seulement avec votre autorisation, car elle remplace les données saisies depuis la sauvegarde.

## 00000000. Programme linguistique des académies, identités dynamiques (27/10/2026)

Rien n'a été déployé ni migré en production (SSH Hetzner refusé). Toutes les validations sont locales, y compris une montée de version sur une pile de production locale construite **depuis l'archive** (voir `TEST_REPORT.md`).

À faire, dans cet ordre, **après la sauvegarde** que `scripts/deploy_feba.sh` réalise et vérifie lui-même :

1. **Déployer**. La migration `schools.0021_curriculum_language_mode` ajoute la colonne et classe chaque académie d'après ses matières et ses classes. Rien d'autre n'est modifié et aucune donnée n'est supprimée.
2. `docker exec feba_backend python manage.py init_academies` : FEBA et FEBA FHA reçoivent « Bilingue français-anglais » **seulement si** leur programme est encore vide. C'est leur fonctionnement actuel (bulletins à deux sections, 60/40, classes monolingues de FEBA FHA).
3. `docker exec feba_backend python manage.py academy_languages_report` : chaque académie restée « À configurer » est listée avec le motif et une proposition. Le super administrateur choisit son programme dans « Académies » → modifier. Le diagnostic s'affiche avant tout enregistrement.
4. Facultatif : `PUBLIC_SITE_ONLINE_ACADEMY_CODE` (défaut `FEBA_FHA`) et `PUBLIC_SITE_CAMPUS_ACADEMY_CODE` (défaut `FEBA`) dans `.env.prod`. Ces réglages ne changent qu'en cas de rattachement du site public à une autre académie.
5. Vérifier dans l'application, avec un compte administrateur de chaque académie :
   - l'en-tête porte le nom de l'académie ;
   - « Admissions en ligne » et « Rapports mensuels » n'apparaissent que pour FEBA FHA ;
   - « Préinscriptions du site » n'apparaît que pour FEBA ;
   - l'emploi du temps n'a qu'un onglet, au nom de l'académie.

Retour arrière : `scripts/deploy_feba.sh --rollback`. La migration se défait (`migrate schools 0020`) sans perte : seule la colonne disparaît.

## 0000000. Gabarits multiformats : Word, OpenDocument, RTF, PowerPoint, TIFF, WEBP (27/10/2026)

Rien n'a été déployé ni migré en production. Validations en local, y compris dans l'image Docker de
production construite **depuis l'archive livrée** (voir `TEST_REPORT.md`).

1. **Faire une sauvegarde vérifiée**, puis lancer `make prod` (ou `scripts/deploy_feba.sh`). Cela :
   - reconstruit l'image backend, qui installe **LibreOffice sans interface** et les polices compatibles Microsoft. L'image grossit d'environ 450 Mo ; la construction dure quelques minutes de plus ;
   - installe une nouvelle dépendance Python, `olefile==0.47` ;
   - applique la migration `documents.0003_template_conversion` : trois colonnes ajoutées. Les versions existantes reçoivent leur format d'origine (pdf, png, jpeg), rien d'autre ne change.
2. **Réglages facultatifs** (`.env.prod`) : `DOCUMENT_CONVERSION_TIMEOUT` (90 s par défaut) et `LIBREOFFICE_BINARY` (détecté automatiquement).
3. **Vérifier après déploiement** :

   ```
   docker compose --env-file .env.prod -f docker-compose.prod.yml exec backend-prod soffice --version
   ```

   Puis, dans « Gabarits des documents », le bandeau des formats acceptés doit lister Word, OpenDocument, RTF et PowerPoint.
4. **Construire l'image depuis un dépôt propre** (git archive ou ZIP livré). Un fichier `.dockerignore` (nouveau) empêche désormais que `media/` et `private_media/` d'un poste soient copiés dans l'image.
5. **Retour arrière** : `make prod-rollback`, puis `migrate documents 0002`. Les gabarits téléversés en format bureautique restent sur le disque, mais l'ancienne version ne sait pas les relire : désactivez-les avant de revenir en arrière.

## 000000. Gabarits officiels des diplômes et certificats (26/10/2026)

Rien n'a été déployé ni migré en production. Validations : en local (voir
`TEST_REPORT.md`), y compris dans l'image Docker de production.

1. **Sauvegarde vérifiée**, puis `make prod` (ou `scripts/deploy_feba.sh`) :
   - l'image backend installe deux nouvelles dépendances Python (roues
     autonomes, aucun paquet système) : `pypdf==6.14.2`, `pypdfium2==4.30.0` ;
   - migration `documents.0002_academy_document_templates` : deux tables
     (gabarits versionnés, journal) et une colonne facultative sur les
     documents ; aucune donnée existante modifiée.
2. **Sauvegardes** : remplacer la tâche cron par le script livré —
   `scripts/backup_files.sh` archive désormais `media/` ET `private_media/`
   (diplômes délivrés, gabarits, dossiers FHA, rapports mensuels). L'ancien
   script n'archivait que `media/`. Vérifier une archive :
   `tar tzf /backups/feba/daily/feba_media_$(date +%F).tar.gz | grep -c '^private_media/'`.
   Autres défauts corrigés dans ces scripts, constatés en les EXÉCUTANT
   contre la pile de production locale :
   - ils visaient les services « backend » / « postgres » et la base
     « feba », absents de `docker-compose.prod.yml` (les tâches cron
     documentées échouaient donc à chaque exécution) — désormais
     `backend-prod`, `postgres-prod`, `feba_user`/`feba_prod`, et
     `--env-file .env.prod` ;
   - ils s'arrêtaient avant la copie hors site tant que les dossiers
     hebdomadaire / mensuel étaient vides ;
   - la restauration des fichiers échouait (« Device or resource busy » :
     les répertoires sont des volumes) et celle de la base aussi
     (`DROP DATABASE` dans un bloc transactionnel), en laissant le backend
     arrêté.
   À faire : vérifier `/var/log/feba-backup.log` (lignes « terminée » et
   « copie distante ») après la première nuit, puis un essai de
   restauration sur un serveur de test (`RESTORE_GUIDE.md`).
3. **Gabarits** : chaque académie téléverse ses fonds dans « Gabarits des
   documents » (`DOCUMENT_TEMPLATES_GUIDE.md`). FEBA et FEBA FHA gardent
   leurs gabarits intégrés tant qu'aucun gabarit téléversé n'est activé.
4. **nginx** : `client_max_body_size 25M` (déjà en place) couvre la limite de
   10 Mo des gabarits ; rien à changer.
5. Retour arrière : `make prod-rollback` puis `migrate documents 0001`
   (supprime les gabarits téléversés et le lien des documents vers leur
   version ; les PDF déjà délivrés restent sur le disque — sauvegarde).

## 00000. Académies typées, fiche FHA (sexe), appréciations (26/10/2026)

Rien n'a été déployé ni migré en production. Validations : en local.

1. **Sauvegarde vérifiée**, puis `make prod` (ou `scripts/deploy_feba.sh`),
   qui applique trois migrations, toutes sans suppression de données :
   - `website.0012_fha_child_gender` : champ « sexe » de la fiche FHA ; les
     dossiers déjà reçus restent VIDES (« Non renseigné ») — rien n'est
     deviné ;
   - `schools.0020_academy_type` : type d'académie, déduit des données
     (académie en ligne → « en ligne » ; niveaux uniquement maternelle /
     primaire → « physique primaire » ; uniquement collège / lycée →
     « physique secondaire »). Une académie qui mêle primaire et secondaire,
     ou sans niveau, reste **non classée** ;
   - `grades.0013_appreciation_rules` : COPIE, dans chaque académie, du
     barème d'appréciations en vigueur (mêmes seuils, mêmes libellés :
     aucun bulletin ne change).
2. **Classement des académies** : `python manage.py academy_types_report`
   (lecture seule) liste chaque académie et, pour une académie non classée,
   le motif et une proposition. Le classement se fait dans « Académies »
   (super administrateur) ; il est refusé tant que des niveaux le
   contredisent (la liste des niveaux en cause est affichée). Une académie
   non classée fonctionne exactement comme avant.
3. **Vérifier les cycles des niveaux** (écran « Niveaux », colonne « Cycle ·
   barème ») : l'ancien écran ne proposait pas le cycle, tout niveau créé
   depuis l'interface était donc « primaire » (bulletin sur 10). Corriger
   en « Collège » ou « Lycée » les niveaux du secondaire (bulletin sur 20).
4. **Appréciations** : écran « Appréciations » de chaque académie ; le
   barème copié est identique à l'ancien. Le modifier ne change pas les
   bulletins déjà émis.
5. **Nouvelle académie** : voir `ACADEMIES_GUIDE.md` (création, puis liste
   « Configuration restante » : année, matières, classes, administrateur,
   logo). Diplômes et certificats : voir § 000000 (gabarits téléversés).
6. Retour arrière : `make prod-rollback` ; `migrate grades 0012`,
   `migrate schools 0019`, `migrate website 0011` retirent les ajouts (le
   sexe saisi sur les nouvelles fiches et les barèmes d'appréciations
   modifiés seraient alors perdus — sauvegarde ; aller-retour vérifié en local).

## 0000. Aperçu des bulletins, logo, favicons, onglets de visio (26/10/2026)

Rien n'a été déployé ni migré en production.

1. Sauvegarde vérifiée, puis `make prod` : applique `schools.0018`
   (une seule version de logo active par académie ; s'il y en avait
   plusieurs, la plus récente reste active — aucune suppression) et
   `schools.0019` (retire des réglages le logo de repli recopié par
   `init_academies` — `logo_feba.jpeg` — pour que le logo fourni devienne le
   repli de FEBA ; valeurs conservées, migration réversible).
2. **Vérifier le logo actif de chaque académie** (page « Branding &
   Logo », académie sélectionnée) : sur la pile de test, le logo FEBA avait
   été posé par erreur sur FEBA FHA (ancien repli « académie 1 »). En
   production, contrôler `GET /api/schools/public-branding/FEBA/` et
   `/FEBA_FHA/` ; corriger en activant la bonne version dans chaque académie.
3. Documents courants : `python manage.py branding_refresh_documents
   --academy FEBA` (aperçu), puis `--apply` ; idem `--academy FEBA_FHA`.
4. Client plugNmeet : `bash scripts/plugnmeet_setup.sh --domain <domaine>
   --public-ip <IP> --feba-url https://globalfeba.com` (idempotent ; secrets
   conservés ; redémarre le serveur plugNmeet). Vérifier dans un onglet de
   réunion : « FEBA - Faith & Excellence Bilingual Academy » / « FEBA FHA -
   FEBA ».
5. Retour arrière : `make prod-rollback` ; `migrate schools 0017` retire la
   contrainte (aucune donnée perdue).

## 000. Commentaires des bulletins et visio multi-académies (26/10/2026)

Rien n'a été déployé ni migré en production. Ordre conseillé :

1. Sauvegarde vérifiée de la base (`deploy_feba.sh` en fait une à chaque
   déploiement) ; vérifier l'identité du serveur.
2. `make prod` — applique deux migrations :
   - `bulletins.0006_comments_operations` : additive (deux colonnes
     nullables, une table) ;
   - `schools.0017_enable_video_for_all_academies` : active la visio pour
     toutes les académies, FEBA comprise ; les valeurs d'origine sont
     conservées dans `settings.features_before_0017`.
3. Le worker Celery doit tourner (il exécute les opérations groupées sur
   les bulletins) : `deploy_feba.sh` vérifie déjà qu'il répond.
4. Contrôle : un administrateur FEBA ouvre « Salles virtuelles », crée une
   salle, la rejoint avec un enseignant et un élève ; puis, dans
   « Bulletins », ajoute un commentaire à un élève et ouvre le PDF.
5. Retour arrière : `make prod-rollback` (images précédentes). Les
   migrations peuvent être défaites :
   `python manage.py migrate schools 0016` puis
   `python manage.py migrate bulletins 0005` (supprime l'historique des
   opérations et les dates de modification des commentaires ; les
   commentaires eux-mêmes restent).

## 00. Version finale validée (25/10/2026) — à faire par l'exploitant

Rien de ce qui suit n'a été exécuté sur le serveur de production (accès
SSH refusé, et déploiement direct interdit par la mission). Aucune
migration nouvelle depuis la version plugNmeet/SMS.

1. **Sur le serveur, AVANT tout déploiement** : vérifier l'identité de la
   machine (`hostname`, `ip -4 addr`, `docker ps`) et faire une sauvegarde
   vérifiée de la base (`RESTORE_GUIDE.md`). `deploy_feba.sh` en refait
   une, contrôlée (`gzip -t`), à chaque déploiement.
2. **`.env.prod`** à partir de `.env.prod.example`, `chmod 600`. Ajouter
   les nouvelles variables `DEPLOYMENT_STAGE=production` et
   `PUBLIC_BASE_URL=https://globalfeba.com`. Puis :
   `make prod-preflight` — il doit afficher 0 erreur. Le backend, le
   worker et Beat **refusent de démarrer** sinon (secret faible, DEBUG,
   SMTP de test, plugNmeet ou SMS incomplet…).
3. **Certificat** : `bash scripts/tls_bootstrap.sh` (une fois ; passe le
   renouvellement en mode webroot et teste `renew --dry-run`).
4. **Déploiement** : `make prod` (= `scripts/deploy_feba.sh`). Le script
   construit, contrôle l'image candidate, sauvegarde, étiquette l'image
   précédente `previous`, démarre, vérifie (santé HTTPS, page d'accueil,
   401 sans jeton, configuration identique backend/worker/Beat, ping
   Celery) et **revient automatiquement** à la version précédente en cas
   d'échec. Retour manuel : `make prod-rollback`.
5. **Recette plugNmeet en production** avant de désactiver Jitsi
   (`PLUGNMEET_DEPLOYMENT_GUIDE.md` §§ 6-7) : 1 enseignant + 2 élèves sur
   des réseaux différents, partage d'écran compris. Ne basculer
   `VIDEO_PROVIDER=plugnmeet` et le DNS qu'après cette recette.
6. **SMTP réel et SMS réel** : actions du § 0 ci-dessous, un seul
   destinataire de test à chaque fois (jamais d'envoi groupé de test).

## 0. Version plugNmeet / SMS / expéditeur (25/10/2026) — actions hors dépôt

Ordre conseillé ; chaque étape est réversible et n'arrête pas Jitsi.

1. **E-mail** — chez Hostinger : boîte `noreply@globalfeba.com`, DKIM actif.
   `.env.prod` : bloc SMTP de `.env.prod.example`. Puis
   `manage.py check` (aucun `notifications.W00x`) et
   `manage.py email_check --to <votre adresse>` ; lire les en-têtes reçus.
2. **SMS** — compte Twilio propriétaire du +1 215 715 5406, Geo permissions
   (Bénin), A2P 10DLC si destinataires américains. `.env.prod` : bloc SMS
   (`SMS_ENABLED=False`), `manage.py sms_check`, puis `sms_check --to
   <votre numéro>`, puis `SMS_ENABLED=True`. Recueillir les consentements
   (Mon profil) ou décision juridique sur `SMS_REQUIRE_EXPLICIT_CONSENT`.
3. **plugNmeet** — `PLUGNMEET_DEPLOYMENT_GUIDE.md` §§ 1-7 (serveur, DNS
   `pnm.globalfeba.com`, pare-feu Hetzner Cloud, certificat, recette, bascule).
4. **Migrations FEBA** (additives) : `manage.py migrate` — accounts 0007,
   notifications 0007, payments 0014, virtualclass 0004. Sauvegarde de la
   base AVANT (`RESTORE_GUIDE.md`).

## État constaté au moment de la livraison

Mesuré, pas supposé :

| Vérification | Commande | Résultat observé |
|---|---|---|
| `globalfeba.com` résout | `getent hosts globalfeba.com` | ✅ `62.238.38.111` |
| Le site répond en HTTPS | `curl -o /dev/null -w '%{http_code}' https://globalfeba.com/` | ✅ `200` |
| L'API répond | `curl -o /dev/null -w '%{http_code}' https://globalfeba.com/api/health/` | ✅ `200` |
| **`meet.globalfeba.com` résout** | `getent hosts meet.globalfeba.com` | ❌ **aucun enregistrement** |

La visioconférence est donc **indisponible en production**, et c'est
exactement ce que l'application affiche. Ce n'est pas un défaut logiciel :
il manque l'infrastructure décrite ci-dessous.

> **Défaut de configuration constaté sur le site en ligne.**
> Toute URL statique inexistante renvoie aujourd'hui `HTTP 200` avec la
> page HTML de l'application, au lieu d'un `404` :
> ```
> curl -sSI https://globalfeba.com/images/feba-fha/definitely-not-here.pdf
> → HTTP/2 200 ; content-type: text/html
> ```
> Un fichier manquant passe donc pour un fichier servi. Les règles Nginx
> livrées corrigent ce point pour le flyer (`try_files $uri =404`) ; le
> déploiement de `nginx/nginx.prod.conf` et `frontend/nginx.prod.conf` est
> ce qui rendra la correction effective.

---

## ACTION EXTERNE 01 — Serveur Jitsi (Hetzner)

**Service :** Hetzner Cloud
**Pourquoi :** l'instance de visioconférence doit être auto-hébergée. Le
backend **refuse** `meet.jit.si` (`JITSI_FORBIDDEN_DOMAINS`) : les cours
concernent des mineurs, et un flux qui transite chez un tiers sans
authentification n'est pas une option de repli.

| Paramètre | Valeur |
|---|---|
| Type | **CPX32** — 4 vCPU, 8 Go RAM, 160 Go SSD |
| Image | Ubuntu 24.04 LTS (ou 26.04) |
| Localisation | au choix ; **Helsinki** ou **Nuremberg** conviennent |
| Réseau | IPv4 publique **obligatoire** (le pont vidéo l'annonce aux navigateurs) |
| Nom suggéré | `feba-jitsi` |

Un CPX32 dimensionne confortablement des groupes de 10 à 15 élèves, la
taille annoncée sur le flyer FEBA FHA.

**Vérification**
```bash
ssh root@<IP_JITSI> 'docker --version && free -g'
```

---

## ACTION EXTERNE 02 — Enregistrement DNS (Hostinger)

**Service :** Hostinger — zone DNS de `globalfeba.com`

| Champ | Valeur |
|---|---|
| Type | `A` |
| Nom / Host | `meet` |
| Valeur | `<IP_PUBLIQUE_DU_SERVEUR_JITSI>` (action 01) |
| TTL | `3600` (300 pendant la mise en place, pour itérer vite) |
| Proxy | **aucun** — le trafic WebRTC ne doit pas être intermédié |

> Ne pas créer d'enregistrement `AAAA` tant que la pile n'est pas démarrée
> avec `ENABLE_IPV6=1` : un `AAAA` qui pointe une pile sans IPv6 fait
> échouer un navigateur sur deux, de façon intermittente — la panne la plus
> longue à diagnostiquer de cette liste.

**Vérification**
```bash
dig +short meet.globalfeba.com          # doit renvoyer l'IP de l'action 01
getent hosts meet.globalfeba.com
```

---

## ACTION EXTERNE 03 — Pare-feu Hetzner

**Service :** Hetzner Cloud → Firewalls, appliqué au serveur `feba-jitsi`.

| # | Protocole | Port | Source | Raison |
|---|---|---|---|---|
| 1 | TCP | `80` | `0.0.0.0/0`, `::/0` | Validation HTTP-01 de Let's Encrypt **et** redirection vers HTTPS. Sans ce port, la délivrance du certificat échoue et le conteneur redémarre en boucle. |
| 2 | TCP | `443` | `0.0.0.0/0`, `::/0` | Interface Jitsi et signalisation (BOSH / WebSocket). |
| 3 | **UDP** | `10000` | `0.0.0.0/0`, `::/0` | **Jitsi Videobridge — flux audio et vidéo.** Fermé, tout le monde se connecte, se voit dans la liste des participants, et **personne n'entend rien**. |
| 4 | TCP | `22` | **IP d'administration uniquement** | SSH. Ne pas ouvrir à `0.0.0.0/0`. |

**Vérification**
```bash
nc -z -w5 meet.globalfeba.com 443 && echo "443 ouvert"
nc -u -z -w5 meet.globalfeba.com 10000 && echo "10000/udp ouvert"
```

---

## ACTION EXTERNE 04 — Secrets de production

**Où :** sur le serveur, dans `.env.jitsi` et `.env.prod`. **Jamais dans Git.**

Les deux fichiers doivent porter **les mêmes valeurs** : c'est le secret
partagé qui fait qu'aucune salle ne s'ouvre sans une autorisation vérifiée
par Django. Un écart et chaque « Rejoindre » est refusé par Prosody, sans
message côté FEBA — la panne la plus déroutante de cette liste.

```bash
JITSI_APP_ID="feba_$(openssl rand -hex 6)"
JITSI_APP_SECRET="$(openssl rand -hex 32)"

# .env.jitsi (serveur Jitsi)          # .env.prod (serveur applicatif)
JITSI_APP_ID=$JITSI_APP_ID            JITSI_APP_ID=$JITSI_APP_ID
JITSI_APP_SECRET=$JITSI_APP_SECRET    JITSI_APP_SECRET=$JITSI_APP_SECRET
JITSI_DOMAIN=meet.globalfeba.com      JITSI_DOMAIN=meet.globalfeba.com
JITSI_PUBLIC_URL=https://meet.globalfeba.com
JVB_ADVERTISE_IPS=<IP_JITSI>          # action 01
LETSENCRYPT_EMAIL=<adresse réelle>
```

`JVB_ADVERTISE_IPS` et `LETSENCRYPT_EMAIL` n'ont **pas** de valeur par
défaut : `docker-compose.jitsi.prod.yml` refuse de démarrer sans elles,
plutôt que de démarrer une instance muette ou sans TLS.

**Vérification**
```bash
make jitsi-config-check     # cohérence des deux fichiers, sans réseau
```

---

## ACTION EXTERNE 05 — Démarrage de l'instance

```bash
# Sur le serveur Jitsi, dans le dépôt :
make jitsi-prod-up
# équivaut à :
#   docker compose -f docker-compose.jitsi.yml \
#                  -f docker-compose.jitsi.prod.yml \
#                  --env-file .env.jitsi up -d
```

**Vérification — depuis n'importe quelle machine :**
```bash
make jitsi-health JITSI_TARGET=meet.globalfeba.com
```

Le rapport nomme chaque contrôle séparément (configuration, domaine non
public, signature de jeton, DNS, TLS, HTTP, page Jitsi). Il doit finir par
`État : OPÉRATIONNEL`. Tant que l'action 02 n'est pas faite, il affiche
aujourd'hui :

```
 ÉCHEC  dns   Le domaine « meet.globalfeba.com » ne résout pas […].
               Créez l'enregistrement DNS A vers l'IP du serveur Jitsi
               (voir MANUAL_PRODUCTION_ACTIONS.md).
```

---

## ACTION EXTERNE 06 — Déploiement de l'application corrigée

Les correctifs P1 (numéro institutionnel) et P2 (flyer) sont dans le code ;
ils ne prennent effet qu'une fois déployés sur `globalfeba.com`.

```bash
git pull
docker compose -f docker-compose.prod.yml build frontend-prod backend-prod
docker compose -f docker-compose.prod.yml up -d
docker compose -f docker-compose.prod.yml exec backend-prod \
    python manage.py migrate          # applique schools.0015
docker compose -f docker-compose.prod.yml exec backend-prod \
    python manage.py init_academies   # aligne la colonne de gestion
docker compose -f docker-compose.prod.yml restart nginx-prod
```

`schools.0015_retire_legacy_institutional_phone` retire de la base le
numéro hors service. Ce n'est pas ce qui corrige les documents — ils ne
lisent plus cette colonne — mais l'écran « Paramètres » l'affiche encore.

**Vérification**
```bash
# Le flyer est servi en pièce jointe, et non en HTML :
curl -sSI https://globalfeba.com/images/feba-fha/feba-fha-flyer.pdf \
  | grep -iE 'HTTP|content-type|content-disposition'
# attendu : 200 · application/pdf · attachment; filename="FEBA-French-Heritage-Academy-flyer.pdf"

# Un fichier absent doit désormais répondre 404, et non 200 :
curl -sS -o /dev/null -w '%{http_code}\n' \
  https://globalfeba.com/images/feba-fha/definitely-not-here.pdf
# attendu : 404
```

Puis, dans l'application : générer un reçu et vérifier qu'il porte
`0160011717`.

---

## Récapitulatif

| # | Action | Prestataire | Faite ? |
|---|---|---|---|
| 01 | Serveur CPX32 | Hetzner | ⬜ **EXTERNAL ACTION REQUIRED** |
| 02 | DNS `A meet` | Hostinger | ⬜ **EXTERNAL ACTION REQUIRED** |
| 03 | Pare-feu 80/443 TCP + 10000 UDP | Hetzner | ⬜ **EXTERNAL ACTION REQUIRED** |
| 04 | Secrets JWT partagés | Serveur | ⬜ **EXTERNAL ACTION REQUIRED** |
| 05 | Démarrage de la pile | Serveur | ⬜ **EXTERNAL ACTION REQUIRED** |
| 06 | Déploiement de l'application corrigée | Serveur | ⬜ **EXTERNAL ACTION REQUIRED** |

Aucune de ces cases n'est cochée. Aucune ne peut l'être depuis ce dépôt.
