# FEBA v37 — Rapport : comptes déjà liés, parents en masse, effectifs et suppression de classes

Date : 07/07/2026 · Base : v36 · Diagnostic par extraction d'images et OCR de vos 3 enregistrements d'écran.

---

## Vidéo 1 — « Nouvel élève » avec un compte déjà lié (80 s)

**Scénario observé** : ouverture du formulaire, sélection du compte **eleve5@feba.bj (Estelle Acakpo)** — un compte qui possède **déjà** un profil élève (matricule GROUPESCOL-2026-0005, visible dans la liste) — changement d'année (2026-2027 → 2024-2025, niveau CP1), enregistrement, retour à un formulaire vide.
**Cause racine** : `Student.user` est une relation OneToOne (une identité élève unique par compte — c'est le modèle voulu), mais **(a)** le sélecteur proposait tous les comptes élève, y compris ceux déjà liés, et **(b)** aucune validation ne traduisait la contrainte : la soumission partait en **IntegrityError 500** brute. L'utilisateur voulait en réalité *réinscrire* Estelle dans une autre année — un parcours qui existe (Inscription individuelle) mais vers lequel rien n'orientait.
**Corrections** :
- API utilisateurs : nouveau filtre `?unlinked=1` (comptes sans profil élève/enseignant/parent selon le rôle) ; le formulaire « Nouvel élève » ne propose plus **que les comptes libres**, avec une aide sous le champ : « Pour réinscrire un élève existant dans une autre année : Inscriptions → Inscription individuelle ».
- Validation serializer : si un compte lié est malgré tout soumis (API directe, données concurrentes), réponse 400 explicite — « Ce compte est déjà associé à l'élève Estelle Acakpo (GROUPESCOL-2026-0005, année X). Pour l'inscrire dans une autre année, utilisez Inscriptions → Inscription individuelle — ne créez pas de doublon. » Plus aucune 500, plus aucun risque de double identité.

## Vidéo 2 — Suppression en masse des Parents (26 s)

**Scénario observé** : page Parents (« Toutes » : 10 parents, 2 enfants chacun), sélection globale, confirm **générique** « Supprimer 10 élément(s) sélectionné(s) » → toutes les puces d'années affichent ensuite 0 parent.
**Cause racine** : la page Parents utilisait encore le bulk-delete **générique** (BulkDeleteMixin → destruction physique des parents et, par cascade, de tous les liens familiaux) — la refonte v35 n'avait couvert que les Élèves.
**Corrections** : `POST /parents/bulk-delete/` réécrit en **désactivation réversible** des comptes (aucune destruction : parents, liens ParentStudent et historique intacts) ; côté interface, bouton « Désactiver la sélection » et confirmation explicite (« Action réversible… Aucune donnée n'est détruite »), toasts reprenant le message serveur. Cohérent avec la suppression unitaire (v34) et la politique générale : **rien de destructif par défaut**.

## Vidéo 3 — Classes : effectifs à 0/30 et suppression non gardée (33 s)

**Scénario observé** : page Classes, année 2023-2024 — les 10 classes affichent toutes **0/30** alors que 30 élèves y sont inscrits (visibles en vidéo 1) ; puis « Confirmer la suppression » d'une classe.
**Causes racines** :
1. L'effectif (`student_count`) comptait `class.students` — c'est-à-dire les élèves dont le **pointeur** `current_class` vise la classe. Après promotion, plus personne ne « pointe » les classes des années passées → 0/30 partout. Même anti-modèle pointeur-vs-historique que les listes (v31) et le passage par classe (v33).
2. La suppression d'une classe n'était pas gardée : `StudentEnrollment.class_obj` étant en SET_NULL, détruire une classe **orphelinait silencieusement l'historique** (les inscriptions perdaient leur classe) ; les devoirs et créneaux (CASCADE) disparaissaient.
**Corrections** :
- `student_count` compte désormais les **inscriptions annuelles** de la classe (distinctes, élèves actifs), avec repli sur le pointeur pour les élèves jamais formellement inscrits. Les classes des années passées affichent leurs vrais effectifs.
- Suppression gardée, à l'unité (**409** listant les dépendances : inscriptions, créneaux d'emploi du temps, devoirs) comme en masse (les classes référencées sont conservées et nommées dans la réponse ; seules les classes vides sont supprimées).

## Vérifications (boucle)

Backend compilé intégralement ; 78 fichiers frontend, 0 erreur de syntaxe ; imports et appels API valides ; aucune migration nécessaire (corrections de logique et de validation). **7 nouveaux tests** (`test_linked_accounts_and_classes.py`) rejouent chaque scénario vidéo : filtre `unlinked`, erreur claire sur compte lié (aucun doublon créé), désactivation en masse des parents avec liens intacts, effectif d'une classe passée via les inscriptions, refus 409 de suppression d'une classe référencée, bulk mixte (vides supprimées / référencées conservées et nommées). Check-list du guide portée à **40 scénarios**.

## Fichiers modifiés
| Fichier | Nature |
|---|---|
| `backend/apps/accounts/views.py` | Filtre `?unlinked=1` sur la liste des comptes |
| `backend/apps/students/serializers.py` | `validate_user` : message clair, zéro doublon |
| `backend/apps/parents/views.py` | Bulk = désactivation réversible |
| `backend/apps/classes/serializers.py` | Effectif via inscriptions annuelles |
| `backend/apps/classes/views.py` | Suppression gardée (unité + masse, 409 détaillé) |
| `frontend/src/pages/admin/Students.jsx` | Sélecteur limité aux comptes libres + aide réinscription |
| `frontend/src/pages/admin/Parents.jsx` | Libellés/confirmations de désactivation |
| `backend/tests/test_linked_accounts_and_classes.py` | 7 tests de régression |
| Guides PDF | Check-list 40 scénarios |
