# Messagerie interne et e-mails — phase 7

Deux outils distincts : la **messagerie interne** (échanges entre comptes FEBA) et les **e-mails groupés** (envoi d'e-mails à des adresses internes ou externes au nom de l'académie). Ils partagent la validation des pièces jointes (`apps/notifications/attachments.py`) et le stockage privé.

## 1. E-mails groupés (chantier D) — PR #101

### Audit de l'existant
- Envoi par académie et par profil, un message par destinataire, suivi par destinataire, file Celery (`send_campaign`), reprise et nouvelles tentatives automatiques (beat 5 et 10 min), jeton anti double-clic, plafond de destinataires et de campagnes par heure, pièces jointes contrôlées (extension, signature binaire, tailles), contenu archivé.
- Manquaient : adresses saisies librement, Cc, Cci, mise en forme, brouillons, recherche des envois, statut de rejet.
- Fournisseur : SMTP Hostinger (`smtp.hostinger.com:587`, TLS), expéditeur `contact@globalfeba.com`. Aucun accusé de livraison n'est fourni par ce fournisseur : le statut le plus avancé est « Envoyé au fournisseur ».

### Architecture
- **Champs À / Cc / Cci** : adresses saisies (validées) ou comptes de l'académie (identifiant vérifié dans le périmètre de l'académie, sinon refus global). Doublons : une seule copie (priorité À > Cc > Cci > profils).
- **Mode individuel** (par défaut) : chaque destinataire reçoit son message ; aucune adresse visible.
- **Mode message commun** : chaque destinataire reçoit sa copie avec les en-têtes `To` (À) et `Cc` (Cc) **affichés** ; l'enveloppe SMTP ne contient que lui. Une adresse en Cci n'apparaît dans aucun en-tête. Profils et membres ajoutés restent toujours individuels. Champ `EmailDelivery.en_tetes_visibles`.
- **Mise en forme** : éditeur sans dépendance (gras, italique, souligné, listes, liens, effacer ; collage en texte brut) ou texte brut. HTML **nettoyé côté serveur** par liste blanche (`nh3`, nouvelle dépendance), aucun attribut d'événement, aucun style, aucune image distante, liens http/https/mailto avec `rel="noopener noreferrer"` ; version texte dérivée. L'aperçu affiche le HTML nettoyé par le serveur.
- **Brouillons** (`BrouillonEmail`, `PieceJointeBrouillon`) privés à leur auteur (404 pour les autres), pièces jointes en stockage privé, reprise, envoi depuis le brouillon (pièces incluses, brouillon supprimé). **Signature** personnelle (`SignatureEmail`).
- **Envoyés** : recherche (objet, nom, adresse), filtres statut et dates, rapport (champ de chaque destinataire, contenu, pièces jointes). Statuts : En attente, En cours d'envoi, Envoyé au fournisseur, Envoyé avec des échecs, Échec ; destinataire « Rejeté par le serveur d'envoi » après épuisement des nouvelles tentatives sur un refus SMTP (le refus reste relançable à la main).
- **Antivirus** : aucun moteur antivirus n'est déployé sur l'infrastructure. Mécanismes en place : liste blanche d'extensions, contrôle de la signature binaire (le contenu doit correspondre à l'extension), tailles bornées, fichiers jamais servis publiquement. Recommandation : ClamAV en service séparé si l'on accepte des documents Office de l'extérieur.

### Tests
- Backend `tests/test_emails_composition.py` (16) : en-têtes et **enveloppe SMTP réelle de chaque copie** (individuel, commun, Cci invisible, profils individuels), doublons, adresses invalides, compte d'une autre académie, nettoyage HTML (script, onclick, image, javascript:, iframe), version texte, brouillon avec pièce jointe puis envoi, brouillon privé, signature, recherche et filtres des envois, rejet définitif, double soumission. Suites e-mail existantes : 98 OK (PostgreSQL), 81 OK (SQLite).
- Frontend : compositeur, aperçu HTML serveur, brouillon, envoyés (13 tests).
- E2E `emails` (21 contrôles) : composition complète dans le navigateur, brouillon avec pièce jointe repris puis envoyé, aperçu, envoi, rapport, recherche, 390 px.

## 2. Messagerie interne (chantier E) — PR #102

### Audit de l'existant
- Une conversation entre deux personnes ; la réponse partait au « premier autre participant » (incorrect à plus de deux).
- Aucun état personnel (archives, importants, corbeille), aucun brouillon, une seule pièce jointe.
- Quatre copies identiques (481 lignes chacune) de l'écran pour admin, enseignant, parent, élève.
- Liste : plusieurs requêtes SQL par conversation.

### Architecture
- `EtatConversation` (par participant) : dossier réception / archives / corbeille, important, lecture (`lu_le` pour les messages de groupe), suppression définitive **pour soi seul** — aucune donnée effacée, les autres participants conservent l'échange. Un nouveau message ramène la conversation dans la boîte de réception des autres.
- Plusieurs destinataires, tous contrôlés par `allowed_message_recipients` dans l'académie (refus global 404 sinon). Répondre à tous, ou à l'expéditeur seul (tête-à-tête séparé, invisible du groupe).
- Pièces jointes multiples (`PieceJointeMessage`, au plus 5), dossier privé `messages/` refusé par nginx, servies par lien signé aux seuls participants.
- Brouillons (`BrouillonMessage`) privés ; recherche (objet, contenu, personne), filtres non lus, correspondant, dates ; compteurs par dossier ; liste en requêtes groupées (nombre de requêtes indépendant du nombre de conversations, testé).
- Notifications existantes (cloche) créées pour chaque destinataire ; actualisation sans rechargement (liste 15 s, fil ouvert 8 s, compteurs 15 s, `staleTime: 0` : le cache global de 30 s masquait un message arrivé en changeant de dossier — trouvé par l'E2E).
- Écran unique `pages/shared/Messagerie.jsx` : trois colonnes sur ordinateur, un panneau à la fois sur mobile, bulles différenciées, avatars, états vides et erreurs explicites, animations sobres.

### Permissions (vérifiées côté API)
| Règle | Test |
|---|---|
| Seuls les participants lisent, répondent, archivent, marquent, déplacent (404 sinon, identifiant deviné compris) | `test_conversation_inaccessible_aux_non_participants`, E2E |
| L'administration ne lit pas les échanges des autres | idem |
| Destinataires limités par profil et par académie | `test_un_destinataire_non_autorise_bloque_tout_l_envoi` |
| Pièces jointes : liens signés remis aux seuls participants | `test_plusieurs_pieces_jointes_liens_signes_pour_les_participants`, E2E téléchargement |
| Brouillons privés | `test_brouillons_prives_et_envoi` |

### Tests
- Backend `tests/test_messagerie_phase7.py` (11) + messagerie existante + balayage de fuites et balayage API (aucune erreur 500) : OK PostgreSQL et SQLite.
- Frontend `Messagerie.test.jsx` (8).
- E2E `messagerie` réécrit (19 contrôles).

## 3. Anomalie trouvée par le balayage API
Un identifiant démesuré (10³⁰) dans les nouvelles routes atteignait PostgreSQL (erreur 500). Corrigé dans les deux PR avec `request_text.identifiant` (bornes de clé).
