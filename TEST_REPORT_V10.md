# FEBA — Rapport de tests V10

Exécuté le 2026-09-04.

---

## 1. Totaux

| Suite | Commande | Résultat |
|---|---|---|
| Backend PostgreSQL (référence) | `pytest tests apps --ds=feba_project.settings.test_postgres` | **1265 passés, 0 échec**, 582 sous-tests |
| Backend SQLite | `pytest tests apps --ds=feba_project.settings.test_sqlite` | **1264 passés, 1 ignoré** |
| Frontend | `npx vitest run` | **223 passés, 24 fichiers** |
| Parcours navigateur | Playwright / Chromium | **15/15** |
| ESLint | `npx eslint src --ext .js,.jsx` | **0 erreur**, 81 avertissements |
| Build | `npm run build` | **OK** |
| Migrations | `manage.py makemigrations --check --dry-run` | **Aucun changement détecté** |

### L'unique test ignoré

`tests/test_parent_student.py::…` — test de concurrence multi-threads.
SQLite en mémoire verrouille la table entière (« database table is
locked »). **Il s'exécute et passe sur PostgreSQL**, qui est la base de
référence. Ce n'est pas un test contourné : c'est le même test, exécuté
là où il a un sens.

---

## 2. Tests ajoutés en V10

### Backend — 69 tests

`tests/test_v10_academy_scope_and_rooms.py` (61) :

| Classe | Objet |
|---|---|
| `ClassesVisiblesDansLesListesTests` | le défaut central : une académie sans année activée voit ses classes |
| `NonRegressionFebaTests` | §37 — FEBA inchangé |
| `CloisonnementDesClassesTests` | aucune fuite entre académies |
| `ParcoursLinguistiqueTests` | parcours déclaré, matières attendues |
| `AccesAuxSallesTests` | qui peut rejoindre, et qui ne peut pas |
| `IdorParLApiTests` | identifiants postés directement → 403 |
| `JetonJitsiTests` | forme et portée du JWT |
| `JoinLeaveIdempotentsTests` | une adhésion, un départ |
| `ActivationAutomatiqueDeLAnneeTests` | la première année s'active ; une année clôturée **reste close** |
| `AffectationDesClassesAUnEnseignantTests` | §29 — créer, relire, remplacer, vider, refuser |
| `AuditDeLaPorteeAcademiqueTests` | §6/§44 — toutes les listes d'un coup |
| `SallesPhysiquesTests` | §5 — le « 0 » était exact ; le cloisonnement est vérifié |

`tests/test_bulletin_language_track.py` (8) : le bulletin suit le
parcours, sans masquer ni anomalie ni résultat.

### Frontend — 38 tests

| Fichier | Objet |
|---|---|
| `components/JitsiMeeting.test.jsx` (12) | cycle de vie : **combien** de conférences sont créées, et **quand** l'ancienne est détruite |
| `pages/shared/VirtualRoomSession.test.jsx` (18) | onglet plein écran, portée d'académie, StrictMode, idempotence, absence de jeton dans l'URL |
| `pages/shared/VirtualRooms.test.jsx` (8) | ouverture synchrone du nouvel onglet, bloqueur de fenêtres, menus peuplés, `target_roles` en liste |

---

## 3. Chaque correction prouvée par sa suppression

Un test qui ne tombe jamais ne prouve rien. Chaque correctif a été retiré
temporairement, et les échecs observés :

| Correctif retiré | Tests qui tombent |
|---|---|
| `scope_to_active_year` dans `classes/views.py` | **2** — dont l'audit, qui nomme l'endpoint |
| `_state.adding` dans `SchoolYear.save()` | **3** — dont un test préexistant du dépôt |
| Adaptation du bulletin au parcours | **2** |
| Dépendances réduites de `JitsiMeeting` | **5** |
| Garde par identifiant (StrictMode) | **2** |
| Attente de `scopeReady` avant `join()` | **3** |

---

## 4. Une fixture qui mentait

