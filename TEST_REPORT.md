# FEBA — Rapport de tests : gabarits officiels des diplômes et certificats

Tests du 26 octobre 2026, branche `feat/gabarits-diplomes-certificats`, **en local uniquement**.

- Version précédente : `docs/historique/TEST_REPORT_2026-10-26_academies_appreciations.md`.
- Statuts : PASS · FAIL · BLOCKED · NOT RUN · SIMULATED. Un test ignoré n'est jamais compté comme réussi.
- Vérification depuis l'archive extraite : `DELIVERY_VERIFICATION_GABARITS.txt`, livré à côté du ZIP.

## 1. Tests automatisés (code final, commit 4eff65c)

| Suite | Résultat | Statut |
|---|---|---|
| Backend PostgreSQL 16 + Mailpit SMTP + plugNmeet v2.5.3 réel | **1 882 réussis, 0 ignoré, 0 échec** | PASS |
| Backend SQLite | 1 869 réussis, **13 ignorés**, 0 échec. Les 13 exigent PostgreSQL, Mailpit ou plugNmeet ; tous ont été exécutés et réussis sous PostgreSQL. | PASS |
| Frontend Vitest | 372 / 372 (50 fichiers) | PASS |
| ESLint | 0 erreur ; 74 avertissements, tous antérieurs, aucun ajouté | PASS |
| Build Vite de production | réussi | PASS |
| `makemigrations --check` | aucune migration manquante | PASS |
| `build_branding_assets.py --check` | ressources dérivées conformes | PASS |

### Nouveaux tests backend

`test_academy_document_templates.py` (62 tests) :

- **Téléversement**
  - diplôme PNG et certificat PDF valides ;
  - formats refusés : GIF, TXT, DOCX (avec explication) ;
  - PDF et PNG corrompus ;
  - fichier de plus de 10 Mo ;
  - extensions falsifiées (PDF→`.png`, PNG→`.pdf`, PNG→`.jpg`) et type MIME incohérent ;
  - PDF contenant du JavaScript ;
  - PDF de 11 pages, image trop petite ;
  - JPEG redressé selon l'EXIF ;
  - stockage privé, nom aléatoire, rangé par académie, aucun chemin exposé ;
  - relecture depuis la base et le disque ;
  - fond et original servis en `no-store`.
- **Configuration**
  - superposition, zone hors page, champ étranger au type : refusés ;
  - nom de l'élève exigé ;
  - texte fixe placé sans valeur ;
  - une version validée modifiée revient au brouillon ;
  - une version active n'est pas modifiable, on la duplique ;
  - aperçu filigrané sans création de document ;
  - PDF multipage : la page choisie est la seule restituée.
- **Génération**
  - les **4 combinaisons** (A diplôme PNG, A certificat JPEG, B diplôme PDF, B certificat PDF portrait). Chaque PDF est **ouvert**, et on vérifie :
    - le texte : nom, numéro, aucune donnée de l'autre académie ;
    - la taille de page, paysage ou portrait ;
    - la **couleur du fond relevée par PDFium** ;
  - données réelles : matricule, nom officiel, version et empreinte du gabarit ;
  - certificat : objet, classe, année ;
  - ouverture par pypdf **et** PDFium, dessin vectoriel du fond conservé ;
  - accents et ligatures (« Œuvray », « Çaëlle ») ;
  - caractère hors police refusé clairement ;
  - nom long sur deux lignes, puis refus sans troncature (aucun document créé) ;
  - champ obligatoire manquant et champ facultatif vide ;
  - aperçu par élève sans document ni numéro consommé ;
  - historique et empreinte du téléchargement ;
  - **remplacement** : le document délivré garde la même empreinte et son fond rouge, les nouveaux sortent en jaune, l'ancienne version ne peut pas être supprimée ;
  - brouillon sur une version remplacée : non délivrable ;
  - désactivation, puis réactivation ;
  - suppression de la version active avec confirmation (élèves, inscriptions et notes intacts) ;
  - fichier disparu du stockage : erreur claire, sans document ;
  - numéros uniques ;
  - deux versions actives impossibles en base.
