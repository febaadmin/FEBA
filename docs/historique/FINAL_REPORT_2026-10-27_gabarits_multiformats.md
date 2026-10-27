> **DOCUMENT HISTORIQUE** — version « gabarits multiformats ». Voir `FINAL_REPORT.md` pour la version en cours.

# FEBA — Gabarits multiformats : Word, OpenDocument, RTF, PowerPoint, images

27 octobre 2026 · branche `feat/gabarits-multiformats`.

- **Départ** : commit `efdec5b` (archive `FEBA_GABARITS_DIPLOMES_CERTIFICATS_VALIDEE.zip`, vérifiée identique).
- **Commit livré** : `SOURCE_COMMIT.txt` dans l'archive.
- **Statuts** : PASS · FAIL · BLOCKED · NOT RUN · SIMULATED.
- **Documents associés** : tests dans `TEST_REPORT.md`, mode d'emploi dans `DOCUMENT_TEMPLATES_GUIDE.md`, actions dans `MANUAL_PRODUCTION_ACTIONS.md` § 0000000, limites dans `KNOWN_LIMITATIONS.md` § 00000000.

**Validations en local uniquement**, avec :
- l'image Docker contenant LibreOffice ;
- PostgreSQL, Mailpit et plugNmeet locaux ;
- Chrome réel ;
- la pile de production (`docker-compose.prod.yml`) construite **depuis l'archive livrée** (voir `DELIVERY_VERIFICATION_GABARITS_MULTIFORMATS.txt`).

Rien n'a été fait en préproduction ni sur Hetzner (SSH refusé). Rien n'a été déployé en production.

---

## Les dix problèmes à résoudre

| # | Problème | Traitement | Preuve |
|---|---|---|---|
| 1 | Formats limités (PDF, PNG, JPEG) | Ajout de **DOCX, DOC, ODT, RTF, PPTX, PPT, ODP, TIFF, WEBP**, chacun converti et testé. Les formats non exploitables (DOCM, XLSX, GIF, SVG, HEIC…) sont refusés **avec la cause**. | `test_template_conversion.py` (un test par format) |
| 2 | DOC/DOCX refusés | Le fichier Word est téléversé **tel quel** depuis l'écran. Le serveur le convertit (LibreOffice sans interface, dans l'image Docker). Aucun export manuel. | Tests API et navigateur, avec les vrais `.docx` et `.doc` envoyés à FEBA |
| 3 | Fichier seulement stocké | Le fond converti sert à **produire** les documents : données de l'élève, numéro, délivrance. Le PDF est relu. | Les 4 combinaisons A/B, scénario navigateur |
| 4 | Pages multiples, mises en page variées | Choix de la page de fond. La page des marqueurs est retenue automatiquement. Dimensions, orientation, bordures, couleurs, logos et tableaux sont conservés. | Document de deux pages, paysage et portrait, relevé des couleurs, image du logo, texte des tableaux |
| 5 | Ne pas casser l'éditeur | Fond normalisé en PDF, même repère en mm, même moteur. Les marqueurs `{{ champ }}` deviennent des champs **déjà placés**, retirés du fond **sans rien décaler**. | Tests « aucune superposition », éditeur en navigateur |
| 6 | Isolation | Original, fond normalisé, versions et documents : rangés par académie, introuvables (404) depuis une autre. | Tests multi-académies, navigateur, conteneur de production |
| 7 | Dépendances absentes de Docker | LibreOffice, les polices compatibles Microsoft et `olefile` sont dans `Dockerfile.prod` et `Dockerfile.dev`. Les tests de conversion ont tourné **dans l'image**, et l'image de production a été construite **depuis le ZIP**. | Campagne dans le conteneur ; vérification de livraison |
| 8 | Conversions en échec | Code de retour, présence et lisibilité du PDF, délai maximal (processus tué). Aucun gabarit partiel, aucun fichier ni répertoire temporaire restant, message clair. | Tests : délai dépassé, XML illisible, DOC abîmé, archive piégée, macros |
| 9 | Documents anciens | Les documents délivrés gardent leur fichier et leur version. Un brouillon fait sur une version remplacée n'est pas délivrable. | Tests de remplacement ; montée de version sur la pile de production |
| 10 | Sécurité, régressions | Voir § D. Les campagnes complètes sont vertes. | `TEST_REPORT.md` |

## A. Interface

L'écran **« Gabarits des documents »** reste à `/admin/document-templates` et `/superadmin/document-templates` :
- l'académie est choisie dans le sélecteur ;
- l'administrateur ne voit que la sienne ;
- tout est vérifié par le serveur.

Ce qui change à l'écran :
- **Formats acceptés** : la liste est calculée par le serveur. Si LibreOffice manque, l'écran le dit.
- **Sélecteur de fichier** : il propose les extensions réellement prises en charge.
- **Pendant le téléversement** : « Conversion en cours… ».
- **Chaque version affiche** :
  - le format d'origine (« Word (DOCX) ») et le fond normalisé (« → fond normalisé PDF ») ;
  - la durée de conversion ;
  - les marqueurs repérés et les champs placés automatiquement ;
  - la page retenue ;
  - un avertissement si les dimensions diffèrent de la version précédente ; la vérification est alors de nouveau exigée ;
  - le rapport de vérification.
- **« Original »** télécharge le fichier tel que téléversé (DOCX, ODT…).

## B. Architecture

**Conversion** : `apps/documents/conversion.py` est le **point d'entrée unique**. Il assure :
- la détection du format réel (signature, structure ZIP/OLE) ;
- les contrôles de sécurité ;
- la conversion LibreOffice ;
- la normalisation des images ;
- le traitement des marqueurs.

