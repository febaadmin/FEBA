# Audit global — phase 7

## 1. Périmètre audité
- **Frontend** (React/Vite) : routage des cinq profils, écrans Paiements, tableau de bord, E-mails groupés, Messages, Aperçu de bulletin, Transactions carte, page publique ; build de production et types MIME servis.
- **Backend** (Django/DRF) : paiements (liste, filtres, graphique, carte, remboursements), notifications (campagnes, envois, pièces jointes), messagerie, bulletins (aperçu), permissions et isolation par académie.
- **Infrastructure** : image nginx de production (mime.types, `nosniff`, CSP), conteneurs, migrations, Celery beat, journaux, incidents techniques.
- **Données de production**, en lecture seule : cohérence des totaux, recherche, e-mails, messagerie, transactions carte, incidents.
- **Méthode** : reproduction en production quand c'était possible sans compte, tests automatisés (backend PostgreSQL et SQLite, frontend, E2E navigateur sous la CSP de production), balayages API (fuites entre académies, erreurs 500 sur charges hostiles).

## 2. Anomalies découvertes (non signalées) et corrections

| # | Anomalie | Cause | Correction | État |
|---|---|---|---|---|
| 1 | Aperçu PDF cassé **en production seulement** | worker pdf.js en `.mjs`, inconnu de nginx 1.28 → `application/octet-stream` + `nosniff` | build en `.js` ; contrôle MIME du build contre l'image nginx en CI | Corrigé, vérifié en production (PR #99) |
| 2 | Page d'accueil publique : écran d'erreur si l'API répond autre chose qu'une liste | `.filter` sur une réponse non tableau | listes tolérées | Corrigé (PR #99) |
| 3 | Parents ne voyant pas les paiements d'un enfant **sans compte utilisateur** | filtre `student__user__is_active=True` excluait `user` vide | `user` vide ou actif | Corrigé (PR #100) |
| 4 | Page Paiements : liste entière chargée dans le navigateur (`page_size=1000`), recherche limitée à 3 champs, export limité aux lignes chargées | recherche et tri côté client | recherche, filtres, tri, pagination, totaux et export côté serveur | Corrigé (PR #100), vérifié en production (lecture seule) |
| 5 | Recherche sans accents impossible sous SQLite (suite CI) | `translate()` absent de SQLite | `replace()` imbriqués sous SQLite | Corrigé (PR #100) |
| 6 | Messagerie : réponse au « premier autre participant » | modèle à deux personnes | groupes, répondre à tous / à l'expéditeur | Corrigé (PR #102) |
| 7 | Messagerie : quatre copies identiques de 481 lignes | duplication | écran commun | Corrigé (PR #102) |
| 8 | Messagerie : liste en N requêtes par conversation | sérialiseur par objet | requêtes groupées (testé) | Corrigé (PR #102) |
| 9 | Messagerie : nouveau message invisible en changeant de dossier jusqu'à 30 s | `staleTime` global de 30 s | `staleTime: 0` sur la messagerie | Corrigé (PR #102), trouvé par l'E2E |
| 10 | Nouvelles routes : erreur 500 sur un identifiant démesuré | identifiant non borné → débordement PostgreSQL | `request_text.identifiant` | Corrigé avant fusion (PR #101, #102), trouvé par le balayage API |
| 11 | Paiement carte inutilisable pour les académies béninoises | seul prestataire : Stripe | intégration FedaPay | Développé et testé en réseau simulé (PR #103) ; bloqué par le compte marchand |
| 12 | Remboursement carte impossible à constater sans API prestataire | flux pensé pour Stripe | remboursement constaté par l'administration | Corrigé (PR #103) |

## 3. Contrôles sans anomalie (production, lecture seule, 05/11)
- Services sains, 0 migration en attente, aucun incident technique sur 48 h, aucune erreur 500 ni erreur Celery dans les journaux sur 3 h.
- E-mails : 52 envoyés, 0 échec ; aucune campagne ; messagerie vide (0 conversation) ; 0 transaction carte.
- Cohérence page Paiements ↔ graphique : égalité stricte sur 4 combinaisons × 2 académies.
- CSP, X-Frame-Options et `frame-ancestors` inchangés.

## 4. Problèmes restants et risques
| Sujet | Risque | Action |
|---|---|---|
| Tarifs et échéances non saisis en production | attendu et reste à payer non calculables ; paiement en ligne non proposé (aucun tarif publié) | saisie par l'administration |
| Compte marchand FedaPay absent | paiement carte non opérationnel | voir RAPPORT_VALIDATION_PAIEMENTS.md § 4.6 |
| FedaPay : XOF seulement | l'académie FHA (USD) ne peut pas payer en ligne | autre prestataire pour l'USD, ou facturation FHA en XOF (décision métier) |
| Aucun antivirus sur les pièces jointes | document malveillant transmis (contenu contrôlé par signature, jamais exécuté sur le domaine) | ClamAV en service séparé (facultatif) |
| SMTP Hostinger sans accusé de livraison ni retour de rejets asynchrones | un rejet après acceptation n'est pas visible | fournisseur transactionnel avec webhooks (facultatif) |
| Brouillons de messagerie : pièces jointes non conservées | à rejoindre à l'envoi (signalé à l'utilisateur) | amélioration facultative |
| Parcours connectés en production (aperçu d'un vrai bulletin, nouvelle messagerie, nouveaux e-mails) | non vérifiés avec un vrai compte | connexion humaine dans le navigateur intégré |
| Navigateurs Safari et Firefox | non testés | test manuel |
| Points ouverts de la phase 6 (données orphelines, doublons de notes, comptes 191/209, restauration de sauvegarde) | inchangés | décisions humaines (voir SUIVI_REPRISE_PHASE6.md) |
