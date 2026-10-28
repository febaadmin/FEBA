# Guide : gabarits officiels des diplômes et certificats

Ce guide s'adresse à l'administrateur d'une académie et au super administrateur.

Chaque académie téléverse **son propre** gabarit de diplôme et **son propre**
gabarit de certificat. FEBA les utilise réellement pour produire les documents :
- le fond est reproduit tel quel ;
- les données réelles de l'élève sont écrites aux emplacements que vous avez placés.

Les gabarits d'une académie ne servent jamais à une autre. C'est garanti par le serveur
(tests `tests/test_academy_document_templates.py`, scénario navigateur
`e2e/parcours-gabarits.mjs`).

## 1. Où et qui

| Rôle | Écran | Portée |
|---|---|---|
| Administrateur d'une académie | Menu **Gabarits des documents** (`/admin/document-templates`) | Uniquement son académie |
| Super administrateur | Menu **Gabarits des documents** (`/superadmin/document-templates`) | L'académie choisie dans le sélecteur en haut de page. En mode « Toutes les académies », l'écran demande d'en choisir une. |
| Enseignant, parent, élève | aucun accès | — |

L'écran a deux espaces distincts, **Gabarit du diplôme** et **Gabarit du certificat**.
Un fichier téléversé pour le diplôme ne sert jamais au certificat.

## 2. Formats acceptés

Le fichier se téléverse **tel quel** : FEBA détecte son format réel et le convertit lui-même.
Aucun export manuel en PDF n'est nécessaire.
L'original est toujours conservé ; le moteur travaille sur un **fond normalisé** (PDF ou PNG) rangé à côté.

| Format | Traitement par FEBA |
|---|---|
| **PDF** | La page choisie est reprise **telle quelle** (vectorielle), et les champs sont dessinés par-dessus. |
| **PNG, JPEG** | L'image est inscrite dans la page choisie (A4 ou A5, paysage ou portrait, ou Lettre US) **sans déformation**, centrée. Un JPEG tourné par l'EXIF est redressé. |
| **TIFF, WEBP** | Convertis en PNG, puis traités comme une image. Un TIFF de plusieurs pages devient un PDF dont on choisit la page. |
| **Word (DOCX, DOC)**, **OpenDocument texte (ODT)**, **RTF** | Convertis en PDF par **LibreOffice** sur le serveur, puis traités comme un PDF. |
| **PowerPoint (PPTX, PPT)**, **OpenDocument présentation (ODP)** | Convertis en PDF par **LibreOffice** sur le serveur (une diapositive par page). |

La conversion conserve les dimensions et l'orientation de la page, les marges, les couleurs, les bordures, les images (logos, signatures et cachets scannés), les tableaux et la disposition.
Les documents de plusieurs pages (10 au plus) sont acceptés : on choisit la page qui sert de fond, et le document délivré n'en contient qu'**une**.
Les polices compatibles avec celles de Microsoft (Carlito pour Calibri, Caladea pour Cambria, Liberation pour Arial, Times et Courier) sont installées dans l'image : la mise en page d'un document Word est recomposée à l'identique.
Une police propre à l'établissement, non installée, est remplacée par une police voisine : vérifiez l'aperçu.

Contrôles appliqués à chaque téléversement, **avant** toute conversion :
- taille maximale : 20 Mo ;
- l'extension, le type annoncé **et le contenu réel** doivent concorder : un PDF renommé `.docx` est refusé, et le message dit ce qu'est vraiment le fichier ;
- fichiers corrompus ou tronqués : refusés ;
- documents **avec macros** (DOCM, PPTM, ou DOCX/DOC contenant un projet VBA) : refusés, car **aucune macro n'est jamais exécutée** ;
- documents protégés par mot de passe : refusés ;
- RTF contenant des objets OLE incorporés : refusés ;
- archives anormales : plus de 3 000 éléments, plus de 250 Mo une fois décompressées, ou taux de compression piégé ;
- PDF chiffrés ou actifs (JavaScript, lancement de programme, fichiers joints, formulaires dynamiques) : refusés ;
- images de plus de 40 millions de pixels : refusées.