`academy_templates.py` ne fait que l'appeler.

**LibreOffice** :
- `soffice --headless --convert-to`, arguments passés en liste, nom de fichier fixe ;
- un répertoire et un **profil** jetables par conversion ;
- macros désactivées (niveau de sécurité maximal) ; liens externes jamais mis à jour ;
- environnement vide (aucune variable du serveur, donc aucun secret) ;
- taille de fichier limitée, pas de fichier `core` ;
- délai maximal, avec destruction du groupe de processus ;
- répertoire supprimé dans tous les cas.

**Marqueurs** : retirer le texte du marqueur décalait la ligne (constaté en navigateur, voir § D). La méthode retenue est la suivante :
1. Chaque marqueur est isolé dans sa propre portion de texte OpenDocument, avec un style neutre.
2. LibreOffice produit **un seul** PDF.
3. Les positions des marqueurs sont relevées sur ce PDF.
4. Leurs objets texte sont retirés de **ce même PDF** (PDFium). Les autres pages sont reprises intactes.

**Contrôle de recouvrement** : la vérification refuse une zone qui recouvre du texte du fond. Les pointillés et soulignés de remplissage restent permis.

**Modèle** : migration `documents.0003_template_conversion`.
- Nouveaux champs : `source_format` (format réel), `normalized_sha256` (empreinte du fond converti, vérifiée), `conversion` (moteur, durée, marqueurs).
- `render_path` désigne le fond normalisé.

**Docker** : `libreoffice-writer-nogui`, `libreoffice-impress-nogui`, fonts-liberation(2), Carlito, Caladea, DejaVu.
- L'image grossit d'environ 450 Mo.
- `olefile==0.47` est ajouté à `requirements/base.txt`.
- Nouveaux fichiers **`.dockerignore`** (backend et frontend).

**Réglages** (facultatifs) : `DOCUMENT_CONVERSION_TIMEOUT` (90 s) et `LIBREOFFICE_BINARY`.

**Taille maximale** : 20 Mo. nginx accepte déjà 25 Mo.

## C. Génération

Rien ne change dans la production des documents : même moteur, mêmes règles d'émission, même numérotation, même historique.

Seul le fond diffère : c'est le PDF normalisé, figé par son empreinte au moment de la vérification. La conversion a lieu au téléversement (2 à 6 s mesurées), jamais au moment de produire un document.

## D. Défauts trouvés et corrigés pendant la mission

| Défaut (reproduit) | Correction | Test |
|---|---|---|
| **Image Docker** : aucun `.dockerignore`. `docker build` copiait `media/` et `private_media/` du poste dans l'image : diplômes, dossiers et pièces jointes, soit **2,9 Go ici**. | `.dockerignore` backend et frontend. Image de développement : 7,3 Go → 1,8 Go. | Construction mesurée avant et après |
| **Marqueurs** : remplacés par des espaces, ils décalaient les lignes centrées. La date venait chevaucher « Délivré le », l'année chevaucher « pour l'année scolaire » (vu sur les PDF rendus). | Isolement, puis retrait des objets texte du même PDF | `MarkerLayoutTests` (positions mesurées dans le PDF final) |
| **PDFium** : en régénérant une page, il réécrivait les polices partagées ; le texte des autres pages devenait illisible. | Recomposition page par page (pypdf) | Document de deux pages |
| **Zone pré-placée** : elle s'étendait jusqu'au marqueur suivant et recouvrait le tiret « — » du fond. | Bornée par le texte du fond le plus proche | `MarkerNeighbourTests` |
| **Recouvrement** : aucune vérification ne détectait une zone posée sur le texte du fond. | La vérification la refuse en citant le texte. | `test_zone_qui_recouvre_le_texte_du_fond_refusee` |
| **TIFF multipage** sans résolution déclarée : page de 44 m. | Mise à l'échelle sur un A4 | `test_tiff_de_plusieurs_pages…` |
| **Index de caractères** de PDFium décalé par les caractères générés. | Lecture caractère par caractère | Idem |
| **Rendus simultanés** dans un même processus : ReportLab partage l'objet d'une police TrueType, et son découpage n'est pas sûr entre fils. Une délivrance sur 6 échouait (`IndexError` dans `ttfonts.makeSubset`). Trouvé par la campagne **lancée depuis l'archive**, puis reproduit à 12 fils. Les processus gunicorn de production ne partagent rien, mais un serveur à fils, oui. | Verrou de rendu commun au moteur (`renderer.RENDER_LOCK`) | `ConcurrentRenderingTests` : 180 rendus simultanés, 0 échec ; il échoue sans le correctif |

Audit des fonctionnalités voisines :
- permissions et isolation : tests d'accès croisés rejoués ;
- documents délivrés : intacts après montée de version ;
- sauvegarde : `private_media` (originaux et fonds normalisés compris) archivé, puis restauré sur la pile de production ;
- migrations : propres ;
- frontend : 375 tests ;
- e2e documents et devises : verts.

## E. Livraison

Voir `DELIVERY_VERIFICATION_GABARITS_MULTIFORMATS.txt` à côté de l'archive : commit, taille, SHA-256, tests depuis l'extraction, image construite depuis l'archive, conversion DOCX dans ce conteneur, deux académies, sauvegarde et restauration.

| Statut | Éléments |
|---|---|
| **BLOCKED** | Hetzner, préproduction, plugNmeet de production (SSH refusé) ; SMTP Hostinger ; Twilio |
| **NOT RUN** | Gabarits officiels **réels** des académies (non fournis : les fichiers de test sont fabriqués) ; impression papier ; partage d'écran ; réunion entre réseaux ; CDN |
