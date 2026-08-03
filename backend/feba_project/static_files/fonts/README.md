# Polices des documents officiels

## Pourquoi des polices dans le dépôt

Un diplôme doit se rendre à l'identique sur n'importe quelle machine. Une
police résolue par le système produirait un document différent selon le
serveur — et personne ne s'en apercevrait avant l'impression.

## Ce qui est fourni

| Fichier | Usage | Licence |
|---|---|---|
| `CrimsonPro-Italic.ttf` | nom de l'élève sur le diplôme et le certificat | SIL OFL 1.1 (`CrimsonPro-OFL.txt`) |
| `CrimsonPro-Regular.ttf` | date, mentions de signature | SIL OFL 1.1 |

## Ce que ces polices ne sont PAS

Le placeholder « Nom Prénom » du visuel d'origine est composé dans une
**anglaise calligraphique** (copperplate). Cette fonte n'est pas fournie
avec le projet et n'a pas été identifiée.

Crimson Pro Italic est un choix **compatible** — serif élégante,
italique, même couleur dorée, même ligne de base — et non **identique**.
Le rapport de fidélité le dit explicitement : la zone du nom est une zone
VARIABLE, exclue de la comparaison pixel à pixel des zones statiques.

Le jour où l'établissement fournit la fonte d'origine, il suffit de la
déposer ici et de changer `font.family` dans les deux gabarits.
