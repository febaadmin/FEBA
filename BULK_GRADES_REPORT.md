# BULK_GRADES_REPORT.md — Saisie groupée de notes (V6, 20/07/2026)

Saisir plusieurs notes (plusieurs matières) pour **un même élève** en **une
seule opération atomique**, sans jamais modifier la saisie simple existante.

## 1. Contrat de l'API

`POST /api/grades/bulk-create/` (action DRF `bulk_create` du `GradeViewSet`).

Corps de requête :

```json
{
  "student": 26,
  "school_year": 3,          // optionnel → année active de l'établissement
  "grades": [
    { "subject": 1, "period": "T1", "value": "15.50",
      "note_type": "devoir", "note_coefficient": 1, "comment": "" },
    { "subject": 8, "period": "T2", "value": "12.00",
      "note_type": "examen", "note_coefficient": 2 }
  ]
}
```

Réponses :

| Cas | Statut | Corps |
|---|---|---|
| Succès | `201` | `{ "created": N, "detail": "N note(s) ajoutée(s) avec succès pour <élève>.", "grades": [ …notes créées… ] }` |
| Erreur(s) de ligne | `400` | `{ "grades": [ {}, { "value": ["La note dépasse le barème (max 20)."] }, … ] }` (index = ligne) |
| Erreur globale | `400` | `{ "student": ["…"] }` / `{ "school_year": ["…"] }` / `{ "detail": "…" }` |
| Matière non autorisée (enseignant) | `400` | `{ "grades": [ { "subject": ["Vous n'êtes pas autorisé à noter en <matière>…"] } ] }` |
| Élève hors établissement (IDOR) | `400` | `{ "student": ["Élève introuvable."] }` (jamais 200 partiel) |
| Parent / élève | `403` | `IsAdminOrTeacher` |
| Anonyme | `401` | — |

## 2. Garanties (règles strictes de la mission)

- **Atomicité — tout ou rien.** La validation de **toutes** les lignes précède
  toute écriture. Si une seule ligne est invalide, la requête renvoie `400` et
  **aucune** note n'est créée : le bloc d'écriture n'est atteint que si
  `line_errors` est entièrement vide, puis exécuté dans `with
  transaction.atomic():`. Aucune écriture partielle silencieuse.
