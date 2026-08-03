# Gabarits documentaires — calibrage au millimètre

## Comment les coordonnées ont été obtenues

Elles n'ont pas été estimées à l'œil. La commande `document_probe` mesure
le fond : elle repère les règles horizontales dorées, les blocs de texte
et les médaillons, et convertit tout en millimètres dans le repère de la
page. Ce qu'elle imprime est reporté tel quel dans le JSON.

```bash
python manage.py document_probe --file "document_templates/originals/Diplôme FEBA(2).png"
```

Chaque coordonnée du gabarit est donc rattachée à un pixel mesurable, et
la mesure est reproductible.

## Conversion pixel ↔ millimètre

Le fond est inscrit dans la page **en conservant ses proportions**. La
conversion utilise ce facteur, et pas celui d'un étirement plein cadre :

| | Diplôme | Certificat |
|---|---|---|
| Pixels | 1492 × 1054 | 1491 × 1055 |
| Rapport d'aspect | 1,41556 | 1,41327 |
| A4 paysage | 1,41429 | 1,41429 |
| Rendu | 297,00 × 209,81 mm | 296,79 × 210,00 mm |
| Décalage | 0,000 / 0,095 mm | 0,107 / 0,000 mm |
| Échelle | 1 px = 0,19906 mm | 1 px = 0,19905 mm |

L'écart d'aspect vaut 0,09 %. Étirer le fond aux bords serait invisible à
l'œil et déplacerait chaque élément d'environ **0,1 mm — la moitié de la
tolérance**. C'est pourquoi le mode `contain` est imposé, et pourquoi la
bande résiduelle est calculée plutôt que subie.

## Ancres mesurées

### Diplôme

| Élément | Pixels | Millimètres |
|---|---|---|
| Règle d'écriture du nom | y 692–693, x 386–1105 | y 137,85 · x 76,84 → 219,96 |
| Règle DIRECTEUR | y 886, x 216–479 | y 176,46 · x 43,00 → 95,35 |
| Règle ENSEIGNANT | y 886, x 853–1010 | y 176,46 · x 169,80 → 201,05 |
| Règle DATE | y 920–921, x 1140–1314 | y 183,23 · x 226,93 → 261,57 |
| Mention d'exemple « Nom Prénom » | y 615–687, x 503–981 | y 122,4 → 136,8 |

### Certificat

| Élément | Pixels | Millimètres |
|---|---|---|
| Règle d'écriture du nom | y 689–691, x 338–1153 | y 137,15 · x 67,39 → 229,61 |
| Règle DATE | y 902–904, x 374–587 | y 179,55 · x 74,55 → 116,95 |
| Règle SIGNATURE | y 902–904, x 904–1116 | y 179,55 · x 180,05 → 222,25 |
| Disque intérieur du médaillon | centre (1283,5 · 197,5), ⌀ 119 | centre (255,59 · 39,31), ⌀ 23,69 |

## Ce que déclare chaque champ

Le code Python ne contient **aucune coordonnée**. Tout est dans les deux
JSON, et le moteur ne sait rien d'autre que ce qu'ils disent.

| Attribut | Rôle |
|---|---|
| `box.x_mm`, `y_mm`, `width_mm`, `height_mm` | zone, origine en haut à gauche |
| `font.family` | police embarquée du projet, jamais une police système |
| `font.size_pt` | taille initiale |
| `font.min_size_pt` | plancher de réduction |
| `align`, `vertical_align` | alignement horizontal et vertical |
| `color` | couleur, relevée sur le fond |
| `max_lines` | nombre maximal de lignes |
| `shrink_to_fit` | autorise la réduction de corps |
| `truncate` | **false partout** : un nom ne se coupe pas |
| `bleed_mm` | débord des jambages, pour la comparaison |

### Diplôme — champs

| Champ | x mm | y mm | l × h mm | police | corps | mini | align | couleur |
|---|---|---|---|---|---|---|---|---|
| `student_name` | 78,0 | 121,0 | 141,0 × 15,5 | FEBA-Script | 34 | 17 | centre / bas | `#B08A2E` |
| `issue_date` | 226,9 | 176,2 | 34,7 × 6,5 | FEBA-Text | 11 | 8 | centre / bas | `#1E3A6E` |
| `director_name` | 43,0 | 169,0 | 52,4 × 6,5 | FEBA-TextItalic | 10 | 7 | centre / bas | `#1E3A6E` |
| `teacher_name` | 169,8 | 169,0 | 31,3 × 6,5 | FEBA-TextItalic | 10 | 7 | centre / bas | `#1E3A6E` |
| `document_number` | 200,0 | 190,5 | 50,0 × 5,0 | FEBA-Text | 7,5 | 6 | droite / milieu | `#8A7A55` |

