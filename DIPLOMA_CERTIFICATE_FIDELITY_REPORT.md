# Diplômes et certificats — rapport de fidélité

## Résultat mesuré

| Gabarit | Pixels statiques comparés | Au-delà de la tolérance | Écart maximal | **Score** |
|---|---|---|---|---|
| Diplôme FEBA | 1 433 891 | **0** | **0 / 255** | **100,0000 %** |
| Certificat FEBA | 1 441 620 | **0** | **0 / 255** | **100,0000 %** |

Hors des zones variables déclarées, le fond est reproduit **au bit près**.
Aucune bordure, aucun ornement, aucune médaille, aucun ruban, aucun sceau
statique, aucun logo n'est déplacé d'un seul pixel.

Preuves jointes, par gabarit : `rendu_*.png`, `masque_variables_*.png`,
`difference_*.png`, `comparaison_*.json`.

## La réserve qui accompagne ce score

**Les fonds installés ne sont pas les PNG d'origine.**

Les deux visuels sont parvenus par le canal de conversation, qui **ré-encode
les images jointes en WebP avec perte** avant de les remettre. Ce qui a été
reçu :

| | Dimensions attendues | Dimensions reçues | Empreinte |
|---|---|---|---|
| Diplôme | 1492 × 1054 | **1492 × 1054** ✓ | ✗ |
| Certificat | 1491 × 1055 | **1491 × 1055** ✓ | ✗ |

Les dimensions correspondent **exactement** — la géométrie est donc
intacte, et tout le calibrage millimétré est valide. Les pixels, eux, ont
été ré-encodés : les empreintes déclarées
(`d0d52ee2…` et `6ff65e31…`) sont **structurellement inatteignables**
depuis un transcodage avec perte.

Le moteur a d'abord **refusé** ces fichiers :

```
CommandError: Empreinte incorrecte.
  Fichier fourni : 356e61b8f11e1d4e26c6cb5a7636c1f88cdbcd032f9f5b55a3d9df54541a9732
  Attendue       : d0d52ee219d2850fffd2cdc740b46836aed85d95f66d328de7b443132e79bff8
```

Ils ont ensuite été acceptés **nommément**, avec motif et responsable, via
`--accept-variant --reason … --accepted-by …`. La variante est inscrite
dans le gabarit :

```json
"accepted_variants": [{
  "sha256": "356e61b8…",
  "source": "fichier PNG fourni à l'installation",
  "reason": "Visuel transmis par le canal de conversation, qui ré-encode
             les images jointes en WebP avec perte…",
  "accepted_by": "Livraison V8 — opérateur d'intégration",
  "accepted_at": "2026-08-01"
}]
```

Conséquences, sans détour :

- l'empreinte d'origine **reste l'autorité** dans le gabarit ; elle n'a pas
  été remplacée ;
- chaque `GeneratedDocument` conserve `background_sha256`, donc **chaque
  document produit sait sur quel fond il l'a été** ;
- `document_samples` et `document_compare` **affichent l'avertissement** à
  chaque exécution ;
- le score de 100 % porte sur la fidélité au **fichier réellement
  installé**, ce qui est exactement ce qu'il faut mesurer : il prouve que
  le moteur n'altère rien.

**Pour lever la réserve** : transmettre les deux PNG par un canal sans
transcodage (archive ZIP, dépôt Git, transfert de fichier), puis

```bash
python manage.py install_document_template --template diploma_feba \
    --file "…/Diplôme FEBA(2).png" --force
python manage.py document_neutralize --template diploma_feba --force
python manage.py document_compare    --template diploma_feba
```

L'empreinte passera alors sans `--accept-variant`, et `is_original`
deviendra vrai.

## Comment la comparaison est faite

1. le document est rendu **avec des valeurs réalistes** — pas vide : le
   rendu comparé doit être celui qu'on livre ;
2. le PDF est rastérisé à la **résolution exacte du fond** ;
3. les deux images sont alignées (mêmes dimensions, aucun redimensionnement
   nécessaire) ;
4. les **zones variables déclarées** sont masquées ;
5. tout le reste est comparé pixel par pixel ;
6. une image de différence amplifiée ×8 est produite (un écart de 3 niveaux
   est invisible sur une image brute — c'est précisément ce qu'on cherche
   à voir) ;
7. un score et l'écart maximal sont calculés ;
8. la commande **échoue** au-delà du seuil.

