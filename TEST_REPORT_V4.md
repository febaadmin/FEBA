# Rapport de tests — V4 multi-entités

## 1. Commandes exactes

```bash
# Backend (cible de test du projet)
cd backend
DJANGO_SETTINGS_MODULE=feba_project.settings.test_postgres python -m pytest -q

# Frontend
cd frontend
npx vitest run
npx eslint src
npm run build
```

## 2. Résultats

| Suite | Référence (avant travaux) | Après travaux |
|---|---|---|
| Backend PostgreSQL | **406 passed** | **481 passed** |
| Frontend Vitest | 71 passed | **75 passed** |
| ESLint | 0 erreur | **0 erreur** (65 avertissements préexistants) |
| Build production | OK | **OK** (8,2 s) |

Aucun test ignoré (`skip`) dans la suite finale.

### Versions

| | |
|---|---|
| Python | 3.11.15 |
| Django | 5.0.4 |
| PostgreSQL | 16.13 |
| Node | v22.22.2 |

## 3. Tests ajoutés (75 nouveaux)

### `tests/test_entity_features.py` — 21 tests
Matrice de fonctionnalités : valeurs par défaut `campus` / `online`,
surcharge administrable, clé inconnue ignorée, entités créées par la
migration, **absence de donnée commerciale inventée**. Refus API des salles
virtuelles pour une entité présentielle (lecture **et** écriture). Contexte
d'entité, bascule du superadmin et son journal, interdiction de bascule pour
un admin, contraintes d'unicité des appartenances vérifiées par
`IntegrityError`.

### `tests/test_fha_forms.py` — 30 tests
Rattachement d'entité par la route, **`entity` client ignoré**, numéro de
dossier unique, doublons refusés, consentements obligatoires datés et
versionnés, date de naissance future rejetée, téléphone et e-mail validés,
niveau de français et jours inconnus rejetés, honeypot, âge calculé, groupe
suggéré, historique de statut, e-mail de confirmation contenant le numéro de
dossier, cloisonnement des boîtes de réception, anti-IDOR sur les dossiers,
changement de statut tracé, et vérification que `/fha/program/` n'expose
aucune donnée non validée.

### `tests/test_entity_isolation.py` — 23 tests
Voir `ENTITY_PERMISSION_MATRIX.md` §2 pour la correspondance exigence → test.
Couvre les deux sens (FEBA→FHA et FHA→FEBA) pour utilisateurs, élèves,
enseignants et classes ; l'anti-IDOR en lecture, écriture et suppression ; la
falsification de `?school_id=` et des payloads ; la séparation des
statistiques du tableau de bord et de la recherche ; et le périmètre du
superadmin selon l'entité active.

### `frontend/src/site/legacyNaming.test.js` — 5 tests
Parcourt les sources et échoue si « FEBA Online » réapparaît dans un texte
visible, ou si `/feba-online` est référencée autrement que pour rediriger.

## 4. Tests existants adaptés — et pourquoi

Trois adaptations, chacune parce que la **prémisse du test a cessé d'exister**,
non pour faire passer la suite.

| Test | Raison |
|---|---|
| `test_superadmin_creates_year_single_school_inferred` | La déduction « mono-établissement » n'a plus de sens dès que FEBA et FEBA FHA coexistent : deviner rattacherait l'année à la mauvaise entité. Remplacé par **deux** tests : refus explicite en cas d'ambiguïté, et résolution via l'entité active. |
| `test_virtualclass.py` (`make_school`) | Les salles virtuelles sont désormais une fonctionnalité d'**académie en ligne**. Les tests portent sur une entité `online`, seul type qui possède la fonctionnalité. Le refus pour `campus` est couvert par `test_entity_features.py`. |
| `test_bulk_year_and_jitsi.py` (`JitsiJwtTests`) | Même raison. |

## 5. Vérification en conditions réelles

Serveur Django lancé sur une base PostgreSQL migrée depuis un état V3.

### Soumission de fiche FEBA FHA
```
POST /api/website/fha/enroll/  →  201
  reference       : FHA-2026-0001
  status          : form_received
  child_age       : 11          (calculé, non saisi)
  suggested_group : french_explorers   (cohérent : 10-15 ans)

Seconde soumission identique  →  400
  duplicate : « Une fiche existe déjà pour cet enfant avec cette adresse
               e-mail (dossier FHA-2026-0001). »
```

### Isolation inter-entités
```
ADMIN FEBA (campus)
  dossiers FHA listés            : 0
  accès direct dossier FHA #1    : HTTP 404
  GET /api/virtual-rooms/        : HTTP 403
  messages de contact visibles   : 1  ['Question FEBA']

ADMIN FEBA FHA (online)
  dossiers FHA listés            : 1  [FHA-2026-0001, FEBA_FHA, Naomi, 11 ans]
  GET /api/virtual-rooms/        : HTTP 200
```

### Bascule du Super Administrateur
```
bascule → FEBA
  active=FEBA      virtual_classrooms=False   cache_invalidated=True
  GET /api/virtual-rooms/  : HTTP 403      ← la matrice s'applique aussi au superadmin

bascule → FEBA_FHA
  active=FEBA_FHA  virtual_classrooms=True
  GET /api/virtual-rooms/  : HTTP 200

journal d'audit
  su@feba.bj : FEBA → FEBA_FHA (127.0.0.1)
  su@feba.bj : None → FEBA     (127.0.0.1)
```

### Programme public
```
GET /api/website/fha/program/  →  200
  tagline    : "From English Speakers to Confident French Speakers"
  whatsapp   : "+1 (215) 715-5406"
  currency   : USD        timezone : America/New_York

  annual_fee, school_year_start_date, group_schedules,
  refund_policy, teacher_names, payment_provider  →  tous null
```

## 6. Non-régression FEBA

Les 406 tests de référence sont **tous** toujours présents et passants (à
l'exception des trois adaptations documentées au §4). Sont couverts sans
modification : authentification, profils, tableaux de bord, élèves, parents,
enseignants, classes, matières, notes, moyennes, bulletins, paiements, reçus,
présences, emplois du temps, annonces, notifications, messagerie, devoirs,
documents, réinitialisation de mot de passe, site vitrine, galerie,
admissions, génération des PDF, cachets et permissions existantes.
