# Calibrage des quatre gabarits officiels

Chaque nombre de ce dossier a été **mesuré sur le fond réellement
dessiné**, par une commande qu'on peut relancer, et non choisi à l'œil.
Les commandes sont citées à côté de leurs résultats : un calibrage qu'on
ne peut pas refaire est un calibrage qu'on ne peut pas vérifier.

Deux outils produisent ces mesures :

```
manage.py document_analyze <fond.png>     # règles, bandes de texte, marges
manage.py document_calibrate --template <id>   # grille millimétrée sur le fond
```

---

## 1. Les quatre gabarits, d'un coup d'œil

| Gabarit | Source | SHA-256 source | Fond dérivé | SHA-256 dérivé | Dimensions | Zone du nom | Police | Nominale | Minimale | Lignes | Interligne | Masques | Résultat visuel |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `diploma_feba` | `originals/diplome_feba_2.png` | `d0d52ee2…79bff8` (original) · `356e61b8…41a9732` (variante installée) | `derived/diplome_feba_2.neutralise.png` | `f233b6bc…9de2cbc902` | 1492 × 1054 px | y 119,93–136,85 mm (16,92 mm) · x 78,0–219,0 mm (141,00 mm) | FEBA-Script | 34 pt | 14 pt | 2 | 1,0 em | 1 bande | conforme |
| `certificate_feba` | `originals/certificat_feba_2.png` | `6ff65e31…23ffa36` (original) · `bccead70…3958f41a` (variante installée) | *(aucun masque)* | — | 1491 × 1055 px | y 121,62–135,95 mm (14,33 mm) · x 71,0–226,0 mm (155,00 mm) | FEBA-Script | 34 pt | 14 pt | 2 | 1,0 em | aucun | conforme |
| `diploma_feba_fha` | `sources/feba_fha/diplome_feba_fha.png` | `09fa3534…1c4ef0d5` | `derived/diplome_feba_fha.neutralise.png` | `9fa7d7a2…50fe2371` | 1492 × 1054 px | y 126,50–142,62 mm (16,12 mm) · x 85,0–214,6 mm (129,60 mm) | FEBA-Script | 34 pt | 14 pt | 2 | 1,0 em | 1 bande | conforme après 4 corrections |
| `certificate_feba_fha` | `sources/feba_fha/certificat_feba_fha.png` | `08cb93ec…1e476073` | `derived/certificat_feba_fha.neutralise.png` | `94bf1554…5a5efc66c6` | 1492 × 1054 px | y 126,30–137,24 mm (10,94 mm) · x 78,0–219,0 mm (141,00 mm) | FEBA-Script | 34 pt | 14 pt | 2 | 1,0 em | 1 médaillon | conforme après 2 corrections |

Les deux fonds de Cotonou déclarent une **variante acceptée** : le canal
de conversation qui les a transmis ré-encode les images jointes avec
perte. L'empreinte de l'original reste l'autorité ; la variante est
acceptée nommément, datée et motivée dans le gabarit, jamais substituée.

**Les quatre zones sont différentes, et c'est le contrôle.** Si elles se
ressemblaient, ce serait le signe qu'un calibrage a été copié plutôt que
mesuré — ce qui est précisément arrivé, et que
`test_les_zones_different_parce_que_les_fonds_different` interdit
désormais.

---

## 2. Du pixel au point : la chaîne de conversion

Le fond est **inscrit** dans la page A4 paysage en conservant ses
proportions (`fit: contain`), puis centré. L'étirer jusqu'aux bords
déplacerait chaque élément d'environ 0,1 mm — la moitié de la tolérance
de calibrage — sans que cela se voie à l'écran.

| Gabarit | Ratio du fond | Fond dans la page | Bande résiduelle | 1 px vaut |
|---|---|---|---|---|
| `diploma_feba`, `diploma_feba_fha`, `certificate_feba_fha` | 1492/1054 = 1,41556 | 297,00 × 209,81 mm | 0,095 mm en haut et en bas | 0,19906 mm |
| `certificate_feba` | 1491/1055 = 1,41327 | 296,79 × 210,00 mm | 0,107 mm à gauche et à droite | 0,19905 mm |

Conversion, dans cet ordre et une seule fois :