### Ce qui est masqué, et pourquoi c'est déclaré à l'avance

Le nom, la date, le numéro et le sceau appliqué **sont censés** différer du
fond : c'est leur raison d'être. Les compter comme des écarts noierait,
sous des dizaines de milliers de pixels attendus, le décalage d'un
millimètre qu'on cherche à détecter.

Rien n'est exclu « parce que ça diffère ». Les zones masquées sont
**exactement** celles que le gabarit déclare — champs, assets, masques de
placeholder — plus une marge de 1 mm et le débord propre à chaque champ.

| Gabarit | Zones exclues | Part de la page |
|---|---|---|
| Diplôme | 8 | 8,9 % |
| Certificat | 6 | 9,3 % |

### Le débord des jambages

Premier passage sur le certificat : **124 pixels** d'écart, maximum
194/255, localisés en x 122–161 mm, y 137,15–138,34 mm — c'est-à-dire sur
la règle d'écriture.

Diagnostic : les **jambages descendants** du nom rendu (« Exemple
Comparaison ») passent sous la ligne de base et franchissent la règle. Ce
n'était pas une altération du fond, mais une zone variable mal bornée : la
boîte d'un champ décrit son texte, pas la descente de ses lettres.

Corrigé par un attribut `bleed_mm` déclaré sur les champs de nom (3 mm),
utilisé **uniquement par la comparaison** — il ne déplace rien au rendu.
Score après correction : **100,0000 %, écart maximal 0/255**.

## A4 paysage, sans déformation

| | Diplôme | Certificat |
|---|---|---|
| Page PDF | 841,89 × 595,28 pt = **297 × 210 mm** | idem |
| Rapport du fond | 1,41556 | 1,41327 |
| Rapport A4 paysage | 1,41429 | 1,41429 |
| Fond rendu | 297,00 × 209,81 mm | 296,79 × 210,00 mm |
| Bande résiduelle | 0,095 mm haut et bas | 0,107 mm gauche et droite |

L'écart d'aspect vaut 0,09 %. L'étirement aux bords serait invisible et
déplacerait chaque élément d'environ **0,1 mm — la moitié de la
tolérance de calibrage**. Le mode `contain` est donc imposé, et la bande
résiduelle **calculée**, pas subie. Elle reste sous la tolérance.

## Traitement de « Nom Prénom »

Le diplôme porte cette mention d'exemple en anglaise dorée, px y 615–687.

Elle est retirée **de l'image**, dans un fichier dérivé, par interpolation
entre deux bandes de parchemin **mesurées comme vierges d'encre**
(y 120,5 mm et y 141,5 mm), avec médiane par colonne sur 1,6 mm.

La règle d'écriture (px y 692–693) est **préservée au pixel près**.

Vérifications automatisées :

| Contrôle | Résultat |
|---|---|
| Pixels dorés restants dans la bande du placeholder | **0** |
| Pixels dorés sur la règle d'écriture | **> 500** (elle est intacte) |

Deux erreurs ont été traversées avant d'arriver là, et elles sont
instructives :

1. **recopier une seule ligne de texture** a produit des stries verticales
   — le papier est texturé, son grain se répète alors à l'identique ;
2. **prélever « 5 mm plus bas »** a fait tomber la bande de référence sur
   l'antialiasing du paragraphe suivant. Les positions de prélèvement sont
   désormais **absolues et mesurées**, pas relatives.

Aucune mention « Nom Prénom » ne subsiste sous ou derrière le vrai nom.

## Traitement de « YOUR SEAL »

Le certificat porte un médaillon doré cranté, à rubans marine, dont le
disque intérieur affiche « YOUR SEAL » et trois étoiles.

Un sceau officiel **existe dans le projet** :
`feba_project/static_files/cachet_feba.png` — le cachet
« COMPLEXE SCOLAIRE FAITH & EXCELLENCE BILINGUAL ACADEMY · LA DIRECTION »,
déjà utilisé sur les bulletins. Ce n'est pas une fabrication : c'est une
ressource validée de l'établissement, et l'autorité qui délivre un
certificat est bien la Direction.

Mesures du disque intérieur :

| | Pixels | Millimètres |
|---|---|---|
| Centre | (1283,5 · 197,5) | (255,59 · 39,31) |
| Diamètre | 119 | 23,69 |

Placement retenu :

