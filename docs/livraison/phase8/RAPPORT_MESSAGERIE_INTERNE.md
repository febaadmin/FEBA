# Messagerie interne — phase 8

## 1. Erreur « La ressource demandée est introuvable »
**Reproduction (données de production, lecture seule)** : super administrateur, académie « Faith & Excellence » sélectionnée, destinataire « Christin YESSOUFOU (superadmin) ».
- Réponse HTTP : **404** sur `POST /api/messages/conversations/` (message générique « ressource introuvable »).
- La liste des destinataires (`/api/auth/recipients/`) proposait 162 comptes au super administrateur, dont les **3 autres super administrateurs (sans académie)** et les comptes de l'autre académie ; l'envoi filtrait par l'académie sélectionnée et n'en acceptait que 151.

**Cause racine** : deux règles différentes pour la liste et pour l'envoi.

**Correction** : `allowed_message_recipients(user, school)` sert aux deux, avec la même académie : super administrateur → académie sélectionnée + super administrateurs ; administrateur → son académie + super administrateurs ; enseignant → aussi ses collègues enseignants ; parent et élève inchangés. Test de propriété : pour chaque profil, **tout destinataire proposé est accepté** ; E2E : cas exact de la capture.

Note : la messagerie visible dans les captures est l'**ancienne** (production = `main` = `767ee07`) ; la refonte (PR #102) et la correction ne sont pas encore fusionnées.

## 2. Refonte (PR #102, complétée en phase 8)
- Trois colonnes sur ordinateur (dossiers, conversations, lecture), un panneau à la fois sur mobile avec retour.
- Dossiers : réception, **non lus**, envoyés, brouillons, importants, archivés, corbeille, avec compteurs.
- Liste : avatar, correspondants, objet, aperçu, date, non lu, importance, pièce jointe, **actions rapides** (important, archiver, corbeille), recherche, filtres (non lus, correspondant), **tri**, **actualisation**.
- Lecture : en-tête (objet, participants), bulles différenciées, dates, pièces jointes par liens signés, actions, réponse ; répondre à tous / à l'expéditeur seul dans un groupe.
- Rédaction : plusieurs destinataires en pastilles avec recherche, objet, message, pièces jointes, brouillon, **bouton à états** (prêt, envoi, envoyé seulement après l'enregistrement par le serveur, réessayer) et aide de validation ; double clic sans effet.
- États vides explicatifs avec action « Démarrer une conversation » ; animations sobres, désactivées si l'utilisateur demande moins de mouvement.

## 3. Permissions (côté API)
Participants seuls (404 sinon, identifiant deviné compris) ; destinataires limités par profil et par académie ; pièces jointes par liens signés aux participants ; brouillons privés ; état personnel (archiver, corbeille, supprimer définitivement pour soi seul).

## 4. Tests
| Test | Résultat | Niveau |
|---|---|---|
| Backend `test_messagerie_phase7.py` (17, dont la règle unique, super admin → super admin, administration ↔ super admin, enseignant → collègue, propriété « proposé = accepté », message vide, non lus, tri) | OK | local + CI |
| Frontend `Messagerie.test.jsx` (10, dont état vide, non lus, tri, bouton à états) | OK | local + CI |
| E2E `messagerie` (21 contrôles : pièce jointe téléchargeable, non-lus, dossiers, recherche, brouillon, identifiant deviné → 404, l'administration ne voit pas l'échange, mobile, cas de la capture, 40 destinataires proposés acceptés) | 21/21 | local (Chrome) |

## 5. Non vérifié
Parcours en production avec de vrais comptes : impossible tant que #102 n'est pas fusionnée et déployée (fusion refusée par le contrôle automatique des permissions).
