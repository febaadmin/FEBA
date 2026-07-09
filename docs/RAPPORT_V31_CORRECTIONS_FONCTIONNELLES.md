# FEBA v31 — Rapport de mission complémentaire : bugs fonctionnels & seeders

Date : 06/07/2026 · Base : v30 · Diagnostic effectué à partir des 8 captures d'écran fournies et de l'analyse croisée frontend ↔ API ↔ backend ↔ base de données.

---

## 1. Bugs détectés, causes racines et corrections

### 🔴 B1 — Listes « Année scolaire » vides partout (Inscriptions : passage de niveau, passage par classe, inscription individuelle, assistant)
**Symptôme** (captures 2, 5, 8) : les sélecteurs d'années n'affichent que « — Sélectionner — » ; toasts « Classe source et année cible requises » / « Sélectionnez une année scolaire ». Le passage en classe supérieure est donc inutilisable.
**Cause racine** : `Enrollments.jsx` appelle `schoolsAPI.listYears()` — **méthode inexistante** (le client API définit `years()`). L'appel lève `TypeError` silencieusement dans React Query → tableau vide. Le backend, lui, renvoyait correctement les années.
**Correction** : appel corrigé → `schoolsAPI.years()`. **Prévention** : un vérificateur systématique a comparé *tous* les appels `xxxAPI.méthode()` du frontend aux définitions réelles — c'était la seule occurrence ; ce contrôle est rejouable.

### 🔴 B2 — Création d'utilisateur : « Établissement : Un établissement est requis pour ce rôle »
**Symptôme** (captures 1, 3) : impossible de créer un élève/enseignant/parent depuis /superadmin/users.
**Cause racine** : la validation backend est **correcte** (tout rôle non-superadmin doit être rattaché à un établissement — fondement du multi-tenant). Le bug est frontend : les formulaires superadmin (`Users.jsx`, `Admins.jsx`) **n'ont aucun champ Établissement** et n'envoient jamais `school`.
**Correction** : champ « Établissement* » ajouté aux deux formulaires — affiché dynamiquement dès que le rôle choisi n'est pas superadmin (comportement conforme à votre matrice : superadmin sans établissement, tous les autres rôles avec établissement obligatoire) ; liste alimentée par l'API schools ; envoyé en création **et** en modification ; forcé à null pour un superadmin.

### 🔴 B3 — Liste des élèves vide sur les années passées (« 0 élève(s) — 2023-2024 »)
**Symptôme** (capture 4) : sélectionner une année antérieure vide la liste, alors que l'historique de l'élève montre bien une inscription cette année-là.
**Cause racine** (architecture) : le filtre `?school_year=` interrogeait `Student.school_year` — un **pointeur « année courante »** déplacé à chaque promotion — au lieu de l'historique `StudentEnrollment`. Exactement l'anti-modèle « déplacement de données » que la mission proscrit. Aggravant : `school_year` figurait aussi dans `filterset_fields`, donc django-filter ré-appliquait le filtre cassé même après correction manuelle.
**Correction** : le filtre interroge désormais `enrollments__school_year` (avec repli sur le pointeur pour les élèves jamais formellement inscrits) + `distinct()` ; `school_year` retiré de `filterset_fields`. Le sérialiseur devient **sensible à l'année demandée** : colonnes Classe / Niveau / Année affichent la classe **de l'inscription de cette année-là** (préchargements ajustés, zéro N+1).

