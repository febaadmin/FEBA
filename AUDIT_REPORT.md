# AUDIT_REPORT.md — Missions V4 → V8

## Audit V8 (26/07/2026)

### Anomalies trouvées et corrigées

| # | Domaine | Anomalie | Gravité | Correction |
|---|---|---|---|---|
| 1 | Profils | Matricule enseignant généré via `count()+1` → collision d'unicité → **500** | Critique | Génération sur le **max existant** + reprise + création atomique |
| 2 | Sécurité | Filtrage multi-établissement **inopérant** sur les champs DRF `many=True` | **Élevée** | `child_relation.queryset` + test dédié |
| 3 | Transparence | « L'équipe technique a été notifiée » **sans aucune notification** | Élevée | Système d'incidents réel + message honnête avec référence |
| 4 | Notes | Poids d'évaluation hétérogènes (examen ×3) | Métier | Poids unique 1 + migration + source centralisée |
| 5 | Bulletins | Primaire noté /20 au lieu de /10 | Métier | Barème par `Level.order`, conversion unique |
| 6 | Documents | Mauvais cachet sur les reçus | Métier | Cachet SECRÉTARIAT sur reçus, DIRECTION sur bulletins |
| 7 | Documents | Cachet débordant d'une cellule fixe (chevauchement date/signature) | Moyenne | Bloc dédié insécable |
| 8 | Documents | Nom de l'école chevauchant l'adresse (reçu) | Moyenne | Interligne proportionnel |
| 9 | Documents | « Moy. Pond. » sur /20 face à une moyenne /10 | Moyenne | Pondérée exprimée dans le barème affiché |
| 10 | Documents | **Observations tronquées** au bord droit du reçu | Moyenne | Valeurs longues en `Paragraph` (repli) |
| 11 | Incidents | `resolved_at` non renseigné par un PATCH de statut | Faible | Règle portée par le serializer |
| 12 | Migrations | Dérive de l'état du modèle (`note_coefficient`) | Faible | Migration `grades/0012` ; `makemigrations --check` propre |

### Points vérifiés sans anomalie

Authentification et sessions ; rôles et permissions (403/401 conformes) ;
multi-établissement (après correctif n°2) ; transactions et rollback ;
contraintes d'unicité (validées sur PostgreSQL) ; calculs de moyennes et
arrondis ; appréciations et lettres ; notes (10 reste 10 — V7) ; bulletins et
reçus ; paiements ; notifications ; tableau de bord Parent ; site vitrine
(carrousel, galerie, vidéo, menu, formulaires) ; migrations ; build de
production.

### État final

Backend **393** (SQLite) / **394** (PostgreSQL) ; frontend **70** ; ESLint
**0 erreur** ; build **OK**. Aucune régression critique constatée.


## Audit V7 (25/07/2026)
Anomalie critique corrigée : altération silencieuse des notes (10→9,5/9,75) — cause frontend
(input number step + molette), non un bug backend (DecimalField sain). Autres : noms officiels
harmonisés (source unique branding.py), cachet sur documents, médias (façade, vidéo, admissions).
Suites complètes rejouées : backend 311 (+1 skip), frontend 70, eslint 0 erreur, build OK.
Anciennes corrections V4→V6.2 non régressées (couvertes par leurs suites).


## Audit global V6 (20/07/2026)

Audit réalisé après P1–P7, sur l'ensemble du projet, en rejouant la **suite
complète** (et non un sous-ensemble).

### Anomalies détectées et corrigées

| Sujet | Constat | Action |
|---|---|---|
| Point focal galerie | `test_website` échouait : assertion figée sur l'ancien focal `academique-participation` (`82% 28%`), désormais volontairement `26% 64%` (recadrage V6 hors mur crème) | Assertion alignée sur la valeur seedée |
| Traductions | 4 clés dupliquées (`no-dupe-keys`) introduites avec les libellés de saisie groupée → `eslint` 4 erreurs | Doublons retirés (valeurs EN identiques) → 0 erreur |

### Sécurité (P7)

| Sujet | Constat | Action |
|---|---|---|
| Saisie groupée | Permissions **strictement backend** : enseignant limité à ses matières/classes, filtrage établissement (anti-IDOR), parent 403, anonyme 401 ; atomicité `transaction.atomic` (aucune écriture partielle) ; appréciation calculée backend | Implémenté + 16 tests backend + 6 frontend + E2E réel |

