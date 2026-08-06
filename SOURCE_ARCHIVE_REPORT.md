# SOURCE_ARCHIVE_REPORT — provenance de l'archive de travail

Ce document établit la traçabilité de la source utilisée. Aucun fichier ne
provient de GitHub, d'une copie locale préexistante ni d'une autre version.

## 1. Dossier source Google Drive

| Élément | Valeur |
|---|---|
| Dossier | `V1` |
| Identifiant Drive | `1zFPv27HZePcRD1wPPE4Uzmi_cO6jYM0f` |
| Propriétaire | feba.admin@gmail.com |
| Partage | Tous les utilisateurs disposant du lien — Lecteur |
| Sous-dossiers | aucun (structure plate, vérifiée par requête `parentId`) |
| Éléments | 12 |

### Note sur l'archive initialement demandée

L'identifiant `1ROBKxU9J9G9prnrji5HsOgupj5733OBZ`, indiqué dans la première
formulation de la mission, **n'existe pas** dans ce compte Drive. Il a été
recherché par `get_file_metadata`, par `download_file_content`, par listage de
toutes les archives ZIP du compte, par recherche de titre et par
`sharedWithMe` — sans résultat. Le dossier `V1` a ensuite été désigné comme
source de vérité, et l'unique archive de projet qu'il contient a été retenue.

## 2. Archive retenue

Une seule archive de projet est présente dans le dossier ; elle est donc
trivialement la plus récente.

| Élément | Valeur |
|---|---|
| Nom | `feba_multi_academies_v9_application_CORRIGE.zip` |
| Identifiant Drive | `1V4WkjR-2c8YGXDIJnzNiFiRzqM0x8Tlh` |
| Type MIME | `application/zip` |
| Taille annoncée par Drive | 34 091 317 octets |
| Taille téléchargée | 34 091 317 octets (identique) |
| Date de modification | 2026-08-05T00:32:11Z |
| Chemin relatif | `V1/feba_multi_academies_v9_application_CORRIGE.zip` |

**SHA-256 avant extraction :**

```
8ee116a9066314b57fbe964b351c0410fd52da0da2058bb35596f0daee59bff4
```

Intégrité : `unzip -t` → `No errors detected in compressed data`.
Contenu : 1 056 entrées, 37 851 838 octets décompressés.

### Méthode de téléchargement

Le connecteur Drive ne restitue les octets qu'en base64 dans la conversation,
ce qui est impraticable pour 34 Mo. Le dossier étant partagé publiquement, le
téléchargement a été fait dans le conteneur via l'endpoint public de Drive,
avec le jeton de confirmation antivirus exigé au-delà de 25 Mo :

```
https://drive.usercontent.google.com/download?id=<ID>&export=download&confirm=t
```

La taille obtenue correspond exactement aux métadonnées Drive.

## 3. Inventaire complet du dossier

Toutes les tailles téléchargées correspondent aux métadonnées Drive.

| Nom | Identifiant Drive | Taille | Modifié le | MIME | Chemin relatif |
|---|---|---|---|---|---|
| feba_multi_academies_v9_application_CORRIGE.zip | 1V4WkjR-2c8YGXDIJnzNiFiRzqM0x8Tlh | 34 091 317 | 2026-08-05T00:32:11Z | application/zip | V1/ |
| FEBA FHA fliyer.jpeg | 1kXipzovN9hsB9DJ1hkoIlDVAeCPPwc94 | 332 810 | 2026-08-05T02:29:31Z | image/jpeg | V1/ |
| Capture d'écran 2026-08-03 à 22.51.51.png | 1VYwK3Q_C3SRpGWyiADpRMfY68_wr2WVy | 2 018 108 | 2026-08-05T02:31:57Z | image/png | V1/ |
| Capture d'écran 2026-08-05 à 04.14.25.png | 1-o7dkFgkrXn9fbmU7jIv52D-TXWsxzCF | 536 122 | 2026-08-05T02:14:36Z | image/png | V1/ |
| Capture d'écran 2026-08-05 à 04.13.50.png | 1zydDSng_KJiBb1r9v6rjkZ0oN0aq4-5c | 441 235 | 2026-08-05T02:14:11Z | image/png | V1/ |
| Capture d'écran 2026-08-05 à 04.12.46.png | 10UWkKJkT8N9gMt-SFVqn85YoRH6GNMBy | 498 784 | 2026-08-05T02:13:39Z | image/png | V1/ |
| Capture d'écran 2026-08-05 à 04.08.57.png | 1N1_Mfxj7gLpwljTaLXkGC7resxzp0f_Y | 415 460 | 2026-08-05T02:12:13Z | image/png | V1/ |
| Capture d'écran 2026-08-05 à 04.08.00.png | 1sEhlbuFxr6d9GNdfkrl27hKUr1aYOU5g | 1 370 790 | 2026-08-05T02:08:27Z | image/png | V1/ |
| Capture d'écran 2026-08-05 à 03.59.16.png | 1As3C-LW9oUYAeMIzEzuBmCIdS37N3na4 | 1 414 603 | 2026-08-05T02:07:15Z | image/png | V1/ |
| FEBA_French_Heritage_Academy_Complete_Brochure_Final.pdf | 1nCqwCK0_ME2xNbshEPNGhtoJgcyBjQuY | 7 450 639 | 2026-08-03T21:31:57Z | application/pdf | V1/ |
| FEBA_FHA_Modele_Economique.pdf | 1IBh_osm7d3PMDdpcxx4jjvIe6bOmqRL9 | 295 238 | 2026-08-03T21:16:41Z | application/pdf | V1/ |
| FEBA_French_Heritage_Academy.textClipping | 1ZXATsyQ8qM4V760ZeKt0hpmuyMPFa0_G | 384 | 2026-08-03T21:35:52Z | application/octet-stream | V1/ |

