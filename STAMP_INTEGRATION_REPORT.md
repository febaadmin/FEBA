# STAMP_INTEGRATION_REPORT.md — Cachets officiels (V7 + V8)

## V8 — Deux cachets, deux autorités (26/07/2026)

| Document | Cachet | Fichiers |
|---|---|---|
| **Bulletin** | **LA DIRECTION** | `cachet_feba.png` (600 px transparent), `cachet_feba_hd.png` (1000 px), `cachet_feba.webp` |
| **Reçu** | **LE SECRETARIAT** | `cachet_secretariat.png` (600 px transparent), `cachet_secretariat_hd.png` (1000 px), `cachet_secretariat.webp` |

Les intervertir est **interdit** — et impossible sans faire échouer les tests.

### Extraction du cachet « LE SECRETARIAT »

Produit à partir du PNG officiel fourni (1254 × 1254) : auto-rognage aux
limites du sceau, mise au carré, ratio **1:1** conservé, fond blanc rendu
transparent pour l'incrustation PDF. **Le graphisme et le texte ne sont pas
modifiés** ; le fichier source est conservé.

### Intégration

- **Reçu** (`apps/payments/pdf_generator.py`) : cachet **3 cm** dans la zone de
  validation unique « Le Secrétariat ».
- **Bulletin** (`apps/bulletins/pdf_generator.py`) : cachet **2,5 cm** centré
  dans le bloc « La Direction / The Principal ».
- Dégradation gracieuse : fichier absent → document généré sans cachet, sans
  exception.

### Vérification du cachet réellement embarqué

ReportLab **ré-encode** les images : comparer les octets source aux octets
extraits du PDF ne fonctionne pas. Les tests comparent la **signature visuelle
de la bande de texte** du sceau (seule zone où les deux diffèrent) — distance
≈ 2/1024 pour un même cachet ré-échantillonné, ≈ 223/1024 entre les deux
(seuil : 40). `tests/test_pdf_stamps.py` — **22 cas**.


## 1. Extraction fidèle

Le cachet a été extrait de la **1ʳᵉ page du PDF fourni** (image JPEG embarquée,
**1320 × 1301**) via PyMuPDF, **sans recréer ni modifier son graphisme**
(cercle marine « COMPLEXE SCOLAIRE FAITH & EXCELLENCE BILINGUAL ACADEMY »,
blason FEBA, mention « LA DIRECTION »).

Fichiers générés (`backend/feba_project/static_files/`) :

| Fichier | Détail | Usage |
|---|---|---|
| `cachet_feba_hd.png` | 1000 × 1000, fond blanc | **maître** haute définition |
| `cachet_feba.png` | 600 × 600, **fond transparent** | apposé sur les PDF |
| `cachet_feba.webp` | 1000 × 1000 | variante web légère (92 Ko) |

Traitement : auto-rognage aux limites du sceau, mise au carré, ratio conservé,
aucune déformation, aucune ombre ajoutée. Le PDF source n'est **pas** supprimé.

## 2. Intégration

- **Bulletins** (`apps/bulletins/pdf_generator.py`, `_add_signatures`) : le
  cachet (2,6 cm) est apposé dans la case **« Signature & Cachet / Stamp »**,
  sans masquer les notes, le nom de l'élève, les moyennes ni le pied de page.
- **Reçus** (`apps/payments/pdf_generator.py`) : cachet (2,6 cm) dans la case
  **« Cachet de l'École / School Stamp »**, sans masquer le montant, le numéro
  ni la signature.
- **Dégradation gracieuse** : si le fichier est absent, le document se génère
  quand même (case cachet vide) — aucune exception.

## 3. Fidélité

Le graphisme interne du cachet n'est **pas** modifié : son texte
(« COMPLEXE SCOLAIRE FAITH & EXCELLENCE… ») est conservé tel quel, même s'il
diffère des appellations textuelles générées séparément dans les documents
(nom officiel « Faith & Excellence Bilingual Academy », groupe « GROUPE
ÉDUCATIF FEBA »), conformément à la consigne.

## 4. Preuves

- `tests/test_document_branding.py::test_cachet_embarque` : le bulletin
  embarque bien une image de cachet.
- **Bulletin réel** généré et rendu en PNG : cachet net dans la case direction
  (blason + « LA DIRECTION »), taille cohérente, non déformé, une seule page A4.
- **Reçu réel** généré : 2 images (logo + cachet), noms officiels corrects.

## 5. Administration (piste)

Le cachet est un fichier statique packagé (défaut fourni). Une gestion plus
fine (activation/désactivation, remplacement, taille/position par type de
document, réservée aux profils autorisés) est identifiée comme évolution — le
socle actuel lit un fichier unique et se dégrade proprement s'il est absent
(cf. `KNOWN_LIMITATIONS.md`).
