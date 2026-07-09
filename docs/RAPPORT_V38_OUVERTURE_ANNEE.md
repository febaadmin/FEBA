# FEBA v38 — Rapport : ouverture d'année (copie des classes), pré-sélection, en-tête réparé

Date : 07/07/2026 · Base : v37 · Diagnostic : capture + OCR de votre enregistrement (8 s).

---

## 1. Ce que montraient la capture et la vidéo

- Puce **« Année active »** (2026-2027) : **0 classe(s), « Aucun résultat »** — exact (la seule classe de 2026-2027 a été supprimée lors de vos tests), mais l'écran ne l'expliquait pas et n'offrait aucune issue.
- Modale **« Nouvelle classe »** : champs Niveau et **Année scolaire vides** à l'ouverture, alors que le contexte (année filtrée/active) est connu.
- La puce **2025-2026** affiche bien ses 10 classes **avec les effectifs réels (6/30…)** — la correction v37 « effectifs via inscriptions » est confirmée par votre propre vidéo.
- Le vrai manque métier : à l'ouverture d'une nouvelle année, une école ne doit pas **recréer ses classes une à une**.

## 2. Corrections et évolution v38

### « Copier depuis une année » (ouverture d'année en un clic)
- **Backend** `POST /classes/copy-from-year/` : duplique les classes d'une année source vers une année cible — nom, niveau, capacité, **matières FR/EN (M2M)**. **Idempotent** : les classes homonymes déjà présentes dans la cible sont ignorées et nommées dans la réponse. Aucun élève n'est copié (les effectifs viennent des Inscriptions/Passages). Gardes : années distinctes, même établissement, contrôle tenant (superadmin : déduit des années, cohérent v31), 404/400 explicites.
- **Interface** : bouton « Copier depuis une année » dans l'en-tête de la page Classes → modale (année source ↔ cible, cible pré-remplie avec l'année filtrée/active), toast reprenant le détail serveur (« X copiées ; Y déjà présentes, ignorées »).

### Pré-sélection de l'année dans « Nouvelle classe »
La modale s'ouvre désormais avec **l'année scolaire pré-sélectionnée** (année filtrée sur la page, sinon année active) — plus de champ vide à re-chercher à chaque création.

### État vide contextuel
« Aucune classe pour {année}. Créez une classe, ou copiez en un clic celles d'une année précédente (« Copier depuis une année »). »

### Défaut structurel découvert et réparé
En insérant le bouton, la vérification a révélé que les **puces d'années (v34) avaient été injectées À L'INTÉRIEUR du bouton « Nouvelle classe »** (JSX syntaxiquement valide mais imbriqué faux — c'est l'encadré bleu englobant visible sur vos captures). L'en-tête a été entièrement réécrit : boutons d'action et barre de puces proprement séparés.

## 3. Vérifications

Backend compilé ; 78 fichiers frontend, 0 erreur ; imports/appels API valides ; aucune migration (fonction additive sans schéma). **3 nouveaux tests** : copie avec niveaux/capacités/matières vérifiés, idempotence (relance → 0 créée / 2 ignorées), refus source = cible. Check-list portée à **43 scénarios**.

## 4. Fichiers modifiés
| Fichier | Nature |
|---|---|
| `backend/apps/classes/views.py` | Action `copy-from-year` (idempotente, gardée) |
| `frontend/src/pages/admin/Classes.jsx` | Bouton + modale de copie, pré-sélection d'année, état vide contextuel, en-tête réécrit |
| `frontend/src/api/index.js` | `classesAPI.copyFromYear` |
| `backend/tests/test_linked_accounts_and_classes.py` | +3 tests (copie) |
| Guides PDF | Check-list 43 scénarios |

## 5. Parcours « nouvelle année » désormais complet
1. Paramètres → créer l'année (validations v32) → l'activer.
2. Classes → **« Copier depuis une année »** (structures + matières en un clic).
3. Inscriptions → Passage de niveau / par classe / Assistant fin d'année (les élèves suivent, historique intact).
4. Le reste (notes, emplois du temps, paiements…) se remplit dans l'espace isolé de la nouvelle année.
