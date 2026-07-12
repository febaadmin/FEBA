# CORRECTIONS — FEBA School Management

Périmètre de cette itération : les **deux problèmes prioritaires obligatoires**
(mise en page des bulletins PDF, format d'année des matricules). Chaque
correction a été **reproduite avant / corrigée / testée automatiquement / validée
visuellement**. Un état honnête de l'audit global figure en fin de document.

Environnement de validation : `python -m pytest` (Django 5.0.4) et
`npm run build` / `npm run lint` (Vite/ESLint). Voir `TEST_REPORT.md` pour les
sorties réelles des commandes.

---

## PROBLÈME N°1 — Bulletins mal cadrés / débordement latéral

### Symptôme initial
Sur les bulletins comportant des intitulés de matières longs (ex. « Éducation
Civique, Morale et Instruction à la Citoyenneté Démocratique », « Social Studies
and Comprehensive Citizenship Education Programme »), le texte **ne se repliait
pas** : il traversait les colonnes voisines (Coeff, Notes) et débordait hors du
cadre. De plus, un bulletin standard de 10 matières **débordait sur une 2ᵉ page**
(bloc signatures rejeté seul en page 2).

Captures : `docs/bulletin_captures/avant_matieres_longues.png` (collision de
colonnes) et `docs/bulletin_captures/avant_page2_involontaire.png` (2ᵉ page).

### Cause exacte (racine)
Le générateur est **ReportLab** (`SimpleDocTemplate`, pas de HTML/WeasyPrint).
Les cellules des tableaux étaient des **chaînes de caractères brutes**. ReportLab
ne coupe jamais une chaîne : un intitulé long force donc l'élargissement de sa
colonne et pousse le tableau **au-delà de la largeur utile de la page**, d'où le
débordement et le chevauchement des colonnes voisines. Secondairement, les
largeurs de colonnes totalisaient **exactement** la largeur utile (18 cm) sans
marge de sécurité, et l'espacement vertical (Spacers, paddings, hauteurs de
signatures) était trop généreux → passage en 2ᵉ page.

### Fichiers concernés
- `backend/apps/bulletins/pdf_generator.py` (unique moteur de génération).

### Correction réalisée
1. **Retour à la ligne des cellules** : nouvelle fabrique `C(...)` qui enveloppe
   tout texte long (intitulé de matière, appréciation, notes, commentaire,
   identité) dans un `Paragraph` avec `wordWrap='CJK'` — le texte se replie
   **dans** la largeur de colonne, y compris un « mot » sans espace.
2. **Largeurs sécurisées** : marges ramenées à `1,2 cm` (largeur utile
   `21 − 2×1,2 = 18,6 cm`) et **toutes** les tables dimensionnées à `≤ 18,5 cm`
   → marge de sécurité, plus aucun débordement gauche/droite.
3. **Tenue sur une seule page A4 portrait** : paddings de lignes ramenés à
   `2,5 pt`, Spacers resserrés, bloc signatures compacté (hauteurs de lignes
   fixes), logo `2,5 → 2,0 cm`, en-tête resserré.
4. **Colonne « Coeff »** élargie (`1,0 → 1,2 cm`) pour éviter la coupure
   « Coef/f » de l'en-tête.
5. **Template Maternelle** aligné sur les mêmes règles : clé de notation à
   13 colonnes ramenée sous la largeur utile (`18,2 → 18,46 cm`), cellules de
   matières et de conduite enveloppées.

Le PDF **téléchargé** est le même flux que l'aperçu (un seul moteur) : la
correction s'applique donc aux deux.

### Migration
Aucune (changement purement présentation).

### Tests effectués
- Automatiques : `backend/tests/test_bulletin_layout.py` (7 tests) — peu de
  matières, 10 matières, intitulés longs FR/EN, « mot » ininterrompu, bulletin
  annuel, maternelle : **chaque scénario tient sur 1 page A4 portrait**
  (595 × 842 pt) et se génère sans exception.
- Visuels : rendu réel des PDF en PNG (voir `docs/bulletin_captures/`).

### Résultat obtenu
Bulletin cadré, sans débordement latéral, sans colonne coupée, sur **une seule
page**, avec les intitulés longs correctement repliés.
Captures : `docs/bulletin_captures/apres_matieres_longues.png`,
`apres_10_matieres.png`, `apres_maternelle.png`.

---

## PROBLÈME N°2 — Année incorrecte dans les matricules

### Symptôme initial
En 2026, les matricules restaient au format `FEBA-25-0005` (année « 25 ») au lieu
de `FEBA-26-0005`. Le format attendu par le cahier des charges est
`FEBA-YY-NNNN` (tirets), où `YY` = deux derniers chiffres de l'**année système**.

> Remarque : le code du dépôt (v45) générait `FEBA_26_0001` (tirets **bas**), déjà
> basé sur l'année système. Les matricules `FEBA-25-…` visibles à l'écran sont des
> **données héritées** en base. Cette itération fige le **format officiel à tirets**
> et **fiabilise** la séquence.

### Cause exacte (racine)
Deux points :
1. **Format** : la base était construite avec des tirets bas (`FEBA_26_`) au lieu
   du format officiel à tirets (`FEBA-26-`).
2. **Robustesse** : la séquence était calculée par balayage `max(existants) + 1`
   sans verrou → risque de **doublon** en création concurrente (et fragilité en
   cas de suppression). L'année, elle, était déjà correctement dérivée de
   `timezone.now().year` — **aucune valeur codée en dur** n'était en cause.