```
mm  = décalage + pixel / dimension_px × dimension_fond_mm
pt  = mm × 72 / 25,4                     (1 mm = 2,83465 pt)
PDF = (x_mm × mm, (hauteur_page_mm − y_mm) × mm)
```

L'origine des gabarits est **en haut à gauche**, comme on lit une
maquette ; ReportLab compte depuis le bas. La bascule est faite dans
`Layout.to_pdf()`, une fois. La refaire à chaque appel serait l'erreur la
plus prévisible du moteur.

---

## 3. La zone du nom, obstacle par obstacle

La zone n'est pas une préférence de mise en page. Elle est **déduite de
deux obstacles mesurés** dans l'image du fond : le bas de la phrase
gravée qui précède le nom, et le haut de la règle d'écriture qui le
porte.

| Gabarit | Phrase gravée (bas) | Dégagement | Haut de zone | Bas de zone | Dégagement | Règle (haut) | Hauteur utile |
|---|---|---|---|---|---|---|---|
| `diploma_feba` | px y 599 → 119,33 mm | 0,60 mm | **119,93 mm** (px 602) | **136,85 mm** (px 687) | 1,00 mm | px y 692 → 137,85 mm | 16,92 mm = 47,96 pt |
| `certificate_feba` | px y 608 → 121,02 mm | 0,60 mm | **121,62 mm** (px 611) | **135,95 mm** (px 683) | 1,00 mm | px y 688 → 136,95 mm | 14,33 mm = 40,62 pt |
| `diploma_feba_fha` | px y 632 → 125,90 mm | 0,60 mm | **126,50 mm** (px 635) | **142,62 mm** (px 716) | 1,00 mm | px y 721 → 143,62 mm | 16,12 mm = 45,69 pt |
| `certificate_feba_fha` | px y 631 → 125,70 mm | 0,60 mm | **126,30 mm** (px 634) | **137,24 mm** (px 689) | 1,00 mm | px y 694 → 138,24 mm | 10,94 mm = 31,01 pt |

Les dégagements ne sont pas décoratifs : à cette résolution un pixel vaut
0,199 mm, donc 0,60 mm sépare le nom de la phrase de **trois pixels
pleins** et 1,00 mm le sépare de la règle de **cinq**.

La phrase gravée est, mot pour mot :
« Ce diplôme est fièrement décerné à » sur les deux diplômes,
« Ce certificat est fièrement décerné à » sur les deux certificats.

### Étendue latérale : le nom reste dans son trait

Un nom plus large que la règle sur laquelle il est écrit dépasse du
support prévu.

| Gabarit | Règle d'écriture | Zone du nom | Marge |
|---|---|---|---|
| `diploma_feba` | 76,64 – 220,36 mm (px 385–1106) | 78,00 – 219,00 mm | 1,36 / 1,36 mm |
| `certificate_feba` | 67,19 – 229,81 mm (px 337–1153) | 71,00 – 226,00 mm | 3,81 / 3,81 mm |
| `diploma_feba_fha` | 84,00 – 215,58 mm (px 422–1082) | 85,00 – 214,60 mm | 1,00 / 0,98 mm |
| `certificate_feba_fha` | 77,04 – 219,96 mm (px 387–1104) | 78,00 – 219,00 mm | 0,96 / 0,96 mm |

---

## 4. Ce que le moteur fait de cette zone

`apps/documents/textfit.py` — module isolé, sans Django, sans base et
sans canevas. Il lit les tables du fichier TrueType :

- `hmtx` — la chasse de chaque caractère ;
- `glyf` — la boîte englobante de son **dessin** : xMin, yMin, xMax, yMax.

Les deux diffèrent, et l'écart compte. Pour `CrimsonPro-Italic.ttf`
(1024 unités par em) :

| Grandeur | Valeur | D'où elle vient |
|---|---|---|
| Ascendante annoncée par la fonte | 0,896 em | table `hhea` |
| Encre la plus haute d'un nom | **0,8154 em** (le « Å ») | maximum du répertoire, mesuré |
| Encre la plus haute d'une lettre courante | 0,766 em (« É »), 0,678 em (« d »), 0,573 em (« K ») | table `glyf` |
| Descendante annoncée | −0,215 em | table `hhea` |
| Encre la plus basse d'un nom | **−0,2256 em** (le « j ») | maximum du répertoire, mesuré |
| Réserve de jambage retenue | **0,23 em** | couvre −0,2256 avec marge |