Après le correctif de `SchoolYear.save()`, la fixture des tests V10
**s'activait toute seule** : `year(fha, …, current=False)` créait une
année qui devenait immédiatement active, puisque c'était la première de
l'académie.

Le test central passait donc pour de mauvaises raisons — **il passait
même avec le défaut d'origine**. C'est exactement le genre de test qui
donne une fausse assurance.

Corrigé : `year()` force l'état de production par un `update()` qui
contourne `save()` (comme le ferait une migration de données), et les
tests qui portent sur le modèle lui-même passent par `annee_brute()`. Le
garde-fou `test_l_academie_testee_n_a_bien_aucune_annee_activee` vérifie
désormais la prémisse avant tout le reste.

---

## 5. Parcours navigateur (§30)

Chromium, application servie en local, **académie FEBA FHA laissée dans
l'état exact des captures d'écran du rapport** (une année scolaire
existante, jamais activée).

| # | Parcours | Résultat |
|---|---|---|
| A | Connexion administrateur FEBA FHA | **PASS** |
| B | Menu « Classe » : 3 classes FHA proposées | **PASS** |
| B2 | Cases « Réservée à » (4 profils) | **PASS** |
| C | « Classes assignées » ne dit plus « Aucun résultat » | **PASS** |
| D | « Salles physiques de l'école » — compteur = 6 | **PASS** |
| E | Les classes FHA sont listées | **PASS** |
| E2 | Le formulaire propose « Parcours linguistique » | **PASS** |
| F | « Rejoindre » ouvre un NOUVEL onglet | **PASS** |
| F2 | L'onglet pointe `/virtual-room/:id/join` | **PASS** |
| F3 | Aucun jeton dans l'URL | **PASS** |
| F4 | Ni barre latérale, ni en-tête, ni tableau de bord | **PASS** |
| F5 | Aucun repli vers `meet.jit.si` | **PASS** |
| G | Connexion administrateur FEBA | **PASS** |
| G2 | FEBA affiche toujours ses classes (§37) | **PASS** |
| H | Aucune erreur JavaScript pendant les parcours | **PASS** |

Captures d'écran produites pour chaque étape.

### Ce que les parcours ont trouvé

Deux défauts que les tests unitaires ne voyaient pas — l'onglet restait
indéfiniment sur « Ouverture de la salle… ». Voir `V10_REPORT.md` §4.
Les deux sont corrigés et couverts par des tests qui échouent si on
retire le correctif.

---

## 6. Vérifications bout en bout sur l'API réelle

Backend et frontend lancés, base PostgreSQL peuplée :

| Vérification | Mesure |
|---|---|
| `/api/classes/` sans année active | **3 classes** (0 avant correction) |
| Parcours des classes FHA | `ANGLOPHONE`, `BILINGUAL`, `FRANCOPHONE` — `missing_languages = []` |
| `/api/schools/rooms/` FHA | **3 salles** |
| `join` sans domaine Jitsi | **503**, message explicite, aucun repli |
| `join` sans secret Jitsi | **503** — refuse de servir une salle non protégée |
| `join` configuré | JWT `HS256`, `aud=jitsi`, `room` lié à la salle, `exp` présent |
| Secret dans le bundle construit | **0 occurrence** |

---

## 7. Non testé ici

| Point | Statut | Raison |
|---|---|---|
| Réunion à 2 participants (§31) | **À TESTER EN ENVIRONNEMENT RÉEL** | deux navigateurs distants requis |
| Stabilité 30 minutes (§32) | **À TESTER EN ENVIRONNEMENT RÉEL** | idem |
| Poignée de main WebSocket | **À TESTER EN ENVIRONNEMENT RÉEL** | le mandataire du bac à sable ne relaie aucune mise à niveau WebSocket |
| Refus d'adhésion anonyme sur l'instance en service | **À TESTER EN ENVIRONNEMENT RÉEL** | Chromium n'a aucun accès sortant ici |
| `docker compose up` complet | **LIMITATION CONNUE** | le démon Docker est indisponible dans cet environnement ; `docker compose config` reste vérifiable |