### Certificat — champs

| Champ | x mm | y mm | l × h mm | police | corps | mini | align | couleur |
|---|---|---|---|---|---|---|---|---|
| `student_name` | 71,0 | 120,5 | 155,0 × 15,5 | FEBA-Script | 34 | 17 | centre / bas | `#B08A2E` |
| `issue_date` | 74,6 | 172,5 | 42,4 × 6,5 | FEBA-Text | 11 | 8 | centre / bas | `#1E3A6E` |
| `signatory_name` | 180,1 | 172,5 | 42,2 × 6,5 | FEBA-TextItalic | 10 | 7 | centre / bas | `#1E3A6E` |
| `document_number` | 45,0 | 190,5 | 50,0 × 5,0 | FEBA-Text | 7,5 | 6 | gauche / milieu | `#8A7A55` |

Les zones du numéro ont été choisies après mesure : **100 % de parchemin
libre** dans les deux cas. Le coin bas-droit du certificat porte la vague
dorée et marine — un numéro y aurait été coupé, exactement comme il
l'était avant correction sur le diplôme.

## Neutralisation de « Nom Prénom »

Le diplôme porte une mention d'exemple en anglaise dorée. Écrire le vrai
nom par-dessus la laisserait visible en dessous.

Elle est retirée **sur l'image**, une fois, dans un fichier dérivé :

```bash
python manage.py document_neutralize --template diploma_feba
```

| | |
|---|---|
| Zone traitée | x 74,0 → 222,5 mm · y 122,0 → 139,6 mm (px 372–1118, 612–701) |
| Bande saine du haut | y 120,5 mm (px 600–609) — **0 pixel d'encre mesuré** |
| Bande saine du bas | y 141,5 mm (px 706–716) — **0 pixel d'encre mesuré** |
| Méthode | médiane par colonne sur 1,6 mm, puis interpolation verticale |
| Préservé | px y 692–693 — la règle d'écriture, **au pixel près** |

Pourquoi une médiane et non une ligne recopiée : le parchemin est texturé.
Recopier une seule ligne reproduit son grain à l'identique sur toute la
hauteur, et produit des stries verticales. C'est ce qui s'est passé au
premier essai, et c'est visible dans l'historique.

Pourquoi une image dérivée et non un rectangle dans le PDF : un aplat de
couleur unie sur un fond texturé se voit comme une pièce rapportée.

**L'original n'est jamais modifié.** Le dérivé vit dans `derived/`, et
c'est l'original qui reste la référence de la comparaison.

## Polices

| Police | Fichier | Usage | Licence |
|---|---|---|---|
| FEBA-Script | `CrimsonPro-Italic.ttf` | nom de l'élève | SIL OFL 1.1 |
| FEBA-Text | `CrimsonPro-Regular.ttf` | date, numéro | SIL OFL 1.1 |
| FEBA-TextItalic | `CrimsonPro-Italic.ttf` | mentions de signature | SIL OFL 1.1 |

Elles sont **embarquées dans le dépôt**. Une police résolue par le système
produirait un document différent selon le serveur, et personne ne s'en
apercevrait avant l'impression. Une police manquante fait échouer le rendu
avec son nom, plutôt que d'être remplacée en silence par Helvetica.

**Ce n'est pas la fonte d'origine.** Le placeholder est composé en anglaise
calligraphique (copperplate) ; cette fonte n'est pas fournie avec le projet
et n'a pas été identifiée. Crimson Pro Italic est un choix **compatible** —
serif, italique, même or `#B08A2E`, même ligne de base — et non identique.
Le jour où l'établissement fournit la fonte d'origine, il suffit de la
déposer dans `feba_project/static_files/fonts/` et de changer
`font.family` dans les deux gabarits.

## Vérification du calibrage

```bash
python manage.py document_calibrate --template diploma_feba   # grille millimétrée
python manage.py document_compare  --template diploma_feba    # écart mesuré
```

La grille superpose au fond un trait tous les 10 mm, marqué tous les
50 mm, et un rectangle rouge par zone déclarée. Ouverte à 100 %, elle
montre exactement où le moteur écrira.

Résultat de la comparaison, zones variables exclues :

| Gabarit | Pixels statiques | Au-delà de la tolérance | Écart max | Score |
|---|---|---|---|---|
| Diplôme | 1 433 891 | **0** | **0/255** | **100,0000 %** |
| Certificat | 1 441 620 | **0** | **0/255** | **100,0000 %** |

Aucune bordure, aucun ornement, aucun sceau statique n'est déplacé d'un
seul pixel.
