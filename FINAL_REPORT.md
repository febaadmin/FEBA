# FEBA : gabarits officiels des diplômes et certificats, par académie

26 octobre 2026, branche `feat/gabarits-diplomes-certificats`.

- **Départ** : commit `eab95df`, archive `FEBA_VERSION_ACADEMIES_INSCRIPTIONS_APPRECIATIONS_VALIDEE.zip`.
- **Commit livré** : voir `SOURCE_COMMIT.txt` dans l'archive.
- **Statuts** : PASS · FAIL · BLOCKED · NOT RUN · SIMULATED.
- **Où trouver le reste** :

| Sujet | Document |
|---|---|
| Détail des tests | `TEST_REPORT.md` |
| Mode d'emploi | `DOCUMENT_TEMPLATES_GUIDE.md` |
| Actions de l'exploitant | `MANUAL_PRODUCTION_ACTIONS.md` § 000000 |
| Limites | `KNOWN_LIMITATIONS.md` § 0000000 |

**Lieu des validations : en local uniquement.** Ce qui a servi :
- PostgreSQL 16, Mailpit et plugNmeet locaux ;
- Chrome réel ;
- la pile Docker de **production** (`docker-compose.prod.yml`, images construites par `scripts/deploy_feba.sh`), montée à partir de la version précédente.

Rien n'a été fait sur la préproduction ni sur Hetzner (accès SSH refusé). Rien n'a été déployé ni migré en production.

---

## A. Interface

**Emplacement.** Menu **« Gabarits des documents »** :
- `/admin/document-templates` pour l'administrateur d'une académie ;
- `/superadmin/document-templates` pour le super administrateur.

La production se fait dans **« Documents officiels »** (écran existant, complété).

**Rôles.**
- L'administrateur gère son académie et elle seule.
- Le super administrateur gère l'académie choisie dans le sélecteur. En mode « Toutes les académies », l'écran demande d'en choisir une.
- Enseignants, parents et élèves reçoivent une réponse 403.
- Tout est contrôlé par le serveur. L'académie n'est jamais lue dans la requête : un `academy` ou un `school_id` envoyé par le navigateur est ignoré (testé).

**Deux espaces distincts, « Gabarit du diplôme » et « Gabarit du certificat ».** Chacun affiche :
- l'état : Absent, Téléversé non validé, Valide prêt à être activé, Actif, Actif avec remplacement en préparation, Désactivé, Invalide ;
- la version en service : fichier, format, taille, page en mm et orientation, date de téléversement, auteur, date d'activation ;
- la version en préparation, avec le rapport de vérification ;
- l'historique des versions.

**Actions disponibles.**
- Téléverser, remplacer avec reprise de la configuration, placer les champs.
- Aperçu PDF, vérifier, activer, désactiver, réactiver.
- Nouvelle version (duplication), télécharger l'original.
- Supprimer : réservé à une version jamais utilisée, avec confirmation pour la version active.

L'écran « Documents officiels » affiche lui aussi, par type, le gabarit réellement utilisé et ses blocages.

**Éditeur de placement.**
- Il s'ouvre sur le fond réel, rendu par le serveur : PDFium pour un PDF.
- On ajoute les champs du catalogue, on les déplace à la souris, on les redimensionne par une poignée, ou on saisit les valeurs au dixième de millimètre.
- Réglages par champ : police, taille, taille minimale, alignement, couleur, 1 ou 2 lignes, obligatoire.
- Superpositions et zones hors page sont signalées avant l'envoi, puis refusées par le serveur.
- L'aperçu rendu par le serveur s'affiche dans l'éditeur, avec les cadres des zones.
- Les coordonnées sont en **millimètres depuis le coin haut-gauche de la page**. Elles ne dépendent pas de l'écran et valent pour le paysage comme pour le portrait.

## B. Architecture technique

**Moteur existant, audité avant de coder.**
- Des gabarits intégrés (JSON et fond PNG verrouillé par empreinte, calibrage en mm) sont rendus avec ReportLab.
- `GeneratedDocument` porte l'état, le numéro, l'empreinte et le journal.
- Le stockage est privé (`PRIVATE_MEDIA_ROOT`) et le téléchargement passe par une vue authentifiée.

Tout cela est **réutilisé** : même modèle de document, même numérotation, même stockage, même téléchargement, mêmes contrôles d'accès. Aucun second circuit de documents n'a été créé.

