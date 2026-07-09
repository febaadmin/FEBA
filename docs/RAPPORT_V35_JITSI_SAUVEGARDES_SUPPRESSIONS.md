# FEBA v35 — Rapport : suppression par année (vidéos), Jitsi auto-hébergé JWT, sauvegardes, sécurité/RGPD

Date : 07/07/2026 · Base : v34 · Diagnostic depuis vos 2 enregistrements d'écran + capture Jitsi (bandeau « meet.jit.si — 5 minutes »).

---

## 1. Bug des vidéos : la suppression en masse vidait TOUTES les années

**Diagnostic (images extraites de vos enregistrements)** : vidéo 1 — page Élèves, année 2024-2025, sélection des 30 élèves via la case d'en-tête → « Supprimer (30) » → liste vidée ; vidéo 2 — bascule sur 2025-2026 puis « Toutes » : plus aucun élève nulle part.
**Cause racine** : la suppression en masse opérait sur **l'identité globale** de l'élève (destruction en v33, désactivation globale en v34) alors que, dans un contexte « année sélectionnée », l'utilisateur exprime « retirer ces élèves de CETTE année ».
**Correction (comportement par défaut conforme à la mission)** :
- Nouveau endpoint `POST /students/bulk-remove-from-year/` (ids + année) : supprime **uniquement les inscriptions de l'année indiquée**, élève par élève, avec repositionnement du pointeur « année courante » sur l'inscription restante la plus récente. Les autres années sont strictement intactes ; aucun élève n'est désactivé ni détruit.
- Frontend : quand une année précise est affichée, le bouton devient **« Retirer de {année} »** et la confirmation explicite précise « leurs autres années restent intactes » ; depuis « Toutes », l'action est une **désactivation** (réversible) clairement libellée — jamais destructive. La sélection est réinitialisée après l'action.
- 2 tests rejouent exactement le scénario de vos vidéos : retrait de tous les élèves d'une année → l'autre année conserve 100 % de ses inscriptions ; retrait de l'année « pointée » → repositionnement automatique.

## 2. Jitsi professionnel — instance auto-hébergée, service indépendant, JWT (Partie 4)

Votre capture montre le bandeau meet.jit.si « appel limité à 5 minutes » : proscrit en production, comme l'exige la mission.
- **Pile indépendante** `docker-compose.jitsi.yml` (images officielles : jitsi-web, prosody, jicofo, jvb) — jamais mélangée à Django, réseau Docker séparé, `.env.jitsi.example` fourni (tous les secrets via `openssl rand -hex 32`). Démarrage local en 2 commandes (test caméra/micro/écran/JWT/permissions) ; production sur domaine dédié (procédure §9 du guide de déploiement : DNS, TLS, UDP 10000, `JVB_ADVERTISE_IPS`, TURN si nécessaire).
- **Authentification JWT** : `apps/virtualclass/services.py` émet des jetons HS256 conformes au format Jitsi (`iss`=APP_ID, `aud`=jitsi, `room`, `context.user`, `moderator`), signés avec `JITSI_APP_SECRET` partagé — flux exigé : utilisateur FEBA → connexion Django → vérification des permissions (visibilité tenant + rôle) → jeton → accès Jitsi. **Aucun accès direct non autorisé** : Prosody est configuré `AUTH_TYPE=jwt, ENABLE_GUESTS=0`. Enseignants/admins = modérateurs ; expiration 3 h ; sans configuration, repli explicite en mode démo (jamais en production).
- **Présence liée à l'inscription annuelle** (modèle exigé `VirtualAttendance`) : `VirtualRoomAttendance` porte désormais `enrollment` (FK vers l'inscription annuelle de l'élève, migration `virtualclass/0002`), `left_at` et `duration_seconds` ; `join/` lie automatiquement l'inscription de l'année de la salle et renvoie le JWT ; nouveau `leave/` (appelé automatiquement à la fermeture de la réunion côté frontend) horodate la sortie et calcule la durée. Le modèle `VirtualRoom` portait déjà `school_year`, `class_obj`, `subject`, `room_identifier` (room_code), `status` — une salle dépend bien d'une année.
- Frontend : le composant Jitsi transmet le `jwt` à l'iframe ; PyJWT épinglé dans `requirements/base.txt`.

