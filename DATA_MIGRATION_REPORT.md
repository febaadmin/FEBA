# Rapport de migration des données — V3 → V4 multi-entités

## 1. Migrations ajoutées

| Migration | Type | Objet |
|---|---|---|
| `schools.0012_school_code_...` | Schéma | Champs d'entité + `OrganizationMembership` + `EntitySwitchLog` + contraintes |
| `schools.0013_entity_codes_and_fha` | **Données** | Code `FEBA` sur l'entité historique, création de `FEBA_FHA`, rétro-remplissage des appartenances |
| `accounts.0006_customuser_active_organization` | Schéma | Entité active persistée du superadmin |
| `website.0004_contactmessage_category_...` | Schéma | `entity` sur contacts/préinscriptions, champs FHA, `FHAEnrollmentApplication`, historique de statuts |
| `website.0005_backfill_form_entities` | **Données** | Rattachement des soumissions existantes à FEBA |

## 2. Règles appliquées

- Les données scolaires existantes **restent** rattachées à leur établissement
  d'origine (FEBA). Aucun déplacement.
- Les messages de contact et préinscriptions antérieurs à la séparation sont
  rattachés à **FEBA** : ils ont été déposés via les formulaires du site FEBA.
- Les demandes portant `desired_level = "feba_online"` **ne sont pas déplacées
  automatiquement** vers FEBA FHA. La donnée serait ambiguë : l'ancien
  formulaire FEBA ne collectait aucune des informations nécessaires au
  programme FHA (origines, niveau de français, fuseau, équipement,
  consentements). Elles restent sur FEBA et sont **comptées et journalisées**
  pour revue manuelle par l'administration.
- **Aucune donnée n'est supprimée**, dans aucun sens de migration.

## 3. Vérification sur base existante

Scénario rejoué réellement : base PostgreSQL amenée à l'état V3
(`schools 0011`, `accounts 0005`, `website 0003`), peuplée comme un
déploiement FEBA, puis migrée vers la V4.

### Avant migration

| Table | Lignes |
|---|---|
| `schools_school` | 1 |
| `accounts_customuser` | 4 (1 admin, 1 enseignant, 1 parent, 1 superadmin) |
| `website_contactmessage` | 1 |
| `website_preregistration` | 2 (dont 1 `feba_online`) |

### Après migration

```
Entités :
  [FEBA    ] Faith & Excellence Bilingual Academy   type=campus  XOF fr
  [FEBA_FHA] FEBA French Heritage Academy           type=online  USD en

Utilisateurs conservés : 4
  FEBA                     : 3
  FEBA_FHA                 : 0
  (superadmin sans entité) : 1

Appartenances créées : 5
  a@feba.bj   → FEBA     role=admin       principale=True
  t@feba.bj   → FEBA     role=teacher     principale=True
  p@feba.bj   → FEBA     role=parent      principale=True
  su@feba.bj  → FEBA_FHA role=superadmin  principale=False
  su@feba.bj  → FEBA     role=superadmin  principale=False

Messages de contact : 1 (rattachés FEBA : 1)
Préinscriptions     : 2 (rattachées FEBA : 2)
  dont issues de l'ancien module FEBA Online (à revoir) : 1
```

Message émis par la migration :

```
Migration entités formulaires : 1 messages et 2 préinscriptions rattachés à
FEBA ; 1 demandes « FEBA Online » à revoir manuellement pour un éventuel
rattachement à FEBA FHA.
```

**Contrôle avant/après : 4 utilisateurs → 4 utilisateurs, 1 contact → 1
contact, 2 préinscriptions → 2 préinscriptions. Aucune perte.**

## 4. Idempotence — vérifiée

Les deux migrations de données ont été **rejouées** sur la base déjà migrée :

```
AVANT rejeu : {'entites': 2, 'appartenances': 5, 'contacts': 1, 'preinscriptions': 2}
APRÈS rejeu : {'entites': 2, 'appartenances': 5, 'contacts': 1, 'preinscriptions': 2}
IDEMPOTENT  : True
```

Toutes les opérations utilisent `filter(...)` / `get_or_create(...)` et ne
réécrivent jamais une valeur déjà saisie par l'administration.

## 5. Installation neuve — vérifiée

`migrate` sur une base vierge s'exécute sans erreur. Seule `FEBA_FHA` est
créée (aucune école historique à coder). Le repli de `get_feba_entity()`
rattache alors les formulaires FEBA à la première entité présentielle active.

## 6. Retour arrière

Les deux migrations de données définissent une fonction `backwards` **non
destructive** :

- `schools.0013` retire les codes et les appartenances générées, mais **ne
  supprime pas** l'entité FEBA FHA ni aucune donnée métier qui lui aurait été
  rattachée entre-temps ;
- `website.0005` se contente de délier (`entity = NULL`).

## 7. Compatibilité SQLite

`DJANGO_SETTINGS_MODULE=feba_project.settings.test_sqlite` **échoue**, mais
pour une cause **antérieure** à ces travaux : les migrations multi-tenant V29
(`accounts.0003`, `attendance.0003`, `bulletins.0003`, `grades.0007`,
`parents.0003`) utilisent `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`, syntaxe
PostgreSQL que SQLite ne comprend pas.

C'est documenté dans le projet lui-même (`settings/test_postgres.py`). Le
comportement est **identique avant et après** cette livraison — vérifié sur le
commit de référence. PostgreSQL est la cible de test du projet. Voir
`KNOWN_LIMITATIONS.md`.