**Total téléchargé : 12 éléments** — 1 archive, 6 captures PNG, 1 flyer JPEG,
2 PDF de spécifications, 1 fragment de texte.

### SHA-256 des références

```
4dedb347991c2e2972904a3a60651c06be118f48d5b41656898da7d9eec45ceb  FEBA FHA fliyer.jpeg
e880b298f45f23f6f4fade2619b215a4c617d531df4d6bb975aa5c667f77af22  FEBA_French_Heritage_Academy_Complete_Brochure_Final.pdf
05989634f30ccadbbb1468b68413ca8ee5755ff8354581f94d7af3d2b46c127b  FEBA_FHA_Modele_Economique.pdf
ca11672cfe0f87ebff82eb58c9d560b6b05275bc49929aacb642fe6b06e27662  FEBA_French_Heritage_Academy.textClipping
b9b0f0c327e088b91353854aea9f8ec989a35123a3706121c79a5ecc88f29593  capture_2026-08-03_22.51.51.png
77c79b4ed9f7172c340c9a9ccd3026c907f3eecab01c95c5fc1cc4d198b0b29f  capture_2026-08-05_03.59.16.png
00803c5fe3b1a632d781d774cb5631ad2316970451ce064510a710486d0dab4b  capture_2026-08-05_04.08.00.png
fdcc8d8d6a1aace52d591947a5124c19be88d726e5cf815be44a05da13f4de27  capture_2026-08-05_04.08.57.png
94f29a381a5ef9002f5643033799dbcde1b6d6ee8b0ac0fde2ed5538293ac20c  capture_2026-08-05_04.12.46.png
bd48df4111b568eed8af59f1554e30aed20d8eca0311b6b69830493702ee9dba  capture_2026-08-05_04.13.50.png
d93d3193428af5c75f4532a4f24d0af26303b83f1cb00860f5890a02619d961a  capture_2026-08-05_04.14.25.png
```

## 4. Extraction

Dossier de travail **neuf et vide** avant extraction :

```
/home/user/feba_drive_source/extracted/
└── feba_multi_academies_v9_application/
```

937 fichiers extraits.

## 5. Contrôles structurels — tous validés

| Contrôle | Résultat |
|---|---|
| `backend/` | PRÉSENT |
| `frontend/` | PRÉSENT |
| `docker-compose.yml` | PRÉSENT |
| `docker-compose.prod.yml` | PRÉSENT |
| `docker-compose.jitsi.yml` | PRÉSENT |
| `Makefile` | PRÉSENT |
| Migrations Django | PRÉSENT — 98 fichiers dans 22 répertoires |
| Médias | PRÉSENT — 146 fichiers image/vidéo |
| Scripts | PRÉSENT — `scripts/`, 18 fichiers |
| Fichiers d'environnement d'exemple | PRÉSENT — `.env.example`, `.env.dev.example`, `.env.prod.example`, `.env.jitsi.example` |
| Tests backend | 65 modules |
| Tests frontend | 18 modules |
| Tests e2e | 13 fichiers |
| `.env` réels (secrets) | **ABSENT** — aucun fichier `.env`, `.env.dev` ou `.env.prod` réel dans l'archive |

Aucune correction n'a été entreprise avant la validation de ces contrôles.

## 6. Nommage

L'archive s'appelle `…v9…` alors que la mission parle de « V6 ». C'est le
nom du fichier tel que déposé dans le dossier source ; il a été conservé sans
modification. Le dépôt contient d'ailleurs des rapports `KNOWN_LIMITATIONS_V4`
à `V9`, le versionnage interne du projet ayant progressé au-delà de V6. Ce
point est signalé pour éviter toute ambiguïté, sans changer la source retenue.
