# Phase 9 — Erreur à l'ouverture de la messagerie et compteur « Messages »

Légende des états : **Développé** · **Testé en local** · **CI** · **Déployé** · **Testé en production** · **Validé avec un compte réel**.

## 1. « Une erreur est survenue » à l'ouverture (ex. /superadmin/academies, Messages)

**Cause prouvée en production.** Les modules JavaScript des anciennes versions n'existent plus après un déploiement :
- `index-CnWUVqyn.js` et `index-DO0mM_KK.js` répondent **404** ;
- le module courant, `index-DCbnfBN7.js`, répond **200**.

Un onglet resté ouvert pendant un déploiement demande l'ancien module au moment d'ouvrir une page. Le chargement échoue et l'écran d'erreur s'affiche. « Réessayer » ne pouvait pas réparer la page, puisqu'il remontait le même composant sans recharger.

Côté serveur, l'API de la messagerie répondait correctement :
- tous les points d'accès de la messagerie répondent 200 pour deux comptes de production ;
- les compteurs sont cohérents.

**Correction (`utils/versionPerimee.js`) :**
- **Rechargement automatique, une seule fois.**
  - Il se déclenche sur l'événement `vite:preloadError` (`main.jsx`) et dans l'`ErrorBoundary`.
  - Il est limité à un rechargement toutes les 30 s par onglet (garde en `sessionStorage`), ce qui empêche toute boucle si le module manque vraiment.
- **L'erreur n'est pas étouffée** (pas de `preventDefault`).
  - L'E2E a montré que l'étouffer faisait résoudre l'import avec `undefined`.
  - React échouait alors sur une erreur trompeuse (« Cannot read properties of undefined (reading 'default') »), enregistrée à tort comme incident.
- **Pour une version périmée, l'écran d'erreur l'explique :** « Une nouvelle version de FEBA a été mise en ligne. Rechargez la page pour continuer. » « Réessayer » recharge alors réellement la page.
- **Les erreurs d'affichage sont tracées côté serveur.**
  - Elles sont envoyées à `POST /api/incidents/frontend/`, ouvert à tout compte connecté.
  - L'accès est limité : 20 signalements par heure et par compte ; le texte est assaini et tronqué à 500 caractères ; la réponse n'est qu'un accusé de réception.
  - La liste des incidents reste réservée au super administrateur.
  - Les versions périmées sont regroupées en un seul incident, de gravité moyenne, sans multiplier les alertes à chaque déploiement.

## 2. Badge « Messages 1 »

**Causes :**
1. **Le menu super administrateur lisait l'ancienne messagerie.** Il appelait `messagesAPI.inbox()` et comptait `!is_read`. Cette route ignore les archives, la corbeille et les conversations masquées, et la messagerie actuelle ne la rafraîchit jamais. Le chiffre ne correspondait donc à rien de visible dans la messagerie.
2. **Les autres profils comptaient des messages, pas des conversations.** Deux messages dans une même conversation affichaient « 2 », alors que la colonne « Réception » affichait 1.
3. **Le badge n'était pas mis à jour après lecture.** La lecture n'invalidait que la liste (`["messagerie","liste"]`), et les clés des menus (`msg-count-*`) étaient différentes.
4. **Course au démarrage, découverte en E2E.** Elle existait déjà pour le compteur des notifications.
   - Juste après la connexion, les compteurs partaient avant que la portée d'académie soit établie.
   - La bascule de portée qui suit les annulait (`ERR_ABORTED`), sans nouvel essai.
   - Le badge restait vide jusqu'au rafraîchissement suivant, jusqu'à 30 s : 3 connexions sur 6 dans la sonde.

**Correction :**
- **Une seule règle et une seule source.**
  - `GET /api/messages/conversations/unread_count/` renvoie `count`, le nombre de conversations non lues hors archives, corbeille et conversations masquées. C'est le même chiffre que le badge « Réception ».
  - Le nombre de messages reste disponible dans `messages`.
- **Un seul crochet pour les cinq menus** : `hooks/useNonLusMessagerie.js`.
  - Sa clé `["messagerie","menu",id]` est invalidée par toute action de la messagerie : lecture, envoi, déplacement.
  - Il est rafraîchi toutes les 30 s et au retour sur l'onglet.
  - Il attend `businessDataEnabled`. Les compteurs de notifications des menus attendent la même condition.
- Le badge est lisible au lecteur d'écran (« {n} conversation(s) non lue(s) ») et plafonné à « 9+ ».
- **Rien n'est supprimé ni marqué lu pour corriger l'affichage.** Un test le vérifie : le message reste non lu en base après archivage puis restauration.

## 3. Preuves

| Contrôle | Où | Résultat |
|---|---|---|
| Détection des erreurs de module (Chrome, Safari, Firefox) ; un seul rechargement | `utils/versionPerimee.test.js` | ✅ |
| Cinq profils (super admin, admin, enseignant, parent, élève) : même règle ; 2 messages = 1 conversation ; ses propres messages ne comptent pas ; lecture par personne ; archives et corbeille exclues sans rien supprimer | `tests/test_phase9_communications.py::CompteurMenuTests` | ✅ |
| Signalement : version périmée regroupée, anonyme refusé (401), limite (429), liste des incidents toujours réservée (403) ; balayages API sans 500 | `SignalementInterfaceTests`, `test_balayage_api`, `test_balayage_fuites` | ✅ |
| Navigateur réel : badge exact pour les **cinq profils** (comparé à l'API) ; mis à jour après lecture **sans recharger** ; module de la page coupé une fois (404) → rechargement unique, page affichée, aucun écran d'erreur, incident « version périmée » enregistré, aucune erreur trompeuse | E2E `messages_site` | ✅ |
| Messagerie complète (envoi, réception, pièce jointe, non-lus, réponse, dossiers, corbeille, restauration, brouillon, confidentialité, mobile) | E2E `messagerie` | ✅ (un échec intermittent sur 3 passages, voir SUIVI_REPRISE_PHASE9.md) |

## 4. État

| Étape | État |
|---|---|
| Développé | ✅ |
| Testé en local | ✅ |
| CI / Déployé / Testé en production | voir SUIVI_REPRISE_PHASE9.md |
| Validé avec un compte réel | **non** : à confirmer en ouvrant la messagerie avec chaque type de compte réel |
