# Fonds officiels — FEBA French Heritage Academy

Ce dossier reçoit les **originaux non modifiés** des visuels officiels de
FEBA French Heritage Academy. Ils ne sont jamais retouchés sur place : les
variantes neutralisées sont produites séparément dans
`document_templates/derived/`, et l'original reste l'autorité de
comparaison.

## Fichiers attendus

| Fichier à déposer ici        | Gabarit produit        | Académie   |
|------------------------------|------------------------|------------|
| `DIPLOME FEBA FHA(1).png`    | `diploma_feba_fha`     | `FEBA_FHA` |
| `certificat FEBA FHA(1).png` | `certificate_feba_fha` | `FEBA_FHA` |

Les deux visuels se distinguent des fonds FEBA de Cotonou par leur ligne
d'académie : « FRENCH HERITAGE ACADEMY » au lieu de « Faith & Excellence
Bilingual Academy ». **Un fond ne sert jamais à l'autre académie** : un
document sortirait au nom de l'une et à l'effigie de l'autre.

## Pourquoi ce dossier existe séparément

Le dépôt conserve, pour chaque fond :

- le nom d'origine du fichier ;
- ses dimensions en pixels ;
- son empreinte SHA-256 ;
- la date d'intégration ;
- la version du gabarit ;
- l'académie propriétaire.

Ces informations vivent dans le JSON du gabarit
(`document_templates/*_template.json`, bloc `background`). Elles servent
au contrôle de démarrage : si un fond est remplacé, même par une version
visuellement identique mais ré-encodée, l'application le détecte et
refuse de produire un document plutôt que d'en sortir un altéré sans
prévenir.

## Après le dépôt

Rien n'est demandé à l'utilisateur final. La neutralisation des mentions
d'exemple (« Nom Prénom », « YOUR SEAL ») est faite **une fois, à
l'intégration**, et le fond dérivé est versionné dans le dépôt. Personne
n'a à lancer `manage.py document_neutralize` après l'installation.

## État actuel

Ce dossier est **vide**. Les deux PNG ont été annoncés à deux reprises
dans la conversation mais ne sont jamais arrivés sur le disque du
conteneur : rien n'a été écrit dans le répertoire de pièces jointes, et
une recherche sur l'ensemble du système de fichiers ne les trouve pas.

Tant qu'ils manquent, les gabarits `diploma_feba_fha` et
`certificate_feba_fha` ne peuvent pas être calibrés : chaque coordonnée
d'un gabarit est **mesurée sur l'image réelle** (position de la règle
d'écriture, des zones de signature, du sceau), et l'inventer produirait un
document décalé que rien ne signalerait.