**Modèles** (migration `documents.0002_academy_document_templates`, sans modification des données) :
- `AcademyDocumentTemplate` : académie, type, version, fichier (nom aléatoire), format, empreinte, taille, nombre de pages, page choisie, dimensions, champs en mm, options (textes, règle d'émission), état, rapport de vérification, auteur, dates.
  - Contrainte en base : **une seule version active** par académie et par type.
  - Unicité des numéros de version.
- `AcademyTemplateEvent` : journal des opérations sur un gabarit.
- `GeneratedDocument.academy_template` : version qui a produit le document (PROTECT).

**Services.**
- `apps/documents/academy_templates.py` :
  - contrôle des fichiers, catalogue des champs, validation de la configuration ;
  - rendu : PDF fusionné par pypdf, image en mode « contain » par ReportLab ;
  - vérification par rendu d'essai relu ;
  - activation, désactivation, suppression ;
  - règle unique de choix du gabarit (`resolve_template`) ;
  - valeurs de l'élève, règles d'émission.
- `apps/documents/services.py` : `create_for_kind`, `create_from_academy_template`, délivrance et remplacement des documents produits sur gabarit téléversé.

**API.**
- `/api/documents/academy-templates/` :
  - liste et téléversement, détail, configuration, suppression ;
  - `background/`, `original/`, `preview/` ;
  - `validate/`, `activate/`, `disable/`, `reactivate/`, `duplicate/`.
- `/api/documents/check/` et `/api/documents/preview/` : vérification et aperçu sans écriture.
- `/api/documents/batch/` et `/api/documents/batch-issue/` : production et délivrance par classe.
- `POST /api/documents/` accepte désormais un `kind`.

**Formats.**
- Acceptés : PDF (1 à 10 pages, une seule utilisée), PNG, JPEG (EXIF redressé).
- **DOCX refusé**, avec une explication. Le convertir exigerait LibreOffice dans l'image et la mise en page varie selon les versions.

**Dépendances.** Elles sont installées dans l'image de production et vérifiées dans le conteneur :
- `pypdf==6.14.2`, déplacé de `dev` vers `base` ;
- `pypdfium2==4.30.0`, roue autonome, sans paquet système.

**Stockage.**
- Emplacement : `PRIVATE_MEDIA_ROOT/academy_templates/<académie>/<type>/<uuid>.<ext>`, en mode 0600.
- Volume : `private_media_prod`, déjà persistant.
- Aucune URL publique. Les réponses sont servies en `no-store` et `nosniff`.

**Sécurité des téléversements.**
- L'extension, le type MIME et la **signature réelle** du fichier doivent concorder.
- Taille maximale : 10 Mo. Les images de plus de 40 Mpx (bombes de décompression) sont refusées.
- Les fichiers corrompus ou tronqués sont refusés : ils sont décodés entièrement.
- Les PDF chiffrés ou actifs (JavaScript, Launch, fichiers joints, XFA…) sont refusés.
- Les annotations et actions du PDF d'origine sont retirées du document délivré.

## C. Génération des documents

1. **Choix du gabarit.** On prend la version téléversée **active** de l'académie **de l'élève**, sinon le gabarit intégré prévu pour cette académie, sinon on refuse. Ce n'est jamais le gabarit d'une autre académie.
   - En mode « Toutes les académies », l'élève détermine l'académie.
   - En lot, le gabarit est résolu élève par élève.
2. **Données.** Elles sont toutes lues dans la base, jamais inventées :
   - fiche de l'élève, identité de l'académie, inscription de l'année ;
   - moyenne annuelle et mention, par les fonctions de notes et le barème d'appréciations existants ;
   - date de délivrance du jour, numéro attribué à la délivrance ;
   - textes du gabarit.

   La **date d'obtention** est saisie, jamais déduite. Le navigateur ne peut fournir que la date d'obtention et l'objet du certificat.
   Un champ obligatoire manquant bloque la production en nommant la donnée.
3. **Placement.** Le texte est centré verticalement dans sa zone, selon l'encre réelle. Il est réduit jusqu'à la taille minimale, puis réparti sur 2 lignes si c'est permis. S'il ne tient pas, la production est **refusée**, jamais tronquée.
4. **Production.**
   - Fond PDF : la page est reprise telle quelle et un calque ReportLab est fusionné par-dessus (pypdf).
   - Fond image : il est inscrit sans déformation dans la page choisie.
   - Le résultat est un PDF d'une page, avec un filigrane « APERÇU » pour les aperçus.
5. **Historique.**
   - Brouillon, puis délivrance qui revérifie la règle, attribue le numéro et régénère le PDF, puis révocation ou remplacement.
   - Chaque document garde sa version de gabarit, l'empreinte du fond, l'empreinte du PDF et ses valeurs.
   - Un remplacement de gabarit **ne modifie aucun document délivré** : même empreinte (tests et pile de production).
   - Un brouillon produit sur une version remplacée n'est plus délivrable.
6. **Éligibilité.**
   - Diplôme : « décision de l'administration », par défaut, car FEBA n'avait aucune règle et en inventer une changerait le métier ; ou « moyenne annuelle minimale », sur 20 et convertie sur 10 au primaire, calculée avec les fonctions existantes.
   - Certificat : « élève inscrit dans une classe pour l'année », par défaut, ou « décision de l'administration ».
   - Les refus sont motivés : moyenne inférieure au seuil, aucune note, pas de classe, fiche inactive, pas d'année en cours.
   - Les notes ne sont jamais modifiées.
   - Une académie **non classée** peut téléverser ses gabarits. La règle de moyenne s'appuie sur le cycle du **niveau** de l'élève.
7. **Numérotation.** On réutilise `DocumentNumberSequence` (verrou en base), avec la **même clé** que le gabarit intégré de l'académie : passer au gabarit téléversé ne remet pas le compteur à 1.
   Sous PostgreSQL, 6 délivrances simultanées donnent 6 numéros distincts.

## D. Audit : défauts confirmés et corrigés

| Défaut (reproduit) | Correction | Test |
|---|---|---|
| **Sauvegardes** : `scripts/backup_files.sh` n'archivait que `/app/media`. Les diplômes délivrés, les gabarits, les dossiers FHA et les rapports mensuels (`private_media`) n'étaient pas sauvegardés. | Archive `media` et `private_media`. La restauration ne remplace que les répertoires présents dans l'archive : une ancienne archive n'efface pas `private_media`. | `test_backup_private_media.py` (scripts exécutés) ; pile de production : archive vérifiée |
| **Sauvegardes** : services `backend` / `postgres` et base `feba` par défaut, absents de `docker-compose.prod.yml`. Les tâches cron documentées échouaient toujours. | Valeurs alignées sur `deploy_feba.sh`, et ajout de `--env-file .env.prod`. | `ScriptDefaultsMatchProductionComposeTests` ; exécution réelle contre la pile de production |
| **Sauvegardes** : avec `pipefail`, la rotation d'un dossier vide arrêtait le script **avant la copie hors site**. | Rotation tolérante. | `BackupReachesOffsiteCopyTests` |
| **Restauration des fichiers** : `rm -rf /app/media` échoue sur un volume monté (« Device or resource busy »). | Les répertoires sont vidés, pas supprimés. | Exécution réelle : gabarit supprimé puis restauré |
| **Restauration de la base** : `DROP` et `CREATE DATABASE` dans un seul `psql -c` sont refusés (bloc transactionnel). Le script s'arrêtait en laissant le backend arrêté. | Deux `-c`, `WITH (FORCE)`, `ON_ERROR_STOP`. | Exécution réelle : donnée modifiée puis restaurée, santé 200 |
| **Éditeur** (trouvé dans Chrome) : un champ ajouté recevait un nom vide, car la liste était remise à zéro avant que React n'applique l'ajout. | Valeur lue avant la mise à jour. | `TemplateEditor.test.jsx` (échoue sans le correctif) |
| **Régression de ma propre refonte** (trouvée par le scénario e2e existant) : l'écran « Documents officiels » n'annonçait plus l'état réel des gabarits. | Cartes d'état par type. | `OfficialDocuments.kind.test.jsx`, e2e `devises-et-documents` |
| **Suppression d'une académie vide** : les fichiers de ses gabarits restaient orphelins. | Fichiers supprimés après la suppression. | `EmptyAcademyDeletionTests` |

Le reste de l'audit (bash 3.2 de macOS) n'est **pas** un défaut de production, mais une fragilité locale :
- `"$PG_DB…"` est lu comme un nom de variable incluant l'octet du « … » ;
- sous bash 5.2 (Linux, serveur), toutes les locales ont été essayées sans erreur ;
- l'écriture a été rendue portable (`${PG_DB}`).

## E. Livraison

Voir `DELIVERY_VERIFICATION_GABARITS.txt` à côté de l'archive : commit, taille, SHA-256, contenu, et vérification depuis une extraction neuve.

**BLOCKED** :
- Hetzner, préproduction, plugNmeet de production (SSH refusé) ;
- SMTP Hostinger ;
- Twilio.

**NOT RUN** :
- impression papier réelle d'un diplôme ;
- partage d'écran ;
- réunion entre réseaux ;
- CDN de production.