### 🔴 B4 — Toutes les opérations de promotion échouaient pour un superadmin
**Symptôme** : « Établissement introuvable » sur passage de niveau / par classe / individuel / assistant fin d'année (rôle utilisé dans tous vos tests).
**Cause racine** : ces endpoints résolvaient le tenant via `get_request_school()`, qui renvoie **None pour un superadmin** (il n'appartient à aucun établissement). Le service refusait alors, correctement, d'opérer sans tenant.
**Correction** (à la racine, pas un contournement) : nouvelle résolution `resolve_school_for_year()` — pour un superadmin, le tenant est **déduit de l'année scolaire cible**, qui appartient sans ambiguïté à un établissement. Appliquée aux 4 endpoints (`enroll-all-from-year`, `enroll-class`, `promote`, `end-of-year-assistant`) et à la **création d'élève** par un superadmin (tenant déduit de l'année fournie). Pour les autres rôles, rien ne change : le contrôle tenant élève-par-élève du service reste la barrière de sécurité.

### 🟠 B5 — Historique élève : badge « Actuel » sur toutes les années
**Symptôme** (capture 6) : chaque ligne de l'historique porte « Actuel ».
**Cause racine** : le badge lisait `enrollment.is_active` — vrai pour **toute** inscription valide (le flag signifie « inscription non annulée », pas « année en cours »).
**Correction** : nouveau champ sérialisé `is_current_year` (vrai uniquement si `school_year.is_current`) ; l'UI affiche « Année active » sur la seule année en cours. Ajout de `promotion_status_label` (libellé lisible).

### 🟠 B6 — Historique élève incomplet (exigence n°3 de la mission)
**Correction / évolution** : l'endpoint `GET /students/{id}/history/` renvoie désormais, **pour chaque année** : classe, décision de passage, et un bloc `stats` — moyenne réelle et nombre de notes, absences / retards / justifiées, total payé et nombre de paiements, bulletins, devoirs de la classe. L'onglet « Historique élève » affiche ce dossier par année ; changer d'élève ou d'année actualise tout. La page Élèves (avec B3) permet la consultation N-1/N-2/N-3 sans perte.

### 🟠 B7 — « Salle : Aucun résultat » dans Nouveau créneau (capture 7)
**Cause racine** : pas un bug de code (l'API des salles fonctionne pour tous les rôles) — **aucune salle n'existe** après une installation propre. C'est le déficit de données de démonstration (mission n°5).
**Correction** : couvert par le seeder (6 salles physiques) — voir §2.

### ✅ Vérifié conforme (aucune correction nécessaire)
Le **modèle d'inscription annuelle** exigé (Élève → Inscription → Année → Classe/Niveau, données pédagogiques liées à l'inscription, promotion = nouvelle inscription sans toucher à l'historique) est en place et correct : `StudentEnrollment` unique par (élève, année), FK `enrollment` sur notes/absences/paiements/bulletins, service de promotion transactionnel tenant-safe couvrant passage individuel/massif/redoublement/changement de classe/départ/exclusion/diplômation, années ouvrables/clôturables via `is_current` + `set_current`. Les bugs ci-dessus étaient des défauts d'**exposition** (frontend, résolution tenant, filtre) de ce modèle sain — c'est pourquoi ils ont été corrigés au niveau exact de leur cause, sans reconstruire un socle déjà conforme.

---

## 2. Seeders — installation immédiatement exploitable (mission n°5)

La commande `seed_demo_data` (réécrite intégralement, idempotente, transactionnelle, graine aléatoire fixe pour la reproductibilité) génère :

un établissement ; **3 années scolaires calculées dynamiquement** (N-2, N-1, N active) ; 10 niveaux (CP1→3ème) ; **une classe par niveau et par année** (30 classes — indispensable au vrai historique puisque les classes appartiennent à une année) ; 10 matières FR/EN avec coefficients ; 6 salles physiques ; comptes superadmin/admins/enseignants/parents/élèves ; 30 élèves avec **parcours réaliste sur 3 ans** — progression de niveau (CE1→CE2→CM1…), un redoublant par classe, dates d'inscription rétrodatées à la rentrée de chaque année ; parents liés (2 enfants/parent, relations père/mère/tuteur) ; **notes des 3 années liées aux inscriptions annuelles** ; absences/retards/justifiées sur 2 ans ; paiements (inscription + mensualités) sur 3 ans liés aux inscriptions ; **bulletins T1–T3 avec moyennes calculées depuis les vraies notes** et appréciations ; emplois du temps de l'année courante (5 classes × 5 jours × 2 créneaux, salles affectées — corrige la capture 7) ; devoirs ; annonces ; notifications ; 2 salles virtuelles Jitsi.

Exécution : `make seed` ou `docker compose exec backend-dev python manage.py seed_demo_data`. Comptes démo documentés dans le guide d'installation (§5).

---

## 3. Tests (boucle de correction)

Nouveau fichier `tests/test_school_year_history.py` — chaque test verrouille une cause racine de cette mission : promotion en masse par un superadmin (B4) ; la promotion crée une nouvelle inscription **sans modifier** l'ancienne ; le filtre d'année passe par l'historique et renvoie la classe de l'année demandée (B3) ; l'endpoint history renvoie stats + `is_current_year` correct (B5/B6) ; création d'élève par superadmin avec tenant déduit de l'année (B4). S'ajoutent aux suites existantes (sécurité tenant, comptes, parents-élèves, salles virtuelles). Exécution : `make test`.

Vérifications statiques repassées après chaque lot de modifications (boucle analyser → corriger → vérifier) : 76 fichiers frontend analysés syntaxiquement (0 erreur), tous les imports résolus, **tous les appels API frontend validés contre leurs définitions** (0 méthode fantôme restante), 210+ fichiers Python compilés, graphe de migrations intègre. Aucune nouvelle migration n'était nécessaire (aucun changement de schéma). Les validations d'exécution (docker, suite de tests, parcours navigateur) sont à rejouer chez vous : la check-list complète de 13 scénarios figure au §11 du guide d'installation.

## 4. Récapitulatif des fichiers modifiés

| Fichier | Nature |
|---|---|
| `frontend/src/pages/admin/Enrollments.jsx` | B1 (listYears→years) + B5/B6 (historique enrichi, badge année active) |
| `frontend/src/pages/superadmin/Users.jsx` / `Admins.jsx` | B2 (champ Établissement dynamique, payload normalisé) |
| `backend/apps/students/views.py` | B3 (filtre via historique, prefetch), B4 (resolve_school_for_year × 5), B6 (history enrichi) |
| `backend/apps/students/serializers.py` | B3 (classe par année demandée), B5 (is_current_year, libellé décision) |
| `backend/apps/schools/management/commands/seed_demo_data.py` | Réécriture complète (mission n°5) |
| `backend/tests/test_school_year_history.py` | Nouveaux tests de régression |
| `scripts/generate_guides.py` + 2 PDF | Étape seed, comptes démo, guide de validation fonctionnelle (13 scénarios) |

## 5. Changelog v31
- **fix(frontend)** : appel API fantôme `listYears` → toutes les listes d'années se remplissent (débloque passage de niveau / par classe / individuel / assistant).
- **fix(frontend)** : sélecteur d'établissement requis selon le rôle dans les formulaires superadmin de création d'utilisateurs et d'admins.
- **fix(backend)** : filtre élèves par année via l'historique des inscriptions (+ retrait du filtre django-filter concurrent) ; classe/niveau/année affichés pour l'année demandée.
- **fix(backend)** : résolution du tenant depuis l'année cible pour les opérations superadmin (promotions, assistant, création d'élève).
- **fix(api/ui)** : badge « Année active » basé sur l'année en cours, plus sur `is_active`.
- **feat(api)** : `history/` renvoie le dossier annuel complet (moyenne, notes, absences, retards, paiements, bulletins, devoirs, décision).
- **feat(seed)** : seeder complet 3 années avec progression réaliste, tous modules.
- **docs** : guides PDF enrichis (seed, comptes démo, validation fonctionnelle 13 points).
