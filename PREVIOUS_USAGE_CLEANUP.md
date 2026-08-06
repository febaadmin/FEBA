# PREVIOUS_USAGE_CLEANUP — remise à zéro des données d'usage

**Priorité absolue n°2.** Statut : **livré, 26 tests passants.**

Commande : `python manage.py clean_previous_usage_data`
Fichier : `backend/apps/core/management/commands/clean_previous_usage_data.py`

> **La commande réelle (`--execute`) n'a JAMAIS été exécutée sur des données
> de production pendant cette mission.** Elle n'a tourné que sur des bases de
> test SQLite éphémères, créées et détruites par la suite de tests.

## 1. Ce qui est CONSERVÉ

**Structure** — vérifiée après coup par comparaison d'identifiants :
`School`, `Subject`, `Class`, `Level`.

**Structure préservée sans contrôle d'identifiants** (volume légitimement
variable) : `SchoolBranding`, `SchoolYear`, `RoomType`, `Room`,
`StudentMatriculeSequence`, `DocumentNumberSequence`, `SiteSettings`,
`GalleryAlbum`.

**Comptes** : `superadmin`, `admin`, `teacher` **et `enseignant`** — les deux
orthographes coexistent dans les données historiques, en oublier une
supprimerait des enseignants de façon irréversible.

**Également conservés** : profils enseignants (`Teacher`),
`OrganizationMembership` des comptes conservés, groupes, permissions,
`ContentType`, tables techniques Django, séquences de matricules.

## 2. Ce qui est SUPPRIMÉ

Comptes `student` et `parent` ; profils `Student` et `Parent` ;
`ParentStudent` ; `StudentEnrollment` ; notes et historiques (`Grade`,
`GradeHistory`) ; `Bulletin` ; `Attendance` ; `Payment`, `PaymentHistory` ;
`Conversation`, `Message` ; `Notification`, `EmailDelivery` ;
`Announcement` ; `Homework`, `HomeworkAttachment` ; `GeneratedDocument`,
`DocumentEvent` ; `MonthlyStudentReport`, `MonthlyReportAttempt` ;
`VirtualRoom`, `VirtualRoomAttendance` ; `ContactMessage`,
`PreRegistration`, `FHAEnrollmentApplication` et ses dépendances ;
`EntitySwitchLog` ; `PasswordResetLog` ; `TechnicalIncident` ; `UserFile` ;
`OutstandingToken`, `BlacklistedToken` ; sessions Django (sauf
`--keep-sessions`).

### Point d'attention trouvé pendant le développement

`Student.user` est en `on_delete=SET_NULL`. Supprimer le compte élève ne
supprime donc **pas** son profil : il resterait orphelin avec `user=NULL`.
Le profil `Student` est par conséquent supprimé explicitement, avant les
comptes. `Parent.user` est en `CASCADE` et partirait avec le compte, mais
`Parent` est tout de même listé pour couvrir les profils déjà orphelins.
Ce cas a été révélé par le test n°9 et non par la relecture.

## 3. Options

```
--dry-run                              simulation, aucune écriture
--execute                              suppression réelle
--confirm DELETE-PREVIOUS-USAGE-DATA   obligatoire avec --execute
--academy CODE                         restreint à une académie
--keep-sessions                        conserve les sessions Django
--report-json CHEMIN                   écrit le rapport JSON
```

### Garde-fous

- `--dry-run` et `--execute` sont **exclusifs**, et l'un des deux est
  **requis** : aucune exécution par défaut n'est possible.
- `--execute` sans `--confirm` exact est refusé.
- Un dry-run travaille dans une transaction **systématiquement annulée** :
  il compte les cascades réelles sans en subir les effets.
- Verrou de fichier `flock` : deux exécutions ne peuvent pas se croiser.
- Toute la suppression tient dans un seul `transaction.atomic()`.

## 4. Utilisation

### Simulation (à faire systématiquement d'abord)

