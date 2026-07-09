# FEBA v32 — Rapport : bugs critiques (années scolaires, bulletins PDF, moyennes, UI notes)

Date : 06/07/2026 · Base : v31 · Diagnostic depuis les 8 captures fournies + analyse croisée UI → API → services → modèles → base.

---

## 1. Création des années scolaires (priorité n°1)

**Symptôme** (capture « Nouvelle année scolaire ») : la création renvoie une page d'erreur Django brute — `IntegrityError` sur `schools_schoolyear.school_id`.
**Cause racine** : le formulaire envoyait bien l'établissement (`school: school?.id`), mais `SchoolYearViewSet.perform_create` faisait `serializer.save(school=get_request_school(request))` — soit `school=None` pour un **superadmin** — **écrasant** la valeur du payload et violant la contrainte NOT NULL. Aggravants : aucune validation métier (fin ≤ début acceptée, doublons de nom acceptés jusqu'à l'erreur SQL), pas de garantie « une seule année active », pas d'action de clôture.
**Corrections (chaîne complète)** :
- `perform_create` : résolution du tenant — établissement de l'utilisateur → sinon celui du payload → sinon, cas mono-établissement, l'unique établissement → sinon erreur 400 explicite (« Précisez l'établissement… »). Plus aucune 500.
- Sérialiseur : `fin > début` obligatoire ; **nom unique par établissement** avec message clair ; messages requis en français.
- Modèle + **migration `schools/0007`** : contrainte d'unicité `(school, name)` en base (avec dé-doublonnage préalable des éventuels homonymes existants, relations réaffectées).
- Règle « une seule année active » garantie à la création, à la modification et via `set_current` ; **nouvelle action `close/`** (clôturer l'année active) + bouton « Clôturer » dans Paramètres.
- 5 tests : création superadmin (payload / mono-établissement), fin ≤ début rejetée, doublon rejeté avec message, unicité de l'année active + clôture.

## 2. « Détail de la note » mal positionné en desktop (priorité n°2)

**Cause racine** : deux mises en page distinctes dans `Grades.jsx` — bottom-sheet `fixed` en mobile (correct) mais, en desktop, `lg:static lg:col-span-2` : le panneau devenait une **colonne latérale collée à droite du tableau** (grille 3/5–2/5), sans fond ni centrage, contrairement aux autres formulaires (composant Modal centré).
**Correction** : en desktop le panneau devient une **modale centrée** (`fixed inset-0 flex items-center justify-center` + fond sombre cliquable + largeur max + coins arrondis + contenu défilant), le tableau reprend toute la largeur ; le comportement mobile (bottom-sheet + poignée) est conservé à l'identique.

## 3. Bulletins : PDF → `DNS_PROBE_FINISHED_NXDOMAIN` (priorité n°3)

**Symptôme** : cliquer un bulletin ouvre `http://backend-dev:8000/media/bulletins/….pdf` — hôte **interne Docker**, irrésoluble par le navigateur.
**Cause racine** : 13 endroits construisaient des **URLs absolues** via `request.build_absolute_uri(...)`. En dev, les requêtes passent par le proxy Vite (`changeOrigin: true`) : Django voit `Host: backend-dev:8000` et fabrique des liens sur cet hôte. Le problème touchait TOUS les médias : bulletins, photos élèves/parents, reçus de paiement, pièces jointes de devoirs, logos.
**Correction (définitive, zéro URL codée en dur)** : toutes les URLs médias renvoyées par l'API sont désormais **relatives** (`/media/...`) — 13 occurrences corrigées, 0 restante. Elles se résolvent sur l'origine du client : en dev via le proxy Vite `/media` (déjà configuré), en prod via le bloc Nginx `location /media/` (déjà configuré). Aucune variable ni configuration supplémentaire requise ; le même code fonctionne dans les deux environnements.

## 4. Moteur de calcul des moyennes (priorité n°4)

**Audit** : le moteur est bien **centralisé** dans `Grade` (`get_subject_averages` → moyenne par matière pondérée par les coefficients de notes ; `calculate_average` → moyenne générale pondérée par les coefficients de matières ; annuel = moyenne des trimestres renseignés ; bilingue FR 40 % / EN 60 %). Bulletins PDF, endpoint `averages/`, résumé par élève et classement l'utilisent tous. **Deux défauts graves** ont toutefois été trouvés, visibles sur votre capture (« 0.00/20 F — Note automatique (aucune note saisie) ») :
1. **Injection de zéros réels** : la génération de bulletin appelait `_ensure_zeros_for_period`, qui **créait des notes 0/20 permanentes** pour chaque matière non notée (+ un endpoint public `ensure-zeros`). Le carnet de notes était pollué et les moyennes effondrées.
2. **Zéro implicite dans le moteur** : une matière sans note recevait `average = 0` et entrait dans la moyenne générale **avec son coefficient**.

**Corrections (règle métier : une matière non notée n'est pas un zéro)** :
- Moteur : matière sans note → `average = None`, lettre « — », **exclue** des moyennes générale, bilingue et annuelle (seuls les trimestres notés comptent). Un élève noté 16 en Maths (coeff 4) et non noté en Français (coeff 2) a désormais 16.00 de moyenne — plus 10.67.
- Générateur PDF : suppression de l'injection de zéros ; les matières non notées s'affichent « Non noté / — » ; tous les affichages rendus sûrs face à `None` (lignes trimestre, colonnes annuelles T1/T2/T3, moyenne générale, rang).
- Suppression de l'endpoint `ensure-zeros` et de son entrée API frontend (fonctionnalité mal conçue remplacée, conformément à la mission).
- **Migration de données `grades/0008`** : les notes automatiques 0/20 déjà créées sont marquées supprimées (soft-delete → exclues des calculs, audit conservé) — vos moyennes existantes redeviennent justes après `migrate`.
- Seeder aligné : les bulletins de démonstration utilisent `Grade.calculate_average` (identité bulletins ↔ tableaux de bord ↔ pages élèves garantie par construction : une seule implémentation).
- 3 tests : exclusion des matières non notées, moyenne None sans aucune note, double pondération (coeff de note × coeff de matière) vérifiée numériquement.

## 5. Parents invisibles selon l'année (captures Parents)

**Cause racine** : même anti-modèle que la liste élèves (v31) — le filtre année passait par le **pointeur** `student.school_year` au lieu de l'historique des inscriptions : un parent disparaissait des années passées dès la promotion de son enfant.
**Correction** : filtre via `children_links__student__enrollments__school_year` (avec repli sur le pointeur) + `distinct()`, dans les deux branches (admin et non-admin).

## 6. Vérifications (boucle analyser → corriger → vérifier, rejouée après chaque lot)

Backend : 210+ fichiers compilent ; graphe de migrations intègre (56 fichiers, dont les 2 nouvelles) ; plus **aucun** `build_absolute_uri` sur des médias. Frontend : 76 fichiers, 0 erreur de syntaxe ; tous les imports résolvent ; tous les appels `xxxAPI.méthode()` correspondent à des définitions réelles. Suites de tests enrichies (8 nouveaux tests v32, s'ajoutant aux suites tenant/années/promotions/salles virtuelles). Les validations d'exécution restent à rejouer chez vous : le guide d'installation contient la **check-list portée à 19 scénarios** (§11), couvrant précisément chaque bug de cette mission (création/activation/clôture d'année, modale de note centrée, moyennes sans zéros, ouverture des PDF de bulletins, photos/reçus/justificatifs).

## 7. Fichiers modifiés

| Fichier | Nature |
|---|---|
| `backend/apps/schools/views.py` / `serializers.py` / `models.py` / `migrations/0007` | Année scolaire : tenant, validations, unicité DB, close/ |
| `backend/apps/grades/models.py` | Moteur central : matières non notées exclues (générale, bilingue) |
| `backend/apps/grades/views.py` | Suppression endpoint + helper `ensure-zeros` |
| `backend/apps/grades/migrations/0008` | Nettoyage des notes 0 automatiques existantes |
| `backend/apps/bulletins/pdf_generator.py` | Plus d'injection de zéros ; rendus None-safe |
| `backend/apps/{bulletins,students,parents,teachers,payments,homework,user_files,schools}` (serializers/views/models) | 13 URLs médias absolues → relatives |
| `backend/apps/parents/views.py` | Filtre année via l'historique des inscriptions |
| `backend/apps/schools/.../seed_demo_data.py` | Bulletins via le moteur central |
| `frontend/src/pages/admin/Grades.jsx` | Détail de la note : modale centrée desktop, bottom-sheet mobile conservé |
| `frontend/src/pages/admin/Settings.jsx` + `api/index.js` | Bouton/API « Clôturer l'année » ; retrait de `ensureZeros` |
| `backend/tests/test_years_and_averages.py` | 8 nouveaux tests de régression |
| Guides PDF | Check-list de validation portée à 19 scénarios |
