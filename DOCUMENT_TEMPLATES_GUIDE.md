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

| Format | Utilisation | Remarques |
|---|---|---|
| **PDF** | La page choisie est reprise **telle quelle** (vectorielle), et les champs sont dessinés par-dessus. | Couleurs, bordures et signatures préimprimées sont conservées sans perte. Si le PDF a plusieurs pages (10 au plus), on choisit la page utilisée : le document délivré n'en contient qu'**une**. |
| **PNG / JPEG** | L'image est inscrite dans la page choisie (A4 ou A5, paysage ou portrait, ou Lettre US) **sans déformation**, centrée. | 600 px minimum sur le plus grand côté. En dessous de 150 dpi, un avertissement de qualité s'affiche ; 300 dpi est l'idéal. Une photo de téléphone tournée par l'EXIF est redressée. |
| **DOCX** | **Refusé.** | Le convertir exigerait LibreOffice sur le serveur, et la mise en page varie d'une version à l'autre. Dans Word : « Enregistrer sous » → PDF, puis téléverser le PDF. |

Contrôles appliqués à chaque téléversement :
- taille maximale : 10 Mo ;
- l'extension, le type annoncé et le **contenu réel** doivent concorder : un PDF renommé `.png` est refusé ;
- un fichier corrompu ou tronqué est refusé ;
- un PDF chiffré ou contenant du contenu actif est refusé (JavaScript, lancement de programme, fichiers joints, formulaires dynamiques) ;
- une image de plus de 40 millions de pixels est refusée.

Le fichier est rangé dans le **stockage privé** (`PRIVATE_MEDIA_ROOT/academy_templates/<académie>/<type>/`).
Son nom est aléatoire. Il n'a aucune URL publique : il n'est lisible que par les routes
authentifiées de l'administration de l'académie.

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

- **Dépendances** : `pypdf==6.14.2` (lecture et fusion des PDF) et `pypdfium2==4.30.0` (aperçu des pages PDF).
  - Elles sont déclarées dans `backend/requirements/base.txt` et installées dans l'image Docker de production.
  - Ce sont des roues autonomes : aucun paquet système, aucune variable d'environnement nouvelle.
- **Stockage** : le volume `private_media_prod` existe déjà dans `docker-compose.prod.yml` et survit aux redémarrages.
  `scripts/backup_files.sh` le sauvegarde désormais. **Avant cette version, il ne sauvegardait que `media/`** (voir `FINAL_REPORT.md`, § D).
- **Migration** : `documents.0002_academy_document_templates`.
  - Elle crée deux tables et une colonne facultative.
  - Elle ne modifie aucune donnée existante.