- **Éligibilité**
  - moyenne annuelle : 14,67/20 accepté avec mention, 7,33/20 refusé, notes inchangées ;
  - aucune note : refus ;
  - certificat refusé à un élève sorti ;
  - décision administrative par défaut pour le diplôme ;
  - règle revérifiée à la délivrance ;
  - date d'obtention saisie, jamais inventée.
- **Lot**
  - classe de 3 élèves : 2 produits, 1 refusé avec motif, délivrance en lot sur le bon fond ;
  - classe d'une autre académie : 404.
- **Permissions et isolation**
  - enseignant, parent et élève : 403 ;
  - **accès croisés par identifiant manipulé** (détail, fond, original, aperçu, vérification, désactivation, duplication, modification, suppression) : 404, gabarit intact ;
  - élève, classe et document d'une autre académie : 404 ;
  - corps de requête `academy` / `school` / `?school_id` : ignorés ;
  - le service refuse un gabarit étranger ;
  - le super administrateur suit l'académie choisie ; en mode consolidé, l'élève détermine le fond ;
  - même nom de fichier dans deux académies.
- **Cinq académies** : 5 fonds de couleurs distinctes, chaque diplôme a le bon fond, accès croisés 5 × 5.
- **Choix du gabarit** : priorité au gabarit téléversé sur le gabarit intégré ; clé de numérotation partagée.
- **Suppression d'une académie vide** : les fichiers des gabarits sont supprimés aussi.
- **Concurrence réelle sous PostgreSQL**, avec fils d'exécution et connexions distincts :
  - 6 délivrances simultanées donnent 6 numéros distincts ;
  - 2 activations simultanées laissent 1 seule version active ;
  - 3 téléversements simultanés donnent les versions 1, 2 et 3.

`test_backup_private_media.py` (6 tests). Les scripts sont **exécutés**, pas relus :
- l'archive contient `private_media` ;
- restauration complète ;
- une ancienne archive n'efface pas `private_media` ;
- installation sans fichier privé ;
- la copie hors site est atteinte dès la première nuit ;
- les valeurs par défaut correspondent à `docker-compose.prod.yml`.

### Nouveaux tests frontend

- `templateLayout.test.js` (5) : millimètres, conversion écran vers page, superpositions.
- `DocumentTemplates.test.jsx` (8) : deux espaces, états, jamais « prêt » au seul téléversement, multipart, mode consolidé.
- `TemplateEditor.test.jsx` (3) : il **échoue sans le correctif** du champ ajouté sans nom.
- `OfficialDocuments.kind.test.jsx` (4) : état des gabarits par type, vérification préalable, refus, saisie de la date d'obtention.

## 2. Navigateur réel (Chrome, pile locale : runserver, Vite, PostgreSQL, Mailpit)

### `e2e/parcours-gabarits.mjs` — **34 contrôles, 0 échec : PASS**

- **FEBA FHA**
  - faux PNG et PDF corrompu refusés, avec le message affiché ;
  - diplôme PDF téléversé ;
  - zone du nom **déplacée à la souris** (31,5 → 67,5 mm) ;
  - aperçu rendu par le serveur ;
  - vérification, puis activation ;
  - production avec vérification préalable « version 1 », puis délivrance `FHA-DIP-2026-0005` (numéros précédents consommés par les passages antérieurs sur la même base) ;
  - empreinte du PDF téléchargé égale à l'empreinte affichée.
- **Remplacement** : configuration reprise, état « remplacement en préparation », v2 active et v1 archivée, diplôme délivré **inchangé**.
- **FEBA** : certificat PNG en A4 portrait déduit de l'image, vérifié, activé, délivré `FEBA-CER-2026-0003`.
- **Administrateur FHA** : seule son académie est visible ; gabarit et certificat de Cotonou en 404 (détail, fond, original, désactivation, téléchargement).
- **Console** : aucune erreur JavaScript ni réponse 5xx. Les 400 et 404 sont ceux provoqués volontairement.

