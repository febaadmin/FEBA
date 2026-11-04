# Sauvegardes plugNmeet — incident ERR-310AC0

Date : 04/11/2026. Serveur vidéo `89.167.63.1`. Correctif : PR #69 (commit de fusion sur `main`), script installé le 04/11 à 02:03 UTC.

## 1. Constat

| Élément | Valeur |
|---|---|
| Incident | ERR-310AC0, critique, module « surveillance », 19 occurrences du 03/11 05:00 au 03/11 09:30 UTC |
| Message | « Sauvegarde plugNmeet : aucune réussite depuis plus de 26 h. » |
| Dernière réussite avant correctif | 02/11/2026 02:49:48 UTC (`sauvegarde.txt`) |
| Passage en échec | 03/11/2026 02:44:54 UTC (`systemctl status feba-pnm-sauvegarde.service` : `failed`, code 1) |

Journal systemd du 03/11, extrait :

```
ERROR 2026 (HY000) at line 73: TLS/SSL error: unexpected eof while reading
ÉCHEC : restauration d'essai (0 table(s))
```

L'export de la base avait réussi. C'est la **restauration d'essai** (contrôle intégré au script) qui a échoué, si bien que la sauvegarde n'a pas été déclarée valide et que `sauvegarde.txt` n'a pas été mis à jour.

Pourquoi l'incident a cessé de croître après 09:30 UTC : la surveillance tourne dans Celery, lui-même en panne à partir du 03/11 vers 09:40 UTC (voir `RAPPORT_INCIDENTS_FINAL.md`, panne Celery). L'arrêt du compteur ne signifiait donc pas un retour à la normale.

## 2. Cause racine

L'image `mariadb` démarre d'abord un serveur **temporaire** (sans TCP) pour son initialisation, puis l'arrête avant de lancer le serveur définitif. Le script jugeait le conteneur d'essai prêt dès qu'un `select 1` répondait par le socket local, donc parfois pendant ce serveur temporaire. La restauration commencée à ce moment était coupée lors de son arrêt.

Ce défaut est systémique mais intermittent : le vrai dump est petit (environ 11 Ko compressés) et gagnait la course la plupart des nuits.

### Reproduction (locale, `mariadb:11.4.12`, `--network none`)

| Attente | Essais | Résultat |
|---|---|---|
| `select 1` (ancienne) | 3 | 3 échecs `ERROR 2026 … unexpected eof`, 39/47/62 tables sur 400 |
| `healthcheck.sh --connect --innodb_initialized` (nouvelle) | 3 | 3 réussites, 400/400 tables |

## 3. Correctif (`plugnmeet/ops/sauvegarde_pnm.sh`)

- La restauration attend `healthcheck.sh --connect --innodb_initialized` : le serveur temporaire refuse le TCP.
- Le nombre de tables restaurées est **comparé à celui de la base source**, et non plus au seuil fixe de 4.
- Une seconde tentative est faite sur un conteneur d'essai neuf ; la sauvegarde elle-même n'est jamais refaite.
- La sortie de la restauration va vers la sortie d'erreur et n'est plus capturée dans le comptage.
- Les chemins sont paramétrables (`PNM`, `DB`, `RACINE`) pour le test local. Les valeurs par défaut de production sont inchangées.

Essai local complet sur une maquette : sauvegarde VALIDE, 59/59 tables.

Installation sur le serveur vidéo, le 04/11 à 02:03 UTC :
- ancien script conservé : `sauvegarde_pnm.sh.avant-20261104` ;
- SHA-256 identique entre `main` et le serveur (`d440b565e2cdf4b1…`) ;
- le dépôt du serveur (`/opt/feba/pnm/FEBA`, commit `6e10073`) n'a pas été mis à jour, seul ce fichier l'a été.

## 4. Vérifications réelles (production, autorisées par la mission)

| Contrôle | Résultat |
|---|---|
| Sauvegarde manuelle (`systemctl start feba-pnm-sauvegarde.service`, 02:04 UTC) | VALIDE, `/root/backups/pnm/20261104T020401Z`, 36 Ko, 4/4 tables |
| Intégrité (`sha256sum -c SHA256SUMS`) | `plugnmeet.sql.gz: OK`, `runtime.tgz: OK` |
| Contenu de `runtime.tgz` (noms seulement) | `pnm-web.conf`, `nats-server.conf`, `redis.conf`, `livekit.yaml`, `config.yaml`, `plugnmeet.env`, `certs/` |
| Restauration isolée indépendante (conteneur sans réseau, supprimé ensuite) | lignes identiques à la source : `pnm_room_info` 87/87, `pnm_room_artifacts` 86/86, `pnm_recordings` 0/0, `pnm_room_analytics` 0/0 |
| Date publiée | `sauvegarde.txt` = `2026-11-04T02:04:11Z` |
| Surveillance FEBA (`anomalies()` exécutée en lecture seule en production) | date lue `2026-11-04T02:04:11Z`, anomalies `[]` |
| Conteneurs d'essai restants | aucun |
| Rétention | 14 sauvegardes ; aucune ancienne sauvegarde supprimée (8 présentes) |
| Passage automatique (minuteur systemd, 04/11 02:40 UTC) | VALIDE, `/root/backups/pnm/20261104T024034Z`, 36 Ko, 4/4 tables ; `sauvegarde.txt` = `2026-11-04T02:40:42Z` |

Aucune donnée plugNmeet n'a été modifiée. L'export se fait en lecture (`--single-transaction`).

## 5. Détection d'une future défaillance

- Règle de surveillance (toutes les 15 min) : âge de `sauvegarde.txt` supérieur à 26 h, date illisible ou fichier injoignable, ce qui crée un incident critique. Elle est désormais **testée** (`tests/test_surveillance_sauvegarde.py`, 5 cas, PR #74).
- Les incidents critiques sont désormais visibles : cloche dans l'interface superadmin, et e-mail aux superadmins aux seuils 1, 5, 25… (PR #73). Auparavant, 87 notifications restaient sans lecteur.
- La surveillance dépend de Celery. Le déploiement vérifie maintenant le worker et le planificateur, et la CI démarre un vrai worker (PR #76).

## 6. Limites

- Données de session LiveKit, Redis et NATS : elles sont éphémères (salles en cours) et ne sont pas sauvegardées. C'est volontaire : une restauration repart de salles fermées.
- Fichiers d'enregistrement : 0 enregistrement en base. Aucun fichier n'est donc à sauvegarder aujourd'hui. Si les enregistrements sont activés, leur dossier devra être ajouté au script.
- Les sauvegardes restent sur le serveur vidéo lui-même, sans copie hors site. Une perte du serveur emporterait les sauvegardes : **décision humaine** (stockage externe, coût).
- ERR-310AC0 reste « corrigé, à valider » : la validation humaine reste à faire (§ 7).

## 7. Scénario de validation humaine

1. Le lendemain d'un passage automatique, ouvrir « Incidents techniques » : aucune nouvelle occurrence d'ERR-310AC0.
2. En SSH root sur le serveur vidéo :

   ```
   journalctl -u feba-pnm-sauvegarde.service --since yesterday
   ```

   Le journal doit contenir « Sauvegarde plugNmeet VALIDE ».
3. Vérifier que `https://<serveur vidéo>/assets/feba/sauvegarde.txt` date de moins de 24 h.