Chaque format refusé reçoit un message qui dit pourquoi :
- GIF : qualité insuffisante ;
- SVG : contenu actif possible ;
- Excel : n'est pas un fond de document ;
- HEIC, Pages, Keynote : à exporter dans un format accepté.

**Conversion isolée.** Chaque conversion LibreOffice :
- s'exécute dans un répertoire temporaire et avec un **profil** qui lui sont propres : des conversions simultanées ne partagent rien ;
- a les macros désactivées et ne met à jour aucun lien externe ;
- ne reçoit aucune variable d'environnement du serveur, donc aucun secret ;
- a un **délai maximal** (90 s par défaut) : au-delà, le processus est tué et le téléversement refusé avec un message.

Le répertoire temporaire est supprimé dans tous les cas. Un échec ne laisse ni version, ni fichier, ni gabarit partiellement actif.

## 2 bis. Marqueurs {{ champ }} dans un document Word, OpenDocument, RTF ou PowerPoint

Un gabarit bureautique peut contenir des marqueurs explicites à l'endroit des données, par exemple :
« Décerné à {{ student_name }} pour l'année {{ school_year }} ».

À la conversion, FEBA :
1. repère la position exacte de chaque marqueur sur la page ;
2. le **retire du fond** sans rien déplacer d'autre : le reste de la ligne garde sa place au point près ;
3. crée à cet endroit un **champ déjà placé**, avec une taille de texte voisine de celle du marqueur. La zone s'arrête au texte du fond qui suit, et un marqueur seul et centré sur sa ligne donne un champ centré ;
4. choisit comme fond la page qui porte le plus de marqueurs.

On ajuste ensuite les champs dans l'éditeur comme pour n'importe quel fond. Un marqueur peut être coupé en plusieurs morceaux de mise en forme par Word : il est reconnu quand même.

Noms reconnus, en plus des noms du tableau du § 4 :

| Alias | Champ |
|---|---|
| `student_full_name`, `nom_eleve`, `nom_complet` | nom de l'élève |
| `matricule` | matricule |
| `date_naissance` | date de naissance |
| `academie` | nom de l'académie |
| `ville` | ville |
| `intitule`, `type_certificat` | intitulé |
| `objet` | objet du certificat |
| `niveau` | niveau |
| `classe` | classe |
| `annee_scolaire` | année scolaire |
| `moyenne` | moyenne |
| `mention` | mention |
| `date_obtention` | date d'obtention |
| `date_delivrance` | date de délivrance |
| `numero`, `reference` | numéro |
| `signataire`, `fonction_signataire` | signataire et sa fonction |

Les noms sont insensibles à la casse.

Un marqueur **inconnu** est retiré du fond mais **bloque la vérification**, en le nommant : renommez-le, ou placez le champ voulu dans l'éditeur.
Un PDF ou une image qui contient des marqueurs ne peut pas être nettoyé : la vérification le refuse et demande le document source.
Aucun marqueur ne peut donc apparaître sur un document délivré.

Laissez à chaque marqueur la place de la valeur réelle. Une valeur longue est réduite jusqu'à la taille minimale, puis refusée si elle ne tient pas ; elle n'est jamais tronquée.

## 3. Mettre un gabarit en service, étape par étape

1. **Téléverser** le fichier. Il apparaît « Téléversé, non validé » : il n'est **pas encore utilisé**.
2. **Placer les champs**. L'éditeur s'ouvre sur le fond réel.
   - Ajoutez un champ avec « Champ à placer… », puis **faites glisser** sa zone.
   - Agrandissez-la avec la poignée, ou saisissez X, Y, largeur et hauteur en millimètres.
   - Réglez la police, la taille (et la taille minimale), l'alignement, la couleur, 1 ou 2 lignes, et le caractère obligatoire.

   Les positions sont enregistrées en **millimètres depuis le coin haut-gauche de la page**.
   Elles ne dépendent pas de l'écran utilisé et valent aussi en portrait.
