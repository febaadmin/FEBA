# VERIFICATION_CHECKLIST — mission bilinguisation + audit (16/07/2026)

Statuts : ✅ corrigé/conforme · 🟢 vérifié, aucun problème détecté · 🟡 partiellement couvert (détail en note)

## Hotfix post-livraison — page blanche /parent/home

| Élément | Statut |
|---|---|
| `t2 is not a function` (shadowing de la fonction t par `.map(([t, v]))`) | ✅ **Corrigé et testé dans le navigateur** — `frontend/src/pages/parent/Home.jsx`, garde statique `no-t-shadowing.test.js`, 22 tests Vitest verts, console 0 erreur |
| Error Boundary global | ✅ `components/ErrorBoundary.jsx` monté dans `App.jsx` (écran bilingue réessayer/retour, erreur tracée) |

## A. Les 30 problèmes obligatoires

| # | Point | Statut | Détection | Correction / preuve | Vérification |
|---|---|---|---|---|---|
| 1 | Application pas entièrement bilingue | ✅ | ~1 500 chaînes FR codées en dur | Système i18n central + dictionnaire ~1 050 entrées (`frontend/src/i18n/`) | Navigateur FR/EN + build |
| 2 | Page de connexion non bilingue | ✅ | Textes uniquement FR | Affichage « FR / EN » simultané partout (`LoginPage.jsx`) | Capture navigateur |
| 3 | Labels/placeholders/erreurs de connexion non bilingues | ✅ | idem | `tBoth()` sur labels, placeholders, bouton, erreurs zod + serveur, aria-labels | Capture navigateur + lecture code |
| 4 | Pas de sélecteur FR–EN après connexion | ✅ | Inexistant | `LanguageSwitcher` dans les 5 layouts | Capture navigateur (FR→EN) |
| 5 | Changement de langue non immédiat | ✅ | n/a | Remontage `<AppRouter key={lang} />` — bascule instantanée sans déconnexion | Capture navigateur |
| 6 | Langue non conservée | ✅ | n/a | localStorage + `preferred_language` serveur (PATCH auto) prioritaire au login | `test_i18n_preferences.py::test_language_restored_after_relogin` + PATCH 200 observé |
| 7 | Textes codés en dur | ✅ | 56 pages, 5 layouts, 12 composants | Codemod + passes manuelles (nœuds mixtes, ternaires, template literals, sous-titres) | Balayages grep successifs |
| 8 | Pages/fonctionnalités non traduites | ✅ | Toutes les pages concernées | Toutes traitées ; repli FR sûr pour tout reliquat | Extraction automatique : 0 clé manquante volontaire |
| 9 | Messages backend non traduits | ✅ | Messages FR bruts | `Accept-Language`+LocaleMiddleware (framework) + dictionnaire via `utils/errors.js` (métier) | Lecture code + dictionnaire |
| 10 | Bugs dans des pages « qui semblent marcher » | ✅ | Import debug_toolbar fragile ; shadowing `t` ; lookup JSON non portable | Corrigés (urls.py, renommages, `filter_targets_role`) | Tests + démarrage |
| 11 | Boutons/liens/menus non fonctionnels | 🟢 | Aucun bouton mort détecté sur les parcours vérifiés | — | Navigateur (login, dashboard, navigation) + revue code des handlers |
| 12 | Fonctionnalités incomplètes/simulées | 🟢 | Rien de simulé détecté ; fonctionnalités adossées à l'API réelle | — | Revue des ViewSets + parcours |
| 13 | Erreurs de logique métier scolaire | ✅ | Conflits d'emploi du temps non contrôlés ; doublons de présence possibles | Validations serveur ajoutées | `test_audit_validations.py` (11 tests) |
| 14 | Calculs (notes/moyennes/soldes) incorrects | 🟢 | Aucun écart détecté — formules couvertes par la suite dédiée (60/40, moyennes annuelles = moyenne des trimestres notés) | — | 220 tests verts dont suites moyennes/bulletins |
| 15 | Relations BDD incohérentes | 🟢 | FK/contraintes cohérentes ; suppression élève protégée si données liées | — | Lecture modèles + `test_year_isolation_deletion.py` |
| 16 | Autorisations seulement côté interface | 🟢 | Permissions DRF par action + tenant | — | `test_tenant_security.py` réexécuté + lecture `get_permissions()` |
| 17 | Routes accessibles sans autorisation | 🟢 | `IsAuthenticated` par défaut global + classes par rôle | — | Lecture settings/permissions + tests |
| 18 | Validations serveur manquantes | ✅ | Paiements (montant/date), présences (doublon/date), emploi du temps (chevauchements) | Ajoutées | 11 nouveaux tests |
| 19 | Erreurs mal gérées | ✅ | Page 404 authentifiée existante (V3) ; normalisation des erreurs API centralisée | Messages réseau/HTTP bilingues via `extractApiError` + dictionnaire | Lecture code + toasts observés |
| 20 | Anomalies cas limites | ✅ | Dates futures, montants ≤ 0, chevauchements | Validations + tests | `test_audit_validations.py` |
| 21 | Dépendances/configs incompatibles | ✅ | debug_toolbar/DEBUG ; proxy Vite docker-only ; creds test_postgres | Corrigés (urls.py, `BACKEND_ORIGIN`, `TEST_DB_*`) | Démarrages locaux effectués |
| 22 | Code inutilisé/dupliqué | ✅ | `allRoomTypeOptions` mort | Supprimé | Build OK |
| 23 | Problèmes de sécurité | 🟢 | Pas de vulnérabilité critique reproduite ; durcissements validations | § Sécurité de l'audit | Revue settings/serializers + tests |
| 24 | Erreurs de navigation/boucles | 🟢 | Corrigées en V3 (NotFound authentifié, `notification_path` par rôle) — vérifiées présentes | — | `test_priority_fixes.py` + revue router |
| 25 | Affichage mobile/tablette/EN | ✅ | RAS bloquant ; layouts responsives (sidebar mobile) | Vérifié en viewport étroit pendant la session navigateur | Captures (mobile ~460px) |
| 26 | Données enregistrées partiellement | 🟢 | Transactions présentes sur les opérations groupées (seed, passages) | — | Lecture services + tests |
| 27 | Opérations produisant des doublons | ✅ | Présences (API) ; inscriptions déjà protégées | Validation doublon présence ; `test_subject_dedup`, contrôles d'inscription existants | Tests |
| 28 | Suppressions cassant l'intégrité | 🟢 | Suppression définitive élève refusée si données liées ; soft-delete notes/paiements avec justification | — | `test_year_isolation_deletion.py` + lecture views |
| 29 | Concurrence | 🟢 | Test dédié multi-threads (liens parent-élève) vert sur PostgreSQL | Skip documenté sur SQLite uniquement | `220 passed` PostgreSQL |
| 30 | Tests absents/insuffisants | ✅ | Pas de tests i18n ni des validations ajoutées | +18 tests (7 i18n + 11 validations) → 220 au total | pytest |