### Fichiers concernés
- `backend/apps/students/models.py` — `generate_matricule`, `_matricule_base`,
  `_seed_last_number`, nouveau modèle `StudentMatriculeSequence`, `Student.save`.
- `backend/apps/students/migrations/0005_studentmatriculesequence.py` (nouveau).
- `backend/apps/schools/models.py`, `…/management/commands/seed_demo_data.py`
  (commentaires mis à jour vers le format à tirets).
- Serializer/API/frontend : **inchangés** — le matricule est `read_only` et
  n'est généré qu'à un seul endroit (`Student.save()`), confirmé par recherche
  exhaustive (`matricule`, `generate_matricule`, `year_suffix`, `FEBA-`…). Le
  frontend ne fait **qu'afficher** le matricule.

### Correction réalisée
- **Format officiel** `FEBA-YY-NNNN` :
  `base = f"{prefix}-{year % 100:02d}-"`, `year = timezone.now().year`.
- **Séquence fiable et concurrente** : nouveau modèle
  `StudentMatriculeSequence(school, year, last_number)` avec **contrainte unique
  `(school, year)`**. La génération incrémente le compteur sous
  `transaction.atomic()` + `select_for_update()` (verrou de ligne effectif sous
  PostgreSQL, le SGBD de production) → **pas de doublon** en création simultanée.
- **Redémarrage par année** : compteur indépendant par `(établissement, année)`
  → `…-25-0002` puis `…-26-0001`.
- **Anti-collision héritage** : à la première création d'une année, le compteur
  est **amorcé** sur le plus grand numéro déjà présent du même format.
- **Compatibilité** : les anciens matricules (`FEBA_25_0005`,
  `GROUPESCOL-2026-0005`…) ne sont **jamais** renumérotés. Garde-fou conservé
  dans `Student.save()` (5 tentatives, repli `TMP-…`).

### Migration
`backend/apps/students/migrations/0005_studentmatriculesequence.py` — crée la
table `StudentMatriculeSequence` + contrainte unique `(school, year)`. Écrite à
la main (surgicale) pour n'ajouter **que** ce modèle, sans embarquer la dérive de
migrations pré-existante d'autres apps.

### Règle appliquée
- **Nouveaux matricules** : `FEBA-YY-NNNN` avec `YY` = année système à la
  création, séquence par établissement/année, verrouillée.
- **Anciens matricules** : conservés tels quels (aucune migration de données).
- **Mise en service** : à l'application de la migration `students 0005`.

### Tests effectués
`backend/tests/test_matricule.py` (16 tests) + `MatriculeTests` mis à jour dans
`tests/test_bug_fixes_v45.py` :
- années système simulées : `2023→FEBA-23-0001`, `2025→FEBA-25-0001`,
  `2026→FEBA-26-0001`, `2027→FEBA-27-0001`, `2030/2031` ;
- format à tirets (pas de `_`) ; séquence 0001/0002/0003 ; redémarrage par année ;
- indépendance par établissement ; amorçage anti-collision ; ancien matricule
  intact ; suppression → pas de réutilisation de numéro ; suivi du compteur ;
  garde-fou anti-hardcode (le suffixe dérive de `year % 100`).

### Résultat obtenu
Une création en 2026 produit `FEBA-26-0001`, `FEBA-26-0002`, … ; en 2027,
`FEBA-27-0001`. Aucune année codée en dur, aucun doublon en concurrence.

---

## Fichiers modifiés / créés

**Modifiés**
- `backend/apps/students/models.py`
- `backend/apps/bulletins/pdf_generator.py`
- `backend/apps/schools/models.py` (commentaire)
- `backend/apps/schools/management/commands/seed_demo_data.py` (commentaire)
- `backend/tests/test_bug_fixes_v45.py` (`MatriculeTests` → format à tirets)
- `.gitignore` (ignore l'environnement de test local)

**Créés**
- `backend/apps/students/migrations/0005_studentmatriculesequence.py`
- `backend/tests/test_matricule.py`
- `backend/tests/test_bulletin_layout.py`
- `backend/feba_project/settings/test_sqlite.py` (réglages de test SQLite, CI sans postgres)
- `docs/bulletin_captures/*.png` (preuves visuelles avant/après)
- `CORRECTIONS.md`, `TEST_REPORT.md`

Aucun fichier supprimé ni entièrement réécrit.

---

## Audit global — état honnête

Les deux problèmes **prioritaires** sont corrigés, testés et validés
visuellement, **sans régression** (voir `TEST_REPORT.md`). L'audit exhaustif des
~25 modules réclamé par le cahier des charges **n'est pas terminé** dans cette
itération et ne doit pas être considéré comme livré.

Points relevés mais **hors périmètre des deux corrections** (non corrigés ici,
signalés pour transparence) :
- **Dérive de migrations pré-existante** (indépendante de ce travail) :
  `makemigrations --check` signalait déjà, avant intervention, des `AlterField`
  non migrés sur `parents`, `students(exit_notes)`, `subjects`, `attendance`,
  `bulletins`, `grades`, `payments`. Non touchés pour éviter d'inventer des
  valeurs par défaut sur des modèles hors sujet. Ma modification ajoute **une
  seule** migration propre (`students 0005`).
- Le ZIP final **n'a volontairement pas été généré** : le contrat le conditionne
  à la fin de l'audit global, non atteint ici.
