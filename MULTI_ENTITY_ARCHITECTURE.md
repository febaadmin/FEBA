# Architecture multi-entités FEBA / FEBA French Heritage Academy

Version 4 — plateforme unique hébergeant deux entités distinctes.

## 1. Décision d'architecture

### 1.1 Le socle existait déjà

L'application V3 était **déjà multi-tenant** : `schools.School` jouait le rôle
de racine d'isolation, `CustomUser.school` portait le rattachement, et
`apps/core/tenancy.py` appliquait le filtrage au niveau des ViewSets DRF.

Le choix a donc été d'**étendre ce socle éprouvé** plutôt que d'introduire un
modèle `Organization` parallèle. Créer une seconde notion d'entité à côté de
`School` aurait produit deux sources de vérité concurrentes pour la même
question — « à qui appartient cette donnée ? » — et c'est exactement ce genre
de duplication qui finit par créer une faille d'isolation le jour où l'une des
deux est mise à jour sans l'autre.

`School` **est** l'entité. Elle a simplement reçu les attributs qui lui
manquaient pour tenir ce rôle pleinement.

### 1.2 Stratégie d'isolation

Base de données partagée, schéma partagé. L'isolation est appliquée
**explicitement** dans la couche API, et non via un état global thread-local.

Ce choix est documenté dans `apps/core/tenancy.py` et reste valable : le projet
utilise Celery et Channels, deux contextes où une variable posée par un
middleware HTTP n'existe plus. Un filtrage implicite y donnerait une **fausse
impression de sécurité**.

## 2. Le modèle d'entité

`schools.School` — champs ajoutés en V4 :

| Champ | Rôle |
|---|---|
| `code` | **Identifiant interne stable** (`FEBA`, `FEBA_FHA`). Unique. |
| `legal_name` | Dénomination légale (documents, contrats, factures). |
| `entity_type` | `campus` (présentiel) ou `online` (académie en ligne). |
| `whatsapp` | Numéro international. Vide = bouton masqué. |
| `timezone` | Fuseau de référence administrative. |
| `currency` | Devise des paiements et documents. |
| `default_language` | Langue par défaut des documents et notifications. |
| `settings` | JSON administrable (features, textes, politiques). |
| `updated_at` | Horodatage de modification. |

### 2.1 Règle du code interne stable

> **La logique métier s'appuie exclusivement sur `code`, jamais sur le nom
> affiché.**

`School.CODE_FEBA` et `School.CODE_FEBA_FHA` sont des constantes de classe.
L'administration peut renommer une entité dans l'interface sans qu'aucune règle
d'accès, de routage de formulaire ou de numérotation ne change de comportement.

C'est la raison pour laquelle `get_fha_entity()` filtre sur `code=FEBA_FHA` et
non sur `name__icontains="Heritage"`.

## 3. Entités créées

| | FEBA | FEBA French Heritage Academy |
|---|---|---|
| Code | `FEBA` | `FEBA_FHA` |
| Nom complet | Faith & Excellence Bilingual Academy | FEBA French Heritage Academy |
| Abréviation menu | — | **FEBA FHA** |
| Type | `campus` | `online` |
| Fuseau | `Africa/Porto-Novo` | `America/New_York` |
| Devise | XOF | USD |
| Langue par défaut | fr | en |
| Préfixe dossier | FEBA | FHA |

## 4. Appartenances — `OrganizationMembership`

`CustomUser.school` **reste la source de vérité** du rattachement principal :
c'est ce champ que lit le filtrage de queryset. Le conserver évite de réécrire
des règles d'isolation déjà éprouvées par la suite de tests existante.

`OrganizationMembership` ajoute ce qu'un champ simple ne peut pas exprimer :

- le **Super Administrateur**, rattaché à plusieurs entités ;
- l'**historique** des affectations (qui a affecté qui, quand) ;
- un **statut** (`active` / `suspended` / `revoked`) sans supprimer la ligne ;
- un rôle porté par l'appartenance elle-même.

Les deux restent cohérents via le signal `sync_primary_membership`
(`apps/accounts/signals.py`), déclenché à chaque sauvegarde d'utilisateur.

### Contraintes en base

```
uniq_membership_user_org           un seul lien par (utilisateur, entité)
uniq_primary_membership_per_user   au plus une appartenance principale
```

Ces contraintes sont vérifiées par des tests qui provoquent volontairement une
`IntegrityError` — la garantie est au niveau du moteur, pas seulement du code.

## 5. Contexte d'entité

### 5.1 Résolution — `get_request_school(request)`

| Rôle | Entité active |
|---|---|
| admin / enseignant / parent / élève | `user.school`, toujours |
| superadmin | `?school_id=` explicite → sinon `user.active_organization` → sinon `None` (mode plateforme) |