## B. Parcours critiques exigés

| Parcours | Méthode | Résultat |
|---|---|---|
| Connexion identifiants valides | Navigateur (admin@feba.bj) + API | ✅ 200 + redirection dashboard |
| Connexion identifiants invalides | Navigateur + API | ✅ 400 + toast bilingue |
| Déconnexion | Code vérifié + test accounts existant (blacklist refresh) | ✅ |
| Changement FR→EN / EN→FR | Navigateur | ✅ immédiat |
| Persistance langue (refresh) | localStorage + remount | ✅ |
| Persistance langue (reconnexion) | Test API dédié | ✅ |
| Création/modification utilisateur | Tests accounts + serializers | ✅ |
| Création/modification élève | Tests students existants | ✅ |
| Inscription élève / affectation classe | Tests enrollment/promotion existants | ✅ |
| Création enseignant / affectation | Tests + serializer M2M classes/matières | ✅ |
| Présence/absence | Nouveaux tests validation + tests notifications | ✅ |
| Évaluation + saisie notes + validation | Tests grades (barème 0–20, coefficient) | ✅ |
| Calcul des moyennes | Suites moyennes (60/40, annuel) | ✅ |
| Génération bulletin | Tests bulletins (layout, moteur central) | ✅ |
| Frais scolaire + paiement + solde | Tests payments + nouvelles validations | ✅ |
| Permissions par rôle + accès interdit | `test_tenant_security.py` + permissions par action | ✅ |
| Données invalides | Nouveaux tests (montants, dates, chevauchements) | ✅ |
| Suppression donnée liée | `test_year_isolation_deletion.py` | ✅ |
| Mobile | Session navigateur en viewport étroit | ✅ |
| Pages principales FR + EN | Session navigateur | ✅ |

## C. Conditions de fin de mission

| Condition | Statut |
|---|---|
| Installation depuis copie propre | ✅ README §Installation (Docker et local sans Docker) |
| Dépendances sans erreur bloquante | ✅ (npm install présent ; pip requirements ; docker build OK) |
| BDD préparable + migrations | ✅ PostgreSQL : migrations complètes (0004 incluse) ; SQLite démo : `--run-syncdb` documenté |
| Application démarre | ✅ Docker (vérifié avant l'arrêt de Docker Desktop) + local sans Docker (vérifié de bout en bout) |
| Connexion/déconnexion | ✅ |
| Login bilingue | ✅ |
| Sélecteur après connexion | ✅ |
| FR et EN dans tous les modules principaux | ✅ |
| Préférence conservée | ✅ |
| Parcours scolaires testés | ✅ (suite 220 tests) |
| Calculs critiques vérifiés | ✅ |
| Permissions testées côté serveur | ✅ |
| Tests importants verts | ✅ 220/220 PostgreSQL |
| Pas d'erreur bloquante connue | ✅ |
| Pas de vulnérabilité critique reproductible connue | ✅ |
| Archive ZIP finale générée | ✅ `feba_v1_bilingual_audited_fixed.zip` |
| Rapport d'audit fourni | ✅ `AUDIT_REPORT.md` |
