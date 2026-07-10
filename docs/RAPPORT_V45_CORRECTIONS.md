# RAPPORT V45 — Corrections complètes (Bugs N°1 à N°9 + audit)

**Périmètre** : refonte du bulletin bilingue, formule 60/40, tableaux de bord,
gestion des utilisateurs admin, CRUD des années scolaires, déduplication des
listes de classes, nouveaux matricules, nettoyage console et audit global.

**Validation** : `python manage.py test tests/` → **152 tests, 0 échec** ·
`npm run build` → OK · `npm run lint` → **0 erreur** (60 avertissements
non bloquants) · scénarios API et PDF rejoués sur données de démonstration.

---

## BUG N°1 — Refonte de la présentation des bulletins

**Fichier réécrit** : `backend/apps/bulletins/pdf_generator.py`

Le bulletin PDF suit désormais le modèle de référence fourni :

1. En-tête établissement (nom + adresse réels de l'école, logo dynamique
   SchoolBranding → School.logo → logo statique) ;
2. Bloc identité élève (sans rang — voir BUG N°2) ;
3. **RÉSULTATS — PARTIE FRANÇAISE / FRENCH SECTION** : tableau des matières
   FR avec notes détaillées, coefficient, moyenne /20, moyenne pondérée,
   lettre et **appréciation par matière**, puis ligne « MOYENNE DE LA
   PARTIE » (moyenne pondérée par coefficients des matières FR) ;
4. **ACADEMIC RESULTS — ENGLISH SECTION / PARTIE ANGLAISE** : idem pour les
   matières EN (charte verte pour distinguer visuellement) ;
5. Tableau « MOYENNES & STATISTIQUES DE LA CLASSE » (voir BUG N°2) ;
6. Formule bilingue affichée : (Moyenne Française × 60 %) + (Moyenne
   Anglaise × 40 %) ;
7. Bande « Moyenne Générale + Lettre + Appréciation » ;
8. Signatures directeur/parent + pied de page.

Le template **maternelle** (notation en lettres + conduite) est conservé,
lui aussi réorganisé en sections FR/EN et débarrassé du rang. Le bulletin
**annuel** présente T1/T2/T3 + moyenne annuelle par matière, dans les mêmes
sections séparées.

**Choix techniques (module réécrit)** :
- La séparation FR/EN s'appuie sur `Subject.language` (source de vérité du
  système bilingue existant) — aucune donnée nouvelle à saisir.
- Les fonctions de rendu sont factorisées (`_add_header`,
  `_add_student_info`, `_add_language_section`, `_add_stats_section`,
  `_add_signatures`, `_add_footer`) et partagées entre les templates
  standard/maternelle : une seule implémentation de chaque bloc.
- Les moyennes de section sont recalculées avec les mêmes règles que le
  moteur central (matières non notées exclues, pondération par coefficient).
- `_build_annual_subject_data` privilégie désormais les matières M2M de la
  classe (cohérent avec `Grade.get_subject_averages`).

## BUG N°2 — Statistiques du bulletin (min/max à la place du rang)

**Fichiers** : `backend/apps/grades/models.py`,
`backend/apps/bulletins/pdf_generator.py`,
`frontend/src/pages/{admin,parent,student}/Bulletins.jsx`

- Le rang n'apparaît **plus nulle part** sur le bulletin PDF ni dans les
  listes de bulletins (admin, parent, élève) ; `generate_bulletin()` ne le
  calcule plus (`rank_in_class = None`, champ conservé en base pour
  compatibilité).
