# FEBA — Rapport de tests : gabarits multiformats

27 octobre 2026, branche `feat/gabarits-multiformats`, **en local uniquement**.

- Version précédente : `docs/historique/TEST_REPORT_2026-10-26_gabarits.md`.
- Statuts : PASS · FAIL · BLOCKED · NOT RUN · SIMULATED. Un test ignoré n'est jamais compté comme réussi.
- Vérification de l'archive : `DELIVERY_VERIFICATION_GABARITS_MULTIFORMATS.txt`, livré à côté du ZIP. Elle couvre les tests depuis l'extraction, l'image construite depuis l'archive, la conversion dans ce conteneur et la sauvegarde/restauration.

## 1. Tests automatisés (code final, commit 8a2c313)

Le backend a été exécuté **dans l'image Docker de FEBA qui contient LibreOffice** (`backend/Dockerfile.dev`), avec le dépôt entier monté.

| Suite | Résultat | Statut |
|---|---|---|
| Backend PostgreSQL 16 + Mailpit SMTP + plugNmeet v2.5.3 réel | **1 919 réussis, 0 ignoré, 0 échec** | PASS |
| Backend SQLite | 1 905 réussis, **14 ignorés**, 0 échec. Les 14 exigent PostgreSQL, Mailpit ou plugNmeet ; tous ont été exécutés et réussis sous PostgreSQL. | PASS |
| `makemigrations --check` | aucune migration manquante | PASS |
| Frontend Vitest | 375 / 375 (50 fichiers) | PASS |
| ESLint | 0 erreur ; 74 avertissements, tous antérieurs | PASS |
| Build Vite | réussi | PASS |

Sur un poste **sans** LibreOffice, 31 des 37 tests de conversion sont ignorés avec ce motif (constaté sur macOS). Ils ont tous été exécutés, et réussis, dans le conteneur ci-dessus.

### Nouveaux tests : `tests/test_template_conversion.py` (37 tests exécutés, dont 3 hérités)

Les fichiers d'origine (DOCX, DOC, ODT, RTF, PPTX, PPT, ODP) sont **envoyés à l'API tels quels** : aucun PDF n'est préparé à l'avance. Chaque document délivré est **rouvert** pour vérifier :
- le texte ;
- les dimensions et l'orientation ;
- la couleur du bandeau, relevée par PDFium ;
- la bordure dorée ;
- la présence de l'image du logo ;
- le texte du tableau ;
- l'absence de `{{` et de `}}` ;
- l'original conservé, octet pour octet ;
- le fond normalisé présent.

