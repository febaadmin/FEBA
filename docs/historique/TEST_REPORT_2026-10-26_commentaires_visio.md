# FEBA — Rapport de tests : commentaires des bulletins et visio multi-académies

> **DOCUMENT HISTORIQUE** — version « commentaires des bulletins et visio multi-académies » (commit 575d493).
> Version courante : `FINAL_REPORT.md` et `TEST_REPORT.md` à la racine.

Exécuté le 26 octobre 2026, branche `fix/feba-commentaires-visio`, **en
local uniquement**. Version précédente : `docs/historique/TEST_REPORT_2026-10-25.md`.

Statuts : **PASS** · **FAIL** · **BLOCKED** · **NOT RUN** · **SIMULATED**.
Un test ignoré n'est jamais compté comme réussi. La vérification depuis une
extraction neuve de l'archive est consignée dans `DELIVERY_VERIFICATION_*.txt`,
livré à côté du ZIP.

## 1. Tests automatisés (dépôt)

| Suite | Résultat | Statut |
|---|---|---|
| Backend PostgreSQL 16 + Mailpit SMTP + plugNmeet v2.5.3 réel | **1693 réussis, 0 ignoré, 0 échec** (607 sous-tests) | PASS |
| Backend SQLite | 1684 réussis, **9 ignorés** (3 Mailpit, 3 plugNmeet réel, 3 concurrence PostgreSQL — tous exécutés et réussis sur PostgreSQL), 0 échec | PASS |
| Frontend Vitest | 313 / 313 (38 fichiers) | PASS |
| ESLint | 0 erreur ; 80 avertissements, tous antérieurs (aucun ajouté) | PASS |
| Build Vite | réussi | PASS |
| `makemigrations --check`, `manage.py check` | aucun écart | PASS |
| `compose_config_check.sh`, `repo_safety_check.sh` | valides | PASS |

Nouveaux tests (ils échouent sur le code livré `25b4c57`, vérifié) :
- `test_bulletin_comments.py` — 26 tests : les 22 scénarios demandés
  (ajout, base, PDF réel lu avec PyMuPDF, modification, ancien texte absent,
  suppression → texte par défaut, régénération qui conserve, échec qui
  conserve bulletin + commentaire + PDF, caractères spéciaux, commentaire
  long sans débordement, classe, académie seule, suppression groupée sans
  perte de notes, bulletins manquants selon le choix, échec partiel
  rapporté, parent/élève/enseignant refusés, autre académie refusée, super
  administrateur obligé de choisir l'académie, lien PDF renouvelé, annotation
  rouge jamais imprimée) + double requête, modification concurrente (409),
  année passée, file Celery indisponible (503), exécution unique de la tâche.
- `test_visio_multi_academies.py` — 16 tests : les 20 scénarios demandés
  (activation pour toutes les académies et les nouvelles, admin et
  enseignant FEBA créent / modifient / suppriment / ouvrent, élève et
  parent rejoignent, mêmes fonctions ailleurs, listes et accès par
  identifiant cloisonnés sans révéler l'existence, classe/matière/année
  étrangères refusées, événements et présences dans la bonne académie,
  webhook d'un participant d'une autre académie non rattaché, enregistrements
  protégés, tâche de réconciliation par salle, super administrateur,
  migration réversible, même serveur plugNmeet sans mélange).
- `test_audit_2026_10_26.py` — 7 tests (défauts de l'audit global).
- `BulletinCommentManager.test.jsx` — 5 tests (lien PDF renouvelé, suppression,
  échec affiché, portée + confirmation + bilan partiel, aucune action sans
  académie sélectionnée).

## 2. Validations réelles (local)

| Contrôle | Résultat | Statut |
|---|---|---|
| Commentaires dans Chrome : page Notes (élève Estelle Acakpo, T1) — ajout, modification, suppression ; page Bulletins — classe CE1-A via le vrai worker Celery (`bulletins.run_operation` exécutée) | à chaque enregistrement, nouveau lien PDF ; texte lu dans les 4 PDF téléchargés conforme (accents, guillemets « », apostrophes, retour à la ligne ; texte par défaut après suppression ; aucune annotation) | PASS |
| Second passage de l'opération de classe | 1 bulletin modifié, 5 inchangés (déjà à jour) — bilan exact | PASS |
| Rendu visuel de la zone du commentaire | lisible, sans chevauchement de la signature ni du pied de page | PASS |
| Visio FEBA : salle créée par l'admin FEBA dans l'interface (menu visible), enseignant `prof.math@feba.bj` et élève `eleve1@feba.bj` dans la réunion plugNmeet (caméra et micro simulés, vidéo de l'autre participant reçue), présences enregistrées par webhook (107 s, 99 s), fin par l'enseignant, élève redirigé vers la page de fin | conforme | PASS |
| Même salle demandée par l'admin FEBA FHA (détail, participants, join) ; présence dans sa liste | 404, 404, 404 ; absente | PASS |
| Migration d'une base EXISTANTE (ancienne version + données de démonstration) | `bulletins.0006` et `schools.0017` appliquées ; FEBA obtient la visio, ses autres drapeaux intacts ; commentaire, 3 salles, 120 bulletins conservés ; régénération qui garde le commentaire ; retour arrière puis réapplication réussis | PASS |
| Scénarios e2e (`e2e/*.mjs`, Chrome) : académies, espaces anglais, site public, devises et documents, documents officiels (54/54), préinscription (41/41), rapports mensuels (30/30), v9 | tous verts | PASS |
| Sondes d'audit (lecture 4 632 requêtes, écriture par rôle, routes frontend, 119 pages, tâches Celery) | voir `FINAL_REPORT.md` § 3 | PASS |

## 3. Non exécuté ou bloqué

| Contrôle | Statut |
|---|---|
| Validation sur Hetzner / préproduction (SSH refusé) | BLOCKED |
| SMTP Hostinger, Twilio | BLOCKED |
| Partage d'écran, réunion entre réseaux distincts (TURN), charge | NOT RUN |
| Fournisseur plugNmeet de production | NOT RUN (local uniquement) |