`CustomUser.active_organization` est **persistée en base**. C'est le point
central de la conception :

> Le frontend ne peut pas imposer une entité. Il n'existe aucune lecture d'un
> `entity_id` de payload, d'un en-tête ou d'un `localStorage` dans le chemin de
> résolution.

Pour un utilisateur normal, un `?school_id=` forgé est **simplement ignoré** —
la fonction retourne `user.school` sans même le consulter.

### 5.2 Bascule du Super Administrateur

`POST /api/auth/entity-context/switch/` — réservé au rôle `superadmin`
(403 sinon, y compris avec un payload forgé). Chaque bascule :

1. vérifie que l'entité existe et est active ;
2. persiste `active_organization` ;
3. écrit une ligne `EntitySwitchLog` (auteur, origine, destination, IP) ;
4. renvoie `cache_invalidated: true`, signal qui déclenche côté React une purge
   complète du cache React Query — sans quoi les listes de l'entité quittée
   resteraient affichées quelques instants et donneraient l'illusion d'une fuite.

## 6. Matrice de fonctionnalités

`apps/core/features.py` — permission `HasEntityFeature`, activée par
l'attribut `required_feature` d'une vue.

| Drapeau | FEBA (`campus`) | FEBA FHA (`online`) |
|---|---|---|
| `virtual_classrooms` | ✗ | ✓ |
| `video_conferencing` | ✗ | ✓ |
| `placement_tests` | ✗ | ✓ |
| `online_lessons` | ✗ | ✓ |
| `online_assignments` | ✗ | ✓ |
| `learning_library` | ✗ | ✓ |
| `skill_progress` | ✗ | ✓ |
| `certificates` | ✗ | ✓ |
| `support_tickets` | ✗ | ✓ |
| `payments` | ✓ | ✓ |
| `messaging` | ✓ | ✓ |
| `schedules` | ✓ | ✓ |

Surchargeable par entité via `settings["features"]`. Une clé inconnue est
ignorée (test dédié) : on ne peut pas injecter une fonctionnalité inexistante.

**Le refus est côté serveur.** `VirtualRoomViewSet` porte
`required_feature = "virtual_classrooms"` sur **toutes** les actions, lecture
comme écriture. Vérifié en conditions réelles : un admin FEBA reçoit `403` sur
`/api/virtual-rooms/`, y compris le superadmin lorsqu'il a basculé sur FEBA.

Le filtrage des menus React (`visibleNav`) est un **confort d'affichage**, pas
une protection.

## 7. Séparation des formulaires

| Formulaire | Route publique | Entité | Modèle |
|---|---|---|---|
| Préinscription FEBA | `/admissions` → `/api/website/preregistrations/` | FEBA | `PreRegistration` |
| Contact FEBA | `/contact` → `/api/website/contact/` | FEBA | `ContactMessage` |
| Fiche FEBA FHA | `/feba-fha/enroll` → `/api/website/fha/enroll/` | FEBA_FHA | `FHAEnrollmentApplication` |
| Contact FEBA FHA | `/feba-fha/contact` → `/api/website/fha/contact/` | FEBA_FHA | `ContactMessage` |

**L'entité est déduite de la route**, côté serveur. Le champ `entity` n'est
déclaré dans aucun serializer d'écriture : un navigateur qui envoie
`{"entity": 1}` voit ce champ silencieusement ignoré (test dédié).

Les boîtes de réception administratives sont filtrées par entité. Un accès
direct par identifiant à un dossier d'une autre entité renvoie `404`.

## 8. Numérotation par entité

`FHAEnrollmentApplication.generate_reference()` produit
`<PRÉFIXE>-<ANNÉE>-<SÉQUENCE>` (`FHA-2026-0001`), calculé **par entité**. Les
numérotations FEBA et FHA ne peuvent donc jamais entrer en collision.

La prévention des doublons repose sur une contrainte en base incluant
l'entité :

```
uniq_fha_application_child_per_parent
  (entity, parent1_email, child_first_name, child_last_name, child_birth_date)
```

Le serializer vérifie d'abord pour renvoyer un message clair ; la contrainte
reste la garantie contre les soumissions concurrentes.

## 9. Points de vigilance connus

- **Vue consolidée du superadmin.** `StudentViewSet` (et quelques vues
  antérieures) autorisent un superadmin sans entité active à voir toutes les
  entités. C'est un comportement **préexistant et assumé** du rôle plateforme,
  couvert par un test explicite. Il ne s'applique à aucun autre rôle : un
  compte non-superadmin sans entité n'obtient même pas de jeton.
- **`Teacher` n'a pas de champ `school`.** Son entité est celle de son compte
  utilisateur. C'est ce rattachement qui est filtré.