**Formats** — chacun est téléversé par l'API, converti, vérifié, activé, puis le document est produit, délivré, téléchargé et rouvert :
- DOCX paysage avec marqueurs (5 champs placés automatiquement) ;
- DOC (Word 97) ;
- ODT ;
- RTF ;
- PPTX ;
- PPT ;
- ODP ;
- certificat DOCX portrait **sans** marqueur, champs placés dans l'éditeur ;
- DOCX de deux pages : la page 2, celle des marqueurs, est retenue, et la page reste modifiable ;
- nom de fichier complexe (apostrophe typographique, tiret, guillemets, #) ;
- TIFF ;
- WEBP ;
- TIFF de deux pages, page choisie.

**Marqueurs et mise en page** :
- marqueur inconnu : la vérification le refuse en le nommant ;
- marqueur coupé entre deux portions Word : reconnu ;
- isolement XML : découpage, imbrication, cas sans marqueur ;
- **aucune superposition**, mesurée dans le PDF final :
  - l'année commence après « scolaire » ;
  - la date commence après « Délivré le » ;
  - le nom de l'académie s'arrête avant le tiret du fond ;
- zone posée sur le titre du fond : refusée, puis acceptée une fois déplacée.

**Erreurs** — refus propres, sans version créée, sans fichier stocké, sans répertoire temporaire restant :
- DOCX avec macros ;
- extensions falsifiées (PDF→`.docx`, DOCX→`.odt`, PPT→`.doc`) ;
- DOCX tronqué ;
- DOCX au XML illisible : « conversion échouée » ;
- archive piégée (300 Mo dans 2 Mo) ;
- **délai de conversion dépassé** : processus interrompu ;
- RTF avec objet OLE ;
- PDF sans page ;
- PDF contenant des marqueurs : vérification refusée.

**Multi-académies** :
- A : diplôme **DOCX** et certificat **PDF** ; B : diplôme **PNG** et certificat **DOCX**. Les quatre documents ont le bon fond et les bonnes données, et leurs numéros sont distincts ;
- les gabarits de B (détail, fond, original, désactivation) renvoient 404 depuis A ;
- **gabarit remplacé pendant une production** : le brouillon n'est plus délivrable, et le document déjà délivré reste identique.

**Concurrence (PostgreSQL)** : trois conversions simultanées (DOCX, ODT, PPTX) donnent trois versions distinctes, toutes converties, sans conflit de profil LibreOffice.

### Tests mis à jour

Trois tests de la version précédente ont été adaptés parce que l'exigence a changé. Ce qu'ils vérifient est conservé :
- le refus de DOCX devient le refus d'un DOCX **corrompu** ;
- le message générique de format refusé devient un message **expliqué** ; les refus XLSX et DOCM ont été ajoutés ;
- le nom du fond redressé d'un JPEG change, et son format d'origine est désormais vérifié.

Frontend : +3 tests dans `DocumentTemplates.test.jsx` :
- formats annoncés par le serveur et proposés par le sélecteur ;
- Word téléversé directement, avec « Conversion en cours… » ;
- format d'origine, fond normalisé, marqueurs et avertissement de dimensions.

## 2. Navigateur réel (Chrome ; backend dans le conteneur LibreOffice ; PostgreSQL)

| Scénario | Résultat | Statut |
|---|---|---|
| `parcours-gabarits-multiformats` | **28 contrôles, 0 échec**. Formats annoncés ; faux DOCX refusé avec un message explicite ; **DOCX téléversé depuis l'écran et converti (4,4 s)** ; éditeur sur le fond converti, avec les 5 champs aux marqueurs ; vérification ; activation ; diplôme FHA délivré ; certificat DOCX portrait placé dans l'éditeur ; diplôme **PPTX** ; documents FEBA délivrés ; administrateur FHA : son diplôme Word seulement, gabarits et certificat de FEBA en 404 ; aucune exception ni réponse 5xx. | PASS |
| `parcours-gabarits` (PDF et images, version précédente) | 34 contrôles, 0 échec | PASS |
| `parcours-documents-officiels` | 54 contrôles, 0 échec | PASS |
| `devises-et-documents` | 14 contrôles, 0 échec | PASS |

PDF délivrés rouverts et rasterisés :
- diplôme Word de 297 × 210 mm ; certificat Word de 210 × 297 mm ; diplôme PowerPoint de 297 × 210 mm ;
- bordures, bandeaux, logo et tableaux conservés ;
- aucun marqueur ;
- aucune superposition.

Le premier passage avait montré deux superpositions, puis un tiret recouvert. Les trois ont été corrigés et sont désormais couverts par des tests.

## 3. Non exécuté ou bloqué

| Contrôle | Statut |
|---|---|
| Hetzner, préproduction, plugNmeet de production | BLOCKED (SSH refusé) |
| SMTP Hostinger, Twilio | BLOCKED |
| Gabarits officiels réels des académies (non fournis ; fichiers de test fabriqués) | NOT RUN |
| Impression papier | NOT RUN |
| Scénario `academies` (écran Élèves, non modifié) | NOT RUN. Il est instable sur le serveur de développement mono-processus ; voir le rapport précédent : même comportement sur la version précédente. |

Aucun test n'est SIMULATED. Les conversions sont réelles et faites par le LibreOffice de l'image.
