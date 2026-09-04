# FEBA — Rapport V10

Correction profonde, audit global et finalisation.
Toutes les affirmations de ce document sont vérifiées ; les statuts
suivent la convention §42.

---

## 1. Résumé

| Vérification | Résultat |
|---|---|
| Tests backend PostgreSQL | **1265 passés, 0 échec** |
| Tests backend SQLite | **1264 passés, 1 ignoré** (limite SQLite documentée) |
| Tests frontend (Vitest) | **223 passés, 24 fichiers** |
| Parcours navigateur réels | **15/15** |
| ESLint | **0 erreur**, 81 avertissements (référence inchangée) |
| `npm run build` | **OK** |
| `manage.py makemigrations --check` | **Aucun changement détecté** |

Les quatre bugs signalés avaient **deux causes racines**, pas quatre.

---

## 2. Les causes racines

### 2.1 Un invariant que rien ne garantissait

Bugs n°1 (menu « Classe » d'une salle virtuelle) et n°4 (« Classes
assignées » d'un enseignant) : **le même endpoint**, donc le même défaut.

Mesuré sur l'API, même utilisateur, même académie, même instant :

```
GET /api/classes/                →  0 classe
GET /api/classes/?all_years=1    →  3 classes
```

Le filtre par défaut `school_year__is_current=True` est légitime : sans
lui, une académie de trois années affiche « CP1-A » trois fois dans
chaque menu. Mais il suppose que **chaque académie a exactement une année
active** — et rien ne l'imposait. FEBA FHA avait une année scolaire que
personne n'avait jamais activée : tous ses menus tombaient à zéro.

En silence. L'utilisateur ne lisait pas « aucune année active » ; il
voyait ses classes disparaître.

**Réparé à trois niveaux**, pas seulement là où ça se voyait :

| Niveau | Fichier | Rôle |
|---|---|---|
| Lecture | `apps/schools/academic_year.py` | une seule réponse à « quelle est l'année de travail », avec repli sur l'année la plus récente |
| Écriture | `apps/schools/models.py` (`SchoolYear.save()`) | la première année d'une académie est active — **à la création uniquement** |
| Données | `apps/schools/migrations/0016` | répare les académies déjà dans cet état |

La garde `_state.adding` n'est pas un détail : sans elle, une année
enregistrée à `is_current=False` était aussitôt réactivée, et le bouton
« Clôturer » ne clôturait plus rien.

### 2.2 Une règle de FEBA promue en règle universelle

Bugs n°2 et n°3. « Au moins une matière française **et** une anglaise
sont obligatoires » décrit FEBA, qui est bilingue. Appliquée à une classe
francophone de FEBA FHA, elle lui reprochait sans fin l'absence d'une
langue qu'elle n'enseigne pas — et le reproche ne pouvait jamais être
levé.

`Class.language_track` (`BILINGUAL` par défaut, donc **FEBA inchangé**)
dit ce qui est attendu. Voir `CLASS_LANGUAGE_MODEL_REPORT.md`.

---

## 3. Les bugs signalés

| # | Signalement | Statut | Preuve |
|---|---|---|---|
| 1 | Menu « Classe » limité à « Toute l'école » | **CORRIGÉ ET VÉRIFIÉ** | Parcours B : `["Toute l'école","French Ambassadors","French Explorers","Junior Roots"]` |
| 2 | Classes monolingues bloquées | **CORRIGÉ ET VÉRIFIÉ** | `ParcoursLinguistiqueTests`, parcours E2 |
| 3 | Bulletin inadapté au parcours | **CORRIGÉ ET VÉRIFIÉ** | `tests/test_bulletin_language_track.py` (8 tests) |
| 4 | « Classes assignées » → « Aucun résultat » | **CORRIGÉ ET VÉRIFIÉ** | Parcours C ; `AffectationDesClassesAUnEnseignantTests` |
| 5 | « Salles physiques de l'école (0) » | **CORRIGÉ ET VÉRIFIÉ** | Parcours D : compteur = 6 |

### Sur le bug n°5 — ce que le diagnostic a réellement donné

Ce n'était **pas** un défaut de portée. `Room` n'a aucun lien avec
l'année scolaire ; `RoomViewSet` filtre sur `school`, un point c'est
tout. FEBA FHA affichait « 0 » parce qu'elle n'avait **réellement** aucune
salle enregistrée — FEBA en avait six.

La correction est donc dans les données de démonstration
(`seed_demo_data` crée trois salles FHA), pas dans le filtrage. Faire
apparaître un chiffre en modifiant la requête aurait affiché les salles de
FEBA dans les paramètres de FEBA FHA.

Le compteur affiche 6 = 3 salles physiques + 3 classes présentées comme
salles ; les deux ensembles sont scopés FHA. C'est le comportement voulu
de l'écran, pas une fuite.

---

## 4. Deux défauts que seuls les parcours navigateur ont montrés

Les tests unitaires passaient. Le navigateur, non : l'onglet de
conférence restait **indéfiniment** sur « Ouverture de la salle… », y
compris quand le backend avait déjà répondu « visioconférence
indisponible ».

**Défaut A — le résultat de la seule requête était jeté.** La garde
anti-double-adhésion empêchait la seconde exécution de l'effet
(React StrictMode) de relancer la requête, pendant que le nettoyage de la
première posait `cancelled = true`. La garde retient désormais
l'identifiant de la salle plutôt qu'un booléen : elle protège toujours
contre la double adhésion, elle laisse passer le résultat, et elle
corrige un second défaut latent — un onglet mené d'une salle à une autre
n'adhérait jamais à la seconde.

**Défaut B — la requête partait avant la portée d'académie.** La route de
conférence vit à la racine du routeur (c'est tout son intérêt : ni barre
latérale, ni en-tête) et échappait donc au garde `AcademyScopedOutlet`.
`join()` partait sous la portée `UNKNOWN` et `setAcademyScope()`
l'annulait dès l'arrivée du contexte — exactement le scénario que le
commentaire d'`AcademyScopedOutlet` décrit pour les écrans métier. Le
garde n'est pas contourné : il est appliqué à la main.

Les deux sont tenus par des tests qui échouent si on les retire.

---

## 5. Non-régression FEBA (§37)

| Vérification | Résultat |
|---|---|
| Connexion administrateur FEBA | **PASS VÉRIFIÉ** (parcours G) |
| Classes FEBA listées | **PASS VÉRIFIÉ** (parcours G2) |
| Menu déroulant FEBA : 10 classes, sans doublon | **PASS VÉRIFIÉ** |
| `?all_years=1` : 30 classes | **PASS VÉRIFIÉ** |
| Bulletin bilingue FEBA inchangé | **PASS VÉRIFIÉ** (`test_feba_bilingue_inchange`) |
| Cloisonnement FEBA / FEBA FHA | **PASS VÉRIFIÉ** |

`language_track` vaut `BILINGUAL` par défaut : toutes les classes FEBA
existantes conservent exactement leur comportement, sans migration de
données.

---

## 6. Méthode

Chaque correction a été **prouvée en la retirant** et en observant les
tests échouer :

| Correction retirée | Tests qui tombent |
|---|---|
| `scope_to_active_year` | 2 (dont l'audit, qui **nomme** l'endpoint fautif) |
| `_state.adding` sur `SchoolYear.save()` | 3 |
| Adaptation du bulletin au parcours | 2 |
| Dépendances réduites de `JitsiMeeting` | 5 |
| Garde par identifiant (StrictMode) | 2 |
| Attente de `scopeReady` | 3 |

Un défaut trouvé en cours de route mérite d'être signalé : depuis le
correctif de `SchoolYear.save()`, la fixture des tests V10 **s'activait
toute seule**. Le test central passait donc pour de mauvaises raisons —
il passait même avec le défaut d'origine. Le helper `year()` force à
nouveau l'état réel de production, et les tests qui portent sur le modèle
lui-même passent par `annee_brute()`.

---

## 7. Renvois

- `JITSI_AUDIT_REPORT.md` — visioconférence : architecture, sécurité, réseau
- `CLASS_LANGUAGE_MODEL_REPORT.md` — parcours linguistique et bulletins
- `MULTI_ACADEMY_AUDIT.md` — portée académique, endpoint par endpoint
- `TEST_REPORT.md` — inventaire des tests
- `KNOWN_LIMITATIONS.md` — ce qui reste à vérifier en environnement réel
- `MANUAL_PRODUCTION_ACTIONS.md` — actions humaines requises