- Nouveau moteur `Grade.get_class_bilingual_stats(classe, année, période)` :
  pour **tous les élèves actifs de la classe** (résolus par les inscriptions
  annuelles de l'année demandée), calcule et renvoie
  `fr_min/fr_max`, `en_min/en_max`, `bi_min/bi_max`, `general_min/general_max`.
  **Aucune valeur codée en dur** — tout est recalculé à chaque génération,
  y compris pour la période `annual`.
- Le bulletin affiche : moyenne de l'élève, moyenne minimale de la classe et
  moyenne maximale de la classe pour les catégories Française, Anglaise et
  Bilingue.

## BUG N°3 — Tableaux de bord Élève et Parent

**Fichiers** : `backend/apps/dashboard/views.py`,
`frontend/src/pages/student/Home.jsx`, `frontend/src/pages/parent/Home.jsx`,
`frontend/src/pages/student/Grades.jsx`

**Cause racine** : `Grade.calculate_average(student, school_year)` était
appelé **sans période** → le queryset filtrait `period=None` → aucune note ne
correspondait jamais → la moyenne générale valait toujours `None` et l'UI
affichait « — ».

**Corrections** :
- Moyenne générale = moyenne annuelle (`calculate_annual_average`, moyenne
  des trimestres effectivement notés) pour l'élève et pour chaque enfant du
  parent.
- L'API dashboard renvoie désormais : `average`, `average_t1/ت2/t3`,
  `annual_average`, `appreciation`, `progression` (T2 − T1).
- `safe_float(avg) if avg else None` → `if avg is not None` (une moyenne de
  0.00 n'est plus confondue avec « pas de moyenne »).
- UI élève : carte « Moyenne générale » avec appréciation et progression +
  rangée de cartes T1 / T2 / T3 / Moyenne annuelle ; page « Mes notes » :
  carte « Année » ajoutée à côté de T1/T2/T3.
- UI parent : moyenne générale + appréciation, moyennes T1/T2/T3 et
  progression par enfant.
- Audit bonus : le dashboard **admin** ne perd plus les élèves sans compte
  utilisateur lié (`user__is_active=True` excluait `user=None`).

## BUG N°4 — Gestion des utilisateurs pour le profil Admin

**Fichiers** : `backend/apps/accounts/{serializers,views,permissions}.py`
(déjà en place — validés et couverts par tests), `frontend/src/pages/admin/Users.jsx`,
menu `frontend/src/layouts/AdminLayout.jsx` (entrée « Utilisateurs »).

Comportements vérifiés par tests automatiques et par scénario API réel :
- L'admin **crée** des comptes Élève, Parent, Enseignant (rattachés d'office
  à SON établissement, même si le frontend envoie un autre `school`) ;
- La création d'un compte **Admin ou Super Admin est refusée (400)** avec un
  message explicite ;
- La **modification de rôle vers admin/superadmin est refusée** ;
- Un admin **ne voit pas** les comptes admin/superadmin dans ses listes et ne
  peut pas les gérer (`can_manage`, querysets filtrés par `role_level`).
- Correctif UI : le bouton « Annuler » de la confirmation de suppression était
  mort (prop `onCancel` inexistante sur `ConfirmDialog` → `onClose`).

## BUG N°5 — CRUD complet des années scolaires

**Fichiers** : `backend/apps/schools/views.py`,
`backend/apps/schools/serializers.py`, `frontend/src/pages/admin/Settings.jsx`,
`frontend/src/api/index.js`

**Endpoints** (routeur `schools/years/`) : GET (liste/détail), POST, PUT,
PATCH, DELETE + actions `set_current` et `close`.

- **DELETE protégé** (`SchoolYearViewSet.destroy`) :
  - année **active** → 409 « ne peut pas être supprimée. Clôturez-la… » ;
  - année **utilisée** → 409 avec le **détail des dépendances**
    (inscriptions, classes, notes, élèves rattachés, paiements, bulletins,
    absences) ;
  - année vide → 200 + message de succès.
- **Correctif création** : DRF générait un `UniqueTogetherValidator` depuis
  la contrainte `(school, name)` qui rendait `school` obligatoire dans le
  payload — alors que le tenant est résolu côté serveur. Validator désactivé
  (`Meta.validators = []`) ; l'unicité du nom reste vérifiée dans
  `validate()` avec un message clair + contrainte en base.
- **UI (Paramètres → Années Scolaires)** : boutons ✏️ **Modifier**
  (modale pré-remplie, création/édition mutualisées) et 🗑️ **Supprimer**
  (désactivé sur l'année active, boîte de confirmation, messages de succès
  et d'erreur relayés depuis l'API). Validations : nom requis, dates
  requises, fin > début, nom unique par établissement.

## BUG N°6 — Formule des moyennes bilingues

**Fichiers** : `backend/apps/grades/models.py` (source unique),
`backend/apps/grades/views.py`, `backend/apps/bulletins/pdf_generator.py`,
`frontend/src/pages/admin/Grades.jsx`,
`backend/tests/test_class_promotion_and_summary.py`

- Ancienne formule (fausse) : `(FR × 40 %) + (EN × 60 %)`.
- Nouvelle formule **centralisée** dans des constantes du moteur :
  `Grade.BILINGUAL_FR_WEIGHT = 0.6`, `Grade.BILINGUAL_EN_WEIGHT = 0.4`,
  `Grade.BILINGUAL_FORMULA` (libellé unique repris par l'API et les écrans).
- Tous les usages recensés et corrigés : calcul trimestriel, calcul annuel,
  endpoint `/api/grades/bilingual/` (y compris sa charge de secours),
  bulletin PDF (calculs + libellé), écran admin « Bilingue », tests.
- Vérification chiffrée : FR 15 / EN 10 → **13,00** (15×0,6 + 10×0,4).

## BUG N°7 — Doublons dans les listes de classes

**Fichier** : `frontend/src/pages/admin/Enrollments.jsx`

**Cause** : les listes déroulantes chargées avec `all_years=1` mélangeaient
les homonymes de toutes les années (CE1-A 2024, CE1-A 2025, CE1-A 2026…).

**Corrections** :
- dédoublonnage strict par id (`new Map(classes.map(c => [c.id, c]))`) ;
- **cascade année → classes** : dans « Passage par classe » (classe cible),
  « Inscription individuelle » et « Assistant de fin d'année », la liste des
  classes est **filtrée par l'année cible sélectionnée** — une classe
  n'apparaît donc qu'une seule fois par année ; changer d'année réinitialise
  la classe choisie ;
- la liste « classe source » (multi-années par nature) reste désambiguïsée
  par le libellé « CE1-A — 2024-2025 (CE1) ».
- Écrans déjà protégés vérifiés : Élèves (cascade v34), Notes (filtre par
  année v34), Classes (filtre par année).

## BUG N°8 — Nouvelle génération des matricules

**Fichiers** : `backend/apps/students/models.py`,
`backend/apps/schools/models.py`, migrations `0009` et `0010`,
`backend/apps/schools/management/commands/seed_demo_data.py`

- **Nouveau format** : `FEBA_26_0001`
  (préfixe école + année sur 2 chiffres + séquence sur 4 chiffres — 12
  caractères contre 20).
- Préfixe **configurable** par établissement (`School.matricule_prefix`,
  nouveau champ) avec **dérivation automatique** depuis le slug si vide
  (`groupe-scolaire-feba` → `FEBA`) — multi-tenant proprement supporté.
- **Séquentiel** par établissement ET par année : la séquence est calculée
  sur le maximum existant (regex sur `PREFIX_YY_NNNN`), garde-fou
  anti-collision conservé dans `Student.save()`.
- **Unique** : contrainte `unique_matricule_per_school` inchangée.
- **Compatible** : les anciens matricules (`GROUPESCOL-2026-0005`) restent
  tels quels — aucun renumérotage ; recherche, unicité et affichages
  fonctionnent à l'identique (le matricule est un CharField opaque pour tous
  les modules consommateurs).
- Migrations : `0009` ajoute le champ (+ résorption d'un drift
  modèle↔migrations préexistant sur Room/RoomType/School), `0010` configure
  le préfixe FEBA pour l'établissement existant (réversible).

## BUG N°9 — Erreurs console & warnings

**Corrections effectuées** :

| Problème | Fichier | Correctif |
|---|---|---|
| `<div>` rendu directement dans `<table>` (erreur React `validateDOMNesting`) | `admin/Grades.jsx` | barre d'actions groupées déplacée au-dessus du tableau |
| `colSpan={7}` pour 8 colonnes | `admin/Grades.jsx` | `colSpan={8}` |
| Onglets Notes non responsives (capture fournie) | `admin/Grades.jsx` | `flex-wrap + max-w-full + whitespace-nowrap` |
| Prop `rows` dupliquée sur `<textarea>` (erreur JSX) | `Messages.jsx` ×4 (admin/enseignant/parent/élève) | prop unique `rows={6}` |
| Éléments JSX sans `key` dans un tableau (warning React) | `admin/Payments.jsx` | `key` ajoutées |
| Reconnexion WebSocket replanifiée après démontage (fuite + erreurs) | `hooks/useWebSocket.js` | reconnexion annulée au cleanup (`active` + `clearTimeout`) |
| `userFilesAPI.update` envoyait `{headers}` comme payload | `api/index.js` | payload transmis correctement |
| Bouton « Annuler » mort sur la suppression d'utilisateur | `admin/Users.jsx` | `onClose` au lieu d'`onCancel` |
| `TypeError: None > 0` cassait le bulletin annuel dès qu'un trimestre était vide | `bulletins/pdf_generator.py` | `any(v is not None …)` |
| Logs pollués par des stacktraces pour l'absence (normale) de branding | `schools/models.py` | repli silencieux `filter().first()` |
| Rate-limit du login qui cassait toute la suite de tests | `settings/dev.py` | mode test : `RATELIMIT_ENABLE=False`, cache mémoire, hachage rapide |

**Balayage console automatisé** (Chromium/Playwright, ~46 pages sur les 5
rôles avec les comptes de démo) : plus d'erreur applicative — seules
subsistent les tentatives WebSocket (`/ws`) lorsque le serveur Channels
n'est pas lancé en dev local, comportement attendu hors Docker.

## Audit global — anomalies supplémentaires détectées et corrigées

1. **Suite de tests inutilisable** (79 échecs avant correctifs) :
   - le rate-limit du login (Redis, 20/min) bloquait ~80 tests ;
   - `test_parent_student.py` mettait en cache module une école supprimée par
     le rollback inter-tests (`School.DoesNotExist` au login) ;
   - le test de concurrence laissait 2 connexions DB ouvertes (threads) → la
     destruction de la base de test échouait ;
   - `test_tenant_security.py` créait des `Class`/`ClassSchedule` sans
     `level`/`subject` (NOT NULL).
   → **152 tests passent désormais** (128 existants réparés + 24 nouveaux).
2. **Dashboard admin** : les élèves sans compte lié disparaissaient des KPI.
3. **Message d'erreur « compte déjà associé »** : le `UniqueValidator`
   auto-généré court-circuitait le message métier clair de `validate_user`
   (`students/serializers.py`).
4. **ESLint absent** : configuration flat (eslint 9 + react + react-hooks)
   ajoutée + script `npm run lint` → 0 erreur.
5. **Sélection groupée cassée sur 3 écrans admin** (détectée par le balayage
   console) : dans `admin/Bulletins.jsx`, `admin/Homework.jsx` et
   `admin/Announcements.jsx`, les props `selectable` / `onBulkDelete` /
   `bulkDeletePending` destinées à `DataTable` étaient posées par erreur sur
   une icône (`<Download>`, `<Pencil>`, `<Eye>`) — warnings React « unknown
   prop » en console et cases de sélection/suppression groupée absentes.
   Props remises sur `DataTable` : la sélection groupée fonctionne sur les
   trois écrans et la console est propre.

## Tests ajoutés (backend/tests/test_bug_fixes_v45.py — 24 tests)

- `BilingualFormulaTests` (3) : formule 60/40 (moteur + endpoint + libellé) ;
- `ClassStatsTests` (2) : min/max de classe, classe vide ;
- `BulletinGenerationTests` (3) : PDF généré sans rang, contenu PDF réel
  vérifié (sections FR/EN, min/max, formule 60 %, absence de « Rang »),
  bulletin annuel avec trimestres manquants ;
- `DashboardTests` (2) : moyenne générale élève et parent ;
- `AdminUserManagementTests` (4) : rôles autorisés/interdits, escalade,
  visibilité ;
- `SchoolYearCrudGuardTests` (5) : suppressions protégées/autorisées,
  création sans `school`, modification ;
- `MatriculeTests` (5) : format, séquence, unicité, compatibilité anciens,
  dérivation de préfixe, indépendance par établissement.

## Endpoints créés ou modifiés

| Endpoint | Changement |
|---|---|
| `DELETE /api/schools/years/{id}/` | gardes d'intégrité (409 année active / utilisée + détail des dépendances) |
| `POST /api/schools/years/` | fonctionne sans champ `school` (tenant auto-résolu) |
| `GET /api/dashboard/student/` | + `average` (annuelle), `average_t3`, `annual_average`, `appreciation`, `progression` |
| `GET /api/dashboard/parent/` | + `average` (annuelle), `average_t1/t2/t3`, `appreciation`, `progression` par enfant |
| `GET /api/dashboard/admin/` | comptage corrigé (élèves sans compte lié) |
| `GET /api/grades/bilingual/` | formule 60/40 (valeurs + libellé) |
| `POST /api/bulletins/generate*` | nouveau PDF FR/EN + stats min/max, `rank_in_class` désormais null |

## Migrations ajoutées

- `schools/0009_school_matricule_prefix_alter_room_custom_type_label_and_more.py`
- `schools/0010_feba_matricule_prefix.py` (données, réversible)

## Liste exhaustive des fichiers modifiés

**Backend (16)** : `feba_project/settings/dev.py`, `apps/grades/models.py`,
`apps/grades/views.py`, `apps/bulletins/pdf_generator.py`,
`apps/dashboard/views.py`, `apps/schools/models.py`, `apps/schools/views.py`,
`apps/schools/serializers.py`, `apps/schools/migrations/0009_*.py` (nouveau),
`apps/schools/migrations/0010_*.py` (nouveau),
`apps/schools/management/commands/seed_demo_data.py`,
`apps/students/models.py`, `apps/students/serializers.py`,
`requirements/dev.txt`, `tests/test_bug_fixes_v45.py` (nouveau),
`tests/test_class_promotion_and_summary.py`, `tests/test_parent_student.py`,
`tests/test_tenant_security.py`

**Frontend (23)** : `package.json`, `eslint.config.js` (nouveau),
`src/api/index.js`, `src/hooks/useAuth.js`, `src/hooks/useWebSocket.js`,
`src/pages/admin/{Announcements,Bulletins,Enrollments,Grades,Homework,Messages,Payments,Settings,Users}.jsx`,
`src/pages/parent/{Bulletins,Home,Messages}.jsx`,
`src/pages/student/{Bulletins,Grades,Home,Messages}.jsx`,
`src/pages/teacher/Messages.jsx`

## Checklist de validation

| Point | Statut | Preuve |
|---|---|---|
| Bulletins réorganisés avec séparation FR / EN | ✅ | PDF inspecté + test `test_bulletin_pdf_contains_fr_and_en_sections` |
| Rang supprimé du bulletin | ✅ | PDF sans « Rang », `rank_in_class=None`, listes UI nettoyées |
| Moyennes minimales FR, EN, bilingues affichées | ✅ | tableau « Statistiques de la classe » + `ClassStatsTests` |
| Moyennes maximales FR, EN, bilingues affichées | ✅ | idem |
| Moyenne générale sur le tableau de bord Élève | ✅ | API : `average: 12.62` (données démo) + test |
| Moyenne générale sur le tableau de bord Parent | ✅ | API : moyennes par enfant + test |
| Menu Admin : création Élève / Parent / Enseignant | ✅ | page `/admin/users` + créations 201 vérifiées |
| Création Admin / Super Admin interdite à l'Admin | ✅ | 400 vérifié (création ET modification de rôle) |
| CRUD complet des années scolaires | ✅ | POST 201 / PATCH 200 / DELETE 200 / 409 actifs vérifiés |
| Formule bilingue 60 % FR / 40 % EN partout | ✅ | grep exhaustif + tests + PDF |
| Plus de doublons dans les listes de classes | ✅ | dédoublonnage id + cascade année→classes |
| Matricule `FEBA_26_0001` | ✅ | `MatriculeTests` (5 tests) + génération réelle vérifiée |
| Console navigateur sans erreurs critiques | ✅ | balayage Playwright 5 rôles + correctifs DOM/props/keys |
| APIs backend sans erreurs | ✅ | 152 tests OK + scénarios API rejoués |
| Scénarios fonctionnels testés | ✅ | boucle corriger→tester→retester appliquée à chaque bug |
