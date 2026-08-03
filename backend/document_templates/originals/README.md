# Fonds originaux des documents officiels

Ce répertoire contient les **images de fond verrouillées** des diplômes et
certificats. Il est vide dans le dépôt : ces fichiers sont des documents
officiels de l'établissement, ils sont installés lors du déploiement et non
versionnés.

## Fichiers attendus

| Fichier stocké | Nom d'usage | Dimensions | SHA-256 de l'original |
|---|---|---|---|
| `diplome_feba_2.png` | `Diplôme FEBA(2).png` | 1492 × 1054 px | `d0d52ee219d2850fffd2cdc740b46836aed85d95f66d328de7b443132e79bff8` |
| `certificat_feba_2.png` | `Certificat FEBA(2).png` | 1491 × 1055 px | `6ff65e31f6eef6da4da516f7ba80c680f74c067f903444f7fd79e00b223ffa36` |

### Pourquoi un nom ASCII

`unzip` recode les noms non-ASCII : `Diplôme FEBA(2).png` ressort en
`Dipl#U00f4me FEBA(2).png`, et le moteur ne retrouve plus son fond dans une
archive extraite. Le nom d'usage de l'établissement est conservé dans le
gabarit (`background.original_filename`).

**L'identité d'un fond est son empreinte SHA-256, jamais son nom de
fichier.** C'est l'empreinte qui est vérifiée avant chaque installation.

### Ce qui est actuellement installé

Les fichiers présents ne sont **pas** les PNG d'origine : ce sont des
variantes transcodées, acceptées nommément et tracées dans les gabarits
(`background.accepted_variants`). Les dimensions sont exactes — la
géométrie et donc le calibrage sont valides — mais les pixels ont été
ré-encodés par le canal de transmission.

Pour installer les vrais originaux :

```bash
python manage.py install_document_template --template diploma_feba \
    --file "…/Diplôme FEBA(2).png" --force
python manage.py document_neutralize --template diploma_feba --force
python manage.py document_compare    --template diploma_feba
```

L'empreinte passera alors sans `--accept-variant`.

## Installation

```bash
python manage.py install_document_template \
    --template diploma_feba \
    --file /chemin/vers/"Diplôme FEBA(2).png"
```

La commande **vérifie les dimensions et l'empreinte SHA-256 avant de
copier**. Un fichier qui ne correspond pas est refusé, y compris s'il
ressemble beaucoup à l'original : un ré-export, une recompression ou un
recadrage de quelques pixels déplacent tous les éléments et rendent le
calibrage faux sans que rien ne le signale à l'écran.

Une fois les deux fonds installés :

```bash
python manage.py document_templates_check   # présence, empreinte, cohérence
python manage.py document_calibrate --template diploma_feba
python manage.py document_compare  --template diploma_feba
```

## Pourquoi rien n'est émis sans ces fichiers

Le moteur documentaire refuse d'**émettre** (état `issued`) un document
tant que :

1. le fond n'est pas présent et conforme à son empreinte ;
2. le gabarit n'est pas marqué `calibrated: true`.

Il produit alors un **aperçu filigrané « NON CALIBRÉ »**, utilisable pour
travailler la mise en page, jamais pour remettre un document à un élève.

Ce refus est délibéré. Un diplôme dont le nom est décalé de trois
millimètres, ou posé sur un fond ré-exporté, reste un diplôme aux yeux de
celui qui le reçoit : l'erreur ne se voit pas, et elle circule.

## Signatures et cachets

Les zones `director_signature` et `official_seal` ne sont remplies **que**
si un fichier officiel existe dans les ressources du projet
(`feba_project/static_files/`). En son absence, la zone reste telle qu'elle
figure sur le fond — y compris la mention « YOUR SEAL » du certificat.

Aucune signature et aucun cachet ne sont dessinés, reconstitués ou
approchés par le moteur. Une signature inventée sur un diplôme n'est pas
une approximation graphique : c'est un faux.