## 3. Sauvegardes professionnelles (Partie 7)

Quatre scripts exécutables dans `scripts/` — `backup_database.sh` (dump PostgreSQL complet), `backup_files.sh` (médias : photos, documents, bulletins, reçus), `backup_jitsi.sh` (volumes web/prosody-JWT/jicofo/jvb + `.env.jitsi`), `restore_backup.sh` (base et médias) — avec : **checksum SHA-256** systématique, **rotation automatique 7 quotidiennes / 4 hebdomadaires / 12 mensuelles**, **copie hors site** via `RCLONE_REMOTE` (S3 compatible / NAS / serveur secondaire — jamais uniquement sur le serveur principal), lignes cron prêtes (02h00 chaque nuit), restauration avec vérification du checksum, confirmation explicite, arrêt/redémarrage propres des services. Procédures complètes (dont **reconstruction de serveur** et **tests de restauration mensuels**) : `docs/SECURITE_RGPD_DISASTER_RECOVERY.md` + §7 du guide de production.

## 4. Sécurité & RGPD (Parties 5–6)

Document dédié `docs/SECURITE_RGPD_DISASTER_RECOVERY.md` : synthèse d'audit sécurité (JWT rotation+blacklist, rôles hiérarchisés testés anti-escalade, isolation multi-tenant testée, HTTPS/HSTS en prod, ports internes non exposés, **aucun secret dans le code** — uniquement variables d'environnement, `settings/prod.py` refuse de démarrer sans SECRET_KEY) ; cartographie RGPD des données (élèves, parents, personnels, journaux ; aucun enregistrement vidéo par défaut) et mise en œuvre des droits — accès/portabilité (exports + dossier annuel), rectification, **effacement gradué** (retrait d'année / désactivation réversible / définitif gardé par dépendances), limitation de conservation bornée par la rotation des sauvegardes, journalisation immuable (GradeHistory, PaymentHistory). L'auto-hébergement Jitsi supprime tout transfert de flux vers un tiers.

## 5. Vérifications (boucle)

Backend compilé intégralement ; graphe de migrations intègre (nouvelle migration `virtualclass/0002` additive) ; 4 scripts shell validés (`bash -n`) ; YAML Jitsi validé ; 78 fichiers frontend sans erreur de syntaxe ; imports et appels API tous valides. **5 nouveaux tests** (`test_bulk_year_and_jitsi.py`) : bulk par année n'affectant pas les autres années (scénario exact des vidéos), repositionnement du pointeur, payload JWT conforme (décodé et vérifié), présence liée à l'inscription + leave/durée, absence de jeton hors configuration. Check-list du guide portée à **33 scénarios**. À exécuter chez vous : `docker compose up --build -d && make seed && make test`, plus la pile Jitsi locale (guide §7.1) pour la validation caméra/micro/JWT.

## 6. Fichiers créés / modifiés

| Élément | Nature |
|---|---|
| `docker-compose.jitsi.yml` + `.env.jitsi.example` | Pile Jitsi indépendante avec JWT |
| `backend/apps/virtualclass/{services,views,models}.py` + migration `0002` | JWT signés, présence liée à l'inscription, leave/durée |
| `backend/apps/students/views.py` | `bulk-remove-from-year` (bug des vidéos) |
| `frontend` (Students, DataTable, VirtualRooms, JitsiMeeting, api) | Suppression en masse par année + libellés explicites ; jwt à l'iframe ; leave auto |
| `scripts/backup_{database,files,jitsi}.sh`, `scripts/restore_backup.sh` | Sauvegardes 7/4/12 + checksum + hors-site ; restauration |
| `docs/SECURITE_RGPD_DISASTER_RECOVERY.md` | Sécurité, RGPD, reprise d'activité |
| `backend/tests/test_bulk_year_and_jitsi.py` | 5 tests de régression |
| Guides PDF | Jitsi auto-hébergé (local §7.1, prod §9), sauvegardes/restauration §7, 33 scénarios |
