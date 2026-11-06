# Phase 9 — Messages du site vitrine (« Message reçu »)

Légende des états : **Développé** · **Testé en local** (tests automatisés et navigateur réel sur l'environnement E2E local) · **CI** (GitHub Actions) · **Déployé** · **Testé en production** · **Validé avec un compte réel**.

## 1. Défauts constatés

| # | Défaut | Cause prouvée |
|---|--------|---------------|
| A | « Répondre par email » ouvrait l'application de messagerie de l'ordinateur (ou Gmail) | Le bouton était un lien `mailto:` (`pages/admin/Website.jsx`). Un autre `mailto:` restait dans l'espace parent (`pages/parent/Children.jsx`). |
| B | Le bouton WhatsApp disparaissait sur certains messages ; les deux boutons n'avaient pas la même taille | Le bouton n'était rendu que si un numéro existait ; les classes des deux boutons étaient différentes. En production, 14 messages sur 15 ont un WhatsApp et le plus récent (n° 17) n'en a pas : c'est sur lui que le bouton disparaissait. |

## 2. Correction

### Réponse par e-mail dans FEBA (plus de `mailto:`)

- La fenêtre **« Répondre par email »** est interne à FEBA : `ReponseEmail`, dans `pages/admin/Website.jsx`. Elle contient :
  - les champs À / Cc / Cci, À prérempli avec l'adresse du contact ;
  - l'objet prérempli « Re: <sujet> », sans doubler un « Re: » existant ;
  - le message d'origine, toujours visible ;
  - l'éditeur commun (texte brut ou mise en forme) ;
  - la signature et les pièces jointes.
- Côté serveur, l'action est `POST /api/website/admin/contact-messages/<id>/reponses/`.
  - Elle passe par le service d'envoi existant de la boîte contact (`apps.boite_mail.services.envoyer` → journal d'envoi `mailer`), depuis `contact@globalfeba.com`. Aucun nouveau SMTP, aucune nouvelle dépendance.
  - Les droits sont ceux du message lui-même : queryset cloisonné par académie, donc 404 pour une autre académie, et 403 pour un enseignant, un parent ou un élève.
  - Codes renvoyés :
    - **201** seulement si le serveur d'envoi a accepté le message ;
    - **202** s'il n'a pas accepté (nouvel essai automatique) ;
    - **400** pour un destinataire, un objet ou un corps manquant, une pièce refusée ou plus de 50 destinataires.
  - L'interface n'annonce « acceptée » que sur 201.
- Traçabilité :
  - `MessageMail` reçoit deux champs : `message_site` (lien vers le message d'origine) et `envoye_par`. Migration additive `boite_mail/0002_reponses_site`.
  - La réponse est rangée dans **Envoyés** de la boîte contact (origine `site_vitrine`). Une copie est déposée chez Hostinger quand l'envoi est accepté, comme les autres envois.
  - Le message d'origine est marqué lu.
  - `GET …/reponses/` liste l'historique : date, destinataires, auteur, statut réel et erreur éventuelle. Il est affiché dans la fiche, rubrique « Réponses envoyées depuis FEBA ».
  - La liste expose `nb_reponses`, calculé par annotation, sans requête par ligne.
- La création d'un message de contact par l'administration reste refusée (405) : POST n'est ouvert que pour l'action `reponses`.

### Deux boutons toujours présents (`ActionsContact`)

- Les deux boutons ont la même classe de base et la même largeur minimale (`min-w-[13rem]`). Ils ont aussi la même bordure : l'écart de 2 px mesuré par l'E2E est corrigé.
- **WhatsApp** n'utilise que le champ WhatsApp du contact, jamais le téléphone (`utils/contactsSite.js` → `numeroWhatsApp`).
  - Numéros acceptés :
    - `+` ou `00` suivi de 8 à 15 chiffres ;
    - un numéro béninois à 10 chiffres commençant par `01`, qui reçoit `229`. C'est la seule règle locale, et elle n'est pas ambiguë.
  - Tout autre numéro est refusé, avec sa raison : absent, invalide, ou sans indicatif pays.
  - Quand le numéro est refusé, le bouton reste visible, désactivé, avec la raison en infobulle et en texte.
  - Le message est seulement prérempli : rien n'est envoyé sans action de l'utilisateur.
- **E-mail** ouvre l'éditeur interne. Si l'adresse est invalide, le bouton est désactivé avec la mention « Adresse e-mail absente ou invalide. ».
- Le bouton WhatsApp des **préinscriptions** suit la même règle.

## 3. Preuves

| Contrôle | Où | Résultat |
|---|---|---|
| Normalisation WhatsApp (11 cas) | `utils/contactsSite.test.js` | ✅ |
| Boutons toujours présents, désactivés avec raison, même largeur, aucun `mailto:` ; éditeur prérempli ; envoi multipart ; refus du serveur avec texte conservé ; historique | `pages/admin/Website.contact.test.jsx` (9 tests) | ✅ |
| Réponse envoyée depuis contact@, rangée dans « Envoyés », reliée, auteur, `nb_reponses` ; Cc/Cci (Cci absent des en-têtes) et pièce jointe ; validations sans envoi ; panne du fournisseur → 202 avec erreur, jamais « envoyé » ; cloisonnement 404 / 403 / 401 ; création toujours en 405 | `backend/tests/test_phase9_communications.py` (6 tests, e-mails en mémoire) | ✅ |
| Navigateur réel : dépôt sur le site public, lien `wa.me` normalisé, bouton désactivé avec raison, éditeur prérempli, envoi, historique « Accepté », **aucune redirection externe** (ni `mailto:`, ni Gmail, ni nouvel onglet), réponse visible dans « Envoyés » de la boîte contact, téléphone 375 px sans défilement horizontal | E2E `e2e/ci/scenarios/messages_site.mjs` | ✅ (voir SUIVI_REPRISE_PHASE9.md) |

## 4. État

| Étape | État |
|---|---|
| Développé | ✅ |
| Testé en local | ✅ (backend, frontend, E2E en navigateur réel, e-mails capturés en mémoire) |
| CI | voir SUIVI_REPRISE_PHASE9.md |
| Déployé | voir SUIVI_REPRISE_PHASE9.md |
| Testé en production | lecture seule et transaction annulée uniquement : **aucun e-mail réel envoyé** (aucun destinataire n'a été autorisé) |
| Validé avec un compte réel | **non** : il faut qu'une personne de FEBA réponde à un vrai message depuis la fiche |