```bash
docker compose run --rm backend-dev \
  python manage.py clean_previous_usage_data \
  --dry-run --report-json /app/cleanup_dryrun.json
```

### Exécution réelle

```bash
docker compose run --rm backend-dev \
  python manage.py clean_previous_usage_data \
  --execute --confirm DELETE-PREVIOUS-USAGE-DATA \
  --report-json /app/cleanup_report.json
```

### Une seule académie

```bash
... --execute --confirm DELETE-PREVIOUS-USAGE-DATA --academy FEBA_FHA
```

### Conserver les sessions

```bash
... --execute --confirm DELETE-PREVIOUS-USAGE-DATA --keep-sessions
```

## 5. Vérifications

**Avant** : identifiants et quantités de `School`, `Subject`, `Class`,
`Level` mémorisés ; comptes conservés et supprimés listés ; base cible
affichée **sans mot de passe** ; `DEBUG` affiché ; académies concernées
affichées.

**Après** : identifiants structurels comparés un à un ; comptes protégés
tous présents ; appartenances conservées ; absence de profils orphelins ;
plus aucun compte élève/parent dans le périmètre. **Toute vérification en
échec annule l'intégralité de la transaction** (statut `ROLLED_BACK`), et la
commande sort en erreur.

Les cascades sont auditées avec `django.db.models.deletion.Collector` avant
chaque suppression : si une suppression devait emporter un modèle
structurel, l'anomalie est consignée dans le rapport.

## 6. Rapport JSON

Contient : `counts_before`, `counts_after`, `direct_deletions`,
`cascade_deletions`, `kept_accounts`, `deleted_accounts`,
`academies_processed`, `anomalies`, `media_files`, `database` (sans mot de
passe), `debug`, `keep_sessions`, et `status` valant `SUCCESS` ou
`ROLLED_BACK`.

## 7. Médias

Les fichiers médias rattachés aux enregistrements supprimés sont **recensés
dans tous les modes** mais **effacés du disque uniquement en mode réel** :
un dry-run qui supprimerait des fichiers ne serait pas une simulation.

## 8. Restauration Restic

La commande **ne touche ni à CI/CD, ni à Docker, ni à Restic, ni aux
migrations existantes**. En cas de besoin, la restauration passe par la
procédure Restic déjà documentée dans `RESTORE_GUIDE.md`. **Prendre un
instantané Restic avant toute exécution réelle** : la commande est
transactionnelle, mais une transaction validée n'est plus annulable.

## 9. Limites

- Une `Conversation` n'appartient à aucune académie (elle est définie par ses
  participants, potentiellement de plusieurs académies). En mode `--academy`
  elle est **ignorée** et l'omission est consignée dans `anomalies` plutôt que
  devinée. Elle est bien nettoyée en mode global.
- Le rattachement d'académie des autres modèles suit un chemin d'ORM explicite,
  validé un par un contre les modèles réels.
- La commande est idempotente : une seconde exécution ne change rien et
  n'échoue pas (test n°17).

## 10. Tests — 26 passants

`backend/tests/test_clean_previous_usage_data.py`

Les 20 scénarios demandés sont couverts : dry-run sans écriture ; execute sans
confirmation refusé ; mauvaise confirmation refusée ; académies conservées ;
matières/classes/niveaux conservés ; comptes d'encadrement conservés ; profils
enseignants conservés ; comptes parent/élève supprimés ; profils supprimés ;
liens et inscriptions supprimés ; notes/bulletins/présences/paiements
supprimés ; messages/notifications/documents/formulaires supprimés ;
memberships conservés ; memberships supprimés ; absence d'orphelins ; rollback
sur échec simulé ; idempotence ; filtre `--academy` ; connexion des comptes
conservés (via l'API réelle) ; créations fonctionnelles après nettoyage
(matricule régénéré).

Six tests supplémentaires couvrent : refus si aucun mode, refus si les deux
modes, académie inconnue, complétude du rapport JSON, absence de fuite du mot
de passe de la base, et absence de cascade sur les modèles structurels.
