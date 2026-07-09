# FEBA v39 — Rapport : désynchronisation puce/contenu sur la page Classes (année active)

Date : 07/07/2026 · Base : v38 · Diagnostic par extraction d'images + OCR de votre enregistrement (77 s).

---

## Ce que confirme la vidéo (fonctionnalités v37/v38 validées)

- **Copie des classes** (v38) : « 10 classe(s) copiée(s) de 2025-2026 vers 2026-2027 » — la fonction marche, matières FR/EN incluses.
- **Effectifs par année** (v37) : en parcourant 2023-2024 puis 2024-2025, les classes affichent des effectifs **variés et réels** (0/30, 5/30, 21/30, 26/30…) — plus de 0/30 systématique.
- **État vide contextuel**, **clôture/activation d'année**, **modification de classe** : tous opérationnels.

## Le bug corrigé (images f_11 et f_16)

**Symptôme** : sur la page Classes, la puce **« Année active » / « 2026-2027 ✓ »** est surlignée en bleu, mais le **tableau affiche des classes 2023-2024**. La puce sélectionnée et le contenu ne désignent pas la même année.

**Deux causes racines cumulées :**

1. **Frontend non déterministe.** La puce « Année active » posait `yearFilter=""` et appelait `classesAPI.list()` **sans paramètre**, en s'en remettant au filtre implicite du backend (`is_current=True`). La puce surlignée (calculée côté client) et le contenu (résolu côté serveur) pouvaient donc diverger. **Correction** : le filtre est désormais **résolu explicitement** vers un identifiant d'année concret (`effectiveYearId` = année filtrée, sinon année active), envoyé systématiquement au backend. La puce surlignée est calculée à partir de ce **même** identifiant → puce et contenu sont toujours cohérents. La puce « Année active » affiche en plus le nom de l'année suivie, ex. « Année active (2026-2027) ».

2. **Invariant métier violé en base.** Le décalage n'était possible que si **plusieurs années portaient `is_current=True`** dans l'établissement (états laissés par des cycles de tests/activations successifs) : le filtre `is_current` renvoyait alors une année différente de celle attendue. **Corrections** :
   - **Migration de données `schools/0008`** : ne conserve comme active que l'année la plus récente de chaque établissement (dédoublonnage).
   - **Contrainte de base** `uniq_current_year_per_school` (UniqueConstraint partielle sur `is_current=True`) : il devient **impossible** d'avoir deux années actives dans un même établissement — l'invariant est garanti au niveau PostgreSQL, pas seulement applicatif.
   - **Transactions** : `set_current` et la création d'année désactivent les autres puis activent la nouvelle **de façon atomique**, dans le bon ordre, pour respecter la contrainte.
   - **Seeder** aligné : purge du drapeau actif avant création, une seule année marquée active.

## Vérifications

Backend compilé ; graphe de migrations intègre (nouvelle migration additive `0008`) ; 78 fichiers frontend, 0 erreur ; imports/appels API valides. **4 nouveaux tests** (`test_single_active_year.py`) : le `save()` du modèle désactive l'ancienne active ; la contrainte DB refuse deux actives (insertion directe) ; `set_current` bascule atomiquement (toujours exactement 1 active) ; deux établissements conservent chacun leur propre année active. Audit des autres pages filtrées par année : **Students** et **Parents** résolvaient déjà leur filtre vers un identifiant concret (pas de divergence) — la page Classes était le seul point faible. Check-list du guide portée à **45 scénarios**.

## Fichiers modifiés
| Fichier | Nature |
|---|---|
| `frontend/src/pages/admin/Classes.jsx` | Filtre d'année déterministe (puce = contenu), dédup de variables |
| `backend/apps/schools/models.py` | Contrainte « une seule année active par établissement » |
| `backend/apps/schools/migrations/0008_single_current_year.py` | Dédoublonnage + contrainte |
| `backend/apps/schools/views.py` | `set_current` / création d'année atomiques |
| `backend/apps/schools/management/commands/seed_demo_data.py` | Purge du drapeau actif avant création |
| `backend/tests/test_single_active_year.py` | 4 tests de régression |
| Guides PDF | Check-list 45 scénarios |

## Note de migration
Au prochain `docker compose up`, la migration `schools/0008` s'applique automatiquement : si votre base contenait plusieurs années actives (à l'origine du bug), elle en conserve une seule (la plus récente) et verrouille l'invariant. Aucune action manuelle requise.