- **Permissions appliquées côté serveur.** Réutilise
  `_validate_teacher_permission(teacher, subject, student)` :
  - enseignant → **uniquement ses propres matières** (matière assignée) **et
    ses propres classes** (élève inscrit dans une classe qu'il enseigne) ;
  - admin / superadmin → périmètre élargi (matières de l'établissement) ;
  - filtrage `student`/`school_year` par établissement (`get_request_school`)
    → **anti-IDOR** : un enseignant d'une autre école reçoit « Élève
    introuvable », pas la note.
  Le frontend ne fait que présenter les matières transmises en props ; il n'est
  jamais l'autorité.
- **Erreurs indexées par ligne.** Chaque ligne est validée séparément
  (`BulkGradeLineSerializer(data=raw)`, sans `raise_exception`) ; erreurs de
  champ **et** erreurs métier sont fusionnées dans le même
  `line_errors[i]`, de sorte que **toutes** les lignes fautives sont signalées
  d'un coup (et pas seulement la première).
- **Détection des doublons** de signature `(subject, period, note_type)` à
  l'intérieur du même lot → refus ciblé sur la ligne en double, mais des lignes
  **distinctes** (période ou type différents) sont acceptées.
- **Appréciation = backend source de vérité.** L'appréciation stockée et
  renvoyée provient de `apps.grades.models.get_appreciation` (barème V4).
  L'aperçu client (`src/utils/appreciation.js`) est **affichage seul**.
- **Saisie simple intacte.** Aucune modification de l'endpoint de création
  unitaire ; le modal groupé est ouvert par un bouton « Saisie groupée »
  distinct.

## 3. Frontend

- `src/components/grades/BulkGradeModal.jsx` — modal réutilisable
  (enseignant + admin + superadmin) : filtre classe + `SearchableSelect` élève,
  lignes en **tableau sur desktop / cartes empilées sur mobile** (pas de scroll
  horizontal), ajout / duplication / suppression de lignes, aperçu
  d'appréciation par ligne, mapping des erreurs backend `grades[i].champ` au bon
  endroit, double-soumission empêchée, résumé + rafraîchissement à la réussite.
- Boutons « Saisie groupée » ajoutés sur `pages/teacher/Grades.jsx` et
  `pages/admin/Grades.jsx` ; invalidation React Query après succès.
- `gradesAPI.bulkCreate` (`src/api/index.js`) ; ~20 clés EN ajoutées.

## 4. Vérification

### 4.1 Tests backend — 16/16 (`tests/test_bulk_grades.py`)

| Classe | Test | Vérifie |
|---|---|---|
| BulkSuccess | `test_single_line_via_bulk` | 1 ligne via bulk = 1 note |
| BulkSuccess | `test_multiple_lines_atomic_success` | N lignes créées ensemble |
| BulkSuccess | `test_year_optional_uses_active` | année omise → année active |
| BulkSuccess | `test_averages_recomputed` | moyennes recalculées après lot |
| Rollback | `test_one_invalid_line_rolls_back_all` | 1 ligne KO → **0 note créée** |
| Rollback | `test_errors_indexed_by_line` | toutes les lignes fautives signalées, index correct |
| Rollback | `test_invalid_coefficient` | coefficient < 1 refusé |
| Rollback | `test_duplicate_line_rejected_but_distinct_allowed` | doublon refusé, distinct accepté |
| Permission | `test_teacher_subject_not_assigned` | matière non enseignée → refus |
| Permission | `test_teacher_student_not_in_class` | élève hors de ses classes → refus |
| Permission | `test_teacher_cannot_target_other_school_student_idor` | **IDOR bloqué** |
| Permission | `test_admin_can_bulk_in_school` | admin autorisé (son école) |
| Permission | `test_superadmin_can_bulk` | superadmin autorisé |
| Permission | `test_parent_forbidden` | parent `403` |
| Permission | `test_anonymous_unauthorized` | anonyme `401` |
| Permission | `test_empty_grades_rejected` | lot vide refusé |

### 4.2 Tests frontend — 6/6 (`src/components/grades/BulkGradeModal.test.jsx`)

Message d'atomicité affiché ; ajout de ligne ; **charge utile groupée**
`{ student, grades:[…] }` correcte + succès (toast + `onSaved` + fermeture) ;
mapping d'une **erreur backend par ligne** au bon endroit **sans** fermeture
(pas d'écriture partielle) ; blocage si champ obligatoire manquant ; élève
obligatoire.

### 4.3 E2E navigateur — session enseignant réelle (prof.math)

Exécuté via la session authentifiée réelle contre l'API locale :

| Scénario | Résultat observé |
|---|---|
| Lot valide (Maths=15.50 + Mathematics=12.00 pour Ayo Codjo) | `201`, `created 2`, appréciations backend « SATISFAISANT » / « PEUT MIEUX FAIRE » |
| Matière interdite (Histoire-Géo, non enseignée) | `400`, `grades[0].subject = ["Vous n'êtes pas autorisé à noter en Histoire-Géo…"]` |
| Rollback (ligne 0 valide=14, ligne 1 note=25 > barème) | `400`, `grades[1].value = ["La note dépasse le barème (max 20)."]`, **comptage T3 inchangé** (aucune écriture partielle) |

Le modal a été affiché et rempli dans l'interface enseignant réelle (élève
sélectionné, colonnes matière/période/note/type/coeff/appréciation, bouton
« Enregistrer toutes les notes »).

## 5. Fichiers

- Backend : `apps/grades/serializers.py` (`BulkGradeLineSerializer`),
  `apps/grades/views.py` (action `bulk_create` + `_notify_bulk`,
  `get_permissions`), `tests/test_bulk_grades.py`.
- Frontend : `components/grades/BulkGradeModal.jsx`,
  `components/grades/BulkGradeModal.test.jsx`, `utils/appreciation.js`,
  `api/index.js`, `pages/teacher/Grades.jsx`, `pages/admin/Grades.jsx`,
  `i18n/translations.js`.