3. **Textes du gabarit**, si vous placez ces champs :
   - intitulé du document ;
   - nom et fonction du signataire ;
   - objet du certificat.
4. **Règle d'émission** :
   - **Diplôme** :
     - « Décision de l'administration » (par défaut : aucune condition automatique, c'était le fonctionnement de FEBA) ;
     - ou « Moyenne annuelle minimale », calculée avec les fonctions de notes existantes : sur 20, convertie sur 10 au primaire.
   - **Certificat** :
     - « Élève inscrit dans une classe pour l'année » (par défaut) ;
     - ou « Décision de l'administration ».
5. **Aperçu** : le serveur rend le document avec des valeurs d'exemple longues et accentuées, filigrané « APERÇU », avec les cadres des zones.
6. **Enregistrer et vérifier**. FEBA :
   - contrôle qu'aucune zone ne **recouvre du texte du fond** (titre, mention imprimée…), les pointillés et soulignés de remplissage restant permis ;
   - produit un document d'essai ;
   - le **relit** (chaque valeur doit s'y retrouver, sans aucun marqueur `{{ }}`) ;
   - contrôle la page, les débordements et les superpositions.

   Le gabarit passe à « Valide, prêt à être activé » ou à « Invalide », avec la liste des erreurs.
7. **Activer**. Le gabarit devient « Actif — utilisé pour les documents ».

États affichés :
- Absent ;
- Téléversé, non validé ;
- Valide, prêt à être activé ;
- Actif ;
- Actif — remplacement en préparation ;
- Désactivé ;
- Invalide ou incompatible.

## 4. Champs disponibles

Les valeurs viennent **toujours** de la base FEBA. Elles ne sont jamais inventées.

| Champ | Source |
|---|---|
| Nom complet, matricule, date de naissance | Fiche de l'élève |
| Nom officiel et ville de l'académie | Identité de l'académie de l'élève (jamais d'une autre) |
| Niveau, classe, année scolaire | Inscription de l'élève pour l'année |
| Moyenne annuelle, mention | Notes réelles. La mention vient du barème d'appréciations de l'académie. Vide s'il n'y a aucune note. |
| Date d'obtention (diplôme) | **Saisie** à la production. Jamais déduite. |
| Date de délivrance | Date du jour de la production |
| Numéro de référence | Attribué **à la délivrance**, séquentiel par académie, par type et par année, sans doublon possible (verrou en base) |
| Intitulé, signataire, fonction, objet | Textes du gabarit (l'objet du certificat peut être précisé à la production) |

Un champ **obligatoire** sans donnée bloque la production, et la donnée manquante est nommée.
Un champ facultatif vide est signalé, puis laissé vide.

Un texte trop long est d'abord réduit jusqu'à la taille minimale, puis réparti sur deux lignes si le champ l'autorise.
S'il ne tient toujours pas, la production est **refusée** avec un message : il n'est jamais tronqué.

Les polices « Serif » (Crimson Pro, embarquée) couvrent les caractères accentués étendus.
Les polices standard du PDF (Helvetica, Times) refusent explicitement un caractère hors du jeu Windows‑1252.

## 5. Produire les documents

Les documents se produisent dans l'écran **Documents officiels**.

**Pour un élève** :
1. Cliquez sur « Produire un document ».
2. Choisissez le type, puis l'élève.

   Le serveur affiche :
   - le gabarit retenu (version téléversée active, sinon le gabarit intégré prévu pour l'académie) ;
   - les valeurs qui seront imprimées ;
   - les données manquantes et les refus de la règle d'émission.
3. **Aperçu** : un PDF filigrané. Rien n'est enregistré et aucun numéro n'est consommé.
4. Confirmez l'académie émettrice, puis cliquez sur « Produire ». Un brouillon est créé.
5. Cliquez sur **Délivrer**. FEBA :
   - revérifie la règle ;
   - attribue le numéro ;
   - régénère le PDF ;
   - le rend définitif.

**Par classe** : « Production par classe » crée un brouillon par élève, chacun sur le gabarit de **son** académie.
Les élèves refusés sont listés avec leur motif. « Délivrer les brouillons » délivre ensuite le lot.

Les documents se téléchargent depuis la liste, uniquement par une route authentifiée.
Chaque document conserve :
- son historique (production, délivrance, révocation, remplacement) ;
- la version du gabarit qui l'a produit ;
- l'empreinte du fond et l'empreinte du PDF.

## 6. Remplacer, désactiver, supprimer

- **Remplacer** : téléversez un nouveau fichier. Vous pouvez reprendre la configuration de la version précédente.
  - La version active reste utilisée tant que la nouvelle n'est pas vérifiée **puis** activée.
  - À l'activation, l'ancienne passe à « Remplacé ».
  - **Les documents déjà délivrés ne changent jamais** : leur fichier est conservé tel quel (empreinte vérifiée par les tests).
- **Modifier une version active** : c'est impossible. « Nouvelle version » la duplique en brouillon.
  Une version qui a servi n'est jamais modifiée, sinon ses documents ne pourraient plus être rejoués.
- **Brouillon produit sur une version remplacée** : sa délivrance est refusée. Produisez un nouveau brouillon.
- **Désactiver** : la production de ce type s'arrête pour l'académie, sauf si un gabarit intégré est prévu pour elle.
  Les documents délivrés restent consultables. « Réactiver » revérifie la version avant de la remettre en service.
- **Supprimer** : seulement une version qui n'a **jamais** servi.
  Pour la version active, une confirmation explicite est demandée.
  Élèves, inscriptions, notes et documents ne sont jamais touchés.

## 7. Académies FEBA et FEBA FHA, et académies non classées

FEBA et FEBA FHA ont des **gabarits intégrés** livrés avec l'application.
Ils continuent de servir tant qu'aucun gabarit téléversé n'est actif pour l'académie.
Dès qu'un gabarit téléversé est activé, il prime.
La numérotation continue sur le **même compteur** : il n'y a pas de doublon `FEBA-DIP-2026-0001`.

Une académie **non classée** peut téléverser ses gabarits normalement.
La règle « Moyenne annuelle » s'appuie sur le cycle du **niveau** de l'élève, qui existe même si l'académie n'est pas classée.
Un élève sans classe pour l'année est refusé, avec le motif.

## 8. Exploitation

- **LibreOffice** (paquets `libreoffice-writer-nogui` et `libreoffice-impress-nogui`) et les polices compatibles Microsoft sont installés dans `backend/Dockerfile.prod` et `backend/Dockerfile.dev`.
  - L'image de production grossit d'environ 450 Mo.
  - Rien n'est à installer à la main sur le serveur.
  - Sans LibreOffice (poste de développement), les formats bureautiques sont refusés avec un message, et l'écran l'indique.
- **Réglages facultatifs** dans `.env.prod` :
  - `DOCUMENT_CONVERSION_TIMEOUT` : délai maximal d'une conversion, en secondes (90 par défaut) ;
  - `LIBREOFFICE_BINARY` : chemin de `soffice`, détecté automatiquement.
- **Dépendances Python**, dans `backend/requirements/base.txt` :
  - `pypdf==6.14.2` : lecture et fusion des PDF ;
  - `pypdfium2==4.30.0` : aperçu et retrait des marqueurs ;
  - `olefile==0.47` : contrôle des DOC et PPT.
- **Stockage** : l'original et le fond normalisé sont dans `PRIVATE_MEDIA_ROOT/academy_templates/<académie>/<type>/`, sous des noms aléatoires.
  - Ce dossier est dans le volume `private_media_prod`, persistant.
  - Il est sauvegardé par `scripts/backup_files.sh` (archive `media` + `private_media`).
- **Migrations** :
  - `documents.0002_academy_document_templates` ;
  - `documents.0003_template_conversion` : format d'origine, empreinte du fond normalisé, rapport de conversion. Aucune donnée existante n'est modifiée ; les versions déjà téléversées reçoivent leur format d'origine.
- **Durée** : une conversion bureautique prend de 2 à 6 s (mesuré). Elle a lieu au téléversement, jamais à la production des documents, qui reste de l'ordre de 0,1 s.