La dernière ligne de base est posée à `0,23 × corps` au-dessus du bas de
la zone : la réserve croît avec le corps, donc un nom écrit gros est posé
plus haut, et **aucune lettre ne touche la règle, quel que soit le corps
retenu**.

Le corps ne dépend **pas** des lettres du nom : il est calculé sur
l'encre la plus haute que la police puisse produire dans un nom
(0,8154 em). Sans cela, « Élise Kponou » sortirait à 31 pt et
« Jean Dossou » à 34 pt sur le même certificat — deux documents remis le
même jour, deux tailles de nom.

### Résultats mesurés, par gabarit

Nom court : `Élise Kponou` (12 caractères).
Nom long : `Marie-Élisabeth Joséphine Adjovi-Bokô d'Almeida de Souza Hounkpatin Ahouangonou` (**79 caractères**).

| Gabarit | Nom | Lignes | Corps | Interligne | Ligne de base | Encre (y) | Largeur d'encre |
|---|---|---|---|---|---|---|---|
| `diploma_feba` | court | 1 | 34,00 pt | 34,00 pt | 134,09 mm | 124,91 – 136,67 mm | 57,71 mm |
| `diploma_feba` | long | **2** | 22,75 pt | 22,75 pt | 135,00 mm | 120,83 – 136,79 mm | 139,87 mm |
| `certificate_feba` | court | 1 | 34,00 pt | 34,00 pt | 133,19 mm | 124,01 – 135,77 mm | 57,71 mm |
| `certificate_feba` | long | **2** | 19,75 pt | 19,75 pt | 134,35 mm | 122,05 – 135,90 mm | 121,43 mm |
| `diploma_feba_fha` | court | 1 | 34,00 pt | 34,00 pt | 139,86 mm | 130,68 – 142,44 mm | 57,71 mm |
| `diploma_feba_fha` | long | **2** | 21,00 pt | 21,00 pt | 140,92 mm | 127,84 – 142,57 mm | 129,11 mm |
| `certificate_feba_fha` | court | 1 | 29,50 pt | 29,50 pt | 134,85 mm | 126,88 – 137,08 mm | 50,07 mm |
| `certificate_feba_fha` | long | **2** | 15,00 pt | 15,00 pt | 136,02 mm | 126,68 – 137,20 mm | 92,22 mm |

Toutes les valeurs d'encre tiennent dans les bornes du § 3.

Le certificat FEBA FHA compose plus petit que les trois autres — 29,50 pt
au lieu de 34 pt pour un nom court, 15 pt pour un nom de 79 caractères.
Ce n'est pas un réglage : sa bande utile ne mesure que 10,94 mm contre
16,92 mm pour le diplôme FEBA. À 34 pt, un nom portant un « Å »
monterait à 12,54 mm au-dessus du bas de la zone, soit 1,60 mm de plus
qu'elle n'en offre. Le maximum honnête de ce fond est 29,7 pt.

### Essais effectués

Le moteur consigne chaque hypothèse mesurée (`Composition.trials`) : le
nombre de lignes, le corps, la largeur et la hauteur d'encre, la montée
réelle, la montée de référence, le plafond, la descente, le plancher,
l'interligne et le blanc entre lignes. Le nom de 79 caractères offre
**sept coupes possibles** — une par espace — et le corps descend de 34 pt
à 14 pt par pas de 0,25 pt. Nombre d'hypothèses réellement mesurées avant
d'aboutir :

| Gabarit | Hypothèses | Résultat |
|---|---|---|
| `diploma_feba` | 368 | 22,75 pt, 2 lignes |
| `diploma_feba_fha` | 424 | 21,00 pt, 2 lignes |
| `certificate_feba` | 464 | 19,75 pt, 2 lignes |
| `certificate_feba_fha` | 616 | 15,00 pt, 2 lignes |

L'ordre est : à **chaque** corps, une ligne d'abord, puis deux. Une
première écriture épuisait toutes les tailles sur une ligne avant
d'envisager la seconde — un nom de 73 caractères sortait alors sur UNE
ligne à 14,75 pt quand deux tenaient à 20,5 pt.

