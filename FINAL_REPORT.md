# FEBA — Rapport final : commentaires des bulletins et visioconférence multi-académies

26 octobre 2026 · branche `fix/feba-commentaires-visio` · base : archive
`FEBA_VERSION_FINALE_VALIDEE_PRODUCTION.zip` (commit `25b4c57`, empreinte
vérifiée). Commit livré : `SOURCE_COMMIT.txt` dans l'archive.

Statuts : **PASS** · **FAIL** · **BLOCKED** · **NOT RUN** · **SIMULATED**.
Détail des tests : `TEST_REPORT.md`. Limites : `KNOWN_LIMITATIONS.md` § 0000.
Actions de l'exploitant : `MANUAL_PRODUCTION_ACTIONS.md` § 000.
Version précédente : `docs/historique/FINAL_REPORT_2026-10-25.md`.

**Où la validation a eu lieu : uniquement en local** (piles Docker isolées
sur le poste de travail, plugNmeet v2.5.3 local, navigateur Chrome réel).
Ni préproduction ni serveur Hetzner : accès SSH refusé (BLOCKED). Rien n'a
été déployé, migré ni envoyé en production.

---

## 1. P0 n° 1 — Commentaire du Directeur / Principal's Comment

### Cause racine (reproduite sur le code livré)
1. **Aucun parcours de gestion** : le champ `Bulletin.general_comment`
   existait et le générateur l'imprimait, mais aucune page ne permettait de
   le saisir ; un PATCH sur l'API changeait la base sans changer le PDF.
2. **La régénération effaçait le commentaire** : `generate`,
   `generate-class` et `generate-all` SUPPRIMAIENT le bulletin avant de le
   recréer (reproduit : commentaire `''` après régénération, identifiant
   du bulletin changé).
3. **Un échec détruisait le PDF** : `generate_bulletin` effaçait l'ancien
   fichier AVANT de construire le nouveau (reproduit : élève sans PDF après
   une génération échouée).
4. Case du commentaire de hauteur fixe (2,4 cm) : un texte long débordait
   sur la signature du parent.
5. `generate-all` d'un super administrateur sans académie sélectionnée
   générait pour TOUTES les académies (le commentaire du code affirmait le
   contraire) ; et la génération groupée synchrone dépassait le délai de
   60 s du proxy sur une académie entière.

### Correction
- **Génération sans perte** (`pdf_generator.generate_bulletin`) : bulletin
  existant réutilisé (jamais supprimé), commentaire conservé, PDF construit
  en mémoire puis enregistré sous un **nom unique** (nouvelle URL : pas de
  cache navigateur) ; ancien fichier supprimé seulement après succès ; en
  cas d'échec, rien n'est écrit et un bulletin absent n'est pas créé ;
  `generated_at` = dernière génération réussie.
- **API** (administrateur / super administrateur uniquement, contrôle côté
  serveur) :
  - `POST /api/bulletins/{id}/comment/` — ajouter, modifier, supprimer
    (texte vide) + régénération ; validation (1 200 caractères max., pas de
    troncature silencieuse, retours à la ligne normalisés) ; `409` si un
    autre administrateur a modifié entre-temps (`expected_comment`) ;
  - `POST /api/bulletins/comment-preview/` — portée vérifiée avant
    confirmation (élèves, bulletins existants, avec commentaire, absents
    avec ou sans notes) ;
  - `GET|POST /api/bulletins/operations/`, `GET /api/bulletins/operations/{id}/`
    — opération pour un élève, une classe ou toute l'académie, exécutée par
    le **worker Celery** (tâche `bulletins.run_operation`), bilan détaillé,
    une seule opération à la fois par académie, `503` honnête si la file
    est indisponible ;
  - `generate-class` / `generate-all` passent par ces opérations (`202`) ;
  - les écritures génériques `PUT/PATCH/POST /bulletins/` sont fermées
    (`405`) : elles contournaient la validation et le PDF.
- **Journal d'audit** : modèle `BulletinOperation` (utilisateur, académie,
  portée, période, année, nombre de bulletins, résultat).
- **Interface** : composant `BulletinCommentManager`, ouvert depuis
  **Notes** (« Commentaires des bulletins ») et **Bulletins** (« Commentaires
  du directeur », et « Commentaire » sur chaque ligne). Colonne
  « Commentaire du directeur » et mention « PDF à régénérer » dans la liste.
- **PDF** : case extensible ; texte exceptionnellement long (données
  anciennes) imprimé pleine largeur dans un bloc sécable, jamais tronqué ;
  texte toujours échappé (pas de balisage injectable).
- Correctif voisin : le détail d'un bulletin d'une **année passée** n'est
  plus un 404 (le filtre « année active » ne vaut que pour la liste).

## 2. P0 n° 2 — Visioconférence pour toutes les académies

### Cause racine
`School.DEFAULT_FEATURES["campus"]` désactivait `virtual_classrooms` et
`video_conferencing` : l'académie FEBA (type « campus ») recevait `403` sur
toute l'API des salles et le menu était masqué.

