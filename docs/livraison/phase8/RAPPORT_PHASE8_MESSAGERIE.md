# Rapport de la phase 8 — messagerie, espace e-mails, boîte contact

## État initial (05/11/2026, vérifié)
- Production = `main` = `767ee07` (#99, #100, #101 déployées).
- Ouvertes, CI verte : #102 (messagerie), #103 (carte FedaPay), #104 (rapports phase 7). Fusion de #102 refusée en phase 7 par le contrôle automatique des permissions (« fusion sans revue ») : les captures montrent donc l'**ancienne** messagerie.

## Anomalies et causes racines
| Anomalie | Cause racine | Correction | PR |
|---|---|---|---|
| « La ressource demandée est introuvable » à l'envoi d'un message | liste des destinataires et contrôle d'envoi : deux règles différentes (super administrateur, académie sélectionnée) | règle unique `allowed_message_recipients(user, school)` | #102 |
| Messagerie vide et peu lisible | ancienne interface (refonte non déployée) | refonte #102 complétée (non lus, tri, actions rapides, états vides, bouton à états) | #102 |
| « Boîte d'envoi » limitée aux envois de la plateforme | aucune lecture de la boîte réelle | boîte mail IMAP Hostinger complète | #105 |
| Envois SMTP absents de « Envoyés » chez Hostinger | Hostinger ne garde pas les envois SMTP | import des envois FEBA + copie APPEND pour les envois depuis la boîte | #105 |
| Risque : un Cci affiché dans « Cc » si les en-têtes visibles n'ont pas de Cc | Django affiche `cc` quand l'en-tête n'est pas forcé | destinataires supplémentaires en copie cachée | #105 |
| Message-ID différent à chaque reconstruction (nouvel essai, copie) | Message-ID régénéré | Message-ID d'origine conservé | #105 |
| Libellé « E-mails groupés » | — | « Espace d'envoi d'e-mails » / « Email Center » | #105 |

## Fichiers principaux
- `backend/apps/accounts/views.py`, `backend/apps/messaging/services.py`, `frontend/src/pages/shared/Messagerie.jsx` (#102).
- `backend/apps/boite_mail/*` (nouvelle application), `backend/apps/notifications/mailer.py`, `backend/feba_project/settings/base.py`, `backend/feba_project/urls.py`, `frontend/src/pages/admin/BoiteMail.jsx`, `Outbox.jsx`, layouts, `aide/articles.js`, guides (#105).

## Tests
Voir RAPPORT_MESSAGERIE_INTERNE.md et RAPPORT_BOITE_MAIL_CONTACT.md. Synthèse : backend messagerie 17, boîte mail 14, suites e-mail 112 OK ; frontend 589 à 595 selon la branche, tous verts ; E2E messagerie 21/21 (Chrome) ; boîte réelle vérifiée en lecture seule (45 messages analysés, 0 erreur).

## Niveaux de validation
| Élément | Développé | Testé localement | CI | Déployé | Testé en production | Fournisseur réel |
|---|---|---|---|---|---|---|
| Correctif d'envoi + refonte messagerie | oui | oui | oui (#102) | **non** (fusion à autoriser) | non | — |
| Boîte mail contact | oui | oui | en cours (#105) | **non** | lecture seule du code d'analyse | connexion IMAP réelle vérifiée en lecture seule |
| Espace d'envoi d'e-mails (renommage) | oui | oui | en cours (#105) | non | non | — |
