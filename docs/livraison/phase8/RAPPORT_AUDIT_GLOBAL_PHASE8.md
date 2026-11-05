# Audit global — phase 8

## Modules audités
Messagerie interne (règles de destinataires, interface, permissions), envoi d'e-mails (mailer, en-têtes, Message-ID), boîte professionnelle (DNS, fournisseur, IMAP), infrastructure de messagerie du domaine, état Git / PR / production.

## Anomalies découvertes et corrections
| # | Anomalie | Gravité | Correction | État |
|---|---|---|---|---|
| 1 | Envoi de message interne en 404 pour des destinataires proposés (super administrateur) | élevée | règle unique liste/envoi | corrigé (#102), à déployer |
| 2 | Enseignants ne pouvant pas écrire à leurs collègues | moyenne | collègues de l'académie autorisés | corrigé (#102) |
| 3 | Copie cachée potentiellement visible dans « Cc » (en-têtes affichés sans Cc) | élevée (confidentialité) | copie cachée réelle | corrigé (#105) |
| 4 | Message-ID régénéré à chaque nouvel essai : doublons indétectables chez le destinataire | moyenne | Message-ID conservé | corrigé (#105) |
| 5 | Envois de FEBA absents du dossier « Envoyés » du fournisseur | moyenne | import + APPEND | corrigé (#105) |
| 6 | DMARC `p=none` : usurpation du domaine non bloquée | moyenne | recommandation : `p=quarantine` après lecture des rapports (action DNS humaine) | documenté |
| 7 | Sélecteur DKIM `hostingermail-b` à clé vide | faible | sans effet (clé révoquée) | documenté |

## Contrôles sans anomalie
Production saine (`767ee07`) : services en bonne santé, aucune erreur 500 après le dernier déploiement, IMAP et SMTP Hostinger joignables depuis le serveur.

## Anomalies restantes et risques
- Fusion des PR #102, #103, #104, #105 : bloquée par le contrôle automatique des permissions (autorisation humaine).
- Paiement carte : compte marchand FedaPay (voir phase 7).
- Tarifs et échéances non saisis ; points ouverts de la phase 6 (données orphelines, doublons de notes, comptes 191/209, restauration de sauvegarde).
- Navigateurs : seul Chrome testé.