---

## 5. Neutralisation des mentions d'exemple

Les visuels d'origine portent des mentions destinées à montrer la mise en
page : « Nom Prénom » sur les deux diplômes, « YOUR SEAL » sur le
médaillon du certificat FEBA FHA. Écrire par-dessus les laisserait
visibles en dessous.

La neutralisation est faite **sur l'image, une fois**, et le résultat est
versionné : un rectangle de couleur unie posé dans le PDF se verrait
comme une pièce rapportée sur un fond texturé, et une commande à lancer
après l'installation est une commande qu'on oublie. Le dérivé est vérifié
par empreinte avant chaque émission ; absent ou altéré, il **bloque**
l'émission au lieu de laisser le moteur revenir silencieusement à
l'original — c'est ce repli qui faisait sortir un diplôme avec
« Nom Prénom » lisible sous le vrai nom.

Régénération (jamais nécessaire à l'installation) :

```
manage.py document_neutralize --template diploma_feba_fha
```

### 5.1 Masque « bande » — les deux diplômes

La texture est reconstruite par **interpolation verticale** entre une
bande saine au-dessus et une bande saine en dessous du placeholder.

| Gabarit | Boîte du masque | Échantillon haut | Échantillon bas | Épaisseur | Sous-bande préservée |
|---|---|---|---|---|---|
| `diploma_feba` | x 74,00 y 122,00 · 148,50 × 17,60 mm | y 120,50 mm | y 141,50 mm | 1,60 mm | y 137,78 mm, h 0,42 mm |
| `diploma_feba_fha` | x 83,61 y 127,80 · 132,37 × 16,92 mm | y 126,01 mm | y 145,91 mm | 1,60 mm | y 143,52 mm, h 0,60 mm |

La sous-bande préservée est la **règle d'écriture**, qui traverse la zone
du placeholder. Elle doit rester pixel pour pixel : c'est sur elle que le
nom est posé. Sur le fond de Cotonou elle occupe exactement les px 692 et
693 — en conserver un de plus laisserait les quatre pixels du jambage qui
la frôle en 691.

### 5.2 Masque « médaillon » — certificat FEBA FHA

La mention « YOUR SEAL » et ses trois étoiles sont posées sur un **disque
marine en dégradé**, cerné d'un anneau doré. Un rectangle inscrit dans le
disque ne couvrirait pas tout le texte ; un rectangle qui le couvre
déborde sur l'anneau et le détruit.

Le masque est donc **radial** : pour chaque anneau de rayon constant, la
couleur médiane est calculée, et seuls les pixels qui s'en écartent
au-delà de la tolérance sont repeints par cette médiane. Le dégradé est
conservé, l'anneau doré est intact, la mention disparaît.

| Paramètre | Valeur | Rôle |
|---|---|---|
| Centre | (256,79 ; 38,42) mm | mesuré sur le fond |
| Rayon | 11,74 mm | s'arrête à l'intérieur de l'anneau doré |
| `ink_tolerance` | 10 | écart à la médiane de l'anneau, sur 255 |
| `ink_dilation` | **3** passes | étend le masque au halo d'anticrénelage |
| Affinage de la médiane | 6 itérations | la médiane est recalculée en excluant les pixels déjà détectés |

**Pourquoi trois passes de dilatation.** Trois versions ont été
produites et regardées :

1. règle sur la couleur seule → l'ombre gravée du texte restait lisible ;
2. écart à la médiane, sans dilatation → le halo d'anticrénelage
   subsistait, contraste résiduel **46** sur 255 : le mot restait
   devinable ;
3. écart à la médiane + 3 passes de dilatation → contraste résiduel
   **33**, disque visuellement propre.

La dilatation est écrite sans SciPy : quatre décalages du masque
booléen, réunis, répétés. Ajouter une dépendance scientifique pour
trois passes de morphologie serait payer très cher une ligne de code.

---

## 6. Zones interdites

Ce que le moteur n'a le droit de toucher sur aucun des quatre fonds.

| Zone | Où | Pourquoi |
|---|---|---|
| Phrase gravée | au-dessus de la zone du nom (§ 3) | elle est **dans l'image** : aucune analyse de la structure du PDF ne voit qu'un nom la recouvre |
| Règle d'écriture | sous la zone du nom (§ 3) | le nom est écrit dessus, jamais dessus |
| Fleuron central des règles FEBA FHA | px y 901–922, 15,9 mm de large, centré | propre au fond FEBA FHA — voir § 7, défaut 4 |
| Médaillon du certificat FEBA FHA | centre (256,79 ; 38,42), rayon 11,74 mm | seul le texte d'exemple est neutralisé ; l'anneau doré et le dégradé sont conservés |
| Blason et ruban du logo | `logo_groupe_feba.png` | copie au pixel près de `logo_feba.jpeg` privée de la seule ligne nommant une académie |
| Cachets de Cotonou | `cachet_feba*.png`, `cachet_secretariat*.png` | leur dessin porte « COMPLEXE SCOLAIRE FAITH & EXCELLENCE BILINGUAL ACADEMY » — interdits sur tout document FEBA FHA |

---

## 7. Défauts trouvés à l'inspection, et leur correction

Six défauts. **Quatre n'ont été trouvés qu'en regardant un rendu ou en
mesurant un fond** — aucun n'était visible dans le code, et aucun
n'était attrapé par les suites d'alors.

### Défaut 1 — la hauteur d'une ligne était estimée

*Trouvé* : le bloc de deux lignes remontait sur la phrase gravée. Trois
tentatives, trois échecs, puis retrait de la fonctionnalité.

*Cause* : la hauteur était déduite de la fonte (ascendante nominale
0,896 em), ou pire d'une constante `corps × 0,75`. Les lettres d'un nom
montent en réalité à 0,766 em au plus. L'écart — près d'un quart de la
hauteur — était exactement ce qui manquait.

*Correction* : `textfit.py` lit `glyf`. Le module ne dessine rien et ne
dépend ni de Django ni d'une base : il s'éprouve isolément, ce qu'une
mesure enfouie dans un moteur de rendu ne permet pas.

*Vérifié par* : `test_la_boite_englobante_est_celle_du_dessin_pas_de_la_fonte`,
`test_la_hauteur_est_l_interligne_plus_l_encre_pas_le_corps`.

### Défaut 2 — la zone du nom FEBA FHA venait du fond de Cotonou

*Trouvé* : en mesurant l'étendue latérale des règles d'écriture.

*Cause* : les deux gabarits FEBA FHA avaient hérité de `x 78,0–219,0` et
`x 71,0–226,0`, tirés des fonds de Cotonou. Leurs propres règles sont
plus courtes de 11,4 mm et 10,0 mm. Un nom large dépassait du trait sur
lequel il est écrit.

*Correction* : `diploma_feba_fha` → x 85,00–214,60 ; `certificate_feba_fha`
→ x 78,00–219,00, chacun mesuré sur sa propre règle.

*Vérifié par* : `test_le_nom_reste_a_l_interieur_de_sa_regle_d_ecriture`.

### Défaut 3 — signatures et date du diplôme FEBA FHA calées sur les ancres de Cotonou

*Trouvé* : en ouvrant le rendu. Les signatures flottaient au-dessus de
leur trait.

*Cause* : le fond de Cotonou a **deux** hauteurs de règles (176,26 mm
pour les signatures, 183,23 mm pour la date) ; le fond FEBA FHA en a
**une seule**, à 183,83 mm, pour les trois. Les coordonnées copiées
plaçaient les signatures 8,3 mm trop haut et la date 1,1 mm trop haut.

*Correction* : trois boîtes recalées sur les ancres rendues par
`document_analyze` — px y 923–924, px x 295–549 (directeur), 893–1081
(enseignant), 1157–1307 (date).

Le certificat FEBA FHA avait le même défaut, de 5,2 mm : sa règle est à
184,22 mm quand celle de Cotonou est à 179,72 mm.

### Défaut 4 — un fleuron traversé par la signature

*Trouvé* : en agrandissant le rendu corrigé du défaut 3. La signature
sortait juste au-dessus du trait, comme prévu, **et passait à travers un
ornement**.

*Cause* : le fond FEBA FHA pose un fleuron centré **au-dessus** de chaque
trait — px y 901–922, soit 4,4 mm de haut et 15,9 mm de large, px x
382–462. Il est exactement sous le texte centré. Le fond de Cotonou n'a
pas ce motif : ses ornements sont aux extrémités du trait.

*Correction* : la ligne d'écriture utile de ce fond n'est pas le trait
mais le **sommet du fleuron**, 179,45 mm, moins 0,5 mm de dégagement.

Aucune mesure automatique n'aurait posé la question : le fleuron est un
trait horizontal de plus, indiscernable d'une règle pour un détecteur.
Il a fallu regarder.

### Défaut 5 — `getAscent()` divisée puis remultipliée

*Trouvé* : en relisant le placement vertical.

*Cause* : `pdfmetrics.getAscent(police, corps)` rend **déjà des points**.
Le code la divisait par 1000 avant de la remultiplier par le corps,
réduisant le terme d'un facteur ~30. À 11 pt, la correction de
descendante valait 0,009 mm au lieu de 0,76 mm.

*Correction* : le placement est **conservé** — c'est contre lui que les
cinq champs courts ont été calibrés, et le bas de leur boîte est la ligne
d'écriture imprimée sur le fond. Il est désormais écrit sans détour,
plutôt que par une expression qui prétend corriger quelque chose. Y
revenir déplacerait cinq champs déjà justes.

### Défaut 6 — une ligne minuscule préférée à deux lignes lisibles

*Trouvé* : en lisant les résultats de composition gabarit par gabarit.

*Cause* : le moteur épuisait tous les corps sur une ligne avant
d'envisager la seconde. Un nom de 73 caractères sortait sur UNE ligne à
14,75 pt là où deux tenaient à 20,5 pt. Techniquement conforme,
typographiquement mauvais.

*Correction* : une et deux lignes sont essayées **à chaque corps**. À
corps égal, une ligne reste préférée.

*Vérifié par* : `test_deux_lignes_valent_mieux_qu_une_ligne_minuscule`.

---

## 8. Comment ce calibrage est tenu

`backend/tests/test_textfit.py` — 50 tests, 147 sous-tests.

Le contrôle décisif est une **analyse de pixels**. Le document est
produit, rastérisé à 200 dpi, et comparé au **même fond posé par le même
calcul, sans un seul champ**. Les deux pages passent par `drawImage` avec
la même transformation : leur différence est, au pixel près, ce que le
moteur a ajouté.

C'est le seul contrôle qui voyait le défaut d'origine. La phrase gravée
est un dessin dans le fond ; aucune analyse de la structure du PDF ne
peut constater qu'un nom la recouvre — c'est ainsi que trois versions
successives du repli sur deux lignes ont passé les contrôles
géométriques.

Deux mutations volontaires ont été appliquées pour vérifier que la suite
mord :

| Mutation | Effet attendu | Résultat |
|---|---|---|
| Réserve de jambage 0,23 → 0,002 em | le nom descend sur la règle | 52 échecs |
| Zone du diplôme FEBA étendue à y 114 mm (sur la phrase) | la zone chevauche la phrase gravée | `test_la_zone_tient_entre_la_phrase_gravee_et_la_regle` échoue |

Contrôles complémentaires :

- les largeurs du moteur sont confrontées à celles de ReportLab, qui
  dessinera, à 10⁻⁴ pt près, sur sept noms et trois corps ;
- les quatre hauteurs de zone doivent rester **distinctes** ;
- la zone doit rester strictement entre la phrase et la règle ;
- l'encre ne doit se trouver ni entre la phrase et le haut de la zone,
  ni entre le bas de la zone et la règle ;
- le nom long doit produire **deux paquets de lignes encrées** sur le
  rendu, séparés par du blanc ;
- le centre optique de l'encre doit tomber à moins de 1 mm du centre de
  la zone.

## 9. Inspection visuelle

Huit rendus ont été produits, ouverts et examinés : diplôme et certificat
× FEBA et FEBA FHA × nom court et nom de 79 caractères. Ils sont
régénérables par le script de livraison et joints à l'archive.

Ce que l'inspection a montré, et qu'aucun test ne disait : les défauts 3
et 4 ci-dessus. Un test affirme qu'un nom ne touche pas une règle ; il
n'affirme pas qu'il est bien posé.