### Correction
- Valeurs par défaut corrigées (toutes les académies, et toute nouvelle
  académie) ; **migration `schools.0017`** : réactive les désactivations
  explicites, ne touche aucun autre drapeau, conserve les valeurs d'origine
  (réversible). `HasEntityFeature` est conservé : une désactivation
  explicite reste appliquée.
- **Isolation renforcée** (défauts trouvés en testant) :
  - une salle pouvait viser la **classe, la matière ou l'année d'une autre
    académie** (reproduit : HTTP 201) → `TenantRelationsMixin` ; classe et
    année doivent concorder ;
  - un **enseignant pouvait supprimer la salle de l'administration**
    (reproduit : HTTP 204) → il ne gère que ses salles et celles de ses
    classes ; champ `can_manage` pour l'interface ;
  - super administrateur sans académie sélectionnée : création refusée.

## 3. Audit global — défauts confirmés et corrigés

| Défaut (reproduit) | Correction | Test |
|---|---|---|
| L'administrateur d'une académie changeait `entity_type` (campus → online) et s'ouvrait toutes les fonctions en ligne | champ réservé au super administrateur | `test_audit_2026_10_26` |
| Un PATCH `{school: autre}` déplaçait un **niveau** ou une **salle physique** dans une autre académie ; type de salle d'une autre académie accepté | `TenantRelationsMixin` (niveaux, types de salle, salles, logos) | idem |
| Un PATCH `{entity: autre}` transférait un **dossier d'admission FHA** ou un **test de placement** dans une autre académie | `entity`, `application`, `meeting_room` en lecture seule (préinscriptions : `entity`) | idem |

Sondes exécutées sur la pile de démonstration (deux académies, 6 rôles) :
- **lecture** : 229 routes de liste et 194 routes de détail, 4 632
  requêtes → **0 fuite inter-académies, 0 erreur serveur** ;
- **écriture par rôle** (parent, élève, enseignant ; 130 routes, POST /
  PATCH / DELETE) → aucune écriture illégitime (les seules acceptées
  concernent les classes de l'enseignant) ;
- **frontend → backend** : 230 appels API, 0 route orpheline ;
- **navigateur** : 119 pages de menu visitées (6 comptes) → aucune erreur
  JavaScript ; seules erreurs HTTP : 400 « Choisissez l'académie
  destinataire » du super administrateur en vue « toutes les académies »,
  comportement voulu et affiché à l'écran ;
- tâches planifiées Celery : les 6 sont enregistrées dans le worker.

## 4. Résultats

| Domaine | Résultat | Statut |
|---|---|---|
| Backend PostgreSQL 16 + Mailpit + plugNmeet réel | voir `TEST_REPORT.md` § 1 | PASS |
| Backend SQLite | voir `TEST_REPORT.md` § 1 | PASS |
| Frontend (Vitest, ESLint, build) | 313/313, 0 erreur (aucun avertissement ajouté), build OK | PASS |
| Migrations : base EXISTANTE de l'ancienne version migrée, retour arrière, réapplication | commentaire, salles, 120 bulletins conservés | PASS |
| Commentaires — parcours réel dans Chrome (Notes et Bulletins, ajout, modification, suppression, classe via le vrai worker Celery), texte vérifié dans les PDF produits | 4/4 PDF conformes | PASS (local) |
| Visio — réunion réelle dans l'académie FEBA (salle créée par l'admin FEBA dans l'interface, enseignant + élève, vidéo reçue, présences par webhook, fin par l'enseignant), FEBA FHA refusée (404) | conforme | PASS (local) |
| Scénarios e2e (8) | tous verts | PASS |
| Plusieurs académies sur le même plugNmeet | identifiants de salle distincts, événements rattachés à la seule académie de la salle | PASS (tests + réel local) |
| SMTP Hostinger, Twilio, serveur Hetzner | aucun accès | BLOCKED |
| Partage d'écran, TURN entre réseaux, recette en production | — | NOT RUN |

## 5. Fichiers, migrations, API

- **Migrations ajoutées** : `bulletins.0006_comments_operations` (champs
  `comment_updated_at`, `comment_updated_by`, `generated_at` sans
  `auto_now_add`, modèle `BulletinOperation` — additive) ;
  `schools.0017_enable_video_for_all_academies` (données, réversible).
- **Backend** : `bulletins/{models,operations (nouveau),pdf_generator,serializers,tasks,views}.py` ;
  `schools/{models,serializers}.py` ; `core/features.py` ;
  `virtualclass/{serializers,views}.py` ; `website/{serializers,fha_serializers}.py`.
- **Frontend** : `components/bulletins/BulletinCommentManager.jsx` (nouveau) ;
  `pages/admin/{Bulletins,Grades}.jsx` ; `pages/shared/VirtualRooms.jsx` ;
  `api/index.js` ; `i18n/translations.js`.
- **Tests ajoutés** : `test_bulletin_comments.py` (26),
  `test_visio_multi_academies.py` (16), `test_audit_2026_10_26.py` (7),
  `BulletinCommentManager.test.jsx` (5). Tests de l'ancienne règle « FEBA
  sans visio » adaptés à la nouvelle règle, sans affaiblir le contrôle (la
  désactivation explicite reste testée).
