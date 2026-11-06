# Phase 9 — Audit des flux de communication

Périmètre :
- messages du site vitrine ;
- messagerie interne ;
- espace d'envoi d'e-mails ;
- boîte contact (contact@globalfeba.com, Hostinger IMAP) ;
- notifications ;
- erreurs d'affichage.

## 1. Sorties vers des outils externes (recherche dans tout le frontend)

| Endroit | Lien | Verdict |
|---|---|---|
| `pages/admin/Website.jsx`, réponse à un message du site | `mailto:` | **supprimé** → éditeur interne (phase 9) |
| `pages/parent/Children.jsx`, e-mail d'un parent | `mailto:` | **supprimé** → texte sélectionnable |
| `pages/admin/Website.jsx`, WhatsApp (messages et préinscriptions) | `wa.me` | conservé, **seulement** sur le numéro WhatsApp normalisé ; jamais sur le téléphone ; jamais d'envoi automatique |
| `pages/parent/Children.jsx` | `tel:` | conservé (appel, pas un envoi de message) |
| Site public (`site/…` : pied de page, Contact, Accueil, Admissions, Mentions légales, FHA) | `mailto:`, `tel:`, `wa.me` vers FEBA | conservés : c'est le visiteur qui contacte FEBA avec ses propres outils |
| `components/email/EditeurMessage.jsx` | `mailto:` accepté **dans un lien du corps** d'un message | conservé (contenu, pas une action) |

## 2. Flux et règles vérifiés

| Flux | Règle | Preuve |
|---|---|---|
| Réponse à un message du site | contact@ ; service d'envoi existant ; 201 seulement si accepté ; trace dans « Envoyés », reliée au message ; cloisonnement par académie | `test_phase9_communications`, E2E `messages_site` |
| Messagerie interne | destinataires autorisés (phase 7) ; dossiers personnels ; pièces jointes par lien signé ; compteur unique | `test_messagerie_phase7`, `test_audit_messagerie_devoirs_presences`, E2E `messagerie` |
| Compteur du menu | conversations non lues hors archives / corbeille ; mêmes chiffres pour les 5 profils ; mis à jour après lecture | `CompteurMenuTests`, E2E `messages_site` |
| Espace d'envoi d'e-mails | À / Cc / Cci, HTML nettoyé côté serveur, droits | `test_mass_email*`, E2E `emails` |
| Boîte contact | IMAP lu sans marquer lu, synchronisation incrémentale sans doublon, droits explicites | `test_boite_mail_contact` ; en production, synchronisation Celery toutes les 3 min réussie (`{'nouveaux': 0, 'erreur': ''}`) |
| Notifications | compteur des menus soumis à la même attente de portée que la messagerie (course corrigée) | E2E (badge présent à chaque connexion) |
| Erreurs d'affichage | rechargement unique en cas de version périmée ; incident côté serveur | `versionPerimee.test.js`, `SignalementInterfaceTests`, E2E |

## 3. Sécurité

- Aucun identifiant Hostinger ni secret n'est envoyé au frontend : les réponses de l'API ne contiennent que l'adresse publique.
- La nouvelle route POST, `/api/incidents/frontend/`, est ajoutée **délibérément** à la liste des écritures ouvertes aux familles et aux enseignants (`test_balayage_fuites`). Elle ne renvoie qu'un accusé de réception ; son débit est limité et le texte est assaini.
- POST est ouvert sur le ViewSet des messages de contact uniquement pour l'action `reponses` ; la création reste refusée (405, testé).
- Aucune règle de CSP n'est modifiée, aucune protection n'est désactivée et aucune donnée n'est supprimée ou marquée lue pour corriger un affichage.

## 4. Suite de non-régression

| Suite | Résultat |
|---|---|
| Backend complet (PostgreSQL) | **2227 tests, OK** (7 ignorés) |
| Frontend complet (Vitest) | **91 fichiers, 625 tests, OK** |
| Lint | 0 erreur (avertissements existants inchangés) |
| E2E navigateur réel | voir SUIVI_REPRISE_PHASE9.md |