Les PDF délivrés ont été relus (texte et image) :
- diplôme de 297 × 210 mm, fond vectoriel intact ;
- certificat de 210 × 297 mm, image non déformée ;
- aucune annotation ;
- données aux emplacements placés.

### Scénarios e2e existants

| Scénario | Résultat | Statut |
|---|---|---|
| `parcours-documents-officiels` (adapté au choix par type) | 0 échec | PASS |
| `devises-et-documents` | 0 échec, au second passage. Le premier passage a révélé ma régression (état des gabarits absent de l'écran de production), corrigée depuis. | PASS |
| `espaces-anglais`, `site-public-anglais`, `parcours-preinscription-feba`, `parcours-rapports-mensuels`, `parcours-v9` | 0 échec. Les trois derniers ont été rejoués avec Mailpit et l'adresse d'API de cette pile. | PASS |
| `academies` | 2 à 5 contrôles d'effectif en échec, variables d'un passage à l'autre. La **version précédente livrée (eab95df), rejouée sur la même pile, échoue de la même façon** : c'est la cadence du scénario face au serveur de développement mono-processus, sur l'écran Élèves, non modifié. Ce scénario passait sur la pile Docker de développement lors de la livraison précédente. | FAIL (environnement, non imputable) |

## 3. Pile Docker de PRODUCTION (locale, `scripts/deploy_feba.sh`)

| Contrôle | Résultat | Statut |
|---|---|---|
| Version précédente déployée, puis certificat FEBA délivré avec le gabarit intégré (`FEBA-CER-2026-0001`) | conforme | PASS |
| Montée vers cette version par `deploy_feba.sh` : sauvegarde vérifiée, construction, migration `documents.0002`, santé | réussie | PASS |
| `pypdf 6.14.2` et `pypdfium2 4.30.0` importés dans l'image | conforme | PASS |
| Ancien certificat après la montée | même empreinte, version de gabarit absente (gabarit intégré) | PASS |
| Dans le conteneur : gabarit PDF téléversé, configuré, vérifié, activé ; diplôme produit et délivré `FHA-DIP-2026-0001`, texte relu (accents) | conforme | PASS |
| Temps de production et de délivrance d'un document | 0,105 s | PASS |
| Temps de rendu moyen | 0,019 s | PASS |
| **Conteneurs détruits puis recréés** (`down` puis `up`, nouvel identifiant de conteneur) : gabarit, diplôme et ancien certificat intacts, rendu de nouveau possible | conforme | PASS |
| Santé HTTPS | 200 | PASS |
| `check --deploy` | aucun problème | PASS |
| `backup_database.sh` et `backup_files.sh` exécutés contre la pile | gabarit, diplôme et certificat dans l'archive | PASS |
| Restauration des fichiers (gabarits supprimés puis restaurés) | conforme | PASS |
| Restauration de la base (donnée modifiée puis restaurée, santé 200) | conforme, après correction des deux défauts du script | PASS |

## 4. Non exécuté ou bloqué

| Contrôle | Statut |
|---|---|
| Hetzner, préproduction, plugNmeet de production | BLOCKED (SSH refusé) |
| SMTP Hostinger, Twilio | BLOCKED |
| Impression papier d'un diplôme | NOT RUN |
| Gabarits officiels réels des académies (non fournis). Les fonds de test ont été fabriqués : PDF vectoriel et PNG à 300 dpi. | NOT RUN |
| Partage d'écran, réunion entre réseaux, CDN de production | NOT RUN |

Aucun test n'est SIMULATED. Les faux `docker` et `rclone` des tests de scripts sont des tests unitaires de scripts shell. Les mêmes scripts ont aussi été exécutés pour de vrai contre la pile de production locale (§ 3).