| Élément | Diamètre | Raison |
|---|---|---|
| Disque de fond clair | 22,5 mm | **plus petit** que le disque, pour que l'anneau marine reste visible et que la couronne dorée ne soit jamais recouverte |
| Sceau | 21,0 mm | inscrit dans le fond clair |

Le disque clair est nécessaire : le sceau officiel est un tracé marine sur
fond transparent ; posé directement sur le marine du médaillon, il serait
invisible. Seul le **contenu** du médaillon est remplacé — couronne
dorée crantée et rubans marine viennent du fond, intacts.

Une première tentative avec `cachet_feba_hd.png` a posé un **carré blanc**
par-dessus le médaillon : ce fichier est opaque. La version à canal alpha
est désormais préférée, et un test vérifie que la ressource retenue est
bien en mode `RGBA`. « Plus haute résolution » n'est pas un critère quand
le résultat détruit l'ornement qu'on devait préserver.

**Sans sceau officiel, « YOUR SEAL » resterait visible** — ni masqué, ni
remplacé par un ersatz. C'est le signal que le document n'est pas finalisé.

## Les cinq noms difficiles

Cinq variantes fictives, choisies pour ce qu'elles font au moteur :

| Cas | Nom | Ce qu'il éprouve |
|---|---|---|
| court | `Ana Ba` | centrage calculé sur le texte, non sur la zone |
| long | `Marie-Christelle Adjovi Hounkpatin` | réduction de corps sans troncature |
| composé | `Jean-Baptiste N'Diaye-Sow` | tirets et apostrophe droite |
| accents | `Élisabeth Ahouéfa Gbêdjissi` | É majuscule, é, ê — glyphes et encodage |
| apostrophe | `N'Guessan D'Almeida` | apostrophe typographique U+2019 |

Les dix documents (5 × 2 gabarits) sont produits et joints dans
`exemples/`. Aucun n'est tronqué, aucun ne déborde.

`truncate: false` sur tous les champs de nom : un nom trop long **réduit
la police** jusqu'au plancher, puis le rendu **échoue franchement**.
Couper le nom d'un élève sur son propre diplôme produirait un document
faux qui a l'air correct.

## La police n'est pas celle d'origine

Le placeholder est composé en **anglaise calligraphique** (copperplate).
Cette fonte n'est pas fournie avec le projet et n'a pas été identifiée.

Crimson Pro Italic est un choix **compatible** — serif, italique, même or
`#B08A2E`, même ligne de base, posée sur la règle comme une signature — et
**non identique**. La zone du nom étant une zone variable, elle est exclue
de la comparaison des zones statiques : le score de 100 % ne porte pas sur
elle et ne prétend pas le contraire.

Le jour où l'établissement fournit la fonte d'origine, il suffit de la
déposer dans `feba_project/static_files/fonts/` et de changer
`font.family` dans les deux gabarits.

## Signatures

**Aucune signature n'est apposée.** Aucun fichier officiel n'existe dans
les ressources du projet — `resolve_resource("signature_director")` renvoie
`None`, et un test le vérifie.

Les documents d'exemple portent donc, aux emplacements prévus, la mention
`(signature requise)`. Un nom dactylographié n'est pas une signature et ne
prétend pas l'être.

Le moteur ne dessine, ne reconstitue et n'approche **jamais** une
signature. Une signature inventée sur un diplôme n'est pas une
approximation graphique : c'est un faux.

**Pour lever ce point** : déposer `signature_direction.png` dans
`feba_project/static_files/`. Elle sera apposée automatiquement, et le
champ `(signature requise)` disparaîtra.

## Ce qui est validé, et ce qui ne l'est pas

| Point | État |
|---|---|
| Fonds installés, dimensions conformes | **oui** |
| Fonds = PNG d'origine au bit près | **non** — variantes transcodées, tracées |
| Calibrage millimétré, tolérance 0,2 mm | **oui**, mesuré |
| A4 paysage sans déformation | **oui**, mesuré |
| Placeholder « Nom Prénom » neutralisé | **oui**, vérifié sur l'image |
| « YOUR SEAL » remplacé par le sceau officiel | **oui** |
| Comparaison pixel à pixel, zones statiques | **oui — 100,0000 %** |
| Dix documents d'exemple produits | **oui** |
| Signature officielle apposée | **non** — aucune ressource |
| Police calligraphique d'origine | **non** — substitut compatible |
