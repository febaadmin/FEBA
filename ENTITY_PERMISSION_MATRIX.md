# Matrice des permissions par entité

## 1. Portée des rôles

| Rôle | Entités visibles | Peut changer d'entité | Peut créer des profils |
|---|---|---|---|
| Super Administrateur | Toutes | **Oui** (endpoint dédié, journalisé) | Dans toute entité |
| Administrateur | La sienne uniquement | **Non** (403) | Dans **sa** entité uniquement |
| Enseignant | La sienne uniquement | Non | Non |
| Parent | La sienne uniquement | Non | Non |
| Élève | La sienne uniquement | Non | Non |
| Compte sans entité (non-superadmin) | Aucune | Non | Non — **aucun jeton délivré** |

## 2. Ce qu'un administrateur ne peut jamais faire

Chaque ligne correspond à un test automatisé de `tests/test_entity_isolation.py`.

| Tentative | Résultat | Test |
|---|---|---|
| Lister les utilisateurs d'une autre entité | Absents de la réponse | `test_feba_admin_sees_no_fha_users` |
| Lister les élèves d'une autre entité | Absents de la réponse | `test_feba_admin_sees_no_fha_students` |
| Lire un élève d'une autre entité par son ID | **403 / 404** | `test_direct_id_access_to_foreign_student_is_refused` |
| Modifier un élève d'une autre entité | **403 / 404**, donnée inchangée | `test_direct_id_update_of_foreign_student_is_refused` |
| Supprimer un élève d'une autre entité | **403 / 404**, objet conservé | `test_direct_id_delete_of_foreign_student_is_refused` |
| Lire un utilisateur d'une autre entité par ID | **403 / 404** | `test_direct_id_access_to_foreign_user_is_refused` |
| Forger `?school_id=<autre entité>` | Paramètre **ignoré** | `test_forged_school_id_query_param_is_ignored_for_admin` |
| Forger `school` / `entity` dans un payload | Déplacement **impossible** | `test_forged_entity_id_in_payload_cannot_move_a_student` |
| Créer un utilisateur dans une autre entité | Refusé, ou créé dans **sa** entité | `test_admin_cannot_create_user_in_another_entity` |
| Changer sa propre entité active | **403** | `test_admin_cannot_switch_entity` |
| Consulter le journal des bascules | **403** | `test_switch_log_reserved_to_superadmin` |

## 3. Fonctionnalités conditionnelles

Vérification **serveur** via `HasEntityFeature`. Le masquage des menus React
n'intervient qu'après, pour le confort.

| Action | Admin FEBA | Admin FEBA FHA | Superadmin (contexte FEBA) |
|---|---|---|---|
| `GET /api/virtual-rooms/` | **403** | 200 | **403** |
| `POST /api/virtual-rooms/` | **403** | autorisé selon rôle | **403** |

Le superadmin **n'échappe pas** à la matrice lorsqu'il a sélectionné une
entité : consulter FEBA, c'est accepter les limites de FEBA. Vérifié en
conditions réelles sur serveur lancé.

## 4. Formulaires publics et boîtes de réception

| Boîte | Admin FEBA | Admin FEBA FHA | Superadmin |
|---|---|---|---|
| Messages de contact FEBA | ✓ | ✗ | selon entité active |
| Messages de contact FEBA FHA | ✗ | ✓ | selon entité active |
| Préinscriptions FEBA | ✓ | ✗ | selon entité active |
| Dossiers d'inscription FEBA FHA | ✗ (404 par ID) | ✓ | selon entité active |

Le superadmin peut filtrer explicitement via `?entity_code=FEBA` ou
`?entity_code=FEBA_FHA`. L'entité de chaque ligne est exposée (`entity_code`)
pour qu'aucune donnée ne soit affichée sans son origine.

## 5. Données sensibles de mineurs

| Donnée | Visibilité |
|---|---|
| Besoins particuliers (`special_needs`) | Administration habilitée **uniquement** (`is_admin_or_above`), y compris sur le détail |
| Photo de l'enfant | Idem — masquée pour tout autre profil |
| Dossiers d'inscription | Jamais exposés par une route publique |
| Liens de visioconférence | Jamais sur une page publique |

Le serializer `FHAApplicationDetailSerializer.to_representation()` blanchit
activement ces champs plutôt que de compter sur le fait que la vue ne soit pas
appelée.

## 6. Consentements

Neuf consentements distincts, chacun **daté** (`consents_accepted_at`) et
**versionné** (`consents_version`).

Obligatoires : règlement, confidentialité, traitement des données, autorisation
parentale. Une soumission sans l'un d'eux est rejetée en `400`, et
**aucune fiche n'est créée**.

Facultatifs et révocables : Zoom, photo/vidéo (distincte, comme exigé),
communications, politique de paiement, engagement annuel.