### État final V6

- Backend : **300 tests OK** (+1 skip concurrence PostgreSQL documenté).
- Frontend : **56 tests OK**, `eslint` **0 erreur**, build prod OK.
- Anciennes corrections (V4/V5) : non régressées — couvertes par les suites
  `test_note_types_appreciations`, `test_password_reset`,
  `test_parent_averages_missing_period`, `test_priority_fixes`,
  `test_tenant_security`, `parent/Home.test.jsx`, toutes vertes ; page notes
  enseignant vérifiée en navigateur (appréciations V4 correctes).

---

# AUDIT_REPORT.md — Mission V4 (19/07/2026)

Audit réalisé APRÈS livraison des quatre priorités, sur l'ensemble du
projet (le projet avait déjà bénéficié d'audits successifs V29→V45 puis de
l'audit bilinguisation — archivés dans `docs/`). Constats et actions de la
passe V4 :

## 1. Sécurité

| Sujet | Constat | Action |
|---|---|---|
| Permissions réinitialisation mdp | Nouvelles règles strictement vérifiées côté backend (`can_reset_password_of`), 403 sur contournement par ID, périmètre établissement respecté | Implémenté + 23 tests |
| Sessions après réinitialisation | Blacklist de tous les refresh tokens de la cible ; l'auteur conserve sa session ; l'access token résiduel expire (≤ 60 min, configurable) | Implémenté + testé ; voir SECURITY_NOTES |
| Journalisation | `PasswordResetLog` + logs applicatifs sans aucun secret | Vérifié par test |
| Formulaires publics | Validation backend, honeypot, rate-limit IP (5/min), aucune lecture publique des soumissions (401/405), champs saisis par les familles en lecture seule côté admin | Implémenté + testé |
| Endpoints admin du CMS | `IsAuthenticated + IsAdminOrAbove` sur tout `/api/website/admin/**` (anonyme → 401, parent → 403, testés) | Testé |
| `manage.py check` | Aucun problème signalé | — |
| Site public vs ERP | Instance axios publique séparée (aucun jeton envoyé, pas d'intercepteur de déconnexion) ; robots.txt désindexe les espaces privés | Implémenté |

## 2. Logique métier

| Sujet | Constat | Action |
|---|---|---|
| Appréciations dupliquées | `seed_demo_data` recalculait ses propres seuils (« Excellent travail »…) divergents du moteur | Centralisé sur `get_appreciation` |
| Appréciations stockées | `Bulletin.appreciation` contenait l'ancienne échelle | Migration de données réversible `bulletins/0005` |
| Valeurs invalides | L'ancienne fonction classait silencieusement n'importe quelle valeur | `ValueError` sur note hors [0, barème], barème ≤ 0, non numérique |
| Types de notes | Valeurs internes déjà stables (`interrogation`, `examen`) — seuls les libellés changent : compatibilité totale des anciennes données | Vérifié en navigateur sur données seedées |

## 3. Frontend

| Sujet | Constat | Action |
|---|---|---|
| Bundle unique 1,5 Mo | Toutes les pages ERP importées statiquement : un visiteur du site public téléchargeait tout l'ERP | Router 100 % lazy : 407 → 113 Ko gzip au premier chargement |
| Clé i18n dupliquée | `Réinitialiser` définie deux fois (erreur eslint) | Supprimée |
| Appréciations non traduites | Les cellules affichaient la chaîne backend brute en mode EN | Passage par `t()` + dictionnaire EN des 9 libellés |
| 404 | URL inconnue → page de connexion (impression de déconnexion) sur les anciennes versions ; la passe bilingue l'avait déjà corrigé côté ERP | V4 : 404 publique du site vitrine, session intacte, header « Mon espace » |
| eslint global | 0 erreur (warnings préexistants de style/compiler conservés) | — |

## 4. Revérification des anciens correctifs (mission précédente)

| Sujet | Vérification V4 (navigateur) | Résultat |
|---|---|---|
| Tableau de bord Parent | `/parent/home` : rendu complet, aucune page blanche ni TypeError, données chargées | ✅ |
| Moyennes Parent | 4 cartes affichées (générale, française, anglaise, bilingue), valeurs cohérentes, aucun tiret indu | ✅ |
| Notifications | Clic cloche : panneau OK ; clic notification : ouvre la page Notes (activité correcte), session conservée, pas de redirection forcée vers les annonces | ✅ |
| Changement de mot de passe personnel | Parcours `change-password` inchangé et re-testé (utilisé par le flux must_change_password) ; le drapeau est levé à la réussite | ✅ |

## 5. Points suivis mais non bloquants

- Suite PostgreSQL (`settings.test_postgres` via Docker) non exécutée :
  Docker indisponible sur la machine pendant la mission. La suite SQLite
  complète (280 tests) passe ; le seul test dépendant de PostgreSQL est
  skippé avec justification. À rejouer sur un poste avec Docker
  (commande dans README / KNOWN_LIMITATIONS).
- Warnings Django préexistants (STATICFILES_STORAGE déprécié,
  pagination non ordonnée sur un queryset) : inchangés, hors périmètre.
- L'admin Django (`/django-admin/`) sert d'interface de gestion des slides
  et de la galerie ; l'écran React « Site vitrine » couvre messages,
  préinscriptions, actualités et paramètres (le plus opérationnel).

## 6. Tableau récapitulatif final

| ID | Priorité | Module | Problème / besoin | Cause | Fichiers modifiés (principaux) | Correction | Tests exécutés | Résultat | Statut |
|----|----|----|----|----|----|----|----|----|----|
| V4-01 | P1 | Notes | Libellés « Interrogation », « Examen » à renommer partout | Libellés portés par les choices backend + listes frontend | grades/models.py, migration 0010, admin/teacher Grades.jsx, translations.js | Libellés renommés, valeurs internes stables | pytest test_note_types_appreciations (19) + création/modif UI navigateur | 280 ✅ backend, UI vérifiée | Corrigé et testé |
| V4-02 | P3 | Notes/Bulletins | Nouveau barème officiel 9 niveaux | Ancienne échelle 6 niveaux codée dans get_appreciation + seuils dupliqués dans le seed + valeurs stockées | grades/models.py, seed_demo_data.py, bulletins/0005, pages React (t()) | Fonction centrale + normalisation + rejets + migration | Bornes exhaustives + balayage 0,01 + barèmes ≠20 + API + navigateur | ✅ | Corrigé et testé |
| V4-03 | P2 | Comptes | Réinitialisation mdp par admin/superadmin absente | Fonctionnalité inexistante | accounts (models/serializers/views/urls + migration 0005), ResetPasswordModal, ForcePasswordChange, router, useAuth, Users/Admins.jsx | Endpoint sécurisé + UI + parcours forcé + audit log + révocation tokens | pytest test_password_reset (23) + parcours navigateur complet | ✅ | Implémenté et testé |
| V4-04 | P4 | Site public | Site vitrine à créer, « / » devait devenir public | Application 100 % ERP | apps/website (complet), frontend/src/site (18 fichiers), router, index.html, robots/sitemap, tailwind, scripts/optimize_site_media.py | Site 13 pages + CMS + formulaires + SEO + médias optimisés | pytest test_website (19), vitest site (13), E2E desktop+mobile, build prod | ✅ | Implémenté et testé |
| V4-05 | Audit | Frontend | Visiteurs téléchargeaient l'ERP entier (1,5 Mo) | Imports statiques du routeur | router/index.jsx | Lazy loading intégral | vite build (chunks), navigateur | 407→113 Ko gzip | Corrigé et testé |
| V4-06 | Audit | i18n | Clé dupliquée (erreur eslint) | Ajout V4 en double d'une clé existante | translations.js | Doublon supprimé | eslint --quiet, vitest | 0 erreur | Corrigé et testé |
| V4-07 | Audit | Outillage | Impossible de tester le build prod localement | vite preview sans proxy API | vite.config.js | Proxy preview | vite preview + navigateur | ✅ | Corrigé et testé |
| V4-08 | Suivi | Tests | Suite PostgreSQL non rejouée | Docker indisponible sur la machine | — | Procédure documentée | — | — | Bloqué par une dépendance externe |
