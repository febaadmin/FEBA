# Bugs et anomalies

Trouvés sans signalement préalable, sauf B1.

| ID | Gravité | Anomalie | Cause | Correction | Fichiers | Test | État |
|---|---|---|---|---|---|---|---|
| B1 | Élevée | Faux « identifiants incorrects » | Voir `RAPPORT_AUTHENTIFICATION.md` | Connexion atomique | `useAuth.js`, `LoginPage.jsx` | Oui | Déployé |
| B2 | Élevée | Écriture annulée ou rejetée par une bascule : le serveur l'appliquait, l'écran annonçait un échec, avec risque de doublon | Contrôle de portée sur toutes les méthodes | Lectures seulement | `api/index.js` | `connexion.test.js` | Déployé |
| B3 | Moyenne | Panne d'API affichée comme une liste vide | 168 requêtes sur 57 pages sans traitement | Message global | `erreursRequetes.js` | Oui | Déployé. Le tableau reste vide derrière le message |
| B4 | Moyenne | Texte d'exception renvoyé au client | `str(e)` | Message fixe | `payments/views.py`, `accounts/views.py` | CI | Déployé |
| B5 | Moyenne | `last_login` jamais renseigné | Validation remplacée | `update_last_login` | `accounts/serializers.py` | Oui | PR de livraison |
| B6 | Faible | Bouton d'envoi de réponse sans libellé | Icône seule | `aria-label` | `*/Messages.jsx` | Non | PR de livraison |

## Faux positifs de mes scripts, écartés après vérification

Message enseignant vers élève : interdit par conception. Entrée dans la réponse : retour à la ligne normal. Devoir non vu : élève d'une autre classe.

## Dette relevée

`Messages.jsx` existe en 4 copies identiques de 480 lignes.

## Données réelles à arbitrer, non modifiées

Voir `GUIDE_VALIDATION_HUMAINE.md`.
