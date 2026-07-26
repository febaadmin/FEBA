# PDF_LAYOUT_REPORT.md — Mise en page des documents (V8-P6/P7, 26/07/2026)

## 1. Reçu de paiement — zone de validation unique

### Avant

Trois colonnes : « Signature du Caissier » | vide | « Cachet de l'École /
School Stamp », avec le cachet de la **Direction** (mauvais cachet) et une
composition déséquilibrée.

### Après

| Élément | Choix |
|---|---|
| Mentions supprimées | « Signature du Caissier », « Cachet de l'École / School Stamp » |
| Zone unique | mention légale à **gauche**, bloc de validation à **droite** |
| Bloc de validation | « **Le Secrétariat** » → **cachet 3 cm** → « Cotonou, le JJ/MM/AAAA » |
| Cachet | `cachet_secretariat.png` (600 px, fond transparent), ratio **1:1** |
| Structure | table à 2 colonnes (10,6 cm / 6,4 cm) — aucune coordonnée absolue |

Le cachet ne chevauche **ni le montant, ni le numéro de reçu, ni la date, ni
les informations du payeur**, et ne sort pas de la page.

### Défaut corrigé au passage

Le nom de l'établissement (16 pt) **chevauchait l'adresse** : `ParagraphStyle`
utilise `leading = 12` par défaut, insuffisant pour du 16 pt. L'interligne est
désormais proportionnel à la taille de police (`fontSize × 1,25`).

## 2. Bulletin — zone de validation de la Direction

### Cause de l'aspect « flottant » signalé

Le cachet (2,6 cm) était placé dans une cellule à **hauteur fixe de 1,15 cm**
d'une table à 4 lignes. ReportLab ne redimensionne pas l'image : le cachet
**débordait de sa case** et se superposait à la ligne de signature et à la
date — d'où l'impression qu'il « flottait » sans alignement.

> Conséquence méthodologique : l'ancienne mise en page paraissait compacte
> **parce qu'elle était cassée**. La corriger demandait de la place réelle.

### Après

```
┌─────────────────────────────┐   ┌──────────────────────────┐
│ Commentaire du Directeur    │   │  La Direction /          │
│ …                           │   │  The Principal           │
├─────────────────────────────┤   │      ( cachet 2,5 cm )   │
│ Signature du Parent : ____  │   │  Cotonou, le JJ/MM/AAAA  │
└─────────────────────────────┘   └──────────────────────────┘
```

| Élément | Choix |
|---|---|
| Intitulé | « La Direction / The Principal » |
| Cachet | `cachet_feba.png`, **2,5 cm**, centré, ratio 1:1 |
| Lieu et date | sous le cachet, centrés |
| Insécabilité | `KeepTogether` — le cachet ne peut pas être isolé sur une page |
| Rééquilibrage | commentaire **+ signature du parent** empilés à gauche (la ligne pleine largeur du parent est absorbée) → la hauteur nécessaire est libérée **sans allonger le bulletin** |

### Non-régression de pagination

Le bloc « signature du parent » occupait auparavant une ligne pleine largeur
supplémentaire. En l'empilant dans la colonne de gauche, la zone de validation
gagne la hauteur requise **à coût nul** : un bulletin chargé (10 matières +
commentaire long, ou bulletin annuel) tient **toujours sur une seule page A4**
— vérifié par les tests de mise en page préexistants.

### Défaut corrigé au passage

La colonne « Moy. Pond. » restait calculée sur l'échelle interne /20 : on
lisait **« 48.00 »** en face de **« 6.00/10 »**. Elle suit désormais le barème
affiché (6.00/10 × coefficient 4 = **24.00**).

## 3. Deux cachets, deux autorités

| Document | Cachet | Fichier |
|---|---|---|
| **Bulletin** | LA DIRECTION | `cachet_feba.png` |
| **Reçu** | LE SECRETARIAT | `cachet_secretariat.png` |

Les intervertir est **interdit** — et impossible sans faire échouer les tests.

## 4. Vérification des PDF (réellement effectuée)

| Contrôle | Reçu | Bulletin |
|---|---|---|
| PDF généré et ouvert | ✅ | ✅ |
| Nombre de pages | 1 | 1 (court **et** chargé) |
| Format A4 (595 × 842 pt) | ✅ | ✅ |
| Texte extrait | ✅ | ✅ |
| Pages rendues en images et **inspectées visuellement** | ✅ | ✅ |
| Cachet dans la page, non étiré (ratio ≈ 1,00) | ✅ | ✅ |
| Aucun chevauchement (montant / date / titre / bord) | ✅ | ✅ |

### Tests de présence / absence

**Reçu** — contient « Le Secrétariat » ; **ne contient pas** « Signature du
Caissier », « Cachet de l'École », « School Stamp ».
**Bulletin** — contient « La Direction » et le cachet Direction ; **ne contient
pas** le cachet Secrétariat.

### Identification du cachet embarqué

ReportLab **ré-encode** les images : comparer les octets du fichier source à
ceux extraits du PDF ne fonctionne pas. Les tests comparent donc la
**signature visuelle de la bande de texte** du sceau (« LA DIRECTION » vs
« LE SECRETARIAT »), seule zone où les deux diffèrent — distance ≈ 2/1024 pour
un même cachet ré-échantillonné, ≈ 223/1024 entre les deux cachets (seuil : 40).

`tests/test_pdf_stamps.py` — **14 cas**.


## Compléments V8 (vérification sur documents réellement générés)

| Document | Défaut trouvé | Correction | Preuve |
|---|---|---|---|
| Bulletin (primaire) | Détail des notes imprimé sur 20 face à des moyennes sur 10 | `_fmt_note` convertit le détail dans le barème du document (2 décimales sur 10) | `bulletin_2_cm2_primaire.pdf` + test interdisant toute valeur hors barème |
| Bulletin (maternelle) | Clé de notation sur 20 — seule référence chiffrée d'un gabarit en lettres | `_grading_key_cells(scale)` : « A+ (≥9.75) … F (<2) » | `bulletin_1_garderie_maternelle.pdf` |
| Reçu | Observation contenant « & » ou « <trimestre 2> » **silencieusement amputée** | texte échappé avant `Paragraph`, retours à la ligne convertis en `<br/>` | `recu_2_multiligne.pdf`, test `test_caracteres_speciaux_conserves` |

### Jeu d'exemples livré

Trois bulletins (Garderie/maternelle, CM2/primaire, 6ème/collège) et six reçus
(simple, multiligne, observation longue, nom long, partiel, duplicata) sont
générés depuis le HEAD final, rendus en PNG et inspectés un par un : aucune
troncature, aucun débord à droite, « Le Secrétariat » et son cachet présents,
« Signature du Caissier » et « Cachet de l'École » absents, en-tête sans
collision, une seule page A4 par document.
